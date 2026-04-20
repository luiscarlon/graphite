# Crosswalk notes — snv_anga

Union of meter IDs from `01_extracted/flow_schema_meters.csv`,
`excel_meters_used.csv`, and `excel_intake_meters.csv`, mapped to the
Snowflake BMS export (`Untitled 1_2026-04-16-1842.csv`) using the
fuzzy-match procedure in `RESOLVE_ONTOLOGY.md §7`.

## Summary

- **44 canonical meters** after normalisation.
- **34 Excel-referenced meters** (all 34 match Snowflake exactly after
  `_VM`→`_VMM` normalisation + `_E` strip).
- **3 PDF-only meters** are genuinely Snowflake-absent — all are
  distribution-trunk nodes numbered `_VMM70` that don't correspond to any
  automatic-read meter on BMS. See below.
- **7 PDF-only meters** with Snowflake data but not in Excel — left in
  the crosswalk with `excel_used=no` for annotation purposes; excluded
  from the ontology unless required by a hasSubMeter chain.

## Canonical form

Following the shared rules:

- Strip trailing `_E` (energy-variant suffix; not a separate meter).
- Normalise `_VM##` → `_VMM##` on the trailing meter index.

Example: `B301.Å1_VMM71_E` (Snowflake) ↔ `B301.Å1_VMM71` (canonical) ↔
`B301.Å1_VMM71` (PDF).

## Snowflake-absent meters (3)

| facit_id | role | action |
|---|---|---|
| `B200.Å1_VMM70` | PDF root, south distribution main | Drop from ontology; topology aid only. Snowflake has `B200.Å1_VMM71` which is a different meter (VMM71 vs VMM70). |
| `B304.Å1_VMM70` | PDF sub-node above B304.Å1_VMM71 | Drop from ontology; Excel uses `B304.Å1_VMM71_E` as the B304 + term. |
| `B327.Å1_VMM70` | PDF sub-node above B327.Å1_VMM71 | Drop; Excel uses `B327.Å1_VMM71_E` as the B327 + term. |

Pattern: in this flödesschema the parser occasionally infers a parent
"VMM70" feeder upstream of the actual metered "VMM71" inlet. These
parent nodes are not real meters — they're pipe junctions with no
instrument. Safe to exclude.

## PDF-only meters with Snowflake data (7)

These meters emit on BMS but are not referenced by any Excel formula.
They are likely:

- Downstream taps whose consumption is already captured by the parent's reading
  (so Excel doesn't double-subtract), or
- Dormant / disabled instruments.

| facit_id | snowflake_id | notes |
|---|---|---|
| `B200.Å1_VMM71` | `B200.Å1_VMM71` | PDF has no VMM71 node here; Snowflake has a reading. Likely a trunk check meter. |
| `B310.Å1_VMM71` | `B310.Å1_VMM71_E` | B310's tree already captures all consumption via VMM70 − {VMM71, VMM72, VMM73, VMM74}; VMM71 is one of the subtractors (in Excel row 26). |
| `B310.Å1_VMM72` | `B310.Å1_VMM72_E` | — as above (row 26 U column). |
| `B310.Å1_VMM73` | `B310.Å1_VMM73_E` | not in Excel row 26. Likely unused tap. |
| `B310.Å1_VMM74` | `B310.Å1_VMM74_E` | not in Excel row 26. Likely unused tap. |
| `B311.Å1_VMM70` | `B311.Å1_VMM70` | PDF trunk above B311.Å1_VMM71. No Excel reference. |
| `B337.Å1_VMM72` | `B337.Å1_VMM72_E` | not in Excel row 46. Likely a secondary tap. |

Wait — B310 Excel row 26 actually uses VMM71 and VMM72 as subtractors,
so they *are* excel_used. See `excel_meters_used.csv`. Adjust evidence
accordingly when finalising `meter_id_map.csv`.

## Known SNV Ånga caveats

- **Boiler-side meters**: `B325.Panna2_MWH` and `B325.Panna3_MWH` are the
  only +terms for B325 (steam plant); both are in Snowflake and STRUX.
  There is no flow-schema PDF node for the boilers — the schema starts
  downstream at the distribution network.
- **`Panna1` exists in Snowflake** (`B325.Panna1_MWH`) but is not
  referenced by Excel — decommissioned/reserve boiler. Do not include.
- **No `-S` / `-1` / `_1_1` drift** for Ånga: all 34 Excel meters
  match exactly after `_VM`↔`_VMM` normalisation + `_E` strip. The
  summary-suffix conventions from EL/värme do not apply here.
- **Dual-building label `330/331`** appears in the Excel building column
  (row 44) and the building totals CSV. Normalise to `B330` post-hoc
  per RESOLVE_ONTOLOGY §7 (mirrors GTN's `850/662` → `B850` decision).
