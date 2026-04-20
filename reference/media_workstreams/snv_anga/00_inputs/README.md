# 00_inputs — snv_anga

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `flow_schema.pdf` | `reference/flow_charts/V390-52.E.8-001.pdf` | Flödesschema — authoritative for topology (distributionsnät Ånga, SNV) |
| `overview.pdf` | `reference/flow_charts/V390-52.E.1-001.pdf` | Översiktsritning — meter inventory cross-check |
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/snv.xlsx` | Site-specific monthly reporting; formulas, intake meters (sheet "Ånga") |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**Document dates:** flow schemas are `FÖRVALTNINGSHANDLING` dated 2025-02-26 (Creanova for AstraZeneca Södertälje Snäckviken, system ÅNGA, area B3xx).

**Timeseries source:** `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` — daily-aggregated readings, date range 2025-01-01 → 2026-02-28. Not symlinked; subset used via `slice_timeseries.py`.

**Snowflake query used for the export:** same as `gtn_anga/00_inputs/README.md`.

**Known SNV Ånga quirks to watch for:**
- Boiler-side / plant-side meters (e.g. `B325.Panna2/3_MWH`) sit *upstream* of the flow-schema entry point — will not appear in the PDF parser output; add them explicitly in reconciliation.
- Apply the SNV crosswalk conventions (§7): `-1` summary suffix, `_1_1` underscore trunk, dash↔underscore separator drift.
