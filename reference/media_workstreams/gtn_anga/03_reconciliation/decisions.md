# Reconciliation decisions — gtn_anga

Every merge decision with evidence and date. Entries stay in chronological order; if a decision is superseded later, keep the original and add a newer entry that links back.

---

### 2026-04-16 — Parser is now arrow-aware + multi-component; ånga output unchanged

Late 2026-04-16, `parse_flow_schema.py` was refactored to:
1. Enumerate connected components instead of running BFS from declared sources only.
2. Extract filled-triangle flow-direction arrows from the PDF (`<` / `>` / `^` / `v` chevrons) and use them to auto-detect sources and validate direction per pipe segment.

Ånga has 7 arrows on the V600-52.E.8 drawing, all consistent with the declared `--sources=B600S.Å1_VMM71,B600N.Å1_VMM71`. Re-running the refactored parser against ånga produced the **same 19 edges** as before; all are tagged `explicit` because the declared sources win over arrow auto-detection when both would apply to the same component. This confirms the prior ånga topology is arrow-consistent.

No changes to `facit_relations.csv`; only adding this note for traceability.

---

### 2026-04-16 — Flow schema is facit for topology

**Question:** When the flow-schema PDF disagrees with the Excel accounting formula about parent/child relationships, which wins?

**Sources:**
- `01_extracted/flow_schema_relations.csv` (19 edges, all coefficient 1.0)
- `01_extracted/excel_formulas.csv` (23 meter refs across 15 building rows on the Ånga sheet)
- `docs_to_bric_parsing.md` §3 defines this authority rule.

**Decision:** `facit_relations.csv` is copied from `01_extracted/flow_schema_relations.csv`. The Excel formulas are preserved in `01_extracted/excel_formulas.csv` for later use as *accounting-allocation* rules, not as topology edges.

**Consequence:** the ontology will carry two separate relationship types — a physical `feeds` edge from the flow schema, and an accounting allocation encoded later in `05_ontology/` using the Excel S+T−U−V−W formula pattern. Neither overwrites the other.

---

### 2026-04-16 — B611.VMM72 is a dead-end side-tap, not an inline meter

**Question:** Earlier hand analysis placed `B611.VMM72` inline on the main vertical at x=1476, implying the chain `B611.VMM73 → B611.VMM72 → B622.VMM72`. Flow schema parser placed it as a dead-end side-tap off an east horizontal stub, making `B611.VMM72` and `B622.VMM72` *siblings* both fed from `B611.VMM73`. Which is right?

**Sources:**
- `01_extracted/flow_schema_preview.html` — showed `B611.VMM72`'s ⊗ glyph at x=1524 on the east tap, not on the x=1476 main vertical.
- Pipe geometry from `parse_flow_schema.py`: the vertical `V(1476.8, 894) → (1476.8, 621)` is **one continuous segment** with no gap at y=772 (where `B611.VMM72` would sit if inline). A continuous vertical cannot host an inline meter.
- Diagonal path strokes at (1524, 772) form the ⊗ X-mark — that's where the meter symbol actually is.
- Excel formula for B611 (`01_extracted/excel_formulas.csv`): `+B611.VM71 +B611.VM73 −B622.VM72`. It does *not* mention `B611.VM72` or `VMM72`, consistent with `B611.VMM72` being an intra-building meter whose reading is already subsumed in `B611.VM73`'s inlet measurement.

**Decision:** adopt the flow-schema topology. `facit_relations.csv` contains `B611.VMM73 → B611.VMM72` and `B611.VMM73 → B622.VMM72` as two separate sibling edges.

**Consequence:** any external documentation (including memory, prior notes) that described this as a chain is wrong and should be updated.

---

### 2026-04-16 — Meter-ID normalisation: VMM↔VM, ±`_E`

**Question:** The three sources name the same meter three ways — `B611.Å1_VMM71` (facit), `B611.Å1_VM71` (STRUX/Excel), and `B611.Å1_VM71` (Snowflake). Some meters add an `_E` suffix (`B600N.Å1_VMM71_E`); others don't. Do we treat these as different meters or normalise?

**Sources:**
- `02_crosswalk/meter_id_map.csv` — all 21 facit meters resolved to Snowflake; 19 of 21 also resolved to STRUX.
- `02_crosswalk/crosswalk_notes.md` — documents the normalisation rule and the one drift case (`B616.Å1_VMM71` has `VMM71_E` in Snowflake but `VM71` in STRUX).

**Decision:** adopt the uniform facit naming (`VMM##` with no `_E`) as the canonical ID. Every other ID is a variant for source look-up, recorded in the crosswalk. `facit_meters.csv` uses `VMM##`; scripts that consume other sources must look up the crosswalk.

**Consequence:** the crosswalk is load-bearing. If a new source appears with a fourth naming, add a column to `meter_id_map.csv` rather than inventing a new canonical form.

---

### 2026-04-16 — Two facit meters have no Excel accounting row

**Question:** `B611.Å1_VMM72` and `B642.Å1_VMM71` are in the flow schema and in Snowflake (as `B611.Å1_VM72` and `B642.Å1_VM71` respectively) but never appear in the `Ånga` sheet's S..W columns. Should they be added to the Excel accounting, or left as flow-only?

**Sources:**
- `01_extracted/excel_meters_used.csv` — 19 unique meter IDs, missing both.
- `02_crosswalk/meter_id_map.csv` — both have `excel_used=no` but `snowflake_id` present.
- Flow-schema topology: `B611.VMM72` is a side-tap off `B611.VMM73`'s vertical; `B642.VMM71` is downstream of `B642.VMM72` on the 1.5 BAR branch.

