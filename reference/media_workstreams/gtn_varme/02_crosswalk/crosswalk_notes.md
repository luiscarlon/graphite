# Crosswalk notes — gtn_varme

## Scope

61 meters in the union of flow-schema + Excel Värme sheet. Of those:

- **53 emit live data in Snowflake** (matched via the same VMM↔VM, ±`_E` normalisation we use for gtn_anga).
- **8 are in the flow schema but never emit** and don't appear in the Excel either — candidate interpretation: planned meters that were never installed, or removed before the export window opens (2025-01-01).
- **54 are on the flow schema** (parsed from `V600-56.8-001.pdf`).
- **46 are referenced in the Excel Värme tab** accounting formulas.

## Meters drawn but silent

These 8 meter labels appear on the flow schema but have no Snowflake timeseries and are not in any Excel formula row. Flag them as unknown-state; operations should confirm whether they exist physically.

- `B613.VP1_VMM62`
- `B616.VS1_VMM61`
- `B621.VÅ9_VMM41`
- `B631.VP1_VMM61`
- `B661.VS1_VMM61`
- `B674.VÅ9_VMM41`
- `B674.VÅ9_VMM42`
- `B821.VS1_VMM61`

## Meters referenced by Excel but not on the schema

These 7 meter IDs appear in Excel formulas but aren't drawn on `V600-56.8-001.pdf`. All 7 **do** emit in Snowflake, so they're real installed meters. Interpretation: the flow schema's draftsperson omitted them, or they were commissioned after the schema's 2025-02-26 draft date.

- `B612.VP2_VMM64` (Snowflake: `_E`)
- `B612.VP2_VMM65`
- `B613.VP2_VMM61`
- `B616.VP1_VMM61` (Snowflake: `_E`)
- `B631.VP1_VMM62`
- `B661.VP1_VMM61` (Snowflake: `_E`)
- `B821.VP1_VMM61` (Snowflake: `_E`)

## Naming normalisation

Same rule as gtn_anga:

- strip `_E` suffix if present
- `VMM##` ↔ `VM##` (drop one M)

Candidate order when probing each source: `{fid, fid+_E, fid_vm, fid_vm+_E}`. First hit wins.

For värme, the `_E` suffix behaviour differs from ånga — Snowflake uses `_E` for all energy meters in this domain, regardless of whether it's VP, VS, or VÅ9. Easy to strip mechanically.

## Sources per meter

`excel_label` in the CSV records the **exact** string used in the Excel S..Z formula cells (may include `_E` or not). `strux_id` is the key the Excel XLOOKUPs resolve against; usually equal to `excel_label` but documented separately in case it drifts.

## Confidence

- `high` — meter has a Snowflake match and is in at least one of (flow schema, Excel).
- `low` — meter has no Snowflake match. Present on flow schema only.

No `medium` cases for värme (unlike ånga where two flow-schema-only meters had Snowflake matches). The dead-in-Snowflake cohort here is drawings-only.
