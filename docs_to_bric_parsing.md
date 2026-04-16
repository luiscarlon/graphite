# Docs → Brick parsing — plan

Persistent plan for turning AstraZeneca's heterogeneous documentation (flow-schema PDFs, monthly-reporting Excel files, BMS timeseries) into a per-media Brick-style ontology dataset, one workstream per (site, media). Written so the work can be resumed cold from this document.

---

## 1. Goal

Produce a Brick-style ontology deliverable (equivalent to `data/reference_site/abbey_road/*`) for each (site, media) workstream, where:

- Topology (which meter feeds which) is reconstructed from the authoritative source for that aspect.
- Accounting formulas and intake/manual meters come from the Excel monthly-reporting files.
- Actual meter behaviour (which meters exist, emit, and how they move) is grounded in the Snowflake BMS export.
- **Every reconciliation decision and every flagged anomaly is recorded** — nothing is silently resolved.

## 2. Scope

Two sites × ~6 media each = **12 workstreams**. Not all sources are available for every workstream:

|  | ånga | värme | kyla | kallvatten | sjövatten | kyltornsvatten | el |
|---|---|---|---|---|---|---|---|
| **GTN** (Gärtuna, B6xx)  | ✓ all three | PDF+Excel+BMS | Excel+BMS | PDF+Excel+BMS | — | Excel+BMS | Excel+BMS (no PDF) |
| **SNV** (Snäckviken, B3xx) | ✓ all three | PDF+Excel+BMS | Excel+BMS | PDF+Excel+BMS | Excel+BMS | — | Excel+BMS (no PDF) |

Flow-chart PDFs available under `reference/flow_charts/`:

- `V600-52.E.{1,8}-001.pdf` — GTN ånga (done ✓)
- `V600-52.B.{1,8}-001.pdf` — GTN 52-B subsystem (kallvatten likely)
- `V600-56.{1,8}-001.pdf` — GTN värme (56 = värmesystem)
- `V390-52.E.{1,8}-001.pdf` — SNV ånga (done ✓)
- `V390-52.B.{1,8}-001.pdf` — SNV 52-B subsystem
- `V390-56.{1,8}-001.pdf` — SNV värme
- `HF Rörsystem.pdf` — pipe-system overview (index / cross-reference)

Electricity has **no PDF** — topology for el will have to come from Excel + Snowflake naming only. Some workstreams also lack a PDF (confirm per workstream when opened).

## 3. Sources and authority scopes

| source | authoritative for | weak on | path |
|---|---|---|---|
| flow-schema PDF (`V###-##.#.8-***`) | physical topology, pressure levels, meter presence, drawing date | BMS naming drift, accounting coefficients, electricity (missing) | `reference/flow_charts/` |
| Excel monthly reporting | formulas, intake meters, provider manual readings, allocation coefficients, tenant splits, human comments | pipe topology (none), silent year-over-year changes | `reference/monthly_reporting_documents/inputs/{gtn,snv,formula_document}.xlsx` |
| Snowflake BMS export | which meter IDs actually exist, which emit, actual consumption, commissioning/swap/decommission events | topology, intent, meaning of coefficients | `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` |

**Rule of thumb:** when sources conflict, prefer the one with authority for the aspect in question and log the decision. When uncertain, leave the conflict open in `open_questions.md` rather than guess.

## 4. Pipeline architecture (per-workstream folder)

Every workstream gets a numbered-stage folder under `reference/media_workstreams/{site}_{media}/`. Numbering encodes dependency order: re-running stage N invalidates stages ≥N+1.

