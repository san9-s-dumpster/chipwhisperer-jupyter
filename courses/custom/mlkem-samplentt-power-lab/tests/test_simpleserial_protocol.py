"""Run the real firmware adapter through ChipWhisperer's C UART parser.

Only HAL I/O is stubbed. No capture device is opened. This catches reserved
command collisions that a fake target accepting arbitrary commands misses.
"""
import os
from pathlib import Path
import select
import shutil
import subprocess
import time
from types import SimpleNamespace

import pytest

from analysis.ground_truth import generated_seed, ground_truth, output_digest

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "fd72834bd789c644b52fe0d62b2fa3b9f34dfaec"


@pytest.fixture(scope="session", params=["variable_time", "fls"])
def uart_firmware(request, tmp_path_factory):
    roots = list(ROOT.parents)
    if os.environ.get("CHIPWHISPERER_ROOT"):
        roots.insert(0, Path(os.environ["CHIPWHISPERER_ROOT"]))
    roots.append(Path.home()/"Desktop/work/chipwhisperer-new")
    repo = next((p for p in roots if (p/"firmware/mcu/simpleserial/simpleserial.c").is_file()), None)
    if repo is None:
        pytest.skip("set CHIPWHISPERER_ROOT to test against its real SimpleSerial parser")
    if not shutil.which("cc"):
        pytest.skip("host C compiler required")
    folder = tmp_path_factory.mktemp("uart-"+request.param)
    (folder/"hal.h").write_text("""
void platform_init(void);
void init_uart(void);
void trigger_setup(void);
void trigger_high(void);
void trigger_low(void);
char getch(void);
void putch(char c);
""")
    (folder/"hal.c").write_text("""
#include <stdio.h>
#include <stdlib.h>
static int triggered;
void platform_init(void) {}
void init_uart(void) { setvbuf(stdout, NULL, _IONBF, 0); }
void trigger_setup(void) {}
void trigger_high(void) { triggered = 1; }
void trigger_low(void) { triggered = 0; }
char getch(void) {
    int c = getchar();
    if (c == EOF) exit(0);
    return (char)c;
}
void putch(char c) {
    if (triggered) exit(20);
    putchar(c);
}
""")
    serial = repo/"firmware/mcu/simpleserial"
    tempo = ROOT/"reference/tempo"
    algorithm = "a1" if request.param == "fls" else "a0"
    exe = folder/"target"
    subprocess.run(["cc","-std=c99","-O2","-DSS_VER=1",
        "-DLAB_FLS="+str(int(request.param=="fls")),
        "-I"+str(folder),"-I"+str(serial),"-I"+str(tempo/"include"),
        str(ROOT/"firmware/common/main.c"),str(serial/"simpleserial.c"),
        str(tempo/f"src/algorithm_{algorithm}.c"),str(tempo/"src/fips202.c"),
        str(folder/"hal.c"),"-o",str(exe)],check=True,capture_output=True,text=True)
    return request.param,exe


def exchange(exe, commands):
    output = subprocess.run([str(exe)],input=commands,text=True,capture_output=True,
                            check=True,timeout=10).stdout
    # Upper- and lower-case ASCII hex are both valid SimpleSerial payloads.
    return [line.lower() for line in output.splitlines()]


def test_identity_and_reserved_version_commands(uart_firmware):
    variant,exe=uart_firmware
    identity="i"+bytes([int(variant=="fls")]).hex()+COMMIT
    assert exchange(exe,"v\ni\nv\n") == ["z01",identity,"z00","z01"]


def test_registered_commands_are_unique(uart_firmware):
    _,exe=uart_firmware
    response,ack=exchange(exe,"w\n")
    assert response[0]=="r" and ack=="z00"
    raw=bytes.fromhex(response[1:])
    commands=[chr(raw[i]) for i in range(0,len(raw),3)]
    assert len(commands)==len(set(commands))
    assert set(commands)==set("vwypi")


def test_sampling_digest_and_ack_remain_aligned(uart_firmware):
    variant,exe=uart_firmware
    seed=generated_seed(7,"uart-regression")
    truth=ground_truth(seed,1,2,variant)
    commands="i\np"+seed.hex()+"0102\ni\n"
    lines=exchange(exe,commands)
    identity="i"+bytes([int(variant=="fls")]).hex()+COMMIT
    assert lines==[identity,"z00","r"+output_digest(truth.coefficients).hex(),
                   "z00",identity,"z00"]


def test_python_identity_client_with_real_c_parser(uart_firmware):
    pytest.importorskip("chipwhisperer")
    from chipwhisperer.capture.targets.SimpleSerial import SimpleSerial
    from capture.hardware import HardwareBackend
    variant,exe=uart_firmware

    class PipeTarget:
        simpleserial_write=SimpleSerial.simpleserial_write
        simpleserial_read=SimpleSerial.simpleserial_read
        simpleserial_wait_ack=SimpleSerial.simpleserial_wait_ack
        def __init__(self,process):
            self.process=process
            self.ser=self
        def flush(self):pass
        def write(self,data):
            self.process.stdin.write(data.encode("ascii"))
            self.process.stdin.flush()
        def read(self,num_char,timeout=500):
            deadline=time.monotonic()+timeout/1000
            data=bytearray()
            while len(data)<num_char:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not select.select([self.process.stdout],[],[],remaining)[0]:
                    break
                chunk=os.read(self.process.stdout.fileno(),num_char-len(data))
                if not chunk:break
                data.extend(chunk)
            return data.decode("ascii")

    with subprocess.Popen([str(exe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE) as process:
        target=PipeTarget(process)
        backend=HardwareBackend.__new__(HardwareBackend)
        backend.target=target
        backend.settings=SimpleNamespace(timeout_seconds=1)
        backend.build={"variant":variant,"source_commit":COMMIT}
        try:
            backend.verify_firmware()
            # The application exchange consumed its acknowledgement; the
            # following built-in command remains independently decodable.
            target.simpleserial_write('v',bytearray())
            assert target.simpleserial_wait_ack()==1
        finally:
            process.stdin.close()
            process.wait(timeout=2)
