# Reconciliation decisions — gtn_kyla

Every merge decision with evidence and date.

---

### 2026-04-19 — No PDF; topology from Excel formulas only

**Question:** Without a flödesschema PDF for kyla, how is physical topology established?

**Sources:**
- `00_inputs/README.md`: "No flow-schema PDF exists for GTN kyla"
- `RESOLVE_ONTOLOGY.md` §2: kyla has "Excel+BMS" only
- `01_extracted/excel_formulas.csv`: 45 meter refs across 25 building rows

**Decision:** Topology is derived entirely from the Excel formula structure. A `−` term in a building formula is treated as a physical downstream sub-meter of the `+` inlet, but ONLY when both meters are physical (not virtual), and ONLY when the formula represents a genuine parent→child pipe relationship (not an accounting allocation across unrelated meters).

**Consequence:** 6 physical edges vs the 11+2 raw Excel-derived edges. Many buildings have no topology edges because their meters are standalone or their relationships are pure accounting allocations.

---

### 2026-04-19 — B600-KB2 is virtual accounting, not physical topology

**Question:** The B600-KB2 formula (`= B623 + B653.ACK + B654.KB2 − B658 − B661 − B821`) generates 3 parent→child edges (B623→B658, B623→B661, B623→B821) when the `excel_relations.py` extractor picks B623 as the principal inlet. Are these physical?

**Sources:**
- `01_extracted/excel_formulas.csv` row 8: B600-KB2 has 6 terms
- `01_extracted/excel_meters_used.csv`: B600-KB2 is used as `add` input in B611, B613, B621(T), B622 — these are allocation recipients
- `04_validation/monthly_conservation.csv` rows 44-57: B623 parent has delta 0-5 MWh/month vs children sum 5-42 MWh → residual −3.6% to −132837%. Children vastly exceed parent. This is physically impossible for a real parent→child relationship.
- B600-KB2 has no Snowflake data (`02_crosswalk/meter_id_map.csv` row 25: no snowflake_id)

**Decision:** Remove all 5 edges derived from B600-KB2's formula (3 from B623→children, 2 from B600-KB2→B631). B600-KB2 is a virtual campus-level accounting aggregate that allocates net cooling production to unmetered buildings via fixed fractions (B611=38%, B613=3%, B621=50%, B622=9%). None of these represent pipe-level physical topology. The conservation check independently confirms: "children" exceed "parent" by 10-100×.

B623, B658, B661, B821 are all standalone meters on independent buildings.

---

### 2026-04-19 — B612.KB1_PKYL → B637, B638 are hasSubMeter, not 0.1 feeds

