# topology_overrides — audit log

| action | from | to | result | reason | date | author |
|---|---|---|---|---|---|---|
| `remove` | `B600N.Å1_VMM71` | `B600S.Å1_VMM71` | applied (removed naming_index_chain) | B600N and B600S are parallel intakes (north/south spine) not series. Conservation check: B600S flow (103 kWh/d) exceeds B600N (63 kWh/d). naming_index_chain wrongly inferred parent-child from N/S naming. | 2026-04-18 | luis |
