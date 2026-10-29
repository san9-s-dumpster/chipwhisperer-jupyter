"""Build without flashing; record the full command, log, hashes, and assembly."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analysis.c_reference import verify_sources


def build(chipwhisperer, platform, variant, optimization="2", profile="measurement"):
    if profile not in ("measurement", "calibration"):
        raise ValueError("unknown firmware profile")
    if variant not in ("variable_time", "fls"):
        raise ValueError("unknown sampler variant")
    if profile == "calibration" and platform != "CW308_STM32F4":
        raise ValueError("DWT calibration supports CW308_STM32F4 only")
    source = verify_sources()
    cw = Path(chipwhisperer).expanduser().resolve()
    mcu = cw/"firmware/mcu"
    if not (mcu/"Makefile.inc").is_file():
        raise ValueError("not a ChipWhisperer checkout containing firmware/mcu")
    name = variant if profile == "measurement" else variant+"_calibration"
    directory = ROOT/"firmware"/name
    command = ["make","-C",str(directory),f"FIRMWAREPATH={mcu}",
               f"PLATFORM={platform}","SS_VER=SS_VER_1_1",f"OPT={optimization}","VERBOSE=true"]
    # Never reuse objects built with different flags/profiles.
    subprocess.run(command+["clean"],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log = subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (directory/"build.log").write_text(log.stdout)
    if log.returncode:
        raise RuntimeError(f"firmware build failed; see {directory/'build.log'}")
    stem = directory/f"samplentt-{name}-{platform}"
    elf, image = stem.with_suffix(".elf"),stem.with_suffix(".hex")
    disassembly = subprocess.check_output(["arm-none-eabi-objdump","-d",str(elf)],text=True)
    stem.with_suffix(".asm").write_text(disassembly)
    record = {"variant":variant,"profile":profile,"target_platform":platform,"source_commit":source["commit"],
              "compiler":subprocess.check_output(["arm-none-eabi-gcc","--version"],text=True).splitlines()[0],
              "command":command,"simpleserial":"1.1","optimization":optimization,
              "compiler_flags_in":"build.log", "image":str(image),
              "compile_commands":[line[line.index("arm-none-eabi-gcc "):].removesuffix(" ...")
                                  for line in log.stdout.splitlines()
                                  if "arm-none-eabi-gcc -c " in line],
              "build_log_sha256":hashlib.sha256(log.stdout.encode()).hexdigest(),
              "firmware_sha256":hashlib.sha256(image.read_bytes()).hexdigest(),
              "elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest(),
              "chipwhisperer_commit":subprocess.check_output(["git","-C",str(cw),"rev-parse","HEAD"],text=True).strip(),
              "adapter_sha256":hashlib.sha256((ROOT/"firmware/common/main.c").read_bytes()).hexdigest(),
              "calibration_adapter_sha256":hashlib.sha256((ROOT/"firmware/common/calibration_timing.c").read_bytes()).hexdigest() if profile == "calibration" else None,
              "measured_interval":"complete upstream function including SHAKE and malloc/free",
              "constant_time_verified":False,"hardware_validated":False}
    (directory/"build.json").write_text(json.dumps(record,indent=2)+"\n")
    return record


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chipwhisperer",required=True)
    parser.add_argument("--platform",required=True)
    parser.add_argument("--variant",choices=["variable_time","fls"],required=True)
    parser.add_argument("--optimization",choices=["0","1","2","3","s"],default="2")
    parser.add_argument("--profile",choices=["measurement","calibration"],default="measurement")
    args=parser.parse_args()
    print(json.dumps(build(args.chipwhisperer,args.platform,args.variant,args.optimization,args.profile),indent=2))
