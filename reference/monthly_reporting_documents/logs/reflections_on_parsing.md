# Reflections on parsing and validation

Across all tabs (GTN + SNV), the problems fall into a few recurring categories.

## 1. Naming disambiguation is weak or useless

The Excel formulas use flat accounting (all meters in one cell), so when a building has multiple `+` meters, we need naming to figure out which parent feeds which child. This works decently for **GTN EL** (transformer roots like T4, T8) and **SNV EL** (same), but breaks down for:

- **Ånga** (both sites): all meters share the Å1 prefix — regex can't even match `Å` as ASCII. Every assignment is arbitrary.
- **Kallvatten** (both sites): all meters share KV1. Same problem.
- **Värme VP1/VP2/VS1/VS2**: works within circuits but can't cross-match (VS1 child with no VS1 parent).

The result: relations are recorded but individual parent assignments may be wrong. Building-level totals still validate because the sum is invariant.

## 2. Formulas are accounting shortcuts, not wiring diagrams

The single biggest source of complexity. Each building formula computes net consumption in one cell by subtracting the **entire downstream chain**, not just direct children. This means:

- **Zone aggregation buildings** (B310 in Värme/Ånga/Kallvatten, B307 in Ånga, B311 in Kallvatten) subtract 10–22 meters spanning multiple hierarchy levels. We can't tell direct children from grandchildren without cross-referencing other formulas.
- **Per-building subtraction subsets** (SNV EL B310/B311 T26S, T49): different buildings subtract different subsets of the same parent's children. This pattern appears ONLY in SNV EL, in two places (T26S and T49), both involving B310/B311/B313/B317. Everywhere else across 12 tabs and 2 sites, formulas are consistent. The strongest signal that this is a bug: B311 **adds** `+0.5*T26S_3_24` while B310 **subtracts** it — contradictory for any physical topology. The formula_document.xlsx confirms the same inconsistency (inherited, not caught). Suspected spreadsheet bug, not a structural modeling problem.

## 3. Cross-subtractions / cycles

When two buildings mutually subtract each other's meters (B310/B311 VS2 in Värme), the naive parse creates a cycle. We resolve by keeping the direction from the more specific formula (fewer subtractions = closer to the actual feed). Works but requires manual reasoning about which building is upstream.

## 4. Shared meters without coefficient splits

Some meters are `+` in multiple buildings at coefficient 1.0 (B326.VS1 in both B326 and B327 Värme, B315.KV1 in both B314 and B315 Kallvatten, B339.T77-4-5 in both B305 and B392 EL). We assign by naming convention (Bxxx → building xxx), which means the other building's graph calc is wrong by exactly that meter's reading. Not fixable without inventing a split that doesn't exist in the source.

## 5. Computed meters not in STRUX

Some "meters" are actually computed aggregations (B600-KB2 in GTN Kyla, BPS_V2 in SNV Sjövatten). Their values come from formulas over other buildings' meters, not from STRUX. The graph model can't resolve them because:
- The component meters already belong to their own buildings
- Storing them as relations would create double-counting

Formula validation handles these correctly (we use the cached computed value), but graph validation always fails for the dependent buildings.

## 6. Source data errors

Confirmed errors in the Excel files themselves:
- **B317 parenthesis typo** (SNV EL): col C has correct `(T49-SUM(subs))*0.5`, cols D–N have wrong `T49-SUM(subs)*0.5`. Cached values are wrong for Feb–Dec.
- **B318 sign typo** (SNV EL): snv.xlsx adds T21-6-2-A, formula_document.xlsx subtracts it. Overcounts by ~4.4 MWh/month.
- **B392 meter swap** (SNV EL): different meter IDs between snv.xlsx and formula_document.xlsx. Not a typo — intentional reassignment between document versions.

## 7. Orphan meters

Meters that only appear as `-` (never `+` anywhere). Some are negligible (B307 EL orphans at <0.02 kWh), some are real gaps (B385.VP2_VMM62_E in Värme). They represent unmeasured pass-through, decommissioned meters, or missing building rows. We record them with `building=''`.

---

**In short**: the core difficulty is that the Excel encodes a **flat accounting view** (one formula per building) while we need a **hierarchical topology** (parent→child DAG). Recovering the hierarchy requires cross-referencing formulas across buildings, naming heuristics, and accepting that some assignments are genuinely ambiguous.
