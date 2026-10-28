# Evaluation of the completed VT SampleNTT lab

The main result is credible for this conditioned, warm-target experiment. The frozen classifier correctly predicts the first candidate's accept/reject label for all 256 previously unseen test seeds, using one physical trace per seed. This is substantially stronger than the previous early-window experiment. Reporting and control interpretation still need correction before presenting the lab as a finished experimental methodology.

| Frozen model, single trace | Balanced accuracy | ROC AUC | Meaning |
|---|---:|---:|---|
| Power | 100.0% | 1.000 | 128/128 rejects and 128/128 accepts correct |
| Total-duration linear baseline | 58.2% | 0.601 | Weak but measurable residual timing association |
| Shuffled-training-label diagnostic | 19.1% | 0.186 | Strong inverse prediction; not a clean negative control |

## What was verified

- 256 development and 256 different final-test seeds; no overlap. Each has two captures, giving 1,024 distinct waveform arrays. The primary test denominator remains 256 independent seeds.
- Every record passes independently regenerated Python SHAKE ground truth and polynomial-digest checks. Both classes have 160 pairs, 320 visited candidates, exactly 256 valid candidates, a valid second candidate, and output completion on the final candidate.
- Frozen model/source/plan hashes and both dataset fingerprints match. Recreating the power and shuffled fits from development data reproduces their saved coefficients exactly (maximum difference 0).
- Development ended at 18:17:10 EDT; the fit was frozen at 18:17:40 EDT; final capture began at 18:17:46 EDT, on October 28, 2026. The saved chronology supports separation of fitting from final capture.
- All model captures use the ordinary measurement profile, the same image hash, gain, clock and window. They are not calibration-profile records. Acquisition reported no failed attempts or retries.
- ADC samples are finite integer codes, range 1555–2529 across the cohorts, with no hits on 12-bit rails. Stored flags/provenance and the executed capture path are consistent with physical measurements, though metadata alone cannot independently authenticate a device recording.
- Both acquisition classes are interleaved. Label/order correlations are small (-0.064 development, -0.021 final test), with both classes present throughout the batches. There is no obvious class-block drift explanation.
- Re-evaluation of the second capture of each same final-test seed also gives 100%. This is a repeatability diagnostic, not another independent-seed experiment.

## Why perfect classification is plausible here

The frozen window spans samples 95,336–95,848 from the trigger, approximately 3.237–3.254 ms, or CPU cycles 23,834–23,962. It uses 16 fixed waveform sample points selected using development data only.

The independent calibration image measured 71 cycles between first squeeze return and second squeeze entry for accept/accept pairs. Its one observed reject/accept pair took 64 cycles. The seven-cycle difference matches the exploratory alignment of the two real final-test class means: shifting the accept mean earlier by 28 ADC samples (four samples per CPU cycle) changes their correlation from 0.339 to 0.964. That delay is approximately 0.95 microseconds.

This agreement supports a straightforward explanation: the early accepted path executes extra work, delaying subsequent activity. A classifier looking at a fixed time sees different instruction phases. Even when total sampling work is matched, local timing remains informative. This is a valid waveform distinguisher; it is not evidence of an amplitude-only channel independent of timing, or a proof that only one particular comparison instruction caused the signal. The calibration wrapper changes timing/layout, and there is only one reject/accept calibration observation.

## Correction 1: perfect bootstrap intervals

The notebook prints a balanced-accuracy interval of [1, 1]. Every resample contains only correct predictions, so this percentile bootstrap cannot express the uncertainty about unseen errors. It does not establish a guaranteed 100% future success rate.

For this audit, I computed exact Clopper–Pearson intervals for the two class recalls, using 97.5% coverage for each and Bonferroni combination. Averaging their endpoints gives a conservative joint 95% balanced-accuracy interval of **96.63%–100%**. For reference, an ordinary binomial interval for 256/256 raw successes is 98.57%–100%; that is a different interval construction and estimand. Neither reflects variation across hardware, compiler builds or new sessions.

The saved permutation p-value is approximately 0.0002, the smallest reported value with 5,000 random permutations and the plus-one correction. It is a strong association check for the fixed model, not a probability that the device experiment is genuine. SciPy documents the [exact binomial interval method](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html) and [degenerate bootstrap distributions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).

## Correction 2: shuffled-label control

The shuffled development labels accidentally agree with the true labels for 116/256 seeds (45.31%), giving correlation -0.09375. The fit really used those shuffled labels: independently refitting reproduces it exactly. Its development accuracy against true labels was 21.09%, close to 19.14% on the fresh test. The inverse relationship was therefore already present before test acquisition.

In a waveform region with a very strong class signal, an accidental training-label association can make such a model learn the opposite direction. Its bad accuracy is not absence of information: reversing the predictions would give 80.86%. This supports interpreting the shuffled fit as an imperfect diagnostic, rather than as a clean passed control. It does not by itself invalidate the correctly frozen primary model or the test-label permutation result. The report should not say all controls passed. A future experiment should define the null-control design more carefully; a single shuffled training-label fit is not a dependable chance baseline.

## Limits and next experiment

This demonstrates first-candidate validity association for balanced, workload-conditioned public seeds on this one setup and build. It does not estimate precision under ordinary random-seed priors, identify an unknown seed, recover a secret key, or generalize to arbitrary candidate positions.

The calibration first call started 203 CPU cycles later than subsequent calls, consistent with a cold-versus-warm setup effect. All model data followed a representative check capture, so the result primarily describes a warmed target. Power cycling/resetting, then testing a predeclared first-call/warmed-call protocol, remains necessary for cross-session claims.

The next useful step is a fresh-session replication with the current model/ROI frozen and new seeds from the same declared population, plus corrected uncertainty/control reporting. Any subsequent model tuning requires another new final test. Do not tune against the now-examined holdout.

The original notebook, frozen fit and saved results were not modified for this audit. This report and its figures are derived evaluation artifacts only.
