# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **17** edges
- `flow_schema`: **0** edges
- `naming`: **0** edges
- `timeseries`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **0**
- single-source (1 source only):          **17**
- direction conflicts (A↔B):              **0**

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (17 edges)

| from | to |
|---|---|
| `B209.T21` | `B209.T21-4-6` |
| `B209.T21` | `B209.T32-2-2` |
| `B209.T21` | `B209.T32-2-4` |
| `B209.T21` | `B209.T32-4-2` |
| `B308.T57` | `B308.T57-3-2` |
| `B308.T57` | `B308.T57-4-7` |
| `B308.T57` | `B308.T58-4-2` |
| `B310.T27-12-2` | `B317.T49-4-2` |
| `B310.T27-12-2` | `B317.T49-4-3` |
| `B310.T27-12-2` | `B317.T49-5-5` |
| `B310.T27-12-2` | `B317.T49-5-6` |
| `B310.T27-12-2` | `B317.T49-5-9` |
| `B312.T34` | `B312.T34-2-3` |
| `B312.T34` | `B312.T34-2-4` |
| `B312.T34` | `B312.T34-2-5` |
| `B334.T87` | `B334.T87-5-2` |
| `B334.T87` | `B334.T88-4-2` |

