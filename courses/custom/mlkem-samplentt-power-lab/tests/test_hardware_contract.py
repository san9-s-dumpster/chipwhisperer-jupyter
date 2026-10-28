"""Exercise failure handling with fake API objects; never connect a device."""
from types import SimpleNamespace
import numpy as np
import pytest
from analysis.ground_truth import generated_seed, ground_truth, output_digest
from capture.hardware import HardwareBackend, HardwareSettings


def backend(timeout=False,reply=None,length=8,ticks=8,offset=0):
    class Target:
        baud=38400
        def flush(self): pass
        def simpleserial_write(self,cmd,payload):
            assert cmd == "p" and len(payload) == 34
        def simpleserial_read(self,*args,**kwargs): return reply
    obj=HardwareBackend.__new__(HardwareBackend)
    obj.settings=HardwareSettings("Lite","CWLITEARM","unused","test",samples=8,offset=offset)
    obj.build={"variant":"variable_time"}
    obj.target=Target()
    obj.scope=SimpleNamespace(arm=lambda:None,capture=lambda:timeout,
        get_last_trace=lambda **kw:np.ones(length),adc=SimpleNamespace(trig_count=ticks,samples=8,offset=offset),
        clock=SimpleNamespace(adc_freq=1000,clkgen_freq=7372800),gain=SimpleNamespace(db=25.))
    obj.snapshot="fake scope"
    obj.cw_version="fake"
    return obj


def digest():
    return output_digest(ground_truth(generated_seed(0)).coefficients)


@pytest.mark.parametrize("timeout,reply,length,error",[
    (True,None,8,TimeoutError),(False,None,8,RuntimeError),
    (False,bytes(32),8,RuntimeError),(False,digest(),7,RuntimeError)])
def test_capture_errors(timeout,reply,length,error):
    with pytest.raises(error):
        backend(timeout,reply,length).capture(generated_seed(0))


@pytest.mark.parametrize("ticks,offset,full",[(8,0,True),(10,0,False),(8,4,False)])
def test_trigger_units_and_partial_windows(ticks,offset,full):
    record=backend(reply=digest(),ticks=ticks,offset=offset).capture(generated_seed(0))
    assert record.metadata["duration_seconds"] == ticks/1000
    assert record.metadata["full_operation_captured"] is full
    assert not record.metadata["synthetic"]


def test_variant_mismatch():
    with pytest.raises(ValueError,match="does not match"):
        backend().capture(generated_seed(0),variant="fls")
