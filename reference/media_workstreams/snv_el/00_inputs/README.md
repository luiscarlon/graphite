# 00_inputs — snv_el

| symlink | target | role |
|---|---|---|
| `excel_source.xlsx` | `reference/monthly_reporting_documents/inputs/snv.xlsx` | Monthly reporting; `EL` tab is authoritative for allocation |
| `excel_formula_doc.xlsx` | `reference/monthly_reporting_documents/inputs/formula_document.xlsx` | Cross-site formula reference |

**No flow-schema PDF exists for el** — confirmed via `HF Rörsystem` master index which enumerates only the six flödesscheman (3 media × 2 sites) and none is electricity. Topology from Excel + BMS naming only.

**Snowflake quantity:** `Active Energy Delivered` (kWh, scaled ×0.001 by EL sheet's `$F$5` cell to MWh).

**Meter naming:** EL uses `B###.T##` / `B###.T##-#-#` / `B###.T##-#-#-[A|B]` / `B###.T##S-#-#` (T = transformator/ställverk-station/feeder). A few buildings use the `-S` summary-suffix convention from GTN (e.g. `B313.T26S` — note the `S` is part of the meter ID, not the `-S` suffix). The `-S` suffix convention is applied by the crosswalk builder when exact match fails.

**EL sheet complexity (higher than GTN):**

The SNV EL tab uses heavy "Komplex formel" rows (rows 22, 23, 26, 27, 33, 48) whose coefficients and per-term lists live in helper blocks rows 79–183:

| row | building | formula shape |
|---|---|---|
| 22 | 305 | `$F$5*SUM(C80:C90)` — 11-meter sum |
| 23 | 307 | `$F$5*(SUM(C93:C94) - SUM(C95:C108))` — 2 `+` terms, 14 `−` terms |
| 26 | 310 | `$F$5*((C111-SUM(C112:C121))*0.5 + (C122-C123) + (C124-C125) + (C126*1/3) + (C127-SUM(C128:C140)))` — half-share on T26S pool, third-share on B311.T29, four distinct inlet blocks |
| 27 | 311 | `$F$5*((C143-SUM(C144:C151))*0.5 + (C152*2/3) + (C153-C154) + C155 + (C156-C157) + C158)` — half-share on T26S pool, 2/3-share on B311.T29, six inlet blocks |
| 33 | 317 | `$F$5*(SUM(C161:C163) + (C164-SUM(C165:C169))*0.5)` — half-share on B317.T49 net |
| 48 | 339 | `$F$5*(SUM(C172:C179) - SUM(C180:C183))` — 8 `+` terms, 4 `−` terms |

Additional mixed coefficients on single-line rows:
- Row 11 (B204): `R11*S11 + T11` — 0.75 on S term, 1.0 on T
- Row 12 (B205): `R12*S12 + T12` — 0.25 on S term, 1.0 on T (complement of row 11)
- Row 28 (B312): `R28*(S-T-U-V)` — 0.85 on whole net
- Row 29 (B313): `S + R29*(T-U-V-W-X-Y)` — 0.1 on inner net

**parse_reporting_xlsx.py's `excel_formulas.csv` records a single `faktor` per row**, which is wrong for every row above. Re-parse via `openpyxl.ArrayFormula.text` (see §7 of RESOLVE_ONTOLOGY.md) for rows 11, 12, 22, 23, 26, 27, 28, 29, 33, 48 before writing `facit_accounting.csv`.

The `B305`, `B307`, `B310`, `B311`, `B317`, `B339` helper rows (79+) list the per-term meter IDs in column B — these are the definitive per-term members.
