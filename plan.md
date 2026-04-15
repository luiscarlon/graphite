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
- State of the investigation so far (see `reference/monthly_reporting_documents/logs/`):
  - Formula-level extraction of meters and parent→child relations has been completed for all 6 GTN tabs and all 6 SNV tabs.
  - GTN is clean: every tab graph-validates 100% against Excel cached values for Feb (EL 38/38, Kyla 17/17, Värme 28/28, Ånga 11/11, Kallvatten 37/37, Kyltornsvatten 3/3).
  - SNV has real structural problems that the Excel hides but the graph exposes: per-building subtraction subsets (B310/B311 on T26S, B310/B313/B317 on T49), BPS_V2-style computed meters, shared meters without coefficient splits, and at least three confirmed source-data errors (B317 parenthesis, B318 sign, B392 reassignment).
  - The Excel is not a source of truth — it is a decent starting point for topology, but some of what it encodes is wrong.

# Solution

- Adopt strict Brick Schema concepts, implemented as flat tables. See `ontology_proposal.md`.
- Using the ontology we compute meter *nets* topologically and then aggregate by building, zone, system, or any other concept. Prototyped in `/Users/luis/dev/flexometer` (Brick TTL + DuckDB + CSV inputs).
- External / supplier meter timeseries (TN, manual readings) are modelled as additional `ref:hasExternalReference` entries on the AZ intake meter's sensor — per §7.10 of the ontology proposal — with exactly one marked `ref:preferred true`. Standalone sensors only where there is no AZ intake to attach to (e.g. external tenants like Kringlan and Scania).
- Single surface for everything human-facing: a **Streamlit app** in this repo, covering:
  - browsing and visualising the ontology (scoped DAG views, flow/Sankey, tables with parent/child navigation),
  - managing the ontology (new meters, sensors, buildings, relations, validity),
  - uploading / editing manual time series.
- Components on top of ontology tables + timeseries data:
  - Time series normalisation (unit alignment, counter → period delta, aggregation alignment, gap marking). Trivial DE task; called out so it isn't forgotten.
  - Topology-aware calculations producing per-meter nets and aggregations to building, zone, system, campus.
  - Views that replace the Excel per-site per-media reports and enable cuts Excel cannot produce today (per-zone, per-system).
  - An ontology validation module (see below) that runs on every write and as unit tests.

## Runtime: local first, Snowflake later

- **Phase A — local, pure Python.** Just CSVs, Python, Streamlit, DuckDB, pytest. No Snowflake, no dbt. Calculation logic lives in SQL against DuckDB over the CSVs so it ports later with minimal rewrite. Everything runs in this repo, everything is diff-able.
- **Phase B — Snowflake (deferred).** Once the table shape, calc SQL, and Streamlit workflows are settled against local data, promote the SQL to dbt on Snowflake and point the Streamlit app at Snowflake (or Streamlit-in-Snowflake). Monthly reporting already lives in Snowflake + PBI so that is the production target. Phase A choices are made with this transition in mind — SQL not pandas, ontology tables the same shape local and remote.

## Visualisation strategy

Full-campus topology renders are never readable regardless of renderer — it is an information-density problem, not a layout problem. Every view answers one question for one entity at a scoped depth.

- **Scoped DAG view (Graphviz `dot`)** — primary topology tool. Native Streamlit (`st.graphviz_chart`), DAG-native layout, text input, scales to several hundred nodes when clustered by building/zone. Default scope: one building ± 1 hop, expand on click. Network-viz (force-directed) is explicitly rejected — meter topology is directional, force layout produces hairballs.
- **Walks** — upward (meter → intake) and downward (meter → leaves). Small by construction. Graphviz or mermaid, whichever reads better per walk.
- **Flow / Sankey (Plotly)** — intake → consumers with actual volumes. Best format for stakeholder questions like "where does our steam go this month". Native Streamlit.
- **Tables with parent/child click-through** — the detail page for a meter. Handles most curation work better than any graph. Underrated.
- **Indented tree in the sidebar** — Campus → Building → Zone → Meter. Navigation, not understanding.
- **Mermaid** — kept for documentation only (markdown files, plan.md, ontology proposal). Not used in the app.

## Ontology validation as a first-class module

The management interface will corrupt the model if every write isn't validated. Validation rules live in their own module, are called on every save in the app, and are also the basis of unit tests. Minimum rule set (all derivable from the ontology proposal):

