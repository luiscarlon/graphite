# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **26** edges
- `flow_schema`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **0**
- single-source (1 source only):          **26**
- direction conflicts (A↔B):              **0**

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (26 edges)

| from | to |
|---|---|
| `B611.T1` | `B611.T4-A3` |
| `B611.T1` | `B611.T4-C1` |
| `B611.T1` | `B611.T4-C4` |
| `B611.T1` | `B622.T2-3-1-B1` |
| `B612.T48` | `B612.T8-B5` |
| `B612.T48` | `B612.T8-B6` |
| `B612.T48` | `B615.T7-A2-257` |
| `B612.T48` | `B641.T8-A3` |
| `B612.T48` | `B652.T8-A3-A14-112` |
| `B616.T31` | `B616.T33-6-1` |
| `B616.T31` | `B616.T33-6-2` |
| `B621.T29` | `B621.T5-2-5` |
| `B621.T29` | `B621.T6-2-5` |
| `B621.T29` | `B621.T6-3-1` |
| `B641.T8-A3` | `B652.T8-A3-A14-112` |
| `B643.T37` | `B643.T37-2-1` |
| `B650.T23` | `B650.T23-D5` |
| `B652.T8-A3-A14-112` | `B652.T14-B3-J` |
| `B653.T17` | `B653.T17-A7` |
| `B659.T15` | `B659.T28-3-5` |
| `B665.T42` | `B665.T42-2-1` |
| `B821.T39-1` | `B821.T39-5-1` |
| `B821.T39-1` | `B821.T39-5-2` |
| `B821.T39-1` | `B821.T39-5-3` |
| `B821.T39-1` | `B821.T39-6-2` |
| `B833.T43` | `B833.T44-6-1` |

