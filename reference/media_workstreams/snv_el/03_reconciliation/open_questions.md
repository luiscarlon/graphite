# snv_el — open questions

## 1. Cross-building fractional pools: no views.sql primitive

Four physical meters (or pool-nets) are split fractionally across multiple buildings:

- `B313.T26S` net (T26S minus 10 sub-feeders): 50% → B310, 50% → B311
- `B311.T29`: 1/3 → B310, 2/3 → B311
- `B317.T49` net (T49 minus 13 sub-feeders): 40% → B310, 50% → B317, 10% → B313
- `B209.T32-4-2`: 75% → B204, 25% → B205

The topology can't materialize these today because `views.sql`'s `feeds` relation is restricted to `Σ flow_coefficient ≤ 1.0 for a single parent` and operates over `meter_flow`, not building totals. Even when the shares sum to 1.0 (as in all four cases), the calc engine would need to split a meter's consumption across multiple different building attribution targets — which currently requires the meter to appear in multiple `meter_measures` rows at fractions, a shape the app also doesn't support.

**Open:** design a cross-building fractional-allocation primitive. Options:
1. Allow `meter_measures` to carry a `fraction` column and let `consumption.sql` multiply `net_kwh` by the fraction before rolling up per building.
2. Introduce `virtual_pool` meters with multiple "virtual split" edges at fractional coefficients, and teach `views.sql` to materialize them.
3. Accept the limitation at the topology layer and rely solely on `meter_allocations.csv` + the app's Excel-comparison view for these 10 building-months of deviation.

Affected building-months in the 2026-01 / 2026-02 comparison (all documented in `05_ontology/annotations.csv`): B204 (+33%), B205 (−100%), B310 (+30%), B311 (−19%), B313 (+466%), B317 (±38%).

## 2. B307 complex-formula overcount (+35%)

B307 formula (row 23): `SUM(C93:C94) - SUM(C95:C108)` — 2 `+` terms (`B307.T10-1`, `B307.T11-1`) minus 14 `−` terms.

Topology: per the naming-hierarchy filter, naming edges from T10/T11 stems to sub-meters were only kept when Excel explicitly subtracts the child from the parent's building. For B307 this works out as expected — but the match still shows +62637 kWh (+35%) on Jan and +55718 kWh (+32.6%) on Feb.

**Hypothesis:** the T10-1 / T11-1 summary meters have kWh values in Snowflake that are inconsistent with the STRUX-logged sum of their children. Needs spot-check of `sum(Snowflake sub-feeders) vs Snowflake summary` to see if BMS carries both correctly. 

**Open:** do the spot-check; if BMS has a T10-1 / T11-1 divergence, prefer the sub-feeder sum (via the current topology, which does this correctly) and annotate the T10-1 / T11-1 summary as unreliable.

## 3. B305 complex-formula undercount (−42% to −44%)

B305 formula (row 22): `SUM(C80:C90)` — all 11 + terms at coefficient 1.0.

Topology: 11 + edges from the building virtual to each sub-meter. Should match Excel exactly. Instead it undercounts by 46021 kWh Jan / 43356 kWh Feb.

**Hypothesis:** some of the helper-row meters `B307.T10-6-8, T10-6-9, T10-7-3, T10-7-4, T10-7-5, T10-7-7, T11-7-10, T11-8-5` have hasSubMeter parents via naming-hierarchy edges (e.g. `B307.T10 → B307.T10-6-8`). When T10 is also a member of B307's formula (as it is indirectly via T10-1 which is the summary), the sub-meters get their flow zeroed at the meter_net level and contribute nothing to B305.

**Open:** if confirmed, B305's sub-meter +terms need to bypass the hasSubMeter zeroing — perhaps a `meter_net_view_opt_out=True` flag or a second path. Alternatively, add a direct `virtual_building_B305 → sub-meter (coef=1.0)` edge that's not stripped. Pattern would reappear on any building whose +terms are other buildings' sub-meters.

## 4. B339 complex-formula overcount (+45% to +50%)

B339 formula (row 48): `SUM(C172:C179) - SUM(C180:C183)` — 8 + (T71-1…T78-1 summaries) and 4 − (T77-5-1, T77-4-5, T78-4-1, T78-4-2).

Same overcount pattern as B307 — the T71…T78 summaries and their sub-feeders likely differ in Snowflake.

**Open:** spot-check summary vs children sum; same remediation as issue 2.

## 5. B334 STRUX-only (−95%)

B334 formula: `+T87 +T88 +T89 +T91 +T92 −T87-5-2 −T88-4-2`. The five + summaries are STRUX-only and well-populated (e.g. T87=94561.5 kWh Jan). Two − sub-feeders exist in Snowflake (with underscore normalization) but are small.

Topology can't contribute the T87-T92 flow; Excel's cached total reflects it. Two options:
1. Accept the gap (current choice, documented).
2. Compute T87=sum(T87_1_1, T87_2_2, T87_4_1, T87_5_2, T87_5_3, T87_5_4) via `aggregation=sum` on a derived timeseries ref, since Snowflake has all the sub-meters. Similar for T88, T89, T91, T92.

**Open:** option 2 is the right fix long-term — creates a proper virtual parent meter from its BMS-available children, no STRUX synthesis. Requires per-summary decision: are the Snowflake sub-feeders genuinely the complete children of each summary, or is there an unmonitored tap?

## 6. B344 −8.6% consistent drift

B344 formula: `+B308.T57-4-7 +B318.T21-6-2-A`. Both + terms, no subtractions.

Both meters are also `−` terms in their naming parent's building (T57 → T57-4-7 at B308; T21 → T21-6-2-A at B318). Both therefore have a `hasSubMeter` parent edge in the current topology.

**Open:** verify that `meter_net` correctly yields the meter's full flow when it's a hasSubMeter child. For a leaf, `meter_net` should equal `meter_flow − 0 = meter_flow`. If the `−` term role in the parent building is being double-subtracted (once by the hasSubMeter edge against T57 the building, once by the `-` sign in the B308 virtual-building formula), the meter's contribution to B344 would effectively be zero — which could explain 8.6% drift if the meter is small vs B344's total. Current effect: meter_net does deliver the meter's full flow to B344 since each meter gets attributed to exactly one building via `meter_measures`; it should not double-attribute. Needs investigation.

## 7. Flow-schema absence

Unlike ånga, värme, kallvatten, no PDF flow-schema exists for EL. Topology is 100% from Excel + naming. Any future electricity topology-verification PDF would be useful for validating intra-building edge candidates.
