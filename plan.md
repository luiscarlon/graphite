# Plan: End-to-end pipeline for multi-media ontology building and validation

## Context

We have a working pipeline that takes raw documentation (flow-schema PDFs, Excel monthly reports, BMS meter readings from Snowflake) and builds a Brick Schema ontology for a production site's utility metering. The pipeline was developed and validated against Gärtuna's steam (ånga) media, where we:

1. Extracted topology from PDF + Excel formulas + meter naming conventions + timeseries conservation
2. Reconciled conflicting sources using a layered authority model (PDF > Excel > naming > timeseries)
3. Built an ontology with correct `hasSubMeter`/`feeds` relation types
4. Detected and handled device swaps, meter outages, and data glitches via derived timeseries refs
5. Patched offline meters using children's readings (sum aggregation + rolling_sum stitching)
6. Validated against Excel's building-level monthly figures (Jan/Feb 2026)
7. Documented all findings as structured annotations in the ontology

The pipeline works but was developed organically with manual steps, ad-hoc fixes, and the execution order scattered across scripts and memory. We need to consolidate the helpers into a reusable framework that supports the analytical work for each media.

**Critical principle:** The pipeline is a **framework with helper scripts**, not an automated "run and done" tool. Every media has a different physical system, different data quality issues, and different topology challenges. The scripts produce INPUTS for reasoning (extracted layers, validation reports). The reconciliation, ontology, annotations, and decisions are the ANALYST output — each edge, annotation, and decision is curated individually with evidence. No bulk generation of annotations or decisions. No mechanical re-running of `build_ontology.py` on working workstreams.

## What exists today

### Scripts (`reference/scripts/`)

**Extractors (01_extracted/):**
- `parse_flow_schema.py` — PDF topology (layer 1, primary authority)
- `parse_reporting_xlsx.py` — Excel formula extraction (layer 2a)
- `excel_relations.py` — Excel formulas → candidate edges (layer 2b)
- `slice_timeseries.py` — Snowflake BMS → daily/monthly timeseries + `is_reset` flags
- `detect_meter_swaps.py` — classifies resets as swap/offline/glitch
- `parse_meter_names.py` — canonical IDs + role catalog
- `naming_relations.py` — role hierarchy + index chain edges (layer 3)
- `vlm_edge_check.py` — Claude vision crops for orphans (optional)

**Reconciliation (03_reconciliation/):**
- `apply_topology_overrides.py` — merges layers 1-4 with conflict detection + human overrides
- `generate_building_virtuals.py` — creates virtual building meters from Excel accounting (excluded from ontology)
- `timeseries_relations.py` — orphan residual fit (layer 4, depends on layers 1-3)

**Validation (04_validation/):**
- `source_conflicts.py` — cross-source agreement report
- `validate_conservation.py` — parent vs children energy balance
- `validate_accounting.py` — per-building formula evaluation
- `validate_building_totals.py` — end-to-end vs Excel totals
- `parse_audit.py` — parser regression test
- `render_audit_png.py` — visual PDF overlay

**Ontology (05_ontology/):**
- `build_ontology.py` — produces Abbey Road-schema CSVs from reconciliation output
- `generate_outage_patches.py` — adds children-sum patches for offline meters
- `assemble_site.py` — merges per-media ontologies into single site dataset + materializes readings

**Orchestrator:**
- `regenerate_workstream.py` — runs steps 1-16 for one workstream (extract → validate → ontology)

### App (`packages/app/`)

Streamlit app with: site/media selector, topology graph, readings chart, consumption (series/building/campus), annotations with selectable highlights, Excel comparison table, tests.

### Packages

- `ontology` — Pydantic schema (Dataset, Annotation, etc.), CSV I/O, `filter_by_media()`
- `validation` — structural validators (cycles, coefficients, referential integrity)
- `calc` — DuckDB SQL views (measured_flow → meter_flow → meter_net → consumption)
- `refsite` — Abbey Road reference site generator
- `app` — Streamlit UI

## The pipeline

### Overview

```
For each media in a site:
  Phase 1: Extract          (automated)
  Phase 2: Crosswalk        (manual, one-time per media)
  Phase 3: Reconcile        (automated + manual overrides)
  Phase 4: Validate         (automated)
  Phase 5: Build ontology   (automated)
  Phase 6: Detect & patch   (automated)

Then once per site:
  Phase 7: Assemble site    (automated, all media)
  Phase 8: App validation   (manual, iterative)
  Phase 9: Re-run           (repeat from phase 3 with updated overrides/annotations)
```

