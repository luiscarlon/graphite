# gtn.xlsx — Other Data (not parsed into meter/relation CSVs)

Data extracted from tabs not covered by the 6 media tabs (EL, Kyla, Värme, Ånga, Kallvatten, Kyltornsvatten).

## FV (Fjärrvärme / District Heating) meters

Source: **Kontroll FV-mätare** tab. 14 building-level district heating meters with Telge Nät (TN) reference numbers. **No FV tab exists in gtn.xlsx** — the Intro tab mentions an "FV" tab but it's missing from the workbook. These meters are read via TN reports, not STRUX/PME.

| AZ meter ID | Building | TN number |
|---|---|---|
| B611.FV1_INT_VERK | B611 | 101503 |
| B612.FV1_INT_VERK | B612 | 101254 |
| B614.VP1_VM1 | B614 | 101192 |
| B616.FV1_INT_VERK | B616 | 101428 |
| B621.FV1_INT_VERK | B621 | 101340 |
| B625.FV1_INT_VERK | B625 | 101424 |
| B634.FV1_INT_VERK | B634 | 101456 |
| B643.FV1_INT_VERK | B643 | 101444 |
| B650.FV1_INT_VERK | B650 | 101427 |
| B674.FV1_INT_VERK | B674 | 101622 |
| B821.FV1_INT_VERK | B821 | 101426 |
| B833.FV1_VM61 | B833 | 101596 |
| B841.FV1_INT_VERK | B841 | 101425 |
| B921.FV1_VMM81_E | B921 | 102482 |

No relations between FV meters — each is a standalone building meter. No coefficients.

## VÅ9 (Heat Recovery) meters

Source: **VÅ9 alla mätare** tab. Detailed production and consumption meters for the VÅ9 heat recovery system. The Värme tab already includes some VÅ9 consumption meters (B611.VÅ9_VMM41_E etc.), but this tab has the full picture including production meters.

### Production meters
| Meter | System | Description |
|---|---|---|
| B611.VÅ9_INT_VERK4 | KT1 | Avspänningsånga |
| B611.VÅ9_INT_VERK5 | KT2 | Avspänningsånga |
| B612.VÅ9_INT_VERK2 | KT1 | Avspänningsånga |
| B612.VÅ9_INT_VERK3 | KT2 | Avspänningsånga |
| B612.VÅ9_MQ44 | TLK2 | Tryckluftskompressor |
| B612.VÅ9_MQ45 | TLK1 | Tryckluftskompressor |
| B614.VÅ9_VMM42_E | KT1 | |
| B616.VÅ9_INT_VERK4 | KT1 | |
| B621.VÅ9_INT_VERK3 | KT1 | |
| B621.VÅ9_MQ4 | Ack-tank VÅ9 | Kondensat |
| B650.VÅ9_MQ41 | VPU1A/B | Värmepump |
| B653.VÅ9_INT_VERK | VPU1/2 | Värmepump |
| B654.VÅ9_MQ41_E | VPU1 | Värmepump |
| B661.VÅ9_MQ41 | VPU8A/B | Värmepump |
| B833.VÅ9_INT_VERK3 | K1 | |

### Consumption meters (in heating sub-stations)
| Meter | System |
|---|---|
| B611.VÅ9_VMM41_E | VP1? |
| B611.VÅ9_VMM43_E | VP2? |
| B612.VÅ9_INT_VERK | VP1? |
| B612.VÅ9_VMM41_E | VP2? |
| B614.VÅ9_VMM41_E | VS1 |
| B616.VÅ9_INT_VERK3 | VV2 |
| B616.VÅ9_VMM41_E | VP2 |
| B616.VÅ9_VMM44_E | VP1 |
| B621.VÅ9_INT_VERK2 | VV1 |
| B621.VÅ9_VMM44_E | VP1 |
| B625.VÅ9_VMM41_E | VS1 |
| B634.VÅ9_VMM41_E | VP1 |
| B643.VÅ9_VMM41_E | VP2 |
| B643.VÅ9_VMM42_E | VP1 |
| B650.VÅ9_MQ42 | VP3 |
| B650.VÅ9_MQ43 | VP1 |
| B650.VÅ9_MQ44 | VV1 |
| B674.VÅ9_INT_VERK_VP1 | VP1 |
| B674.VÅ9_INT_VERK_VP2 | VP2 |
| B674.VÅ9_INT_VERK_VV1 | VV1 |
| B821.VÅ9_MQ41_Energy | |
| B821.VÅ9_MQ42_Energy | VP1 |
| B833.VÅ9_INT_VERK2 | VV1 |
| B833.VÅ9_VMM41_E | VP1 |
| B921.VÅ9_MQ41 | HHW (VP) |

The VÅ9 tab also tracks production vs consumption losses (row 10-11). Some consumption meters overlap with the Värme tab (B611.VÅ9_VMM41_E, B625.VÅ9_VMM41_E, etc.).

## Building → Zone mapping

Source: **Site** tab. Maps buildings to organizational zones/departments. Both sites included.

