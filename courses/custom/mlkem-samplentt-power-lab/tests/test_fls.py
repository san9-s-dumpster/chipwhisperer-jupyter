"""FAKE devices/signals exercise integrity and control flow, never physical leakage."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from analysis import fls
from analysis.ground_truth import ground_truth, output_digest
from capture.records import Capture
from capture.cohort import acquire_cohort, read_cohort

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def plan(tmp_path_factory):
    return fls.make_plan(tmp_path_factory.mktemp('fls-plan')/'plan.json', per_class=16)


def records(plan, role, signal=True):
    result = []
    for seed in plan['cohorts'][role]:
        truth = ground_truth(bytes.fromhex(seed), variant='fls').to_dict()
        y = int(truth['valid'][0])
        wave = np.random.default_rng(int(seed[:8], 16)).normal(2000, 1, 1024).astype('float32')
        if signal:
            wave[64:96] += 30*y
        meta = dict(backend='chipwhisperer', synthetic=False,
            settings=dict(target_platform='CW308_STM32F4', scope_serial='FAKE TEST FIXTURE',
                target_clock_hz=7372800., adc_multiplier=4, offset=93000,
                samples=1024, gain_db=10., stream_mode=False, baud=38400),
            firmware_build=dict(variant='fls', profile='measurement', firmware_sha256='TEST FIXTURE', source_commit='TEST FIXTURE'),
            adc_frequency_hz=29491200., adc_bits=12, wave_units='ADC codes', chipwhisperer_version='TEST FIXTURE',
            fls_adc_policy=dict(clip_errors_disabled=False, lo_gain_errors_disabled=True),
            duration_seconds=2_000_000/7372800., verification_digest=output_digest(truth['coefficients']).hex(),
            plan_sha256=plan['sha256'], cohort=role, repeat=0)
        result.append(Capture(wave, truth, meta))
    return result


def localization():
    return dict(measurement_firmware_sha256='TEST FIXTURE', offset=93000, samples=1024)


def test_plan_full_fixed_schedule_balanced_and_disjoint(plan):
    fls.validate_plan(plan)
    assert not set(plan['cohorts']['development']) & set(plan['cohorts']['holdout'])
    for seeds in plan['cohorts'].values():
        truths = [ground_truth(bytes.fromhex(s), variant='fls') for s in seeds]
        assert sum(t.valid[0] for t in truths) == 16
        assert all(t.complete and t.valid[1] and t.candidates_to_fill == 320
                   and t.pair_iterations == 280 and len(t.valid) == 560 for t in truths)
        assert all(t.xof_bytes_requested == 840 and t.xof_rate_blocks == 5 for t in truths)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'calibration', 'a0', 'truth', 'digest', 'mock', 'clip', 'policy', 'gain'])
def test_fls_cohort_integrity(plan, fault):
    rs = records(plan, 'development')
    if fault == 'missing':
        rs.pop()
    elif fault == 'duplicate':
        rs.append(copy.deepcopy(rs[0]))
    elif fault == 'calibration':
        rs[0].metadata['firmware_build']['profile'] = 'calibration'
    elif fault == 'a0':
        rs[0].metadata['firmware_build']['variant'] = 'variable_time'
    elif fault == 'truth':
        rs[0].truth['valid'][0] = not rs[0].truth['valid'][0]
    elif fault == 'digest':
        rs[0].metadata['verification_digest'] = 'wrong'
    elif fault == 'mock':
        rs[0].metadata['synthetic'] = True
    elif fault == 'clip':
        rs[0].metadata['fls_adc_policy']['clip_errors_disabled'] = True
    elif fault == 'policy':
        rs[-1].metadata['fls_adc_policy']['lo_gain_errors_disabled'] = False
    elif fault == 'gain':
        rs[-1].metadata['settings']['gain_db'] = 11.
    with pytest.raises(ValueError):
        fls.cohort_arrays(rs, plan, 'development')


def test_frozen_fls_model_rejects_unfrozen_changed_incomplete_or_wrong_plan_test(tmp_path, plan):
    dev = records(plan, 'development')
    path = tmp_path/'frozen.json'
    frozen = fls.freeze(path, dev, plan, localization())
    assert fls.load_frozen(path) == frozen
    assert fls.freeze(path, dev, plan, localization()) == frozen
    test = records(plan, 'holdout')
    with pytest.raises(ValueError, match='after'):
        fls.evaluate(test, plan, frozen)
    for r in test:
        r.metadata['frozen_sha256'] = frozen['sha256']
    report, _, _, _, _ = fls.evaluate(test, plan, frozen)
    assert report['metrics']['power']['correct'] == 32
    assert report['metrics']['power']['balanced_accuracy_95ci'][0] < 1
    assert report['metrics']['timing']['balanced_accuracy'] == .5
    assert not report['timing']['timing_association_detected']
    assert report['constant_time_verified'] is False
    with pytest.raises(ValueError, match='Incomplete'):
        fls.evaluate(test[:-1], plan, frozen)
    with pytest.raises(ValueError, match='Wrong'):
        fls.evaluate(test, dict(plan, sha256='other'), frozen)
    dev[0].wave += 1
    with pytest.raises(ValueError, match='changed'):
        fls.freeze(path, dev, plan, localization())
    broken = copy.deepcopy(frozen)
    broken['fls_sources']['analysis/fls.py'] = 'changed'
    with pytest.raises(ValueError, match='changed'):
        fls.evaluate(test, plan, broken)


def test_timing_checks_constant_and_equal_mean_different_distributions():
    y = np.repeat([0, 1], 128)
    equal = fls.timing_diagnostics(y, np.ones((256, 1)), 1.)
    assert equal['welch_p'] == equal['ks_p'] == 1
    assert not equal['timing_association_detected']
    different = fls.timing_diagnostics(y, (100+y).reshape(-1, 1), 1.)
    assert different['timing_association_detected']
    x = np.r_[100+np.tile([-10, 10], 64), 100+np.tile([-1, 1], 64)]
    same_mean = fls.timing_diagnostics(y, x, 1.)
    assert same_mean['welch_p'] == 1 and same_mean['ks_p'] < .025
    assert same_mean['timing_association_detected']


def test_checkpoint_dispatches_fls_and_resumes_failed_trial(tmp_path, plan):
    by_seed = {r.truth['seed']: r for r in records(plan, 'development')}
    class Backend:
        build = {'variant': 'fls', 'profile': 'measurement'}
        count = 0
        def capture(self, seed, x, y, variant):
            assert variant == 'fls'
            self.count += 1
            if self.count == 3:
                raise TimeoutError('injected fixture failure')
            return copy.deepcopy(by_seed[seed.hex()])
    backend = Backend()
    with pytest.raises(TimeoutError):
        acquire_cohort(backend, plan, 'development', tmp_path/'development')
    assert len(read_cohort(tmp_path/'development')) == 2
    rs = acquire_cohort(backend, plan, 'development', tmp_path/'development')
    fls.cohort_arrays(rs, plan, 'development')
    assert backend.count == 33
    attempts = [json.loads(s) for s in (tmp_path/'development/attempts.jsonl').read_text().splitlines()]
    assert sum(a['status'] != 'ok' for a in attempts) == 1
    backend.build['variant'] = 'variable_time'
    with pytest.raises(ValueError, match='representative fls'):
        acquire_cohort(backend, plan, 'development', tmp_path/'wrong')


@pytest.fixture
def fake_fls_lab(tmp_path, monkeypatch):
    import chipwhisperer as cw
    import capture.fls as workflow
    repo = tmp_path/'repo'
    companion = repo/'jupyter/courses/custom/mlkem-samplentt-power-lab'
    (companion/'reference').mkdir(parents=True)
    (companion/'reference/manifest.json').write_text('{}')
    calls = []
    current = {}
    def fake_build(repo, platform, variant, profile):
        assert variant == 'fls' and platform == 'CW308_STM32F4'
        name = 'fls' if profile == 'measurement' else 'fls_calibration'
        directory = companion/'firmware'/name
        directory.mkdir(parents=True, exist_ok=True)
        image = directory/'fixture.hex'
        image.write_text('FAKE FIRMWARE '+profile)
        result = dict(variant='fls', profile=profile, target_platform=platform,
            image=str(image), firmware_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            source_commit='fd72834bd789c644b52fe0d62b2fa3b9f34dfaec')
        (directory/'build.json').write_text(json.dumps(result))
        return result
    class Clock:
        clkgen_freq = 7372800.
        adc_mul = 4
        adc_locked = True
        @property
        def adc_freq(self):
            return self.clkgen_freq*self.adc_mul
    class Scope:
        sn = 'FAKE FLS TEST FIXTURE'
        clock = Clock()
        gain = SimpleNamespace(db=10.)
        io = SimpleNamespace()
        trigger = SimpleNamespace()
        adc = SimpleNamespace(samples=2048, offset=0, errors=0, trig_count=8_000_000,
                              bits_per_sample=12, stream_mode=False, max_samples=131070)
        sc = SimpleNamespace(setFastSMC=lambda value: None)
        counter = 0
        disconnected = False
        def __str__(self):
            return 'cwhusky FAKE FLS TEST FIXTURE'
        def default_setup(self, **kwargs):
            pass
        def arm(self):
            pass
        def capture(self):
            return False
        def get_last_trace(self, as_int=True):
            assert as_int
            self.counter += 1
            x = np.random.default_rng(int(self.truth.seed[:8], 16)+self.counter).normal(2000, 1, self.adc.samples)
            x[64:96] += 30*self.truth.valid[0]
            return np.rint(x).astype('uint16')
        def dis(self):
            self.disconnected = True
    scope = Scope()
    class Target:
        baud = 38400
        def flush(self):
            pass
        def dis(self):
            pass
        def simpleserial_write(self, cmd, data):
            if cmd == 'p':
                scope.truth = ground_truth(bytes(data[:32]), data[32], data[33], 'fls')
        def simpleserial_read(self, cmd, size, **kwargs):
            if cmd == 'i':
                return bytes([0x81 if current['profile'] == 'calibration' else 1])+bytes.fromhex(current['source_commit'])
            if cmd == 't':
                return np.array([100, 23700, 24700, 24750, 2_000_000, 280], dtype='<u4').tobytes()
            return output_digest(scope.truth.coefficients)
    def program(scope, programmer, image):
        current.update(json.loads((Path(image).parent/'build.json').read_text()))
        calls.append('program '+current['profile'])
    # Stub every USB entry point; no test may claim or access a real board.
    monkeypatch.setattr(workflow, 'normal_husky_bus', lambda serial: calls.append('normalize'))
    monkeypatch.setattr(workflow, 'build', fake_build)
    monkeypatch.setattr(cw, 'scope', lambda **kwargs: scope)
    monkeypatch.setattr(cw, 'target', lambda *args, **kwargs: Target())
    monkeypatch.setattr(cw, 'program_target', program)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    subject = workflow.FLSPowerLab(repo, per_class=16)
    return subject, scope, calls


def test_fls_notebook_phases_with_fake_board_and_hardware_free_reload(fake_fls_lab):
    import nbformat
    subject, scope, calls = fake_fls_lab
    nb = nbformat.read(ROOT.parent/'Lab 7_2 - ML-KEM FLS Power Lab.ipynb', as_version=4)
    nbformat.validate(nb)
    namespace = {'fls': subject}
    roles = []
    for cell in nb.cells:
        if cell.cell_type != 'code':
            continue
        role = cell.metadata['lab_role']
        compile(cell.source, role, 'exec')
        roles.append(role)
        if role == 'fls_setup':
            continue  # The configured fixture supplies this object without a real USB path.
        exec(compile(cell.source, role, 'exec'), namespace)
    assert len(roles) == 9 and scope.disconnected and subject.scope is None
    assert calls == ['normalize', 'program calibration', 'program measurement']
    assert namespace['report']['power_association_supported']
    assert namespace['report']['metrics']['power']['correct'] == 32
    assert namespace['report']['constant_time_verified'] is False
    assert all(not a['failed_attempts'] for a in namespace['report']['acquisition_audit'].values())
    from capture.fls import FLSPowerLab
    reload = FLSPowerLab(subject.repo, per_class=16, resume=subject.run_path)
    assert reload.scope is None
    assert reload.results()['metrics']['power']['correct'] == 32
    assert calls == ['normalize', 'program calibration', 'program measurement']


def test_fls_clipping_checks_cannot_be_disabled(fake_fls_lab):
    subject, scope, _ = fake_fls_lab
    subject.build()
    subject.connect()
    subject.localize()
    subject.restore_measurement()
    seed = subject._check_seed(99, 'policy-test')
    scope.adc.clip_errors_disabled = True
    with pytest.raises(ValueError, match='clipping'):
        subject.recorder.capture(seed)
    subject.close()


def test_fls_resume_does_not_silently_change_gain(fake_fls_lab):
    subject, _, calls = fake_fls_lab
    from capture.fls import FLSPowerLab
    with pytest.raises(ValueError, match='original FLS settings'):
        FLSPowerLab(subject.repo, per_class=16, gain_db=15., resume=subject.run_path)
    assert not calls
