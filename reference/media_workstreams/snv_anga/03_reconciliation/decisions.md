# Reconciliation decisions — snv_anga

Excel-is-facit build. Source of truth per §0 of `RESOLVE_ONTOLOGY.md`:
Excel formulas on the `Ånga` sheet dictate each meter's + / − role and
therefore its building attribution. The flow-schema PDF (`V390-52.E.8-001`)
is used only where Excel is silent on pipe direction.

## 2026-04-20 — Crosswalk — all 34 Excel meters match Snowflake exactly

**Question:** Does the SNV ånga crosswalk need any of the GTN-EL /
SNV-EL tail-segment conventions (`-1`, `_1_1`, dash↔underscore drift)?

**Sources:**
- `01_extracted/excel_meters_used.csv` — 34 unique meters
- `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`

**Decision:** no. After normalising `_VM##` → `_VMM##` and stripping
the `_E` energy-variant suffix, all 34 Excel meters match Snowflake IDs
exactly. Ånga keeps the clean pattern already documented for GTN ånga.
See `02_crosswalk/crosswalk_notes.md`.

**Consequence:** `02_crosswalk/meter_id_map.csv` is 44 rows (34 Excel
meters + 7 PDF-only meters with Snowflake data + 3 PDF-only meters that
are genuinely Snowflake-absent — all three are distribution-trunk nodes
`_VMM70` that don't correspond to any automatic instrument).

## 2026-04-20 — Row-23 parser bug: AB23 wiped by $B$23 substitution

**Question:** Why did `parse_reporting_xlsx.py` skip B307's 10-term
formula (row 23) even though `parse_formula_terms` correctly returns 10
terms when called directly?

**Sources:**
- `openpyxl` dump of Ånga sheet row 23 — formula text includes
  `XLOOKUP(AB23, …)` referencing column AB (double-letter).
- `extract_building_formulas` passes `row_cells` including `$B$23` +
  unescaped `B23`. The bare `B23` substring matched `B23` inside
  `AB23`, converting `AB23` into `A(307.0)` → regex
  `XLOOKUP\(([A-Z]+)(\d+)…` fails to match → the span count
  drops from 10 to 9 → the function hit the
  `len(resolved_spans) != len(spans)` bail-out and returned `{}`.

**Decision:** fix the parser. Replace the two `str.replace` calls with a
regex `re.sub` that anchors with `(?<![A-Z0-9])` /`(?![0-9])` lookarounds
so `$B$23` substitution cannot bleed into `AB23`. Verified:
- B307 row now produces 10 term rows in `excel_formulas.csv`.
- GTN ånga extraction is byte-identical before and after the fix
  (regression check via `diff /tmp/gtn_anga_regress/excel_formulas.csv
  gtn_anga/01_extracted/excel_formulas.csv`).

**Consequence:** Edit in
`reference/scripts/parse_reporting_xlsx.py::parse_formula_terms`.
Future SNV media with AA/AB-column formulas (values.sql suggests EL
has them too) will parse correctly.

## 2026-04-20 — B330.Å1_VMM71 conflict: row 23 (B307) vs row 46 (B337)

**Question:** B330.Å1_VMM71 is subtracted by B307's 10-term pool
formula (row 23) AND by B337's 2-term formula (row 46). A meter can have
only one hasSubMeter parent. Which one wins?

**Sources:**
- `01_extracted/excel_formulas.csv` rows 23 and 46
- Precedent: `gtn_el` B612 double-subtraction → direct edge to the most
  specific downstream parent (decisions.md for gtn_el).

**Decision:** assign B330.Å1_VMM71 as a hasSubMeter child of
**B337.Å1_VMM71** (row 46, 2-term). Shorter formulas are typically
direct physical sub-meter chains; long pool formulas are accounting
aggregators. Drop the B307→B330 edge.

**Consequence:** B307's topology-computed building total will be
higher than Excel by Δ(B330.Å1_VMM71). Annotate this as `excel_bug` in
`05_ontology/excel_comparison_annotations.csv` after validation. B330
and B337 accounting remains correct.

## 2026-04-20 — B302.Å1_VMM72_E attributed to campus (not B302)

**Question:** B302.Å1_VMM72_E is subtracted by B302 row 19 but never
appears as a + term in any building formula. Where does it attribute?

**Decision:** attribute to campus (blank `building_id`). The meter is a
hasSubMeter child of B302.Å1_VMM71 (intra-building sub-meter). Attributing
VMM72 to B302 would double-count — the subtraction is already captured
via `meter_net = ΔVMM71 − ΔVMM72 − …`. Campus-attribution removes
VMM72's own delta from B302's building total. Pattern documented in
`RESOLVE_ONTOLOGY §5` (building_virtuals / meter_measures semantics).

**Consequence:** one campus-attributed meter in the SNV ånga set.

## 2026-04-20 — B325 boilers are upstream of the flödesschema

**Question:** `B325.Panna2_MWH` and `B325.Panna3_MWH` appear in the
Excel formula for B325 (row 40) and in Snowflake/STRUX, but do not
appear in the flow-schema PDF. The PDF root is `B200.Å1_VMM70`
(south distribution trunk), not B325.

**Sources:**
- `RESOLVE_ONTOLOGY §10 "Known risks" — boiler-side meters sit
  upstream of the schema entry point`.
- `01_extracted/flow_schema_meters.csv` — no Panna nodes.
- `01_extracted/excel_formulas.csv` row 40 — the B325 formula is
  `Panna2 + Panna3 − B390.Å1_VMM70_E`.

**Decision:** include the two Panna meters as standalone + terms
attributed to B325, with a hasSubMeter edge
`B325.Panna2_MWH → B390.Å1_VMM70_E` to mirror the B390 subtraction.
Mark both Panna meters as PDF-absent in the ontology (flow schema
starts downstream of them). `B325.Panna1_MWH` exists in Snowflake but
is NOT in any formula — treat as decommissioned, exclude.

## 2026-04-20 — Dual-building label "330/331" → B330

**Question:** Row 44 uses the dual-building label `330/331` and the
cached Excel building-totals file has `B330/331` as the key.

**Decision:** normalise to **B330** (the lower ID), following GTN's
`850/662 → B850` precedent (RESOLVE_ONTOLOGY §7). The three + terms on
row 44 (B330.VMM71_E, B330.VMM72_E, B330.VMM73_E) all carry the `B330.`
prefix, so the label canonicalises cleanly.

**Consequence:** `excel_building_totals.csv` B330/331 row must be
renamed to B330 before assembly. Meters.csv uses `330` in the `building`
column.

## 2026-04-20 — "339 Kolfilter" building label → B339

**Question:** Row 48 uses the label `339 Kolfilter` (kolfilter =
carbon-filter, likely a process-water filter house). Row 47 uses bare
`339`. Snowflake and STRUX refer to `B339.Å1_VMM70_E` without the
"Kolfilter" suffix.

**Decision:** normalise to **B339**. The + term `B339.Å1_VMM70_E` is a
regular meter; the label is just an Excel bookkeeping comment.
