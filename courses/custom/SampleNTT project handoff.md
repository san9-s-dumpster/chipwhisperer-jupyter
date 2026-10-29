# SampleNTT / FLS power-analysis project — Codex handoff

This is context for continuing an existing physical ChipWhisperer experiment on another computer. The work already includes functioning interactive capture notebooks, measured A0 and FLS results, and a published Git branch. Inspect the new computer and checkout before changing anything; paths below identify the original machine unless stated otherwise.

## 1. Project and user preferences

- Investigate whether a power trace reveals the **first SampleNTT candidate's accept/reject decision**, including in a fixed-loop implementation intended to avoid timing leakage.
- The user wants real, explanatory, executable Jupyter labs like ChipWhisperer's SCA101/SCA201 notebooks. Helper modules are fine, but the notebook must let them build, program, capture, train and evaluate their actual hardware.
- Keep the notebook readable. All hardware notebooks belong together in `jupyter/courses/custom`, not SCA101 or the companion `docs` folder.
- Preserve existing measurements, executed notebook outputs, frozen models and the Git checkpoint. Never tune a classifier against an already inspected final test.
- The user explicitly corrected the Git workflow: **push the existing lab branch to `samplentt`; do not rebase/cherry-pick it onto their fork's `main`, merge it into `main`, or modify remote `main`.**
- Previously approved Git author: `Alexandru Scurtu <sasha.scurtu@gmail.com>`. Use repository-local configuration if needed.

## 2. Published repository and exact checkpoint

Repository: https://github.com/san9-s-dumpster/chipwhisperer-jupyter

Branch: **`samplentt`**

Published HEAD when this handoff was written: **`a8f2d85ef9ac5a5a0ae0666a70b70860569ba981`**.

Recent history, newest first:

| Commit | Purpose |
|---|---|
| `a8f2d85` | Save the long SampleNTT/FLS explanation verbatim as Markdown |
| `04d7678` | Add the measured FLS lab, move the full method beside the short lab, preserve executed outputs |
| `01722e1` | Simplify A0 to a short fixed-window proof notebook |
| `ff0716f` | Checkpoint the first validated A0 experiment, including a compressed raw-data/build archive |

The original lab history was preserved. Remote `main` remained at `705ff2da36050088f5125c3e215e9ed17ea370f0` when the push was verified. A temporary attempt to prepare commits on the fork's `main` was abandoned before any push; those rewritten commits are **not** the published branch.

On the original PC the publication was made from a separate checkout at:

`/home/ubuntu/Documents/Codex/2026-10-28/i-x20/work/github-samplentt`

The physical working checkout remained:

`/home/ubuntu/Desktop/work/chipwhisperer-new`

Its `jupyter` directory is a separate Git repository/submodule. The old live Jupyter checkout still had local changes on `samplentt-power-lab`; it was not reset to the published branch. Do not assume that original working checkout has a clean Git state.

## 3. What to clone on another PC

The GitHub repository above is the **Jupyter repository**, not the complete ChipWhisperer software/firmware checkout. The lab also needs the parent ChipWhisperer repository, including `firmware/mcu/Makefile.inc` and STM32F4 HAL support.

The tested parent software baseline was upstream ChipWhisperer commit:

`8406f685e67e19c758b391ee75c94607260ac732`

Local parent commits `cdf1ae21bfa55599fd0eaa8a6409b82f76d57f39` and `2fdd66ae91e63699bfb81684893006ed9cd3f3c2` changed only the Jupyter submodule pointer. They did not add a private STM32F4 HAL patch.

Example **for a fresh directory**, adapting the location to the new PC:

```bash
git clone --recurse-submodules https://github.com/newaetech/chipwhisperer.git chipwhisperer-new
cd chipwhisperer-new
git checkout 8406f685e67e19c758b391ee75c94607260ac732
git submodule update --init --recursive
git -C jupyter remote add samplentt-project https://github.com/san9-s-dumpster/chipwhisperer-jupyter.git
git -C jupyter fetch samplentt-project samplentt
git -C jupyter switch --create samplentt --track samplentt-project/samplentt
```

Run submodule initialization **before** switching Jupyter to the project branch. A later parent `git submodule update` can detach/reset the Jupyter checkout to the parent's recorded commit. Inspect existing work before using these commands on a non-fresh directory.

