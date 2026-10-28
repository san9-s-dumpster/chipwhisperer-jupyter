# Short notebook validation

The main notebook now has seven executable cells. The former full workflow is
preserved in Full SampleNTT Method.ipynb and in the checkpoint commit.

The short flow retains real hardware capture, pinned/hash-checked source,
exact calibrated image/window binding, identity and polynomial verification,
ADC error checks, per-trace checkpoints, independent balanced seed cohorts,
training-only sample selection, an immutable model before fresh-test capture,
and comparison with a total-duration baseline.

The main proof fixes the window before collecting any new data. It uses one
capture per seed, omits redundant repeat averaging and the misleading single
shuffled-training-label diagnostic, and reports conservative exact confidence
bounds for balanced accuracy. The fixed-model test-label permutation p-value
is computed exactly from its hypergeometric distribution.

Validation: 121 tests passed, including all seven code cells executed against
an explicitly fake device, and exhaustive small-sample checks of the exact
permutation calculation. No fake outputs are embedded in the notebook.

The actual ARM cross-build reproduces the reference image hash. Replaying the
existing measured development and test traces, cropped to the preselected
512-sample window, reproduces 256/256 correct and a conservative 95% balanced-
accuracy interval of 96.63–100%. This is recorded-data software validation,
not a new physical capture or an independent-session replication.

The direct 512-sample live acquisition path must still be exercised on the
board. Hardware and build compatibility remain tied to proof-preset.json;
use the full method for a different image, target, clock or calibration.
