# decisions — gtn_kyltornsvatten (built 2026-04-19)

Built from scratch per RESOLVE_ONTOLOGY.md. No PDF exists for this media. Simplest workstream in the project: 7 buildings, each with a single +term meter, no subtractions, no coefficients.

## 2026-04-19 — Crosswalk: 4/7 match Snowflake; 3 are Excel-only inactive

| Excel meter_id | Snowflake | notes |
|---|---|---|
| B611.V2_VM21 | exact match | standard |
| B612.V4_INT_VERK2 | exact match | standard |
| B614-V2-GF4 | B614.V2_GF4 | dash→dot normalization |
| B621-52-V2-INT_VERK2 | — | STRUX-less, Excel cache=0 for B621 Jan–Feb |
| B625.V2_VM21_V | exact match | standard |
| B654-55-V2 | — | STRUX-less, Excel cache=0 for B654 Jan–Feb |
| B661-52-V2-MQ43 | — | STRUX-less, Excel cache=0 for B661 Jan–Feb |

The three system-code Excel IDs (`-52-`, `-55-`) follow the same pattern as gtn_kyla's `B821-55-KB2-VMM1`: legacy Excel labels for manually-read meters that are currently not in use. STRUX has no cached value for any of them. Since their Excel cells evaluate to 0 during the comparison window, the crosswalk leaves them with blank Snowflake IDs and they produce no topology artifacts.

## 2026-04-19 — Topology: trivial

All 7 formulas are `=S` (single +term, T through W slots empty). No hasSubMeter edges, no feeds, no virtuals. Each + term meter attributed to its own building.

## 2026-04-19 — Result

- 7 meters (4 with Snowflake data + 3 Excel-only inactive).
- 0 edges, 0 virtuals.
- **47/47 match Jan, 43/43 match Feb** (Excel cache for many buildings is just 0 because the media is only reported at a few buildings; the "offender" count is 0 across all buildings).
- 0 Brick validation violations.