### Phase 1: Extract

All extractors run independently on raw inputs. No cross-talk between them.

| Step | Script | Input | Output | Notes |
|------|--------|-------|--------|-------|
| 1.1 | `parse_flow_schema.py` | `00_inputs/flow_schema.pdf` | `flow_schema_{meters,relations}.csv`, `preview.html` | Only for media with PDFs (ånga, värme, kallvatten). Skipped for kyla, el. |
| 1.2 | `parse_reporting_xlsx.py` | `00_inputs/excel_source.xlsx` | `excel_{formulas,intake_meters,meters_used}.csv`, `excel_comments.md` | All media have Excel tabs. |
| 1.3 | `excel_relations.py` | `excel_formulas.csv` | `excel_relations.csv` | Derives candidate edges from formula structure. |
| 1.4 | `slice_timeseries.py` | Snowflake CSV + `meter_id_map.csv` | `timeseries_{daily,monthly}.csv` | Needs crosswalk (phase 2). Can run after crosswalk is ready. |
| 1.5 | `detect_meter_swaps.py` | `timeseries_daily.csv` | `meter_swaps.csv` | Classifies counter resets. |
| 1.6 | `parse_meter_names.py` | `flow_schema_meters.csv`, `excel_*.csv` | `meter_roles.csv` | Canonical IDs. |
| 1.7 | `naming_relations.py` | `meter_roles.csv` | `naming_relations.csv` | Deterministic naming rules. |

**Dependency:** Steps 1.4-1.5 need the crosswalk from phase 2. Steps 1.1-1.3, 1.6-1.7 can run before the crosswalk exists.

### Phase 2: Crosswalk (manual)

Human creates `02_crosswalk/meter_id_map.csv` mapping facit_id ↔ snowflake_id ↔ excel_label.

For each meter found in any source (PDF, Excel, BMS), the crosswalk records the ID in each system. This is load-bearing — all downstream steps join through it.

**Scaffolding:** Generate a draft crosswalk from the union of all source meter IDs for the human to review and complete. Document ambiguous mappings in `crosswalk_notes.md`.

### Phase 3: Reconcile (automated + manual)

| Step | Script | What it does |
|------|--------|-------------|
| 3.1 | `apply_topology_overrides.py` | Merge layers 1-3 (PDF + Excel + naming) with conflict detection. Apply human `topology_overrides.csv`. Output: `facit_relations.csv`. |
| 3.2 | `timeseries_relations.py` | Layer 4: orphan residual fit against merged facit. |
| 3.3 | `apply_topology_overrides.py` | Re-merge with layer 4 additions. |
| 3.4 | `generate_building_virtuals.py` | Create virtual building meters from Excel accounting (optional). |

**Manual review after phase 3:**
- Read `04_validation/source_conflicts.md` (generated in phase 4, but conceptually informs reconciliation)
- Add `topology_overrides.csv` entries for direction conflicts, false edges, missing edges
- Document decisions in `decisions.md`

### Phase 4: Validate

| Step | Script | Output |
|------|--------|--------|
| 4.1 | `source_conflicts.py` | `source_conflicts.md` — all 5 sources compared |
| 4.2 | `validate_conservation.py` | `monthly_conservation.csv`, `anomalies.md` — parent vs children balance |
| 4.3 | `validate_accounting.py` | `accounting_anomalies.md` — per-building formula check |
| 4.4 | `render_audit_png.py` | `flow_schema_audit.png` — visual overlay (if PDF exists) |

### Phase 5: Build ontology

| Step | Script | What it does |
|------|--------|-------------|
| 5.1 | `build_ontology.py` | Produces `05_ontology/` CSVs. Excludes virtual building meters. Handles swap/offline/glitch events from `meter_swaps.csv` by generating multi-segment timeseries refs. |

### Phase 6: Detect & patch

| Step | Script | What it does |
|------|--------|-------------|
| 6.1 | `generate_outage_patches.py` | For offline meters with children: adds `{id}.patch` (sum of children) and stitches into the preferred derived ref. Auto-generates annotations for all detected events. |

**Auto-generated annotations from pipeline:**
- Each swap → annotation (category=swap, related_refs=A|B|derived)
- Each offline → annotation (category=outage, related_refs=patch if patched, empty if leaf)
- Each glitch → annotation (category=data_quality, related_refs=A|B)
- Conservation violations → annotation (category=unknown, description with residual %)

Output: `05_ontology/annotations.csv`

