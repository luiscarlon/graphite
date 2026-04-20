# Crosswalk notes — snv_varme

Union of Excel-used + PDF-found + STRUX-listed meter IDs mapped to Snowflake
via the §7 fuzzy-match procedure.

## Summary

- **50 canonical meters** total.
- **46 Excel-referenced meters** — all 46 match Snowflake exactly after
  `_VM##` → `_VMM##` normalisation and `_E` strip.
- **4 PDF-only meters** (not in any Excel formula) with Snowflake data:
  `B203.FV1_MQ4` (district-heating inlet check meter), `B217.VS1_VMM61`
  (secondary-side meter not referenced by Excel), `B310.VP1_VMM62` and
  `B311.VP1_VMM61` (intra-building trunk variants superseded by the
  meters actually referenced).
- **0 Snowflake-absent meters** — cleaner than snv_el and snv_anga.

## Canonical form

Shared rules apply:
- Strip trailing `_E` (energy-variant suffix).
- Normalise `_VM##` → `_VMM##`.

No SNV-specific drift (no `-S`, `-1`, or `_1_1` suffixes for värme).

## Dual-building labels

- `B330/331` on row 27 — normalise to **B330** post-extraction (mirrors
  `snv_anga` and GTN's `B850/662 → B850`).
- `"202,203,204,205,209"` on row 9 — the formula's + term is
  `B203.VP1_VMM61_E`, so the B203 meter's reading covers this 5-building
  block. Normalise the building_totals row to **B203**; the other four
  buildings have zero direct attribution in the Excel formula.

## Non-canonical role tokens observed

- `B337.VP12_VMM61_E` and `B337.VS12_VMM61_E` — the role token is
  `VP12` / `VS12` (two-digit), not the usual VP1/VS1. Both are +terms
  for B337 row 46.
- `B311.VP1_VMM65_E` — index 65, higher than the usual 61/62.

These are preserved as-is in the crosswalk; no canonicalisation is
necessary since the Excel and Snowflake IDs match exactly.

## Notes on PDF-only meters (excluded from ontology unless evidence emerges)

- `B203.FV1_MQ4_E`: "Fjärrvärme 1 mätqvarter 4" — district-heating-side
  check meter. Not in any Excel accounting formula. Dormant.
- `B217.VS1_VMM61_E`: secondary-side (VS1) meter. Excel uses
  `B217.VP1_VMM61_E` (primary) instead. Likely a downstream tap to the
  primary.
- `B310.VP1_VMM62_E`: second primary inlet variant. Excel row 22 uses
  only VP1_VMM61 / VP2_VMM61 / VS2_VMM61 / VS2_VMM62 as + terms;
  VP1_VMM62 would be intra-building and is not referenced.
- `B311.VP1_VMM61_E`: inlet variant not referenced by Excel's B311
  formula (row 23 starts at VMM62). Likely a disconnected trunk node.
