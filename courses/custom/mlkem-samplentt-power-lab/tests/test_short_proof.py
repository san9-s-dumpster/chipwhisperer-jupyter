"""Tests use explicitly fake devices; their scores are not experimental evidence."""
import itertools
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from sklearn.metrics import balanced_accuracy_score
from analysis.proof import exact_recall_bounds,exact_label_permutation_p,freeze_classifier,load_classifier,evaluate
from analysis.distinguisher import make_plan
from analysis.ground_truth import ground_truth,output_digest
from capture.records import Capture

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('bits',['00000000','11111111','00001111','11110000','10100110','00000111'])
def test_exact_permutation_matches_exhaustive_test_label_assignments(bits):
    y=np.array([0]*4+[1]*4);pred=np.array(list(map(int,bits)),bool)
    observed=balanced_accuracy_score(y,pred)
    scores=[]
    for ones in itertools.combinations(range(8),4):
        labels=np.zeros(8,int);labels[list(ones)]=1
        scores.append(balanced_accuracy_score(labels,pred))
    assert exact_label_permutation_p(y,pred)==pytest.approx(np.mean(np.array(scores)>=observed-1e-12))


def test_perfect_predictions_keep_nonzero_uncertainty():
    y=np.repeat([0,1],128)
    per_class,interval=exact_recall_bounds(y,y)
    assert .96<interval[0]<.98 and interval[1]==1
    assert interval[0]==pytest.approx(.9663447899063922)
    _,chance=exact_recall_bounds(y,np.zeros_like(y))
    assert chance[0]<.5<chance[1]


def records(plan,role):
    result=[]
    for seed in plan['cohorts'][role]:
        truth=ground_truth(bytes.fromhex(seed)).to_dict()
        wave=np.random.default_rng(int(seed[:8],16)).normal(2000,1,512).astype('float32')
        wave[32:80]+=30*truth['valid'][0]
        metadata=dict(backend='chipwhisperer',synthetic=False,settings=dict(
            target_platform='CW308_STM32F4',scope_serial='TEST FIXTURE',adc_multiplier=4,offset=95336,
            samples=512,gain_db=10.,stream_mode=False,baud=38400),
            firmware_build=dict(profile='measurement',firmware_sha256='fixture',source_commit='fixture'),
            adc_frequency_hz=29454545.,adc_bits=12,wave_units='ADC codes',chipwhisperer_version='test',
            duration_seconds=.0134,verification_digest=output_digest(truth['coefficients']).hex(),
            plan_sha256=plan['sha256'],cohort=role,repeat=0)
        result.append(Capture(wave,truth,metadata))
    return result


def test_fixed_fit_fresh_test_and_exact_bounds(tmp_path):
    plan=make_plan(tmp_path/'plan.json',per_class=16,repeats=1)
    dev=records(plan,'development');test=records(plan,'holdout')
    path=tmp_path/'frozen.json';frozen=freeze_classifier(path,dev,plan,{'firmware_sha256':'fixture'})
    assert set(frozen['models']['single_trace'])=={'power','timing'}
    assert load_classifier(path)==frozen
    assert freeze_classifier(path,dev,plan,{'firmware_sha256':'fixture'})==frozen
    with pytest.raises(ValueError,match='follow this frozen'):evaluate(test,plan,frozen)
    for record in test:record.metadata['frozen_sha256']=frozen['sha256']
    report,_,_,_=evaluate(test,plan,frozen)
    assert report['supported'] and report['n_test_seeds']==32
    assert report['metrics']['power']['correct']==32
    assert report['metrics']['power']['balanced_accuracy_95ci'][0]<1
    assert report['metrics']['timing']['balanced_accuracy']==.5
    assert not set(frozen['development_seeds'])&set(plan['cohorts']['holdout'])
    with pytest.raises(ValueError,match='incomplete'):evaluate(test[:-1],plan,frozen)


