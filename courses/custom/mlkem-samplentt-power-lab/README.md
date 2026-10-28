# SampleNTT single-trace power lab

Open **Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb** in the parent custom folder.
The short lab has seven executable cells: setup, hardware preparation, training
capture, frozen fit, fresh-test capture, evaluation and disconnect. It uses
Husky + CW308_STM32F4 and the variable-time A0 sampler only.

Use chipwhisperer-new/.venv as the kernel and run from the top. The default
is 128 seeds per class in each of training and test, one capture per seed.
Set RESUME_RUN to the printed folder to resume a partial run. The acquisition
checkpoints each success, logs failures, verifies the full polynomial digest,
and rejects changed settings or contaminated/incomplete cohorts.

The window is fixed from the validated physical experiment, rather than searched
again in every run. proof-preset.json binds its sample positions to the exact
firmware image. A changed image stops preparation before target programming;
use docs/Full SampleNTT Method.ipynb to recalibrate. Two check calls warm the
target before model data. FLS and repeated-trace averaging are deferred.

The model predicts first-candidate accept/reject on balanced, workload-matched
public seeds. It is a profiling demonstration, not an ML-KEM key-recovery attack.
Both classes have exactly 160 pairs and 256 accepted candidates, with candidate
one valid and the final candidate completing the output.

Host details live in capture/lab.py; core acquisition and immutable NPZ/JSON
records stay in capture/. analysis/proof.py freezes numeric models and evaluates
one capture per unseen seed with simultaneous exact class-recall confidence
bounds and an exact fixed-model test-label permutation test. The timing baseline
is linear. There is no synthetic fallback in the hardware workflow and no
single shuffled-training-label model presented as a passed null control.

The original full notebook and measured 256/256-success run are preserved.
checkpoints/validated-2026-10-28 contains the Git-backed data/build archive,
its checksum manifest, and the independent evaluation. Existing results/runs
are unchanged and remain ignored by Git; every new capture run gets a unique
folder. The full historical pipeline remains in docs/Full SampleNTT Method.ipynb.

Run software checks from this companion folder with python -m pytest -q.
Fake-device tests never establish physical leakage. Original code is
GPL-3.0-or-later; vendored sources retain their original notices.
