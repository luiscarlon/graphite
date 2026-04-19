# 00_inputs — gtn_kyltornsvatten

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Monthly reporting workbook; `Kyltornsvatten` tab is authoritative for accounting |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**No flow-schema PDF** exists for GTN kyltornsvatten (cooling-tower water). Topology is derived from Excel formulas + BMS naming only.

**Timeseries:** Snowflake with `QUANTITY = Water Volume (m^3)`, m³. Only 7 building rows in the Kyltornsvatten tab, each with a single meter in most cases.
