# Validation methodology — gtn_varme

Värme can't use the parent-minus-children conservation check we use for ånga — the flow schema doesn't connect meters to each other (see `03_reconciliation/decisions.md`). Instead, validation runs two complementary passes:

## Per-meter data quality (`01_extracted/timeseries_anomalies.csv`)

Produced by `slice_timeseries.py`. Flags:
- `reset_days`: daily `v_last < v_first`. Clamped to 0, day flagged. **43 of 53 meters logged a reset on 2025-01-08/09** — this looks like a system-wide BMS event, not individual swaps.
- `flat_all_window`: zero delta every day in the export window.
- `mostly_zero`: >50% of days have Δ=0 but total isn't zero.
- `coverage_gap`: fewer days of data than expected.
- `no_readings`: present in facit but absent from Snowflake export (the 8 drawing-only meters).

## Per-building accounting sanity (`validate_accounting.py`)

Runs the per-building Excel formula `Σ ± meter_delta` against the live timeseries. Reports, per (building, month, formula-row): `sum`, `n_add`, `n_sub`, `any_data`. Then per-building stats and flags.

**Flag thresholds (tuned for heating seasonality):**
- `negative_month`: a month where the formula gives a negative net (sign error or subtractive meter reporting higher than additive).
- `erratic`: `stdev / mean > 120%`. Heating naturally varies 30–100% stdev/mean between winter peak and summer trough; `erratic` catches truly unusual variation.
- `near_zero`: mean monthly sum < 0.1 MWh.

**Why the 120% threshold:** our earlier 30% rule flagged 29/29 buildings. Heating demand in a Scandinavian site has stdev/mean easily 60–80% across 12 months of real data — the 30% bar was measuring seasonality, not data problems. 120% only triggers on buildings with genuinely erratic readings.

## What this validation does NOT do

- No site-level conservation: there is no single upstream värme meter on this schema. District heating enters at each building's substation independently.
- No cross-meter consistency check beyond naming. If two Excel formulas disagree about which meter covers a given flow, we don't currently catch it.
- No check against an "expected consumption" baseline (e.g., from a previous year). That would need an additional data source.

## Known gotchas

- The 2025-01-08/09 system reset eats the first ~8 days of readings. Don't trust sub-monthly residuals spanning that date.
- `B612.VP2_VMM61` has only 35 days of data — it was likely commissioned or decommissioned mid-year. Any building (612) using this meter will have a partial-year bias.
- Seasonal swing dominates the signal; don't read too much into per-month stdev on heating.
