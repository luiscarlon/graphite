# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **30** edges
- `flow_schema`: **34** edges
- `naming`: **17** edges
- `timeseries`: **0** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **5**
- single-source (1 source only):          **69**
- direction conflicts (A↔B):              **1**

## Direction conflicts — require a `force_direction` decision

| meters | source(s) saying A→B | source(s) saying B→A |
|---|---|---|
| `B311.VP1_VMM61` ↔ `B311.VP1_VMM62` | `B311.VP1_VMM62 → B311.VP1_VMM61` [flow_schema] | `B311.VP1_VMM61 → B311.VP1_VMM62` [naming] |

## Confirmed — ≥2 independent sources agree

| from | to | sources |
|---|---|---|
| `B308.VS1_VMM61` | `B307.VS1_VMM61` | excel_formula, flow_schema |
| `B308.VS1_VMM61` | `B327.VS1_VMM61` | excel_formula, flow_schema |
| `B313.VP1_VMM62` | `B314.VP1_VMM61` | excel_formula, flow_schema |
| `B314.VP1_VMM61` | `B315.VP1_VMM61` | excel_formula, flow_schema |
| `B318.VP1_VMM61` | `B319.VP1_VMM61` | excel_formula, flow_schema |

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (25 edges)

| from | to |
|---|---|
| `B310.VP1_VMM61` | `B301.VP2_VMM61` |
| `B310.VP1_VMM61` | `B301.VP2_VMM62` |
| `B310.VP1_VMM61` | `B302.VP2_VMM61` |
| `B310.VP1_VMM61` | `B302.VP2_VMM62` |
| `B310.VP1_VMM61` | `B303.VP2_VMM61` |
| `B310.VP1_VMM61` | `B304.VP2_VMM61` |
| `B310.VP1_VMM61` | `B304.VP2_VMM62` |
| `B310.VP1_VMM61` | `B305.VP2_VMM61` |
| `B310.VP1_VMM61` | `B311.VP1_VMM62` |
| `B310.VP1_VMM61` | `B311.VP1_VMM64` |
| `B310.VP1_VMM61` | `B311.VP1_VMM65` |
| `B310.VP1_VMM61` | `B311.VS2_VMM61` |
| `B310.VP1_VMM61` | `B312.VP2_VMM61` |
| `B310.VP1_VMM61` | `B312.VP2_VMM62` |
| `B310.VP1_VMM61` | `B313.VP1_VMM62` |
| `B310.VP1_VMM61` | `B313.VS1_VMM61` |
| `B310.VP1_VMM61` | `B317.VP1_VMM61` |
| `B310.VP1_VMM61` | `B317.VP1_VMM62` |
| `B310.VP1_VMM61` | `B317.VP1_VMM63` |
| `B310.VP1_VMM61` | `B341.VS1_VMM61` |
| `B310.VP1_VMM61` | `B385.VP2_VMM61` |
| `B310.VP1_VMM61` | `B385.VP2_VMM62` |
| `B311.VP1_VMM62` | `B310.VS2_VMM61` |
| `B311.VP1_VMM62` | `B310.VS2_VMM62` |
| `B311.VP1_VMM62` | `B381.VP1_VMM61` |

### flow_schema (28 edges)

| from | to |
|---|---|
| `B203.VP1_VMM61` | `B201.VP1_VMM61` |
| `B203.VP1_VMM61` | `B207.VP1_VMM61` |
| `B203.VP1_VMM61` | `B216.VP1_VMM61` |
| `B310.VP1_VMM62` | `B313.VS1_VMM61` |
| `B310.VP1_VMM62` | `B317.VP1_VMM61` |
| `B310.VP1_VMM62` | `B317.VP1_VMM63` |
| `B310.VP2_VMM61` | `B301.VP2_VMM61` |
| `B310.VP2_VMM61` | `B301.VP2_VMM62` |
| `B310.VP2_VMM61` | `B302.VP2_VMM61` |
| `B310.VP2_VMM61` | `B302.VP2_VMM62` |
| `B310.VP2_VMM61` | `B303.VP2_VMM61` |
| `B310.VP2_VMM61` | `B304.VP2_VMM61` |
| `B310.VP2_VMM61` | `B304.VP2_VMM62` |
| `B310.VP2_VMM61` | `B305.VP2_VMM61` |
| `B310.VP2_VMM61` | `B312.VP2_VMM61` |
| `B310.VP2_VMM61` | `B312.VP2_VMM62` |
| `B310.VP2_VMM61` | `B341.VS1_VMM61` |
| `B310.VP2_VMM61` | `B385.VP2_VMM61` |
| `B310.VP2_VMM61` | `B385.VP2_VMM62` |
| `B311.VP1_VMM65` | `B381.VP1_VMM61` |
| `B311.VS2_VMM61` | `B310.VP1_VMM62` |
| `B311.VS2_VMM61` | `B310.VS2_VMM61` |
| `B311.VS2_VMM61` | `B310.VS2_VMM62` |
| `B311.VS2_VMM61` | `B311.VP1_VMM62` |
| `B311.VS2_VMM61` | `B311.VP1_VMM65` |
| `B311.VS2_VMM61` | `B313.VP1_VMM62` |
| `B313.VP1_VMM62` | `B317.VP1_VMM62` |
| `B327.VS1_VMM61` | `B326.VS1_VMM61` |

### naming (16 edges)

| from | to |
|---|---|
| `B217.VP1_VMM61` | `B217.VS1_VMM61` |
| `B301.VP2_VMM61` | `B301.VP2_VMM62` |
| `B302.VP2_VMM61` | `B302.VP2_VMM62` |
| `B304.VP2_VMM61` | `B304.VP2_VMM62` |
| `B310.VP1_VMM61` | `B310.VP1_VMM62` |
| `B310.VP1_VMM61` | `B310.VS2_VMM61` |
| `B310.VP1_VMM61` | `B310.VS2_VMM62` |
| `B310.VS2_VMM61` | `B310.VS2_VMM62` |
| `B311.VP1_VMM61` | `B311.VS2_VMM61` |
| `B311.VP1_VMM62` | `B311.VP1_VMM64` |
| `B311.VP1_VMM64` | `B311.VP1_VMM65` |
| `B312.VP2_VMM61` | `B312.VP2_VMM62` |
| `B313.VP1_VMM62` | `B313.VS1_VMM61` |
| `B317.VP1_VMM61` | `B317.VP1_VMM62` |
| `B317.VP1_VMM62` | `B317.VP1_VMM63` |
| `B385.VP2_VMM61` | `B385.VP2_VMM62` |

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
| `B203.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B202,203,204,205,209; no downstream in Excel |
| `B308.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B308; no downstream in Excel |
| `B310.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B310; no downstream in Excel |
| `B310.VP2_VMM61` | `terminal_leaf_per_excel` | +input to B310; no downstream in Excel |
| `B318.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B318; no downstream in Excel |
| `B325.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B325; no downstream in Excel |
| `B330.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B330/331; no downstream in Excel |
| `B334.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B334; no downstream in Excel |
| `B339.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B339; no downstream in Excel |

