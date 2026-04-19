# topology_overrides — audit log

| action | from | to | result | reason | date | author |
|---|---|---|---|---|---|---|
| `remove` | `B616.VP1_VMM62` | `B661.VS1_VMM61` | applied (removed flow_schema_V600-56.8-001/auto_root_degree) | PDF labels B661 meter as VS1 but Excel/Snowflake use VP1. Same physical meter. Replacing with canonical VP1 ID. | 2026-04-19 | luis |
| `add` | `B616.VP1_VMM62` | `B661.VP1_VMM61` | applied | B661's sole heating meter is labeled VS1 in PDF but VP1 in Excel/Snowflake. Same physical meter (same VMM61 index). Using canonical VP1. | 2026-04-19 | luis |
| `remove` | `B612.VP2_VMM63` | `B612.VP2_VMM64` | applied (removed naming_index_chain) | naming_index_chain is wrong for B612. Excel formula adds VMM62+63+64+65 as parallel zone meters — all are + terms. They are siblings under VMM61 not a sequential chain. | 2026-04-19 | luis |
| `add` | `B612.VP2_VMM61` | `B612.VP2_VMM64` | applied | B612.VP2_VMM64 is a parallel zone meter under VMM61 (not sequential after VMM63). Excel confirms: all VP2 sub-meters in B612 are additive terms. | 2026-04-19 | luis |
| `remove` | `B612.VP2_VMM64` | `B612.VP2_VMM65` | applied (removed naming_index_chain) | Same as VMM64: VMM65 is a sibling not a child of VMM64. Excel confirms parallel structure. | 2026-04-19 | luis |
| `add` | `B612.VP2_VMM61` | `B612.VP2_VMM65` | applied | B612.VP2_VMM65 is a parallel zone meter under VMM61. All VP2 sub-meters in B612 are additive per Excel formula. | 2026-04-19 | luis |
| `remove` | `B674.VP1_VMM61` | `B674.VÅ9_VMM42` | applied (removed naming_role_hierarchy) | Naming VP1→VÅ9_42 conflicts with PDF arrow VÅ9_42→VP2 creating cycle VP1→VÅ9_42→VP2→VÅ9_41→VP1. PDF arrows are authority for B674 heat recovery direction. | 2026-04-19 | luis |
| `remove` | `B674.VP2_VMM61` | `B674.VÅ9_VMM41` | applied (removed naming_role_hierarchy) | Naming VP2→VÅ9_41 conflicts with PDF arrow VÅ9_41→VP1 creating cycle. Same as VÅ9_42 case. | 2026-04-19 | luis |
| `remove` | `B821.VP1_VMM61` | `B821.VS1_VMM61` | applied (removed naming_role_hierarchy) | PDF labels B821 meter as VS1; Excel/Snowflake use VP1. Same physical meter (same VMM61 index). Removing self-reference. | 2026-04-19 | luis |
| `remove` | `B643.VP2_VMM61` | `B643.VÅ9_VMM42` | applied (removed naming_role_hierarchy) | Naming VP2→VÅ9_42 combined with PDF VÅ9_42→VP1 creates VP2→VÅ9_42→VP1 chain. Excel shows VP1 and VP2 as independent parallel inputs (both are + terms). VP2 is not upstream of VP1. | 2026-04-19 | luis |
