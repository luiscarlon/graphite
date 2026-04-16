# Open questions — gtn_varme

---

### 8 drawing-only meters — do they exist physically?

These meter labels are on `V600-56.8-001.pdf` but have zero Snowflake readings and no Excel formula reference:

- `B613.VP1_VMM62`
- `B616.VS1_VMM61`
- `B621.VÅ9_VMM41`
- `B631.VP1_VMM61`
- `B661.VS1_VMM61`
- `B674.VÅ9_VMM41`
- `B674.VÅ9_VMM42`
- `B821.VS1_VMM61`

Either they were never installed, were decommissioned before 2025-01-01, or are on a non-standard data path. Operations needs to confirm.

---

### 7 Excel-only meters — missing from the flow schema

These appear in Excel Värme formulas and emit in Snowflake, but are not drawn on `V600-56.8-001.pdf`:

- `B612.VP2_VMM64`
- `B612.VP2_VMM65`
- `B613.VP2_VMM61`
- `B616.VP1_VMM61`
- `B631.VP1_VMM62`
- `B661.VP1_VMM61`
- `B821.VP1_VMM61`

Candidate causes: (a) commissioned after the 2025-02-26 flow-schema draft; (b) drafting omission. If a newer PDF is available, re-parse and update facit. If not, document that the drawing is out of date.

---

### What caused the 2025-01-08/09 system-wide reset?

43 of 53 active värme meters logged a large negative daily delta on either 2025-01-08 or 2025-01-09. This looks like a BMS baseline/configuration event, not individual meter swaps. Possibilities:

- firmware update on the data-acquisition side
- year-start accumulator rollover/reset
- data migration that re-baselined counters

Asking the BMS team would:
- clarify the date/cause
- tell us whether pre-2025-01-08 data from this export is usable at all
- clarify whether the same event affected other media (ånga didn't show this pattern — only 2 resets all year — so it may be värme-specific)

---

### B612.VP2_VMM61 only has 35 days of data

`01_extracted/timeseries_anomalies.csv` flags `B612.VP2_VMM61` as `flat_all_window` with only 35 days. Either it came online late, or went offline early, or its data source changed. Worth cross-checking the Snowflake export against a wider window to see if the meter appears under a different ID.

---

### VÅ9 double-accounting between Värme and VÅ9 sheets

The Excel has a separate `VÅ9 alla mätare` tab. Some VÅ9 meters appear in *both* Värme and VÅ9 tabs. We need to decide whether gtn_varme covers VÅ9 meters (as the flow schema suggests — they're on the V600-56 drawing) or whether VÅ9 is its own workstream. For now, VÅ9 meters are in the gtn_varme facit because the flow schema places them there.

---

### Non-uniform formula patterns across the Värme sheet

Unlike ånga (uniform 5-term formula), Värme rows have 4-, 5-, 7-, and 8-term formulas with variable sign patterns. The extractor now parses each formula's signs from the formula text. No data quality issue found, but the ontology layer needs to represent variable-length allocation rules cleanly. Worth eyeballing a few edge-case formulas (e.g., `B612` with 8 terms, `B821 (T)` with 4 terms) against operations/accounting intent.
