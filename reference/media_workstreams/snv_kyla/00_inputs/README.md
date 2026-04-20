# 00_inputs — snv_kyla

Read-only mirror (symlinks). No flow-schema PDF exists for kyla (see
`RESOLVE_ONTOLOGY §2` "Flow-chart PDFs available").

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/snv.xlsx` | Site-specific monthly reporting; sheet `Kyla` |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**Timeseries source:** `reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv`.

**Known kyla quirks (from GTN kyla completion, RESOLVE_ONTOLOGY §2 & §7):**

- `parse_reporting_xlsx.py`'s `excel_formulas.csv` records ONE `faktor`
  per row applied uniformly — wrong when rows use `$R{n}` cell factors
  (apply only to first term) or mixed inline coefficients (e.g.
  `0.8×S + 0.9×T − 0.9×U`). **Always re-parse formula text directly
  via `openpyxl.ArrayFormula.text` and rebuild per-term coefficients
  before writing `facit_accounting.csv`.**
- Fractional subtractions (0.9×term, 0.1×term) have no `views.sql`
  primitive. Expect 1–3 MWh residuals on affected buildings;
  don't pad measured_flow to close the per-day gap.
- Cross-building accounting virtuals (GTN had `B600-KB2 pool`,
  `Prod-600`). SNV may have analogous aggregators.
- Dead source meters create negative building values — keep them in
  the ontology; don't prune.
- Bi-daily BMS sensors possible (GTN had `B833.KB1_GF4` sampling ~31
  times over 59 days). Negative residual is a sampling artifact, not
  an ontology error.
- Dash vs dot separator: Excel uses `B612-KB1-PKYL` (dashes),
  Snowflake uses `B612.KB1_PKYL` (dot+underscore). Canonicalise first
  dash to dot, remaining to underscores.
- `_ACK` suffix = accumulator. The non-`_ACK` variant is typically
  instantaneous power, NOT the same meter.