### Phase 7: Assemble site

| Step | Script | What it does |
|------|--------|-------------|
| 7.1 | `assemble_site.py` | Merges all media workstreams into `data/sites/{site}/`. Concatenates meters, relations, sensors, timeseries_refs, annotations. Deduplicates buildings, media_types. Generates shared tables (campuses, databases, zones, meter_measures, devices). Extracts readings from Snowflake dump. Materializes derived refs (sum for patches, rolling_sum for stitching). Copies meter_allocations for Excel comparison. |

### Phase 8: App validation (manual, iterative)

User opens the app, selects site + media, and validates:

1. **Topology** — does the graph make sense? Missing edges? Wrong directions?
2. **Readings** — any spikes, flat periods, missing data? Select annotations to see highlighted events.
3. **Consumption** — building and campus levels. Negative buildings = topology issue or data anomaly.
4. **Excel comparison** — ontology vs Excel for Jan/Feb. All buildings should match except intake (B600 pattern). Any diff > 1% needs investigation.
5. **Annotations** — review auto-generated annotations. Add manual ones for findings.

Findings from app validation feed back into:
- `topology_overrides.csv` (topology corrections)
- `annotations.csv` (data quality notes)
- `decisions.md` (documented reasoning)

### Phase 9: Re-run

Re-run from phase 3 (reconcile) with updated overrides and annotations. Phases 1-2 only need re-running if raw inputs change.

```bash
# Re-run for one media:
python regenerate_workstream.py reference/media_workstreams/gtn_anga

# Re-assemble site (all media):
python assemble_site.py --campus GTN --campus-name Gärtuna --database ion_sweden_bms \
  --workstreams reference/media_workstreams/gtn_anga reference/media_workstreams/gtn_varme ... \
  --snowflake-readings "reference/snowflake_meter_readings/..." \
  --output data/sites/gartuna
```

## Changes needed

### 1. Extend `regenerate_workstream.py` to include phases 5-6

Add these steps to the orchestrator after the existing validation steps:

- `detect_meter_swaps.py` (after `slice_timeseries.py`)
- `build_ontology.py` (phase 5)
- `generate_outage_patches.py` (phase 6)
- Auto-generate `annotations.csv` from pipeline events

Currently `detect_meter_swaps.py` runs standalone. Move it into the orchestrator between `slice_timeseries` and the first merge.

### 2. Auto-generate annotations from pipeline

`generate_outage_patches.py` (or a new `generate_annotations.py`) should produce `05_ontology/annotations.csv` with one row per detected event:

- Every swap, offline, glitch from `meter_swaps.csv`
- Every conservation violation > threshold from `validate_conservation.py`
- Every direction conflict from `source_conflicts.py`

The human adds to this file; the pipeline never overwrites human-authored annotations.

### 3. Extract Excel comparison months

`parse_reporting_xlsx.py` should extract the cached building-level values for Jan and Feb 2026 from the Excel file, not just the formulas. Store as `01_extracted/excel_building_totals.csv` with columns: `building_id, month, excel_kwh`.

The app's Excel comparison section reads this file instead of recomputing from formulas + raw readings.

### 4. Consolidate `assemble_site.py` to include annotations

Currently annotations live in `data/sites/gartuna/annotations.csv` (manually created). The assembly script should:
- Concatenate annotations from all workstreams' `05_ontology/annotations.csv`
- Append any existing manual annotations from `data/sites/{site}/annotations_manual.csv`
- Write the merged result to `data/sites/{site}/annotations.csv`

### 5. Clean up `docs_to_bric_parsing.md`

Update to reflect the consolidated pipeline:
- Add phase 6 (detect & patch) and phase 7 (assemble) to §8 script inventory
- Update §11.7 with the conflict rules we implemented (reverse-direction, duplicate-parent)
- Add §11.8 for device swap/offline/glitch handling (already partially there)
- Add §11.9 for outage patching (children-sum + rolling_sum stitching)
- Add §11.10 for annotation auto-generation
- Remove any references to manual steps that are now automated

### 6. Per-media configuration

Each media workstream needs a config block (already in `regenerate_workstream.py`). Extend to include:
- `excel_tab_name` — which Excel sheet to parse
- `quantity` — Snowflake QUANTITY filter ("Active Energy Delivered(Mega)", "Active Energy Delivered", etc.)
- `unit` — sensor unit ("Megawatt-Hour", "KiloW-HR", "M3")
- `has_pdf` — whether a flow schema PDF exists
- `primary_role` — for Excel relation extraction ("Å1", "VP1", "T", etc.)
- `pdf_sources` — declared source meters for PDF parsing

