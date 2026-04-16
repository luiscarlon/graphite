# 00_inputs — gtn_varme

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `flow_schema.pdf` | `reference/flow_charts/V600-56.8-001.pdf` | Flödesschema — meter inventory (but no meter→meter edges for värme) |
| `overview.pdf` | `reference/flow_charts/V600-56.1-001.pdf` | Översiktsritning — cross-check |
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Monthly reporting workbook; `Värme` tab is authoritative for allocation |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**Document dates:** flow schemas are `FÖRVALTNINGSHANDLING` dated 2025-02-26 (Creanova for AstraZeneca Södertälje Gärtuna, system VÄRME, area B600).

**Timeseries:** same Snowflake export as gtn_anga (`reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`), filtered to `QUANTITY = 'Active Energy Delivered(Mega)'` and the 53 meter IDs in the crosswalk.

See `../../gtn_anga/00_inputs/README.md` for the Snowflake query used for the export.
