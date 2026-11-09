# SampleNTT lab companion

Start with the [project overview and notebook list](../README.md). The notebooks run the experiment; this folder holds their shared code and saved recordings.

| Folder | Purpose |
|---|---|
| `capture/` | Connect, program, verify and record the target; save progress after each capture. |
| `analysis/` | Calculate correct answers, fit the scoring rule, and evaluate fresh inputs. |
| `firmware/` | Build ordinary and calibration images for A0 and FLS. |
| `reference/` | Hash-checked copies of the authors' sampler code. |
| `results/runs/` | Raw recordings, plans, frozen models and reports; Git-ignored. |
| `tests/` | Software checks, including fake-device workflow checks. |
| `checkpoints/` | The earlier measured A0 backup, including its archived raw data. |
| `docs/` | Detailed methods, hardware notes and project history. |

From this folder, run `python -m pytest -q` to check the software. Fake-device tests verify the workflow; the measured notebook runs provide the physical evidence.

The short A0 window is tied to its exact firmware image. If the image check fails, use the [full method](../Full%20SampleNTT%20Method.ipynb) to recalibrate. Preserve existing results and use a fresh test set after changing a model.

Original lab code is GPL-3.0-or-later; vendored files retain their licenses. [More detail](docs/README.md).
