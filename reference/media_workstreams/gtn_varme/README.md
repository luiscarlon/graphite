# gtn_varme — GTN Gärtuna, värme (heating), B600 system

**Status:** workstream complete through `04_validation`. Ontology deferred to a common pass alongside gtn_anga.

## What this workstream covers

District-heating (`FVM`) deliveries and their per-building secondary circuits across the Gärtuna campus. Unlike steam, **there is no single site-wide distribution network**: each building has its own substation (FVM inlet → heat exchanger → VP / VS / VÅ9 circuits). That topology difference cascades through every stage.

## Facit scope

| | count | source |
|---|---:|---|
| meters in facit | **61** | flow schema ∪ Excel Värme ∪ Snowflake (union of all three) |
| meters with live Snowflake data | 53 | `01_extracted/timeseries_*` |
| meters on the flow schema | 57 (54 unique after dedup) | `01_extracted/flow_schema_meters.csv` |
| meters in Excel formulas | 46 | `01_extracted/excel_meters_used.csv` |
| physical meter→meter edges | **26** | same-axis-preferring parser + Excel S-column sources + VVX gap bridging (37 bridges); 22 explicit, 3 auto-root, 1 arrow-confirmed |
| per-building accounting rows | 29 | `03_reconciliation/facit_accounting.csv` |

## Confidence by stage

| stage | confidence | notes |
|---|---|---|
| `01_extracted` | **high** — deterministic extraction from three sources | 57 labels on schema (54 unique); 63 meter references across 46 unique meter IDs on the Excel Värme sheet; 53 timeseries match after crosswalk; 36 directional arrows extracted from the PDF |
| `02_crosswalk` | **high** — 53/61 meters resolved to Snowflake, 8 drawing-only flagged | normalisation: `VMM↔VM, ±_E` |
| `03_reconciliation` | **high** — 21 `feeds` edges derived from flow-schema components + arrow orientation | all edges `explicit` (rooted at Excel S-column meters), 6 of 21 arrow-confirmed. See `decisions.md` for the supersession note on the prior "0 edges" claim. |
| `04_validation` | **medium** — conservation now runs on 12 parents | per-meter anomalies found 43 meters caught in a system-wide reset on 2025-01-08/09 (not individual swaps); per-parent residuals mix `swap_event` (6), `review` (3), `dead_children` (1), `no_data` (2) |
| `05_ontology` | **done** — Abbey Road-shaped CSVs plus `meter_allocations.csv` extension (0 edges, 63 allocation rows, 53 timeseries refs) | meter_relations.csv is deliberately empty for värme; accounting is encoded in meter_allocations.csv |

## Key differences vs gtn_anga

1. **No physical topology.** `parse_flow_schema.py` found 0 meter→meter edges. Each building's substation is a standalone island.
2. **Excel formulas are variable-length (4, 5, 7, or 8 terms) and mixed-sign.** Ånga was uniformly `+S +T −U −V −W`; värme ranges from `+S −T −U −V` to `+S +T +U +V −W −X −Y −Z`. The extractor now parses signs from the formula text.
3. **61 meters vs 21.** Lots of small local meters (VP1/VP2/VS1/VS2/VÅ9/VÅ2 circuits per building).
4. **System-wide 2025-01-08/09 reset event** dwarfs the per-meter swap events we saw in ånga.

## Top residual risks

1. **The 2025-01-08/09 mass reset** — cause unknown. If it reflects a data-migration re-baseline, values before vs. after may mean different things. Open question for BMS team.
2. **8 drawing-only meters** (`B613.VP1_VMM62`, `B616.VS1_VMM61`, `B621.VÅ9_VMM41`, `B631.VP1_VMM61`, `B661.VS1_VMM61`, `B674.VÅ9_VMM41`, `B674.VÅ9_VMM42`, `B821.VS1_VMM61`) never emit — likely planned-but-not-installed or decommissioned.
3. **7 Excel-only meters not on the flow schema** — likely commissioned after the 2025-02-26 drawing date; a refreshed PDF would confirm.
4. **`B612.VP2_VMM61` only has 35 days of data** — came online or went offline mid-year. Building 612's totals are partial for most of the year.
5. **VÅ9 double-accounting risk** — some VÅ9 meters might appear both in the Värme tab and in the separate `VÅ9 alla mätare` tab. This workstream only processes the Värme tab; if the two tabs cover overlapping meters, a future VÅ9 workstream will need to dedupe.

## How to re-run

```sh
# 1. Flow schema → meter inventory (0 edges is expected)
.venv/bin/python reference/scripts/parse_flow_schema.py \
  reference/flow_charts/V600-56.8-001.pdf \
  --sources B921.VP1_VMM61 \
  --out-dir reference/media_workstreams/gtn_varme/01_extracted \
  --prefix flow_schema \
  --preview reference/media_workstreams/gtn_varme/01_extracted/flow_schema_preview.html

# 2. Excel → accounting formulas
.venv/bin/python reference/scripts/parse_reporting_xlsx.py \
  reference/monthly_reporting_documents/inputs/gtn.xlsx \
  --media Värme \
  --out-dir reference/media_workstreams/gtn_varme/01_extracted

# 3. crosswalk (rebuild inline, see 02_crosswalk/crosswalk_notes.md)

# 4. Timeseries slice
.venv/bin/python reference/scripts/slice_timeseries.py \
  "reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv" \
  --meters-csv reference/media_workstreams/gtn_varme/02_crosswalk/meter_id_map.csv \
  --quantity 'Active Energy Delivered(Mega)' \
  --out-dir reference/media_workstreams/gtn_varme/01_extracted

# 5. Accounting validator (topology-free)
.venv/bin/python reference/scripts/validate_accounting.py \
  --accounting reference/media_workstreams/gtn_varme/03_reconciliation/facit_accounting.csv \
  --timeseries reference/media_workstreams/gtn_varme/01_extracted/timeseries_monthly.csv \
  --crosswalk reference/media_workstreams/gtn_varme/02_crosswalk/meter_id_map.csv \
  --out-dir reference/media_workstreams/gtn_varme/04_validation

# 6. Ontology build
.venv/bin/python reference/scripts/build_ontology.py \
  reference/media_workstreams/gtn_varme \
  --campus GTN --media VARME --database ion_sweden_bms --emit-shared
```

## Where to look next

- **Decisions taken:** `03_reconciliation/decisions.md`
- **Still unresolved:** `03_reconciliation/open_questions.md`
- **Flow-schema meter positions to eyeball:** `01_extracted/flow_schema_preview.html`
- **Per-meter data quality:** `01_extracted/timeseries_anomalies.csv`
- **Per-building accounting sums:** `04_validation/monthly_building_accounting.csv`
- **Curated findings:** `04_validation/anomalies_curated.md`
- **Methodology + threshold reasoning:** `04_validation/methodology.md`
