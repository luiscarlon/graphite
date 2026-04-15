# snv.xlsx — Other Data (not parsed into meter/relation CSVs)

Data extracted from tabs not covered by the 6 media tabs (EL, Kyla, Värme, Ånga, Kallvatten, Sjövatten).

## Lena tab — B212-area and B341 meters

Source: **Lena** tab. Manual tracking sheet for two building groups: B212-area (rows 10–15) and B341 (rows 19–27). 13 meter rows total.

### Block 1 — B212-area

| Meter ID | Media | Unit |
|---|---|---|
| B212.V2_VM51 | Sjövatten | m³ |
| B229.V2_VM51 | Sjövatten | m³ |
| B230.V2_VM51 | Sjövatten | m³ |
| B409.V2_GF4 | Sjövatten | m³ |
| B209.KB6_VMM51 | Kyla | MWh |
| B212.KB5 | Kyla | MWh |

### Block 2 — B341

| Meter ID | Media | Unit |
|---|---|---|
| B341.T60 | EL | kWh |
| B341.T61 | EL | kWh |
| B341.T62 | EL | kWh |
| B341.T63 | EL | kWh |
| B341.KB1 | Kyla | MWh |
| B341.KV1_VM21_V | Kallvatten | m³ |
| B341.VS1_VMM61_E | Fjärrvärme | MWh |

Note: B341 EL rows include two "Summa" aggregation rows (Summa kWh, Summa MWh) which are not physical meters.

## FV (Fjärrvärme / District Heating) meters

Source: **Kontroll FV-mätare** tab. 10 Snäckviken district heating meters with Telge Nät (TN) reference numbers.

| AZ meter ID | TN number |
|---|---|
| B203.FV1_MQ4_E | 100420 |
| B216.FV1_VMM61_E | 102815 |
| B308.FV1_VMM61_E | 102081 |
| B310.FV1_VMM61 | 120390 |
| B310.FV1_VMM62 | 150390 |
| B310.FV1_VMM63 | 130390 |
| B310.FV1_VMM64 | 140390 |
| B318.FV1_VMM80 | 102080 |
| B330.FV1_INT_VERK_E | 101172 |
| B334.VP1_VMM1_E | 101433 |
| B339.FV1_VMM61_E | 102079 |

Note: B310 has four sub-meters (VMM61–VMM64) each with their own TN number. The tab cross-checks AZ values against TN meter readings; small diffs are floating-point rounding.

## EAN / Contract references

Source: **Evidence Snäckviken** tab.

| EAN | Contract ref | Description | Media |
|---|---|---|---|
| 735999248000070661 | TN 0661 | B324 ASTRA A — Snäckviken+Elpanna | Electricity (site total incl. boiler) |
| 735999248000070678 | TN 0678 | B324 ASTRA A — AZ Elpanna only | Electricity (boiler sub-meter) |

The tab splits TN 0661 into AZ Elpanna (0678) and the remainder TN Snäckviken to allow apples-to-apples comparison with AZ meter B324.H4-1 and B324.H3.

The tab also carries TN meter reading cross-checks for Kallvatten (serial numbers 23772635, 23772633, 53989390, 23793258, 23793257, 68844912, 68844913, 73353516) covering buildings B409, B334, B217, and B310. These are Telge Nät physical serial numbers, not AZ meter IDs.

## Total SNV — additional meters and KV serial numbers

Source: **Total SNV** tab.

### Meters not in the 6 media tabs

| Media | Meter ID | Description | Unit |
|---|---|---|---|
| EL | B324.H4-1 | B324.H4-1 (site intake) | MWh |
| EL | B324.H3 | B324.H3 Elpanna Ånga SNV | MWh |
| Spillvatten | B390.S1_VM20_V | B390.S1_VM20 | m³ |
| Sjövatten | B342.V2_VM90_V | B342.V2_VM90_V (intagsmätare) | m³ |
| Sjövatten | B342.V2_VM91_V | B342.V2_VM91_V (intagsmätare) | m³ |
| Sjövatten | TE-52-V2-GF4:1 Kringlan | Kringlan fjärrkyla | m³ |
| Sjövatten | TE-52-V2-SCANIA | Scania fjärrkyla | m³ |

Note: B324.H4-1 and B324.H3 are the physical EL intake meters reconciled against TN contracts 0661/0678. Sjövatten intake meters B342.V2_VM90_V and B342.V2_VM91_V are the site-level seawater intakes; TE-52-V2-GF4:1 Kringlan and TE-52-V2-SCANIA are external customer deliveries (not building consumption).

### KV physical meter serial numbers

| AZ meter ID | Physical serial | Notes |
|---|---|---|
| B334.KV1_VM21 | 23772633 | Tidigare (old) serial: 10607 |
| B311.KV1_VM26_V | 11065 | Description labels it B310-KV1-VM21_1 |

The other KV meters in the tab (B409.KV1_VM21, B390.KV1_VM25_V, B217.KV1_VM001, B217.KV1_VM002) have no physical serial listed in the description field.

### Ånga physical meter

| AZ meter ID / TN | Description | Unit |
|---|---|---|
| 101543-0 | Bravida Elpanna | MWh |

This is the Ånga TN meter for the steam boiler at Snäckviken. Already noted in gtn_other_data.md Avläsning section as "Ånga TN: 101543-0".

## Building → Zone mapping

Source: **Site** tab (columns E/F). Snäckviken only.

| Zone | Buildings |
|---|---|
| Engineering | B201, B202, B203, B204, B205, B209, B312, B313, B314, B316, B318, B319, B320, B322, B323, B324, B325, B326, B328, B339, B341, B342, B345, B346, B348, B349, B351, B352, B353, B359, B360, B361, B381, B385, B386, B387, B389, B390, B403, B420 |
| API | B301, B302, B303, B304, B305, B307, B308, B309, B315, B327, B339 Kolfilter, B343, B344, B357, B358, B382, B393 |
| QC | B207, B216, B217, B228, B354 |
| Respiratory | B310, B311, B317, B334, B337 |
| Steriles | B330, B331, B392 |

Note: The tab also contains combined-building rows (B204/205, B202,203,204,205,209, B330/331) which are reporting aggregates, not distinct buildings; they are omitted from the table above.

### Differences vs gtn_other_data.md

gtn_other_data.md was derived from the same Site tab but parsed from gtn.xlsx. The SNV site section in snv.xlsx adds three buildings absent from gtn_other_data.md:

- **B389** (Engineering) — not listed in gtn_other_data.md
- **B390** (Engineering) — not listed in gtn_other_data.md

All other SNV buildings match exactly between the two files. The Gärtuna side of the Site tab is identical between the two workbooks.

## Tabs reviewed but not extracted

- **Intro**: documentation of Excel structure and tab overview. No meter data.
- **Rapport Site**: derived report pulling from media tabs via formulas. No new data.
- **Rapport Byggnad**: per-building derived report. Formula references only, no new meter IDs.
- **PME_EL**: raw Power Monitoring Expert EL readings. Source data already captured in the EL tab; no new meter IDs.
- **PME**: raw PME readings for other media. Source data already captured in media tabs.
- **Lista**: unit lookup table (EL=kWh, Kyla=MWh, Värme=MWh, Ånga=MWh, Kallvatten=m³, Sjövatten=m³). Reference only.
- **STRUX**: meter registry / STRUX system export. Reference list; all meter IDs are subsets of the media tabs already parsed.
