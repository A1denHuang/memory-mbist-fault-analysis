# Fresh-seed follow-up evaluation

| Method | Strict exact type | SAF0/TF_UP merged only |
|---|---:|---:|
| March C- CSV | 38/55 (69.09%) | 43/55 (78.18%) |
| March C- + auxiliary reads | 45/55 (81.82%) | 50/55 (90.91%) |

Only SAF0/TF_UP is merged. Coupling errors and no-failure DRF observations remain errors. Same samples and denominator for all four metrics.

## Per-type counts

| Truth | Samples | March-only correct | Assisted correct |
|---|---:|---:|---:|
| SAF0 | 5 | 5 | 5 |
| SAF1 | 5 | 5 | 5 |
| TF_UP | 5 | 0 | 0 |
| TF_DOWN | 5 | 5 | 5 |
| CFIN | 5 | 3 | 5 |
| CFID | 5 | 5 | 5 |
| CFST | 5 | 0 | 5 |
| AF | 5 | 5 | 5 |
| ROW | 5 | 5 | 5 |
| COL | 5 | 5 | 5 |
| DRF | 5 | 0 | 0 |

## Remaining errors

| Seed | Truth | Prediction |
|---|---|---|
| 200003 | TF_UP | SAF0 |
| 200011 | DRF | NONE |
| 200014 | TF_UP | SAF0 |
| 200022 | DRF | NONE |
| 200025 | TF_UP | SAF0 |
| 200033 | DRF | NONE |
| 200036 | TF_UP | SAF0 |
| 200044 | DRF | NONE |
| 200047 | TF_UP | SAF0 |
| 200055 | DRF | NONE |

## Method and limits

Only this report and metrics.json are tracked. Input/probe CSVs, fixtures, saved predictions and per-sample scoring are generated locally and available in the mbist-verification CI artifact (14-day retention).
The victim comes only from the failing address in the March CSV. All other 255 addresses are tried as aggressors. Four fresh trials per address cover both initial aggressor states and victim backgrounds. Settle, toggle, and victim-rewrite reads separate inversion, transition-triggered forcing, and state forcing.
No injection type, aggressor or force value is supplied to prediction. Fixture configuration is used only by the SRAM simulator. Predictions are saved before scoring loads labels.
Fresh array state between trials is simulator setup via initialize/load_config, not a hardware test primitive. Results apply to this single-fault behavioral model. A silicon implementation needs a justified reset/preconditioning procedure; no production test or independent validation of fault semantics is claimed.
3060 additional reads and 4080 writes per probed cell (255 addresses x 4 trials); this is a diagnostic follow-up, not an improvement in March C- itself.
