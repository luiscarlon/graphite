# Curated anomalies — gtn_varme

Human review layered on top of the auto-generated flags. `accounting_anomalies.md` is deliberately permissive; this file narrows to issues worth an operator's attention.

## Confirmed real findings

### System-wide reset on 2025-01-08/09

43 of 53 active värme meters logged a large negative daily delta on one of these two days. This is almost certainly a BMS/data-platform event (firmware roll, data migration, or annual counter reset) rather than physical meter replacements. The slicer clamps the negative deltas; monthly totals from Feb 2025 onwards are usable.

- **Evidence:** `01_extracted/timeseries_anomalies.csv` — search for `reset_days`.
- **Action:** flag the root cause to the BMS team before relying on pre-2025-01-09 data for anything.

### `B612.VP2_VMM61` only 35 days of data

Reported `flat_all_window` because it was only present in Snowflake for a short window. Either the meter came online late, went offline early, or changed identifier mid-year. Building 612's formula uses it additively (col S), so 612's totals for most of the year exclude whatever this meter measures.

- **Evidence:** `01_extracted/timeseries_anomalies.csv` line for `B612.VP2_VMM61_E`; `03_reconciliation/facit_accounting.csv` row 12 col S.
- **Action:** confirm commissioning/decommissioning date with operations; update the crosswalk if the ID changed.

### 8 drawing-only meters never emit

`B613.VP1_VMM62`, `B616.VS1_VMM61`, `B621.VÅ9_VMM41`, `B631.VP1_VMM61`, `B661.VS1_VMM61`, `B674.VÅ9_VMM41`, `B674.VÅ9_VMM42`, `B821.VS1_VMM61`. Present on the flow schema drawing but no Snowflake data and not in any Excel formula. Either never installed, decommissioned, or on a different data path.

- **Evidence:** `02_crosswalk/meter_id_map.csv` — rows with `in_excel=no` and empty `snowflake_id`.
- **Action:** site ops verifies physical presence; update the drawing or remove from facit based on their answer.

### 7 Excel-only meters absent from the drawing

`B612.VP2_VMM64`, `B612.VP2_VMM65`, `B613.VP2_VMM61`, `B616.VP1_VMM61`, `B631.VP1_VMM62`, `B661.VP1_VMM61`, `B821.VP1_VMM61`. Emit live data, used in Excel formulas, but not on the 2025-02-26 flow schema. Candidate reason: commissioned after the drawing date, or drawing-drafting omission.

- **Action:** when a refreshed flow-schema PDF arrives, re-parse and check whether these show up.

## Likely false positives (noise to ignore)

### Every building is "seasonal" (stdev/mean up to ~75%)

That's heating. Don't chase these.

### B654 flagged `erratic` (stdev/mean 123%)

Looking at the monthly sums: May–June at exactly 0.0 MWh, Dec at 369 MWh. It's a one-meter building (`+B654.VP2_VMM61` only) whose consumer apparently shuts off in summer. High stdev/mean is mathematically true but physically normal for a seasonal consumer. **Not an issue.**

### Two January 2026 months show unusually low values

Only 2 days of Jan 2026 are in the export (2026-01-01..02) — the low January numbers are just a partial-month artifact. Don't read anything into it.
