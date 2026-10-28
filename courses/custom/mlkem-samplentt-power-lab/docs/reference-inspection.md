# Reference inspection

Inspected 2026-10-28. Repository: [ProjectTempo](https://github.com/afonsoarriaga/ProjectTempo),
commit `fd72834bd789c644b52fe0d62b2fa3b9f34dfaec` (2026-08-19).
The selected upstream files are copied without edits into `reference/tempo`.
`reference/manifest.json` records their original paths and SHA-256 hashes.
They are sufficient for the sampler-only host build, without downloading
OpenSSL or pqm4. The complete upstream project remains available at the link.

| Purpose | Actual source at pinned commit | Signature / use |
|---|---|---|
| Variable-time sampler | `src/algorithm_a0.c` | `void algorithmA0(int16_t a[KYBER_N], const uint8_t extseed[KYBER_SYMBYTES + 2])` |
| FLS sampler | `src/algorithm_a1.c` | `void algorithmA1(int16_t a[KYBER_N], const uint8_t extseed[KYBER_SYMBYTES + 2])` |
| Declarations | `include/algorithms.h` | Both declared with output `[KYBER_N]`, input `[34]` |
| Constants | `include/config.h` | `KYBER_N=256`, `KYBER_Q=3329`, `MAX_ITER=280` |
| SHAKE128 | `src/fips202.c`, `include/fips202.h` | `shake128_inc_init/absorb/finalize/squeeze/ctx_release` |
| Matrix integration | `src/noic/indcpa.c` | `gen_matrix(polyvec *a, const uint8_t seed[KYBER_SYMBYTES], int transposed)` selects sampler through `SAMPLENTT` |
| Cortex-M4 sampler copies | `src/pqm4/crypto_kem/noic-a0-mlkem512/ref/samplentt.c`, corresponding `noic-a1-mlkem512/ref/samplentt.c` | Same `algorithmA0` / `algorithmA1` names; **A1 implementation differs** |
| Host benchmarks | `Makefile`, `main.py`, `main_count_cycles_x86.py`, `main_count_cycles_mac_m1.py` | Full project includes PAKE/ML-KEM benchmarks |
| Cortex-M4 benchmarks | upstream README, `results/pqm4_Nucleo_L4R5ZI.md`, `pqm4_compute_avg_and_std_dev.py` | pqm4, Nucleo-L4R5ZI, `PLATFORM=nucleo-l4r5zi` |
| External dependencies | `.gitmodules` | `external/openssl` and `external/pqm4` |

## Differences that change the experiment

The top-level A0 has `while (j < KYBER_N && iter < MAX_ITER)`. It stops after
at most 280 three-byte pairs. It does not report failure if too few candidates
were accepted. This is a bounded implementation of the usual SampleNTT process;
the Python model exposes the shortfall and acquisition refuses that seed.
Both algorithms match the standard's accepted-prefix output when the cap fills
the polynomial. Synthetic all-rejected tests exercise the exceptional case.

Top-level A1 executes 280 outer iterations and two 256-word scans per iteration.
It writes a candidate into the current slot even when that candidate is invalid,
and increments its counter by the validity bit. Invalid tentative values are
overwritten by later candidates. Its counter continues increasing after 256;
the scans then find no matching slot. Every scan still executes stores to all
256 addresses, even when the stored value is unchanged.

The pqm4 A1 copy instead forms `mask = match * acceptable_d1` (and similarly
for d2) and uses arithmetic updates and `flag` accumulation. These uint16
masks have specific wrapping behavior. Its counter saturates at 256. It has
a different intermediate-value and power profile. Do not pool observations
from these implementations under one undifferentiated "FLS" label.

The notebook and adapters deliberately select **top-level A0/A1** for a
comparable, pinned baseline. The pqm4 copies are retained for inspection only.
Changing to the pqm4 variant needs its own build identity, intermediate labels,
and functional/assembly checks.

`valid` is the candidate comparison result. `committed` means a valid candidate
enters the accepted output prefix. `tentative_update` identifies the top-level
A1 scan whose matching slot receives the candidate, including rejected values.
It is not an assertion that bits physically change, nor a list of all stores.
After the output is full, comparisons continue in A1, while no new coefficient
is committed. A0 decodes both candidates in its final pair, even if d1 fills
the output. Candidate count, pair count, XOF byte count, and SHAKE rate-block
count are recorded separately.

Input is **rho || x || y**. For the untransposed matrix entry A[row,column],
use x=column and y=row. The sampler itself simply receives two literal bytes.

## Builds and compatibility

The standalone A0/A1 files use only their three headers and `fips202.c`.
OpenSSL is required for upstream B0/C0 and the full upstream make dependency
graph, but is not required for this reduced reference build. The upstream
SHAKE context allocates 208 bytes with malloc and releases it with free.
This lab preserves that code, so the triggered interval includes SHAKE,
allocation, sampling, and release. It does not isolate rejection operations.

Upstream documents an ARM Cortex-M4 build through pqm4 and Nucleo-L4R5ZI.
That is not proof of compatibility with every ChipWhisperer target. Our adapter
cross-compiles with the local ChipWhisperer STM32F3 HAL; actual operation, clock
configuration, memory use and sampling windows must be checked on the selected
board. Source-level fixed loops do not certify constant-time machine code.

No official standalone SampleNTT KAT set was identified in the inspected
standalone sampler sources or README. `tests/vectors.json` contains our
C-generated regression vectors, clearly labeled as such. We additionally
compare 48 deterministic seed/index pairs per variant against unchanged C.

Sources: [FIPS 203, Algorithm 7](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf),
[pinned A0](https://github.com/afonsoarriaga/ProjectTempo/blob/fd72834bd789c644b52fe0d62b2fa3b9f34dfaec/src/algorithm_a0.c),
[pinned A1](https://github.com/afonsoarriaga/ProjectTempo/blob/fd72834bd789c644b52fe0d62b2fa3b9f34dfaec/src/algorithm_a1.c),
[pinned pqm4 A1](https://github.com/afonsoarriaga/ProjectTempo/blob/fd72834bd789c644b52fe0d62b2fa3b9f34dfaec/src/pqm4/crypto_kem/noic-a1-mlkem512/ref/samplentt.c).
