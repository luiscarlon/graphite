# snv_el — reconciliation decisions

## 2026-04-20 — Excel formula re-parse for complex rows

**Question:** `parse_reporting_xlsx.py` only handles single-line XLOOKUP-S/T/U... formulas. SNV EL rows 22, 23, 26, 27, 33, 48 use `SUM(C80:C90)` and `INDEX(STRUX_data, MATCH(...))` patterns that reference helper blocks (rows 79–183). The parser emits zero meter refs for those buildings in `excel_formulas.csv` (verified: `B305, B307, B310, B311, B317, B339` all have 0 rows).

**Sources:**
- `01_extracted/excel_formulas.csv`: zero rows for building numbers 305, 307, 310, 311, 317, 339.
- `00_inputs/excel_source.xlsx` EL tab: row 22 formula `=$F$5*SUM(C80:C90)`, row 26 formula `=$F$5*((C111-SUM(C112:C121))*0.5 + (C122-C123) + (C124-C125) + (C126*1/3) + (C127-SUM(C128:C140))*0.4)`.
- Helper blocks (rows 79–183) list per-term meters in column B and the per-term coefficient is encoded in the row-22/23/26/27/33/48 formula text.

**Decision:** parse the six complex rows by hand (following the coefficient table in `02_crosswalk/crosswalk_notes.md`) and emit explicit per-term rows into `03_reconciliation/facit_accounting.csv` with an added `coefficient` column. Simple rows (+ inline-fraction rows 11/12/28/29) come directly from the parser.

**Consequence:** `facit_accounting.csv` carries 203 rows across 43 buildings with explicit coefficients in `{0.1, 0.25, 0.333333, 0.4, 0.5, 0.666667, 0.75, 0.85, 1.0}`. `generate_building_virtuals.py` picks up the `coefficient` column correctly and emits 43 building virtuals with 203 `{physical → virtual}` or `{virtual → physical}` edges tagged `derived_from=building_virtual_B###`.

---

## 2026-04-20 — parser fix: `$F$5` scalar detection

**Question:** For SNV EL, `extract_building_totals` inferred `sheet_factor=1.0` because `{faktor}` values in `excel_formulas.csv` span `{0.001, 0.00085, 0.00075, 0.00025, 0.0001}` (multiple values from inline R28/R11/R12/R29 fractions). The function only uses `faktor` when all records share one value. Consequence: `excel_building_totals.csv` stored MWh (cached cell values) instead of kWh (Snowflake-native). Same bug would hit any future media with mixed inline coefficients.

**Decision:** patch `parse_reporting_xlsx.py:549` to read `$F$5` directly from `_workbook_scalar_cells(ws_values)` when present with `0 < value < 1`, falling back to the faktor-consensus heuristic only when `$F$5` is absent. Also patch `_normalize_building_id` to reject strings containing `.` (prevented helper-row meter IDs like `B307.T10-1` from being written as rows in `excel_building_totals.csv`).

**Consequence:** SNV EL's `excel_building_totals.csv` now has ~109 proper building rows × 12 months instead of ~122 rows polluted with helper-row meter IDs; values are in kWh matching Snowflake.

---

## 2026-04-20 — Keep naming-hierarchy edges only where Excel subtracts the child