- coefficient splits sum to 1.0 per shared meter
- exactly one `ref:preferred true` per sensor
- no cycles in `hasSubMeter` / `feeds`
- validity intervals on the same relation don't overlap
- orphan detection (meter with no building, no campus)
- media type consistent along a meter chain

This replaces what SHACL would do in the TTL world, without requiring TTL in Phase A.

# How to get to the solution

- Approach validated in `dev/flexometer` (Brick TTL + DuckDB over flat CSVs). Ontology captured in `ontology_proposal.md`.
- Topology extracted from the monthly reporting Excels into 12 `{site}_{media}_meters.csv` + `{site}_{media}_relations.csv` pairs under `reference/monthly_reporting_documents/outputs/`. Parsing notes, validation results, and known gaps in `reference/monthly_reporting_documents/logs/`.
- Note on `reference/ebo_xml_exports/outputs/`: remnants of an earlier attempt over polluted data — do not treat as a starting point. The raw EBO XMLs may still hold useful device/zone metadata worth pulling later.

## Sequencing

### 0. Fabricated reference site

Build a small, self-contained fake site that exhibits every structural pattern we know the real model has to handle. Everything downstream — calc engine, visualisations, management interface, unit tests — is developed and tested against this site first. It is the spec artifact for the model and the regression surface for the pipeline.

**Constraints**

- ~20–40 meters, 4–8 buildings, 2–3 zones. Small enough to hold mentally, diff by eye, render in full.
- Unmistakable naming (campus `CTEST`, buildings `BT01`…) so it cannot be confused with production data.
- Deterministic timeseries generator (e.g. sinusoid + step + seeded noise) kept as a script; the site's CSVs are regenerated, never hand-edited. Ground truth for every aggregation is computable from first principles, not from an Excel cached value.

**Pattern coverage (one instance of each, sourced from real GTN/SNV weirdness)**

- simple parent→child chain
- coefficient split, matching coefficients (child lives on real parent)
- coefficient split, non-matching (child lives on virtual share)
- computed / pooled meter at site level (BPS_V2 / B600-KB2 pattern)
- shared meter, no coefficient split (the B314/B315 case)
- zone-aggregation building with residual net
- multi-zone building (B339-style)
- mutual subtraction / cycle (B310↔B311 VS2)
- rename with `validTo` / `validFrom`
- bad-data period nulled via validity
- external supplier ref on an intake sensor (TN-style)
- manual monthly reading (Avläsning-style)
- campus-level intake meter (no building)
- external tenant standalone (Kringlan/Scania-style)

If the fake site fails on any of these, the model isn't done.

**Complement: one small real-data slice.** One GTN building and its sub-tree (e.g. B612 in Kyla — coefficient splits matching and non-matching, small) is kept alongside the fake site, as a sanity check that we haven't over-fit to synthetic regularities.

### 1. Repo scaffold

Stand up the skeleton once the reference site exists:

- Python project layout (`pyproject` / `requirements.txt`), `pytest`, `make run` or equivalent.
- Ontology tables as CSVs in the repo (reference site seeded from the generator, real-data slice seeded from `reference/monthly_reporting_documents/outputs/`).
- Calculation layer: SQL views in DuckDB reading the CSVs.
- Ontology validation module (see Solution §).
- Streamlit app entry point with the page skeleton (topology browse, meter detail, manual timeseries upload).
- README pointing at `ontology_proposal.md` and this plan.

### 2. Build out against the reference site

Order of implementation, each step validated end-to-end on the reference site before moving on:

1. **Ontology tables** — schema, seed data from the generator, validation module passing.
2. **Visualisations** — scoped Graphviz DAG, meter detail pages with parent/child tables, indented tree sidebar. Sankey deferred until there's timeseries data to flow.
3. **Calculations** — SQL views for meter nets and aggregations to building, zone, system, campus. Unit tests assert exact per-building totals against the generator's ground truth.
4. **Management interface** — CRUD for meters, sensors, buildings, relations, validity intervals. Every write goes through the validation module.
5. **Manual timeseries upload** — CSV upload, attached as `ref:hasExternalReference` on the chosen sensor, preferred flag handling.

### 3. Load GTN (one media at a time)

