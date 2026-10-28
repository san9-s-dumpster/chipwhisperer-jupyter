"""Predeclared VT experiment: seed-separated development, frozen fit, fresh test.

These tools test association with candidate-zero validity in a conditioned seed
population. They do not establish that a particular branch causes the leakage,
recover a secret, or establish representative attack accuracy on random seeds.
"""
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from analysis.ground_truth import generated_seed, ground_truth, output_digest


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def make_plan(path, per_class=128, repeats=2, pair_iterations=160, x=0, y=0, excluded=()):
    """Balance label zero; fix label one and exact final workload in both classes."""
    path = Path(path)
    if path.exists():
        raise FileExistsError('reuse the saved plan with load_plan; never silently regenerate it')
    if per_class < 16 or repeats < 1 or not 129 <= pair_iterations <= 168:
        raise ValueError('need >=16 seeds/class, >=1 repeat, and a three-block workload')
    plan = dict(schema=2, experiment='vt-candidate-zero-v2', id=uuid.uuid4().hex,
                variant='variable_time', candidate_index=0, second_candidate_valid=True,
                pair_iterations=pair_iterations, candidates_to_fill=2*pair_iterations,
                x=x, y=y, per_class=per_class, repeats=repeats,
                seed_policy='balanced first candidate, second valid, exact total pairs, final candidate fills output',
                primary='one trace per unseen seed (repeat 0)', secondary='mean of repeats per unseen seed',
                order_seed=42017, model_seed=20261028, cohorts={}, excluded_seeds=sorted(set(excluded)))
    forbidden = set(excluded)
    for role in ('development', 'holdout'):
        selected = [[], []]
        for i in range(1_000_000):
            seed = generated_seed(i, f"{plan['id']}:{role}")
            truth = ground_truth(seed, x, y)
            label = int(truth.valid[0])
            if (seed.hex() not in forbidden and truth.complete and truth.valid[1]
                    and truth.pair_iterations == pair_iterations and truth.candidates_to_fill == 2*pair_iterations
                    and len(selected[label]) < per_class):
                selected[label].append(seed.hex())
                forbidden.add(seed.hex())
            if min(map(len, selected)) == per_class:
                break
        else:
            raise RuntimeError('seed search exhausted; no partial plan written')
        plan['cohorts'][role] = sorted(selected[0]+selected[1])
    plan['sha256'] = digest(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(plan, f, indent=2)
    return plan


def load_plan(path):
    plan = json.loads(Path(path).read_text())
    expected = plan.pop('sha256')
    if digest(plan) != expected:
        raise ValueError('experiment plan changed')
    plan['sha256'] = expected
    return plan


def signature(record):
    m, s = record.metadata, record.metadata['settings']
    b = m['firmware_build']
    return dict(firmware_sha256=b['firmware_sha256'], profile=b.get('profile', 'measurement'),
                source_commit=b['source_commit'], platform=s['target_platform'], serial=s['scope_serial'],
                adc_frequency_hz=m['adc_frequency_hz'], adc_multiplier=s['adc_multiplier'],
                offset=s['offset'], samples=s['samples'], gain_db=s['gain_db'],
                stream_mode=s['stream_mode'], baud=s['baud'], adc_bits=m.get('adc_bits'),
                wave_units=m.get('wave_units'), chipwhisperer_version=m['chipwhisperer_version'])


def cohort_arrays(records, plan, role, averaged=False):
    """Fail closed on missing, duplicate, contaminated, or mixed-condition trials."""
    if role not in ('development', 'holdout') or not records:
        raise ValueError('need a nonempty declared cohort')
    grouped = {}
    sig = signature(records[0])
    for r in records:
        m, t = r.metadata, r.truth
        if m.get('synthetic') is not False or m.get('backend') != 'chipwhisperer':
            raise ValueError('physical evaluation requires ChipWhisperer records; mock data are excluded')
        if signature(r) != sig or sig['profile'] != 'measurement':
            raise ValueError('mixed conditions or calibration traces; reacquire consistently')
        if m.get('plan_sha256') != plan['sha256'] or m.get('cohort') != role:
            raise ValueError('record does not belong to this plan/cohort')
        seed = t['seed']
        if seed not in plan['cohorts'][role]:
            raise ValueError('unexpected seed')
        expected = ground_truth(bytes.fromhex(seed), plan['x'], plan['y']).to_dict()
        if t != expected or not t['complete'] or t['pair_iterations'] != plan['pair_iterations'] or t['candidates_to_fill'] != plan['candidates_to_fill'] or not t['valid'][1]:
            raise ValueError('ground truth or workload does not match the declared experiment')
        if m['verification_digest'] != output_digest(t['coefficients']).hex():
            raise ValueError('polynomial verification mismatch')
        rep = m['repeat']
        if rep not in range(plan['repeats']) or rep in grouped.setdefault(seed, {}):
            raise ValueError('unexpected or duplicate repeat')
        if len(r.wave) != sig['samples'] or not np.isfinite(r.wave).all():
            raise ValueError('bad waveform')
        grouped[seed][rep] = r
    seeds = plan['cohorts'][role]
    if set(grouped) != set(seeds) or any(len(g) != plan['repeats'] for g in grouped.values()):
        raise ValueError('incomplete cohort: resume acquisition; do not silently drop failed seeds')
    waves, labels, timing = [], [], []
    for seed in seeds:
        rs = [grouped[seed][rep] for rep in range(plan['repeats'])] if averaged else [grouped[seed][0]]
        waves.append(np.mean([r.wave for r in rs], axis=0))
        labels.append(int(rs[0].truth['valid'][0]))
        timing.append([np.mean([r.metadata['duration_seconds'] for r in rs])])
    return np.asarray(waves), np.asarray(labels), np.asarray(timing), seeds, sig


class SelectPOI(TransformerMixin, BaseEstimator):
    """Welch-score sample selection, fitted separately inside every CV fold."""
    def __init__(self, count=16, spacing=4):
        self.count, self.spacing = count, spacing

    def fit(self, X, y):
        a, b = X[y == 0], X[y == 1]
        score = np.abs(a.mean(0)-b.mean(0)) / np.sqrt(a.var(0)/len(a)+b.var(0)/len(b)+1e-12)
        chosen = []
        for j in np.argsort(-score, kind='stable'):
            if all(abs(int(j)-p) >= self.spacing for p in chosen):
                chosen.append(int(j))
                if len(chosen) == self.count:
                    break
        self.indices_ = np.array(sorted(chosen))
        return self

    def transform(self, X):
        return X[:, self.indices_]


def pipeline():
    return make_pipeline(SelectPOI(), StandardScaler(),
                         LogisticRegression(C=0.1, class_weight='balanced', max_iter=2000))


def window_grid(samples, start=0, stop=None, widths=(128, 256, 512, 1024), step=128):
    stop = samples if stop is None else stop
    if not 0 <= start < stop <= samples:
        raise ValueError('window search must lie within the captured window')
    return [(a, a+w) for w in widths for a in range(start, stop-w+1, step)]


def develop(records, plan, windows):
    waves, y, _, seeds, sig = cohort_arrays(records, plan, 'development')
    if not windows or any(not 0 <= a < b <= waves.shape[1] for a,b in windows):
        raise ValueError('invalid window grid')
    cv = StratifiedKFold(4, shuffle=True, random_state=plan['model_seed'])
    search = []
    for a,b in windows:
        scores = cross_val_score(pipeline(), waves[:,a:b], y, cv=cv, scoring='balanced_accuracy', n_jobs=1)
        search.append(dict(start=int(a), stop=int(b), mean_cv_ba=float(scores.mean()), folds=scores.tolist()))
    # Stable tie break: narrowest and then earliest. This is development only.
    winner = min(search, key=lambda s: (-s['mean_cv_ba'], s['stop']-s['start'], s['start']))
    return dict(schema=2, plan_sha256=plan['sha256'], signature=sig, development_seeds=seeds,
                best_window=[winner['start'], winner['stop']], search=search,
                caution='Selected CV score is optimistic after window search. Only the untouched holdout estimates final performance.')


def _linear_fit(X, y, use_poi=True):
    model = pipeline() if use_poi else make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    model.fit(X, y)
    scaler, logistic = model[-2], model[-1]
    indices = model[0].indices_ if use_poi else np.arange(X.shape[1])
    return dict(indices=indices.tolist(), mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist(),
                coefficient=logistic.coef_[0].tolist(), intercept=float(logistic.intercept_[0]))


def freeze(path, development_records, plan, selection):
    """Store only numeric coefficients/JSON; no pickle and no holdout dependency."""
    path = Path(path)
    if path.exists():
        raise FileExistsError('frozen model exists; load it rather than overwrite it')
    if selection['plan_sha256'] != plan['sha256']:
        raise ValueError('selection belongs to another experiment')
    a,b = selection['best_window']
    fits = {}
    for name, average in (('single_trace', False), ('mean_repeats', True)):
        X,y,t,seeds,sig = cohort_arrays(development_records,plan,'development',average)
        if sig != selection['signature']:
            raise ValueError('development acquisition changed')
        shuffled = np.random.default_rng(plan['model_seed']).permutation(y)
        fits[name] = dict(power=_linear_fit(X[:,a:b],y), timing=_linear_fit(t,y,False),
                          shuffled_labels=_linear_fit(X[:,a:b],shuffled))
    record = dict(schema=2, plan_sha256=plan['sha256'], signature=sig,
                  development_seeds=seeds, roi=[a,b], models=fits,
                  decision_threshold=0.5, primary='single_trace',
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  development_fingerprint=records_fingerprint(development_records),
                  selection=selection)
    record['sha256'] = digest(record)
    with path.open('x') as f:
        json.dump(record,f,indent=2)
    return record


def load_frozen(path):
    record = json.loads(Path(path).read_text())
    expected = record.pop('sha256')
    if digest(record) != expected:
        raise ValueError('frozen model changed')
    record['sha256'] = expected
    if record['source_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('analysis code changed since freeze: use a fresh experiment')
    return record


def records_fingerprint(records):
    values = sorted((r.truth['seed'],r.metadata['repeat'],
                     hashlib.sha256(np.asarray(r.wave,dtype='<f4').tobytes()).hexdigest(),
                     digest(r.metadata)) for r in records)
    return digest(values)


def _score(model, X):
    Z = (X[:,model['indices']]-np.asarray(model['mean']))/np.asarray(model['scale'])
    return Z @ np.asarray(model['coefficient']) + model['intercept']


def _metrics(y, score):
    pred = score >= 0
    return dict(balanced_accuracy=float(balanced_accuracy_score(y,pred)),
                roc_auc=float(roc_auc_score(y,score)),
                confusion_matrix_reject_valid=confusion_matrix(y,pred,labels=[0,1]).tolist(),
                recall_reject=float(np.mean(~pred[y==0])), recall_valid=float(np.mean(pred[y==1])),
                accuracy=float(np.mean(pred==y)))


def _bootstrap(y, score, rng, count, other=None):
    # Stratify by independent seed. Averages/repeats never become extra samples.
    classes = [np.flatnonzero(y==c) for c in (0,1)]
    values = []
    for _ in range(count):
        j = np.concatenate([rng.choice(c,len(c),replace=True) for c in classes])
        m = _metrics(y[j],score[j])
        row = [m['balanced_accuracy'],m['roc_auc']]
        if other is not None:
            row.append(m['roc_auc']-roc_auc_score(y[j],other[j]))
        values.append(row)
    bounds = np.quantile(values,[.025,.975],axis=0).T.tolist()
    return dict(zip(('balanced_accuracy_95ci','roc_auc_95ci','auc_minus_timing_95ci'),bounds))


def evaluate(records, plan, frozen, bootstrap=2000, permutations=5000):
    if frozen['plan_sha256'] != plan['sha256']:
        raise ValueError('frozen model belongs to another plan')
    if set(frozen['development_seeds']) & set(plan['cohorts']['holdout']):
        raise ValueError('seed leakage between development and holdout')
    if bootstrap < 100 or permutations < 100:
        raise ValueError('use at least 100 resamples for diagnostic intervals')
    if any(r.metadata.get('frozen_sha256') != frozen['sha256'] for r in records):
        raise ValueError('holdout was not collected after this model was frozen')
    rng = np.random.default_rng(plan['model_seed']+1)
    report = dict(schema=2,plan_sha256=plan['sha256'],frozen_sha256=frozen['sha256'],
                  holdout_fingerprint=records_fingerprint(records),
                  primary='single_trace', n_seeds=len(plan['cohorts']['holdout']),
                  bootstrap=bootstrap, permutations=permutations, results={})
    for name, average in (('single_trace',False),('mean_repeats',True)):
        X,y,t,_,sig = cohort_arrays(records,plan,'holdout',average)
        if sig != frozen['signature']:
            raise ValueError('holdout conditions differ from frozen development conditions')
        a,b = frozen['roi']
        models = frozen['models'][name]
        scores = dict(power=_score(models['power'],X[:,a:b]), timing=_score(models['timing'],t),
                      shuffled_labels=_score(models['shuffled_labels'],X[:,a:b]))
        results = {}
        for key,score in scores.items():
            result = _metrics(y,score)
            result.update(_bootstrap(y,score,rng,bootstrap,scores['timing'] if key=='power' else None))
            if key == 'power':
                # Fixed model + independent test: permutations of TEST labels,
                # without refitting, are the appropriate conditional null test.
                observed = result['balanced_accuracy']
                pred = score >= 0
                exceed = sum(balanced_accuracy_score(rng.permutation(y),pred) >= observed-1e-12
                             for _ in range(permutations))
                result['one_sided_permutation_p_ba'] = (1+exceed)/(1+permutations)
            results[key] = result
        report['results'][name] = results
    p = report['results']['single_trace']['power']
    report['decision'] = ('Evidence of a held-out single-trace validity association in this conditioned population.'
        if p['balanced_accuracy_95ci'][0] > .5 and p['one_sided_permutation_p_ba'] < .05
        else 'No convincing held-out single-trace distinguisher demonstrated; report the negative result.')
    report['limits'] = [
        'Primary inference uses one trace per independent seed; repeated traces are secondary.',
        'Balanced, workload-conditioned seeds: precision is not the precision on naturally distributed seeds.',
        'Timing and shuffled-label controls are diagnostic; a failed control needs investigation.',
        'AUC difference from timing is descriptive; no causal branch attribution or secret recovery follows.',
        'Never tune against this holdout. Any rework needs a new plan and fresh final seeds.',
        'Firmware identity proves variant/revision/profile, not the complete flashed binary hash; program the recorded image explicitly.'
    ]
    return report
