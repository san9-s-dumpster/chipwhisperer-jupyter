# FLS notebook validation

The interactive FLS notebook is `../Lab 7_2 - ML-KEM FLS Power Lab.ipynb`, relative to the companion folder. All three hardware notebooks now live in `jupyter/courses/custom`; the full A0 notebook was moved byte for byte, preserving its latest outputs.

Software validation completed on October 28, 2026 (America/New_York): **138 tests passed**. The tests include fake-device execution of the FLS acquisition, calibration, freeze, fresh-test, reporting and cleanup cells; missing/duplicate/calibration/A0/mock trace rejection; ADC policy enforcement; interrupted capture resumption; and hardware-free result reload. Fixtures explicitly inject synthetic signals and are not evidence of physical FLS leakage.

Both STM32F4 images cross-compiled with `arm-none-eabi-gcc 14.2.1`, optimization `-O2`:

- Measurement HEX SHA256: `b1913a9f200fec71840e19211f65144e45fffdc9997e614549481c29d8020478`
- Calibration HEX SHA256: `64c179a12305a335df10269166faac05568b4a7351d35c3fdc28d682768f28e8`

These are build checks, not a pre-calibrated FLS preset. The notebook builds and localizes its own image pair on the selected board. Build artifacts are not installed from the staging environment.

A manual inspection of the measurement build's `algorithmA1` found three conditional branches: the two 256-element scans and the 280-pair outer loop. Candidate comparisons become arithmetic masks; scan addresses advance by fixed strides. This spot check is not an audit of SHAKE, allocation, the complete binary, or microarchitectural timing. The model/report keep `constant_time_verified = False`.

The unchanged upstream top-level A1 source is selected. It differs from the upstream pqm4 A1 implementation. First-candidate label balance, a valid second candidate, and a common first-fill position condition the seed population. All 280 pairs still execute; the suffix and total count of valid candidates are not fixed.

Power uses independent development-only window/point selection, a frozen numeric model and a fresh single-capture test cohort. Confidence bounds and fixed-model test-label permutation probabilities use the exact methods from the short lab. Timing includes a linear frozen baseline, a Welch mean test and a KS distribution test. Failure to detect a duration difference is not a constant-time proof and cannot exclude local timing variation. A negative power result does not establish power resistance.

Existing A0 analysis source hashes remain unchanged. Both saved full-method frozen models and the saved short-lab frozen model were successfully loaded using the updated tree. No hardware was opened, flashed, or captured during development/installation.