Pick one GTN media (recommend EL or Kallvatten — both graph-validate 100%, simple topology, all-real meters, no virtual meters). Load into the ontology tables, load the local timeseries dump, run the calc views, compare against Excel cached values for Feb 2026 (baselines already established in `parsing_validation.md`).

**Success criterion**: monthly per-building consumption matches the existing Snowflake/PBI report within a small tolerance.

Then add the remaining media one at a time: Kyla, Värme, Ånga, Kyltornsvatten. Kyla brings the first real modelling question — `B600-KB2` is a computed meter whose components live in other buildings. If the reference site's computed-meter pattern already handles it, good; if not, the model adapts. Not worth speculating before hands-on.

### 4. Enrich GTN topology and metadata

Once GTN runs end-to-end, fill in what the Excel cannot give us:

- Equipment layer (heat pumps, chillers, heat exchangers) linking meters to physical equipment.
- System / subsystem (`ext:System`) for reporting axes beyond media.
- Real device metadata (serial, manufacturer) as it becomes available — replacing the meter-as-device placeholder.
- Validity intervals for the seven known real renames (B616.Å1_VM71 → B616.Å1_VMM71_E, and six others in `parsing_notes.md`) as the rename-workflow test cases.
- Zones for shared buildings (B339: API + Engineering).

### 5. Load SNV — absorb the hard cases

SNV is structurally harder. The ontology and pipeline may need adjustments; treat SNV as the real stress test. Items to resolve in situ, not up front:

- **BPS_V2 / computed-meter pattern** (Sjövatten; by analogy GTN Kyla `B600-KB2`). Decide representation once.
- **Per-building subtraction subsets** (SNV EL: T26S split across B310/B311, T49 across B310/B313/B317). The current graph computes one parent net from all children; the Excel uses per-receiver subsets. Options range from richer relations (per-receiver child list) to fixing the underlying topology. Decide based on what the meters actually mean physically.
- **Shared meters without coefficient splits** (B318.T21-6-2-A in 318+344, B315.KV1_VM21_V in 314+315, etc.). Either a coefficient exists in reality and we recover it, or the Excel is double-counting and we correct it.
- **Source-data errors** (B317 parenthesis, B318 sign, B392 reassignment). Confirm with stakeholders whether the new pipeline should reproduce the (wrong) Excel or fix.
- **Ånga / Kallvatten naming-ambiguous subtrees** — individual parent assignments are uncertain, building-level totals still balance. Fine for v1; revisit when EBO or drawings data can anchor.

Every new pattern surfaced in SNV is reduced to its smallest form and added as a fixture to the reference site. Over time the reference site becomes the accumulated structural history of the model.

### 6. Promote to Snowflake (Phase B)

Once SNV also validates: migrate DuckDB SQL to dbt on Snowflake, point Streamlit at Snowflake, move manual timeseries upload to a Snowflake stage. The Brick schema is runtime-agnostic; only the connection layer swaps.

### Why this order

- The fake site gives a deterministic ground truth, fast iteration, and complete LLM-friendly context. Everything downstream is built and regression-tested against it.
- GTN extracted topology graph-validates cleanly on every media — if the pipeline breaks on GTN, it's a pipeline problem, not a data problem.
- SNV last, because it is the model's real stress test and the point of *surfacing* modelling questions, not speculating about them.
- Snowflake last, because it buys nothing in the design phase and slows iteration.

## Known open items tracked for later

- **Manual / TN reconciliation**: monthly upload of TN reports, Avläsning, and Vista Produktion timeseries. Owned by energy engineers. Trivial operationally — CSV into a stage, attach as additional `ref:hasExternalReference`.
- **Streamlit app scope**: v1 only needs enough surface to drive the reference site and GTN vertical slice. Full curation UX is iterated on, not specified up front.
- **Bad-data discipline**: policy for marking periods invalid via `validTo` / `validFrom` on timeseries refs vs. relying on `brick:Fault_Status`. Per §7.11 of the ontology proposal, nulling over patching. Operationalise when we hit the first real case.
- **Weather and solar**: two weather stations (B390.MS01_GT41, B600.MS01_GT41) and SOLPARK meters are standard Brick, negligible cost to include. Add when useful for normalisation (degree-day) or reporting.
- **Large-subgraph visualisations**: Graphviz clustered by building/zone handles several hundred nodes, but the full campus will never render usefully. If and when a wider view is needed, reconsider; probably not before Phase B.
