# 00_inputs — gtn_anga

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `flow_schema.pdf` | `reference/flow_charts/V600-52.E.8-001.pdf` | Flödesschema — authoritative for topology |
| `overview.pdf` | `reference/flow_charts/V600-52.E.1-001.pdf` | Översiktsritning — meter inventory cross-check |
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/gtn.xlsx` | Site-specific monthly reporting; formulas, intake meters |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**Document dates:** flow schemas are `FÖRVALTNINGSHANDLING` dated 2025-02-26 (Creanova for AstraZeneca Södertälje Gärtuna, system ÅNGA, area B600).

**Timeseries source:** `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` — daily-aggregated readings from `OPS_WRK.ION_SWEDEN.DATALOG2`, date range 2025-01-01 to 2026-01-02. Not symlinked here because only a subset matters for this workstream; `01_extracted/timeseries_monthly.csv` is derived from it via `slice_timeseries.py`.

**Snowflake query used for the export** (persisted for reproducibility):

```sql
SELECT
  source.name                        AS meter_id,
  q.name                             AS quantity,
  DATE_TRUNC('day', d.timestamputc)  AS day,
  MIN_BY(d.value, d.timestamputc)    AS v_first,
  MAX_BY(d.value, d.timestamputc)    AS v_last,
  MIN(d.value)                       AS v_min,
  MAX(d.value)                       AS v_max,
  AVG(d.value)                       AS v_avg,
  COUNT(*)                           AS n_readings
FROM ops_wrk.ion_sweden.datalog2 d
JOIN ops_wrk.ion_sweden.source   source ON d.sourceid   = source.id
JOIN ops_wrk.ion_sweden.quantity q      ON d.quantityid = q.id
WHERE d.hvr_is_deleted = 0
  AND d.timestamputc >= '2025-01-01'
  AND d.timestamputc <  '2026-01-01'
GROUP BY 1, 2, 3
ORDER BY meter_id, quantity, day
```
