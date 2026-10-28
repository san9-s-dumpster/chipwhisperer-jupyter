# Validation record — 2026-10-28

- 71 pytest tests passed, including deterministic C/Python equivalence,
  full-polynomial regression vectors, byte order, rejection boundaries,
  post-fill FLS labels, exceptional shortfalls, dataset round trips,
  seed-disjoint evaluation, and mocked capture error handling.
- All 22 notebook cells completed from a fresh Python kernel. The default
  path never imported/opened a capture device and never flashed firmware.
- An additional 16 seed/index pairs per variant matched the unchanged C
  reference during the notebook run.
- The notebook captured and reloaded 192 mock traces per variant (96 seeds,
  two repetitions), with zero failed mock trials. The 384 traces were
  synthetic. Repetition averaging preceded the seed-level train/test split.
- Both adapter variants cross-compiled against the user's ChipWhisperer
  checkout at `e7f47d853a5d412872069f306c4ed16be9ab7f08`, using
  `PLATFORM=CWLITEARM`, `SS_VER=SS_VER_1_1`, `OPT=2`, `CRYPTO_TARGET=NONE`.
  Compiler: `arm-none-eabi-gcc (15:14.2.rel1-1) 14.2.1 20241119`.
- The compiled `algorithmA1` body was inspected: two scan loops compare
  their public loop counters to 256 and the outer loop runs 280 times;
  coefficient accesses in those scans advance sequentially. This limited
  inspection does not audit the full binary or certify constant-time behavior.
- Figures were visually inspected for readability. Example computed ground
  truth and explicitly labeled synthetic figures/metrics are included under
  `results/figures` and `results/metrics`.

Validation ran on the provided Linux execution environment with Python 3.12.
The package versions used are recorded in `requirements-tested.txt`.
The README supplies the requested Arch Linux setup commands. They were not
executed as system package installations during this work.

No physical capture device was connected, queried, programmed, or measured.
Live CW-Lite/Husky operation, candidate-operation localization, electrical
settings, full FLS timing behavior, and seed distinction remain unvalidated.
The hardware unit tests use fake scope/target API objects only.

Generated ELF/HEX files and the large mock trace datasets are omitted from
the installed source package. Build them or rerun the notebook to regenerate
artifacts on the selected system. The sample metric files document only the
mock experiment and must not be used as hardware evidence.

## Hardware-notebook revision

The user confirmed **Husky + CW308_STM32F4**. The main Lab 7_1 notebook was
rewritten as a hardware-first workflow with 40 cells (20 executable code
cells), covering connection, real firmware build/program calls, ADC/window
configuration, firmware handshake, verified single capture, randomized
batches, plots, timing and ROI classification, a separate FLS pass, reload,
and disconnection. The old mock workflow is a separate software-validation
notebook in the companion folder.

Both adapters cross-compile for `CW308_STM32F4` with the local ARM compiler.
All 20 hardware-notebook code cells were executed sequentially in a fresh
Python process using **fake ChipWhisperer device objects** and the real
STM32F4 compiler. The harness exercised both programming calls, identity and
polynomial checks, 128 fake captures per variant, analysis, saving/reloading,
and disconnect. Test-harness data is kept in scratch space and is not shipped
as measured data. Notebook format and code-cell syntax were checked.

The revised pytest suite has 77 tests, including attaching to an existing
scope/target, a lowercase `cwhusky` device representation, handshake/window
mismatch failures, progress wrapping, partial batches on interruption, and
ROI evaluation with seed-disjoint train/test splits.

This validates software behavior and compilation, not USB/ADC behavior or
physical measurements. No target was programmed and no physical capture was
performed by the agent. Husky streaming settings are exposed in the notebook
but their throughput and trigger coverage must be checked on the real setup.

## Migration to chipwhisperer-new

The main notebook and companion folder now live together in
`chipwhisperer-new/jupyter/courses/custom`. The notebook resolves the checkout
from the companion folder, and setup commands use the new repository.
The new repository's Python 3.14.4 `.venv` has the lab requirements installed.
All 77 tests passed in that environment, and both CW308_STM32F4 firmware
variants compiled against ChipWhisperer commit
`8406f685e67e19c758b391ee75c94607260ac732`. The firmware-support submodule is
at its pinned `e1a787f189b2938f3ebfc64a14b15d01a2d54b2e` revision.
Notebook imports and repository discovery were verified from the new checkout.

## Identity command collision fix

The original adapter incorrectly registered its identity callback as `v`,
which SimpleSerial registers first as its built-in protocol-version command.
The v1.1 dispatcher therefore returned `z01` instead of an identity payload.
The application request/reply now use `i`; the built-in `v`, `w`, and `y`
commands remain available. This change requires rebuilding and programming
the STM32F4 adapter and reloading the Python recorder in a live kernel.

Eight added integration checks compile the actual adapter and upstream
SimpleSerial C parser with only UART/GPIO HAL stubs. They check reserved
version behavior, unique registrations, identity payloads, polynomial
digests, ACK alignment, and the real Python SimpleSerial client connected
to that C parser through pipes. Both sampler variants are tested. The full
suite passes 85 tests, and both corrected ARM firmware variants compile.
The original fake-device tests did not model reserved command dispatch.
No physical target was reprogrammed by the agent for this fix.

## VT distinguisher v2 (2026-10-28)

Replaced the active hardware notebook with a variable-time-only workflow:
full survey, separate DWT localization image, restore representative image,
matched/balanced cohorts, development-only window search, frozen numeric fit,
post-freeze final acquisition, seed bootstrap/permutation inference and controls.
Existing physical captures remain historical; no new physical success is claimed.

Validation in chipwhisperer-new's Python 3.14.4 environment:

- 99 pytest tests pass, including injected-signal/noise cases, distinct seed
  cohorts, matched final fill count, immutable artifacts, mixed-condition and
  calibration rejection, live-setting mismatch, DWT reply validation and
  checkpoint resume. The existing real C SimpleSerial-parser tests still pass.
- Both ARM profiles compile for CW308_STM32F4 at O2. Representative assembly
  has no `lab_timing` / wrapper symbol; calibration A0 calls the wrapper and
  the wrapper calls the original SHAKE function. Vendored source hashes pass.
- All 19 notebook code cells execute sequentially with a fake device and the
  real build toolchain. Synthetic fixture data stayed in scratch, outside user
  run data; no fixture outputs are embedded in the installed notebook.
- Notebook format and Python-cell syntax validate. The generated report plot
  was inspected for legibility using synthetic software-test data only.

A physical execution of sections 4–13 is still required to measure candidate
location, data quality and held-out performance. Fake API tests do not verify
DWT operation, probe wiring, real waveform alignment or leakage on the board.
