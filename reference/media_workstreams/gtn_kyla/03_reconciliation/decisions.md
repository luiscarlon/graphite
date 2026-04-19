# decisions — gtn_kyla (rebuilt 2026-04-19)

Full rebuild from 01_extracted following RESOLVE_ONTOLOGY.md's Excel-is-facit approach. No PDF for this media — Excel is the sole source for accounting structure and coefficients.

## 2026-04-19 — Excel formula parser has bugs on kyla; re-parsed directly

**Finding:** `01_extracted/excel_formulas.csv` records a single "faktor" column per row, applied uniformly to all terms. The actual kyla Excel formulas have **per-term coefficients** that the parser doesn't capture correctly. Examples:

- Row 13 (B611): `=($R13*XLOOKUP(S)) - XLOOKUP(T) - XLOOKUP(U) - XLOOKUP(V) - XLOOKUP(W)`. $R13=0.38 applies ONLY to S. The CSV incorrectly tags T and U with faktor=0.38.
- Row 14 (B612): `=0.8*XLOOKUP(S) + 0.9*XLOOKUP(T) - 0.9*XLOOKUP(U) - 0.9*XLOOKUP(V) - XLOOKUP(W)`. Mixed per-term coefficients (0.8, 0.9, 0.9, 0.9, 1.0). CSV tags all four as 0.9.
- Row 26 (B634): `=XLOOKUP(S)*24*31/1000 + ...`. Post-factor 0.744 (power-to-energy assuming 31-day month). CSV loses this.
- Row 29 (B641): `=0.1*XLOOKUP(S) - 0.1*XLOOKUP(T) - 0.1*XLOOKUP(U) - V - W`. Per-term coefficients 0.1 on first three, 1.0 on rest.
- Row 50 (B821): `=XLOOKUP(S) - 0.8*XLOOKUP(T) - ...`. Coefficient 0.8 only on T.

**Decision:** Re-parsed raw formula text from `Kyla` sheet cells directly. `facit_accounting.csv` carries correct per-term sign+coefficient. The pristine 01_extracted file is left untouched; future analysts should treat its `faktor` column as unreliable for rows with special Excel forms (rows with `$R` references or mixed inline coefficients).

## 2026-04-19 — Virtual aggregators: B600-KB2 kept, Prod-600 dropped from topology

Kyla Excel has two cross-building accounting virtuals: `B600-KB2` (south distribution) and `Prod-600` (total production). B600-KB2 is referenced by four real building formulas (611, 613, 621(T), 622) that each take a fractional share. Prod-600 is a pure accounting readout with no downstream dependents.

**Decision:**
- **B600-KB2**: model as a virtual meter in 05_ontology (`is_virtual_meter=True`), attributed to campus. Real + term meters (B623, B653.WVÄRME_ACK, B654.KB2_Pkyl_Ack) feed it with k=1. The four sharing buildings each receive a fractional feed from B600-KB2. Total outgoing coefficients = 0.38+0.03+0.5+0.09 = 1.00.
- **Prod-600**: preserved only in `meter_allocations.csv` as a documented accounting formula. No topology meter is created for it. Its +term sources (B653, B654.KB1, B654.KB2, B661.Pkyl_Ack) would otherwise double-count (they already feed B600-KB2 and/or per-building virtuals). Keeping it as topology would violate conservation (each physical meter can only deliver its flow once).

## 2026-04-19 — B658/B661/B821 are NOT hasSubMeter children of B600-KB2

The Excel formula for B600-KB2 subtracts B658.KB2_VM51, B661.KB1_INTVERK, and B821.KB2_VMM1. In principle these should be hasSubMeter children of B600-KB2 in the topology to mirror the subtraction.

**Decision:** Leave B658/B661/B821 as independent meters attributed to their own buildings. Rationale: Excel's subtractions are derived from STRUX_data which caches zero for all three during Jan–Feb 2026, so the Excel-level effect is nil. Snowflake reads real consumption for B658 (~12 MWh/month). If we made B658 a hasSubMeter child of B600-KB2 in topology, the Snowflake-real flow would leak into B600-KB2's subtraction and thereby into 611/613/621(T)/622's shares — producing topology values that diverge from Excel by ~0.38 × 12 = 4.6 MWh on B611 alone. That would propagate a known "Excel=0 but meter live" issue across multiple buildings.

By keeping them independent, the discrepancy is concentrated at B658 (where Excel cache=0 but topology reports the real 12 MWh — the documented misallocation pattern) and does not propagate. Annotated accordingly.

## 2026-04-19 — B612 and B641 share V_B612_net intermediate virtual

B612 Excel: `0.8×B654.KB1 + 0.9×(B612.KB1_PKYL − B637 − B638)`
B641 Excel: `0.1×(B612.KB1_PKYL − B637 − B638)`

