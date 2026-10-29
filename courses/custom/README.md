# Custom ML-KEM SampleNTT labs

Use **Husky + CW308_STM32F4** and the **chipwhisperer-new/.venv** notebook kernel. Disconnect one notebook before connecting from another.

| Notebook | Purpose |
|---|---|
| [Short A0 lab](Lab%207_1%20-%20ML-KEM%20SampleNTT%20Power%20Lab.ipynb) | Reproduce the variable-time power distinguisher with a fixed validated window. |
| [Full A0 method](Full%20SampleNTT%20Method.ipynb) | Locate the first pair, develop a window and classifier, then test fresh seeds. Existing captured outputs are preserved. |
| [FLS power lab](Lab%207_2%20-%20ML-KEM%20FLS%20Power%20Lab.ipynb) | Test pinned top-level A1 with separate calibration and independent power/timing results. |

Shared code, firmware and saved measurements live in [mlkem-samplentt-power-lab](mlkem-samplentt-power-lab/README.md). New FLS results receive their own `results/runs/fls-...` folder. No physical FLS result is implied by installation or software tests.