```
reference/media_workstreams/{site}_{media}/
  00_inputs/                     # read-only mirror / symlinks of the raw sources used
      flow_schema.pdf            # symlink into reference/flow_charts/ (omit if none)
      excel_source.xlsx          # symlink into monthly_reporting_documents/inputs/
      timeseries_slice.csv       # only the rows from the Snowflake export that matter here
      README.md                  # which files, what dates, which exact versions
  01_extracted/                  # one artifact per source, no merging yet
      flow_schema_meters.csv     # from parse_flow_schema.py (skip if no PDF)
      flow_schema_relations.csv
      flow_schema_preview.html
      excel_formulas.csv         # cell → formula text, per sheet
      excel_intake_meters.csv    # intake / provider manual meters lifted from the xlsx
      excel_comments.md          # any cell comments, sheet notes, merged-cell hierarchy
      excel_tabs_inventory.md    # tab name, purpose, meters/formulas it owns
      timeseries_monthly.csv     # per-meter monthly deltas (first/last, n_readings)
      timeseries_anomalies.csv   # non-monotonic days, zero-run periods, gaps
  02_crosswalk/
      meter_id_map.csv           # facit_id ↔ snowflake_id ↔ excel_label ↔ bms_tag
      crosswalk_notes.md         # how each mapping was established; ambiguous ones
  03_reconciliation/             # the merge; this is where judgements live
      facit_meters.csv           # final meter list for this workstream
      facit_relations.csv        # final parent→child edges
      decisions.md               # every merge decision, with evidence and date
      open_questions.md          # known unknowns; explicitly unresolved
  04_validation/
      monthly_conservation.csv   # per-parent, per-month: Δparent, Σchildren, residual, %
      anomalies.md               # dead meters, swap events, drift, missing children
      methodology.md             # how deltas are computed; threshold choices; caveats
  05_ontology/                   # the Abbey Road-equivalent deliverable
      equipment.csv
      sensors.csv
      meter_relations.csv
      media_types.csv
      brick.ttl                  # once the site-wide TTL pattern is settled
  README.md                      # narrative overview, confidence, residual risks
```

For workstreams without a PDF (electricity, plus some misc.), `01_extracted/flow_schema_*` is simply absent — `decisions.md` notes that topology is derived from Excel + BMS naming only.

## 5. Stage definitions

### 00_inputs — raw-source mirror

Read-only. Either symlinks to the canonical files or dated copies if the canonical files could change. `README.md` records: which version, which date, which sheet/tab, which date range of timeseries. Goal: make it possible to re-run 01 with the exact same inputs six months later.

### 01_extracted — per-source machine output

One extractor per source; each writes into 01 without looking at the others.

- **Flow schema** → `parse_flow_schema.py` (existing). Produces meters, relations, preview HTML. Source-of-truth for topology.
- **Excel** → a new extractor (see Tooling, §8). Must lift: (a) formulas as text per cell, (b) tab inventory with purpose, (c) cell comments and sheet-level notes, (d) intake/manual-reading meters, (e) cross-sheet references. **Don't collapse formulas to numeric results**; the formula text is the evidence.
- **Snowflake timeseries** → a new extractor that takes the Snowflake CSV, slices it to the meters relevant for this workstream (via crosswalk seed), and emits `timeseries_monthly.csv` plus `timeseries_anomalies.csv` (dead meters, swap days, gaps). Uses `last − first` segmented at decrements, not `max − min`.

No merging happens here. Outputs are sibling views of the same underlying reality.

### 02_crosswalk — ID reconciliation

Single file: `meter_id_map.csv`. Columns:

```
facit_id,snowflake_id,excel_label,bms_tag,confidence,evidence
B611.Å1_VMM71,B611.Å1_VM71,"B611 ånga (intake)",611_STEAM_01,high,"GTN xlsx sheet 'Ånga' cell B14; Snowflake emits daily; naming is VMM→VM drop"
```

- `confidence` ∈ {high, medium, low}.
- `evidence` cites specific file/sheet/cell or timeseries observation.
- Ambiguous or conflicting mappings go in `crosswalk_notes.md` with options listed.
- Don't invent IDs that aren't in at least one source.

This is the most load-bearing artifact across the whole project — get it right per workstream before reconciling.

### 03_reconciliation — the facit

`facit_meters.csv` and `facit_relations.csv` are the final, authoritative statement of this workstream's meter set and topology. They're derived by merging 01's outputs, applying the crosswalk, and resolving conflicts per the rules in §3.

**`decisions.md` format** — one entry per merge decision:

