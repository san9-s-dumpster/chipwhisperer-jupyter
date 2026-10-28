import hashlib
import json
from types import SimpleNamespace
import numpy as np
import pytest
from analysis.ground_truth import generated_seed,ground_truth,output_digest
from analysis.hardware import classify_roi,seed_roi
from capture.hardware import HardwareBackend,HardwareSettings
from capture.records import acquire_batch,Capture


def connected(tmp_path,wrong_variant=False):
    image=tmp_path/'sampler.hex'
    image.write_bytes(b':test image')
    build={"target_platform":"CW308_STM32F4","profile":"measurement","image":str(image),
           "firmware_sha256":hashlib.sha256(image.read_bytes()).hexdigest(),
           "source_commit":"fd72834bd789c644b52fe0d62b2fa3b9f34dfaec","variant":"variable_time"}
    (tmp_path/'build.json').write_text(json.dumps(build))
    class Scope:
        adc=SimpleNamespace(samples=64,offset=0,errors=False,trig_count=32,stream_mode=False)
        clock=SimpleNamespace(adc_freq=7372800.,clkgen_freq=7372800.,adc_mul=1)
        gain=SimpleNamespace(db=25.)
        def __str__(self):return 'cwhusky Device (fake)'
        def arm(self):pass
        def capture(self):return False
        def get_last_trace(self, as_int=True):return np.zeros(64)
    class Target:
        baud=38400
        def flush(self):pass
        def simpleserial_write(self,cmd,data):self.cmd,self.data=cmd,data
        def simpleserial_read(self,cmd,size,**kw):
            if cmd=='i':return bytes([int(wrong_variant)])+bytes.fromhex(build['source_commit'])
            return output_digest(ground_truth(bytes(self.data[:32]),self.data[32],self.data[33]).coefficients)
    settings=HardwareSettings('Husky','CW308_STM32F4',str(tmp_path/'build.json'),'fake',
                              samples=64,adc_multiplier=1)
    return Scope(),Target(),settings


def test_borrow_existing_scope_and_target(tmp_path):
    scope,target,settings=connected(tmp_path)
    backend=HardwareBackend.from_connected(scope,target,settings,cw_version='fake')
    assert backend.scope is scope and backend.target is target
    record=backend.capture(generated_seed(0))
    assert record.metadata['full_operation_captured']
    assert record.metadata['settings']['adc_multiplier']==1


def test_attach_rejects_wrong_firmware(tmp_path):
    with pytest.raises(RuntimeError,match='handshake'):
        HardwareBackend.from_connected(*connected(tmp_path,wrong_variant=True))


def test_attach_rejects_stale_window_settings(tmp_path):
    scope,target,settings=connected(tmp_path)
    scope.adc.offset=16
    with pytest.raises(ValueError,match='window'):
        HardwareBackend.from_connected(scope,target,settings)


def test_progress_wrapper_receives_all_trials():
    seen=[]
    def progress(items):
        seen.extend(items)
        return items
    class Backend:
        def capture(self,*args):raise TimeoutError('injected')
    _,failures=acquire_batch(Backend(),[generated_seed(0)],'fls',repeats=3,progress=progress)
    assert len(seen)==len(failures)==3


def test_notebook_interrupt_returns_partial_data():
    class Backend:
        count=0
        def capture(self,*args):
            self.count+=1
            if self.count==2:raise KeyboardInterrupt()
            return Capture(np.zeros(4),{}, {})
    records,failures=acquire_batch(Backend(),[generated_seed(0)],'fls',repeats=3,
                                  keep_partial_on_interrupt=True)
    assert len(records)==len(failures)==1
    assert failures[0]['unattempted_trials']==1
    assert 'KeyboardInterrupt' in failures[0]['error']


def test_hardware_roi_keeps_seeds_disjoint():
    records=[]
    for i in range(96):
        gt=ground_truth(generated_seed(i)).to_dict()
        for repeat in range(2):
            wave=np.full(64,float(gt['valid'][0]))
            records.append(Capture(wave,gt,{"backend":"fake", "sample_window_start":0,
                                          "adc_frequency_hz":7372800.}))
    result=classify_roi(records,0,64,bins=8)
    assert not set(result['train_seeds']) & set(result['test_seeds'])
    assert len(result['train_seeds'])+len(result['test_seeds'])==96
    assert result['balanced_accuracy']==1
    assert result['majority_balanced_accuracy']==0.5
    with pytest.raises(ValueError,match='ROI'):
        seed_roi(records,0,128)


def test_stale_gain_is_rejected_before_capture(tmp_path):
    scope,target,settings=connected(tmp_path)
    backend=HardwareBackend.from_connected(scope,target,settings)
    scope.gain.db=10
    with pytest.raises(ValueError,match='live capture settings'):
        backend.capture(generated_seed(0))


def test_calibration_profile_is_distinct_on_wire(tmp_path):
    scope,target,settings=connected(tmp_path)
    path=tmp_path/'build.json'
    build=json.loads(path.read_text());build['profile']='calibration'
    path.write_text(json.dumps(build))
    with pytest.raises(RuntimeError,match='handshake'):
        HardwareBackend.from_connected(scope,target,settings)


def test_missing_profile_fails_with_rebuild_instruction(tmp_path):
    scope,target,settings=connected(tmp_path)
    path=tmp_path/'build.json'
    build=json.loads(path.read_text());del build['profile']
    path.write_text(json.dumps(build))
    with pytest.raises(ValueError,match='rerun the notebook build cell'):
        HardwareBackend.from_connected(scope,target,settings)


@pytest.mark.parametrize('values',[
    [10,100,120,130,1000,160], [10,100,90,130,1000,160],
    [0,100,120,130,1000,160], [10,100,120,130,1000,1]])
def test_calibration_counter_validation(values):
    obj=HardwareBackend.__new__(HardwareBackend)
    obj.build={'profile':'calibration'}
    obj.settings=SimpleNamespace(timeout_seconds=1)
    obj.target=SimpleNamespace(simpleserial_write=lambda *args:None,
        simpleserial_read=lambda *args,**kw:np.array(values,dtype='<u4').tobytes())
    if 0<values[0]<values[1]<values[2]<values[3]<values[4] and values[5]>=128:
        assert obj.calibration_timing()['squeeze_calls']==160
    else:
        with pytest.raises(RuntimeError,match='DWT'):obj.calibration_timing()


@pytest.mark.parametrize('error_type',[KeyboardInterrupt,RuntimeError])
def test_adc_download_failure_restores_normal_bus_mode(tmp_path,error_type):
    scope,target,settings=connected(tmp_path)
    backend=HardwareBackend.from_connected(scope,target,settings)
    restored=[]
    scope.sc=SimpleNamespace(setFastSMC=lambda value:restored.append(value))
    def fail():raise error_type('injected ADC download failure')
    scope.capture=fail
    with pytest.raises(error_type,match='injected ADC download failure'):
        backend.capture(generated_seed(0))
    assert restored==[0]


def test_bus_cleanup_does_not_mask_original_capture_error(tmp_path):
    scope,target,settings=connected(tmp_path)
    backend=HardwareBackend.from_connected(scope,target,settings)
    def capture_failure():raise RuntimeError('original transfer failure')
    def cleanup_failure(value):raise OSError('device disconnected')
    scope.capture=capture_failure
    scope.sc=SimpleNamespace(setFastSMC=cleanup_failure)
    with pytest.raises(RuntimeError,match='original transfer failure') as error:
        backend.capture(generated_seed(0))
    assert 'Normal bus-mode cleanup also failed' in error.value.__notes__[0]
