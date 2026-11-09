# Technical notes and original lab explanations

Earlier explanations are preserved here for reference. Start with the [project overview](../../README.md).

## Earlier companion README

# ML-KEM SampleNTT labs

All hardware notebooks live together in [the custom folder](../..):

- [Short A0 lab](../../Lab%207_1%20-%20ML-KEM%20SampleNTT%20Power%20Lab.ipynb) — fixed validated window.
- [Full A0 method](../../Full%20SampleNTT%20Method.ipynb) — calibration and window development; existing outputs preserved.
- [FLS lab](../../Lab%207_2%20-%20ML-KEM%20FLS%20Power%20Lab.ipynb) — new A1 calibration, frozen power classifier, fresh test and separate timing diagnostics.

The FLS notebook uses Husky + CW308_STM32F4 and chipwhisperer-new/.venv. It compiles/programs only the STM32 target when its hardware cells are run. No FLS measurements have been taken by installing these files.

## Short A0 lab

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
use ../Full SampleNTT Method.ipynb to recalibrate. Two check calls warm the
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
folder. The full historical pipeline remains in ../Full SampleNTT Method.ipynb.

Run software checks from this companion folder with python -m pytest -q.
Fake-device tests never establish physical leakage. Original code is
GPL-3.0-or-later; vendored sources retain their original notices.

## Earlier explanations: Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb

# SampleNTT: predict rejection from one power trace

**Husky + CW308_STM32F4 · variable-time sampler A0**

This lab demonstrates a narrow, testable leakage claim: a classifier can predict whether the **first 12-bit candidate is accepted** from one power capture of an unseen public seed. Train on known seeds, freeze the classifier, then test on different seeds.

The capture window was fixed using the previously validated experiment. Both classes have the same total sampling workload. This demonstrates local accept/reject leakage; it does not recover an ML-KEM key.

Start a fresh kernel using chipwhisperer-new/.venv. Run the seven code cells in order. Hardware routines, raw records and metadata stay in the companion directory.

## 1. Setup

Use 128 seeds per class for training and another 128 per class for testing: **512 captures, one per seed**. Gain starts at the previously usable 10 dB. To resume an interrupted run, set RESUME_RUN to its printed results folder; completed captures and the frozen model are reused.

## 2. Prepare and verify the hardware

This builds and programs the **STM32F4 target**, connects Husky, verifies the sampler identity and polynomial digest, and warms the target before collecting data. It also restores normal USB–FPGA bus timing.

The fixed 512-sample window covers about 17.4 µs near the first candidate pair, at four ADC samples per CPU cycle. It is tied to the calibrated firmware image; a different image stops the lab and requires recalibration. Clipping and capture errors remain enabled.

## 3. Capture training data

Seeds are balanced between first-candidate acceptance and rejection. Every seed takes exactly 160 pairs, with a valid second candidate and output completion on the final candidate. Trial order is randomized; every successful capture is checkpointed and verified. Failures stop capture rather than silently dropping seeds. Rerun this cell to resume after fixing an error.

## 4. Freeze the distinguisher

The classifier selects 16 power-sample positions and fits a regularized linear model using **training data only**. The window was fixed before this run. The model, threshold and capture settings are saved before test capture. A separate total-duration classifier provides a timing baseline.

## 5. Capture fresh test seeds

These seeds have not appeared in training or earlier saved experiments. The capture code requires the frozen model and unchanged settings. Do not return to model or window selection after inspecting this test.

## 6. Evaluate the claim

**Balanced accuracy** averages accept and reject recall; chance is 50%. **AUC** measures how well the scores separate the classes. Confidence bounds account for finite test seeds even if every prediction is correct. The permutation p-value tests label association with the already frozen predictions.

A convincing run has a power accuracy interval above 50% and a small p-value. Compare against total timing and inspect the waveform/score plots. A negative result is retained. Results apply to this balanced seed population, warmed target and exact build; fresh-session replication strengthens the claim.

## 7. Disconnect

Release the board for another notebook.

The [full calibration and experimental method](../../Full%20SampleNTT%20Method.ipynb), original measured run, and Git checkpoint remain available. Source integrity checks, per-trace digests, raw waveforms, failure logs and model fingerprints are retained by the helper code.


## Earlier explanations: Lab 7_2 - ML-KEM FLS Power Lab.ipynb

# Lab 7.2 — Can fixed-loop SampleNTT still leak through power?

**ChipWhisperer Husky + CW308_STM32F4 · ProjectTempo top-level A1 (FLS)**

This lab asks whether **one physical power trace predicts the first candidate's accept/reject decision on a new seed** after replacing A0 with the Fixed Loop Sampler. A1 processes 280 pairs on every call and uses masks and fixed memory scans. Its values can still affect power consumption. We measure the outcome; success is not assumed.

Use **chipwhisperer-new/.venv** as the notebook kernel. Disconnect the A0 notebook first, then use a fresh kernel and run these nine sections in order. The hardware cells build and program the **STM32 target**, not the Husky USB firmware or FPGA. Installing or opening this notebook does not run a capture.

