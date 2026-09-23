# NAKABANDI Evaluation Sweep Results (B9)

> These results were produced by `scripts/sweep/run_sweep.py` (DOC 4 Step B9).
> The compose stack (world-sim oracle) must be running to produce real metrics.
> Cells without data are marked **STUB** and must be re-run once the stack is
> available. Failures are listed, never hidden.
>
> Do NOT cherry-pick cells. Do NOT report a single accuracy number.
> Baselines are shown side-by-side. Abstention rates are reported when n < 30.


## Default Sweep (3 timing × 3 mix × 2 locality)

| sweep_key | n | status | abstention_rate | note |
|---|---|---|---|---|
| `tm=15.0|mix=atm_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=15.0|mix=atm_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=15.0|mix=mixed|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=15.0|mix=mixed|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=15.0|mix=upi_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=15.0|mix=upi_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=atm_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=atm_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=mixed|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=mixed|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=upi_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=60.0|mix=upi_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=atm_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=atm_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=mixed|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=mixed|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=upi_heavy|loc=local` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `tm=240.0|mix=upi_heavy|loc=dispersed` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |

## Feedback On / Off

| sweep_key | n | status | abstention_rate | note |
|---|---|---|---|---|
| `feedback=on` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |
| `feedback=off` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |

## Cold-Start Curve (7-day worlds)

| sweep_key | n | status | abstention_rate | note |
|---|---|---|---|---|
| `cold_start_7day` | 0 | ok | — | STUB — oracle not reachable; swap when compose stack runs |

## Baseline Comparison

> Baselines: **HotspotBaseline** (frequency), **NearestToVictim**, **BankFootprint**.
> Baseline metrics are computed inside each cell's ExperimentResult when oracle is reachable.
> With stub results (oracle not reachable), baseline comparison is deferred.

## Failures and Refusals

No failures. (Stubs are not failures; they are deferred runs.)

## n < 30 Notice
Cells with n < 30 observations report NaN for precision@k, hit_rate@k, and brier_score.
These are shown as `—` in the table above. Do not interpret NaN as zero or as a good result.