### Gärtuna
| Zone | Buildings |
|---|---|
| OSD | B611, B612, B613, B614, B615, B616, B621 (T), B621 (I&L), B622, B623, B641, B821 |
| Engineering | B602, B603, B604, B631, B634, B637, B638, B649–B660, B662, B665–B668, B671, B674, B675, B682, B684, B835, B841, B842, B843, B847, B850, B869, B626, B805-830 |
| QC | B642, B643 |
| API | B663, B664 |
| P&L | B620, B625 |
| Steriles | B833 |
| SBC | B834, B921, B951 |

### Snäckviken
| Zone | Buildings |
|---|---|
| Engineering | B201–B205, B209, B312–B314, B316, B318–B320, B322–B326, B328, B339, B341, B342, B345, B346, B348, B349, B351–B353, B359–B361, B381, B385–B387, B403, B420 |
| API | B301–B305, B307–B309, B315, B327, B339 Kolfilter, B343, B344, B357, B358, B382, B393 |
| QC | B207, B216, B217, B228, B354 |
| Respiratory | B310, B311, B317, B334, B337 |
| Steriles | B330, B331, B392 |

## EAN / Contract references

Source: **Evidence Gärtuna** tab.
- Gärtuna electricity: EAN 735999248000070067, TN contract "0067"
- Karlebystugan (auxiliary): EAN 735999248050203507, TN contract "3507"

## Avläsning (Manual Readings)

Source: **Avläsning** tab. Mixed data from both Gärtuna and Snäckviken.

### Already-parsed meters (also in STRUX)
- B612-KB1-PKYL (Kyla, Gärtuna) — src: Vista Produktion Gärtuna
- B833-55-KB1-GF4 (Kyla, Gärtuna) — src: Vista Service Gärtuna

### New meters — Gärtuna
| Meter | Media | Unit | Type | Source |
|---|---|---|---|---|
| B656-52-KV1-VM21 | Kallvatten | m3 | Mätarställning | Mätaravläsning driften |

### New meters — Snäckviken
| Meter | Media | Unit | Type | Source |
|---|---|---|---|---|
| B304-52-V2-AW026 | Sjövatten | m3 | Mätarställning | Mejl energigruppen från Ulf |
| TE-52-V2-GF4:1 Kringlan | Sjövatten | m3 | Förbrukning | Kringlan fjärrkyla |
| TE-52-V2-SCANIA | Sjövatten | m3 | Förbrukning | FV_Frikyla_Flode_Astra |

### TN reference meters (Telge Nät numbers)
Same physical meters as FV list above, referenced by TN number. Source: "TN FV Förbrukningsrapport enkel Astra".

**Gärtuna FV TN:** 101192, 101254, 101340, 101424, 101425, 101426, 101427, 101428, 101444, 101456, 101503, 101596, 101622, 102482

**Snäckviken FV TN:** 101172, 101433, 102079, 102080, 102081, 102815, 120390, 130390, 140390, 150390

**Ånga TN:** 101543-0, 102264, 102266 (Gärtuna)

### KV intake note
Manual readings for cold water intake meters at Gärtuna (meter IDs 10137 and 11064).

## Total GTN — additional meters

Source: **Total GTN** tab.

### SOLPARK (Solar)
| Meter | Description | Unit |
|---|---|---|
| SOLPARK.YTA1_ENERGY | Yta 1 | MWh |
| SOLPARK.YTA2_ENERGY | Yta 2 | MWh |
| SOLPARK.YTA3_ENERGY | Yta 3 | MWh |
| SOLPARK.TOTAL_ENERGY | TOTAL | MWh |

### Spillvatten (Wastewater)
| Meter | Description | Unit |
|---|---|---|
| B600.S1_VM20_V | B600.S1_VM20 | m³ |

## Tabs reviewed but not extracted

- **Intro**: documentation of Excel structure. Mentions an "FV" tab that doesn't exist in the workbook.
- **Rapport Site / Rapport Byggnad**: derived reports, just formulas referencing media tabs. No new data.
- **PME_EL / PME**: raw automated meter readings (Power Monitoring Expert). Source data for STRUX — no new meter IDs beyond what's already parsed.
- **VÅ9 Nyckeltal**: KPI summary referencing VÅ9 alla mätare. No new data.
- **Lista**: unit lookup (EL=kWh, Kyla=MWh, Värme=MWh, Ånga=MWh, Kallvatten=m3, Kyltornsvatten=m3).

## Notes for later use
- FV meters should be modeled as Thermal_Power_Meter with database=TN_FV_rapport.
- TN numbers are alternate IDs for the same physical meters, not separate meters.
- Snäckviken meters will be relevant when parsing sne.xlsx.
- SOLPARK meters belong to the solar park entity, not a building.
- VÅ9 production meters (INT_VERK, MQ) are not in the Värme tab formulas — they may need separate handling or a VÅ9-specific model.
- The missing FV tab means FV building consumption is only available from TN reports, not computed from meter formulas like other media.
