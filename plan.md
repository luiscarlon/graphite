# Context

- Today we report media consumption monthly using Excel files per site:
  - meter data is exported from EMS,
  - data is aggregated per building via hardcoded formulas that reflect *how meters are wired* only implicitly,
  - observed data is compared, in some cases, to provider bills and own telemetry at intake — this is manual.
- Problems with this setup:
  - Building calculations are not topological — they are accounting shortcuts. They do not explain wiring, they are hard to validate, and they make reporting at any level other than building (or groups of buildings) impossible. This limitation has pushed teams to invent fake buildings to stand in for missing levels.
  - Maintenance is extremely intensive and error-prone. Every new or removed sub-meter requires editing every upstream building formula.
  - Data is not standardised and not compatible with 3rd-party vendors.
  - The Excels have been built poorly and maintained organically with no consistency. Logic is scattered and the workbooks are no longer manageable.

# Solution

- Adopt strict Brick Schema concepts, implemented as flat tables. See `ontology_proposal.md`.
- Using the ontology we compute meter *nets* topologically and then aggregate by building, zone, system, or any other concept.
- External / supplier meter timeseries (TN, manual readings) are modelled as additional `ref:hasExternalReference` entries on the AZ intake meter's sensor — per §7.10 of the ontology proposal — with exactly one marked `ref:preferred true`.
- Single surface for everything human-facing: a **Streamlit app** in this repo, covering:
  - browsing and visualising the ontology (scoped DAG views, tables with parent/child navigation),
  - site and media selection for multi-site, multi-media browsing,
  - topology-aware calculations producing per-meter nets and aggregations,
  - views that replace the Excel per-site per-media reports.

## Runtime: local first, Snowflake later

- **Phase A — local, pure Python.** Just CSVs, Python, Streamlit, DuckDB, pytest. Calculation logic lives in SQL against DuckDB over the CSVs so it ports later with minimal rewrite.
- **Phase B — Snowflake (deferred).** Once the table shape, calc SQL, and Streamlit workflows are settled against local data, promote the SQL to dbt on Snowflake.

## Architecture

```
packages/
  ontology/     — Pydantic schema, CSV I/O, Dataset with filter_by_media()
  validation/   — Structural validators (cycles, coefficients, referential integrity)
  calc/         — DuckDB SQL views (measured_flow → meter_flow → meter_net → consumption)
  refsite/      — Abbey Road reference site generator (deterministic synthetic data)
  app/          — Streamlit UI (site/media selector, topology, readings, tables, consumption)

data/sites/
  abbey_road/   — Reference site: 23 meters, EL only, synthetic readings
  gartuna/      — Real site: steam+heating+cooling+electricity, real BMS readings

reference/
  media_workstreams/  — Per-media parsing pipeline (6-stage: inputs → ontology)
  scripts/            — Pipeline scripts (parse, build, validate, assemble)
  snowflake_meter_readings/  — Raw BMS data dump
```

## Data flow

```
reference/media_workstreams/{site}_{media}/
  00_inputs → 01_extracted → 02_crosswalk → 03_reconciliation → 04_validation → 05_ontology

reference/scripts/build_ontology.py   — produces per-media 05_ontology CSVs
reference/scripts/assemble_site.py    — merges workstreams → data/sites/{site}/
packages/app/                         — reads data/sites/{site}/, filters by media in UI
```

## Relation type classification

Pipeline edges are classified based on provenance and coefficient:

| derived_from | coefficient | relation_type | flow_coefficient |
|---|---|---|---|
| `building_virtual_*` | any | `feeds` | as-is (aggregator) |
| any | not in {1.0, 0.001} | `feeds` | as-is (allocation share) |
| anything else | 1.0 or 0.001 | `hasSubMeter` | NULL (physical topology) |

The 0.001 case (EL kWh↔MWh) is a unit conversion artifact — handled at sensor/unit level.

# Sequencing

### 0. Reference site ✓

Abbey Road: 23 meters, 10 buildings, 22 relations, 21k synthetic hourly readings.
Exercises: virtual meters, device replacement, temporal validity, share splits, aggregators.

### 1. Repo scaffold ✓

Python workspace (uv), 5 packages, pytest (36 tests), ruff, mypy.

### 2. Build out against reference site ✓

Ontology tables, Graphviz topology, Altair readings charts, DuckDB consumption SQL, validation module.

### 3. Multi-site app + real site data ✓ (in progress)

**Done:**
- Fixed `build_ontology.py` relation_type classification (was all `feeds`, now correctly splits `hasSubMeter` vs `feeds`)
- Regenerated 05_ontology for all 4 Gärtuna workstreams (anga, varme, kyla, el)
- Added `derived_from` field to `MeterRelation` schema
- Created `assemble_site.py` to merge workstreams into single site Dataset
- Assembled Gärtuna with ANGA (36 meters, 49 relations, 8904 daily readings from Snowflake)
- Restructured data: `data/sites/abbey_road/` + `data/sites/gartuna/`
- Generalized calc SQL (removed hourly-only filter, renamed delta_kwh)
- Rewrote app: site selector, media filter, no Abbey Road hardcoding
- All 36 tests pass

**Next:**
- Assemble remaining Gärtuna workstreams (varme, kyla, el) into the site
- Validate consumption numbers against known Excel baselines
- Add Sankey/flow diagrams for stakeholder views
- Per-building deep-dive pages
- Scoped DAG view (single building ± 1 hop)

### 4. Enrich topology and metadata

- Equipment layer (heat pumps, chillers, heat exchangers)
- System / subsystem (`ext:System`)
- Zones for shared buildings (B339: API + Engineering)
- Device metadata (serial, manufacturer)

### 5. Load SNV — absorb the hard cases

SNV is structurally harder. The ontology and pipeline may need adjustments.

### 6. Promote to Snowflake (Phase B)

Migrate DuckDB SQL to dbt on Snowflake, point Streamlit at Snowflake.
