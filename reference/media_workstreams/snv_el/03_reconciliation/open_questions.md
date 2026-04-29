# snv_el — open questions

## 1. Cross-building fractional pools — RESOLVED

**Status:** closed 2026-04-29. The premise ("no views.sql primitive") was wrong — fractional `feeds` (k<1.0) and fractional `hasSubMeter` (k<1.0) have always been supported by `views.sql`. GTN KYLA uses both extensively (10 fractional feeds, 4 fractional hasSubMeter).

The four supposedly-unmodellable splits are now wired up via fractional `feeds k<1.0` edges (`excel_EL_fractional` / `excel_EL_t49_extra_compensation` / `excel_EL_abbey_road_unification`):

| Pool | Split | Modelled |
|---|---|---|
| B209.T32-4-2 | 75% B204 / 25% B205 | feeds k=0.75 + k=0.25 |
| B313.T26S | 50% B310 / 50% B311 | feeds k=0.5 + k=0.5 |
| B311.T29 | 1/3 B310 / 2/3 B311 | feeds k=0.333 + k=0.667 |
| B317.T49 | 40% B310 / 50% B317 / 10% B313 | feeds k=0.4 + k=0.5 + k=0.1 |

Affected buildings now match Excel:

| Building | Excel Jan | Onto Jan | Status |
|---|---|---|---|
| B204 | 1,931 | 1,931 | match |
| B205 | 644 | 644 | match |
| B313 | 14,400 | 14,401 | match |
| B317 (Jan) | 62,941 | 62,947 | match |

**Residual drift not from the coefficient model:**
- **B310 / B311 (~6 MWh, 2-3%)** — `B313.T26S` summary has zero BMS data; only its 10 sub-feeders report. Excel's STRUX cached T26S total carries ~12 MWh of unmetered residual that splits 50/50 between B310 and B311. Same family as B334 T87-T92 (issue §5). Reclassified `strux_only_meter`.
- **B317 (Feb only, -75 MWh)** — Jan reproduces Excel exactly via BMS; Feb diverges. All 13 T49 sub-feeders are well-tracked; T26S-3-16/3-20 (B317's other +terms) are flat in BMS. Likely a STRUX-side Feb entry on T26S-3-16/3-20 or a STRUX divergence on one T49 term. Reclassified `under_investigation` (Feb-only); needs facit spot-check.

## 2. B307 complex-formula overcount (+35%)

B307 formula (row 23): `SUM(C93:C94) - SUM(C95:C108)` — 2 `+` terms (`B307.T10-1`, `B307.T11-1`) minus 14 `−` terms.

Topology: per the naming-hierarchy filter, naming edges from T10/T11 stems to sub-meters were only kept when Excel explicitly subtracts the child from the parent's building. For B307 this works out as expected — but the match still shows +62637 kWh (+35%) on Jan and +55718 kWh (+32.6%) on Feb.

**Hypothesis:** the T10-1 / T11-1 summary meters have kWh values in Snowflake that are inconsistent with the STRUX-logged sum of their children. Needs spot-check of `sum(Snowflake sub-feeders) vs Snowflake summary` to see if BMS carries both correctly. 

**Open:** do the spot-check; if BMS has a T10-1 / T11-1 divergence, prefer the sub-feeder sum (via the current topology, which does this correctly) and annotate the T10-1 / T11-1 summary as unreliable.

## 3. B305 / B392 complex-formula undercount — RESOLVED (excel_bug)

**Status:** closed 2026-04-29. Cause confirmed by per-+term contribution analysis; same 50/50-split remediation as B318/B344.

B305 formula (row 22) = SUM(C80:C90), 11 +terms. B392 formula (row 81) includes `B339.T77-4-5` and `B334.T88-4-2`. The hypothesis that helper-row +terms (T10-6-8, T10-6-9, T10-7-3 …) were being zeroed by hasSubMeter parents was **wrong** — every one of those +terms delivers its full flow to B305.EL_VIRT through the `feeds k=1.0` edges (`excel_EL_abbey_road_unification`).

**Actual cause:** `B339.T77-4-5` is a +1.0 term in **both** B305 and B392 in Excel (Excel double-counts the meter). The ontology splits it 0.5/0.5 via `excel_EL_double_plus_split` to avoid the double-count; each building therefore receives 0.5 × T77-4-5 ≈ 23 MWh/mo less than Excel. That single split accounts for ~100 % of both gaps:

| Building | Gap (Jan) | 0.5 × T77-4-5 (Jan) | Residual |
|---|---|---|---|
| B305 | −23,007 kWh | 23,013 kWh | −6 kWh |
| B392 | −23,005 kWh | 23,013 kWh | −8 kWh |

The two 0-flow +terms in B305 (`T10-7-3`, `T10-7-7`) carry no BMS data, but their Excel values appear to be ≈0 too — they don't contribute to the gap.

**Resolution:** reclassified both as `excel_bug`. The 0.5/0.5 split is the correct remediation for an Excel double-plus where neither building has prefix-match priority (matches B318/B344). Compare with single-parent attribution chosen for B326/B327 (VARME) and B310/B311/B314 (KALLVATTEN), where the meter ID prefix dictated the parent.

## 4. B339 complex-formula overcount (+45% to +50%)

B339 formula (row 48): `SUM(C172:C179) - SUM(C180:C183)` — 8 + (T71-1…T78-1 summaries) and 4 − (T77-5-1, T77-4-5, T78-4-1, T78-4-2).

Same overcount pattern as B307 — the T71…T78 summaries and their sub-feeders likely differ in Snowflake.

**Open:** spot-check summary vs children sum; same remediation as issue 2.

## 5. STRUX-only summaries — accepted gap

**Status:** accepted 2026-04-29. Three buildings drift because of summaries / sub-meters that exist in Excel's STRUX cache but not in Snowflake BMS:

- **B334 (−95%)** — formula `+T87 +T88 +T89 +T91 +T92 −T87-5-2 −T88-4-2`. The five + summaries are STRUX-only and well-populated (e.g. T87=94,561 kWh Jan). The two − sub-feeders exist in Snowflake (with underscore normalization) but are small.
- **B304 (−100%, ~4.5 MWh)** — formula `+B313.T26S-3-12 +B336.T40-3-1`. Both meter IDs are entirely absent from Snowflake (zero rows).
- **B310 / B311 (~6 MWh each, 2-3%)** — `B313.T26S` has no measured flow in Snowflake. Per-component reconstruction shows Excel uses STRUX-cached T26S ≈ 74.6 MWh/mo; the 10 BMS sub-feeders sum to ~63 MWh, leaving a ~12 MWh STRUX-only residual that's split 50/50 via `feeds k=0.5` edges. The feeds are dead because views.sql's recursive `flow` requires a measured base — T26S never enters the recursion, so the 0.5 split delivers 0 to both buildings.

**Decision:** accept all three gaps. They're correctly classified `strux_only_meter` and the explanations document exactly what's missing and why.

**If we ever want to close them**, two paths exist:
1. **Sub-feeder synthesis** — for B334, compute `T87 = sum(T87_1_1, T87_2_2, …)` via `aggregation=sum` on a derived timeseries ref, since Snowflake has all the sub-meters. Risk: doesn't capture an unmonitored tap if one exists. Doesn't apply to B304/B310/B311 because their summary children are also STRUX-only.
2. **STRUX injection** — encode the STRUX summary as a virtual timeseries ref via a structured extraction pipeline (not hand-edited rows — see `feedback_no_hand_readings`). For B313.T26S, a single injected ts_ref would activate the existing 0.5/0.5 feeds and close B310 and B311 simultaneously. For B304, two injected ts_refs (T26S-3-12, T40-3-1) would close it. For B334, five (T87-T92).

Neither path is required for facit reconciliation — the gaps are documented and the BMS-canonical posture is preserved.

## 6. B344 −8.6% consistent drift

B344 formula: `+B308.T57-4-7 +B318.T21-6-2-A`. Both + terms, no subtractions.

Both meters are also `−` terms in their naming parent's building (T57 → T57-4-7 at B308; T21 → T21-6-2-A at B318). Both therefore have a `hasSubMeter` parent edge in the current topology.

**Open:** verify that `meter_net` correctly yields the meter's full flow when it's a hasSubMeter child. For a leaf, `meter_net` should equal `meter_flow − 0 = meter_flow`. If the `−` term role in the parent building is being double-subtracted (once by the hasSubMeter edge against T57 the building, once by the `-` sign in the B308 virtual-building formula), the meter's contribution to B344 would effectively be zero — which could explain 8.6% drift if the meter is small vs B344's total. Current effect: meter_net does deliver the meter's full flow to B344 since each meter gets attributed to exactly one building via `meter_measures`; it should not double-attribute. Needs investigation.

## 7. Flow-schema absence

Unlike ånga, värme, kallvatten, no PDF flow-schema exists for EL. Topology is 100% from Excel + naming. Any future electricity topology-verification PDF would be useful for validating intra-building edge candidates.