```markdown
### 2026-04-16 — B611.VMM72 is a side-tap, not inline

**Question:** The Excel formula sheet implies B611.VMM71 → B611.VMM72 → B622.VMM72 as a chain. The flow schema shows B611.VMM72 as a dead-end side-tap with B622.VMM72 as a sibling.

**Sources:**
- `01_extracted/flow_schema_relations.csv`: B611.VMM73 → {B611.VMM72, B622.VMM72}
- `01_extracted/excel_formulas.csv`: row 14, formula `=B611.VM71 - B622.VM72`
- `01_extracted/flow_schema_preview.html`: the ⊗ glyph sits at x=1524 on the east tap, not on the main vertical

**Decision:** adopt the flow-schema topology (flödesschema is facit). The Excel formula is an accounting shortcut that can still be correct *mathematically* without reflecting the physical layout.

**Consequence:** `facit_relations.csv` lists B611.VMM73 → B611.VMM72 and B611.VMM73 → B622.VMM72 as separate edges. The Excel formula is preserved in `05_ontology/` as an allocation rule, not a topology edge.
```

**`open_questions.md` format** — one entry per unresolved issue, same evidence style, but explicitly **no decision yet**. Kept open until resolved; resolution moves it to `decisions.md` with a closing date.

### 04_validation — conservation

Monthly conservation check against `timeseries_monthly.csv`. Output `monthly_conservation.csv` has columns: `parent, month, delta_parent, sum_children_delta, residual, residual_pct, child_count, dead_children, flags`. `anomalies.md` groups findings into categories (dead meters, swap events, seasonal drift, missing children) with the evidence that implicates each.

Thresholds for flagging (defaults — overridable in `methodology.md`):

- Residual stable across months within ±5 pp of its mean → **losses, expected**.
- Residual stable at 100% → **dead children**.
- Residual shifts >20 pp across adjacent months → **commissioning / swap event**.
- Residual correlates with season → **missing seasonal consumer**.

### 05_ontology — Brick-style deliverable

Matches the Abbey Road schema (`data/reference_site/abbey_road/*`). Once the first workstream hits this stage we'll extract the columns and then keep later workstreams compatible. Hold off on authoring TTL until at least 2–3 workstreams have reached `03_reconciliation` so we can see the common shape.

### README.md — per-workstream narrative

One page. Sections: what this media looks like on this site, which sources were used, confidence per stage, top 3 residual risks, pointer to `decisions.md` for detail. Meant for a human (or agent) opening this folder cold.

## 6. Decision-log conventions

- **Date every entry.** `YYYY-MM-DD` prefix in the heading.
- **Cite evidence by path.** Never "the Excel says X"; always "`01_extracted/excel_formulas.csv` row 14 says X."
- **Prefer reopening to rewriting.** If a decision turns out wrong, add a new entry that supersedes it; leave the original in place with a note pointing to the newer one. History matters.
- **Open questions are first-class.** A workstream can ship to `05_ontology` with open questions as long as they're enumerated and their impact is stated.

## 7. Crosswalk — how to build it

Working rule for meter ID reconciliation observed so far:

- Flow-schema IDs use uniform `VMM##` (no suffix).
- Excel labels are inconsistent and often drop qualifiers.
- Snowflake names fall in two buckets: `VM##` (flow meters) and `VMM##_E` (energy meters). The `_E` suffix is not a separate meter, it's a naming variant.

Build the crosswalk seed by: (a) normalising all three — strip `_E`, `VM` ↔ `VMM` — and matching; (b) disambiguating leftover cases manually with evidence from cell comments or timeseries behaviour. Record the normalisation used in `crosswalk_notes.md` so it's auditable.

## 8. Tooling inventory

Existing:

- `reference/scripts/parse_flow_schema.py` — PDF → meters + relations + preview HTML. Handles inline/dead-end/corner meters, T-junction splitting, orphan-endpoint recovery.
- `reference/scripts/README.md` — usage and caveats.
- `outputs/from_pdf/{gtn_anga,snv_anga}_*.csv` — example facit outputs for validation.
- `logs/topology/flow_schema_parsing_notes.md` — parsing methodology and per-workstream notes.

To build (in order of need):

