# ML-KEM SampleNTT power lab

Open **Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb** in the parent
`jupyter/courses/custom` directory. The active lab is **variable-time A0 only**,
for **Husky + CW308_STM32F4**. FLS files remain for later work and are not part
of this experiment.

The notebook is an executable hardware lab: connect, build/program, survey the
complete sampler, locate the first candidate pair with a separate calibration
image, restore the representative image, capture development data, freeze a
model, then acquire and evaluate a fresh final test. There is no synthetic
fallback in that workflow. Software checks do not establish physical leakage.

The old early-window classifier was inconclusive (balanced accuracy about
0.52 on only 20 test seeds, including three rejections). Its notebook, sources
and build artifacts are preserved in `archive/`; existing datasets under
`results/runs` stay intact. Do not pool those records with the new experiment.

## Start

Use `~/Desktop/work/chipwhisperer-new/.venv/bin/python` in the notebook's kernel
picker. Disconnect the previous notebook's scope/target, restart the kernel,
and run the new notebook from section 1. Its first cell prints the interpreter
and checkout paths. The environment already has the lab requirements.

For a future installation, from the checkout root:

```bash
source .venv/bin/activate
python -m pip install -r jupyter/courses/custom/mlkem-samplentt-power-lab/requirements.txt
python -m pip install -e .
git submodule update --init firmware/mcu/hal/chipwhisperer-fw-extra
cd jupyter/courses/custom
jupyter lab 'Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb'
```

Firmware needs `make`, `arm-none-eabi-gcc` and its ARM C library. The notebook's
programming cells replace the STM32F4 target firmware explicitly. They do not
update Husky firmware. USB access must already be working.

## Experiment

The default is 256 independent development seeds and 256 different final-test
seeds, balanced between acceptance/rejection of candidate zero, two captures
per seed. Both classes have exactly 160 candidate pairs and a valid second
candidate, and fill the output on the final candidate (256 accepted, 64 rejected). This controls obvious workload differences but conditions the seed
population. It does not estimate natural-prior precision or secret recovery.

The primary endpoint is **one trace per unseen seed**. Two-trace averaging is
secondary. Development-only cross-validation selects a local window and
training-only points of interest. A JSON artifact freezes the fit before any
final-test capture. Final evaluation reports balanced accuracy, AUC, seed-level
bootstrap intervals, a fixed-model permutation test, timing-only performance,
and a shuffled-training-label control. A negative result is retained as such.

See [experiment details](docs/distinguisher.md) for exact controls and limits,
and [hardware protocol](docs/hardware.md) for capture settings and calibration.

## Saved data and resuming

Each run has a unique `results/runs/vt-v2-<timestamp>-<id>` folder. Keep its
printed path. To resume, set `RESUME_RUN` in section 2 to that folder before
running the notebook. The saved plan/window/model are reused. Build/program
and attach the same hardware, then rerun the acquisition cell: successful
traces are checkpointed individually and are not recaptured. Failures stop the
batch and are logged in `attempts.jsonl`; rerunning explicitly retries the
failed trial. Analysis refuses incomplete cohorts and changed conditions.

Every checkpoint is numeric NPZ + JSON, committed by an atomic rename. There
is no pickle. Settings, build/image hashes, device serial, actual ADC rate,
trigger duration, ground truth and polynomial digest accompany each trace.
The final report includes capture-failure audit entries. Revisit frequent or
class-dependent failures before making a claim.

## Source and checks

The vendored ProjectTempo top-level sampler/SHAKE sources are pinned at
`fd72834bd789c644b52fe0d62b2fa3b9f34dfaec` and hash checked.
`analysis/ground_truth.py` independently derives candidates with Python
`hashlib.shake_128`. Every target reply verifies SHA3-256 of all 256 LE16
coefficients. See [source inspection](docs/reference-inspection.md).

From this companion folder:

```bash
python -m pytest -q
```

Tests cover C/Python agreement, the real SimpleSerial parser, capture error
handling, cohort integrity, numerical model serialization, held-out inference,
and checkpoint resuming. Synthetic test fixtures demonstrate software behavior
only. **ML-KEM SampleNTT - Software Validation.ipynb** and `experiments/run_mock.py`
remain separate historical software demonstrations.

Original lab code is GPL-3.0-or-later; see LICENSE. Vendored sources retain
their own notices and Apache-2.0 license.