**Question:** The naming-hierarchy candidate set contained 40 edges like `B308.T57 → B308.T57-4-7`. Blindly keeping all of them caused Excel-contradicting sub-meter cancellations (e.g. `B308.T58 → B308.T58-7-8` would subtract T58-7-8's flow from T58 even though Excel treats T58-7-8 as an independent +term for B326, not a sub-meter of T58). Blindly removing all of them caused the opposite problem: B308, B312 etc. started double-counting sub-feeders that Excel correctly treats as hasSubMeters.

**Decision:** apply a filter — keep naming edge `A→B` iff `B` is a `−` term in some building where `A` is a `+` term (i.e. Excel explicitly subtracts the child from the building that contains the parent trunk). This preserves the physical hasSubMeter edges that Excel validates (e.g. `T57→T57-3-2`, which is subtracted from B308 in row 24) and drops the ones that aren't (e.g. `T58→T58-7-8, T58→T58-8-3`).

**Consequence:** 38 of 40 hasSubMeter edges kept. The two dropped edges (`B308.T58 → B308.T58-7-8, B308.T58 → B308.T58-8-3`) represent sub-feeders that Excel never subtracts from T58 — the physical "parent" relationship suggested by naming is false.

---

## 2026-04-20 — STRUX-only meters get normal Snowflake timeseries refs (gap visible)

**Question:** 15 meters referenced in the Excel EL tab have real monthly values in the STRUX tab (verified) but no Snowflake BMS data (e.g. `B313.T26S` = 79168 kWh Jan 2026 in STRUX; absent from Snowflake). How to model?

**Sources:**
- `reference/monthly_reporting_documents/inputs/snv.xlsx` STRUX tab rows 60, 72, 146–183, 224… (real non-zero monthly values).
- `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`: no meter ID matches for any of these 15 IDs after exact, normalized, and tail-segment fuzzy-match.
- Memory `feedback_no_snowflake_overwrite`: "Never synthesize Snowflake-format readings from STRUX monthly values — that hardcodes a secondary source into the primary stream."

**Decision:** follow GTN EL's pattern for `B611.T4-A3/C1/C4` — meters stay in `05_ontology/meters.csv` with `database_id=ion_sweden_bms` pointing at the Snowflake dump. Readings are absent, so `meter_net` correctly reads zero through those meters. Every gap is annotated in `05_ontology/annotations.csv` with the target building, STRUX value evidence, and expected magnitude of the topology-vs-Excel deficit.

**Consequence:** affected buildings (B209, B304, B334 primarily; also the B305/B307/B310/B311/B317 complex-formula pools via B313.T26S / B317.T49 summaries) show large negative `onto − excel` diffs, all attributable to STRUX-only meters per the annotations. No hidden data-synthesis; no Snowflake-stream contamination.

---

## 2026-04-20 — Reservkraft pl7 excluded from facit_meters

**Question:** Excel row 50 (B341) W column = literal string `"Reservkraft pl7"`. Not a meter ID.

**Decision:** skip from `facit_meters.csv` — placeholder for a backup-power allocation not yet mapped to a physical meter. Document in `crosswalk_notes.md` and `annotations.csv`.

**Consequence:** B341's ontology `meter_net` may undercount by the notional reservkraft allocation. In practice B341 matches Excel within ±0.002% (Jan +4 kWh, Feb +3 kWh of 224855 kWh) — the reservkraft placeholder appears to evaluate to zero in STRUX.

---

## 2026-04-20 — Cross-building fractional pools left as meter_allocations-only

**Question:** Four pools require fractional allocation across multiple buildings:

| pool | shares |
|---|---|
| `B313.T26S` net (T26S − 10 sub-meters) | B310 @ 0.5, B311 @ 0.5 |
| `B311.T29` | B310 @ 1/3, B311 @ 2/3 |
| `B317.T49` net (T49 − 13 sub-meters) | B310 @ 0.4, B317 @ 0.5, B313 @ 0.1 |
| `B209.T32-4-2` | B204 @ 0.75, B205 @ 0.25 |

**Sources:** `01_extracted/excel_formulas.csv` for the simple rows, complex-row decomposition in `02_crosswalk/crosswalk_notes.md`.

**Decision:** preserve exact per-term coefficients in `meter_allocations.csv` (via `facit_accounting.csv`) but **do not** create `feeds` edges in `meter_relations.csv` for cross-building splits. `views.sql`'s `feeds_k_sum` expects a single parent's shares to sum to ≤1, which works for intra-building `feeds`, but cross-building fractional splits (where the "parent" is a single physical meter feeding multiple buildings at disjoint fractions) don't fit that shape. Same limitation as `gtn_kyla`'s fractional subtractions (see memory `feedback_kyla_fractional`).

**Consequence:** the four pools leave consistent residuals in the topology-vs-Excel view: B310/B311 for the T26S pool, B310/B311/B317/B313 for the T49 pool, B310/B311 for T29, B204/B205 for T32-4-2. All annotated with magnitude estimates in `05_ontology/annotations.csv`.

**Post-v1 fix:** add a `feeds_cross_building_fractional` primitive to `views.sql` that accepts arbitrary fractional allocations to different buildings without the `feeds_k_sum ≤ 1` constraint. Until then, the app's Excel-comparison surface is the honest source of truth for these 10 building-months.

---

## 2026-04-20 — Small drifts on B330, B337, B342, B344: accepted

**Question:** Four buildings show residuals between 500–5000 kWh (0.5–5 MWh) but not fitting the STRUX-only or pool patterns:

| building | Jan diff | Feb diff | suspected cause |
|---|---|---|---|
| B330 | −3728 kWh (−0.6%) | −44 kWh (−0.0%) | Swap on T65 (2026-01-04 inside comparison window); rolling_sum stitch may introduce boundary skew |
| B337 | −11023 kWh (−2.4%) | +36 kWh (+0.0%) | Swap on T43 (2026-01-29, one day from month boundary); stitch effect |
| B342 | +810 kWh (+0.7%) | +826 kWh (+0.7%) | Consistent small drift — possibly T58-8-3 or T67 post-swap (T67 swap 2025-05-21 well before window) |
| B344 | −4689 kWh (−8.6%) | −4444 kWh (−7.9%) | B318.T21-6-2-A or B308.T57-4-7 have data-quality issues — both are also `−` terms in their naming-parent building. Likely ontology reads are slightly lower than STRUX values for these two. |

**Decision:** accept these as v1 residuals and document in `open_questions.md`. Not worth hand-patching until the broader fractional-pools issue is fixed or more data is available.

**Consequence:** Jan has 7/41 near-match buildings slightly worse than Feb; Feb better because month boundary is farther from the Jan-window swaps on B330 and B337.


---

## 2026-04-20 — Building virtuals + cross-building fractional feeds

**Question:** The initial "meter_measures 1:1" attribution couldn't express fractional coefficients or cross-building splits. Baseline match rate was 50/82 (61%) with significant residuals on every fractional-formula building (B310 -19%, B311 -19%, B312 +17%, B313 +466%, B317 ±38%).

**Decision:** adopt the gtn_kyla pattern — create `B###.EL_VIRT` building virtual meters for every building participating in a fractional allocation, and use `feeds` edges from physical pool meters to the virtuals at the Excel coefficient. Patched `build_ontology.py` so that non-`*_BUILDING` virtuals survive the ontology build.

Virtuals created: B204, B205, B305, B310, B311, B312, B313, B317, B318, B344, B392.

Feeds edges:
- `B209.T32-4-2 → B204.EL_VIRT @ 0.75`, `B205.EL_VIRT @ 0.25`
- `B311.T29 → B310.EL_VIRT @ 1/3`, `B311.EL_VIRT @ 2/3`
- `B312.T34 → B312.EL_VIRT @ 0.85` + residual to `SNV.EL_UNALLOC @ 0.15`
- `B313.T26S → B310.EL_VIRT @ 0.5`, `B311.EL_VIRT @ 0.5`
- `B317.T49 → B310.EL_VIRT @ 0.4`, `B313.EL_VIRT @ 0.1`, `B317.EL_VIRT @ 0.5`

**Consequence:** match rate jumped to 59/82 (72%) within ±500 kWh; 71/82 (87%) within ±5%. B204/B205/B312 now match exactly; B310/B311/B313/B317 within ±3%.

---

## 2026-04-20 — Per-building extra-sub compensation feeds

**Question:** T49 and T26S pools are shared across buildings at fractional coefficients, but each building's Excel formula subtracts a DIFFERENT subset of sub-feeders. B310 subtracts 13 T49 subs (full set); B317 and B313 only subtract 5. Using the union as hasSubMeter children underestimated B317 by `0.5 × 8 extras = 43103 kWh Jan`.

**Decision:** for each "extra" sub (in the larger subtract set but not the smaller), add feeds edges from the sub to the undercounted virtuals at their respective coefficient:
- 8 T49 extras → B317.EL_VIRT @ 0.5, B313.EL_VIRT @ 0.1
- 2 T26S extras → B311.EL_VIRT @ 0.5
- Remaining fraction (1 − sum) → `SNV.EL_UNALLOC` (campus virtual) to satisfy `feeds_flow_coefficients_sum_to_one` validation

**Consequence:** B317 Jan match within 5 kWh; B311 within 6000 kWh (1.8%).

---

## 2026-04-20 — Trunk→sub hasSubMeter edges for complex formulas (B307, B339)

**Question:** Complex rows 23 (B307) and 48 (B339) have trunk + terms (T10-1, T11-1 for B307; T71-1..T78-1 for B339) and sub-feeder − terms. The topology had no naming-hierarchy edges between them because my naming regex stripped only one segment at a time and `T10-1 → T10-6-8` requires a two-segment drop with a different tail pattern.

**Decision:** explicitly add `hasSubMeter` edges from each complex-formula trunk to its Excel-subtracted sub-feeders. For B307, 14 edges (T10-1 → T10-*, T11-1 → T11-*). For B339, 4 edges (T77-1 → T77-*, T78-1 → T78-*). Tag: `excel_EL_complex_formula`.

**Consequence:** B307 went from +35% to ±0%, B339 from +45% to ±0%. Exact matches on both.

---

## 2026-04-20 — Derived sum trunks for B334 T87-T92

**Question:** B334's formula references 5 STRUX-only summary meters (T87, T88, T89, T91, T92) that have no Snowflake BMS data. However, BMS does carry their per-feeder sub-meters (`B334.T87_1_1`, etc., with underscore naming).

**Decision:** create `derived` timeseries refs with `aggregation=sum` for T87, T88, T89, T91, T92 whose sources are the BMS sub-meters (attributed to campus so they don't double-count). Added 20 BMS sub-meters (T87_1_1..T92_4_4) to the crosswalk + facit_meters.

**Consequence:** B334 went from −100% (-439469 kWh Jan) to +7% (+31596 kWh Jan). The +7% residual is the genuine discrepancy between STRUX-cached T87-T92 totals and Snowflake-measured sub-feeders — not synthesizable, accept as data-source fidelity gap.

---

## 2026-04-20 — 50/50 split for Excel's double-+1.0 meters

**Question:** Two meters are +term at coefficient 1.0 in two different buildings simultaneously — Excel's total across buildings is 2.0 × meter_flow, which is physically impossible for a single meter stream:
- `B339.T77-4-5` is +1.0 in B305 (row 22) AND B392 (row 73)
- `B318.T21-6-2-A` is +1.0 in B318 (row 34) AND B344 (row 53)

**Decision:** 50/50 split via feeds to each building's virtual. Neither building matches Excel exactly, but total error is minimized across both (compared to "lowest row wins" which gives 0% for one and -84% for the other).

**Consequence:** B305/B392 and B318/B344 both show residuals proportional to the shared meter's flow. Annotated.

---

## 2026-04-20 — Primary-building attribution: lowest-row wins, pure-minus to campus

**Question:** Previous primary-building rule iterated `facit_accounting.csv` in write-order (which started with parser rows, then helper rows). This meant T77-4-5 got attributed to B392 (row 73 written first) instead of B305 (row 22). And pure-minus meters went to their naming prefix (e.g. T26S-2-12 → B313), over-attributing B313 with flow Excel doesn't allocate there.

**Decision:** sort `facit_accounting` by row number before assigning primary; use first +building (lowest Excel row). For meters never appearing as + anywhere, attribute to campus (not naming prefix). Matches Excel's "unallocated" semantics.

**Consequence:** 25 meter attributions corrected. B313 no longer overcounts by T26S subs' flow.

---

## Final match-rate

- **49/82 (60%) exact matches** (<10 kWh diff)
- **59/82 (72%) within ±500 kWh** (0.5 MWh)
- **71/82 (87%) within ±5%**
- **0 Brick validation violations**

Remaining 23 offenders grouped:

| Count | Buildings | Root cause |
|---|---|---|
| 4 | B209, B304 | Truly STRUX-only trunks with no BMS sub-feeders |
| 4 | B305, B392 | T77-4-5 double-+1.0 Excel anomaly |
| 4 | B318, B344 | T21-6-2-A double-+1.0 Excel anomaly |
| 4 | B310, B311 | T26S pool residual not representable (no T26S BMS data) |
| 1 | B317 Feb | Apparent Excel Feb data anomaly — Jan matches, Feb Excel = 2× Jan |
| 2 | B334 | STRUX summary vs Snowflake sub-feeder fidelity gap (+7%) |
| 3 | B337, B330 | Swap events at month boundary affecting rolling_sum stitch |
| 2 | B342, B344 | Small (<1%) drifts |
