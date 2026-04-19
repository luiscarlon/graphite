# decisions — gtn_varme

### 2026-04-19 — Campus-wide counter reset Jan 8-9 is NOT device swaps

**Question:** `detect_meter_swaps.py` flagged 43 meters as "swap" events on 2025-01-08 and 2025-01-09. Are these real device replacements?

**Sources:**
- `01_extracted/timeseries_anomalies.csv`: all 43 meters show `reset_days` on 2025-01-08 or 2025-01-09
- `01_extracted/timeseries_daily.csv`: counters drop to near-zero then resume normal reading patterns

**Decision:** False positive. All 43 counter resets on the same two days is a campus-wide counter/system reset, not individual device swaps. Removed from `meter_swaps.csv` before running `build_ontology.py`. Only 3 genuine events remain: B658 offline (2026-02-02), B833.VP1_VMM61 offline (2026-02-19), B833.VP1_VMM62 offline (2026-02-19).

---

### 2026-04-19 — B661.VS1_VMM61 (PDF) = B661.VP1_VMM61 (Excel/Snowflake)

**Question:** The flow schema labels building 661's sole heating meter as VS1 (secondary). Excel and Snowflake use VP1 (primary). Are these the same physical meter?

**Sources:**
- `01_extracted/flow_schema_meters.csv`: B661.VS1_VMM61 only
- `01_extracted/excel_formulas.csv` row 41: B661.VP1_VMM61_E
- `01_extracted/meter_roles.csv`: B661.VS1 seen in flow_schema only; B661.VP1 seen in excel_formulas only. Same VMM61 index. Only one meter per building.

**Decision:** Same physical meter. The role classification differs between the PDF drawing (VS1) and the accounting system (VP1). Used VP1 as canonical since that's the ID with Snowflake data. Topology override: removed PDF edge B616.VP1_VMM62 → B661.VS1_VMM61, added B616.VP1_VMM62 → B661.VP1_VMM61.

---

### 2026-04-19 — B821.VS1_VMM61 (PDF) = B821.VP1_VMM61 (Excel/Snowflake)

**Question:** Same as B661 — PDF uses VS1, Excel/Snowflake use VP1.

**Sources:**
- `01_extracted/flow_schema_meters.csv`: B821.VS1_VMM61 only
- `01_extracted/excel_formulas.csv` row 48: B821.VP1_VMM61_E

**Decision:** Same physical meter. Used VP1 as canonical. Removed naming hierarchy edge B821.VP1 → B821.VS1 (self-reference).

---

### 2026-04-19 — B612.VP2 sub-meters are parallel zone meters, not sequential chain

**Question:** The naming_index_chain heuristic inferred B612.VP2_VMM62 → VMM63 → VMM64 → VMM65 as a sequential chain. Is this correct?

**Sources:**
- `01_extracted/excel_formulas.csv` row 12: B612 = VMM62 + VMM63 + VMM64 + VMM65 − B641 − B637 − B613.VP2 − B654. All four VMM meters are **additive** terms.
- `01_extracted/flow_schema_relations.csv`: B612.VP2_VMM61 → VMM62, VMM61 → VMM63 (root → sub)

**Decision:** VMM62, VMM63, VMM64, VMM65 are parallel zone meters under VMM61, not a sequential chain. If they were sequential, the Excel would subtract downstream meters from upstream (not add them all). Override: removed VMM63→VMM64 and VMM64→VMM65 naming chain edges; added VMM61→VMM64 and VMM61→VMM65 as siblings.

---

### 2026-04-19 — B674 heat recovery (VÅ9) is upstream of primary (VP)

**Question:** The PDF shows B674.VÅ9_VMM41 → B674.VP1_VMM61 and B674.VÅ9_VMM42 → B674.VP2_VMM61 (both arrow-confirmed). The naming convention says VP → VÅ9 (primary feeds recovery). Which is correct?

**Sources:**
- `01_extracted/flow_schema_relations.csv`: arrow-confirmed edges VÅ9→VP
- `01_extracted/naming_relations.csv`: VP→VÅ9 (naming_role_hierarchy)

