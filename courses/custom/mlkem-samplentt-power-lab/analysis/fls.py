"""Fresh-seed FLS power experiment; never interpret a negative test as a CT proof."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4
import numpy as np
from scipy.stats import ks_2samp, ttest_ind
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from analysis import distinguisher as core
from analysis.ground_truth import generated_seed, ground_truth, output_digest, MAX_ITER
from analysis.proof import exact_recall_bounds, exact_label_permutation_p

ROOT = Path(__file__).resolve().parents[1]


def source_hashes():
    names = ('analysis/fls.py', 'analysis/distinguisher.py', 'analysis/proof.py',
             'analysis/ground_truth.py', 'capture/fls.py', 'capture/cohort.py',
             'capture/hardware.py', 'capture/records.py', 'firmware/build.py',
             'firmware/common/main.c', 'reference/tempo/src/algorithm_a1.c')
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}


def make_plan(path, per_class=128, excluded=()):
    """Fresh balanced labels, valid neighbour, and matched output-fill position.

    A1 ALWAYS visits 280 pairs, including the suffix after the output is full.
    Matching fill position does not fix suffix values or the full validity count.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError('Load the saved FLS plan instead of replacing it.')
    if type(per_class) is not int or per_class < 16:
        raise ValueError('Use at least 16 independent seeds per class.')
    plan = dict(schema=1, experiment='fls-first-candidate-v1', variant='fls',
                id=uuid4().hex, x=0, y=0, candidate_index=0, second_candidate_valid=True,
                pair_iterations=MAX_ITER, candidates_to_fill=320,
                per_class=per_class, repeats=1, order_seed=42031, model_seed=20261029,
                cohorts={}, excluded_seeds=sorted(set(excluded)),
                primary='one physical capture per fresh test seed',
                seed_policy='balanced candidate zero; candidate one valid; output fills on candidate 320; all 560 candidates still visited')
    forbidden = set(excluded)
    for role in ('development', 'holdout'):
        selected = [[], []]
        for i in range(1_000_000):
            seed = generated_seed(i, f"fls:{plan['id']}:{role}")
            # A0's prefix gives the same first-fill position more cheaply.
            truth = ground_truth(seed)
            label = int(truth.valid[0])
            if (seed.hex() not in forbidden and truth.complete and truth.valid[1]
                    and truth.candidates_to_fill == 320 and len(selected[label]) < per_class):
                selected[label].append(seed.hex())
                forbidden.add(seed.hex())
            if min(map(len, selected)) == per_class:
                break
        else:
            raise RuntimeError('Seed search exhausted; no partial plan written.')
        plan['cohorts'][role] = sorted(selected[0]+selected[1])
    plan['sha256'] = core.digest(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(plan, stream, indent=2)
    return plan


def validate_plan(plan):
    content = {k: v for k, v in plan.items() if k != 'sha256'}
    if core.digest(content) != plan.get('sha256'):
        raise ValueError('FLS plan changed.')
    if (plan.get('experiment') != 'fls-first-candidate-v1' or plan.get('variant') != 'fls'
            or plan.get('repeats') != 1 or plan.get('pair_iterations') != MAX_ITER
            or plan.get('candidates_to_fill') != 320 or (plan.get('x'), plan.get('y')) != (0, 0)):
        raise ValueError('Not the declared FLS experiment.')
    sets = [plan['cohorts'][role] for role in ('development', 'holdout')]
    if (any(len(s) != 2*plan['per_class'] or len(s) != len(set(s)) for s in sets)
            or set(sets[0]) & set(sets[1])
            or set(sets[0]+sets[1]) & set(plan['excluded_seeds'])):
        raise ValueError('Missing, duplicate, overlapping, or previously used FLS seeds.')


def signature(record):
    result = core.signature(record)
    result.update(variant=record.metadata['firmware_build'].get('variant'),
                  target_clock_hz=record.metadata['settings']['target_clock_hz'],
                  adc_policy=record.metadata.get('fls_adc_policy'))
    return result


def cohort_arrays(records, plan, role):
    validate_plan(plan)
    if role not in ('development', 'holdout') or not records:
        raise ValueError('Need a nonempty declared FLS cohort.')
    sig = signature(records[0])
    if (sig['variant'] != 'fls' or sig['profile'] != 'measurement'
            or not sig['adc_policy'] or sig['adc_policy']['clip_errors_disabled'] is not False):
        raise ValueError('Need representative FLS firmware with clipping checks enabled.')
    grouped = {}
    for r in records:
        m, t = r.metadata, r.truth
        if m.get('synthetic') is not False or m.get('backend') != 'chipwhisperer':
            raise ValueError('Physical FLS evaluation excludes synthetic/mock captures.')
        if signature(r) != sig:
            raise ValueError('Mixed capture settings or firmware profiles.')
        if m.get('plan_sha256') != plan['sha256'] or m.get('cohort') != role:
            raise ValueError('Capture belongs to another plan/cohort.')
        seed = t['seed']
        if seed not in plan['cohorts'][role] or seed in grouped or m.get('repeat') != 0:
            raise ValueError('Unexpected seed, duplicate, or repeat.')
        expected = ground_truth(bytes.fromhex(seed), plan['x'], plan['y'], 'fls').to_dict()
        if (t != expected or not t['complete'] or not t['valid'][1]
                or t['pair_iterations'] != MAX_ITER or t['candidates_to_fill'] != 320):
            raise ValueError('FLS ground truth or declared workload mismatch.')
        if m.get('verification_digest') != output_digest(t['coefficients']).hex():
            raise ValueError('Polynomial digest mismatch.')
        if (r.wave.ndim != 1 or len(r.wave) != sig['samples'] or not np.isfinite(r.wave).all()
                or not np.isfinite(m['duration_seconds']) or m['duration_seconds'] <= 0):
            raise ValueError('Invalid waveform or timing.')
        grouped[seed] = r
    seeds = plan['cohorts'][role]
    if set(grouped) != set(seeds):
        raise ValueError('Incomplete FLS cohort: resume capture; never drop failed seeds.')
    ordered = [grouped[seed] for seed in seeds]
    y = np.asarray([int(r.truth['valid'][0]) for r in ordered])
    if sum(y) != plan['per_class']:
        raise ValueError('Unbalanced FLS ground truth.')
    return (np.asarray([r.wave for r in ordered]), y,
            np.asarray([[r.metadata['duration_seconds']] for r in ordered]), seeds, sig)


def develop(records, plan):
    """All window and point selection uses development seeds only."""
    X, y, _, _, sig = cohort_arrays(records, plan, 'development')
    n = X.shape[1]
    windows = core.window_grid(n, widths=tuple(w for w in (512, 2048, 8192) if w <= n), step=1024)
    cv = StratifiedKFold(4, shuffle=True, random_state=plan['model_seed'])
    search = []
    for a, b in windows:
        values = cross_val_score(core.pipeline(), X[:, a:b], y, cv=cv,
                                 scoring='balanced_accuracy', n_jobs=1)
        search.append(dict(start=a, stop=b, mean_cv_ba=float(values.mean())))
    winner = min(search, key=lambda s: (-s['mean_cv_ba'], s['stop']-s['start'], s['start']))
    return dict(plan_sha256=plan['sha256'], signature=sig,
                development_fingerprint=core.records_fingerprint(records),
                best_window=[winner['start'], winner['stop']], search=search,
                caution='Window search makes this CV maximum optimistic; use the fresh test for performance.')


def load_frozen(path):
    record = core.load_frozen(path)
    if record.get('kind') != 'fls-first-candidate-v1' or record.get('fls_sources') != source_hashes():
        raise ValueError('FLS model/source changed; start a new experiment.')
    return record


def freeze(path, records, plan, localization):
    path = Path(path)
    X, y, t, seeds, sig = cohort_arrays(records, plan, 'development')
    if path.exists():
        old = load_frozen(path)
        if old['plan_sha256'] != plan['sha256'] or old['development_fingerprint'] != core.records_fingerprint(records):
            raise ValueError('The frozen FLS training data/plan changed.')
        return old
    if (sig['firmware_sha256'] != localization['measurement_firmware_sha256']
            or sig['offset'] != localization['offset'] or sig['samples'] != localization['samples']):
        raise ValueError('Capture does not match its saved FLS localization.')
    selection = develop(records, plan)
    a, b = selection['best_window']
    result = dict(schema=1, kind='fls-first-candidate-v1', plan_sha256=plan['sha256'],
                  signature=sig, development_seeds=seeds, selection=selection, roi=[a, b],
                  models=dict(power=core._linear_fit(X[:, a:b], y), timing=core._linear_fit(t, y, False)),
                  source_sha256=source_hashes()['analysis/distinguisher.py'], fls_sources=source_hashes(),
                  development_fingerprint=core.records_fingerprint(records),
                  localization=localization, score_threshold=0.,
                  constant_time_verified=False, frozen_utc=datetime.now(timezone.utc).isoformat())
    result['sha256'] = core.digest(result)
    with path.open('x') as stream:
        json.dump(result, stream, indent=2)
    return result


def timing_diagnostics(y, durations, core_hz):
    cycles = np.asarray(durations).reshape(-1)*core_hz
    a, b = cycles[y == 0], cycles[y == 1]
    # Handle exactly constant quantized counters without NaN/zero-variance tests.
    constant = np.ptp(a) == 0 and np.ptp(b) == 0
    welch_p = float(a[0] == b[0]) if constant else float(ttest_ind(a, b, equal_var=False).pvalue)
    ks_p = float(ks_2samp(a, b, method='asymp').pvalue)
    return dict(unit='target CPU cycles inferred from whole-operation trigger duration',
                reject_mean=float(a.mean()), accept_mean=float(b.mean()),
                accept_minus_reject=float(b.mean()-a.mean()),
                reject_range=[float(a.min()), float(a.max())],
                accept_range=[float(b.min()), float(b.max())],
                welch_p=welch_p, ks_p=ks_p,
                timing_association_detected=bool(min(welch_p, ks_p) < .025),
                criterion='two timing tests; Bonferroni threshold 0.025 each',
                caution='No detected difference does not prove constant time or rule out local timing leakage.')


def evaluate(records, plan, frozen):
    if frozen.get('fls_sources') != source_hashes():
        raise ValueError('FLS analysis/capture sources changed since freeze.')
    if frozen['plan_sha256'] != plan['sha256']:
        raise ValueError('Wrong FLS plan/model.')
    if set(frozen['development_seeds']) & set(plan['cohorts']['holdout']):
        raise ValueError('Training/test overlap.')
    if any(r.metadata.get('frozen_sha256') != frozen['sha256'] for r in records):
        raise ValueError('Test must be captured after this FLS model was frozen.')
    X, y, t, seeds, sig = cohort_arrays(records, plan, 'holdout')
    if sig != frozen['signature']:
        raise ValueError('Test firmware or acquisition conditions changed.')
    a, b = frozen['roi']
    report = dict(schema=1, experiment='fls-first-candidate-v1', n_test_seeds=len(seeds),
                  plan_sha256=plan['sha256'], frozen_sha256=frozen['sha256'],
                  test_fingerprint=core.records_fingerprint(records), metrics={},
                  constant_time_verified=False)
    scores = {}
    for name, features in [('power', X[:, a:b]), ('timing', t)]:
        scores[name] = score = core._score(frozen['models'][name], features)
        predicted = score >= frozen['score_threshold']
        class_bounds, bounds = exact_recall_bounds(y, predicted)
        report['metrics'][name] = dict(correct=int(sum(predicted == y)),
            balanced_accuracy=float(balanced_accuracy_score(y, predicted)),
            balanced_accuracy_95ci=bounds, recall_intervals_simultaneous_95=class_bounds,
            roc_auc=float(roc_auc_score(y, score)),
            confusion_matrix_reject_accept=confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
            exact_test_label_permutation_p=exact_label_permutation_p(y, predicted))
    report['timing'] = timing_diagnostics(y, t, sig['target_clock_hz'])
    p = report['metrics']['power']
    report['power_association_supported'] = bool(p['balanced_accuracy_95ci'][0] > .5
                                                and p['exact_test_label_permutation_p'] < .05)
    report['decision'] = ('Fresh-test power discrimination is supported for this FLS build.'
                          if report['power_association_supported'] else
                          'This experiment did not establish a single-trace FLS power distinguisher.')
    report['limits'] = [
        'Known public seeds; first candidate only; balanced, workload-conditioned population; warm target.',
        'Source uses fixed loops; neither timing tests nor this classifier certify constant-time machine code.',
        'Whole-operation timing tests cannot exclude local timing variation or prove the physical leakage mechanism.',
        'A successful classifier is not secret-key recovery; a negative result is not proof of power resistance.',
        'Do not retune using this test. A changed window/model/build needs a fresh plan and test.',
        'The top-level A1 implementation differs from the upstream pqm4 A1 copy.'
    ]
    return report, X, y, t, scores


def result_figure(report, y, t, scores, core_hz):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.4), layout='constrained')
    for label, color, title in [(0, '#c66f65', 'Actual reject'), (1, '#427fac', 'Actual accept')]:
        axes[0].hist(scores['power'][y == label], bins=24, alpha=.65, color=color, label=title)
    axes[0].axvline(0, color='black', linestyle='--')
    axes[0].set(title='Frozen FLS power score', xlabel='Score (accept if ≥ 0)', ylabel='Independent test seeds')
    axes[0].legend(fontsize=8)
    cycles = t.reshape(-1)*core_hz
    # Center only for display; tests and the classifier use original durations.
    center = float(cycles.mean())
    for label, color in [(0, '#c66f65'), (1, '#427fac')]:
        axes[1].scatter(np.flatnonzero(y == label), cycles[y == label]-center, s=12, alpha=.65, color=color)
    axes[1].set(title='Whole-operation trigger duration', xlabel='Test seed (sorted order)', ylabel=f'CPU cycles minus {center:.2f}')
    cm = np.array(report['metrics']['power']['confusion_matrix_reject_accept'])
    axes[2].imshow(cm, cmap='Blues', vmin=0, vmax=max(1, cm.max()))
    for (i, j), value in np.ndenumerate(cm):
        axes[2].text(j, i, str(value), ha='center', va='center', color='white' if value > cm.max()/2 else 'black')
    axes[2].set(xticks=[0, 1], yticks=[0, 1], xticklabels=['Reject', 'Accept'], yticklabels=['Reject', 'Accept'],
                xlabel='Predicted', ylabel='Actual', title='One trace per fresh seed')
    return fig
