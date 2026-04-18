# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **4** edges
- `flow_schema`: **19** edges
- `naming`: **6** edges
- `timeseries`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **3**
- single-source (1 source only):          **19**
- direction conflicts (A↔B):              **2**

## Direction conflicts — require a `force_direction` decision

| meters | source(s) saying A→B | source(s) saying B→A |
|---|---|---|
| `B611.Å1_VMM72` ↔ `B611.Å1_VMM73` | `B611.Å1_VMM73 → B611.Å1_VMM72` [flow_schema] | `B611.Å1_VMM72 → B611.Å1_VMM73` [naming] |
| `B642.Å1_VMM71` ↔ `B642.Å1_VMM72` | `B642.Å1_VMM72 → B642.Å1_VMM71` [flow_schema] | `B642.Å1_VMM71 → B642.Å1_VMM72` [naming] |

## Confirmed — ≥2 independent sources agree

| from | to | sources |
|---|---|---|
| `B612.Å1_VMM71` | `B613.Å1_VMM71` | excel_formula, flow_schema |
| `B612.Å1_VMM71` | `B641.Å1_VMM71` | excel_formula, flow_schema |
| `B614.Å1_VMM71` | `B642.Å1_VMM72` | excel_formula, flow_schema |

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (1 edges)

| from | to |
|---|---|
| `B611.Å1_VMM71` | `B622.Å1_VMM72` |

### flow_schema (14 edges)

| from | to |
|---|---|
| `B600N.Å1_VMM71` | `B616.Å1_VMM71` |
| `B600N.Å1_VMM71` | `B643.Å1_VMM71` |
| `B600N.Å1_VMM71` | `B833.Å1_VMM71` |
| `B600N.Å1_VMM71` | `B921.Å1_VMM71` |
| `B600S.Å1_VMM71` | `B611.Å1_VMM71` |
| `B600S.Å1_VMM71` | `B611.Å1_VMM73` |
| `B600S.Å1_VMM71` | `B612.Å1_VMM71` |
| `B600S.Å1_VMM71` | `B612.Å1_VMM72` |
| `B600S.Å1_VMM71` | `B614.Å1_VMM71` |
| `B600S.Å1_VMM71` | `B614.Å1_VMM72` |
| `B600S.Å1_VMM71` | `B621.Å1_VMM70` |
| `B600S.Å1_VMM71` | `B821.Å1_VMM71` |
| `B600S.Å1_VMM71` | `B841.Å1_VMM71` |
| `B611.Å1_VMM73` | `B622.Å1_VMM72` |

### naming (4 edges)

| from | to |
|---|---|
| `B600N.Å1_VMM71` | `B600S.Å1_VMM71` |
| `B611.Å1_VMM71` | `B611.Å1_VMM72` |
| `B612.Å1_VMM71` | `B612.Å1_VMM72` |
| `B614.Å1_VMM71` | `B614.Å1_VMM72` |

## Orphans — meters with no parent edge in any source

Excel's formulas classify these:
- `terminal_leaf_per_excel`: input-only to a building with no
  downstream term. Parser orphaning is correct.
- `missing_parent`: listed as a child in an Excel formula but no
  source emits a specific parent edge. Candidate for `add`.
- `absent_from_excel`: not referenced anywhere in Excel formulas.
  Needs a PDF walk-through; likely sensor-only or naming drift.

| meter | verdict | detail |
|---|---|---|
| `B600N.Å1_VMM71` | `terminal_leaf_per_excel` | +input to B600; no downstream in Excel |

