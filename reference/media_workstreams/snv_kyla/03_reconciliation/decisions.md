# Reconciliation decisions — snv_kyla

Excel-is-facit build. No flow-schema PDF — topology is derived
entirely from Excel + BMS naming.

## 2026-04-20 — `parse_formula_terms` col-R fallback was clobbering correct per-term coefficients

**Question:** Why do kyla rows 22 (B305) and 23 (B307) report `faktor=0.5`
on both S and T terms when the formula is
`XLOOKUP(S) + R22*XLOOKUP(T) + XLOOKUP(U) − …`?

**Sources:**
- `01_extracted/excel_formulas.csv` before fix (both S and T flagged 0.5).
- Direct re-parse via `openpyxl.ArrayFormula.text` on rows 19/20/22/23 —
  only S has the R factor on 19/20, only T has it on 22/23.

**Decision:** fix `parse_reporting_xlsx.py::extract_building_formulas`.
If any term in a row has a non-unit per-term coefficient, the per-term
values become authoritative for ALL terms in that row — including the
unit-coefficient ones. The col-R `factor_cell` fallback only applies
to rows where every per-term coefficient is 1.0 (legacy rows). Verified
on GTN ånga (byte-identical) and GTN kyla (correct diff: B611 row 13 T/U
terms no longer inherit the $R13=0.38 that belonged only to the S term).

**Consequence:** committed `parse_reporting_xlsx.py`. Future kyla
extractions no longer need the documented manual re-parse step
(RESOLVE_ONTOLOGY §7 caveat). The GTN kyla 01_extracted/excel_formulas.csv
could also be regenerated but the workstream is already built from
analyst-curated `facit_accounting.csv`, so no action there.

## 2026-04-20 — Crosswalk: 25/28 Excel meters match Snowflake; 3 STRUX-only

All meters match via shared rules (`_VM##`→`_VMM##`, strip `_E`).
Three Excel-used meters are genuinely absent from Snowflake:
`B202.VENT` (manual vent meter), `B331.KB1_VM51_E` (row 44, B330 + term)
and `B336.KB1` (row 78). These will be annotated `strux_only_meter` in
`excel_comparison_annotations.csv`.

`B392.KB1_VM51_E` exists in Snowflake but only as `Water Volume (m^3)`,
not `Active Energy Delivered(Mega)`. Not usable for the kyla energy
accounting. Treated as strux_only_meter.

## 2026-04-20 — Cooked-coefficient rows 19/20 and 22/23

SNV kyla has far fewer "cooked" rows than GTN kyla — only four:

- Row 19 (B302): `0.5 × B304.KB2` + (T/U/V/W/X empty)
- Row 20 (B303): `0.5 × B304.KB2` + empties
- Row 22 (B305): `B305.KB1 + 0.5 × B307.KB1` + empties
- Row 23 (B307): `B307.KB1_VM52_E + 0.5 × B307.KB1` + empties

Pattern: `B304.KB2` is split 0.5/0.5 between B302 and B303 (tenant
split). `B307.KB1` is split 0.5/0.5 between B305 and B307. The
coefficient lives on the SECOND + term of rows 22/23 (T column) and on
the FIRST + term of rows 19/20 (S column).

**Decision:** write the per-term coefficients to
`facit_accounting.csv::coefficient`. `generate_building_virtuals.py`
will emit `feeds` edges with these coefficients — pre-existing behavior
per the GTN kyla pattern.

**Consequence:** residuals of ~1–3 MWh expected on B302/B303/B305/B307
because `views.sql::meter_net` has no exact fractional-subtract
primitive (see memory "feedback_kyla_fractional"). Classify as
`excel_cooked_coefficient` after validation.

## 2026-04-20 — Fully-split source meters reattributed to campus

Meters whose entire flow is split into virtual aggregators via `feeds`
edges (Σk = 1.0) are attributed to campus (`building_id=''`), not to a
specific building. Applies to: `B304.KB2`, `B305.KB1`, `B307.KB1`,
`B307.KB1_VMM52`. The virtual (`B###.KYLA_VIRT`) carries the building
attribution; the physical meter routes all its flow via feeds.

Numerically identical to attributing the physical meter to its first +
building (since `meter_net = flow × (1 − Σk) = 0` when Σk = 1.0), but
matches the Abbey Road / reference-site convention.

## 2026-04-20 — No − terms in the entire SNV kyla sheet

Unlike ånga / värme / el, the kyla sheet is all + terms. No
`hasSubMeter` edges are required. `facit_relations.csv` is written
with 0 Excel-derived edges; `generate_building_virtuals.py` will
handle the cross-building feeds for the cooked-coefficient rows.

## 2026-04-20 — B331.KB1 attributed to B330 via Excel row 44

Row 44's building column is `330`, + term is `B331.KB1_VM51_E`.
Physically the meter lives on B331 but its accounting credit goes to
B330. The Excel assigns this STRUX-cached value to B330. Since the
meter isn't in Snowflake anyway, the ontology has nothing to
attribute — B330's kyla total will fall short by the full cached value.
Annotate `strux_only_meter`.

## 2026-04-20 — Row 49 "339 Kolfilter" → B339

Same pattern as snv_anga: the label `339 Kolfilter` is an Excel
bookkeeping comment; the meter `B339.KB1_KOLF` attributes to B339.