The [short A0 lab](../../Lab%207_1%20-%20ML-KEM%20SampleNTT%20Power%20Lab.ipynb) and [full A0 method](../../Full%20SampleNTT%20Method.ipynb) live beside this notebook. [Tempo paper](https://eprint.iacr.org/2025/1399) · [Authors' implementation](https://github.com/afonsoarriaga/ProjectTempo).

We use the pinned **top-level `src/algorithm_a1.c`**, which differs from the authors' pqm4 copy. Fixed loops are a source-level design: this notebook does not certify constant-time machine code. Separate duration measurements help distinguish timing evidence from power classification.


## 1. Load and configure

Default: 128 seeds per class for training and another 128 per class for testing, **512 captures total, one per seed**. Calibration/check captures are separate. The classes are balanced; candidate one is accepted, and the output first fills on candidate 320. FLS still visits all 560 candidates, including the suffix after filling. This conditions the input population rather than estimating accuracy on arbitrary seeds.

The low-gain advisory is suppressed by default, following the working A0 setup. **Clipping detection remains enabled.** Pick gain before training. To resume, set `RESUME_RUN` to the printed run folder and keep all settings identical. Each notebook needs its own kernel.


## 2. Build FLS and its separate calibration image

This cell compiles both images, checks the pinned sampler source hashes, and saves build logs and assembly. It does not open USB. The measurement image contains the ordinary sampler; only the calibration image records the first two SHAKE-call boundaries.

The printed `.asm` file is available for checking `algorithmA1` and its helpers. Loop branches should depend on fixed bounds, not candidate validity. Compiler output and memory accesses matter: stable timings alone do not prove this property. Build metadata deliberately retains `constant_time_verified = False`.


## 3. Locate the first FLS pair

This connects Husky, programs the **calibration target image**, warms the target, and measures eight balanced calibration inputs. Between the first SHAKE return and the second SHAKE entry, A1 performs both 256-element scans for the first pair. The printed cycle counts compare rejected and accepted first candidates.

The ADC stores only a short window during calibration; the DWT markers and trigger counter measure later events through completion. A padded window is derived from the markers and saved once. Wrapping and code layout change timing, so these are approximate guides. **Calibration traces never enter training or testing.** A resumed run reuses its original window.


## 4. Restore ordinary FLS and inspect the waveform

This programs the uninstrumented measurement image, verifies its FLS identity and polynomial digests, and shows a separate check trace. Orange markers are approximate first-pair boundaries from calibration. Check that the waveform has useful variation and no clipping. If gain needs changing, start a fresh run before training.

The captured window is deliberately shorter than the full FLS operation. The **whole-operation trigger duration** is still recorded for every input; it is read after computation completes. The first two measurement calls warm the target and are excluded from model data.


## 5. Capture training data

The lab declares disjoint, balanced training/test seeds and excludes prior planned seeds and recorded check inputs. Labels are independently calculated from SHAKE, and every target output is checked by its full polynomial digest. Trial order is randomized. Each success is checkpointed; a failed attempt is logged and stops acquisition. Rerunning resumes the remaining trials without discarding difficult seeds.


## 6. Select and freeze using training only

Four-fold cross-validation searches windows inside the calibrated first-pair capture. Sample-point selection runs inside each fold. A regularized logistic classifier is then fitted to training data; a separate linear model uses total duration. The best searched CV score is an optimistic development diagnostic, **not the final result**.

This saves numeric model coefficients, selected points, a fixed threshold, source hashes, image/settings identity, and the training-data fingerprint. It cannot overwrite an existing frozen model. There is no single shuffled-training-label model presented as a passed negative control.


## 7. Capture the fresh test

All test seeds are new. Each capture is stamped with the already frozen model hash. Keep gain, clock, window, warning policy, and firmware fixed. Once these results have been seen, any model or window change requires a new plan and a fresh test.


## 8. Evaluate power and timing separately

The table reports correct predictions, balanced accuracy (chance = 50%), conservative exact 95% bounds, and AUC (chance = 0.5). Exact bounds retain uncertainty even for a perfect finite test. The fixed-model test-label permutation p-value measures prediction/label association. All planned captures must be present.

The timing diagnostics compare whole-operation durations with a Welch mean test and a KS distribution test, using a 0.025 threshold per test. Quantized, constant counters are handled explicitly. No detected timing difference **does not prove constant time**, and whole-operation timing can hide local variation. Calibration first-pair timing and compiled-code inspection provide additional context.

- Power succeeds: evidence of first-candidate information in this FLS build's traces. Establishing the physical mechanism requires further work.
- Timing also differs: investigate it before describing the result as independent of timing leakage.
- Power is near chance: this particular experiment did not demonstrate a distinguisher. Preserve the negative result; it does not prove resistance to every power attack.

The figures show power scores, whole-operation durations, and the confusion matrix. `report.json` retains capture failures/retries. These results concern known public seeds on a warmed target; they do not demonstrate secret-key recovery.

To review a completed run without hardware after restarting: run section 1 with its `RESUME_RUN`, then this section.


## 9. Disconnect

Release the device before opening another hardware notebook. If you interrupt a capture, run this cell before restarting the kernel.
