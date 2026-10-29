"""Interactive Husky/CW308_STM32F4 workflow for upstream top-level A1 (FLS)."""
from contextlib import suppress
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import time
from uuid import uuid4
import numpy as np
from tqdm.auto import tqdm
from analysis import fls as analysis
from analysis.distinguisher import load_plan
from analysis.ground_truth import generated_seed, ground_truth
from capture.hardware import HardwareBackend, HardwareSettings
from capture.lab import normal_husky_bus
from capture.records import save_dataset
from capture.cohort import acquire_cohort, read_cohort
from firmware.build import build


class FLSBackend(HardwareBackend):
    def capture(self, seed, x=0, y=0, variant='fls'):
        policy = dict(clip_errors_disabled=bool(self.scope.adc.clip_errors_disabled),
                      lo_gain_errors_disabled=bool(self.scope.adc.lo_gain_errors_disabled))
        if policy['clip_errors_disabled'] or policy != self.capture_policy:
            raise ValueError('ADC warning policy changed or clipping detection was disabled.')
        result = super().capture(seed, x, y, variant)
        result.metadata['fls_adc_policy'] = policy
        return result


class FLSPowerLab:
    def __init__(self, repo, per_class=128, gain_db=10., serial=None, resume=None,
                 suppress_low_gain_warning=True):
        self.repo = Path(repo).expanduser().resolve()
        self.root = self.repo/'jupyter/courses/custom/mlkem-samplentt-power-lab'
        self.config = dict(per_class=per_class, gain_db=float(gain_db), serial=serial,
                           suppress_low_gain_warning=bool(suppress_low_gain_warning),
                           platform='CW308_STM32F4', target_clock_hz=7372800,
                           adc_multiplier=4, baud=38400)
        if type(per_class) is not int or per_class < 16:
            raise ValueError('Use at least 16 seeds per class.')
        if not (self.root/'reference/manifest.json').is_file():
            raise FileNotFoundError('Select the chipwhisperer-new checkout containing the companion lab.')
        self.run_path = Path(resume).expanduser().resolve() if resume else self.root/'results/runs'/(
            'fls-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:6])
        if resume and not self.run_path.is_dir():
            raise FileNotFoundError(self.run_path)
        self.run_path.mkdir(parents=True, exist_ok=True)
        path = self.run_path/'fls-config.json'
        if path.exists():
            if json.loads(path.read_text()) != self.config:
                raise ValueError('Resume with the original FLS settings, or start a fresh run.')
        else:
            if resume:
                raise ValueError('This is not an FLS run folder.')
            with path.open('x') as stream:
                json.dump(self.config, stream, indent=2)
        self.scope = self.target = self.recorder = None
        self.measurement = self.calibration = self.localization = None
        self.plan = load_plan(self.run_path/'plan.json') if (self.run_path/'plan.json').exists() else None
        if self.plan is not None:
            analysis.validate_plan(self.plan)
        self.frozen_path = self.run_path/'frozen-model.json'
        self.cw = importlib.import_module('chipwhisperer')
        print('FLS results:', self.run_path)

    def build(self):
        """Compile both images and inspect them before opening hardware."""
        self.measurement = build(self.repo, self.config['platform'], 'fls', profile='measurement')
        self.calibration = build(self.repo, self.config['platform'], 'fls', profile='calibration')
        path = self.run_path/'localization.json'
        if path.exists():
            previous = json.loads(path.read_text())
            for profile, record in [('measurement', self.measurement), ('calibration', self.calibration)]:
                if previous[profile+'_firmware_sha256'] != record['firmware_sha256']:
                    raise ValueError('Rebuilt FLS image differs from the resumed run; no hardware was opened.')
        print('Pinned top-level algorithmA1; sampler sources are hash checked.')
        print('Measurement image SHA256:', self.measurement['firmware_sha256'])
        print('Assembly to inspect:', Path(self.measurement['image']).with_suffix('.asm'))
        print('Fixed loops in source are not a certificate of constant-time machine code.')
        return self.measurement['firmware_sha256']

    def connect(self):
        if self.scope is not None:
            raise RuntimeError('This FLS lab is already connected.')
        if self.measurement is None or self.calibration is None:
            raise RuntimeError('Run the build cell first.')
        try:
            normal_husky_bus(self.config['serial'])
            self.scope = scope = self.cw.scope(sn=self.config['serial'])
            if 'husky' not in str(scope).lower():
                raise ValueError('This notebook requires Husky.')
            scope.default_setup(verbose=False)
            scope.clock.clkgen_freq = self.config['target_clock_hz']
            scope.io.hs2 = 'clkgen'
            scope.io.tio1, scope.io.tio2, scope.io.tio3 = 'serial_rx', 'serial_tx', 'high_z'
            scope.trigger.module = 'basic'
            scope.trigger.triggers = 'tio4'
            self.target = self.cw.target(scope, self.cw.targets.SimpleSerial)
            self.target.baud = self.config['baud']
            self._window(2048, 0)
            print('Connected Husky:', scope.sn)
        except BaseException:
            with suppress(Exception):
                self.close()
            raise

    def _window(self, samples, offset):
        scope = self.scope
        if not 0 < samples <= int(scope.adc.max_samples) or offset < 0:
            raise ValueError('FLS window exceeds the available non-streaming ADC buffer.')
        scope.clock.adc_mul = self.config['adc_multiplier']
        scope.adc.stream_mode = False
        scope.adc.presamples = 0
        scope.adc.segments = 1
        scope.adc.decimate = 1
        scope.adc.samples, scope.adc.offset = int(samples), int(offset)
        scope.adc.basic_mode = 'rising_edge'
        scope.adc.timeout = 10
        scope.gain.db = self.config['gain_db']
        scope.adc.clip_errors_disabled = False
        scope.adc.lo_gain_errors_disabled = self.config['suppress_low_gain_warning']
        scope.adc.errors = 0
        time.sleep(.25)
        if not scope.clock.adc_locked:
            raise RuntimeError('ADC clock did not lock.')

    def _program(self, record):
        self.recorder = None
        self.cw.program_target(self.scope, self.cw.programmers.STM32FProgrammer, record['image'])
        self.scope.io.nrst = 'low'
        time.sleep(.05)
        self.scope.io.nrst = 'high_z'
        time.sleep(.25)
        self.target.flush()

    def _attach(self, profile):
        scope = self.scope
        name = 'fls' if profile == 'measurement' else 'fls_calibration'
        settings = HardwareSettings('Husky', self.config['platform'],
            str(self.root/'firmware'/name/'build.json'), str(scope.sn),
            target_clock_hz=float(scope.clock.clkgen_freq), adc_multiplier=int(scope.clock.adc_mul),
            samples=int(scope.adc.samples), offset=int(scope.adc.offset), gain_db=float(scope.gain.db),
            baud=int(self.target.baud), timeout_seconds=float(scope.adc.timeout), stream_mode=False)
        recorder = FLSBackend.from_connected(scope, self.target, settings, self.cw.__version__)
        recorder.capture_policy = dict(clip_errors_disabled=False,
            lo_gain_errors_disabled=self.config['suppress_low_gain_warning'])
        return recorder

    def _check_seed(self, number, purpose):
        return generated_seed(number, f"fls:{self.run_path.name}:{purpose}")

    def localize(self):
        if self.scope is None:
            raise RuntimeError('Connect Husky first.')
        path = self.run_path/'localization.json'
        if path.exists():
            self.localization = json.loads(path.read_text())
            if (self.localization['measurement_firmware_sha256'] != self.measurement['firmware_sha256']
                    or self.localization['calibration_firmware_sha256'] != self.calibration['firmware_sha256']):
                raise ValueError('Saved FLS calibration belongs to different images.')
            print('Using the original saved FLS window; no recalibration.')
            return self.localization
        self._window(2048, 0)
        self._program(self.calibration)
        calibrator = self._attach('calibration')
        warm = [calibrator.capture(self._check_seed(i, 'calibration-warmup')) for i in range(2)]
        chosen = [[], []]
        for i in range(10000):
            seed = self._check_seed(i, 'calibration')
            truth = ground_truth(seed, variant='fls')
            label = int(truth.valid[0])
            if truth.complete and truth.valid[1] and len(chosen[label]) < 4:
                chosen[label].append(seed)
            if min(map(len, chosen)) == 4:
                break
        else:
            raise RuntimeError('Could not generate balanced FLS calibration seeds.')
        records, markers = [], []
        seeds = chosen[0]+chosen[1]
        order = np.random.default_rng(97).permutation(len(seeds))
        for index in tqdm(order, desc='FLS first-pair calibration'):
            r = calibrator.capture(seeds[index])
            mark = calibrator.calibration_timing()
            core_cycles = r.metadata['duration_seconds']*float(self.scope.clock.clkgen_freq)
            if abs(mark['total_cycles']-core_cycles) > max(256, .02*core_cycles):
                raise RuntimeError('DWT and trigger scales disagree; inspect the target clock.')
            if mark['squeeze_calls'] != 280:
                raise RuntimeError('FLS calibration did not execute all 280 pairs.')
            r.metadata['calibration_cycles'] = mark
            records.append(r)
            markers.append(mark)
        start = max(0, min(m['first_squeeze_return'] for m in markers)-512)
        stop = max(m['second_squeeze_start'] for m in markers)+1536
        multiplier = self.config['adc_multiplier']
        samples = int(np.ceil(max(8192, (stop-start)*multiplier)/128)*128)
        if samples > int(self.scope.adc.max_samples):
            raise RuntimeError('The first FLS pair plus padding exceeds the buffer. Stop before training and revise acquisition settings in a fresh run.')
        self.localization = dict(offset=int(start*multiplier), samples=samples,
            adc_multiplier=multiplier, core_hz=float(self.scope.clock.clkgen_freq),
            measurement_firmware_sha256=self.measurement['firmware_sha256'],
            calibration_firmware_sha256=self.calibration['firmware_sha256'],
            calibration_seeds=[r.truth['seed'] for r in warm+records], markers=markers,
            first_pair_cycles_by_label={str(label): [m['second_squeeze_start']-m['first_squeeze_return']
                for r, m in zip(records, markers) if int(r.truth['valid'][0]) == label] for label in (0, 1)},
            caveat='Instrumented first-pair bounds are approximate; wrapper overhead and flash layout differ. Calibration traces are excluded from all model data.')
        save_dataset(self.run_path/('calibration-'+uuid4().hex[:6]), warm+records, [], dict(purpose='FLS localization only'))
        with path.open('x') as stream:
            json.dump(self.localization, stream, indent=2)
        print('Calibration first-pair CPU cycles (reject / accept):', self.localization['first_pair_cycles_by_label'])
        print('Measurement window: offset', self.localization['offset'], '; samples', samples)
        return self.localization

    def restore_measurement(self):
        if self.scope is None or self.localization is None:
            raise RuntimeError('Complete the connection/localization cell first.')
        self._program(self.measurement)
        self._window(self.localization['samples'], self.localization['offset'])
        self.recorder = self._attach('measurement')
        checks = [self.recorder.capture(self._check_seed(i, 'measurement-warmup')) for i in range(2)]
        save_dataset(self.run_path/('measurement-check-'+uuid4().hex[:6]), checks, [], dict(purpose='FLS warmup and range check'))
        print('Representative FLS identity and polynomial digests verified.')
        print('Check ADC range:', int(checks[-1].wave.min()), 'to', int(checks[-1].wave.max()),
              '; complete-operation time:', round(checks[-1].metadata['duration_seconds']*1e3, 3), 'ms')
        print('Only the first-pair window is recorded. Trigger duration still covers the entire operation.')
        print('Clipping checks enabled. Low-gain advisory suppressed:', self.config['suppress_low_gain_warning'])
        import matplotlib.pyplot as plt
        from IPython.display import display
        r = checks[-1]
        us = (self.localization['offset']+np.arange(len(r.wave)))/r.metadata['adc_frequency_hz']*1e6
        fig, ax = plt.subplots(figsize=(11, 2.8), layout='constrained')
        ax.plot(us, r.wave, lw=.55)
        for key in ('first_squeeze_return', 'second_squeeze_start'):
            positions = [m[key]/self.localization['core_hz']*1e6 for m in self.localization['markers']]
            ax.axvspan(min(positions), max(positions)+1e-6, color='orange', alpha=.4)
        ax.set(title='Ordinary FLS image; orange = approximate calibration boundaries',
               xlabel='Time since trigger (µs)', ylabel='Raw ADC codes')
        display(fig)
        plt.close(fig)

    def _ensure_plan(self):
        if self.plan is not None:
            analysis.validate_plan(self.plan)
            return
        if self.localization is None:
            raise RuntimeError('Localize FLS before planning model capture.')
        excluded = set(self.localization['calibration_seeds'])
        excluded.update(self._check_seed(i, 'measurement-warmup').hex() for i in range(2))
        for path in (self.root/'results/runs').rglob('plan.json'):
            if self.run_path in path.parents:
                continue
            prior = json.loads(path.read_text())
            for seeds in prior.get('cohorts', {}).values():
                excluded.update(seeds)
        # Include seed data from old unplanned experiments and previous checks.
        for path in (self.root/'results/runs').rglob('manifest.json'):
            manifest = json.loads(path.read_text())
            for stem in manifest.get('records', []):
                item = path.parent/(stem+'.json')
                if item.is_file():
                    excluded.add(json.loads(item.read_text())['truth']['seed'])
        self.plan = analysis.make_plan(self.run_path/'plan.json', self.config['per_class'], excluded)

    def collect_training(self):
        if self.recorder is None:
            raise RuntimeError('Restore the representative FLS image first.')
        self._ensure_plan()
        if self.frozen_path.exists():
            records = read_cohort(self.run_path/'development')
            frozen = analysis.load_frozen(self.frozen_path)
            if frozen['development_fingerprint'] != analysis.core.records_fingerprint(records):
                raise ValueError('FLS training data changed after freeze.')
            print('Training is already frozen; no captures added.')
            return len(records)
        records = acquire_cohort(self.recorder, self.plan, 'development', self.run_path/'development',
                                progress=lambda items: tqdm(items, desc='FLS training captures'))
        analysis.cohort_arrays(records, self.plan, 'development')
        print(len(records), 'verified FLS training captures; one per seed.')
        return len(records)

    def freeze(self):
        self._ensure_plan()
        frozen = analysis.freeze(self.frozen_path, read_cohort(self.run_path/'development'),
                                 self.plan, self.localization)
        print('Frozen FLS model:', frozen['sha256'])
        print('Relative power window:', frozen['roi'])
        print('Best development CV BA:', round(max(s['mean_cv_ba'] for s in frozen['selection']['search']), 3))
        print('That searched CV maximum is optimistic. Only the fresh test estimates performance.')
        return frozen['sha256']

    def collect_test(self):
        if self.recorder is None:
            raise RuntimeError('Restore the representative FLS image first.')
        self._ensure_plan()
        if not self.frozen_path.is_file():
            raise RuntimeError('Freeze the FLS model before test capture.')
        analysis.load_frozen(self.frozen_path)
        records = acquire_cohort(self.recorder, self.plan, 'holdout', self.run_path/'holdout',
            frozen_path=self.frozen_path, progress=lambda items: tqdm(items, desc='FLS fresh-test captures'))
        analysis.cohort_arrays(records, self.plan, 'holdout')
        print(len(records), 'verified fresh FLS test captures; no refitting.')
        return len(records)

    def results(self):
        from IPython.display import display, Markdown
        self._ensure_plan()
        frozen = analysis.load_frozen(self.frozen_path)
        report, X, y, t, scores = analysis.evaluate(read_cohort(self.run_path/'holdout'), self.plan, frozen)
        report['acquisition_audit'] = {}
        for role in ('development', 'holdout'):
            entries = [json.loads(s) for s in (self.run_path/role/'attempts.jsonl').read_text().splitlines()]
            report['acquisition_audit'][role] = dict(total_attempts=len(entries),
                failed_attempts=[a for a in entries if a['status'] != 'ok'])
        (self.run_path/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        rows = ['| Frozen model | Correct | Balanced accuracy (95% bounds) | AUC |', '|---|---:|---:|---:|']
        for key, title in [('power', 'Power'), ('timing', 'Total timing')]:
            m = report['metrics'][key]
            lo, hi = m['balanced_accuracy_95ci']
            rows.append(f"| {title} | {m['correct']}/{report['n_test_seeds']} | {100*m['balanced_accuracy']:.2f}% ({100*lo:.2f}–{100*hi:.2f}%) | {m['roc_auc']:.3f} |")
        display(Markdown('\n'.join(rows)))
        print(report['decision'])
        print('Power exact fixed-model label-permutation p:', f"{report['metrics']['power']['exact_test_label_permutation_p']:.3g}")
        timing = report['timing']
        print('Mean accept-minus-reject duration:', round(timing['accept_minus_reject'], 4), 'CPU cycles')
        print('Timing Welch p:', f"{timing['welch_p']:.3g}", '; KS p:', f"{timing['ks_p']:.3g}")
        print('Timing association detected: investigate before claiming timing-independent leakage.'
              if timing['timing_association_detected'] else
              'No duration association detected by these tests. This does not prove constant time.')
        if any(a['failed_attempts'] for a in report['acquisition_audit'].values()):
            print('Inspect capture failures/retries in report.json before interpreting the result.')
        fig = analysis.result_figure(report, y, t, scores, frozen['signature']['target_clock_hz'])
        fig.savefig(self.run_path/'result.png', dpi=160)
        display(fig)
        import matplotlib.pyplot as plt
        plt.close(fig)
        print('Saved:', self.run_path/'report.json')
        return report

    def close(self):
        if self.target is not None:
            with suppress(Exception):
                self.target.dis()
            self.target = None
        if self.scope is not None:
            try:
                if hasattr(self.scope, 'sc'):
                    with suppress(Exception):
                        self.scope.sc.setFastSMC(0)
            finally:
                self.scope.dis()
                self.scope = self.recorder = None
