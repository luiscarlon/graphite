# Excel tabs inventory

Workbook slice relevant for **Ånga**. The `Ånga` sheet carries the per-building accounting formulas; STRUX is the meter catalog; Avläsning/PME/PME_EL are the underlying reading sources that the accounting formulas XLOOKUP into.

| sheet | rows | cols | hidden | role |
|---|---:|---:|:---:|---|
| Intro | 28 | 3 |  | workbook documentation — what each tab does |
| Rapport Site | 114 | 26 |  | site-level rollup |
| Rapport Byggnad | 109 | 31 |  | per-building rollup |
| Total GTN | 124 | 32 |  | purchased-energy totals for external reporting |
| EL | 65 | 27 |  | electricity per-building accounting |
| Kyla | 63 | 24 |  | cooling per-building accounting |
| Värme | 60 | 26 |  | heating per-building accounting |
| Ånga | 60 | 23 |  | steam per-building accounting — this workstream |
| Kallvatten | 57 | 26 |  | cold-water per-building accounting |
| Kyltornsvatten | 55 | 23 |  | cooling-tower-water per-building accounting |
| STRUX | 476 | 23 |  | meter catalog — one row per meter with monthly values; XLOOKUP target for all media sheets |
| Kontroll FV-mätare | 58 | 17 |  | district-heating meter verification |
| Evidence Gärtuna | 114 | 32 |  | stakeholder evidence dump |
| VÅ9 alla mätare | 120 | 18 |  | VÅ9 (heat-pump recovery) meter inventory |
| VÅ9 Nyckeltal | 21 | 15 |  | VÅ9 KPIs |
| PME_EL | 418 | 17 |  | automatic electricity readings |
| PME | 380 | 18 |  | automatic non-electricity readings (energy, flow meters) |
| Avläsning | 104 | 34 |  | manual readings (e.g. sea-water meters not connected) |
| Site | 109 | 6 | hidden | building → site lookup (hidden) |
| Lista | 6 | 3 | hidden | enumeration: media types, units (hidden) |

**Named ranges of interest:**

- `STRUX_Mätare` = `STRUX!$D$3:$D$4923` — meter ID column; XLOOKUP target from all media sheets.
- `STRUX_data` = `STRUX!$H$3:$S$4923` — monthly values (Jan..Dec) for every meter in STRUX.
- `STRUX_mån` = `STRUX!$H$2:$S$2` — monthly header row.
- `Avläs_data` / `Avläs_mätare` / `Avläs_mån` — the same pattern for manually-recorded meters.
- `PME_data` / `PME_mätare` / `PME_mån` — the same for automatic (BMS) meters.
- `EL_data` / `EL_mätare` / `EL_mån` — same for electricity meters.
- `Site_GTN` = `Site!$A$1:$B$64` — building → site lookup used by the media sheets' col A.

**Per-row accounting formula used on every media sheet (col C..N):**

```
= XLOOKUP(S{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)
+ XLOOKUP(T{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)
− XLOOKUP(U{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)
− XLOOKUP(V{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)
− XLOOKUP(W{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)
```

Semantics: S/T are *additive* supply meters (flows into this building); U/V/W are *subtractive* — meters downstream of the supply that belong to other buildings and get attributed in their own rows. The subtraction is what encodes topology in the accounting view.
