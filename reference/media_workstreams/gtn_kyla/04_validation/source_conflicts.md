# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **13** edges
- `flow_schema`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **0**
- single-source (1 source only):          **13**
- direction conflicts (A↔B):              **0**

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (13 edges)

| from | to |
|---|---|
| `B600-KB2` | `B631.KB1_INTE_VERK2` |
| `B600-KB2` | `B631.KB1_VMM51` |
| `B612-KB1-PKYL` | `B637.KB2_INT_VERK` |
| `B612-KB1-PKYL` | `B638.KB1_INT_VERK1` |
| `B614.KB1_INT_VERK` | `B615.KB1_INT_VERK1` |
| `B614.KB1_INT_VERK` | `B642.KB1_INT_VERK_1` |
| `B623.KB1_INT_VERK1` | `B658.KB2_VMM51` |
| `B623.KB1_INT_VERK1` | `B661.KB1_INTVERK` |
| `B623.KB1_INT_VERK1` | `B821.KB2_VMM1` |
| `B654.KB1_KylEffekt_Ack` | `B637.KB2_INT_VERK` |
| `B654.KB1_KylEffekt_Ack` | `B638.KB1_INT_VERK1` |
| `B821-55-KB2-VMM1` | `B841.KB2_VMM51` |
| `B833-55-KB1-GF4` | `B834.KB2_INT_VERK` |

