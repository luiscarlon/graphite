# Reconciliation decisions — snv_varme

Excel-is-facit build. Source of truth per §0 of `RESOLVE_ONTOLOGY.md`:
Excel formulas on the `Värme` sheet dictate each meter's + / − role.

## 2026-04-20 — Crosswalk: all 46 Excel meters match Snowflake exactly

All 46 Excel-referenced meters match Snowflake after `_VM##` → `_VMM##`
normalisation and `_E` strip. Zero fuzzy-match gaps. No SNV-specific
summary suffixes (`-1`, `_1_1`, dash↔underscore drift) apply to
värme — those were EL-only artifacts.

**Evidence:** `02_crosswalk/meter_id_map.csv`, 50 entries (46 Excel + 4
PDF-only with Snowflake data, 0 Snowflake-absent).

## 2026-04-20 — Default merge dropped Excel edges in favour of PDF

The default `apply_topology_overrides.py` pass kept 34 flow_schema
edges and only 2 Excel-derived edges, dropping 22+ Excel edges as
"child already has parent." Per Excel-is-facit, this is backwards: the
accounting structure must win.

**Decision:** build `facit_relations.csv` by hand from Excel only
(`/tmp/build_snv_varme_facit.py`). 30 hasSubMeter edges emitted, one
per Excel − term at k=1 (shorter-formula rows processed first so the
more specific relation claims the child). Naming heuristics and PDF
edges are NOT merged in — they were the dominant cause of gtn_varme
needing a realignment on 2026-04-19 and would cause the same churn
here.

**Consequence:** `03_reconciliation/facit_relations.csv` is 30 rows, all
tagged `excel_formula_B###`. The PDF is retained in `01_extracted` for
visual audit but does not feed the ontology.

## 2026-04-20 — B310 row 22 is a 27-term distribution pool

Row 22 has 4 + terms (B310.VP2_VMM61, VP1_VMM61, VS2_VMM61, VS2_VMM62)
and 22 − terms covering every downstream building
(B301/302/303/304/305/311/312/313/317/341/385). B310 is the distribution
aggregator for the entire B3xx south campus.

**Decision:** treat all 22 − terms as hasSubMeter children of
`B310.VP2_VMM61` (the first + term). All the subtracted meters are
+ terms for their respective buildings, so their delta stays attributed
where Excel wants it — B310's net = its inlet − all sub-building flows,
correctly.

**Conflicts resolved:** B313.VP1_VMM62 is subtracted in both row 22
(B310) and row 23 (B311). Chose row 23 (B311, shorter formula = more
specific) per the snv_anga precedent. B310 will show a residual
equal to Δ(B313.VP1_VMM62) — typically small.

## 2026-04-20 — B311 row 23 subtracts B310 secondary-side meters

Row 23 has 4 + terms (B311's own VP1/VS2 meters) and 3 − terms,
two of which are `B310.VS2_VMM61_E` and `B310.VS2_VMM62_E`. Those are
+ terms in row 22 (B310). Physically: the secondary-side VS2 meters on
B310 measure flow returning from B311, so both buildings account for
them — B310 subtracts (it's a supply check) and B311 subtracts
(downstream of its own inlets).

**Decision:** edges `B311.VP1_VMM65 → B310.VS2_VMM61` and
`B311.VP1_VMM65 → B310.VS2_VMM62` (B311's first + is VMM65). This
means B310.VS2's deltas are subtracted from B311's sum. B310 itself
still adds them as + terms via `meter_measures`, so B310's own total
is unaffected. Consistent with Excel.

## 2026-04-20 — B326 and B327 both list B326.VS1_VMM61 as + term

Row 37 (B326): +B326.VS1_VMM61 (sole + term)
Row 38 (B327): +B327.VS1_VMM61 +B326.VS1_VMM61

Excel double-counts B326.VS1_VMM61 between B326 and B327. The ontology
attributes each meter to exactly one building (first + wins, row 37
claims it for B326).

**Consequence:** B327 building total will be lower than Excel by
Δ(B326.VS1_VMM61). Annotate as `excel_bug` in
`excel_comparison_annotations.csv` after validation.

## 2026-04-20 — B385.VP2_VMM62_E attributed to campus (sub-only)

`B385.VP2_VMM62_E` appears only as a − term (row 22 AR column) and
never as a +. Attribute to campus (blank `building_id`). Its delta is
subtracted from B310's pool via hasSubMeter, and its own meter_net is
not re-added to any building.

## 2026-04-20 — Dual-building label normalisation

- Row 9 label `"202,203,204,205,209"` → normalise to **B203** (the
  only Excel + term is `B203.VP1_VMM61_E`, and B203 is the block's
  named anchor).
- Row 27/40 label `330/331` → normalise to **B330** (mirrors snv_anga).
