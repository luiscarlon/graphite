# 00_inputs — gtn_kyla

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Monthly reporting workbook; `Kyla` tab is authoritative for allocation |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**No flow-schema PDF exists for GTN kyla** — the cooling distribution on this campus is not captured on an AutoCAD flödesschema. Topology has to come from the Excel formulas plus BMS naming only (`docs_to_bric_parsing.md` §2). Expect a smaller set of parent→child edges than ånga/värme and more orphans fed by an off-page chiller plant (Prod-600 / B600-KB2).

**Timeseries:** same Snowflake export as gtn_anga / gtn_varme (`reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`), filtered to cooling-specific quantities.