**Question:** `excel_relations.py` produced B612-KB1-PKYL → B637 and B612-KB1-PKYL → B638 with coefficient 0.1 (from B641's formula). What is the correct physical relationship?

**Sources:**
- `01_extracted/excel_formulas.csv` row 14-18:
  - B612 = 0.8×B654.KylEffekt_Ack + 0.9×B612-KB1-PKYL − 0.9×B637 − 0.9×B638
  - B641 = 0.1×B612-KB1-PKYL − 0.1×B637 − 0.1×B638
- Both formulas share the same pattern: B612.PKYL minus B637 and B638, just at different allocation fractions (0.9 for B612 building, 0.1 for B641 building). Total: 0.9 + 0.1 = 1.0.
- `01_extracted/timeseries_monthly.csv`: B637 reads 13-18 MWh/month (healthy). B638 reads 0 (dead). B612.KB1_PKYL reads sporadically (197 MWh Jan, then intermittent).

**Decision:** B612.KB1_PKYL is a physical cooling pipe meter. B637 and B638 are downstream sub-meters tapped off the same pipe. The physical relationship is `hasSubMeter` with coefficient=1.0 (NULL in ontology). The 0.9/0.1 split allocates the pipe's *residual* (PKYL − B637 − B638) between buildings B612 and B641 — this is accounting, preserved in `facit_accounting.csv`.

Also corrected the ID from the Excel dash-format `B612-KB1-PKYL` to the canonical `B612.KB1_PKYL`.

---

### 2026-04-19 — B654.KB1_KylEffekt_Ack is production, not physically upstream of B637/B638

**Question:** `excel_relations.py` tried to produce B654.KB1_KylEffekt_Ack → B637 and → B638 (dropped as duplicate-parent conflict). Should these be restored?

**Sources:**
- `01_extracted/excel_formulas.csv` row 15-18: B612 formula sums 0.8×B654 + 0.9×(PKYL − B637 − B638). B654 and PKYL are two separate input terms, not in a parent→child relationship.
- B654 is a production meter in building 653/654 (chiller plant). B637 is in building 637. These buildings are physically separate.

**Decision:** No edge between B654 and B637/B638. The accounting formula adds B654 and the PKYL-pipe residual to calculate B612 building's total, but B654 and B637 are not on the same pipe.

---

### 2026-04-19 — System-code stripping for B821 and B833

**Question:** Excel uses `B821-55-KB2-VMM1` and `B833-55-KB1-GF4` where `55` is a system code (§7). The crosswalk had these as separate entries from the code-stripped forms.

**Sources:**
- `02_crosswalk/meter_id_map.csv` rows 103, 105: both `B821.55_KB2_VMM1` and `B821.KB2_VMM1` exist, neither has Snowflake match.
- `02_crosswalk/meter_id_map.csv` rows 108, 109: `B833.55_KB1_GF4` (Excel only) vs `B833.KB1_GF4` (Snowflake match).
- `RESOLVE_ONTOLOGY.md` §7: "System-code tokens in Excel labels ... sometimes need stripping to match Snowflake"

**Decision:** Merged crosswalk entries. B821-55-KB2-VMM1 → facit_id `B821.KB2_VMM1`. B833-55-KB1-GF4 → facit_id `B833.KB1_GF4` (now has Snowflake match via `B833.KB1_GF4`).

---

### 2026-04-19 — B616.KB1_PKYL device swap to B616.KB1_VMM50_E

**Question:** B616.KB1_PKYL stops emitting Jun 13, 2025. B616.KB1_VMM50_E starts emitting Jul 15, 2025. Is this a device swap?

**Sources:**
- `01_extracted/timeseries_monthly.csv`: B616.KB1_PKYL has 143 MWh for partial June (13 days), then nothing. B616.KB1_VMM50_E has 441 MWh for partial July (17 days), then continues monthly.
- Same building (616), same role (KB1), same media (kyla process cooling).
- `01_extracted/excel_intake_meters.csv`: Both appear — PKYL as "Manuell" and "Automatisk".

**Decision:** This is a device swap. B616.KB1_PKYL.A (valid_to=2025-06-13) and B616.KB1_VMM50_E.B (valid_from=2025-07-15) should be stitched via rolling_sum in the ontology. Note the ~1 month gap (Jun 14 – Jul 14) with no data.

---

### 2026-04-19 — Dead meters kept in facit for completeness

**Question:** Several formula-referenced meters read all-zero in Snowflake: B638.KB1_INT_VERK1, B642.KB1_INT_VERK_1, B643.KB1_INT_VERK, B654.KB2_Pkyl_Ack, B661.KB1_INTVERK (near-dead), B821.KB2_VMM1 (no Snowflake), B841.KB2_VMM51. Include them?

**Decision:** Yes. They are referenced by the Excel accounting formulas and represent real physical meters that happen to be offline or decommissioned. Excluding them would make the accounting formulas incomplete. They will be annotated as dead/offline in the ontology with appropriate validity dates.

---

### 2026-04-19 — B653.KB2_WVÄRME vs B653.KB2_WVÄRME_ACK

**Question:** The crosswalk has both `B653.KB2_WVÄRME` (instantaneous power, frequent counter resets) and `B653.KB2_WVÄRME_ACK` (accumulator). The Excel formula uses _ACK. Should _WVÄRME appear in the ontology?

**Sources:**
- `RESOLVE_ONTOLOGY.md` §7: "`_ACK` suffix = accumulator. The non-`_ACK` variant is typically instantaneous power, NOT the same meter."
- `01_extracted/timeseries_monthly.csv`: B653.KB2_WVÄRME has 130+ counter resets (not real swaps — oscillating power meter). B653.KB2_WVÄRME_ACK has stable cumulative readings until offline Oct 2025.
- Excel formula references `B653.KB2_WVÄRME_ACK` only.

**Decision:** Only `B653.KB2_WVÄRME_ACK` is in the facit. `B653.KB2_WVÄRME` is the instantaneous power counterpart and is NOT included — it's not referenced in the formula and its "swaps" are oscillation artifacts, not real device events.

Similarly, `B654.KB1_KylEffekt` (power) vs `B654.KB1_KylEffekt_Ack` (accumulator): only the _Ack is in the formula and the facit. `B661.KB1_Pkyl` (power) vs `B661.KB1_Pkyl_Ack`: only _Ack in the facit.