The original machine ran Python **3.14.4**, ChipWhisperer **7.0.0**, and `arm-none-eabi-gcc` **14.2.1**, with firmware optimization `-O2`. The parent uses a root `pyproject.toml`; install the parent checkout itself, not a guessed `software/setup.py` package.

Typical environment setup, after ensuring the selected Python has working venv/pip support:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r jupyter/courses/custom/mlkem-samplentt-power-lab/requirements.txt
```

`requirements-tested.txt` records the original package versions; treat it as an environment record, not a guarantee that every version works with every new Python/platform. Install the required ARM cross-compiler, binutils, C library and `make` as appropriate for the new computer. Configure normal ChipWhisperer USB access on that system.

Select the `.venv` interpreter explicitly in VS Code/Jupyter. Previously, VS Code selected `/bin/python3` even though `ipykernel` was installed in `.venv`. Check `sys.executable` and `chipwhisperer.__file__`; the original import came from `chipwhisperer-new/software/chipwhisperer/__init__.py`.

## 4. Repository layout

Relative to the full ChipWhisperer root:

```text
jupyter/courses/custom/
  README.md
  Lab 7_1 - ML-KEM SampleNTT Power Lab.ipynb
  Full SampleNTT Method.ipynb
  Lab 7_2 - ML-KEM FLS Power Lab.ipynb
  SampleNTT and FLS explanation.md
  mlkem-samplentt-power-lab/
    analysis/
    capture/
    firmware/
    reference/
    tests/
    checkpoints/
    docs/
    results/
