# 00_inputs — gtn_kallvatten

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Monthly reporting workbook; `Kallvatten` tab is authoritative for accounting |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |
| `flow_schema.pdf` | `reference/flow_charts/V600-52.B.8-001.pdf` | Kallvatten/stadsvatten distribution schema |
| `overview.pdf` | `reference/flow_charts/V600-52.B.1-001.pdf` | Site-map overview with meter labels |

**Timeseries:** same Snowflake export as the other media (`reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`), filtered to `QUANTITY = Water Volume (m^3)`. Units are m³, not MWh.
