# Reconciliation decisions — gtn_varme

---

### 2026-04-16 — Värme has no physical meter→meter topology (SUPERSEDED 2026-04-16 by the arrow-aware re-parse; kept for history)

**Original claim:** "V600-56.8 has 0 meter→meter edges; all substations are isolated." That was wrong — it was an artifact of running BFS from a single declared source in a many-component graph. The parser correctly built the graph, but BFS from one source couldn't enumerate the other 32 components.

**Superseded by:** `Värme has partial meter→meter topology` below.

---

### 2026-04-16 — Parser improvements: same-axis pair preference + VVX gap bridging + override mechanism (supersedes earlier "21 edges" count)

After finding that parser quality was incomplete (many B611/B612/B616/B674-style substations had their meters split across components wrongly), three improvements were made to `parse_flow_schema.py`:

1. **Same-axis pair preference** — when a meter label has multiple candidate flank pairs, prefer pairs where the two endpoints share an x or y (within 0.5 units, below the 2u snap grid). This fixes the VVX-interior false positive where two diagonally-close rectangle corners (`(498,1288) + (508,1290)`, gap 10.2, dy=2) were being misread as an inline meter gap instead of the real collinear pair (`(524,1318) + (524,1332)`, gap 14). Affected several värme meters; now corrected.
2. **Pipe-gap bridging (up to 20u)** — pipe endpoints within 20u on the same axis are bridged to jump simple VVX/valve/pump symbols whose internal structure my axis-aligned filter drops. 37 bridges added on V600-56.
3. **Per-workstream overrides** (`reference/scripts/apply_topology_overrides.py`): `03_reconciliation/topology_overrides.csv` can carry manual `add` / `remove` / `force_direction` rows. Applied after the parser runs; audit trail in `overrides_audit.md`. No overrides currently defined.

**Current result:** **26 `feeds` edges** (up from 21 in the initial pass, and corrected in composition vs the 27 pre-fix run that had the VVX false positives). 22 `explicit`, 3 `auto_root_degree`, 1 independently `arrow`-confirmed. The general plan for further parser improvements (closed-shape detection, arrow-guided long-span bridging, expected-relations fixture per PDF) is persisted in `docs_to_bric_parsing.md` §11.

---

### 2026-04-16 — Värme has partial meter→meter topology (21 edges)

**Question:** After fixing the parser to enumerate all connected components and to use arrow-direction extraction, what topology does the flödesschema actually encode?

**Evidence:**
- `01_extracted/flow_schema_relations.csv` — **21 `feeds` edges** across 12 multi-meter substations; all marked `explicit` (driven by Excel-derived sources); 6 independently arrow-confirmed.
- Connected-component enumeration on V600-56.8 finds 33 components that contain meters — 25 with exactly one meter (isolated single-meter substations, no edges to produce), and 8 with two or more meters (encoding real physical flow).
- Components with ≥2 meters (meter counts in parens):
  - `{B611.VP1, B611.VÅ9_41, B613.VP1_VMM61, B631.VP1_VMM61, B631.VP1_VMM63}` (5)
  - `{B612.VP2_VMM61/62/63, B641.VP2_VMM61}` (4)
  - `{B621.VP1, B622.VP1, B623.VP1, B658.VP1}` (4)
  - `{B613.VP1_VMM62, B637.VP2, B638.VP2, B654.VP2}` (4)
  - `{B833.VP1_VMM61/62, B833.VÅ9_VMM41, B834.VP1}` (4)
  - `{B614.VS1, B615.VS1, B642.VS1}` (3)
  - `{B643.VP1, B643.VP2, B643.VÅ9_VMM42}` (3)
  - `{B650.VP1, B655.VP1}` (2)
- Every multi-meter component aligns with an Excel row whose subtractive terms are the other meters in the component, confirming the topology matches the accounting's implicit view.

**Decision:** `facit_relations.csv` now carries 21 `feeds` edges. Source meters are derived from the Excel Värme sheet's column-S (primary ADD per building) and passed as `--sources` to the parser. 6 edges get independent confirmation from filled-triangle flow arrows in the drawing; 15 inherit direction from the Excel-declared source without arrow confirmation but the Excel primary-ADD is well-supported by domain convention.

**Consequence:**
1. Conservation checks now meaningfully run on 12 parent meters; `04_validation/monthly_conservation.csv` has real data.
2. The 25 single-meter components remain topologically flat (still valid — those substations are standalone).
3. The 8 Excel-only meters without schema pipes stay in `facit_meters.csv` with no `feeds` edges; they'll inherit building attribution only.

---

### 2026-04-16 — Excel is authoritative for allocation, flow schema for meter inventory and topology

