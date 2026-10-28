"""Algorithm/integrity tests with labelled synthetic fixtures, never SCA evidence."""
import copy
import json
from types import SimpleNamespace
import numpy as np
import pytest
from analysis.ground_truth import ground_truth, output_digest
from analysis.distinguisher import (make_plan,load_plan,cohort_arrays,develop,freeze,
    load_frozen,evaluate,pipeline,_linear_fit,_score,window_grid)
from capture.records import Capture
from capture.cohort import acquire_cohort,read_cohort


@pytest.fixture(scope='module')
def plan(tmp_path_factory):
    return make_plan(tmp_path_factory.mktemp('plan')/'plan.json',per_class=16,repeats=2)


def fake_record(seed,plan,repeat=0,signal=True):
    truth=ground_truth(bytes.fromhex(seed)).to_dict()
    label=int(truth['valid'][0])
    # Test fixture only. Metadata exercises the checks and is not provenance.
    rng=np.random.default_rng(int(seed[:8],16)+repeat)
    wave=rng.normal(2048,1,512).astype('float32')
    if signal: wave[192:208] += 15*label
    metadata=dict(backend='chipwhisperer',synthetic=False,settings=dict(
        target_platform='CW308_STM32F4',scope_serial='TEST FIXTURE',adc_multiplier=4,
        offset=80000,samples=512,gain_db=10.,stream_mode=False,baud=38400),
        firmware_build=dict(profile='measurement',firmware_sha256='fixture',source_commit='fixture'),
        adc_frequency_hz=29454545.,adc_bits=12,wave_units='ADC codes',chipwhisperer_version='test',
        duration_seconds=.0134,verification_digest=output_digest(truth['coefficients']).hex(),
        plan_sha256=plan['sha256'],cohort='development',repeat=repeat)
    return Capture(wave,truth,metadata)


def fixture_records(plan,role,signal=True):
    rs=[fake_record(seed,plan,rep,signal) for seed in plan['cohorts'][role] for rep in range(plan['repeats'])]
    for r in rs:r.metadata['cohort']=role
    return rs


def test_plan_balances_and_matches_workload(plan):
    assert not set(plan['cohorts']['development'])&set(plan['cohorts']['holdout'])
    for seeds in plan['cohorts'].values():
        truths=[ground_truth(bytes.fromhex(s)) for s in seeds]
        assert sum(t.valid[0] for t in truths)==len(seeds)//2
        assert all(t.valid[1] and t.pair_iterations==160 and t.xof_rate_blocks==3
                   and t.candidates_to_fill==320 and sum(t.valid)==256 for t in truths)


def test_plan_integrity_and_exclusive_creation(tmp_path,plan):
    p=tmp_path/'plan.json';p.write_text(json.dumps(plan))
    assert load_plan(p)==plan
    with pytest.raises(FileExistsError):make_plan(p)
    corrupt=copy.deepcopy(plan);corrupt['pair_iterations']=161;p.write_text(json.dumps(corrupt))
    with pytest.raises(ValueError,match='changed'):load_plan(p)


def test_cohort_rejects_missing_duplicates_mock_and_calibration(plan):
    rs=fixture_records(plan,'development')
    assert cohort_arrays(rs,plan,'development')[0].shape==(32,512)
    with pytest.raises(ValueError,match='incomplete'):cohort_arrays(rs[:-1],plan,'development')
    with pytest.raises(ValueError,match='duplicate'):cohort_arrays(rs+[rs[0]],plan,'development')
    rs[0].metadata['synthetic']=True
    with pytest.raises(ValueError,match='mock'):cohort_arrays(rs,plan,'development')
    rs[0].metadata['synthetic']=False
    rs[0].metadata['firmware_build']['profile']='calibration'
    with pytest.raises(ValueError,match='calibration'):cohort_arrays(rs,plan,'development')


def test_cohort_rejects_changed_gain_and_truth(plan):
    rs=fixture_records(plan,'development')
    rs[0].metadata['settings']['gain_db']=12
    with pytest.raises(ValueError,match='mixed'):cohort_arrays(rs,plan,'development')
    rs=fixture_records(plan,'development');rs[0].truth['valid'][0]=not rs[0].truth['valid'][0]
    with pytest.raises(ValueError,match='ground truth'):cohort_arrays(rs,plan,'development')


def test_frozen_numeric_prediction_matches_sklearn():
    rng=np.random.default_rng(1);X=rng.normal(size=(64,128));y=np.tile([0,1],32)
    X[:,20]+=2*y
    m=pipeline().fit(X,y);numeric=_linear_fit(X,y)
    assert np.allclose(m.decision_function(X),_score(numeric,X))
    # Test data cannot change the fitted POIs or scale.
    before=m[0].indices_.copy();m.predict(X*100+1000)
    assert np.array_equal(m[0].indices_,before)


def test_fresh_seed_evaluation_and_controls(tmp_path,plan):
    dev=fixture_records(plan,'development')
    selection=develop(dev,plan,[(0,128),(128,256),(256,384)])
    assert selection['best_window']==[128,256]
    path=tmp_path/'frozen.json';fit=freeze(path,dev,plan,selection)
    assert load_frozen(path)==fit
    with pytest.raises(FileExistsError):freeze(path,dev,plan,selection)
    test=fixture_records(plan,'holdout')
    with pytest.raises(ValueError,match='after'):evaluate(test,plan,fit,100,100)
    for r in test:r.metadata['frozen_sha256']=fit['sha256']
    report=evaluate(test,plan,fit,100,100)
    power=report['results']['single_trace']['power']
    assert power['balanced_accuracy']==power['roc_auc']==1
    assert power['balanced_accuracy_95ci']==[1.,1.]
    assert power['one_sided_permutation_p_ba'] < .05
    assert report['results']['single_trace']['timing']['balanced_accuracy']==.5
    # Fresh noise has no relation to the learned label signal.
    noise=fixture_records(plan,'holdout',False)
    for r in noise:r.metadata['frozen_sha256']=fit['sha256']
    negative=evaluate(noise,plan,fit,100,100)
    assert negative['results']['single_trace']['power']['balanced_accuracy']==.5
    assert negative['decision'].startswith('No convincing')


def test_checkpoint_resume_and_required_freeze(tmp_path,plan):
    class Backend:
        build={'profile':'measurement','variant':'variable_time'}
        count=0
        def capture(self,seed,*args):
            self.count+=1
            if self.count==3:raise TimeoutError('injected')
            return fake_record(seed.hex(),plan)
    backend=Backend();folder=tmp_path/'development'
    with pytest.raises(TimeoutError):acquire_cohort(backend,plan,'development',folder)
    assert len(read_cohort(folder))==2
    records=acquire_cohort(backend,plan,'development',folder)
    assert len(records)==64
    assert backend.count==65  # One failed attempt; successful traces not recaptured.
    cohort_arrays(records,plan,'development')
    with pytest.raises(ValueError,match='freeze'):acquire_cohort(backend,plan,'holdout',tmp_path/'test')
    attempts=[json.loads(s) for s in (folder/'attempts.jsonl').read_text().splitlines()]
    assert sum(a['status']=='failed' for a in attempts)==1


def test_invalid_window_grid():
    with pytest.raises(ValueError):window_grid(512,start=128,stop=513)