### 7. Scaffolding for new media

For each new media, the human needs to:
1. Place raw inputs in `00_inputs/` (PDF if exists, Excel source, Snowflake export)
2. Run phase 1 extractors
3. Create `02_crosswalk/meter_id_map.csv` (draft generated from extracted meter lists)
4. Run phases 3-7
5. Review in app, iterate

A `scaffold_workstream.py` script could create the directory structure and generate the draft crosswalk.

## Step 0: Extend Abbey Road with new patterns

Before running the pipeline on new media, lock down the patterns we developed for ånga in the reference site with deterministic test coverage.

### New Abbey Road fixtures needed

| Pattern | Real-world case | Abbey Road fixture |
|---------|----------------|-------------------|
| Outage + children-sum patch | B600S offline, patched from 9 children | Add a meter that goes offline mid-period. Patch ref with `aggregation=sum` from children. Stitched `rolling_sum` preferred ref. |
| Glitch (counter drop + revert) | B642 Mar 15-18 | Add a meter with a 2-day counter glitch. Validity split excludes bad days. Rolling_sum stitches A+B segments. |
| Frozen counter detection | B600S Jan 17 (flat before hard reset) | Add a meter that freezes (delta=0) for N days then resets. Detection should catch the freeze, not just the reset. |
| Annotations | 16 annotations across ånga | Add annotations of each category (outage, swap, data_quality, unknown, patch) to the reference dataset. |
| Multi-event meter | B642 (glitch + offline on same meter) | One meter with both a glitch and a later offline. Segments: A (before glitch), B (after glitch, before offline), patch (children-sum after offline). |
| Parallel intakes | B600N/B600S | Two root meters with no parent-child relationship (siblings, not series). |
| Conservation violation | B642 exceeds B614 | A child meter that sometimes reads more than its parent (undocumented additional feed). Annotation with category=unknown. |

### New tests

- `test_outage_patch`: meter with offline event → derived patch ref from children → stitched preferred ref → consumption correctly computed
- `test_glitch_exclusion`: glitch period excluded from readings → no spike in consumption
- `test_annotation_filter`: `Dataset.filter_by_media()` correctly filters annotations by target entity
- `test_rolling_sum_stitching`: multi-segment rolling_sum produces monotonic counter with correct deltas at segment boundaries
- `test_conservation_balance`: sum of building consumption = campus total (energy conservation holds)

### Implementation

Extend `refsite/abbey_road.py`:
- Add new meters, relations, and timeseries refs exercising each pattern
- Add synthetic readings with deterministic values (so expected consumption is computable from first principles)
- Add reference annotations

Extend `refsite/tests/test_smoke.py`:
- One test per pattern above
- Each asserts exact numeric results against the known ground truth

## Execution order for remaining Gärtuna media

### Värme (heating) — has PDF
1. Run `regenerate_workstream.py reference/media_workstreams/gtn_varme`
2. Review `source_conflicts.md`, add overrides
3. Re-run, validate in app
4. Assemble into site

### Kyla (cooling) — no PDF
1. Same pipeline but `parse_flow_schema.py` skipped
2. Topology comes from Excel + naming + timeseries layers only
3. Has fractional coefficients (0.38, 0.9) — genuine `feeds` allocation edges

### EL (electricity) — no PDF
1. Same as kyla
2. Has 0.001 coefficients (unit conversion kWh↔MWh) — treated as `hasSubMeter` with NULL coefficient
3. Unit = KiloW-HR (different from other media)

### Assembly
After all 4 media are done:
```bash
python assemble_site.py --campus GTN --campus-name Gärtuna --database ion_sweden_bms \
  --workstreams gtn_anga gtn_varme gtn_kyla gtn_el \
  --snowflake-readings "..." \
  --output data/sites/gartuna
```

App shows all media in one site, filterable by media selector.

## Verification

After implementation:
1. `regenerate_workstream.py gtn_anga` produces identical output to current state (regression test)
2. `regenerate_workstream.py gtn_varme` runs end-to-end, produces valid ontology
3. `assemble_site.py` with all 4 media produces a loadable site dataset
4. App renders all media correctly
5. Excel comparison shows 0 diff for downstream buildings across all media
6. Auto-generated annotations match the manual ones we created for ånga
7. `uv run pytest` — all tests pass
8. Pipeline is re-runnable: running it twice produces the same output