1. **Excel extractor** (`reference/scripts/parse_reporting_xlsx.py`): reads an `.xlsx`, emits `excel_formulas.csv`, `excel_tabs_inventory.md`, `excel_comments.md`, `excel_intake_meters.csv`. Uses `openpyxl` (needs adding to `uv` deps) to preserve formula text; `pandas` alone loses formulas.
2. **Timeseries slicer** (`reference/scripts/slice_timeseries.py`): takes the Snowflake CSV + a crosswalk, emits `timeseries_monthly.csv` and `timeseries_anomalies.csv` for a given workstream. Enforces `last − first` per monotonic segment; flags non-monotonic days, zero runs, gaps.
3. **Conservation runner** (`reference/scripts/validate_conservation.py`): takes `facit_relations.csv` + `timeseries_monthly.csv`, emits `monthly_conservation.csv` and a draft `anomalies.md`.
4. **Workstream scaffolder** (`reference/scripts/new_workstream.py`, optional): creates a fresh `{site}_{media}/` folder tree with empty template files, so every workstream starts identical.

Conservation methodology (persisted from earlier work):

- Use `last − first` sorted by timestamp, not `max − min`.
- Segment at any decrement; sum segment deltas.
- Don't interpolate across multi-day gaps.
- Report zero deltas as a **separate category**, not rolled into residuals.
- Compare parent and children over the same `[t_start, t_end]`, not each meter's own min/max timestamps.
- Always report per-month; collapse to annual only after confirming stability.

## 9. Execution order

1. **Template pass with GTN ånga.** We already have `01_extracted/flow_schema_*` (via the script) and a conservation check done by hand. Move those into the new folder structure, write the first `decisions.md` entries, build the Excel extractor against GTN's `.xlsx`, build the timeseries slicer, build the conservation runner, write `decisions.md` + `anomalies.md` + `README.md`. **This pass defines the template; don't skip the ceremony.**
2. **Second workstream, ideally SNV ånga.** Same media, different site — validates the template generalises. Adjust template if it's awkward.
3. **Remaining media with PDFs** (GTN/SNV värme, GTN/SNV kallvatten), in whatever order fits. These should be mostly routine if the template holds.
4. **Electricity and other PDF-less media.** No flow-schema source, so `01_extracted/flow_schema_*` is absent; topology comes from Excel + BMS naming only. Expect `open_questions.md` to be larger.
5. **Cross-workstream ontology authoring.** Once 3+ workstreams are at `03_reconciliation`, freeze the Abbey Road-equivalent schema for `05_ontology` and backfill.

## 10. Known risks / open questions (to track project-wide)

- Excel files may encode per-tenant allocations via merged cells and formatting — these are hard to extract mechanically; manual transcription into `excel_comments.md` may be necessary for cases the extractor misses.
- Boiler-side / plant-side meters (e.g. `B325.Panna2/3_MWH` in SNV) sit *upstream* of the flow schema's entry point and will never appear in the PDF parser output. Decide per-workstream whether to represent them as an implicit parent above the schema root, or as a separate upstream node in `05_ontology`.
- Virtual accounting meters (B611 Excel case) may have non-unit coefficients. Flow schema is pure topology (coeff = 1.0); Excel carries the coefficients. Reconciliation step must layer the coefficient onto the topology edge without pretending the coefficient is physical.
- Flow-schema PDFs are dated 2025-02-26. Pre-Feb-2025 timeseries may reflect an older topology; flag any per-month residual shifts crossing that date specifically.
- The conservation threshold defaults (5pp stable, 20pp shift) are guesses. Expect to tune them per-media once we've seen 2–3 workstreams.
- Flow-schema parser fails silently if a meter's ⊗ glyph is drawn *on top of* a continuous pipe (no gap) — the meter becomes a dead-end stub on the adjacent tap. See the `B611.VMM72` case in GTN ånga. The preview HTML is the defence; eyeball it for every workstream.

## 11. Flow-schema parser — accuracy & robustness plan

Parser quality is iterative. We expect two classes of work: (a) **general improvements** that make every future PDF come out better, and (b) **per-diagram investment** where we accept that a particular drawing needs manual assistance and provide the mechanism to record and preserve that assistance across re-runs.

### 11.1 Quality dimensions — what "accurate" actually means

| dimension | what it checks | how we measure today |
|---|---|---|
| meter extraction | every labeled `B###.{subsystem}_VMM##` is captured | label-count-in-parser == label-count-in-eyeballed-PDF |
| pipe extraction | every axis-aligned pipe line is captured | spot-check via preview HTML |
| edge completeness | every pair of meters that share a pipe has a `feeds` edge | per-building audit: meters of one building should be in a small number of components |
| edge direction | edge parent→child points the real flow direction | arrow-direction cross-check + Excel S-column agreement |
| symbol passage | pipes passing through VVX / pump / valve are not broken | gap-bridge count + per-building audit |
| visual fidelity | parser's inferred topology overlays cleanly on the PDF | manual eyeball of `flow_schema_preview.html` |