**Decision:** PDF arrows are authority for direction. The heat recovery unit captures waste heat and its output enters the primary circuit upstream of the VP meters. So VÅ9 is physically upstream of VP in B674. Naming convention VP→VÅ9 is the general pattern but does not apply here. Removed naming edges to prevent cycle (VP1→VÅ9_42→VP2→VÅ9_41→VP1).

**Consequence:** B674's topology: VÅ9_41 → VP1, VÅ9_42 → VP2. VÅ9 meters are roots. B674.VP1 and VP2 are the building consumption meters.

---

### 2026-04-19 — B643 VÅ9_42 → VP1 direction follows B674 pattern

**Question:** B643.VÅ9_VMM42 → B643.VP1_VMM61 (auto_root_degree, not arrow-confirmed). The naming convention says VP1 → VÅ9.

**Sources:**
- `01_extracted/flow_schema_relations.csv`: auto_root_degree edge VÅ9_42 → VP1
- B674 arrow-confirmed precedent for the same pattern

**Decision:** Adopted PDF direction (VÅ9_42 → VP1). Consistent with the B674 arrow-confirmed pattern: heat recovery output enters the primary circuit. Removed naming edge VP2 → VÅ9_42 to prevent VP2→VÅ9_42→VP1 chain (Excel confirms VP1 and VP2 are independent parallel inputs — both are + terms in the B643 formula).

---

### 2026-04-19 — B615.VS1 → B642.VS1 conservation anomaly (SUPERSEDED 2026-04-19)

**Question:** B642.VS1_VMM61 consumption (438 MWh/m) far exceeds parent B615.VS1_VMM61 (29 MWh/m). PDF arrows confirm direction.

**Sources:**
- `04_validation/anomalies.md`: B615 swap_event, mean=-1755%
- `01_extracted/flow_schema_relations.csv`: B615.VS1 → B642.VS1 (arrow-confirmed)
- `01_extracted/excel_formulas.csv`: B614 subtracts both B615 and B642 independently

**Decision (original):** Keep PDF topology (arrow-confirmed). B642 likely has additional heating feeds not shown on the PDF.

**Superseded 2026-04-19:** See "Excel-priority realignment" entry below. Edge B615→B642 removed; B642 now a direct hasSubMeter child of B614 per Excel formula.

---

### 2026-04-19 — Excel-priority realignment of värme topology

**Question:** App Excel-comparison view showed 9 värme buildings with 10%–1500% diffs between topology and cached Excel values, despite `04_validation/building_totals_spot_check.csv` reporting 0.0–0.6% per-building deltas. Why the disagreement?

**Root cause:** `spot_check` evaluates the Excel formula using Snowflake deltas — it validates meter-ID mapping, not topology. The app's comparison sums `meter_net` per (building, media) via `meter_measures`, which reflects the actual hasSubMeter topology. Multiple naming/PDF-heuristic edges pulled meters into the wrong subtraction structure.

**Decision:** Align topology with Excel formulas. User directive: prioritize Excel namings and readings over the flow diagram; use the PDF only when it helps, not as base.

**Edges removed** (conflicted with Excel):
- `B631.VP1_VMM61 → B631.VP1_VMM62` (naming_index_chain) — intermediate node has no data, subtraction broken
- `B612.VP2_VMM61 → B612.VÅ9_VMM41` (naming) — VÅ9 not in B612 Excel formula
- `B612.VP2_VMM61 → B613.VP1_VMM62` (flow_schema, wrong meter) — Excel references VP2_VMM61
- `B612.VP2_VMM61 → {B637, B654}.VP2_VMM61` (flow_schema) — parent has no data, re-parented
- `B613.VP1_VMM61 → B613.VP2_VMM61` (timeseries_residual_fit) — Excel treats both as independent + terms
- `B614.VS1_VMM61 → B614.VÅ9_VMM41` (naming) — Excel treats both as + terms
- `B615.VS1_VMM61 → B642.VS1_VMM61` (flow_schema arrow) — Excel subtracts B642 from B614, not B615
- `B616.VP1_VMM61 → VP1_VMM62` (naming) and `VP1_VMM61 → VÅ9_VMM41` (naming) and `VP1_VMM62 → VS2_VMM61` (flow_schema) — all four are independent + terms in Excel
- `B625.VS1_VMM61 → B625.VÅ9_VMM41` (naming) — Excel treats both as + terms
- `B643.VP1_VMM61 → B643.VÅ9_VMM41` (naming) and `B643.VÅ9_VMM42 → B643.VP1_VMM61` (flow_schema) — VÅ9 meters not in Excel B643 formula
- `B833.VP1_VMM61 → {B833.VP1_VMM62, B833.VÅ9_VMM41}` (flow_schema) — Excel treats VMM62 as + term and VÅ9 is not in formula

