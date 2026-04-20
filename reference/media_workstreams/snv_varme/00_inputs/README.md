# 00_inputs — snv_varme

Read-only mirror (symlinks) of the source artifacts used to build this workstream.

| symlink | target | role |
|---|---|---|
| `flow_schema.pdf` | `reference/flow_charts/V390-56.8-001.pdf` | Flödesschema — authoritative for topology (distributionsnät Värme, SNV) |
| `overview.pdf` | `reference/flow_charts/V390-56.1-001.pdf` | Översiktsritning — meter inventory cross-check |
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/snv.xlsx` | Site-specific monthly reporting; sheet `Värme` |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**Document dates:** flow schemas are `FÖRVALTNINGSHANDLING` dated 2025-02-26 (Creanova for AstraZeneca Södertälje Snäckviken, system Värme, area B3xx).

**Timeseries source:** `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`. Subset used via `slice_timeseries.py`.

**Known SNV värme quirks to watch for (from GTN värme completion):**
- Naming-heuristic edges (VP1→VS1, VP1→VÅ9, VMM61→VMM62 chain) frequently contradict Excel. Drop every naming edge that doesn't appear as a `hasSubMeter` implied by an Excel `− term`.
- PDF arrows can disagree with Excel on direction; Excel wins on + / − roles (see RESOLVE_ONTOLOGY §0 "Excel is facit").
- Outage patches on offline primary meters (see memory "feedback_ontology_rebuild_safety"): only use children that Excel treats as subordinates of the parent.
- Apply `_VM##` → `_VMM##` normalisation + strip trailing `_E` (shared rule).
