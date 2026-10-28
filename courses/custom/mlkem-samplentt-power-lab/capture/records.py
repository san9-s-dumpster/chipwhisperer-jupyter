from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import numpy as np


@dataclass
class Capture:
    wave: np.ndarray
    truth: dict
    metadata: dict


def environment():
    packages = {}
    for name in ["numpy","scipy","matplotlib","scikit-learn","chipwhisperer"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": packages, "utc": datetime.now(timezone.utc).isoformat()}


def acquire_batch(backend, seeds, variant, repeats=1, x=0, y=0, order_seed=42,
                  progress=None, keep_partial_on_interrupt=False):
    """Randomized input order. Failed trials are recorded, never silently retried."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    trials = [(seed, repeat) for seed in seeds for repeat in range(repeats)]
    order = np.random.default_rng(order_seed).permutation(len(trials))
    if progress is not None:
        order = progress(order)
    records, failures = [], []
    for position, trial in enumerate(order):
        seed, repeat = trials[trial]
        try:
            result = backend.capture(seed,x,y,variant)
            result.metadata.update(repeat=int(repeat), trial=int(trial),
                                   order_seed=int(order_seed),
                                   sequence=len(records)+len(failures))
            records.append(result)
        except (TimeoutError, RuntimeError, ValueError, Warning) as error:
            failures.append({"seed":seed.hex(), "x":x,"y":y,"variant":variant,
                             "repeat":repeat, "trial":int(trial),
                             "error":f"{type(error).__name__}: {error}"})
        except KeyboardInterrupt:
            if not keep_partial_on_interrupt:
                raise
            failures.append({"seed":seed.hex(), "x":x,"y":y,"variant":variant,
                             "repeat":repeat,"trial":int(trial),
                             "error":"KeyboardInterrupt: returned partial batch",
                             "unattempted_trials":len(trials)-position-1})
            break
    return records, failures


def save_dataset(directory, records, failures, settings):
    """One trace per NPZ plus JSON ground truth; never use pickle/object arrays."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"schema":1, "environment":environment(), "settings":settings,
                "count":len(records), "failures":failures, "records":[]}
    for number, record in enumerate(records):
        stem = f"trace-{number:05d}"
        np.savez_compressed(directory/(stem+".npz"), wave=record.wave)
        (directory/(stem+".json")).write_text(json.dumps(
            {"truth":record.truth,"metadata":record.metadata}, indent=2)+"\n")
        manifest["records"].append(stem)
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return directory


def load_dataset(directory):
    directory = Path(directory)
    manifest = json.loads((directory/"manifest.json").read_text())
    records = []
    for stem in manifest["records"]:
        data = json.loads((directory/(stem+".json")).read_text())
        with np.load(directory/(stem+".npz"),allow_pickle=False) as arrays:
            records.append(Capture(arrays["wave"],data["truth"],data["metadata"]))
    return records, manifest