**Edges added** (to match Excel subtractions):
- `B611.VP1_VMM61 → B631.VP1_VMM62` (excel_formula_B611)
- `B612.VP2_VMM65 → {B637, B613.VP2, B654}.VP2_VMM61` (excel_formula_B612) — chosen VMM65 as parent because it's the largest + term and Excel does not specify which + term feeds which − term
- `B614.VS1_VMM61 → B642.VS1_VMM61` (excel_formula_B614)

**Meters reattributed to campus** (in Excel of no building):
- `B612.VÅ9_VMM41`, `B643.VÅ9_VMM41`, `B643.VÅ9_VMM42`, `B833.VÅ9_VMM41`

**B833 patch adjusted:** Removed `B833.VÅ9_VMM41:d` from the VP1_VMM61 outage patch sources. VÅ9 is not part of B833's Excel accounting, so post-outage VP1 reconstruction should not include it.

**Consequence:** 48/48 buildings within ±0.5 MWh of Excel for 2026-01. 47/48 for 2026-02 — only B833 remains at +23 MWh (+17%) because the outage patch captures post-Feb-19 consumption via B834 that Excel's frozen VP1 counter misses. Documented in annotation `B833_61_offline` as ontology-better-than-Excel.

---

### 2026-04-19 — B612.VP2_VMM61 is PDF root but flat in Snowflake

**Question:** B612.VP2_VMM61 is the root of the VP2 circuit in the PDF but has `flat_all_window` anomaly (35 days all zero delta). Should it be included?

**Sources:**
- `01_extracted/timeseries_anomalies.csv`: `flat_all_window, 35 days, all zero delta`
- `01_extracted/flow_schema_meters.csv`: B612.VP2_VMM61 present
- `01_extracted/excel_formulas.csv`: NOT used in any formula

**Decision:** Include as a topology node (it's in the PDF and Snowflake), but note that its data is unreliable. It's the physical root meter but was apparently not reporting during part of the observation window. The Excel accounting starts from VMM62 instead, bypassing VMM61.

---

### 2026-04-19 — PDF-only meters without Snowflake data

**Question:** 6 meters appear in the flow schema but have no Snowflake timeseries: B613.VP1_VMM62, B616.VS1_VMM61, B621.VÅ9_VMM41, B631.VP1_VMM61, B674.VÅ9_VMM41, B674.VÅ9_VMM42.

**Decision:** Include all as topology nodes. They represent physical meters on the flow schema that either aren't connected to BMS or have different naming in Snowflake. B631.VP1_VMM61 is particularly important as the routing node connecting B611 to B611.VÅ9_VMM41. None of these have timeseries refs in the ontology.

---

### 2026-04-19 — Timeseries-fit edge B613.VP1 → B613.VP2

**Question:** `timeseries_relations.py` proposed B613.VP1_VMM61 → B613.VP2_VMM61 with 71% improvement in conservation residual.

**Sources:**
- `01_extracted/timeseries_relations.csv`: improvement=71%
- `01_extracted/excel_formulas.csv`: B613 = VP1 + VP2 (both additive)

**Decision:** Accepted. B613 has two inlets (VP1 from B611 branch, VP2 from B612 branch). VP1 is the larger meter, and VP2's monthly pattern reduces VP1's residual significantly. The edge makes VP2 a child of VP1, which is a conservation relationship (VP1 − VP2 = B613's net via VP1 circuit). This is an accounting convenience, not physical topology — VP2 is actually on the VP2 circuit, not downstream of VP1 on the VP1 circuit.