@pytest.fixture
def fake_hardware(tmp_path,monkeypatch):
    cw=pytest.importorskip('chipwhisperer')
    import firmware.build as builder
    import chipwhisperer.hardware.naeusb.naeusb as usbmodule
    repo=tmp_path/'repo';companion=repo/'jupyter/courses/custom/mlkem-samplentt-power-lab'
    companion.mkdir(parents=True)
    (companion/'proof-preset.json').write_bytes((ROOT/'proof-preset.json').read_bytes())
    source=Path.home()/'Desktop/work/chipwhisperer-new/jupyter/courses/custom/mlkem-samplentt-power-lab/firmware/variable_time/build.json'
    if not source.is_file():pytest.skip('requires the recorded reference build; never opens a device')
    reference=json.loads(source.read_text())
    image=Path(reference['image']).read_bytes()
    if hashlib.sha256(image).hexdigest()!=reference['firmware_sha256']:pytest.skip('reference image changed')
    calls=[]
    def fake_build(*args,**kwargs):
        folder=companion/'firmware/variable_time';folder.mkdir(parents=True,exist_ok=True)
        dest=folder/'fixture.hex';dest.write_bytes(image)
        record=dict(reference,image=str(dest));(folder/'build.json').write_text(json.dumps(record))
        return record
    class RegisterLink:
        def con(self,**kw):calls.append('normalize');return 0xACE5
        def cmdWriteMem(self,address,value):assert address==36 and bytes(value)==bytes([0])
        def set_smc_speed(self,value):assert value==0
        def close(self):pass
    class Clock:
        clkgen_freq=7372800.;adc_mul=4;adc_locked=True
        @property
        def adc_freq(self):return self.clkgen_freq*self.adc_mul
    class Scope:
        sn='TEST FIXTURE';clock=Clock();gain=SimpleNamespace(db=10.)
        io=SimpleNamespace();trigger=SimpleNamespace()
        adc=SimpleNamespace(samples=512,offset=95336,errors=0,trig_count=400000,bits_per_sample=12,stream_mode=False)
        sc=SimpleNamespace(setFastSMC=lambda value:None)
        counter=0;disconnected=False
        def __str__(self):return 'cwhusky TEST FIXTURE'
        def default_setup(self,verbose=True):assert not verbose
        def arm(self):pass
        def capture(self):return False
        def get_last_trace(self,as_int=True):
            assert as_int;self.counter+=1
            rng=np.random.default_rng(int(self.truth.seed[:8],16)+self.counter)
            wave=rng.normal(2000,1,self.adc.samples)
            wave[32:80]+=30*self.truth.valid[0]
            return np.rint(wave).astype('uint16')
        def dis(self):self.disconnected=True
    scope=Scope()
    class Target:
        baud=38400
        def flush(self):pass
        def dis(self):pass
        def simpleserial_write(self,cmd,data):
            self.cmd=cmd
            if cmd=='p':scope.truth=ground_truth(bytes(data[:32]),data[32],data[33])
        def simpleserial_read(self,cmd,size,**kwargs):
            if cmd=='i':return bytes([0])+bytes.fromhex(reference['source_commit'])
            return output_digest(scope.truth.coefficients)
    monkeypatch.setattr(usbmodule,'NAEUSB',RegisterLink)
    monkeypatch.setattr(builder,'build',fake_build)
    monkeypatch.setattr(cw,'scope',lambda **kw:scope)
    monkeypatch.setattr(cw,'target',lambda *a,**kw:Target())
    monkeypatch.setattr(cw,'program_target',lambda *a,**kw:calls.append('program'))
    monkeypatch.setattr('time.sleep',lambda *a:None)
    import importlib, capture.lab as workflow
    importlib.reload(workflow)
    return repo,scope,calls


def test_all_seven_notebook_cells_with_fake_device(fake_hardware):
    import nbformat
    repo,scope,calls=fake_hardware
    nb=nbformat.read(ROOT.parent/'Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb',as_version=4)
    namespace={'__name__':'__main__'};count=0
    for cell in nb.cells:
        if cell.cell_type!='code':continue
        # Users may add scratch cells; exercise the seven authored lab roles.
        if cell.metadata.get('lab_role') is None:continue
        source=cell.source
        if cell.metadata['lab_role']=='proof_setup':
            source=source.replace("REPO = Path.home() / 'Desktop/work/chipwhisperer-new'",'REPO = Path('+repr(str(repo))+')')
            source=source.replace('PER_CLASS = 128','PER_CLASS = 16')
        exec(compile(source,cell.metadata['lab_role'],'exec'),namespace)
        count+=1
    assert count==7 and calls==['normalize','program']
    assert namespace['report']['supported'] and scope.disconnected
    assert namespace['lab'].scope is None
    saved=json.loads((namespace['lab'].run_path/'report.json').read_text())
    assert saved['metrics']['power']['correct']==32


def test_changed_image_stops_before_any_device_operation(fake_hardware,monkeypatch):
    import capture.lab as workflow
    repo,scope,calls=fake_hardware
    subject=workflow.SampleNTTPowerLab(repo,per_class=16)
    original=workflow.build
    def wrong(*a,**kw):return dict(original(*a,**kw),firmware_sha256='wrong')
    monkeypatch.setattr(workflow,'build',wrong)
    with pytest.raises(ValueError,match='differs from the calibrated'):
        subject.prepare()
    assert calls==[] and subject.scope is None
