"""Reproduce an old imported builder in an otherwise updated notebook kernel."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(autouse=True)
def prevent_physical_usb_in_notebook_tests(monkeypatch):
    # The live connection cell normalizes the register bus before cw.scope().
    # Stub that link too: unit tests must never touch a physical device.
    class RegisterLink:
        def con(self,**kwargs):return 0xACE5
        def cmdWriteMem(self,address,payload):
            assert address==36 and bytes(payload)==bytes([0])
        def set_smc_speed(self,value):assert value==0
        def close(self):pass
    monkeypatch.setattr('chipwhisperer.hardware.naeusb.naeusb.NAEUSB',RegisterLink)



def cell_source(role):
    notebook=ROOT.parent/'Full SampleNTT Method.ipynb'
    cells=json.loads(notebook.read_text())['cells']
    return next(''.join(c['source']) for c in cells if c.get('metadata',{}).get('lab_role')==role)


@pytest.mark.parametrize('role',['build_measurement','build_calibration'])
def test_build_cell_replaces_stale_builder(role,tmp_path,monkeypatch):
    module=importlib.import_module('firmware.build')
    def stale_builder(*args,**kwargs):
        raise AssertionError('cached old builder was called')
    monkeypatch.setattr(module,'build',stale_builder)
    ns=dict(Path=Path,LAB=ROOT,CW_ROOT=tmp_path,PLATFORM='CW308_STM32F4',build=stale_builder)
    # The on-disk builder accepts profile=... and checks this intentionally
    # invalid checkout. No compiler, real build artifacts, or hardware touched.
    with pytest.raises(ValueError,match='not a ChipWhisperer checkout'):
        exec(compile(cell_source(role),role,'exec'),ns)
    assert ns['build'] is module.build and ns['build'] is not stale_builder


def test_programming_guard_runs_before_flash(tmp_path):
    path=tmp_path/'build.json';path.write_text(json.dumps({'variant':'variable_time'}))
    def forbidden_flash(*args,**kwargs):
        raise AssertionError('programming started before checking metadata')
    ns=dict(json=json,MEASUREMENT_JSON=path,cw=SimpleNamespace(program_target=forbidden_flash))
    with pytest.raises(RuntimeError,match='Rerun the preceding build cell'):
        exec(compile(cell_source('program_measurement'),'program_measurement','exec'),ns)


def connection_namespace(fail_setup=False, fail_connect=False):
    class Scope:
        sn='fake-device'
        clock=SimpleNamespace()
        io=SimpleNamespace()
        trigger=SimpleNamespace()
        disconnected=False
        def __str__(self):return 'cwhusky test fixture'
        def default_setup(self):
            if fail_setup:raise ValueError('injected PLL failure')
        def dis(self):self.disconnected=True
    scope=Scope()
    target=SimpleNamespace(dis=lambda:None)
    calls=[]
    def connect(**kwargs):
        calls.append(kwargs)
        if fail_connect:raise ValueError('Unknown ChipWhisperer: Default/Unknown')
        return scope
    cw=SimpleNamespace(scope=connect,target=lambda *a:target,
                       targets=SimpleNamespace(SimpleSerial=object))
    return dict(cw=cw,SCOPE_SN=None,TARGET_FREQ=7372800,UART_BAUD=38400),scope,calls


def test_fresh_connection_uses_standard_factory():
    ns,scope,calls=connection_namespace()
    exec(compile(cell_source('connect'),'connect','exec'),ns)
    assert calls==[dict(sn=None)]
    assert ns['scope'] is scope and ns['recorder'] is None
    assert callable(ns['attach_recorder'])


def test_connection_failure_preserves_root_error_and_invalidates_recorder():
    ns,scope,calls=connection_namespace(fail_connect=True)
    ns['recorder']=object()
    with pytest.raises(RuntimeError,match='Section 3.*Unknown ChipWhisperer') as error:
        exec(compile(cell_source('connect'),'connect','exec'),ns)
    assert isinstance(error.value.__cause__,ValueError)
    assert ns['scope'] is None and ns['target'] is None and ns['recorder'] is None


def test_partial_setup_failure_releases_created_scope():
    ns,scope,calls=connection_namespace(fail_setup=True)
    with pytest.raises(RuntimeError,match='injected PLL failure'):
        exec(compile(cell_source('connect'),'connect','exec'),ns)
    assert scope.disconnected and ns['scope'] is None and ns['recorder'] is None


def test_connection_cell_cannot_discard_a_working_connection():
    ns,scope,calls=connection_namespace()
    ns['scope']=scope
    with pytest.raises(RuntimeError,match='already exists'):
        exec(compile(cell_source('connect'),'connect','exec'),ns)
    assert not calls and not scope.disconnected


def test_survey_reports_missing_setup_before_using_recorder():
    with pytest.raises(RuntimeError,match='Complete section 3 successfully'):
        exec(compile(cell_source('survey'),'survey','exec'),{})
