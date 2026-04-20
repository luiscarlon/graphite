# Open questions — snv_varme

## B326/B327 double-attribution of B326.VS1_VMM61

Excel attributes the same meter `B326.VS1_VMM61` to both B326 (row 37,
sole + term) and B327 (row 38, one of two + terms). The ontology can
only assign a meter to one building. Assigned to B326.

Expected impact: B327 building total will be lower than Excel by
Δ(B326.VS1_VMM61). Classify as `excel_bug` after validation.

## B313.VP1_VMM62 double-subtraction in rows 22 (B310) and 23 (B311)

Same pattern as snv_anga's B307/B337 case. Assigned to B311 (shorter
formula). B310 will show residual = Δ(B313.VP1_VMM62).

## PDF and Excel disagree on topology — PDF excluded

The flow-schema PDF (V390-56.8-001) has 34 edges from `arrow` / 
`auto_root_degree` across 5 independent subtrees. Excel doesn't encode
pipe direction for most of these. Examples the PDF suggests but Excel
doesn't confirm:

- `B308.VS1_VMM61 → B327.VS1_VMM61` (PDF arrow)
- `B318.VP1_VMM61 → B319.VP1_VMM61` (PDF)
- `B311.VP1_VMM65 → B311.VS2_VMM61` (PDF), and many intra-B311 edges
- Various VP1→VP2 naming chains inside B301/302/303/304/305 (PDF)

These could be added after validation if a building shows unexpected
residual because a hasSubMeter is missing. But per Excel-is-facit, we
only add an edge when Excel demands it via a − term.

## B203 anchors a 5-building block

Row 9 label `"202,203,204,205,209"` uses `B203.VP1_VMM61_E` as the
sole + term. B203's reading therefore represents combined consumption
for 5 buildings. Attribute the meter to B203 only; the other four will
have zero Excel totals (confirmed in `excel_building_totals.csv`).
