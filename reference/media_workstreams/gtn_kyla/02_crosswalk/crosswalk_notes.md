# crosswalk notes — gtn_kyla

Rebuilt 2026-04-19 after nuke, following RESOLVE_ONTOLOGY.md §0 (fuzzy-match before declaring a meter Snowflake-absent).

## Naming conventions observed

| pattern | Excel form | Snowflake form | example |
|---|---|---|---|
| Dash vs dot | `B612-KB1-PKYL` | `B612.KB1_PKYL` | normalize with `non-alphanum stripped` match |
| System code | `B821-55-KB2-VMM1`, `B833-55-KB1-GF4` | no system code | strip `-55-` token |
| VM vs VMM | `B658.KB2_VM51` | `B658.KB2_VMM51_E` | `VM` → `VMM` + `_E` suffix |
| UTF-8 | `B653.KB2_WVÄRME_ACK` | identical | no change needed |

All 23 Excel-referenced physical meters map to Snowflake IDs. Two virtual aggregators (`B600-KB2`, `Prod-600`) have no physical BMS meter — they're pure accounting constructs.

## Ambiguous: B821 cooling meter

Excel has three labels that all refer to one cooling meter in building 821:
- `B821.KB2_VMM1` (auto, STRUX)
- `B821-55-KB2-VMM1` (manual, STRUX) — same meter
- `B821.KB2_VMM51` (auto, STRUX) — appears separately in the STRUX tab

Snowflake has two candidates: `B821.KB2_VMM50_E` and `B821.KB2_VMM51`. Both report 0 delta for the Jan–Feb 2026 comparison window. Chose `B821.KB2_VMM51` as the canonical map (matches one of the STRUX auto IDs exactly). Confidence: medium. Should be revisited when the meter becomes active or when on-site staff confirm which physical device corresponds to Excel's `VMM1` vs `VMM51`.

## B658: Excel=0 but meter live (known pattern)

`B658.KB2_VMM51_E` has real Snowflake consumption (Jan 12.10 MWh, Feb 10.47 MWh) while Excel's B658 kyla cell is 0 for both months. Same pattern as B616 steam and B665.T42-2-1 EL — Excel's STRUX_data value is stale/zero while BMS reads real flow. Topology will report the real consumption; Excel comparison will show this as a known misallocation.