The parenthesized expression `B612.KB1_PKYL − B637 − B638` appears in both formulas with different scale factors (0.9 vs 0.1). Total share coefficient = 1.0 — every unit of flow from B612.KB1_PKYL is allocated between B612 (90%) and B641 (10%), minus downstream sub-meters B637 and B638 which each account separately to their own buildings.

**Decision:** Introduce an intermediate virtual meter `V_B612_net` (attributed to campus):
- `B612.KB1_PKYL → V_B612_net` (feeds, k=1)
- `V_B612_net → B637.KB2_INT_VERK` (hasSubMeter) — subtracts B637's flow
- `V_B612_net → B638.KB1_INT_VERK1` (hasSubMeter) — subtracts B638's flow
- `V_B612_net → B612.KYLA_VIRT` (feeds, k=0.9)
- `V_B612_net → B641.KYLA_VIRT` (feeds, k=0.1)

This faithfully encodes the Excel accounting and makes the 90/10 share explicit.

## 2026-04-19 — B631 sub-meters dual-role (own building + subtractor for B611)

`B631.KB1_INTE_VERK2` is a **+term for building B631** (Excel row 25) AND a **subtraction from B611's formula** (Excel row 13). `B631.KB1_VMM51_E` is a **subtraction-only meter** (B611 formula only; not a +term for any building).

**Decision:**
- Attribute `B631.KB1_INTE_VERK2` to building B631 (via meters.csv building_id=B631). Also make it a hasSubMeter child of `B611.KYLA_VIRT`.
  - Building B631 receives `net(B631.INTE) = flow(B631.INTE)`.
  - `B611.KYLA_VIRT` subtracts `flow(B631.INTE)` from its own net.
  - These are independent operations; a single meter's flow "counts" in B631 and "subtracts" in B611's virtual without double-counting because B611's virtual is a separate entity.
- Attribute `B631.KB1_VMM51_E` to campus (blank building_id). It's not a +term anywhere, so attributing to B631 would add 12.97 MWh of uncounted consumption. As a hasSubMeter child of `B611.KYLA_VIRT` it still subtracts from B611's net.

## 2026-04-19 — B821 fractional subtraction (0.8 × B841) not topologically encoded

Excel row 50: `B821 = B821.KB2_VMM51 − 0.8 × B841.KB2_VM51`. The 0.8 coefficient on the subtraction term has no clean topology encoding — `hasSubMeter` subtracts at k=1 only, and `feeds` adds rather than subtracts.

**Decision:** Leave the fractional subtraction out of topology. Both `B821.KB2_VMM51` and `B841.KB2_VM51` report 0 delta in Snowflake for Jan–Feb 2026, so the gap is 0 during the comparison window. When these meters become active, revisit with an intermediate virtual approach (create `V_B841_portion` = 0.8×B841 via feeds, then `B821.KYLA_VIRT` hasSubMeter from it — but hasSubMeter requires real measured_flow rows, so this would need additional plumbing). Documented in annotations.

## 2026-04-19 — B634's power-to-energy conversion

Excel row 26: `B634 = B634.KB1_PKYL × 24 × 31 / 1000`. Literal constant 0.744 (assumes every month is 31 days). `PKYL` suffix suggests this meter reports **power (kW)** rather than energy. Excel converts to MWh/month via `× 24h × 31day / 1000`.

**Decision:** Use `0.744` as a flat coefficient in `meter_allocations.csv`. For topology, attribute `B634.KB1_PKYL` to campus and create `B634.KYLA_VIRT` fed from it at k=0.744. This yields Jan B634 ≈ flow × 0.744. **Caveat:** Feb has 28 days so Excel will be off by 31/28 ≈ 11% from the "true" energy value — but since that's how Excel computes it, matching Excel is the goal.

## 2026-04-19 — Direct subtraction edges for B614 and B833

- B614 formula: `B614.KB1_INT_VERK − B615.KB1_INT_VERK1 − B642.KB1_INT_VERK_1`. All coefficients = 1. Use hasSubMeter edges from B614 to both B615 and B642. Each of B615 and B642 remains attributed to its own building.
- B833 formula: `B833.KB1_GF4 − B834.KB2_INT_VERK`. k=1. Use hasSubMeter edge B833 → B834. B834 remains attributed to its own building (B834 formula: `+B834.KB2_INT_VERK`).

## Open questions

- **B653.KB2_WVÄRME_ACK died 2025-10-09** and **B654.KB2_Pkyl_Ack died 2025-02-10** (Snowflake last reading). Neither has flow during the Jan–Feb 2026 comparison window. Their STRUX values are also 0. Topology + Excel both treat them as 0, so no violation — but document for SNV replication: cooling-plant source meters are fragile, expect outages, plan for stale data.
- **B821 fractional subtraction (0.8 × B841)** not encoded; revisit if these meters become active.
- **B634 power-to-energy** uses literal 31-day month; Feb will be 11% inflated vs reality. Matches Excel intentionally.