Good targets per workstream: ≥95% of "expected edges" captured, 0 wrong-direction edges. Today on V600-56 we're at ~60–70% on edge completeness; direction is good where arrows or Excel cover.

### 11.2 Roadmap — general parser improvements (benefit every PDF)

Phased so each phase is shippable on its own. Implement in order.

**Phase 1 — Closed-shape passage detection.** *Biggest quality win; the #1 remaining cause of missing edges.*

- Detect closed polygons in the pipe graph: 4-segment rectangles (VVX, pump casings), triangles (pressure-reducer symbols), small diamonds (arrow tails, false positives to skip).
- For each closed shape, identify "ports": external pipe endpoints abutting the polygon's perimeter.
- Classify: a shape with two ports on opposite sides → `through-passage`, bridge the ports. A shape with no opposite ports → `terminator` (e.g. tank, consumer flag).
- Replaces the current blunt "bridge same-axis dead-ends within 20u" heuristic, which over-connects in some cases and misses longer gaps.

**Phase 2 — Arrow-guided bridging at larger distances.**

- An arrow near a pipe terminus is strong evidence that flow continues beyond. If a dead-end pipe endpoint lies at an arrow's tail, extend the bridge search radius in the arrow's direction up to ~60–100u.
- Arrows are the *authoritative signal* for "there is still pipe here, even if I can't see it as a segment."

**Phase 3 — Non-axis-aligned pipe support.**

- Some schemas use 45° pipe runs. Extend `filter_pipe_segments` to keep segments whose angle is a multiple of 45°, and generalise `split_at_tees` to diagonal crossings.
- Lower priority — GTN/SNV flow schemas use primarily H/V pipes — but would be needed for HF Rörsystem or any curved-pipe drawings.

**Phase 4 — Curved pipe / Bézier support.**

- PDF arcs/curves appear in the SVG as `C` commands (cubic Béziers). Currently dropped. For rare curved pipes, approximate as piecewise-linear.

**Phase 5 — Structured diagnostic output.**

- Dump a `flow_schema_graph.json` alongside the CSVs: every node, every edge, every arrow, every bridge with source provenance. Enables post-hoc visualization tools and reproducible debugging.

**Phase 6 — Visual audit overlay.**

- Render the PDF to PNG at fixed resolution; overlay parser-inferred edges as coloured lines. Save as `flow_schema_audit.png`. Let a reviewer compare parser output directly against the drawing, not against an SVG approximation.
- This is the defence against silent regressions.

**Phase 7 — Parser unit/regression tests.**

- Save a small hand-curated `expected_relations.csv` per processed PDF under `{workstream}/03_reconciliation/`. A test runner asserts the parser's output contains every expected edge (and no contradicting edge). Break the build when a parser change regresses any PDF.

### 11.3 Per-diagram iteration — when the parser can't figure it out

Not every PDF will yield to generic heuristics. Some drawings are idiosyncratic (custom symbols, handwritten annotations, overlapping labels). Rather than keep tuning the generic parser for edge cases, we make *manual corrections first-class* and preserve them across re-runs.

**Mechanism: overrides and expected-edges files.**

- `{workstream}/03_reconciliation/topology_overrides.csv` — rows the human added, deleted, or reversed. Columns: `action` ∈ `{add, remove, force_direction}`, `from_meter`, `to_meter`, `reason`, `date`, `author`. Applied AFTER `facit_relations.csv` is copied from `flow_schema_relations.csv`, on each re-run.
- `{workstream}/03_reconciliation/expected_relations.csv` — hand-curated ground-truth edges for this PDF. Parser output is diffed against it; differences fall into `parser_missed`, `parser_extra`, `direction_flip`. Shown in a new `04_validation/parse_audit.md`.
- `{workstream}/03_reconciliation/parse_tuning.yaml` — per-diagram CLI parameter overrides (e.g. `bridge_gaps: 35` if a specific drawing has wider VVX symbols). So re-running the parser for this workstream always uses the tuned values.