```

- **Short A0 notebook:** seven authored code cells, plus a user-added low-gain-policy cell in its executed version. Uses an exact-image-bound, fixed 512-sample window; no new window search per run.
- **Full A0 method:** survey, separate timing calibration, ordinary-image restoration, development-only window selection, frozen fit, fresh final test. Its latest saved section 13 reports 252/256 single-trace predictions. Moved out of the companion `docs` folder with all output bytes preserved.
- **FLS notebook:** nine code cells for setup, build, localization, ordinary-image restoration/check, training, freeze, fresh test, results, disconnect. Its saved outputs contain the physical FLS run described below.
- **Explanation Markdown:** the previous approximately 30-minute explanation was exported verbatim. Preserve its wording if editing around it. Its image link intentionally retains an original-PC absolute path; that figure will not automatically render on another PC or GitHub without access to the image.
- The companion also contains a software-validation notebook and clearly identified synthetic examples. Those are not physical leakage evidence.

Key modules:

| File | Role |
|---|---|
| `capture/hardware.py` | Attach to existing scope/target, verify firmware identity and output digest, acquire raw ADC codes, enforce settings |
| `capture/cohort.py` | Randomized, resumable acquisition; per-success checkpoints and failed-attempt logs; A0/FLS dispatch |
| `capture/lab.py` | Short A0 hardware workflow |
| `capture/fls.py` | FLS workflow and explicit ADC warning policy |
| `analysis/ground_truth.py` | Independent SHAKE-based candidate, validity and polynomial calculation |
| `analysis/distinguisher.py` | Original full A0 analysis and reusable point selection/scoring |
| `analysis/proof.py` | Short A0 exact uncertainty and fixed-model test-label permutation calculations |
| `analysis/fls.py` | FLS plan/validation, development-only selection, frozen fit, power and timing evaluation |
| `firmware/build.py` | Clean measurement/calibration builds, hashes, logs, disassembly; no flashing itself |
| `firmware/common/main.c` | SimpleSerial adapter around the unchanged sampler |

Some older documentation contains historical wording about FLS being deferred or STM32F3. The active hardware is **CW308_STM32F4**. Use current notebook code and actual build metadata to resolve such discrepancies.

## 5. Hardware and measurement protocol

- Capture board: **ChipWhisperer Husky**.
- Target: **CW308_STM32F4**, detected as STM32F40xxx/41xxx.
- Original Husky serial: `502032204c5846303230373132313032`; configure the new attached device rather than assuming this serial.
- Clock requested near 7.3728 MHz; measured target clock was approximately **7,363,636.36 Hz**.
- ADC multiplier 4; measured ADC frequency approximately **29,454,545.45 Hz**.
- SimpleSerial **1.1**, baud **38400**.
- HS2 supplies target clock; TIO1 serial RX, TIO2 serial TX; TIO4 basic rising-edge trigger.
- Requested gain **10 dB**, quantized actual gain **9.770642 dB**.
- Non-streaming; one segment; no presamples; decimation 1.
- Records explicitly use `get_last_trace(as_int=True)`: raw 12-bit ADC codes stored as float32, not calibrated watts.

Keep the known-working power/shunt/probe/jumper wiring and document physical changes. The notebook does not fully describe every original physical jumper, so inspect the actual board setup.

The trigger encloses the unchanged upstream sampler, including SHAKE and allocation/release. Polynomial initialization, output hashing and UART replies occur outside the trigger. Trigger duration is read **after the completed target reply**, so it measures the full operation even when only an early waveform window is retained.

Separate calibration firmware uses Cortex-M4 cycle markers and a linker wrapper around SHAKE squeezing. The first pair is processed between the first squeeze return and the second squeeze entry. These markers are approximate because wrapper overhead and flash layout differ. Calibration captures are never accepted as model data. Ordinary measurement firmware must be restored before training/test.

Two non-model measurement calls warm the target. Current claims primarily concern a warmed target.

## 6. Exact sampler and input population

Paper: https://eprint.iacr.org/2025/1399

Authors' code: https://github.com/afonsoarriaga/ProjectTempo

Pinned revision: **`fd72834bd789c644b52fe0d62b2fa3b9f34dfaec`**.

The selected unchanged files are **top-level** `src/algorithm_a0.c` and `src/algorithm_a1.c`. Vendored source hashes are recorded and checked. The upstream pqm4 A1 copy behaves differently internally; do not substitute it or pool its data under the same FLS identity.

- Inputs: 32-byte seed followed by literal bytes `x`, `y`; experiments use `x=y=0`.
- First candidate accepted iff its 12-bit value is **less than 3329**.
- Output: 256 accepted coefficients.
- A0 conditionally stores accepted candidates and stops when full, with a 280-pair cap in this pinned implementation.
- A1/FLS always processes **280 pairs / 560 candidates**, scanning all 256 output slots twice per pair. Its top-level implementation tentatively writes at the current slot even for rejected candidates, then advances the counter by 0/1. Later candidates overwrite rejected tentative values. Its counter continues past 256; scans continue after the output is full.
- The lab rejects incomplete-output cases and verifies the complete polynomial digest.

Plans have 128 seeds per class per cohort by default, randomized capture order, separate training/test seeds, and exclusions of prior available plans/recordings. Candidate one (the second candidate) is accepted. Output first fills on candidate **320**.

For A0, this means exactly 160 pairs and 256 accepted/64 rejected visited candidates. FLS still processes all 280 pairs, including a suffix whose values/validity count are not fixed. This is a deliberately balanced, workload-conditioned seed population; it does not estimate ordinary-random-input precision or accuracy at every candidate position.

## 7. Verified physical results

All figures below concern fresh independent test seeds. The primary endpoint uses one trace per seed.

| Run / notebook | Power correct | Power balanced accuracy | Power AUC | Total-duration baseline |
|---|---:|---:|---:|---:|
| First validated full A0 | 256/256 | 100% | 1.000 | 58.20% |
| Short A0 | 255/256 | 99.61% | 0.998962 | 52.73% |
| Later full A0, section 13 discussed with user | 252/256 | 98.44% | 0.992615 | 56.25% |
| FLS | **250/256** | **97.66%** | **0.991333** | **50.00%** |

Original run directory names under `results/runs/`:

```text
vt-v2-20261028T220911Z-09b982       first validated full A0
proof-20261028T232020Z-ca5338       short A0
vt-v2-20261029T004128Z-b54c09       later full A0
fls-20261029T010815Z-1da2fa         physical FLS
```

UTC timestamps in names cross midnight; locally these experiments were on October 28, 2026, America/New_York.

The full A0 method uses two captures per seed: 1,024 captures total across development/test, with 256 independent seeds in each cohort. Its primary result uses repeat 0. The later run's separate two-capture averaging model achieved 256/256. This is a two-capture result, not a larger independent test sample.

### FLS details

- 256 training captures + 256 test captures, one per seed, 128/class in each.
- All 512 waveform arrays distinct; direct independent SHAKE decoding and polynomial verification passed.
- Refitting from training alone reproduced both saved models exactly.
- Model/plan/source hashes and dataset fingerprints validate. Training preceded freeze; all test captures followed freeze.
- No capture failures or retries. No ADC rail hits. Clipping detection enabled throughout. Actual model-data ADC codes span 1580–2530.
- Every training/test capture recorded exactly **8,690,816 ADC ticks**, equivalent to **2,172,704 target CPU cycles**, approximately **295.058568 ms**.
- Eight balanced calibration inputs all recorded **7,236 cycles** for the first pair, and 280 squeeze calls.
- Confusion matrix, rows actual and columns predicted, reject then accept: **`[[124,4],[2,126]]`**.
- Conservative exact 95% balanced-accuracy bounds: **92.6201%–99.5878%**.
- Exact fixed-prediction test-label permutation p: **`1.5514224169611787e-65`**.
- Frozen model SHA256: `24c0d7e8a4e09b4e06045f6d9f0597230f07e1f4d17078ab7cf67a294efa9da3`.
- Measurement image SHA256: `b1913a9f200fec71840e19211f65144e45fffdc9997e614549481c29d8020478`.
- Calibration image SHA256: `64c179a12305a335df10269166faac05568b4a7351d35c3fdc28d682768f28e8`.
- Capture window: offset **93168**, length **37248** samples. Selected relative power window **[26624,34816]**, 16 selected sample points.
- Selected absolute window **[119792,127984]**, approximately target CPU cycles **29948–31996**. It spans the end of the first pair and subsequent processing relative to approximate calibration markers. Do not attribute all leakage to one comparison instruction.

### A0 details and older reporting limitations

- Earlier calibration observed 71 cycles for accept/accept versus 64 for one reject/accept pair. Class mean waveforms aligned much more closely after a 28-ADC-sample / 7-CPU-cycle shift. This supports a local timing explanation, with limited calibration observations and different calibration-image layout.
- Short A0 conservative exact 95% bounds: **95.8764%–99.9951%**. Its one genuine false acceptance must remain in the result.
- The old full-method bootstrap can print `[1,1]` after perfect classification; that does not establish guaranteed perfection. Exact conservative bounds for the initial 256/256 result were approximately **96.63%–100%**.
- A single shuffled-training-label model was an unreliable diagnostic: earlier it learned an inverse association; the later full run scored 59.38%. Do not claim all controls passed. New short/FLS evaluation uses fixed-model **test-label** permutation probabilities and exact uncertainty instead.
- The timing baseline is linear; poor performance does not rule out all timing attacks.

## 8. Supported conclusion and limits

The defensible statement is:

> On the tested STM32F4 and pinned sampler build, power traces reveal the first candidate's accept/reject decision on fresh, balanced, workload-conditioned seeds. FLS maintained identical measured total durations while power classification achieved 250/256 correct predictions. Constant-time execution does not by itself guarantee resistance to power analysis.

Candidate values, masks, counters and coefficient updates are plausible FLS leakage sources; the exact causal mechanism has not been isolated. Fixed loops and equal measured durations do not constitute a universal machine-code/microarchitectural constant-time proof. Build/model metadata correctly retain `constant_time_verified = False`.

This is **not** demonstrated secret-key recovery, unknown-seed recovery, an attack on all candidate positions, cross-session reliability, or a break of the Tempo protocol. The profiling seeds are known public inputs so true labels can be computed. Ordinary ML-KEM treats the matrix seed as public; Tempo's protocol-level approach exposes that seed deliberately rather than making it password-dependent.

Do not claim FLS is universally weaker/stronger than A0 from small differences between separate runs.

## 9. Critical migration issue: raw data are not all on GitHub

The current notebooks, code, executed output cells, and explanation are on GitHub. **New run folders and build outputs are Git-ignored.** Cloning the branch alone will not restore the latest FLS raw traces, model, plan and complete audit records.

The first validated A0 checkpoint **is** committed at:

`courses/custom/mlkem-samplentt-power-lab/checkpoints/validated-2026-10-28/`

Its `measurements-and-builds.zip` is 30,472,825 bytes, archive SHA256:

`8abbad25f6607fd8d176cc5cb056f124950fe547e543fbeea70b4893a1a88643`

The ZIP contains an internal checksum manifest. Extract it into a separate inspection directory instead of overwriting active results. It predates the short A0, later full A0 and FLS runs.

**Before leaving the old PC, copy separately:**

1. The companion's complete `results/runs/` directory, especially the four named runs above. Preserve all NPZ/JSON files, plans, frozen models, reports and `attempts.jsonl` logs.
2. Firmware build records and artifacts for the four profiles: `variable_time`, `variable_time_calibration`, `fls`, `fls_calibration` (`build.json`, HEX, ELF, ASM and build logs). These preserve exact-image and compiler evidence.
3. The independent review artifacts from `/home/ubuntu/Documents/Codex/2026-10-28/i-x20/outputs/`: `FLS physical-run evaluation.*`, `SampleNTT short-run evaluation.*`, `SampleNTT VT v2 evaluation.*`, and the verbatim explanation if useful. Later full A0 results are in its run's `final-report.json` and notebook output.

Without those copies, a new Codex can inspect saved notebook results and run new experiments, but cannot independently re-audit the latest physical waveforms or reuse their frozen model. A virtual environment can be recreated; do not rely on copying `.venv` between PCs.

## 10. Hardware troubleshooting already resolved

- **One owner per USB board:** disconnect the other hardware notebook/kernel before connecting. Do not open a second diagnostic connection while a kernel owns the Husky.
- A previous `Unknown hwInfoVer` / `Unknown ChipWhisperer` failure followed an interrupted ADC transfer and shifted raw register replies. Recovery cleared register 36 (`FAST_FIFO_READ_MODE`) and restored normal SMC timing. `capture.lab.normal_husky_bus` already performs startup normalization; the non-streaming capture exception path attempts `scope.sc.setFastSMC(0)` cleanup.
- Do not reintroduce unconditional FPGA reloads or Husky USB firmware updates as routine startup. Previous recovery succeeded without a new firmware update. Original USB firmware was 1.7.0.
- **ADC clipped:** lower gain before starting model data; keep clipping checks enabled. A changed recording condition requires a fresh experiment.
- **Low-gain advisory:** the short lab initially rejected one training attempt for this advisory. Analog gain stayed unchanged; the user set `scope.adc.lo_gain_errors_disabled=True` while keeping `scope.adc.clip_errors_disabled=False`, refreshed the recorder snapshot, and resumed the missing trial. There were no test retries. FLS now exposes the same explicit advisory policy consistently from setup.
- Prefer a fresh notebook kernel. Earlier `profile` errors came from stale imported builder code; earlier `recorder` errors came from continuing after a setup cell failed. Current setup reloads/guards address those cases.

## 11. Tests, image guards and future work

Latest software validation: **138 tests passed**. Both FLS measurement and calibration firmware cross-compiled. Fake-device tests exercise workflow/integrity only and never establish physical leakage. On a fresh PC, a reference-build-dependent fixture may skip until the required local image exists; inspect skips instead of claiming the same test coverage blindly.

Run from the companion folder:

```bash
python -m pytest -q
```

The short A0 preset is bound to measurement HEX SHA256:

`fbe72dbef701cfd52eb08b3ca895c66112c9296e3d89797c0ff2301b318f91f3`

A different compiler/library/build can change that image. **Do not weaken the hash guard or reuse old sample positions blindly.** Reproduce the tested build or use the full A0 method to recalibrate and establish a new preset with separate data. FLS calibrates its newly built measurement/calibration image pair; old frozen classifiers still require matching conditions.

Frozen FLS models bind analysis and capture source hashes. Editing those files can deliberately invalidate existing frozen-model loading; preserve the originals when planning a replication.

A sensible next scientific step is a separately declared **new-session test of the existing frozen FLS model** on fresh seeds, with an explicit warmup protocol. Current default notebooks retrain on each new run: repeating them is a replication of training-and-testing, not a test of the old classifier's portability. `RESUME_RUN` resumes the original declared cohort; it does not automatically create a new independent test set.

Implement a separate, clearly bound replication protocol if requested. Do not mutate the old plan/model to attach new seeds, bypass source checks, or retune against the inspected holdout. Additional possible work includes ordinary input populations, other candidate positions, and causal investigation of which data operations leak.

The next action should follow the user's new request; this handoff itself is context, not an instruction to recapture, flash hardware or publish additional changes automatically.
