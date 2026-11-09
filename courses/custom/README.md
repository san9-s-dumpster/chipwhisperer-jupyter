# SampleNTT power-analysis lab

**Can a power recording reveal whether SampleNTT keeps or rejects a number?**

SampleNTT builds a list of 256 numbers. It keeps candidates below 3329 and rejects the others. We measure the STM32F4 while it runs, then predict the **first candidate's decision** from one power recording.

## How the classifier works

1. Record known inputs and calculate their correct accept/reject answers independently.
2. Learn a small scoring rule from up to 16 points in each power trace. Each point contributes toward accept or reject.
3. Freeze the points, weights and decision threshold.
4. Capture different inputs and compare predictions with their correct answers.

The classifier receives power samples. Input seeds and output checks are used to verify the experiment, not as prediction features. Training teaches the rule; the fresh test measures whether it works.

## Choose a notebook

Use **Husky + CW308_STM32F4**. Select `chipwhisperer-new/.venv`, disconnect other device-owning notebooks, and run from the top.

| Notebook | Use it for |
|---|---|
| [Short SampleNTT lab](Lab%207_1%20-%20ML-KEM%20SampleNTT%20Power%20Lab.ipynb) | Start here: ordinary A0 sampler, using the previously validated capture window. |
| [FLS lab](Lab%207_2%20-%20ML-KEM%20FLS%20Power%20Lab.ipynb) | Test the fixed-loop A1 sampler, with its own calibration and timing comparison. |
| [Full SampleNTT method](Full%20SampleNTT%20Method.ipynb) | Optional: inspect the full calibration/window-selection procedure or recalibrate a changed A0 build. |

## What we measured

| Recorded run | Correct predictions from one trace per new input |
|---|---:|
| Short A0 | 255/256 — 99.61% |
| Later full A0 | 252/256 — 98.44% |
| FLS | 250/256 — 97.66% |

FLS had identical recorded total duration for all 512 training/test captures, while power still revealed the decision. This supports power leakage in the tested fixed-loop implementation. These are separate runs, not a ranking of the algorithms. They concern the first decision on balanced, selected inputs; they do not demonstrate key recovery or universal timing resistance.

Default runs use 256 training inputs and 256 different test inputs. Failed captures are logged; completed captures can be resumed. Keep gain, clock, firmware and window fixed once training starts. After viewing a final test, model changes require a new test set.

[Detailed notes, reproducibility and troubleshooting](mlkem-samplentt-power-lab/docs/README.md) are available when needed. Raw captures and frozen models live in the companion's Git-ignored `results/runs/`; transfer them separately when moving computers.
