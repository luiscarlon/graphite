# 00_inputs — gtn_el

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Monthly reporting; `EL` tab is authoritative for allocation |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**No flow-schema PDF exists for el** — confirmed via `HF Rörsystem` master index which enumerates only the six flödesscheman (3 media × 2 sites) and none of them is electricity. Topology has to come from Excel formulas + BMS naming only.

**Snowflake quantity:** `Active Energy Delivered` (kWh, scaled ×0.001 by the EL sheet's `$F$5` cell to report MWh).

**Meter naming:** EL uses `B###.T##` / `B###.T##-#-#` (T = transformator/ställverk-station/feeder). ~496 distinct EL meters in the Snowflake export for campus-wide; the Excel references a subset.
