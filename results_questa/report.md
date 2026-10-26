# Verification and blind analysis report

Simulator: questa. All 283 RTL simulations passed the operation and failure-tuple scoreboard.
Random regression: 60 independent seeds, each with 1-3 faults, both modes.
Healthy memory: 2560 accepted operations, zero failures, pass=1 in both modes.
Model-only unit tests: 51 checks passed (see fault_model_units.log).
Assertion status: enabled in Questa.
Functional bins: 12/12 element x mode; 32/32 row/array boundary addresses.

## Blind holdout

Top-choice exact type accuracy: **38/55 = 69.09%**.
Candidate-set inclusion: **55/55 = 100.00%** (not exact-type accuracy).
Balanced, independent single-fault holdout; 5 samples/type by default. Classifier input contains fail CSVs only. Mixed-fault regression is a controller correctness test, not a classification benchmark.
DRF no-failure observations remain in the denominator. No-fail does not prove no fault.
Rules were fixed before inspecting holdout labels; no model training or truth-driven label lookup. Results are for this behavioral model, not silicon performance.

![Confusion](figures/blind_confusion.png)

## Every misclassified case

| Seed | Injected | Predicted | Reason |
|---|---|---|---|
| 100003 | TF_UP | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100005 | CFIN | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100007 | CFST | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100011 | DRF | NONE | No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF. |
| 100014 | TF_UP | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100018 | CFST | SAF1 | All read-0 elements fail, including the first read after initialization. |
| 100022 | DRF | NONE | No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF. |
| 100025 | TF_UP | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100027 | CFIN | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100029 | CFST | SAF1 | All read-0 elements fail, including the first read after initialization. |
| 100033 | DRF | NONE | No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF. |
| 100036 | TF_UP | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100040 | CFST | CFID | Partial-element single-cell signature suggests coupling; fail CSV alone cannot resolve subtype or aggressor. |
| 100044 | DRF | NONE | No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF. |
| 100047 | TF_UP | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100051 | CFST | SAF0 | Read-1 failures at both backgrounds. SAF0 and TF_UP are observationally identical after w0 initialization; coupling can alias them. |
| 100055 | DRF | NONE | No observed failures: healthy memory or unsensitized/masked fault, including long-threshold DRF. |

## Single-fault detection cross table

Counts are observed fail events, not theoretical coverage percentages. Zero M0 is expected because it only writes. DRF baseline zeros are intentional; see retention_pause.

| Fault | M0 | M1 | M2 | M3 | M4 | M5 |
|---|---:|---:|---:|---:|---:|---:|
| SAF0 | 0 | 0 | 6 | 0 | 6 | 0 |
| SAF1 | 0 | 6 | 0 | 6 | 0 | 6 |
| TF_UP | 0 | 0 | 6 | 0 | 6 | 0 |
| TF_DOWN | 0 | 0 | 0 | 6 | 0 | 6 |
| CFIN | 0 | 9 | 17 | 0 | 17 | 9 |
| CFID | 0 | 2 | 4 | 4 | 5 | 2 |
| CFST | 0 | 6 | 9 | 6 | 9 | 6 |
| AF | 0 | 6 | 6 | 6 | 6 | 0 |
| ROW | 0 | 80 | 16 | 80 | 16 | 80 |
| COL | 0 | 80 | 16 | 80 | 16 | 80 |
| DRF | 0 | 0 | 0 | 0 | 0 | 0 |

## Coupling ordering observed in simulation

| Injection / ordering | Detected elements |
|---|---|
| CFID aggressor < victim; force=0, trigger=0 | M2 |
| CFID aggressor < victim; force=0, trigger=1 | M4 |
| CFID aggressor < victim; force=1, trigger=0 | M5 |
| CFID aggressor < victim; force=1, trigger=1 | M1 |
| CFID aggressor > victim; force=0, trigger=0 | M4 |
| CFID aggressor > victim; force=0, trigger=1 | M2 |
| CFID aggressor > victim; force=1, trigger=0 | M3 |
| CFID aggressor > victim; force=1, trigger=1 | M3 |
| CFIN aggressor < victim; force=0, trigger=0 | M1, M2, M4, M5 |
| CFIN aggressor < victim; force=0, trigger=1 | M1, M2, M4, M5 |
| CFIN aggressor < victim; force=1, trigger=0 | M1, M2, M4, M5 |
| CFIN aggressor < victim; force=1, trigger=1 | M1, M2, M4, M5 |
| CFIN aggressor > victim; force=0, trigger=0 | M2, M4 |
| CFIN aggressor > victim; force=0, trigger=1 | M2, M4 |
| CFIN aggressor > victim; force=1, trigger=0 | M2, M4 |
| CFIN aggressor > victim; force=1, trigger=1 | M2, M4 |
| CFST aggressor < victim; force=0, trigger=0 | M2, M4 |
| CFST aggressor < victim; force=0, trigger=1 | M2, M4 |
| CFST aggressor < victim; force=1, trigger=0 | M1, M3, M5 |
| CFST aggressor < victim; force=1, trigger=1 | M1, M5 |
| CFST aggressor > victim; force=0, trigger=0 | M2, M4 |
| CFST aggressor > victim; force=0, trigger=1 | M2, M4 |
| CFST aggressor > victim; force=1, trigger=0 | M1, M3, M5 |
| CFST aggressor > victim; force=1, trigger=1 | M3 |

## Interpretation and follow-up

- SAF0 and TF_UP share M2/M4 under a w0-first March C- sequence; failure CSV alone cannot distinguish them.
- CFin after-victim can share that same signature. CFid and CFst can mimic stuck-at or transition faults depending on trigger/forced value.
- AF remaps one victim to one aggressor; not all real decoder open/multiple-select faults are modeled.
- For ambiguous cases, run a targeted aggressor-toggle test, independent address-isolation test, changed initialization, or pause-time sweep.
- DRF threshold=10000 cycles is longer than base test duration; a 12000-cycle pause after M0 sensitizes it.
- Native SVA and covergroups were executed in Questa; merged UCDB and detailed assertion/bin counts are in native_coverage.txt. No gate-level synthesis or timing analysis was performed.

## Example bitmaps

![Row](figures/ROW_diag.png)

![Column](figures/COL_diag.png)

![Coupling](figures/CFIN_diag.png)

![Retention](figures/retention_pause.png)
