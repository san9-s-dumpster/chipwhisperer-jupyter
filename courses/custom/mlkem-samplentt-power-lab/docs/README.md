# Detailed reference

Start with the [short project overview](../../README.md). These files support deeper inspection and migration.

| Reference | Contents |
|---|---|
| [Technical notes](technical-notes.md) | Earlier notebook explanations and implementation details, preserved before simplifying the entry documentation. |
| [Long walkthrough](details/SampleNTT%20and%20FLS%20explanation.md) | The original approximately 30-minute explanation, preserved verbatim. Its figure link uses the original PC's absolute path. |
| [Project handoff](details/SampleNTT%20project%20handoff.md) | Original migration checklist, exact versions, historical commit IDs, raw-data locations and known issues. Paths and HEAD refer to when it was written. |
| [Hardware](hardware.md) | Wiring, serial protocol, capture settings and bus recovery. |
| [Sampler source inspection](reference-inspection.md) | Pinned A0/A1 behavior and differences from the upstream pqm4 copy. |
| [A0 analysis](distinguisher.md) | Full-method experiment design. |
| [FLS software validation](fls-validation.md) | Build checks, tests and interpretation limits. |
| [Short-lab validation](short-lab-validation.md) | Validation of the simplified A0 workflow. |
| [Measured checkpoint](../checkpoints/validated-2026-10-28/README.md) | First validated A0 recording archive and its evaluation. |
| [Full runnable method](../../Full%20SampleNTT%20Method.ipynb) | Calibration, window selection, frozen model and fresh test. |

Some historical notes predate the FLS lab and contain earlier platform/deferred-work wording. Current notebooks use Husky + CW308_STM32F4 and the pinned top-level A0/A1 sampler files.

The saved run reports and attempts logs are the detailed record for each experiment. Preserve them. Newer raw run folders are Git-ignored and must be transferred separately from a Git clone.