**Iteration loop for a hard PDF:**

1. Run generic parser → `flow_schema_relations.csv`.
2. Open `flow_schema_preview.html`; eyeball vs the PDF.
3. For each missed or wrong edge, add a row to `topology_overrides.csv` (or `expected_relations.csv` if it's a validation fixture).
4. Re-run: parser output + overrides → corrected `facit_relations.csv`.
5. Audit report shows what was parser-derived vs what was manual, so provenance stays clear.

**Investing in a specific diagram** means (in order of escalating effort):

- Tune CLI params (`--radius`, `--bridge-gaps`).
- Add rows to `topology_overrides.csv`.
- Curate `expected_relations.csv` so regressions become visible.
- If a pattern repeats across multiple diagrams, promote it to a generic improvement (phases 1–7 above).

### 11.4 What good provenance looks like on every edge

Every row in `facit_relations.csv` (and `05_ontology/meter_relations.csv`) already carries a `derived_from` tag. After the improvements above, the tag vocabulary should be:

- `flow_schema_V###-XX.X-NNN` — parser produced this edge, direction from user-declared `--sources` or Excel S-column (the baseline)
- `flow_schema_V###-XX.X-NNN/arrow` — direction independently confirmed by a detected arrow on this pipe
- `flow_schema_V###-XX.X-NNN/bridged` — edge exists thanks to a VVX/symbol-gap bridge (lower confidence)
- `flow_schema_V###-XX.X-NNN/auto_root_degree` — no declared source, direction picked by graph heuristic (lower confidence; warn in audit)
- `topology_override_{YYYY-MM-DD}_{author}` — manually added/corrected; reason must be cited

Downstream consumers (ontology builder, conservation runner, app) can use these tags to colour-code confidence or filter out low-confidence edges.

### 11.5 Effort & order

Rough effort (net-new, not including re-runs):

| phase | est. hours | blocks what |
|---|---|---|
| closed-shape detection | 3–4 | completes most missing VVX bridges |
| arrow-guided bridging | 1 | long-span bridges, pump casings |
| override mechanism | 2 | per-diagram quality ceiling |
| expected-relations fixtures | 1 per PDF | regression safety |
| audit overlay PNG | 2 | visual review |
| unit tests | 1–2 | prevents regressions |
| non-axis-aligned & Bézier | 3–4 | rare-case coverage |

Recommended order for the next push:
1. **Closed-shape detection + override mechanism** together (so we have a principled way to absorb remaining edge cases).
2. **Arrow-guided bridging** + **audit overlay PNG** for visual verification.
3. **Expected-relations fixture for V600-56** (the problem child) — lock in the manually-verified ground truth so later runs can't regress it.
4. Revisit generic improvements only when a new PDF motivates them.

### 11.6 Known limitations to document until fixed

- Meter symbols drawn *on top of* a continuous pipe (no gap) are treated as dead-end stubs. See `B611.VMM72` in GTN ånga. Preview HTML is the defence.
- Complex symbols (pumps with curved internals, three-way valves, pressure reducers) that aren't simple axis-aligned rectangles still break the graph. Phase 1 catches some; phase 3–4 would cover more.
- Multi-page PDFs are untested. All current drawings are single-page.
- Swedish characters in meter IDs (`Å`, `Ä`, `Ö`) work because the code is UTF-8 end-to-end, but assume this on every new data source.

---

## 12. Cross-references

- Flow-schema parsing script: `reference/scripts/parse_flow_schema.py`
- Flow-schema parsing notes: `reference/monthly_reporting_documents/logs/topology/flow_schema_parsing_notes.md`
- GTN ånga facit: `reference/monthly_reporting_documents/outputs/from_pdf/gtn_anga_*.csv` + `gtn_anga_preview.html`
- SNV ånga facit: `reference/monthly_reporting_documents/outputs/from_pdf/snv_anga_*.csv` + `snv_anga_preview.html`
- Abbey Road template (ontology shape we're replicating): `data/reference_site/abbey_road/*.csv`
- Snowflake query used for timeseries export: documented in `00_inputs/README.md` of the first workstream we stand up; the current query is 2025-01-01 → 2026-01-03 daily-aggregated all meters all quantities.
