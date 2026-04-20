# Excel tabs inventory

Workbook slice relevant for **Sjövatten**. The `Sjövatten` sheet carries the per-building accounting formulas; STRUX is the meter catalog; Avläsning/PME/PME_EL are the underlying reading sources that the accounting formulas XLOOKUP into.

| sheet | rows | cols | hidden | role |
|---|---:|---:|:---:|---|
| Intro | 29 | 3 |  | workbook documentation — what each tab does |
| Rapport Site | 116 | 26 |  | site-level rollup |
| Rapport Byggnad | 110 | 31 |  | per-building rollup |
| Total SNV | 125 | 32 |  |  |
| Lena | 28 | 16 |  |  |
| EL | 183 | 27 |  | electricity per-building accounting |
| Värme | 71 | 44 |  | heating per-building accounting |
| Ånga | 75 | 28 |  | steam per-building accounting — this workstream |
| Kyla | 78 | 24 |  | cooling per-building accounting |
| Kallvatten | 104 | 34 |  | cold-water per-building accounting |
| Sjövatten | 107 | 36 |  |  |
| STRUX | 521 | 19 |  | meter catalog — one row per meter with monthly values; XLOOKUP target for all media sheets |
| Kontroll FV-mätare | 46 | 17 |  | district-heating meter verification |
| Evidence Snäckviken | 112 | 32 |  |  |
| PME_EL | 418 | 19 |  | automatic electricity readings |
| PME | 380 | 17 |  | automatic non-electricity readings (energy, flow meters) |
| Avläsning | 101 | 34 |  | manual readings (e.g. sea-water meters not connected) |
| Site | 109 | 6 | hidden | building → site lookup (hidden) |
| Lista | 7 | 3 | hidden | enumeration: media types, units (hidden) |

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
