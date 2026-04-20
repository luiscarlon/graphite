# RESOLVE_ONTOLOGY — working instructions

Instructions for building a Brick-style metering ontology from heterogeneous documentation (flow-schema PDFs, Excel monthly-reporting, Snowflake BMS timeseries). One workstream per (site, media). Written so the work can be picked up cold from this document.

---

## 0. How to work — non-negotiable rules

**You are an analyst, not a pipeline operator.** The scripts in `reference/scripts/` are helpers that produce INPUTS for your reasoning. You read their outputs, understand the physical system, make decisions, and build the ontology by hand. Every edge, annotation, and decision is yours — curated with evidence.

**Excel is facit; flow schema is a helper.** When sources conflict — naming heuristics, flow-schema PDF arrows, timeseries residual fits — **Excel accounting structure wins**. The ontology target is that, for each (building, media) month, `SUM(meter_net)` for meters attributed to that building = the cached Excel cell value. Every + term is an independent supply meter attributed to the building; every − term must be hasSubMeter-reachable from exactly one + term in that building's subtree. The PDF helps only when Excel is silent (e.g. which + term physically feeds which − term). When the PDF disagrees with Excel on direction or membership, the PDF loses.

**Excel comparison = cached values only.** When comparing building totals against the Excel file, use the **actual cached cell values** from the media tab (`excel_building_totals.csv`), NEVER a reconstruction from Snowflake data using the formula structure. The Excel file only has fiscal-year 2026 data (Jan–Dec). Snowflake ends at 2026-02-28. **The only valid comparison months are 2026-01 and 2026-02.** Comparing for 2025 months is impossible — the Excel has no data for those months.

**The real topology-match test:** `SUM(meter_net)` per (building_id, media, month) joined on `meters` — compared to `excel_building_totals.csv`. This is what the app's `_excel_comparison_section` does. **`validate_building_totals.py`'s spot-check is NOT the topology test.** It only proves the Excel formula, evaluated by summing Snowflake deltas per meter_id, produces the cached cell value — i.e., meter-ID mapping is correct. A spot-check at 0.1% can coexist with a topology that's 1500% off (happened with värme). Always run the `meter_net` aggregation test before declaring a workstream done.

**Fuzzy-match before declaring a meter Snowflake-absent.** Before accepting a crosswalk note like "STRUX-only meter (not in Snowflake BMS)", verify against the full Snowflake ID set (~1169 IDs for GTN): exact match, normalized match (strip all non-alphanumerics, lowercase), tail-segment substring (e.g. `T4-A3` in any Snowflake ID with matching building prefix), known transformations (`-S` suffix on EL main transformers, `VM`↔`VMM`, dot↔underscore, `_E` energy-variant suffix). Only after all of these fail is the meter genuinely absent. **Never synthesize Snowflake-format readings from STRUX monthly values** — that hardcodes a secondary source into the primary stream. If a meter is genuinely STRUX-only, accept the gap visibly or model it with a separate `database_id` (e.g. `gtn_strux`) that distinguishes provenance downstream.

**Reference workstreams (use with caution):**
- `gtn_anga` — 21 meters, closest to "done". Study its decisions.md, annotations, and assembled state. Known residuals: B600 intake (expected) and B616 (~900 MWh/month genuinely unallocated in Excel). Note: pre-2026-04-19 it carried a B642.Å1_VMM72 patch derived from VMM71 that was masking valid post-swap Snowflake data — fixed by adding a proper `:d.C` raw segment. Check that any similar patches in new workstreams aren't hiding good data.
- `gtn_varme` — 59 meters, 29 hasSubMeter edges after Excel-priority realignment. 16 PDF/naming edges removed, 5 Excel-derived edges added, 4 VÅ9 meters reattributed to campus. 48/48 match Jan, 47/48 Feb. Demonstrates the pattern for bringing a PDF/naming-led topology into Excel alignment — replicate that diff pattern when you find similar mismatches in SNV.
- `data/sites/gartuna/annotations.csv` — site-level annotations with specific evidence (not generic "swap detected").

**Checklist — do ALL of these for every media:**

1. **Understand the physical system.** What pipes connect what? Where do the meters sit? What does each Excel formula mean physically (not just mathematically)?

2. **Excel reconciliation is the ground truth — and the test is `meter_net` aggregation, not the spot-check.** Compute `SUM(meter_net)` per (building, media, month) and compare to the cached Excel values. Investigate EVERY diff > 1%. The Excel is validated monthly by humans — if your topology disagrees, your topology is probably wrong. Do not mistake `validate_building_totals.py`'s 0.x% spot-check for a topology match; see §0 for what the spot-check actually tests.

3. **Fix all ontology violations.** Run `validate(ds)` after building. Zero violations is the target. Each violation means something is wrong.

4. **Patch only when the raw data is actually bad.** Device swap (counter resets and then resumes recording normally) → A/B/C raw segments + rolling_sum stitching, NOT a children-sum patch. Genuine offline (counter freezes permanently) → children-sum patch + rolling_sum. Glitch (short bad window, then reverts) → validity split around the glitch. Before applying any patch, check the raw post-reset Snowflake readings: if they're monotonic and reasonable, use a segment split. A patch derived from children or siblings can silently mask valid data — B642.Å1_VMM72 carried a VMM71-derived patch that hid the real post-swap counter and caused a 35 MWh B642 / −35 MWh B614 mirror error in the app until 2026-04-19.

5. **Write curated annotations.** Each annotation has: what happened, when, which meter, what the data shows, what was done about it. No generic "swap detected" — explain the swap. No bulk generation.

6. **Document every decision.** In `decisions.md`, with evidence citations (file + row/cell). In `open_questions.md` for unresolved issues.

7. **Classify every building-month diff.** After the first app-validation pass, fill `05_ontology/excel_comparison_annotations.csv` with `reason` + `explanation` for each row. See §5 under `05_ontology` for the current tag vocabulary. Keep tags short; invent new ones when warranted (the vocabulary is intentionally flexible). Update the file whenever the ontology changes — it is a snapshot of the current reconciliation state, not an aspirational target.

**What NOT to do:**

- Do NOT run `regenerate_workstream.py` blindly and call it done
- Do NOT re-run `build_ontology.py` on a working workstream — it destroys outage patches, curated timeseries refs, cross-ID device swaps, relation type fixes, and other manual refinements in `05_ontology/`. **If you must rebuild, re-apply ALL manual edits from Phase 7 afterwards.** The manual edits are documented in `decisions.md` — search for "device swap", "false positive", "relation type" entries.
- Do NOT skip `generate_building_virtuals.py` — it is MANDATORY, not optional. Every building with an Excel formula row needs a virtual meter. Without them, `meter_allocations.csv` is incomplete and the app's Excel comparison view breaks.
- Do NOT skip `classify_excel_diffs.py` — every new workstream must have its `excel_comparison_annotations.csv` filled in before shipping. An unexplained >0.1% offender without a `reason`/`explanation` is an undocumented gap that future-you won't remember.
- Do NOT generate annotations in bulk — every one is curated
- Do NOT model Excel accounting formulas as physical topology. `B600-KB2 = B623 + B653 − B658` is bookkeeping, not pipes. B623 is a standalone building meter, not a feed into a cooling main.
- Do NOT include meters in the ontology that don't belong to this media. If the crosswalk is too broad (includes heating meters in a cooling workstream), narrow it to only the formula-referenced meters + their confirmed physical sub-meters.

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
- `V600-52.B.{1,8}-001.pdf` — GTN kallvatten (done ✓)
- `V600-56.{1,8}-001.pdf` — GTN värme (done ✓)
- `V390-52.E.{1,8}-001.pdf` — SNV ånga (not started)
- `V390-52.B.{1,8}-001.pdf` — SNV kallvatten (not started)
- `V390-56.{1,8}-001.pdf` — SNV värme (not started)
- `HF Rörsystem.pdf` — the master index of the six flödesscheman above (distributionsnät Stadsvatten / Ånga / Värme × GTN / SNV). Confirms definitively that **no PDF exists for kyla, sjövatten, kyltornsvatten, or el** — those must use Excel + BMS only.

**Current workstream status (2026-04-19):**

