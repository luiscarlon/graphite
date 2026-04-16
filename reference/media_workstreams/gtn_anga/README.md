# gtn_anga — GTN Gärtuna, ånga (steam), B600 system

**Status:** template workstream, reconciliation complete, ontology deferred until a second workstream confirms the shape.

## What this workstream covers

Steam (ånga) distribution on the AstraZeneca Gärtuna site, building complex B600. One 29-BAR site plant (B325, external to this schema) feeds two 12-BAR site-entry meters (`B600S.Å1_VMM71` south main, `B600N.Å1_VMM71` north spine), which in turn supply 19 downstream metered tap-offs at individual buildings. Total: 21 physical meters, 19 parent→child relations.

## Sources used

| source | location | role |
|---|---|---|
| flow schema PDF | `00_inputs/flow_schema.pdf` → `reference/flow_charts/V600-52.E.8-001.pdf` | topology facit |
| overview drawing | `00_inputs/overview.pdf` → `reference/flow_charts/V600-52.E.1-001.pdf` | meter-list cross-check |
| monthly reporting xlsx | `00_inputs/excel_source.xlsx` → `reference/monthly_reporting_documents/inputs/gtn.xlsx` | accounting formulas, intake catalog |
| BMS timeseries | `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` | live readings 2025-01-01..2026-01-02 |

All four sources converge on the same 21 physical meters after the crosswalk normalises the three distinct naming conventions (`VMM` vs `VM`, `±_E`).

## Confidence by stage

| stage | confidence | notes |
|---|---|---|
| `01_extracted` | **high** — deterministic extraction, no interpretation | 21 meters, 19 relations, 19 Excel accounting rows, 21 snowflake timeseries with 367 days each |
| `02_crosswalk` | **high** — 21/21 meters resolved | one naming drift case (`B616.Å1_VMM71` has different STRUX and snowflake IDs); documented in `crosswalk_notes.md` |
| `03_reconciliation` | **high** — flow schema adopted as topology facit | 5 decisions in `decisions.md`; 5 open questions (see below) |
| `04_validation` | **medium** — conservation check runs clean but surfaces several unresolved anomalies | 2 stable-loss parents confirmed, 1 dead-children case, 3 swap / commissioning events detected |
| `05_ontology` | **done** — Abbey Road-shaped CSVs plus `meter_allocations.csv` extension | 21 meters, 19 `feeds` edges, 23 allocation rows, 21 timeseries refs |

## Top residual risks

1. **B612.VMM71 → B613.VMM71 / B641.VMM71 — dead children every month.** Both downstream meters report zero delta for all 367 days. Topology is correct per the flow schema; most likely interpretation is that the physical meters are broken, not that the buildings are idle. Operations follow-up required.
2. **B600N has a 60–80% residual across 9 months, even ignoring the B616 swap.** The north spine attributes far less consumption to its 4 registered children than the parent measures. Candidate cause: an unmetered seasonal consumer (cooling-related summer steam?). Not resolvable from the documents alone — needs site knowledge.
3. **Two meter swaps detected in 2025 but not documented anywhere** — `B642.VMM72` on 2025-07-31 and `B616.VMM71_E` on 2025-11-05. For accounting purposes 2025 is actually two different topologies; the ontology should carry installation windows, not single always-valid meters.
4. **B611.VMM72 and B642.VMM71 exist in BMS but not in Excel.** Both are correctly captured by the flow-schema parse. Both have live timeseries. Neither is referenced by any accounting formula — their consumption is only indirectly attributed. If either drifts or fails, the accounting wouldn't flag it.
5. **One comment in the Excel** (`01_extracted/excel_comments.md`) records an ongoing tenant-meter issue on B833/B834 that this workstream doesn't resolve: "Nu 100 % 833. Kan inte ha minus… 834 har redan mätare. 834s mätare är troligen en faktor 10 för hög."

## How to re-run

```sh
# 1. Flow schema → meters + relations + preview
.venv/bin/python reference/scripts/parse_flow_schema.py \
  reference/flow_charts/V600-52.E.8-001.pdf \
  --sources B600S.Å1_VMM71,B600N.Å1_VMM71 \
  --out-dir reference/media_workstreams/gtn_anga/01_extracted \
  --prefix flow_schema \
  --preview reference/media_workstreams/gtn_anga/01_extracted/flow_schema_preview.html

# 2. Excel → per-building accounting formulas
.venv/bin/python reference/scripts/parse_reporting_xlsx.py \
  reference/monthly_reporting_documents/inputs/gtn.xlsx \
  --media Ånga \
  --out-dir reference/media_workstreams/gtn_anga/01_extracted

# 3. (rebuild crosswalk inline — see 02_crosswalk/crosswalk_notes.md)

# 4. Timeseries slice
.venv/bin/python reference/scripts/slice_timeseries.py \
  "reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv" \
  --meters-csv reference/media_workstreams/gtn_anga/02_crosswalk/meter_id_map.csv \
  --quantity 'Active Energy Delivered(Mega)' \
  --out-dir reference/media_workstreams/gtn_anga/01_extracted

# 5. Copy flow-schema facit into 03_reconciliation
cp reference/media_workstreams/gtn_anga/01_extracted/flow_schema_meters.csv \
   reference/media_workstreams/gtn_anga/03_reconciliation/facit_meters.csv
cp reference/media_workstreams/gtn_anga/01_extracted/flow_schema_relations.csv \
   reference/media_workstreams/gtn_anga/03_reconciliation/facit_relations.csv

# 6. Conservation check
.venv/bin/python reference/scripts/validate_conservation.py \
  --facit-relations reference/media_workstreams/gtn_anga/03_reconciliation/facit_relations.csv \
  --timeseries-monthly reference/media_workstreams/gtn_anga/01_extracted/timeseries_monthly.csv \
  --crosswalk reference/media_workstreams/gtn_anga/02_crosswalk/meter_id_map.csv \
  --out-dir reference/media_workstreams/gtn_anga/04_validation

# 7. Ontology build (Abbey Road-shaped CSVs)
.venv/bin/python reference/scripts/build_ontology.py \
  reference/media_workstreams/gtn_anga \
  --campus GTN --media ANGA --database ion_sweden_bms --emit-shared
```

## Where to look next

- **Decisions taken:** `03_reconciliation/decisions.md`
- **Still unresolved:** `03_reconciliation/open_questions.md`
- **Flow-schema preview to eyeball against the PDF:** `01_extracted/flow_schema_preview.html`
- **Per-meter data quality:** `01_extracted/timeseries_anomalies.csv`
- **Curated relationship findings:** `04_validation/anomalies_curated.md`
- **Methodology + thresholds:** `04_validation/methodology.md`
- **Project-wide plan:** `docs_to_bric_parsing.md` in the repo root
