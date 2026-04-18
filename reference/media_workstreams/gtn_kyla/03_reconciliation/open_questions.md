# Open questions — gtn_kyla

## Dead-meter cascade blocking 2026 accounting for 9 buildings

Excel's Kyla sheet references several meters that stopped emitting in Snowflake before 2026-01-01. Because Kyla's accounting formulas use virtual meters (`B600-KB2`, `Prod-600`) that sum physical meters, one dead leaf blocks an entire subtree.

| dead meter | last seen | blocks |
|---|---|---|
| `B653.KB2_WVÄRME_ACK`  | 2025-10-09 | `Prod-600`, `B600-KB2` → 611, 613, 621 (T), 622 (via factor 0.38 / 0.03 on `B600-KB2`) |
| `B616.KB1_PKYL`        | 2025-06-13 | 616 (directly in its formula) |
| `B654.KB2_Pkyl_Ack`    | 2025-02-10 | `Prod-600`, `B600-KB2` (still listed but long since dead) |
| `B821-55-KB2-VMM1`     | never in Snowflake | 821 (Excel formula references this meter ID, Snowflake doesn't carry it — likely decommissioned or typo for `B821.KB2_VMM51`) |
| `B833-55-KB1-GF4`      | never in Snowflake | 833 (same — Snowflake has only `B833.VÅ9_*` for this building) |

**Total impact:** 9 of 25 formula buildings (+ 2 virtuals) cannot be validated against the Excel's reported Jan/Feb 2026 totals because one or more of their referenced meters has no 2026 data.

## Recommended actions (reconciler)

1. **Verify with AstraZeneca facilities**: is `B653.KB2_WVÄRME_ACK` a failed sensor, replaced by a different tag, or intentionally taken out of service? If replaced, add a crosswalk `B653.KB2_WVÄRME_ACK → <new_tag>` to resurrect downstream accounting.
2. **Fix the Excel formula** for B821: does `B821-55-KB2-VMM1` correspond to `B821.KB2_VMM51` (VMM1 likely typo for VMM51)? Confirm via STRUX catalog.
3. **Fix the Excel formula** for B833: does `B833-55-KB1-GF4` correspond to one of the `B833.VÅ9_INT_VERK*` meters, or is this a meter that was never installed?
4. **Replace `_ACK` with non-`_ACK` where applicable**: `B653.KB2_WVÄRME` (without `_ACK`) is still emitting but has many reset_days — worth checking if that's the accumulator's replacement.

## B658 — meter emits real consumption but Excel records zero

Same pattern as B616 (ånga): `B658.KB2_VMM51` shows ~12 MWh Jan 2026 and ~11 MWh Feb 2026 in Snowflake, but Excel Kyla sheet row for B658 reports `0` both months. Either:
- The meter is physically live but legally excluded from this accounting (tenant carve-out, building reassignment)
- The Excel's B658 row is missing a formula and should reference this meter

Needs confirmation from whoever maintains the Excel.
