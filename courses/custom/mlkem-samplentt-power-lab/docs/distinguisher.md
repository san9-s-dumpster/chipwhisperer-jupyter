# VT candidate-zero experiment, version 2

## Question and population

Predict `candidate[0] < 3329` from power for an unseen public seed, with the
pinned top-level ProjectTempo A0 on the specified STM32F4 build. This is a
profiled binary property classifier, not seed identification or key recovery.

Each cohort has 128 accepted and 128 rejected first candidates by default.
Candidate one must be accepted and the complete sampler must take exactly
160 pairs (three SHAKE rate blocks), with the 256th accepted coefficient
reached on candidate 319 (zero-based). Thus every input has exactly 256
accepted and 64 rejected candidates in its 320 visited candidates. Development and final-test domains are
fresh and disjoint; previous saved seeds are excluded. Each seed is captured
twice. Repeat zero defines the primary single-trace analysis; repeat means
are a secondary analysis, with no extra independent observations.

The conditioning removes a large timing confound and adjacent-candidate
label imbalance. It does not match every intermediate rejection pattern,
candidate bit pattern, or Hamming weight. Accepted and rejected 12-bit values
necessarily occupy different ranges. Consequently, even a successful test
would establish a localized validity association, not prove causal leakage
from a specific comparison/branch. It also cannot supply natural-prior
precision (ordinary candidates are accepted with probability 3329/4096).

## Location and measurement

1. Representative image: ordinary A0, trigger enclosing the whole upstream
   function. Record an offset-zero 1× ADC survey covering the whole trigger.
2. Calibration image: use Cortex-M4 DWT CYCCNT and linker
   `--wrap=shake128_inc_squeeze`; capture first two entry/return pairs and total
   cycles/call count. The sampler/SHAKE sources themselves remain unchanged.
3. The first pair is processed between the first squeeze return and the second
   squeeze entry. Use a padded region around these landmarks, sampled at 4×.
   Counter starts slightly before the trigger and wrapper/layout change timing;
   annotations are approximate. Padding is 512 core cycles before, at least
   1536 after, and a minimum 8192-sample window. Inspect the ordinary image.
4. Restore/program the ordinary image, verify its identity, and collect all
   model data with that one build and window. The analysis rejects the
   calibration profile and mixed hardware settings.

The STM32F4 HAL uses external HSE without CPU PLL scaling in the default
build. Check total DWT cycles against trigger-derived core cycles rather than
assuming an arbitrary clock ratio. Build assembly confirms that only the
calibration image contains the wrapper. Calibration is a guide, not cycle-
accurate instrumentation of the representative binary.

## Development and freeze

Randomize seed/repeat trial order separately in each cohort. Check every
coefficient digest and ADC error flag. Checkpoint every accepted capture;
stop and log on the first failure. Do not discard failed seeds to balance a
convenient subset. Complete cohorts are required, and retries are reported.

The default search uses widths 128/256/512/1024 at 128-sample steps inside the
localized capture. Four stratified folds use independent seed rows. Within
each training fold, select up to 16 samples by absolute Welch score with
four-sample spacing, standardize, and fit logistic regression with C=0.1.
No test waveform participates. Stable ties prefer narrower, earlier windows.
No dynamic or label-dependent alignment is used.

Choose a window by development CV only. Its winning score is optimistic after
search and is not an unbiased performance estimate. Refit on development data
and freeze numeric POIs/scales/coefficients and threshold 0.5. Record code,
plan, data, firmware and condition fingerprints. Freeze a timing-only model
and a shuffled-training-label model too. Only then collect final-test traces;
each record includes the frozen artifact hash. This is an accidental-leakage
safeguard, not cryptographic proof of honest experiment chronology.

## Final evaluation

Primary: fixed-threshold single-trace balanced accuracy. The interval is a
stratified bootstrap over independent test seeds (2000 draws). A one-sided
fixed-prediction label permutation test uses 5000 permutations with the plus-
one correction. A positive descriptive decision requires the BA interval's
lower bound above 0.5 and p<0.05. This is one predeclared endpoint; secondary
AUC/control/averaging results do not independently trigger that decision.

Report AUC, both class recalls, confusion matrix, raw accuracy and the 0.5
balanced majority baseline. The timing baseline is standardized, regularized linear logistic regression;
it is a benchmark, not an optimal timing attack. Report it and the shuffled-label results
beside power. The bootstrap AUC difference against timing resamples the same
seeds for both models. An interval spanning zero does not demonstrate better
ranking than timing. These intervals condition on the trained model; they do
not quantify variability across retraining, other devices or new builds.

The shuffled-label control is diagnostic: random training-label fluctuations
can occasionally produce a useful direction, especially with strong low-
dimensional signals. It is not a universal proof that all leakage is absent.
Inspect acquisition drift/retries and replicate successful results with fresh
seeds. One physical run cannot establish deployment generalization.

Freeze/evaluate code never consumes synthetic records. Test-fixture metadata
can of course be fabricated; software provenance fields alone cannot prove
that a physical measurement occurred. Explicit programming/capture records
and retained raw data make the procedure reviewable. The 21-byte device
identity checks variant, revision and calibration profile, not a readback of
the complete firmware hash.

After seeing final-test results, any model/window change requires a new plan
and fresh final seeds. An inconclusive or negative result stays in the record.