**Question:** In the absence of flow-schema topology edges, which source is the "topology facit" for värme?

**Evidence:**
- Flow schema: authoritative for **which meters exist** (57 labels, 54 unique after dedup). Does not encode flow direction or inter-meter links.
- Excel Värme sheet: authoritative for **per-building allocation formulas**. Every building row has an XLOOKUP-based formula summing specific meters with `+` / `−` signs (e.g., building 611 = `+VP1_VMM61 +VÅ9_VMM41 +VP2_VMM61 −B613.VP1_VMM61 −B631.VP1_VMM62 −B631.VP1_VMM63 −B622.VP2_VMM61`).
- The formulas use variable lengths (4–8 terms) and mixed sign patterns — not the rigid `S+T−U−V−W` seen in ånga. My `parse_reporting_xlsx.py` was updated to parse formula text and extract signs dynamically.

**Decision:** split the "topology" concept into two artifacts:
- `facit_meters.csv` — the meter inventory (from flow schema + Excel union, 61 meters total).
- `facit_accounting.csv` — the Excel allocation formulas, lifted verbatim with both excel IDs and facit IDs side-by-side. Each row is `(building, column, sign, role, excel_meter_id, facit_meter_id, n_terms)`.
- `facit_relations.csv` — kept as a first-class artifact but empty for this workstream, with a header only. If a later discovery reveals a physical inter-building link, it goes here.

**Consequence:** the ontology (`05_ontology/`) for värme will carry a flat meter list with per-building `hasAllocationRule` references pointing at the accounting formula, rather than a `feeds` edge tree.

---

### 2026-04-16 — Meters drawn on schema but silent in BMS are flagged, not ignored

**Question:** 8 meter labels appear on V600-56.8 but have no data in Snowflake and aren't in any Excel formula. Include them in the facit or drop them?

**Evidence:** `02_crosswalk/crosswalk_notes.md` — the 8 are: B613.VP1_VMM62, B616.VS1_VMM61, B621.VÅ9_VMM41, B631.VP1_VMM61, B661.VS1_VMM61, B674.VÅ9_VMM41, B674.VÅ9_VMM42, B821.VS1_VMM61.

**Decision:** include them in `facit_meters.csv` with `meter_type = real` (the flow schema asserts they exist physically) but flag them in `open_questions.md` for operations follow-up. Do not silently drop; that would hide a data-quality issue.

**Consequence:** the conservation check will show them as zero-activity and the ontology will carry them with a `provenance = drawing_only` annotation.

---

### 2026-04-16 — 7 Excel-only meters added to the facit

**Question:** 7 meter IDs appear in Excel formulas but aren't on the flow schema. All 7 emit in Snowflake. Add them to the facit?

**Evidence:** `02_crosswalk/crosswalk_notes.md`. The 7 are: B612.VP2_VMM64, B612.VP2_VMM65, B613.VP2_VMM61, B616.VP1_VMM61, B631.VP1_VMM62, B661.VP1_VMM61, B821.VP1_VMM61.

**Decision:** add to `facit_meters.csv` with `meter_type = real`. Two candidate reasons for their absence on the drawing: (a) they were commissioned after 2025-02-26 (the flow-schema draft date), (b) drafting omission. Either way, live data and Excel treatment confirm they exist. Note this in `open_questions.md` so the next version of the flow-schema PDF is checked for them.

---

### 2026-04-16 — Naming normalisation rules match gtn_anga

Same `VMM↔VM, ±_E` rule used to resolve facit IDs against Snowflake and STRUX. Full mapping in `02_crosswalk/meter_id_map.csv`. 53 of 61 facit meters resolve to Snowflake; the 8 that don't are the drawing-only cohort above.

---

### 2026-04-16 — System-wide reset on 2025-01-08 / 2025-01-09

**Observation:** `01_extracted/timeseries_anomalies.csv` flags **43 of 53** värme meters with a single `reset_day` on either 2025-01-08 or 2025-01-09, with large negative daily deltas (some over 90 000 MWh). This is not a per-meter swap — it's a system-wide event.

**Decision:** treat this as a BMS / counter baseline reset and let the existing slicer logic (clamp negative to 0, segment delta) handle it. The conservation and per-building checks run over Jan 10..Dec 31 of 2025 won't be affected; only Jan 1..Jan 8 of 2025 is unreliable.

**Consequence:** residuals before vs. after Jan 9 are not comparable. If we ever want pre-2025 data, it will need a separate export and reconciliation. Record the event date clearly in the validation notes.

**Open:** we don't know *why* the reset happened (firmware update? data migration? year-start accumulator reset?). See `open_questions.md`.
