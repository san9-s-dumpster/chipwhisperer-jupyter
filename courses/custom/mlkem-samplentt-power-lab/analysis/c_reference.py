"""Build and call the unmodified, pinned top-level ProjectTempo C files."""
import ctypes
import hashlib
import json
import platform
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEMPO = ROOT / "reference/tempo"


def verify_sources():
    manifest = json.loads((ROOT / "reference/manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        local = name
        if name.startswith("src/pqm4/"):
            local = "pqm4/samplentt_" + ("a0" if "noic-a0-" in name else "a1") + ".c"
        if hashlib.sha256((TEMPO/local).read_bytes()).hexdigest() != expected:
            raise ValueError(f"reference source hash mismatch: {local}")
    return manifest


def build_reference(output_dir=None, cc="cc"):
    manifest = verify_sources()
    output_dir = Path(output_dir or ROOT/"results/build/host").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    library = output_dir / "libtempo_reference.so"
    command = [cc, "-shared", "-fPIC", "-O2", "-std=c99", "-Wall", "-Wextra",
               "-I"+str(TEMPO/"include"), str(TEMPO/"src/algorithm_a0.c"),
               str(TEMPO/"src/algorithm_a1.c"), str(TEMPO/"src/fips202.c"),
               "-o", str(library)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    record = {"command": command, "compiler": subprocess.check_output(
        [cc, "--version"], text=True).splitlines()[0], "platform": platform.platform(),
        "source_commit": manifest["commit"],
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest()}
    (output_dir/"build.json").write_text(json.dumps(record, indent=2)+"\n")
    return library


class CReference:
    def __init__(self, library):
        self.lib = ctypes.CDLL(str(Path(library).resolve()))
        for name in ("algorithmA0", "algorithmA1"):
            fn = getattr(self.lib, name)
            fn.argtypes = [ctypes.POINTER(ctypes.c_int16), ctypes.POINTER(ctypes.c_uint8)]
            fn.restype = None

    def sample(self, seed, x=0, y=0, variant="variable_time"):
        from .ground_truth import encode_input, VARIANTS
        if variant not in VARIANTS:
            raise ValueError(variant)
        # A1 reads existing words during masked updates: initialize explicitly.
        output = (ctypes.c_int16 * 256)()
        extseed = (ctypes.c_uint8 * 34).from_buffer_copy(encode_input(seed, x, y))
        getattr(self.lib, "algorithmA0" if variant == "variable_time" else "algorithmA1")(output, extseed)
        return list(output)
