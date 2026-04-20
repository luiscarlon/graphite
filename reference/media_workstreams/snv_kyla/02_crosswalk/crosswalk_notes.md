# Crosswalk notes — snv_kyla

Union of Excel-used + STRUX-listed meter IDs mapped to Snowflake via
the §7 fuzzy-match procedure. No PDF — kyla has no flow-schema.

## Summary

- **33 canonical meters** total.
- **28 Excel-referenced meters** — 25 match Snowflake; 3 are STRUX-only.
- **5 STRUX-only catalog entries** with no Excel usage.

## Canonical form

Shared rules + kyla-specific dash↔dot handling:
- Strip trailing `_E`.
- `_VM##` → `_VMM##`.
- First dash → dot, remaining dashes → underscores
  (e.g. `B612-KB1-PKYL` → `B612.KB1_PKYL`). SNV kyla meters already use
  the dot+underscore form so this has no effect for this workstream, but
  the rule is preserved from GTN kyla practice.

## _E variant preference (lesson from snv_varme)

`find_sf_match` tries the STRUX / Excel-authoritative variant first
before any canonical/toggle match. No ambiguous meters surfaced in
kyla (unlike snv_varme where B203/B330 needed this fix), but the
logic is in place.

## STRUX-only meters (3 with Excel usage, no Snowflake data)

| facit_id | STRUX | building | action |
|---|---|---|---|
| `B202.VENT` | `B202.VENT` | 202 | STRUX-only; no BMS reading. Include with `snowflake_id=""`, annotate as strux_only_meter. |
| `B331.KB1_VMM51` | `B331.KB1_VM51_E` | 330 (row 44) | STRUX-only — neither the `_E` nor bare variant is in Snowflake. Tried `B331.KB1_VM51`, `_E`, `VMM51`, `VMM51_E` all gap. |
| `B336.KB1` | `B336.KB1` | 336 | STRUX-only. Manual-read meter. |

Expected impact on building totals:
- B202: STRUX monthly values won't show up in ontology; delta vs Excel =
  full B202.VENT consumption (likely small / seasonal).
- B330: delta = B331.KB1_VM51_E monthly value (row 44's sole + term).
- B336: delta = entire building consumption.

## Non-standard cooked-coefficient rows (2 identified, well below GTN kyla)

After applying the `parse_formula_terms` fix, the following per-term
coefficients are correctly captured in `excel_formulas.csv`:

| row | building | formula (conceptual) | cooked split |
|---|---|---|---|
| 19 | B302 | `0.5 × B304.KB2` | B304.KB2 split 0.5/0.5 between B302 (row 19) and B303 (row 20) |
| 20 | B303 | `0.5 × B304.KB2` | ″ |
| 22 | B305 | `B305.KB1 + 0.5 × B307.KB1` | B307.KB1 split 0.5/0.5 between B305 (row 22) and B307 (row 23) |
| 23 | B307 | `B307.KB1_VM52_E + 0.5 × B307.KB1` | ″ |

These are tenant splits. Expect ~1–3 MWh residuals per building where
the 0.5×term can't be exactly matched against BMS deltas — per the
kyla memory.

**Much simpler than GTN kyla** (which had $R{n}-per-term, post-factors
`*24*31/1000`, mixed inline coefficients on many rows). SNV kyla only
uses whole-term `$R{n}*` factors on rows 19, 20, 22, 23.

## Dual-building / label normalisation

- Row 44 label `330` (attributes `B331.KB1_VM51_E` as the + term)
  — keep `B330` as the target building; the meter itself carries the
  B331 prefix but the Excel accounting credits B330.
- Row 49 label `"339 Kolfilter"` → normalise to **B339** (mirrors ånga).
- No 5-building blocks here.
