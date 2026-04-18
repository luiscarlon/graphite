# source_conflicts

Per-edge agreement/conflict across every extractor in `01_extracted/`.
This file is **advisory** — nothing is applied. Use it to inform
the human reconciliation in `03_reconciliation/decisions.md`.

## Sources consumed

- `excel_formula`: **14** edges
- `flow_schema`: **26** edges
- `vlm_edge_check`: **0** edges

## Summary

- confirmed (≥2 sources, same direction): **9**
- single-source (1 source only):          **22**
- direction conflicts (A↔B):              **0**

## Confirmed — ≥2 independent sources agree

| from | to | sources |
|---|---|---|
| `B611.VP1_VMM61` | `B613.VP1_VMM61` | excel_formula, flow_schema |
| `B611.VP1_VMM61` | `B631.VP1_VMM63` | excel_formula, flow_schema |
| `B614.VS1_VMM61` | `B615.VS1_VMM61` | excel_formula, flow_schema |
| `B621.VP1_VMM61` | `B622.VP1_VMM61` | excel_formula, flow_schema |
| `B621.VP1_VMM61` | `B623.VP1_VMM61` | excel_formula, flow_schema |
| `B621.VP1_VMM61` | `B658.VP1_VMM61` | excel_formula, flow_schema |
| `B637.VP2_VMM61` | `B638.VP2_VMM61` | excel_formula, flow_schema |
| `B650.VP1_VMM61` | `B655.VP1_VMM61` | excel_formula, flow_schema |
| `B833.VP1_VMM61` | `B834.VP1_VMM61` | excel_formula, flow_schema |

## Single-source — candidates for reconciliation review

Grouped by source so the reviewer can weight them against §3's
authority rules (PDF is authoritative for topology; Excel for
accounting; VLM requires human confirmation).

### excel_formula (5 edges)

| from | to |
|---|---|
| `B611.VP1_VMM61` | `B622.VP2_VMM61` |
| `B612.VP2_VMM62` | `B637.VP2_VMM61` |
| `B612.VP2_VMM62` | `B641.VP2_VMM61` |
| `B612.VP2_VMM62` | `B654.VP2_VMM61` |
| `B614.VS1_VMM61` | `B642.VS1_VMM61` |

### flow_schema (17 edges)

| from | to |
|---|---|
| `B611.VP1_VMM61` | `B631.VP1_VMM61` |
| `B612.VP2_VMM61` | `B612.VP2_VMM62` |
| `B612.VP2_VMM61` | `B612.VP2_VMM63` |
| `B612.VP2_VMM61` | `B613.VP1_VMM62` |
| `B612.VP2_VMM61` | `B637.VP2_VMM61` |
| `B612.VP2_VMM61` | `B654.VP2_VMM61` |
| `B612.VP2_VMM63` | `B641.VP2_VMM61` |
| `B615.VS1_VMM61` | `B642.VS1_VMM61` |
| `B616.VP1_VMM62` | `B616.VS1_VMM61` |
| `B616.VP1_VMM62` | `B616.VS2_VMM61` |
| `B616.VP1_VMM62` | `B661.VS1_VMM61` |
| `B631.VP1_VMM61` | `B611.VÅ9_VMM41` |
| `B643.VÅ9_VMM42` | `B643.VP1_VMM61` |
| `B674.VÅ9_VMM41` | `B674.VP1_VMM61` |
| `B674.VÅ9_VMM42` | `B674.VP2_VMM61` |
| `B833.VP1_VMM61` | `B833.VP1_VMM62` |
| `B833.VP1_VMM61` | `B833.VÅ9_VMM41` |

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
| `B611.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B611; no downstream in Excel |
| `B611.VP2_VMM61` | `terminal_leaf_per_excel` | +input to B611; no downstream in Excel |
| `B611.VÅ9_VMM43` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B612.VP2_VMM61` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B612.VÅ9_VMM41` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B614.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B614; no downstream in Excel |
| `B614.VÅ9_VMM41` | `terminal_leaf_per_excel` | +input to B614; no downstream in Excel |
| `B616.VP1_VMM62` | `terminal_leaf_per_excel` | +input to B616; no downstream in Excel |
| `B616.VÅ9_VMM41` | `terminal_leaf_per_excel` | +input to B616; no downstream in Excel |
| `B621.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B621 (T); no downstream in Excel |
| `B621.VÅ9_VMM41` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B625.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B625; no downstream in Excel |
| `B625.VÅ9_VMM41` | `terminal_leaf_per_excel` | +input to B625; no downstream in Excel |
| `B634.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B634; no downstream in Excel |
| `B634.VÅ9_VMM41` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B643.VP2_VMM61` | `terminal_leaf_per_excel` | +input to B643; no downstream in Excel |
| `B643.VÅ9_VMM41` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B643.VÅ9_VMM42` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B650.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B650; no downstream in Excel |
| `B650.VP3_VMM61` | `terminal_leaf_per_excel` | +input to B650; no downstream in Excel |
| `B652.VS1_VMM61` | `terminal_leaf_per_excel` | +input to B652; no downstream in Excel |
| `B674.VÅ9_VMM41` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B674.VÅ9_VMM42` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B821.VS1_VMM61` | `absent_from_excel` | not referenced in any Excel formula — PDF/sensor-only |
| `B833.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B833; no downstream in Excel |
| `B841.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B841; no downstream in Excel |
| `B921.VP1_VMM61` | `terminal_leaf_per_excel` | +input to B921; no downstream in Excel |

