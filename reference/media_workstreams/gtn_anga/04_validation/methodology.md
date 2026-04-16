# Conservation validation — methodology

How the numbers in `monthly_conservation.csv` and `anomalies.md` were produced, and the thresholds used.

## Delta computation

Readings are cumulative accumulators. Daily delta is `V_LAST − V_FIRST` using timestamps (Snowflake's pre-aggregated export already carries first/last per day). Monthly delta is the sum of daily deltas.

**Resets are segmented, not summed negative.** If `V_LAST < V_FIRST` for a day, the day's delta is clamped to 0 and the day is flagged as a reset day. This prevents a mid-year counter-rollover or meter replacement from silently corrupting the full-year total.

**Gaps are not interpolated.** Missing days simply shrink the window; we do not invent values.

**Zero deltas are preserved but flagged.** A meter reading exactly 0 for a full day is different from a missing day — it means the meter is reporting and says no flow. Those are counted in `zero_days` per month and surfaced in `timeseries_anomalies.csv` as `flat_all_window` (zero every day in the window) or `mostly_zero` (>50% of days flat).

## Residual computation

For each parent P with children C₁..Cₙ and each month:

```
delta_parent       = monthly[P][month]
sum_children       = Σ monthly[Cᵢ][month]
residual           = delta_parent − sum_children
residual_pct       = 100 · residual / delta_parent      (if delta_parent > 0.01)
```

Sign convention: positive residual = parent reads more than the sum of its children. In a well-posed steam network that's *expected* and corresponds to genuine losses.

Meter IDs are resolved parent→children and children→timeseries via `02_crosswalk/meter_id_map.csv`. The conservation runner does not do its own normalisation — it trusts the crosswalk.

## Classification thresholds

Per parent, the script looks at the sequence of `residual_pct` values across all months it has data for, and assigns one flag:

| flag | rule |
|---|---|
| `clean` | `abs(mean) < 5 && stdev < 5` |
| `losses_stable` | `stdev < 5 && 5 ≤ mean ≤ 50` |
| `dead_children` | every month's residual within ±5 of 100% |
| `swap_event` | `max adjacent-month jump > 20pp` (tested before `drift_seasonal`) |
| `drift_seasonal` | `stdev > 10` but no single big jump |
| `review` | didn't fit any of the above |
| `no_data` | parent had zero flow every month → pct undefined |

These thresholds are the first cut. Expect to retune after 2–3 workstreams have been through the pipeline — in particular the 5pp stability bound may be too tight for low-flow periods where noise dominates.

## Relationship to the per-meter anomalies

`01_extracted/timeseries_anomalies.csv` flags **individual meter behaviour** (flat, reset, coverage gap). `04_validation/anomalies.md` flags **relationship behaviour** (parent-vs-children). A parent's `swap_event` is typically caused by a specific child's reset day — you should be able to join the two files by meter ID.

Example from this workstream: `B614.Å1_VMM71`'s parent classification is `swap_event` because the daily series of its only child `B642.Å1_VMM72` shows a reset on 2025-07-31. The two findings are the same underlying event seen from different angles.

## Caveats

- **Only one downstream source is considered.** A parent with children "in the flow schema" may also have OTHER real consumers that aren't metered. Those turn into unexplained residual.
- **Coefficients are assumed 1.0.** If the actual accounting uses a non-unit coefficient (some virtual meter formulas), the current check will misattribute. A future iteration should read `coefficient` from `facit_relations.csv`.
- **No unit check.** Everything in this workstream is `Active Energy Delivered(Mega)` but a future workstream mixing quantities would need an explicit unit column. Add one when encountered.
- **Month boundaries are naive** — we use `YYYY-MM` from the day string. Leap-year / month-length effects are small relative to our tolerance.
