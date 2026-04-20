# 00_inputs — snv_kallvatten

| symlink | target | role |
|---|---|---|
| `flow_schema.pdf` | `reference/flow_charts/V390-52.B.8-001.pdf` | Flödesschema — distributionsnät Stadsvatten, SNV |
| `overview.pdf` | `reference/flow_charts/V390-52.B.1-001.pdf` | Översiktsritning |
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/snv.xlsx` | sheet `Kallvatten` |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | cross-site formulas |

**Easy media.** GTN kallvatten achieved 100% match with 11 hasSubMeter edges. Expected pattern per `RESOLVE_ONTOLOGY §2`:
- Uniform `B###.KV1_VM##` naming.
- All coefficients 1.0 — no `feeds`, no fractional splits.
- `_V` water-variant suffix on some meters.
- Dual-building Excel labels possible (watch for `330/331`).
