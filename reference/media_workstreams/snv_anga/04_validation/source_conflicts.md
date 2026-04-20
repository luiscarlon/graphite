# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **16** edges
- `flow_schema`: **38** edges
- `naming`: **18** edges
- `timeseries`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **8**
- single-source (1 source only):          **53**
- direction conflicts (A↔B):              **1**

## Direction conflicts — require a `force_direction` decision

| meters | source(s) saying A→B | source(s) saying B→A |
|---|---|---|
| `B311.Å1_VMM70` ↔ `B311.Å1_VMM71` | `B311.Å1_VMM71 → B311.Å1_VMM70` [flow_schema] | `B311.Å1_VMM70 → B311.Å1_VMM71` [naming] |

## Confirmed — ≥2 independent sources agree

| from | to | sources |
|---|---|---|
| `B216.Å1_VMM71` | `B216.Å1_VMM72` | flow_schema, naming |
| `B216.Å1_VMM71` | `B217.Å1_VMM71` | excel_formula, flow_schema |
| `B302.Å1_VMM71` | `B301.Å1_VMM71` | excel_formula, flow_schema |
| `B302.Å1_VMM71` | `B302.Å1_VMM72` | excel_formula, flow_schema, naming |
| `B310.Å1_VMM70` | `B310.Å1_VMM71` | flow_schema, naming |
| `B310.Å1_VMM70` | `B311.Å1_VMM72` | excel_formula, flow_schema |
| `B310.Å1_VMM72` | `B310.Å1_VMM73` | flow_schema, naming |
| `B337.Å1_VMM71` | `B337.Å1_VMM72` | flow_schema, naming |

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (12 edges)

| from | to |
|---|---|
| `B307.Å1_VMM71` | `B216.Å1_VMM71` |
| `B307.Å1_VMM71` | `B302.Å1_VMM73` |
| `B307.Å1_VMM71` | `B311.Å1_VMM71` |
| `B307.Å1_VMM71` | `B330.Å1_VMM71` |
| `B307.Å1_VMM71` | `B334.Å1_VMM71` |
| `B307.Å1_VMM71` | `B337.Å1_VMM71` |
| `B307.Å1_VMM71` | `B339.Å1_VMM70` |
| `B310.Å1_VMM70` | `B313.Å1_VMM71` |
| `B310.Å1_VMM70` | `B313.Å1_VMM72` |
| `B310.Å1_VMM70` | `B317.Å1_VMM71` |
| `B310.Å1_VMM70` | `B317.Å1_VMM72` |
| `B337.Å1_VMM71` | `B330.Å1_VMM71` |

### flow_schema (29 edges)

| from | to |
|---|---|
| `B200.Å1_VMM70` | `B216.Å1_VMM71` |
| `B200.Å1_VMM70` | `B302.Å1_VMM73` |
| `B200.Å1_VMM70` | `B304.Å1_VMM70` |
| `B200.Å1_VMM70` | `B307.Å1_VMM71` |
| `B200.Å1_VMM70` | `B308.Å1_VMM70` |
| `B200.Å1_VMM70` | `B308.Å1_VMM71` |
| `B200.Å1_VMM70` | `B311.Å1_VMM71` |
| `B200.Å1_VMM70` | `B327.Å1_VMM70` |
| `B200.Å1_VMM70` | `B330.Å1_VMM71` |
| `B200.Å1_VMM70` | `B334.Å1_VMM71` |
| `B200.Å1_VMM70` | `B337.Å1_VMM71` |
| `B200.Å1_VMM70` | `B339.Å1_VMM70` |
| `B302.Å1_VMM72` | `B303.Å1_VMM70` |
| `B302.Å1_VMM72` | `B310.Å1_VMM70` |
| `B302.Å1_VMM72` | `B330.Å1_VMM73` |
| `B302.Å1_VMM72` | `B392.Å1_VMM71` |
| `B307.Å1_VMM71` | `B302.Å1_VMM71` |
| `B307.Å1_VMM71` | `B305.Å1_VMM71` |
| `B307.Å1_VMM71` | `B341.Å1_VMM71` |
| `B307.Å1_VMM71` | `B385.Å1_VMM71` |
| `B308.Å1_VMM71` | `B390.Å1_VMM70` |
| `B310.Å1_VMM70` | `B310.Å1_VMM72` |
| `B310.Å1_VMM72` | `B310.Å1_VMM74` |
| `B310.Å1_VMM72` | `B313.Å1_VMM71` |
| `B310.Å1_VMM72` | `B313.Å1_VMM72` |
| `B310.Å1_VMM72` | `B317.Å1_VMM71` |
| `B310.Å1_VMM72` | `B317.Å1_VMM72` |
| `B313.Å1_VMM71` | `B315.Å1_VMM71` |
| `B337.Å1_VMM71` | `B330.Å1_VMM72` |

### naming (12 edges)

| from | to |
|---|---|
| `B302.Å1_VMM72` | `B302.Å1_VMM73` |
| `B304.Å1_VMM70` | `B304.Å1_VMM71` |
| `B307.Å1_VMM71` | `B307.Å1_VMM72` |
| `B308.Å1_VMM70` | `B308.Å1_VMM71` |
| `B310.Å1_VMM71` | `B310.Å1_VMM72` |
| `B310.Å1_VMM73` | `B310.Å1_VMM74` |
| `B311.Å1_VMM71` | `B311.Å1_VMM72` |
| `B313.Å1_VMM71` | `B313.Å1_VMM72` |
| `B317.Å1_VMM71` | `B317.Å1_VMM72` |
| `B327.Å1_VMM70` | `B327.Å1_VMM71` |
| `B330.Å1_VMM71` | `B330.Å1_VMM72` |
| `B330.Å1_VMM72` | `B330.Å1_VMM73` |

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
| `B200.Å1_VMM70` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |

