# Crosswalk notes — gtn_anga

The crosswalk (`meter_id_map.csv`) maps a single physical meter across three different naming conventions encountered in the sources. All 21 facit meters were resolved.

## Columns

| column | source | authority |
|---|---|---|
| `facit_id` | output of `parse_flow_schema.py` on `V600-52.E.8-001.pdf` | drawings (flödesschema) |
| `snowflake_id` | `METER_ID` column in the BMS daily-aggregated export | live data |
| `strux_id` | col D (`Mätarbeteckning`) on the `STRUX` sheet, filtered to `Mediaslag = Ånga, Avläsning = Automatisk` | Excel's XLOOKUP key on the media sheets |
| `excel_used` | whether the `strux_id` appears in a formula on the `Ånga` sheet (`01_extracted/excel_meters_used.csv`) | — |

## Normalisation rule used

The three sources disagree on two axes:

- `VMM` vs `VM` (an M is dropped) — `B611.Å1_VMM71` (facit) ↔ `B611.Å1_VM71` (STRUX/snowflake)
- optional `_E` suffix — `B600N.Å1_VMM71` (facit) ↔ `B600N.Å1_VMM71_E` (STRUX/snowflake)

For each facit ID, candidates are probed in order `{fid, fid+_E, base_vm, base_vm+_E}` against each target namespace. First hit wins. The resolution is deterministic and auditable.

## Findings

**All 21 facit meters have a Snowflake match.** The BMS always has the meter regardless of whether Excel and STRUX know about it.

**19 of 21 have a STRUX entry / Excel usage.** The 2 missing ones are the meters that only the flow schema surfaces:

- `B611.Å1_VMM72` — side-tap on the 3 BAR branch. The Excel accounting subsumes it into B611's total via the `B611.VM71 + B611.VM73 − B622.VM72` formula, so STRUX has no entry for it.
- `B642.Å1_VMM71` — downstream of `B642.VMM72` on the 1.5 BAR side. Excel only uses `B642.VM72` as B614's subtractive term, which implicitly includes all of B642's downstream consumption.

Both of these meters **do** emit in Snowflake (`B611.Å1_VM72` and `B642.Å1_VM71` respectively), so they're available for the conservation check. They just aren't named in the Excel allocation formulas.

**One naming-drift case between STRUX and Snowflake:** `B616.Å1_VMM71`

| source | ID |
|---|---|
| facit | `B616.Å1_VMM71` |
| snowflake | `B616.Å1_VMM71_E` |
| STRUX (Excel) | `B616.Å1_VM71` |

The STRUX sheet uses the `_VM71` (no M, no _E) form as its internal key; the Excel formulas look it up under that name, and STRUX presumably pulls the underlying reading from PME (whose `B616.Å1_VMM71_E` matches Snowflake). The disagreement is internal to the source system — the physical meter is the same one. No action required for our parse beyond recording the mapping.

## Confidence values

- `high` — both snowflake and STRUX have a match after normalisation.
- `medium` — only snowflake has a match (flow-schema-only meters).
- `low` — no snowflake match (none currently, but reserved for cases where a meter exists only in drawings).

## When to rebuild this

Rebuild the crosswalk if: a new meter appears in the flow schema, the Snowflake export date range shifts enough to include new commissioning, STRUX is edited (new rows), or the naming conventions drift further. The rebuild script lives inline in this workstream's history — record future runs by date if meaningful.
