# topology_overrides — audit log

| action | from | to | result | reason | date | author |
|---|---|---|---|---|---|---|
| `remove` | `B623.KB1_INT_VERK1` | `B658.KB2_VMM51` | applied (removed excel_formula_BB600-KB2) | B600-KB2 is a virtual accounting meter. B623 is one of its inputs not physically upstream of B658. The formula B600-KB2 = B623 + B653.ACK + B654.KB2 − B658 − B661 − B821 is accounting not topology. | 2026-04-19 | analyst |
| `remove` | `B623.KB1_INT_VERK1` | `B661.KB1_INTVERK` | applied (removed excel_formula_BB600-KB2) | Same as B658: B600-KB2 accounting formula is not physical topology. | 2026-04-19 | analyst |
| `remove` | `B623.KB1_INT_VERK1` | `B821.KB2_VMM1` | applied (removed excel_formula_BB600-KB2) | Same as B658/B661: B600-KB2 accounting formula is not physical topology. | 2026-04-19 | analyst |
| `remove` | `B600-KB2` | `B631.KB1_INTE_VERK2` | applied (removed excel_formula_B611) | B600-KB2 is a virtual meter (no Snowflake data). B611 formula allocates 38% of B600-KB2 minus B631 meters but this is accounting not pipe topology. | 2026-04-19 | analyst |
| `remove` | `B600-KB2` | `B631.KB1_VMM51` | applied (removed excel_formula_B611) | Same: B600-KB2 is virtual; the 0.38 coefficient is building-level allocation not physical. | 2026-04-19 | analyst |
| `remove` | `B612-KB1-PKYL` | `B637.KB2_INT_VERK` | applied (removed excel_formula_B641) | Coefficient 0.1 is from B641 allocation formula. Physical relationship is hasSubMeter with coefficient 1.0. Removing to re-add with correct coefficient and canonical ID. | 2026-04-19 | analyst |
| `remove` | `B612-KB1-PKYL` | `B638.KB1_INT_VERK1` | applied (removed excel_formula_B641) | Same: coefficient 0.1 is B641 allocation. Re-adding as hasSubMeter. | 2026-04-19 | analyst |
| `remove` | `B654.KB1_KylEffekt_Ack` | `B637.KB2_INT_VERK` | error (edge not present to remove) | B654 is a production meter not physically upstream of B637. The B612 formula uses 0.8×B654 + 0.9×PKYL − 0.9×B637 which is accounting allocation not topology. | 2026-04-19 | analyst |
| `remove` | `B654.KB1_KylEffekt_Ack` | `B638.KB1_INT_VERK1` | error (edge not present to remove) | Same as B637: B654 production meter has no physical pipe to B638. | 2026-04-19 | analyst |
| `remove` | `B821-55-KB2-VMM1` | `B841.KB2_VMM51` | applied (removed excel_formula_B821) | Removing to re-add with canonical facit_id B821.KB2_VMM1 (system code 55 stripped). | 2026-04-19 | analyst |
| `remove` | `B833-55-KB1-GF4` | `B834.KB2_INT_VERK` | applied (removed excel_formula_B833) | Removing to re-add with canonical facit_id B833.KB1_GF4 (system code 55 stripped). | 2026-04-19 | analyst |
| `add` | `B612.KB1_PKYL` | `B637.KB2_INT_VERK` | applied | Physical hasSubMeter: B612.KB1_PKYL pipe feeds B637 downstream. B612/B641 formulas both subtract B637 from PKYL (0.9/0.1 split is allocation of residual not physical coefficient). | 2026-04-19 | analyst |
| `add` | `B612.KB1_PKYL` | `B638.KB1_INT_VERK1` | applied | Physical hasSubMeter: B612.KB1_PKYL pipe feeds B638 downstream. Same analysis as B637. | 2026-04-19 | analyst |
| `add` | `B833.KB1_GF4` | `B834.KB2_INT_VERK` | applied | Physical hasSubMeter: B833 formula = B833.GF4 − B834.INT_VERK. Canonical ID with system code 55 stripped; B833.KB1_GF4 matches Snowflake. | 2026-04-19 | analyst |
| `add` | `B821.KB2_VMM1` | `B841.KB2_VMM51` | applied | Feeds with allocation: B821 formula = B821.VMM1 − 0.8×B841.VM51. Canonical ID with system code stripped. Both meters currently dead (all-zero Snowflake). | 2026-04-19 | analyst |