**Decision:** no change to Excel — keep these as flow-only meters. The reason they don't appear in Excel is because the accounting already captures their flow *indirectly*:
- `B611.VMM72` flow is included inside `B611.VMM73`'s inlet measurement. Since the meter serves building 611 (same as `B611.VMM73`), subtracting `B622.VMM72` (the only meter downstream of `VMM73` that belongs to *another* building) is sufficient to attribute the rest to building 611.
- `B642.VMM71` is downstream of `B642.VMM72` in the same building, so its consumption is already part of `B642.VMM72`'s reading. Excel subtracts `B642.VM72` from B614's row (the parent), which removes both B642 meters from B614 at once.

**Consequence:** the ontology will carry these as physical meters that *exist* but don't participate in the accounting formula. The `05_ontology/` model needs to express that a meter can be observed (has timeseries) even if no allocation rule references it.

**Open issue:** is `B611.VMM72`'s reading ever reconciled? If not, it's a trust-the-inlet situation that we should flag for the data-quality team.

---

### 2026-04-18 — Conservation-based topology validation (daily readings)

Ran conservation check against assembled daily readings (Jan 2025 – Feb 2026). For every hasSubMeter parent, compared `parent.flow` vs `Σ children.flow`. Two violations found and corrected via `topology_overrides.csv`:

**1. B600N → B600S: removed (parallel intakes, not series)**

- B600N avg flow: 63 kWh/day
- B600S avg flow: 103 kWh/day
- Residual: -108% (child exceeds parent — physically impossible for hasSubMeter)
- Source of false edge: `naming_index_chain` inferred B600N→B600S from "N precedes S" naming
- PDF flow_schema has no edge between B600N and B600S — they are independent intake points for north and south spine respectively
- Fix: `topology_overrides.csv` `remove` action

**2. B614.VMM71 → B642.VMM72: removed (not downstream)**

- B614.VMM71 avg flow: 12 kWh/day
- B642.VMM72 avg flow: 20 kWh/day
- Residual: -71% (child exceeds parent)
- Source: `flow_schema_V600-52.E.8-001` — parser placed B642.VMM72 as downstream of B614.VMM71, but the readings disprove this
- Fix: `topology_overrides.csv` `remove` action

**3. B614.VMM71 → B642.VMM72: kept despite conservation violation (PDF-confirmed)**

- B614.VMM71 avg flow: 12 kWh/day; B642.VMM72 avg flow: 20 kWh/day
- Monthly ratio B642/B614 swings from 0.1 to 7.5 — not noise, structurally anomalous
- PDF flow diagram (V600-52.E.8) clearly shows B642.VMM72 downstream of B614.VMM71 on the 12 BAR branch, with B642.VMM71 on a 1.5 BAR sub-branch
- Edge retained: PDF topology is authoritative per §3; data anomaly flagged for on-site investigation
- Hypothesis: B642.VMM72 may have an additional feed not shown in the PDF, or one meter has a calibration issue

**Healthy relations confirmed:**
- B600S → 9 children: 6.9% residual (pipe losses, expected for steam)
- B611.VMM73 → VMM72+B622: 35.5% residual (unmetered consumption within B611)
- B612.VMM71 → B613+B641: 100% residual (both children are dead meters)
- B642.VMM72 → B642.VMM71: 98% residual (child is near-dead)

---

### 2026-04-16 — `B616.Å1_VMM71` has drifted IDs between STRUX and Snowflake

**Question:** Snowflake knows this meter as `B616.Å1_VMM71_E`; STRUX (and Excel's lookup) knows it as `B616.Å1_VM71`. Both are valid and refer to the same physical meter, but any automated reconciliation will fail at the string-compare level.

**Sources:**
- `02_crosswalk/meter_id_map.csv` row for `B616.Å1_VMM71`.
- `01_extracted/excel_meters_used.csv` confirms Excel uses `B616.Å1_VM71` on the Ånga sheet row 17 (building 616).

**Decision:** record the dual mapping in the crosswalk; take no action to unify the upstream systems. Our consumers join via the crosswalk, not raw string match.

**Consequence:** any future script that slices BMS data using Excel IDs (or vice-versa) must go through `meter_id_map.csv`. A direct string match would lose this meter.

---

### 2026-04-19 — B642.Å1_VMM72: use post-reset raw data instead of VMM71-derived patch

**Question:** B642 topology Jan 2026 = 54 MWh, Excel cache = 89 MWh. Diff -35 MWh matched B614's +35 MWh exactly (B614 subtracts B642 in Excel).

**Root cause:** The ontology had `B642.Å1_VMM72:d.patch` = sum-derived from VMM71 starting 2025-07-31, replacing the raw Snowflake readings post-reset. The raw `B642.Å1_VM72` Snowflake data continues normally after the 2025-07-31 counter reset (Δ=-31533, device swap pattern): Jan 1 2026 V_FIRST=60.19, Jan 31 V_LAST=149.06 → delta 88.87 MWh, matching STRUX/Excel 89.04 within 0.2%.

**Decision:** Replace the VMM71-derived patch with a proper post-swap raw segment. Added `B642.Å1_VMM72:d.C` (raw, valid_from=2025-08-01). Updated `:d` rolling_sum to stitch A|B|C (three raw segments) without any patch. This prefers actual Snowflake data over a synthesized proxy.

**Consequence:** B614 and B642 both match Excel within 0.5 MWh for 2026-01 and 2026-02. Ontology now uses real counter data rather than overwriting with a VMM71-derived approximation.