| workstream | pipeline stage reached | notes |
|---|---|---|
| `gtn_anga` | through `06_assembly` + app-validated + classified | 21 meters, 5 hasSubMeter edges. 96 building-months classified: **92 match**, 2 `match_intake` (B600 — intake residual expected), 2 `excel_stale` (B616 ~900 MWh/month genuinely unallocated in Excel). 2026-04-19 fix: replaced B642.Å1_VMM72 VMM71-derived patch with proper `:d.C` raw segment. |
| `gtn_varme` | through `06_assembly` + app-validated + classified | 59 meters, 29 hasSubMeter edges after Excel-priority realignment. 96 building-months classified: **95 match**, 1 `meter_outage` (B833 Feb +23 MWh — outage patch captures consumption that Excel's frozen VP1 counter misses). 16 PDF/naming edges removed, 5 Excel-derived edges added, 4 VÅ9 meters reattributed to campus. |
| `gtn_el` | through `06_assembly` + app-validated + classified | 76 meters, 10 hasSubMeter edges. 100 building-months classified: **85 match**, 6 `strux_only_meter` (B611/B613/B631 — T4-A3/C1/C4 not in BMS), 4 `excel_stale` (B664/B665 T42-2-1 mirror), 2 `excel_bug` (B652 residual from B612 double-sub fix), 2 `ontology_drift` (small <0.2% unexplained), 1 `under_investigation` (B660 Feb only, −141 MWh). Fix applied: direct edge `B612.T8 → B652.T8-A3-A14-112` to mirror Excel's double-subtraction; B659.T28-3-5 moved from phantom BUNATTR building to campus. |
| `gtn_kyla` | through `06_assembly` + app-validated + classified (full rebuild 2026-04-19) | 32 meters (22 physical + 10 virtual), 20 edges (6 hasSubMeter + 14 feeds). **0 Brick validation violations.** 98 building-months classified: **84 match**, 4 `data_quality_artifact` (B611/B833 — dead pool meters + active sub-meters yield negative residuals), 4 `excel_cooked_coefficient` (B612/B641 — fractional 0.9×/0.1×B637 with no views.sql primitive), 2 `excel_bug` (B623 double-counted in B623 building AND B600-KB2 pool), 2 `excel_stale` (B658 known "Excel=0 but meter live"), 2 `ontology_drift` (B621/B622 small residuals). See `03_reconciliation/decisions.md` — `$R`-style per-row factors and mixed inline coefficients are mis-recorded in `01_extracted/excel_formulas.csv` for kyla rows 13/14/15/20/22/26/29/33/38/50; always re-parse formula text directly via `openpyxl.ArrayFormula.text` for kyla. |
| `gtn_kallvatten` | through `06_assembly` + app-validated + classified (built 2026-04-19) | 63 meters (62 with Snowflake + 1 STRUX-only inactive B869). 11 hasSubMeter edges, 0 feeds. 98 building-months classified: **98/98 match** (100%). 0 Brick validation violations. Simplest pattern of the energy-intensive media: all coefficients 1.0, no cross-building virtuals. Building label `850/662` (dual-building Excel label) normalized to `B850`. |
| `gtn_kyltornsvatten` | through `06_assembly` + app-validated + classified (built 2026-04-19) | 7 meters (4 with Snowflake + 3 Excel-only inactive system-code meters). 0 edges, 0 virtuals. 90 building-months classified: **90/90 match** (100%). 0 Brick validation violations. Each building has a single +term meter, no subtractions. |
| `snv_el` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 156 meters, 125 edges + 43 building virtuals. 137 building-months classified: **117 match**, 6 `under_investigation` (B305/B392 −23 MWh complex-formula undercount likely same root cause; B344 −2.3 MWh hasSubMeter-child double-attribution), 5 `excel_cooked_coefficient` (B310/B311/B317 cross-building fractional pools — 0.5/0.5, 1/3/2/3, 0.4/0.5/0.1 — no views.sql primitive), 2 `strux_only_meter` (B304 STRUX-only summary meters), 7 `ontology_drift` (B318/B330/B337/B342 small <3% unexplained). First SNV workstream: establishes `-1` summary suffix, `_1_1` underscore trunk, and dash↔underscore separator drift crosswalk rules for other SNV media. |
| `snv_anga` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 34 meters, 18 Excel-derived hasSubMeter edges + 24 building virtuals. **0 Brick validation violations.** 131 building-months classified: **126 match**, 3 `meter_outage` (B216.Å1_VM71 froze Feb 18; B308.Å1_VMM71 frozen all period, patched from child B327), 2 `excel_bug` (B307 10-term pool formula double-subtracts B330.Å1_VMM71 that's already B337's child — ~1 MWh/mo residual). Excel-is-facit build: 10-term row 23 (B307) needed a parser fix — `$B$23` substitution was wiping `AB23` inside `XLOOKUP(AB23,…)` because `str.replace` matched the bare `B23` substring (see parse_reporting_xlsx.py §parse_formula_terms, fixed with word-boundary regex). Two other build_ontology.py improvements applied: (a) after an `offline` event, don't emit a `(None, swap_date)` segment that reads as blank valid_from and overlaps prior segments; (b) patch sources pointing at a `rolling_sum` derived ref must be rewritten to the appropriate raw segment since `assemble_site.py` materializes `sum` before `rolling_sum`. No PDF edges kept — PDF roots at B200.Å1_VMM70 which is not in Snowflake; B325.Panna2/3_MWH boilers are upstream of the flödesschema. |
| `snv_varme` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 46 meters, 30 Excel-derived hasSubMeter edges + 31 building virtuals. **0 Brick validation violations.** 127 building-months classified: **125 match**, 2 `excel_bug` (B327 Jan/Feb under-count by ~17 MWh — row 38 double-counts `B326.VS1_VMM61` which is already B326's sole + term in row 37). Row 22 is a 27-term distribution pool for B310 spanning 11 sub-buildings — handled by Excel-derived edges. Crosswalk caveat discovered: when both bare (`B330.VS1_VMM61`) and `_E` (`B330.VS1_VMM61_E`) variants exist in Snowflake, the fuzzy-match must prefer whichever matches STRUX/Excel — the bare variant was the WRONG meter for B203 and B330 (~250 MWh/mo discrepancy). B201 offline detection flagged a 2025-08-05 counter reset that actually stayed dormant until 2026-02-24 — reclassified as `swap` so post-reset Feb readings contribute. No PDF edges kept — the flow schema is exhaustively aligned with Excel's − term structure already. |
| `snv_kyla` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 28 real meters + 4 `B###.KYLA_VIRT` aggregator virtuals, 6 `feeds` edges with fractional coefficients (no `hasSubMeter` — all Excel formulas are pure + terms, zero subtractions). **0 Brick validation violations.** 139 building-months: **139 match (100%)**. Two parser bugs fixed during build: (a) `extract_building_formulas` had a col-R `factor_cell` fallback that clobbered correct per-term coefficients — whenever ANY term has a non-unit coefficient, per-term values are now authoritative for all terms (previously, B305 row 22's S term wrongly inherited `R22=0.5`); (b) `extract_building_totals`'s `sheet_factor` fallback only kicks in when every record has the same numeric factor — previously it matched when the only factor on the sheet was shared by a few rows, doubling all SNV kyla totals. Four cooked-coefficient splits (row 19/20: B304.KB2 0.5/0.5 → B302/B303; row 22/23: B307.KB1 0.5/0.5 → B305/B307) routed via `B###.KYLA_VIRT` feeds edges so `views.sql::meter_net = flow × (1 − Σk)` correctly drains the source meters' contribution. Four STRUX-only meters (B202.VENT, B331.KB1_VM51_E, B336.KB1, B392.KB1_VM51_E — the last only in Snowflake as Water Volume m³, not energy) left as strux_only; their Excel cached values are 0 for the Jan/Feb window so no match loss. |
| `snv_kallvatten` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 63 real meters, 33 Excel-derived hasSubMeter edges + 40 building virtuals. **0 Brick validation violations.** 134 building-months classified: **128 match**, 6 `excel_bug` on B310/B311/B314 (B313.KV1_VMM22_V double-subtracted in rows 26 and 30; B315.KV1_VMM21_V double-subtracted in rows 26 and 27 and double-claimed as + term in rows 30 and 31). Row 27 (B311) is a 16-term distribution pool. Third parser bug fixed: `extract_building_totals` was picking up a "Total från under-mätare" summary row (col A = "Total ...", col B = string "B390") as a per-building total, inflating B390's kallvatten by ~18,700 m³/month — now skipped when col A is "Total*"/"Summa*" AND col B is already a B-prefixed string. GTN kallvatten regression-safe (GTN's "Total Gärtuna" uses integer col B = 600, which the new filter preserves). `primary_add` attribution now prefers the + building whose prefix matches the meter's own prefix (B315.KV1_VMM21_V attributes to B315, not B314). No PDF edges kept — V390-52.B.8-001 yielded only 1 meter / 0 relations from the parser. |
| `snv_sjovatten` | through `06_assembly` + app-validated + classified (built 2026-04-20) | 19 real + 4 `SJOVATTEN_VIRT` virtuals, 4 hasSubMeter edges (row 51 7-term `B339 kylmaskiner`) + 4 `feeds` edges (rows 27/28 and 45/46 0.5-splits). **0 Brick validation violations.** 146 building-months classified: **130 match**, 10 `excel_cooked_coefficient` (B301/B302/B303/B307/B344 BPS fractional splits — `= R{n} × BPS_V2` where BPS_V2 is a sheet-level residual = `Σ(B342 inlets) − Σ(15 direct consumers)`, with monthly-variable R factors; not mirrored in ontology because views.sql expects constant coefficients), 6 `strux_only_meter` (B304-52-V2-AW026 manual meter; Kringlan/Scania external Telge Nät consumers). Building-totals post-processing normalises "339 Kolfilter"/"339 kylmaskiner" → B339 (summed), "409 Kylcentral" → B409, drops "BPS Beräkning" summary row and meter-ID-as-building helper rows 88–105. Most complex SNV sheet by far — BPS aggregator + five-way percentage split + external consumers + mix of auto/manual meter reads. |

**Expected difficulty per media** (based on GTN completion, use for SNV planning):

| media | expected difficulty | watch out for |
|---|---|---|
| ånga | easy-medium | B600-style intake expected-residual; occasional "Excel=0 but meter live" misallocations (B616 on GTN); device-swap patches that might mask real post-swap data (GTN B642) |
| värme | medium | Naming-heuristic edges (VP1→VS1, VP1→VÅ9, VMM61→VMM62 chain) frequently contradict Excel — **drop them unless Excel confirms**. PDF arrows can be wrong too (B615→B642 on GTN). Outage patches on offline primary meters (B658, B833 on GTN) |
| kyla | hard | Excel formulas use `$R`-style factors and per-term coefficients. **As of 2026-04-20 the parser handles these correctly** (extract_building_formulas now preserves per-term coefficients authoritatively when any term is non-unit; extract_building_totals' sheet_factor fallback no longer misfires on partial-factor rows). Fractional subtractions (0.9×term, 0.1×term) have no views.sql primitive → expect 1–3 MWh residuals. Cross-building accounting virtuals (B600-KB2 pool, Prod-600). Dead source meters create negative building values. Bi-daily BMS sensors |
| el | hard | STRUX-only meters without Snowflake data (B611.T4-A3/C1/C4 on GTN, H-prefix provider meters). `-S` suffix on main transformers. Deep sub-feeder chains where Excel double-subtracts from multiple parents. Excel-stale zeros (B664/B665 on GTN) |
| kallvatten | easy | Cleanest media — uniform `B###.KV1_VM##` naming, all coefficients 1.0, typical 100% match. `_V` suffix variant on some meters. Dual-building Excel labels (`850/662`) need renaming post-extraction |
| kyltornsvatten | trivial | 7 single-meter formulas, no subtractions. Some legacy system-code meters (`-52-`, `-55-`) that aren't in Snowflake — accept as dormant |

**SNV starter checklist** (same playbook as GTN; 4 hours per media for a clean one, 1–2 days for a hard one):

1. `mkdir -p reference/media_workstreams/snv_{media}/00_inputs`; symlink `excel_source.xlsx` → `snv.xlsx`, add `flow_schema.pdf` symlink if one exists (see §2 PDF list).
2. Add a `Config` entry in `reference/scripts/regenerate_workstream.py` (pattern: copy the matching GTN entry, change `site="SNV"`, `pdf_sources=` to SNV roots).
3. Run `parse_reporting_xlsx.py` to produce `01_extracted`.
4. **For kyla specifically**: run a formula-text re-parse (see §7 "Excel formula re-parse caveat") and rebuild `facit_accounting.csv` with correct per-term coefficients before proceeding.
5. Build `02_crosswalk` using the fuzzy-match procedure (§7). Document every naming convention discovered in `crosswalk_notes.md`.
6. Build `03_reconciliation/facit_accounting.csv` and `facit_relations.csv` by mirroring the Excel formula structure: each `+` term is an independent supply meter attributed to its building; each `−` term at k=1 becomes a `hasSubMeter` child of one `+` term in the same building (typically the first one); fractional coefficients → `feeds` edges. Virtual meters only for cross-building accounting aggregators (e.g. SNV's equivalent of GTN's B600-KB2 if it has one).
7. Build `05_ontology/` CSVs by hand (don't rely on `build_ontology.py` for anything non-trivial — use it only as a template). Ensure every `+` term meter's building_id is set; orphans go to campus (blank building_id).
8. Run `assemble_site.py` with all SNV workstreams once the first two are ready (need at least 2 to test cross-workstream join logic).
9. App-validate: `SUM(meter_net)` per (building, media, month) vs `excel_building_totals.csv` cached values. Target: >95% of populated buildings within ±0.5 (unit). Investigate every offender; annotate or fix.
10. **Classify every building-month in `05_ontology/excel_comparison_annotations.csv`** (see checklist item 7 in §0 and the schema in §5 under `05_ontology`). This is **required before declaring the workstream done** — it's how known gaps get documented and carried into the app. Run `python reference/scripts/classify_excel_diffs.py`; add a `(workstream, site, media_id)` entry to its `WORKSTREAMS` list and populate the `CURATED` dict with known-offender buildings keyed by reason (pull evidence from your `decisions.md` / `open_questions.md`). Then re-run `assemble_site.py` so the site bundle picks up the new file. Noise threshold is already encoded: `excel > 0 and pct < 0.1` or `excel == 0 and absd < 10` (native unit) → `match`. Everything above noise must have a curated reason or falls through to `ontology_drift` / `under_investigation`.
11. `validate(ds)` must return 0 violations. If a feeds-sum-to-1 violation appears for power-to-energy conversions (like GTN B634), add a residual-destination virtual at k=`1 − coefficient`.

## 3. Sources and authority scopes

| source | authoritative for | weak on | path |
|---|---|---|---|
| Excel monthly reporting | accounting structure (which meters belong to which building, + vs − term roles), cached monthly values per building (`excel_building_totals.csv`), coefficients, tenant splits, human comments | pipe topology (none), silent year-over-year changes | `reference/monthly_reporting_documents/inputs/{gtn,snv,formula_document}.xlsx` |
| Snowflake BMS export | which meter IDs actually exist, which emit, actual consumption, commissioning/swap/decommission events | topology, intent, meaning of coefficients | `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` |
| flow-schema PDF (`V###-##.#.8-***`) | helper for physical pipe layout when Excel is silent (e.g. which + term feeds which − term) | Excel-contradicting arrows, BMS naming drift, coefficients, electricity (missing) | `reference/flow_charts/` |

**Rule of thumb:** Excel wins on accounting structure and building attribution. Snowflake wins on which meters exist and their actual readings. Flow-schema PDF is a helper for ambiguous cases — when it contradicts Excel on direction or membership, drop the PDF edge. Log every decision in `decisions.md`. Leave unresolved conflicts in `open_questions.md` rather than guess.

**Concrete consequences:**
- A PDF arrow `A → B` does NOT override Excel treating both A and B as independent **+** terms for the same building (e.g. `B615 → B642` arrow was removed in favour of Excel's independent subtraction of B615 and B642 from B614).
- Naming heuristics (VP1→VS1, VP1→VÅ9, index chain VMM61→VMM62) are **suggestions, not facts**. Check every one against Excel before keeping. They produced the bulk of värme's violations before the 2026-04-19 realignment.
- Meters not referenced in any Excel `+` term should be reattributed to campus level (blank `building_id`), not left in a building where they add uncounted consumption.

## 4. Pipeline architecture (per-workstream folder)

**The pipeline is a framework with helper scripts, not an automated tool.** The scripts in `reference/scripts/` produce INPUTS for reasoning — extracted layers, validation reports, candidate edges. The reconciliation (`03_reconciliation/`), ontology (`05_ontology/`), annotations, and decisions are the **analyst output**: every edge, annotation, and decision is curated individually with evidence. No bulk generation. No mechanical re-running on working workstreams.

Every media has a different physical system, different data quality issues, and different topology challenges. The analyst must understand the physical system (what pipes connect what, where the meters sit, what the Excel accounting formulas mean physically), analyze every source qualitatively, and build the topology by hand — documenting each decision.

The `05_ontology/` directory is the **product of careful analysis**. It is not a disposable intermediate that can be regenerated by running a script. Re-running `build_ontology.py` on a working workstream will destroy outage patches, curated timeseries refs, and other manual refinements.

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
      meters.csv                 # excludes virtual building meters
      meter_relations.csv        # hasSubMeter (physical) and feeds (allocation)
      sensors.csv
      timeseries_refs.csv        # includes swap/offline/glitch multi-segment refs
      meter_allocations.csv      # Excel accounting formulas (documentation only)
      annotations.csv            # auto-generated from pipeline events + manual additions
      excel_comparison_annotations.csv  # curated reason+explanation per (building, month)
      buildings.csv              # stub for site-level merging
      media_types.csv
```

After all media workstreams reach `05_ontology/`, the site-level assembly runs:

```
data/sites/{site}/               # single Dataset loadable by ontology.load_dataset()
    site_meta.yaml               # name, campus_id, summary
    meters.csv                   # union of all media
    meter_relations.csv
    sensors.csv
    timeseries_refs.csv
    readings.csv                 # materialized from Snowflake + derived refs
    annotations.csv              # merged from all media + manual additions
    excel_comparison_annotations.csv  # merged reason+explanation per (building, month)
    meter_allocations.csv        # Excel formulas for comparison
    campuses.csv, buildings.csv, zones.csv, databases.csv, devices.csv
    meter_measures.csv           # auto-generated: meter → building/campus
```

For workstreams without a PDF (electricity, plus some misc.), `01_extracted/flow_schema_*` is simply absent — `decisions.md` notes that topology is derived from Excel + BMS naming only.

## 5. Stage definitions

### 00_inputs — raw-source mirror

Read-only. Either symlinks to the canonical files or dated copies if the canonical files could change. `README.md` records: which version, which date, which sheet/tab, which date range of timeseries. Goal: make it possible to re-run 01 with the exact same inputs six months later.

### 01_extracted — per-source machine output

One extractor per source; each writes into 01 without looking at the others. See §11.7 for the layer table and the rule that no tool writes into `03_reconciliation/`.

- **Flow schema** → `parse_flow_schema.py`. Produces `flow_schema_{meters,relations}.csv` + `flow_schema_preview.html`. Handles three-tier bridging (same-axis ≤20u, ray-walk ≤80u, arrow-guided ≤160u). Source-of-truth for topology when available.
- **Excel formulas** → `parse_reporting_xlsx.py`. Produces `excel_formulas.csv`, `excel_intake_meters.csv`, `excel_meters_used.csv`, `excel_comments.md`, `excel_tabs_inventory.md`. Per-term sign and factor are extracted from the raw formula (handles pre-factors like `0.9*XLOOKUP(...)`, post-factors like `XLOOKUP(...)*24*31/1000`, and workbook scalar cells like `$F$5 = 0.001` for kWh→MWh).
- **Excel-derived relations** → `excel_relations.py`. Reads `excel_formulas.csv`, picks one principal inlet per building (role priority VP1→VS1→Å1), emits one candidate edge per `−` term. Produces `excel_relations.csv` and `excel_relations_dropped.csv` (for meters not in the PDF).
- **Snowflake timeseries** → `slice_timeseries.py`. Monthly delta = `last_day.V_LAST − first_day.V_FIRST` (register-difference, capturing full month including final hours). Segmented at inter-day decrements (counter reset / swap). Emits `timeseries_{daily,monthly}.csv` + `timeseries_anomalies.csv`.
- **Meter naming** → `parse_meter_names.py`. Canonicalises raw IDs, catalogs role semantics. Emits `meter_roles.csv`.
- **VLM edge suggestions** (optional) → `vlm_edge_check.py`. Crops the PDF around each orphan meter, asks Claude Opus vision which neighbours are pipe-connected. Emits `vlm_edge_suggestions.csv`. Requires `ANTHROPIC_API_KEY`.

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

**Decision:** adopt the flow-schema topology **only because Excel is silent about B611.VMM72's role** (it's an intra-building meter whose flow is already captured in B611.VMM73's inlet reading). When the PDF places a meter that Excel doesn't reference as a + or − term in any building, the PDF is the only source; use it. This is NOT a case of the PDF overriding Excel — they don't conflict.

**Contrast:** if Excel had B611.VMM72 as a + term for some building and the PDF showed it elsewhere, **Excel would win**. See the 2026-04-19 värme realignment: 16 PDF/naming edges that contradicted Excel accounting were removed in favour of Excel-derived edges (decisions.md "Excel-priority realignment").

**Consequence:** `facit_relations.csv` lists B611.VMM73 → B611.VMM72 and B611.VMM73 → B622.VMM72 as separate edges. The Excel formula is preserved in `05_ontology/meter_allocations.csv` as the accounting rule that governs building attribution.
```

**`open_questions.md` format** — one entry per unresolved issue, same evidence style, but explicitly **no decision yet**. Kept open until resolved; resolution moves it to `decisions.md` with a closing date.

### 04_validation — conservation, cross-source, spot-check

Multiple validation artifacts, all read-only (no reconciliation decisions made here):

**Conservation:** `validate_conservation.py` → `monthly_conservation.csv` + `anomalies.md`. Columns: `parent, month, delta_parent, sum_children_delta, residual, residual_pct, child_count, dead_children, flags`.

Thresholds for flagging (defaults — overridable in `methodology.md`):

- Residual stable across months within ±5 pp of its mean → **losses, expected**.
- Residual stable at 100% → **dead children**.
- Residual shifts >20 pp across adjacent months → **commissioning / swap event**.
- Residual correlates with season → **missing seasonal consumer**.

**Cross-source edge analysis:** `source_conflicts.py` → `source_conflicts.md`. Per-edge agreement/conflict across every topology-bearing extractor in `01_extracted/`. Categories: `confirmed` (≥2 sources same direction), `single_source`, `direction_conflict`. Orphans classified via Excel formula (+input = terminal leaf, −child = missing parent, absent = naming drift). See §11.7 for reconciler reading order.

**Parser regression fixture:** `parse_audit.py` → `parse_audit.md`. Diffs parser output against hand-curated `expected_relations.csv` fixture in `03_reconciliation/`. Reports `parser_missed`, `parser_extra`, `direction_flip`.

**Excel-totals spot check — WHAT IT ACTUALLY TESTS:** `validate_building_totals.py` → `building_totals_spot_check.csv`. For each building-month, evaluates the Excel formula (ΣΣ over + and − terms) by summing Snowflake deltas per meter_id and compares to the Excel cached cell. **This validates meter-ID mapping only.** It does NOT test the ontology topology. A spot-check reporting 0.0–0.5% deltas can coexist with topology-vs-Excel diffs of 1500% (see gtn_varme pre-2026-04-19). **Only months 2026-01 and 2026-02 are valid for comparison** — the Excel file contains fiscal-year 2026 data only, and Snowflake ends at 2026-02-28. Do NOT compare for 2025 months — the Excel has no cached values for those.

**The real topology test** lives in the app's `_excel_comparison_section` (`packages/app/src/app/main.py`): it aggregates `meter_net` per (building, media, month) and compares to `excel_building_totals.csv` directly. Run the app against the assembled site before declaring a workstream done — the spot-check is necessary but not sufficient.

**Audit PNG overlay:** `render_audit_png.py` → `flow_schema_audit.png`. Renders the PDF at 150dpi with parser-inferred edges colour-coded by provenance; orphan meters ringed red.

### 05_ontology — Brick-style deliverable

Matches the Abbey Road schema (`data/sites/abbey_road/*`). Produced by `build_ontology.py` + `generate_outage_patches.py`.

**Key transformations applied by `build_ontology.py`:**

- Virtual building meters (`ANGA_BUILDING`, etc.) are **excluded** — redundant with physical hasSubMeter topology + `meter_measures` table. Excel formulas preserved in `meter_allocations.csv`.
- Relation types classified from `derived_from` + coefficient: `building_virtual_*` → excluded; fractional coefficient → `feeds`; everything else → `hasSubMeter` (NULL coefficient).
- Device swap/offline/glitch events from `meter_swaps.csv` → multi-segment timeseries refs with `valid_from`/`valid_to` + derived `rolling_sum` preferred ref (Abbey Road M6 pattern).

**Key transformations applied by `generate_outage_patches.py`:**

- For offline meters with children: adds `{id}.patch` ref (`aggregation=sum`, sources = children's preferred refs). Stitches into the meter's preferred derived ref.
- If the meter already has a multi-segment derived ref (from glitch handling), the patch is appended to its sources — no double-stitching.
- After patching, the analyst writes curated annotations explaining each event.

**`excel_comparison_annotations.csv` — curated reason + explanation per (building, month):**

After the first full app-validation pass (`SUM(meter_net)` vs cached Excel), the analyst classifies every building-month in this file. `assemble_site.py` merges it into `data/sites/{site}/excel_comparison_annotations.csv`, and the app's Excel-comparison table renders the two extra columns next to each month. Columns:

```
media,building_id,month,excel_kwh,onto_kwh,diff_kwh,reason,explanation
```

`reason` is a short tag; vocabulary is **flexible and short-lived** (pick what fits, invent when warranted). Current in-use tags:

- `match` — within floating-point / day-boundary noise (typical: ≤1 kWh and ≤0.1%)
- `strux_only_meter` — Excel references a meter not in BMS (typically STRUX-read)
- `excel_stale` — Excel formula hasn't been updated to reflect physical reality (e.g. B664/B665)
- `excel_bug` — confirmed Excel formula error (e.g. B612 double-subtraction residual)
- `excel_cooked_coefficient` — round-fraction tenant split without a views.sql primitive (kyla 0.9/0.1, SNV EL 0.5/0.5)
- `meter_outage` — real meter went offline; ontology patched (or gap accepted)
- `ontology_drift` — ontology off by a small amount of unclear cause
- `under_investigation` — known offender, root cause not yet diagnosed

`explanation` is one sentence. This file is **documentation of the state at the last reconciliation**, not an aspirational target — rewrite it when the ontology changes. It supersedes `04_validation/building_totals_spot_check.csv` for per-building, per-month diagnosis.

### 06_assembly — site-level dataset

Produced by `assemble_site.py`. Merges all media workstreams into a single Dataset:

- **Concatenates** per-media tables (meters, relations, sensors, timeseries_refs, annotations)
- **Deduplicates** shared tables (buildings, media_types) by primary key
- **Generates** shared tables not in any workstream (campuses, databases, zones, devices, meter_measures)
- **Extracts readings** from the Snowflake dump, respecting `valid_from`/`valid_to` on timeseries refs
- **Materializes derived refs**: `aggregation=sum` (patch counter from children's deltas), `aggregation=rolling_sum` (stitch segments with counter offset)
- **Copies** `meter_allocations.csv` for the app's Excel comparison view

## 6. Decision-log conventions

- **Date every entry.** `YYYY-MM-DD` prefix in the heading.
- **Cite evidence by path.** Never "the Excel says X"; always "`01_extracted/excel_formulas.csv` row 14 says X."
- **Prefer reopening to rewriting.** If a decision turns out wrong, add a new entry that supersedes it; leave the original in place with a note pointing to the newer one. History matters.
- **Open questions are first-class.** A workstream can ship to `05_ontology` with open questions as long as they're enumerated and their impact is stated.

## 7. Crosswalk — how to build it

Working rules for meter ID reconciliation, per media:

**Shared across all media:**
- Strip trailing `_E` (energy-variant suffix; not a separate meter).
- Normalise `VM##` → `VMM##` on the trailing meter index.

**Ånga + Värme (standard naming):**
- Flow-schema: uniform `B###.{role}_VMM##`.
- Snowflake: `B###.{role}_VMM##_E` or `B###.{role}_VM##`.
- Canonical: `B###.{role}_VMM##`. Exact match after `_E`-strip and `VM`→`VMM`.

**Kyla (non-standard naming):**
- Roles include `KB1`, `KB2` (kyla batt 1/2). Meter IDs are often descriptive: `B654.KB1_KylEffekt_Ack`, `B612-KB1-PKYL`, `B637.KB2_INT_VERK`.
- Dash vs dot separator: Excel uses `B612-KB1-PKYL` (dashes), Snowflake uses `B612.KB1_PKYL` (dot+underscore). Canonicalise first dash to dot, remaining to underscores.
- `_ACK` suffix = accumulator (cumulative energy meter). The non-`_ACK` variant (e.g. `B653.KB2_WVÄRME` vs `B653.KB2_WVÄRME_ACK`) is typically instantaneous power, NOT the same meter.
- System-code tokens in Excel labels (`B821-55-KB2-VMM1` where `55` is the system code) sometimes need stripping to match Snowflake.

**Electricity (transformer naming):**
- EL meters use `B###.T##` / `B###.T##-#-#` (T = transformer station / feeder). No `VMM##` suffix.
- **`-S` suffix convention (GTN)**: Excel references bare transformer IDs (`B611.T1`); Snowflake carries them with a `-S` suffix (`B611.T1-S`). Try `<id>-S` when exact match fails.
- **`-1` summary-suffix convention (SNV)**: Excel references bare trunk (`B209.T21`); Snowflake carries `<id>-1` as the summary feeder (`B209.T21-1`). Verified: BMS `T21-1` = 7287 kWh Jan matches STRUX `T21` = 7294 kWh (0.08%). Analogous role to GTN's `-S`.
- **`_1_1` underscore trunk (SNV)**: Some SNV transformers (e.g. `B334.T87`) use underscore-separated position tuples in Snowflake. The `_1_1` variant is the TRUNK feeder (matches STRUX bare-ID value); other positions (`_2_2`, `_4_1`, etc.) are downstream taps that should NOT be summed into the trunk. Verified: BMS `T87_1_1` = 94528 Jan matches STRUX `T87` = 94561 (0.04%).
- **Dash↔underscore separator drift (SNV)**: Some B3xx sub-feeders use underscore in Snowflake and dash in Excel. `B334.T87-5-2` (Excel) = `B334.T87_5_2` (Snowflake). Covered by the normalized-match step of the fuzzy-match procedure.
- Some Excel transformer IDs have no Snowflake match at all (`B660.H23-1`, `B951.H3-B`) — these are likely provider/utility meters (H-prefix) with manual reads, not on BMS.

**Kallvatten (standard water naming):**
- Meter IDs uniform: `B###.KV1_VM##` (with optional `_V` water-variant suffix). On GTN, 62/63 Excel meters match Snowflake exactly on first try — the cleanest media.
- One `KV1` role per building; `VM21` / `VM22` / `VM23` etc for multiple supply meters (tenant splits).
- `VV1_VM21` appears once on GTN (B611) as an extra tap; treat as regular KV1 meter.

**Kyltornsvatten (V2 / V4 naming):**
- Meter IDs `B###.V2_VM##` or `B###.V2_INT_VERK##`, occasionally `V4` variants.
- Legacy Excel labels use system-code tokens: `B621-52-V2-INT_VERK2`, `B654-55-V2`, `B661-52-V2-MQ43`. These are manually-read meters; they often have no Snowflake data and no STRUX cache value (inactive). Leave them in the crosswalk with `snowflake_id=""` and annotate.

**Fuzzy-matching procedure** (applies to every media; use before declaring a meter Snowflake-absent):

1. **Exact match** `em in sf_ids`.
2. **Normalized match** `re.sub(r'[^A-Za-z0-9]', '', em).lower()` against the same normalisation of every Snowflake ID — catches dash↔dot↔underscore, separator drift, case differences.
3. **Known suffix toggles**: try `em + '_E'`, `em + '_V'`, `em + '-S'` (GTN summary), `em + '-1'` (SNV summary), `em + '_1_1'` (SNV underscore trunk), `em + '-A1'`/`em + '-B1'`, `em[:-2]` (strip trailing `_V` or `_E`).
4. **Known transformations**: `VM`↔`VMM`, dash→dot on first separator, strip `-##-` system code, dash↔underscore separator substitution (SNV B334).
5. **Tail-segment search** within the same building prefix: strip `B###.`, compare normalised tails across all `B###.*` Snowflake IDs.
6. **Building-prefix drift**: scan all Snowflake IDs whose tail matches the Excel meter's tail — catches cases where Excel uses B307 prefix but Snowflake has B339 (etc).
7. **Cross-quantity search**: the same meter might appear under a different QUANTITY column in Snowflake (e.g. `Active Energy Delivered(Mega)` vs `Active Energy Delivered`). Check all quantities if the primary one misses.
8. **Last resort**: manually inspect STRUX catalog (`excel_intake_meters.csv`) to see if the meter is marked `Manuell` (manually read, legacy) — often explains why it's not in Snowflake. Also verify the STRUX monthly values magnitude: if a "trunk" candidate's BMS Jan reading matches STRUX's cached trunk value within ~1%, the candidate is the true trunk.

If all six fail, the meter is genuinely Snowflake-absent. Record with `snowflake_id=""` and evidence. **Never synthesize Snowflake rows from STRUX monthly values** (see memory "feedback_no_snowflake_overwrite").

**Excel formula re-parse caveat:** `parse_reporting_xlsx.py`'s `excel_formulas.csv` records a single `faktor` per row, applied uniformly to all terms. This is wrong for rows where (a) a `$R{n}` cell-reference factor applies only to the first term, or (b) per-term inline coefficients differ (e.g. `0.8×S + 0.9×T − 0.9×U`). Known-buggy on kyla rows 13, 14, 15, 20, 22, 26, 29, 33, 38, 50. **For these rows, re-parse the formula text directly via `openpyxl.ArrayFormula.text` and rebuild per-term coefficients before writing `facit_accounting.csv`.** Simple formulas (`=S+T−U−V−W` all at k=1) parse correctly.

**Building-ID normalisation edge cases:**
- `621 (T)` → `B621` (handled by `_normalize_building_id`)
- `621 (I&L)` → `B621` (same)
- `850/662` → **not** handled by the parser — stays as `B850/662`. After extraction, manually rename in `01_extracted/excel_building_totals.csv` to the chosen canonical (GTN used `B850`).

Build the crosswalk seed by: (a) running the fuzzy-match procedure above; (b) recording per-media normalisations in `crosswalk_notes.md` so they're auditable; (c) leaving truly-absent meters with blank `snowflake_id` and annotating their Excel cache values (often 0 during the comparison window, confirming they're dormant).

## 8. Tooling inventory

All scripts live under `reference/scripts/`. Every one is a standalone CLI with `--help`.

### Extractors (01_extracted)

| script | layer | what it does |
|---|---|---|
| `parse_flow_schema.py` | PDF topology | Three-tier bridging (same-axis, ray-walk, arrow-guided). Arrow-based direction. Source tag from resolved symlink stem. |
| `parse_reporting_xlsx.py` | Excel formulas | Per-term sign+factor via XLOOKUP substitution (handles pre/post factors, `$F$5`-style scalars, workbook `data_only` dual-load). Also extracts cached building-level monthly totals as `excel_building_totals.csv`. |
| `excel_relations.py` | Excel→edges | One principal inlet per building (VP1>VS1>Å1 priority). `_dropped` file for meters absent from PDF. |
| `slice_timeseries.py` | Snowflake BMS | Monthly delta = `last_day.V_LAST − first_day.V_FIRST` (register diff, not per-day sum — that had a 4.2% boundary bias). Segmented at resets. Flags `is_reset=1` on counter reset days. |
| `detect_meter_swaps.py` | Counter resets | Reads `timeseries_daily.csv`, classifies each `is_reset=1` row as `swap` (counter resets, readings resume — device replacement) or `offline` (counter drops to zero, stays dead). Outputs `meter_swaps.csv`. |
| `parse_meter_names.py` | Naming convention | Canonical `VMM##` form, role catalog (VP1 primary, VÅ9 recovery, etc.), `_E` variant flag. |
| `vlm_edge_check.py` | Claude vision | Crops around orphans, asks Opus 4.6 which neighbours connect. Optional; needs `ANTHROPIC_API_KEY`. |

### Reconciliation (03_reconciliation)

| script | what it does |
|---|---|
| `apply_topology_overrides.py` | Merges all extractor sources (PDF + Excel + naming + timeseries) in priority order. Applies human `topology_overrides.csv`. Writes `facit_relations.csv` with per-edge `derived_from` provenance. |
| `generate_building_virtuals.py` | Creates one virtual meter per (building, media) from `facit_accounting.csv`. Adds `+` meter → virtual and virtual → `−` meter relations with coefficients. |

### Validators (04_validation)

| script | what it does |
|---|---|
| `source_conflicts.py` | Per-edge agreement across all extractors. Orphan classification via Excel. |
| `parse_audit.py` | Diffs parser output vs hand-curated `expected_relations.csv` fixture. |
| `validate_conservation.py` | Per-parent-per-month conservation residuals. |
| `validate_accounting.py` | Per-building accounting balance using Excel formula structure. |
| `validate_building_totals.py` | End-to-end: evaluates Excel formulas from Snowflake deltas, compares to Excel's reported building totals. Supports recursive virtual meters + per-term factors. |
| `render_audit_png.py` | PDF → PNG with edge overlay, colour-coded by provenance, orphans ringed red. |

### Ontology + assembly (05_ontology + site)

| script | what it does |
|---|---|
| `build_ontology.py` | Produces Abbey Road-schema CSVs from reconciliation output. Excludes virtual building meters. Handles swap/offline/glitch events as multi-segment timeseries refs. |
| `generate_outage_patches.py` | For offline meters with children: adds children-sum patch ref + stitches into preferred derived ref. Auto-generates annotations. |
| `assemble_site.py` | Merges per-media workstreams into single site Dataset. Extracts readings from Snowflake. Materializes derived refs (sum patches, rolling_sum stitching). Concatenates per-workstream annotations + manual `annotations_manual.csv`. |
| ~~`generate_annotations.py`~~ | **Removed.** Annotations are curated by the analyst, not bulk-generated. Each annotation requires specific evidence and context. |
| `scaffold_workstream.py` | Creates the directory structure for a new media workstream and generates a draft crosswalk from the union of meter IDs found across all extraction sources. |

### Pipeline runner

| script | what it does |
|---|---|
| `regenerate_workstream.py` | Runs extractors → detect_meter_swaps → reconciliation → validators in dependency order. Helper only — does NOT produce the final ontology. The analyst builds `05_ontology/` by hand after reviewing all outputs. |

### Timeseries delta methodology

**Corrected 2026-04-17.** The earlier per-day-sum approach (`Σ (day.v_last − day.v_first)`) systematically under-counted by ~4.2% because each day's `v_first` is the first intra-day reading (not the prior day's closing reading), leaving a small gap between days.

**Current method:** `last_day_of_month.V_LAST − first_day_of_month.V_FIRST`, capturing the full register increment. Segments at any inter-day decrement (counter reset / meter swap); sums per-segment register diffs. **Note on the 0.0–0.5% figure often quoted:** that comes from `validate_building_totals.py`'s spot-check (meter-ID mapping test), not from the real topology-match test. The spot-check validates that Excel's formula, evaluated by summing Snowflake deltas, matches Excel's cached values. It does not prove the ontology aggregates correctly. Use the `meter_net`-per-building comparison in the app for topology validation.

## 9. Execution order

### Per-workstream pipeline (automated via `regenerate_workstream.py`)

```
Phase 1: Extract
  1.1  parse_flow_schema.py         (if PDF exists)
  1.2  parse_reporting_xlsx.py
  1.3  excel_relations.py
  1.4  slice_timeseries.py          (needs crosswalk)
  1.5  detect_meter_swaps.py
  1.6  parse_meter_names.py
  1.7  naming_relations.py

Phase 2: Crosswalk (manual, one-time)
  2.1  Create 02_crosswalk/meter_id_map.csv

Phase 3: Reconcile
  3.1  apply_topology_overrides.py  (merge layers 1-3 + human overrides)
  3.2  timeseries_relations.py      (layer 4: orphan fit)
  3.3  apply_topology_overrides.py  (re-merge with layer 4)
  3.4  generate_building_virtuals.py ← MANDATORY, not optional

Phase 4: Validate
  4.1  source_conflicts.py
  4.2  validate_conservation.py
  4.3  validate_accounting.py       (if facit_accounting exists)
  4.4  render_audit_png.py          (if PDF exists)

Phase 5: Build ontology
  5.1  build_ontology.py

Phase 6: Detect & patch
  6.1  generate_outage_patches.py   (adds children-sum patches + auto-generates annotations)

Phase 7: Manual curation (AFTER build_ontology, NEVER re-run 5.1 after this)
  7.1  Cross-ID device swaps        (e.g. B616.KB1_PKYL → B616.KB1_VMM50_E)
  7.2  False-positive swap/offline fixes (e.g. B661.KB1_Pkyl_Ack noisy startup)
  7.3  Relation type corrections     (e.g. feeds→hasSubMeter for dead pairs)
  7.4  Curated annotations           (05_ontology/annotations.csv)
```

### Site-level assembly (after all media)

```
Phase 7: Assemble
  7.1  assemble_site.py             (merges all media → data/sites/{site}/)

Phase 8: App validation (manual, iterative)
  8.1  Review topology, readings, consumption in Streamlit app
  8.2  Add topology_overrides.csv for corrections
  8.3  Add manual annotations for findings
  8.4  Re-run from phase 3

Phase 9: Excel comparison (CACHED VALUES ONLY)
  9.1  App's Excel comparison uses actual cached building totals from the
       Excel file (excel_building_totals.csv), NOT formula-reconstruction
       from Snowflake data. The Excel file only contains fiscal-year data
       for 2026 (columns 2026-01 through 2026-12). Snowflake timeseries
       ends at 2026-02-28. Therefore the ONLY months where a real
       comparison is possible are 2026-01 and 2026-02. Any comparison
       for earlier months (2025-xx) is meaningless — the Excel has no
       cached values for those months.
```

### Sequencing across media

1. **GTN ånga** — done ✓ (template workstream, all patterns validated)
2. **GTN värme** — has PDF, next priority
3. **GTN kyla** — no PDF, has fractional coefficients
4. **GTN el** — no PDF, has unit conversion (0.001)
5. **Site assembly** — after all 4 GTN media reach phase 6
6. **SNV workstreams** — same pipeline, different site

## 10. Known risks / open questions (to track project-wide)

### Still open

- Excel files may encode per-tenant allocations via merged cells and formatting — these are hard to extract mechanically; manual transcription into `excel_comments.md` may be necessary for cases the extractor misses.
- Boiler-side / plant-side meters (e.g. `B325.Panna2/3_MWH` in SNV) sit *upstream* of the flow schema's entry point and will never appear in the PDF parser output. Decide per-workstream whether to represent them as an implicit parent above the schema root, or as a separate upstream node in `05_ontology`.
- Virtual accounting meters (B611 Excel case) may have non-unit coefficients. Flow schema is pure topology (coeff = 1.0); Excel carries the coefficients. Reconciliation step must layer the coefficient onto the topology edge without pretending the coefficient is physical.
- Flow-schema PDFs are dated 2025-02-26. Pre-Feb-2025 timeseries may reflect an older topology; flag any per-month residual shifts crossing that date specifically.
- The conservation threshold defaults (5pp stable, 20pp shift) are guesses. Expect to tune them per-media once we've seen 2–3 workstreams.
- Flow-schema parser fails silently if a meter's ⊗ glyph is drawn *on top of* a continuous pipe (no gap) — the meter becomes a dead-end stub on the adjacent tap. See the `B611.VMM72` case in GTN ånga. The preview HTML is the defence; eyeball it for every workstream.

### Discovered in validation (2026-04-17)

- **"Excel=0 but meter live" pattern** — detected across 3 of 4 media: B616 steam (~900 MWh/month genuinely unallocated), B658 kyla (~12 MWh/month misattributed to B600-KB2), B665.T42-2-1 el (~5 MWh/month misattributed to building 665). B616 is the only case where consumption is completely absent from the per-building rollup; the other two are misattributions where the campus total is correct. Root cause: Excel's STRUX_data table has stale or zero values for these meters while Snowflake reads real consumption. The automated spot check (`validate_building_totals.py`) catches these on every run.
- **EL main-transformer naming: `-S` suffix convention.** Excel references bare transformer IDs (`B611.T1`); Snowflake carries them with a `-S` suffix (`B611.T1-S`, presumably "Sum/Summary"). The crosswalk builder must try `<excel_id>-S` when an exact match fails. Discovered on gtn_el; likely campus-wide for all EL meters.
- **Excel formula per-term factors are media-specific.** Ånga/värme formulas mostly use unit coefficients. Kyla has `0.8×XLOOKUP(...)`, `0.9×XLOOKUP(...)`, and even post-factors like `XLOOKUP(...)*24*31/1000` (power-to-energy conversion). EL wraps every formula in `$F$5*(...)` where F5 = 0.001 (kWh→MWh). `parse_reporting_xlsx.py` handles all of these via an XLOOKUP-substitution approach that evaluates the formula with each term set to 1.
- **Dead-meter cascades in kyla virtual meters.** `B653.KB2_WVÄRME_ACK` stopped emitting Oct 2025. Because kyla's accounting uses virtual meters (`B600-KB2`, `Prod-600`) that sum physical meters, one dead leaf blocks an entire subtree — B611, B613, B621, B622 all depend on B600-KB2 which needs B653.ACK. Documented in `gtn_kyla/03_reconciliation/open_questions.md`.

### Discovered in app validation (2026-04-18, gtn_anga)

- **B600N/B600S are parallel intakes, not series.** `naming_index_chain` wrongly inferred B600N→B600S. Conservation check confirmed: B600S flow (103 kWh/d) exceeds B600N (63 kWh/d). Fixed via `topology_overrides.csv` removal. Both are root meters.
- **B642.VMM72 exceeds parent B614.VMM71 by 2-7x** during Jan and Apr-Jun. PDF confirms downstream relationship. Suspected undocumented additional steam feed bypassing B614. Edge kept (PDF authoritative); annotated as `unknown` for on-site investigation.
- **B600S counter froze Jan 17, hard reset Feb 2.** Frozen counter detection catches the freeze; outage patched from 9 children's readings via `sum` aggregation.
- **B642.VMM72 counter glitch Mar 15-18.** Counter dropped from 25231 to 10890, reverted after 3 days. Excluded via validity split (A+B segments around the glitch).
- **B600N north spine has 60% unmetered flow.** Only 40% of B600N intake captured by downstream meters. The other 60% goes to buildings without steam meters (B602, B603, B604, B631, etc. — all listed in Excel with 0 consumption).
- **31% of total site steam intake unaccounted** by downstream building meters. South spine 14% (acceptable pipe losses). North spine 60% (missing meters). This is consistent with the Excel data — Excel's B600 row also shows the gap implicitly.

### Resolved

- **4.2% timeseries methodology bias** — `slice_timeseries.py` was summing per-day `v_last − v_first`, losing the boundary between days. Fixed 2026-04-17 to use `last_day.V_LAST − first_day.V_FIRST` register-difference method. All four GTN media now match Excel within 0.0–0.5% per building.

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

Every row in `facit_relations.csv` (and `05_ontology/meter_relations.csv`) carries a `derived_from` tag. The tag vocabulary:

**Layer 1 — PDF flow schema:**
- `flow_schema_V###-XX.X-NNN` — parser produced this edge from the pipe graph
- `flow_schema_V###-XX.X-NNN/arrow` — direction independently confirmed by a detected arrow
- `flow_schema_V###-XX.X-NNN/auto_root_degree` — direction picked by degree heuristic (lower confidence)

**Layer 2 — Excel formulas:**
- `excel_formula_B###` — edge derived from building ###'s accounting formula (a `−` term is a child of the principal `+` inlet)

**Layer 3 — Naming convention:**
- `naming_role_hierarchy` — edge derived from intra-building role rules (VP1→VÅ9, VP1→VS1, etc.)
- `naming_index_chain` — edge derived from consecutive VMM index (VMM61→VMM62 in same building/role)

**Layer 4 — Timeseries residual fit:**
- `timeseries_residual_fit` — orphan meter's monthly pattern reduces an existing parent's conservation residual; includes fit statistic (improvement %)

**Manual / VLM:**
- `topology_override_{YYYY-MM-DD}_{author}` — manually added/corrected; reason must be cited
- `vlm_edge_check_{YYYY-MM-DD}` — Claude vision identified the connection from a PDF crop

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

### 11.7 Multi-source topology reconciliation — layer separation

Topology isn't extracted from a single source; it's *reconciled* across four, each with a different authority scope (§3). This section encodes the rule tools must follow so the reconciliation work stays auditable.

**Rule of thumb:** every tool is either an **extractor** (writes into `01_extracted/`) or a **validator** (writes into `04_validation/`). Only **`apply_topology_overrides.py`** writes into `03_reconciliation/`, and only by applying a *human-authored* `topology_overrides.csv` to the parser's output. Nothing else writes a decision silently.

| layer | source | extractor | artifact(s) | authority | emits edges? |
|---|---|---|---|---|---|
| 1 | Flödesschema PDF | `parse_flow_schema.py` | `flow_schema_{meters,relations}.csv`, `flow_schema_preview.html` | **physical topology** (primary) | Yes |
| 2 | Excel monthly-reporting | `parse_reporting_xlsx.py` + `excel_relations.py` | `excel_formulas.csv`, `excel_intake_meters.csv`, `excel_relations.csv` | accounting, coefficients | Yes |
| 3 | Meter naming convention | `naming_relations.py` | `naming_relations.csv` | intra-building role hierarchy + index chains | **Yes (new)** |
| 4 | Snowflake BMS timeseries | `slice_timeseries.py` + `timeseries_relations.py` | `timeseries_{daily,monthly}.csv`, `timeseries_relations.csv` | consumption magnitudes; conservation-residual fit | **Yes (new)** |

Layer 4 **depends on layers 1–3**: it needs their edges already merged to compute meaningful conservation residuals. If it ran first, it would rediscover what naming already found. The dependency order is encoded in `regenerate_workstream.py`.

Optional augmentations:

- `vlm_edge_check.py` → `01_extracted/vlm_edge_suggestions.csv` — Claude vision crops for PDF-orphaned meters.
- `parse_meter_names.py` → `01_extracted/meter_roles.csv` — canonical IDs and role catalog (input to `naming_relations.py`).

**Pipeline dependency order:**

```
00_inputs/          (raw sources, read-only)
       │
       ▼
01_extracted/  — independent extractors, no cross-talk:
   ├─ flow_schema_relations.csv      ← layer 1: PDF parser
   ├─ excel_relations.csv            ← layer 2: Excel formulas
   ├─ meter_roles.csv                ← parse_meter_names.py (input to layer 3)
   ├─ naming_relations.csv           ← layer 3: role hierarchy + index chain
   ├─ timeseries_monthly.csv         ← slice_timeseries.py (input to layer 4)
   └─ vlm_edge_suggestions.csv       ← optional VLM
       │
       ▼
03_reconciliation/  — merge layers 1–3 (apply_topology_overrides.py):
   └─ facit_relations.csv            ← union of {PDF, Excel, naming} + human overrides
       │
       ▼
01_extracted/  — layer 4 runs AFTER merge:
   └─ timeseries_relations.csv       ← layer 4: orphan residual fit against merged facit
       │
       ▼
03_reconciliation/  — re-merge with layer 4 additions:
   └─ facit_relations.csv            ← final (all 4 layers + overrides)
       │
       ▼
04_validation/      (comparison, no decisions)
   ├─ source_conflicts.md            ← cross-source agreement
   ├─ building_totals_spot_check.csv ← end-to-end check vs Excel totals
   ├─ monthly_conservation.csv       ← parent-child energy balance
   └─ flow_schema_audit.png          ← visual overlay
       │
       ▼
05_ontology/        (Brick-style deliverable)
```

**Provenance flows end-to-end.** Every edge in `facit_relations.csv` carries `derived_from` (see §11.4). `build_ontology.py` copies this tag into `05_ontology/meter_relations.csv` so downstream consumers can filter by confidence.

**apply_topology_overrides.py** merges sources in priority order with **reverse-direction conflict detection**:
1. Start with `flow_schema_relations.csv` (if PDF exists) OR `excel_relations.csv` (for PDF-less media).
2. Merge `naming_relations.csv` — add edges not already present. If a naming edge `A→B` conflicts with an existing edge `B→A` from a higher-priority layer, the naming edge is **dropped** and logged to stderr. Higher-priority layers always win on direction.
3. Apply human `topology_overrides.csv` (add/remove/force_direction).
4. Merge `timeseries_relations.csv` — same reverse-direction check as step 2.
5. Write `facit_relations.csv` with the union, each edge tagged by its source.

**Conflict rules** enforced during merge (both logged to stderr):

1. **Reverse-direction:** if edge `(A→B)` is proposed but `(B→A)` already exists from a higher-priority layer, the new edge is rejected. Prevents cycles.
2. **Duplicate parent:** if edge `(P→C)` is proposed but child `C` already has a parent from a higher-priority layer, the new edge is rejected. The physical meter topology is a tree — each meter has at most one `hasSubMeter` parent.

To override either rule, use `force_direction` / `add` + `remove` in `topology_overrides.csv`.

**source_conflicts.py** checks all 5 sources (flow_schema, excel, naming, timeseries, vlm) for direction disagreements and reports them in `04_validation/source_conflicts.md`. Any `direction_conflict` count > 0 signals edges that `apply_topology_overrides.py` will have silently dropped from the lower-priority layer.

**generate_building_virtuals.py** materializes building-level virtual meters in `03_reconciliation/`:

Each Excel building row is an implicit virtual meter (e.g. `B611_VARME = VP1 + VÅ9 + VP2 − B613 − B631 − B622`). This script creates:
1. A virtual meter entity `B{N}.{MEDIA}_BUILDING` in `facit_meters.csv` (`meter_type=virtual`).
2. Relations: each `+` term → virtual (input, with coefficient); virtual → each `−` term (pass-through, with coefficient).
3. Tag: `derived_from = building_virtual_B{N}`.

**Important:** `build_ontology.py` **excludes** virtual building meters and their edges from `05_ontology/`. They are redundant with the physical `hasSubMeter` topology + `meter_measures` table, and their cross-building feeds edges (e.g. `B612.ANGA_BUILDING → B613.VMM71`) conflict with the calc engine's semantics. The accounting formulas they encode are preserved separately in `05_ontology/meter_allocations.csv` for documentation and auditing. Building-level consumption is computed topologically via `meter_measures` → `meter_net` → `consumption.sql`.

**Naming-relation rules** (`naming_relations.py`):

For each building with ≥2 meters on the same media, the script proposes role-hierarchy edges:

| rule | condition | edge | provenance tag |
|---|---|---|---|
| Supply feeds secondary | VP1 + VS1 in same building | VP1 → VS1 | `naming_role_hierarchy` |
| Supply feeds recovery | VP1 + VÅ9 in same building | VP1 → VÅ9 | `naming_role_hierarchy` |
| Index chain | VMM61 + VMM62 same building + role | VMM61 → VMM62 | `naming_index_chain` |

**These rules produce frequent false positives** and must be verified against Excel before accepting. Observed failure modes:

- Excel often treats VS1 and VÅ9 meters as **independent + terms** for the same building, not as downstream of VP1. Examples (gtn_varme 2026-04-19): B614, B616, B625, B643 all had VP1→VÅ9 naming edges that contradicted Excel's "VÅ9 is a + term" treatment. Added naming edges produced net-cancellation in the best case and wrong attribution in the worst.
- Index chains break when the mid-meter has no BMS readings. Example: `B631.VP1_VMM61 → B631.VP1_VMM62` naming chain meant B611's intended subtraction of B631.VMM62 didn't happen because VMM61 had no data to propagate the subtraction through. Fix: direct edge from the real parent (B611.VP1_VMM61 → B631.VP1_VMM62).
- Meters outside any Excel formula (pure PDF artifacts attributed to a building by naming) add uncounted consumption to that building. Reattribute to campus.

Rule of thumb: propose naming edges, then **diff against Excel formulas before keeping any of them**. Drop every edge that contradicts Excel's + / − structure.

**Timeseries-relation rules** (`timeseries_relations.py`):

For each orphan meter (not in facit after layers 1–3), test:

```
for each parent P in facit with children {C1, C2, ...}:
    if building(P) ≠ building(orphan): skip          ← same-building only
    residual = P.delta − Σ Ci.delta  (per month)
    new_residual = residual − orphan.delta  (per month)
    if Σ|new_residual| < Σ|residual| × (1 − threshold):  ← default 20%
        → candidate edge P → orphan, provenance = timeseries_residual_fit
```

Same-building filter eliminates seasonal-correlation noise. The 20% threshold avoids weak fits. **These are candidate edges, not facts** — verify each against Excel before keeping. Example failure: `B613.VP1_VMM61 → B613.VP2_VMM61` (fit improvement 71%) contradicted Excel which treats both as independent + terms for B613. The residual-fit metric captures any correlation — including two independent + terms of the same building — and will happily propose edges that break building attribution.

### 11.8 Device swap, offline, and glitch handling

Counter resets in BMS data are detected by `slice_timeseries.py` (flags `is_reset=1`) and classified by `detect_meter_swaps.py` into:

| event | meaning | ontology encoding |
|---|---|---|
| `swap` | Device replaced, counter resets, readings resume | Two raw refs (.A, .B) with `valid_to`/`valid_from` at swap date + one derived `rolling_sum` ref (preferred). Same pattern as Abbey Road M6. |
| `offline` | Meter decommissioned, counter drops to zero or freezes permanently | Single raw ref with `valid_to` at the offline date. Frozen counter (delta=0 at end of data window) is also detected. |
| `glitch` | Counter drops significantly then reverts within a few days | Two raw refs (.A, .B) split around the glitch period + derived `rolling_sum` (preferred). Bad readings excluded by validity windows. |

A meter can have multiple events (e.g., glitch in March + offline in July). `build_ontology.py` processes events chronologically, creating one segment per gap-free period. Each segment becomes a raw ref with `valid_from`/`valid_to`. The preferred derived ref stitches all segments via `rolling_sum`.

`assemble_site.py` materializes the stitched readings: when switching segments, the offset = previous segment's last stitched value, and the anchor = new segment's first raw value. Only deltas carry over — the new device's absolute counter value is subtracted so the stitched series is smooth at the boundary.

### 11.9 Outage patching from children

When a meter goes offline but its children keep reporting, the gap can be filled with a derived timeseries that sums the children's deltas.

`generate_outage_patches.py` creates:
1. `{id}.patch` — `kind=derived`, `aggregation=sum`, `sources=child1|child2|...`, `valid_from=outage_date`
2. Updates the preferred derived ref's sources to include the patch segment

**Before patching, verify the raw Snowflake data is actually bad.** A counter reset followed by resumption of normal readings is almost always a **device swap** — the correct encoding is a rolling_sum of multiple raw segments (A, B, C, …) with validity windows, not a children-sum patch. Patching in that case silently masks valid data. Example: B642.Å1_VMM72 had a reset 2025-07-31 (Δ=-31533) but continued monotonic readings afterward; an earlier VMM71-derived patch was replacing the good post-swap data with a proxy, producing a −35 MWh B642 / +35 MWh B614 mirror error in the app. Resolved 2026-04-19 by replacing the patch with a `:d.C` raw segment + rolling_sum A|B|C.

**Patch sources must match Excel's accounting structure.** If the offline parent is attributed to building X, the patch sources should be children that Excel treats as subordinated to that parent. Including siblings or cross-accounted meters in the patch will leak their consumption into X's total. Example: B833.VP1_VMM61 outage patch originally included VÅ9_VMM41 as a source. VÅ9 isn't in Excel's B833 formula, so post-outage VP1 patched up with VÅ9's consumption and inflated B833 by ~61 MWh/month. Fixed by dropping VÅ9 from the patch sources.

The patch is honest when applied correctly: it says "we estimated this meter's readings from what we can see downstream." It's a lower bound (doesn't capture distribution losses). The original raw readings and the outage gap are preserved — source data is never modified.

For leaf meters (no children), no patch is possible. The outage is left as a gap with an annotation.

`assemble_site.py` materializes the patch: for each day from `valid_from` onwards, the patch counter = cumulative sum of children's daily deltas.

### 11.10 Annotations

Structured notes attached to entities (meters, buildings, campus) with date ranges. Stored as `annotations.csv` in `05_ontology/` and merged into the site dataset.

| field | type | description |
|---|---|---|
| `annotation_id` | string | unique ID (e.g., `B616_swap`) |
| `target_kind` | string | `meter`, `building`, `campus`, `timeseries` |
| `target_id` | string | the entity's primary key |
| `category` | string | `outage`, `swap`, `calibration`, `data_quality`, `patch`, `unknown` |
| `valid_from` | date | start of the annotated period (null = non-temporal) |
| `valid_to` | date | end (null = ongoing) |
| `description` | string | human-readable explanation |
| `related_refs` | pipe-joined list | timeseries_ids of patches/derived refs created as remediation |

**Every annotation is curated by the analyst.** Each annotation must include specific evidence: which meter, what happened, when, what the data shows, and what was done about it (e.g., patch created, readings excluded). Generic bulk-generated annotations ("swap detected on X") are worthless — they don't explain what happened or what it means.

The `detect_meter_swaps.py` and `validate_conservation.py` scripts flag CANDIDATES. The analyst reviews each one, writes a proper annotation with context, or dismisses it with a note in `decisions.md`.

**Manual annotations** added during app validation:
- Data quality findings, undocumented feeds, unmetered buildings, etc.

The app surfaces annotations as selectable highlights on the Readings and Consumption charts — dashed vertical lines at start/end dates, with category-colored labels and description tooltips. The "Isolate" toggle filters the charts to only show the annotation's target meters/buildings.

**What tools must NOT do:**

- No tool writes directly into `03_reconciliation/` except `apply_topology_overrides.py`.
- No tool "auto-promotes" a suggestion. Each layer writes its own extractor CSV; the merge script unions them with provenance preserved.
- No tool seeds `expected_relations.csv` from parser output.

**What `source_conflicts.md` is for (the reconciler's reading order):**

1. **Direction conflicts** — always need a decision; PDF arrow or Excel sign settles it.
2. **Confirmed** edges (≥2 sources agree) — high-confidence; no action needed.
3. **Single-source edges** by layer, weighted by §3 authority.
4. **Orphans** by Excel classification (terminal leaf / missing parent / absent).

Every non-trivial call goes into `decisions.md` with evidence citations (file + row/cell).

---

## 12. Cross-references

- All scripts: `reference/scripts/` (see §8 for inventory)
- Pipeline runner: `reference/scripts/regenerate_workstream.py` — per-(site, media) config; `python regenerate_workstream.py reference/media_workstreams/gtn_varme`
- Site assembly: `reference/scripts/assemble_site.py` — merges all media workstreams into `data/sites/gartuna/`
- STRUX-only reading injection (handle with care, not a default): `reference/scripts/inject_strux_readings.py` — see §0's "Fuzzy-match" rule before using
- Flow-schema parsing notes: `reference/monthly_reporting_documents/logs/topology/flow_schema_parsing_notes.md`
- GTN ånga ontology: `reference/media_workstreams/gtn_anga/05_ontology/meter_relations.csv` (5 hasSubMeter edges, 46/48 match)
- GTN värme ontology: `reference/media_workstreams/gtn_varme/05_ontology/meter_relations.csv` (29 hasSubMeter edges, 95/96 match)
- GTN kyla ontology: `reference/media_workstreams/gtn_kyla/05_ontology/meter_relations.csv` (6 hasSubMeter + 14 feeds, 90/98 match, 10 virtual meters)
- GTN el ontology: `reference/media_workstreams/gtn_el/05_ontology/meter_relations.csv` (10 edges, 33/100 match — STRUX-only cascade limits)
- GTN kallvatten ontology: `reference/media_workstreams/gtn_kallvatten/05_ontology/meter_relations.csv` (11 hasSubMeter edges, 98/98 match)
- GTN kyltornsvatten ontology: `reference/media_workstreams/gtn_kyltornsvatten/05_ontology/meter_relations.csv` (0 edges, 90/90 match)
- Assembled site: `data/sites/gartuna/` — loaded by `ontology.load_dataset()`. The app's `_excel_comparison_section` (`packages/app/src/app/main.py`) shows the canonical topology-vs-Excel comparison per media (cached values, not formula reconstruction).
- Abbey Road template (ontology shape): `data/reference_site/abbey_road/*.csv`
- Snowflake export: `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv` — daily-aggregated all meters, date range 2025-01-01 → 2026-02-28 (updated 2026-04-17). Query documented in `gtn_anga/00_inputs/README.md`.
- Building-totals spot-check results (**meter-ID mapping test only, not topology**): `{workstream}/04_validation/building_totals_spot_check.csv`
- Source-conflicts advisory: `{workstream}/04_validation/source_conflicts.md`
