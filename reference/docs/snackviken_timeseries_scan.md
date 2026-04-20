# Snäckviken per-timeseries data-quality scan

Scan over every preferred counter ref in the six SNV workstreams (snv_anga,
snv_el, snv_kallvatten, snv_kyla, snv_sjovatten, snv_varme). Source data:
`data/sites/snackviken/readings.csv` (assembled daily counter values) and
`reference/media_workstreams/*/01_extracted/timeseries_daily.csv` (raw per-meter
deltas). Heuristics: non-monotonic deltas, flat runs ≥4d during active season,
spikes > max(3·p99, 10·median), upper-IQR outliers > 10·Q3, zero-with-sibling-flow
runs ≥7d, and stitch-artifact > 1 % for derived rolling_sum refs.

Discovery only — no annotations, refs, or YAML touched.

## Summary

| medium         | n_anomalies | covered by existing primitives | new-pattern candidates |
|----------------|------------:|-------------------------------:|-----------------------:|
| snv_anga       |          41 |                             22 |                     19 |
| snv_el         |          26 |                             17 |                      9 |
| snv_kallvatten |          53 |                             15 |                     38 |
| snv_kyla       |           7 |                              3 |                      4 |
| snv_sjovatten  |           9 |                              4 |                      5 |
| snv_varme      |          34 |                              9 |                     25 |

**Cross-medium event — 2026-01-14 synchronized catch-up.** At least 9 preferred
counters across värme (B310.VP2_VMM61, B313.VP1_VMM62, B311.VP1_VMM64),
kallvatten (B310.KV1_VMM23_V, B310.KV1_VMM20_V, B313.KV1_VMM22_V,
B317.KV1_VMM21_V) and anga (B315.Å1_VMM71, B317.Å1_VMM72) froze between
2025-09-20 and 2025-09-22, stayed flat for 114–116 days, and caught up in a
single-day delta on 2026-01-14. Estimated ~4 MWh värme + ~2 MWh KV + ~1.3 MWh
anga lost to "lump on resume day" distortion. These meters appear to share a
BMS poll path (buildings B310/B313/B315/B317). None of the existing primitives
distribute the catch-up back over the frozen window — this is the top
new-pattern finding.

---

## snv_anga

| meter | anomaly | date/range | magnitude (MWh) | context | primitive / new pattern |
|-------|---------|------------|----------------:|---------|-------------------------|
| B217.Å1_VMM71 | iqr_hi + non_monotonic | 2025-07-15..2025-10-10 (17 spike days, 6 neg) | 4024 / 3228 | 805k-band register artifacts leak into `:d` output; peak delta 805 173 | **REGRESSION** of `bracket` patch (already annotated `ann-snv-anga-b217-register-corruption`). Bracket drops samples in `:d.raw` but the stitched `:d` still emits them via V_LAST aggregation — needs investigation. |
| B325.Panna3_MWH | flat_run 66d + 6 runs totalling 213d | 2025-12-23..2026-02-26 biggest | 6028 | Steam boiler, median 28.3 MWh/d; may be seasonal shutdown vs. dead meter | new: need Panna-family seasonal mask, or annotate as standby |
| B307.Å1_VMM71 | zero_with_sibling 194d | 2025-01-02..2025-07-14 | 7981 (flat_run sum) | Pre-swap quiet period — meter dead before documented 2025-07-31 swap. Annotated `ann-snv-anga-b307-vmm71-swap` only covers the swap boundary | extend rolling_sum: need pre-swap offline segment, or sum-children patch |
| B304.Å1_VMM71 | flat_run 6 runs, Σ=74d | 2025-07-10..2025-08-10 (32d biggest) | 1967 | Summer-season outage on leaf meter, no annotation | new: unnotated outage; candidate for sum-children or ext-offline tag |
| B308.Å1_VMM71 | flat_run 85d + zero_with_sibling 24d | 2025-11-13..2026-02-05 | 1556 / 1258 | Frozen counter, already on sum-patch from 2026-02-07; pre-patch window still dead | annotated `ann-snv-anga-b308-frozen` — extend patch valid_from back to 2025-11-13 |
| B325.Panna2_MWH | flat_run 10d | 2025-07-14..2025-07-23 | 1298 | July mid-summer shutdown; matches B325 Panna3/Panna4 family | likely real outage cluster — verify siblings, else outage annotation |
| B315.Å1_VMM71 | flat_run 114d | 2025-09-22..2026-01-13 | 1143 | 2026-01-14 cluster — part of site-wide catch-up event | **NEW: interpolate primitive over frozen window** |
| B302.Å1_VMM71 | flat_run 11 runs Σ=83d | 2025-12-19..2026-01-06 (19d biggest) | 694 | Highly intermittent reporting across the whole year | new: "intermittent-reporting" pattern — cannot distinguish real-zero from lost-reading |
| B334.Å1_VMM71 | flat_run 9d | 2025-07-15..2025-07-23 | 252 | July cluster (7 meters flatline same week) | sum-children if available, else outage annotation |
| B317.Å1_VMM72 | flat_run 156d + spike 135 | 2025-09-22..2026-01-13 + 2026-01-14 | 192 / 135 | 2026-01-14 cluster | **interpolate primitive** |
| B337.Å1_VMM71 | flat_run 17d | 2025-07-15..2025-07-23 | 134 | Part of mid-July cluster | sum-children / outage annotation |
| B339.Å1_VMM70 | flat_run 18d + zero_with_sibling 7d | 2025-07-14..2025-07-24 + 2025-12-23..2025-12-29 | 86 + 33 | July cluster + winter mini-outage | outage annotation or sum-children |
| B311.Å1_VMM71 | flat_run 10d | 2025-07-14..2025-07-23 | 80 | Mid-July cluster | outage annotation |
| B317.Å1_VMM71 | flat_run 6 runs Σ=62d | 2026-01-22..2026-02-20 (30d) | 78 | Feb 2026 window — affects facit | flag for human review; no sibling to patch from |
| B216.Å1_VMM71 | flat_run 9d | 2025-07-15..2025-07-23 | 46 | July cluster | sum-children (B217 child exists) already used in annotation — extend window |
| B301.Å1_VMM71 | flat_run 6 runs Σ=98d | 2025-06-14..2025-08-05 (53d) | 34 | Long summer outage on leaf | outage annotation |
| B339.Å1_VMM70 | zero_with_sibling 7d | 2025-12-23..2025-12-29 | 33 | Short winter outage coincident with B325.Panna3 | outage annotation |
| B303.Å1_VMM70 | flat_run 7 runs Σ=78d | 2025-12-13..2026-01-06 (25d) | 31 | Intermittent reporter | intermittent pattern |
| B311.Å1_VMM72 | flat_run 26 runs Σ=199d | 2025-12-18..2026-01-04 (18d) | 28 | Very low-value meter reporting only sporadically | intermittent pattern |
| B307.Å1_VMM72 | flat_run 17d | 2025-12-19..2026-01-04 | 12 | Inside existing swap annotation window | extend `ann-snv-anga-b307-vmm72-swap` |

*Not flagged but worth manual check*: the B217.Å1_VMM71 bracket-patch regression
is load-bearing for the August–October 2025 anga totals. A quick spot-check on
`readings.csv` for that meter will confirm whether the `:d.clip` source is being
honoured at assemble-time or silently dropped. The 2026-01-14 catch-up cluster
is tightly correlated with kallvatten/värme peers in the same buildings — treat
those three media's fixes as one batch.

---

## snv_el

| meter | anomaly | date/range | magnitude (kWh) | context | primitive / new pattern |
|-------|---------|------------|----------------:|---------|-------------------------|
| B328.T20-4-1 | flat_run 8d | 2025-07-08..2025-07-15 | 4136 | Single summer outage on medium-load feeder (517 kWh/d median); not annotated | new: short outage annotation or sum-children if T20-4-1 has sub-feeders |
| B307.T10-7-6 | flat_run 6 runs Σ=27d | 2025-07-29..2025-08-03 | 2139 | Intermittent summer reporter | intermittent pattern |
| B209.T21-4-6 | flat_run 8 runs Σ=57d | 2025-05-07..2025-05-18 (12d) | 1139 | Intermittent / low-flow | intermittent pattern |
| B313.T26S-3-16 | flat_run 63d + zero_w/sibling 63d | 2025-08-12..2025-10-13 | 251 + 219 | Pre-offline window; annotated `snv_el_B313_T26S_3_16_offline` from 2025-12-10 | extend annotation valid_from back to 2025-08-12 |
| B313.T26S-3-24 | flat_run 34 runs Σ=227d | 2025-05-28..2025-06-06 | 227 | 1 kWh/d meter — probably near-idle device | new: low-flow intermittent; tolerate as noise or annotate as idle |
| B207.T94-4-7 | flat_run 3 runs Σ=14d | 2025-07-13..2025-07-17 | 3 | Tiny feeder | no action |
| B307.T10-5-2, T10-6-5, T10-7-3, T10-7-7 | flat_run 300+d, near-zero | Whole year | < 1 | All annotated offline; residual flat noise before offline date is expected | no-op — existing annotations cover |
| B324.T14-4-1 | flat_run 44 runs Σ=357d | 2025-02-03..2025-02-14 | 0.4 | Essentially-idle meter | no action / intermittent-tolerate |
| B317.T49-4-7 | flat_run 32 runs Σ=340d | 2025-09-10..2025-10-09 | 0.3 | Before annotated offline — low magnitude | no action |
| B209.T32-2-4 | flat_run 59 runs Σ=336d | 2025-04-06..2025-04-14 | 0.3 | Idle feeder | no action |
| B307.T10-7-7 | flat_run 49 runs Σ=324d | 2025-06-27..2025-07-10 | 0.3 | Idle feeder | no action |
| B307.T10-5-3 | flat_run 23 runs Σ=120d | 2025-07-15..2025-07-24 | 0.1 | Idle feeder | no action |
| B328.T19-3-4 | flat_run 19 runs Σ=82d | 2025-06-11..2025-06-15 | 0.1 | Idle feeder | no action |
| B307.T10-6-2 | flat_run 10d | 2025-06-24..2025-06-29 | 0 | Idle feeder | no action |

*Not flagged but worth manual check*: spikes have been suppressed here because
most T71-1 / T73-1 feeders have strongly bimodal load (median ~150 kWh/d, p95
~8 MWh/d). The 12 273 kWh peak on B339.T71-1 (2025-06-26) is 85× median but
only 1.5× p99 — i.e. within the meter's own upper band. snv_el's biggest data
loss risk is `B328.T20-4-1` and short summer outages on medium-load feeders
rather than the high-value trunks.

---

## snv_kallvatten

| meter | anomaly | date/range | magnitude (m³) | context | primitive / new pattern |
|-------|---------|------------|---------------:|---------|-------------------------|
| B308.KV1_VMM23_V | iqr_hi 12 days | ~Mar–May 2025 | 2878 | Sustained high-delta band (219–366 m³/d vs Q3=22) — not a spike; possible leak or operational change | **new**: "level-shift" pattern; not a transient spike, not swap — needs human review before patching |
| B330.KV1_VMM23_V | flat_run 21d | 2025-01-21..2025-02-10 | 2673 | Largest single outage in KV, not annotated; 127 m³/d normal | outage annotation or sum-children patch |
| B302.KV1_VMM21_V | iqr_hi 22 days (77–164 m³/d vs Q3=5.8) | scattered | 2031 | Annotated swap (Jan-09). High-delta days may be post-swap calibration burst | extend swap annotation or add calibration note |
| B310.KV1_VMM23_V | spike + flat + zero_w/sibling, all same window | 2025-09-22..2026-01-14 | 1963 + 1839 | **2026-01-14 cluster** (see summary) | **interpolate primitive** |
| B203.KV1_VMM22_V | iqr_hi 52 days (10–30 m³/d vs Q3=0.9) | scattered | 1516 | Bimodal/seasonal usage — flag as pattern, not anomaly | tolerate / probably legitimate |
| B389.BRV1_VMM21 | flat_run Σ=150d + spike 261 on 2026-02-03 | 2025-12-17..2026-02-03 | 459 + 261 | Annotated swap 2025-10-17. Post-swap flat runs + catch-up spike | extend annotation; candidate for interpolate post-swap |
| B317.KV1_VMM22_V | flat_run 127d + zero_w/sibling 127d | 2025-09-09..2026-01-13 | 281 + 289 | Annotated offline from 2026-02-21, but long pre-offline silence — extend valid_from back | amend annotation |
| B318.KV1_VMM21_V | spike 2d (biggest 161 m³, 11× p99) | 2025-10-01 | 161 | Single-day anomaly — leak, or manual hose fill? | flag for operator review |
| B317.KV1_VMM21_V | flat_run 114d + spike 97 | 2025-09-22..2026-01-14 | 114 + 97 | **2026-01-14 cluster** | **interpolate primitive** |
| B313.KV1_VMM22_V | flat_run 114d + spike 105 | 2025-09-22..2026-01-14 | 64 + 105 | **2026-01-14 cluster**; already annotated as double-subtract | interpolate + keep double-subtract note |
| B209.KV1_VMM21_V | flat_run 5 runs Σ=84d | 2025-07-30..2025-08-27 | 105 | Long summer outage, not annotated | outage annotation |
| B313.KV1_VMM21_V | iqr_hi 5 days (9.8–10.3 vs Q3=1.0) | scattered | 50 | Level shift / episodic use | tolerate unless sibling data contradicts |
| B304.KV1_VMM23_V | flat_run 6 runs Σ=112d | 2025-05-09..2025-06-18 (41d) | 48 | Intermittent / seasonal | intermittent pattern |
| B207.KV1_VMM21 | spike 40 + iqr_hi 3d | 2025-06-09 | 40 + 26 | Possible leak event; flag for operator | operator review |
| B302.KV1_VMM21_V | flat_run 26d | 2025-12-24..2026-01-03 (11d) | 39 | Inside swap annotation window | extend existing annotation |
| B207.KV1_VMM21 | iqr_hi 3 days | scattered | 26 | Same meter as above, probably related | consolidate with spike finding |
| B314.KV1_VMM21_V | iqr_hi 1 day (26 m³) + flat 8d | 2025-12-30..2026-01-06 | 26 + 11 | Single spike + holiday flat | tolerate or flag |
| B326.KV1_VMM21 | iqr_hi 11 days (0.3–16 m³ vs Q3=0) | scattered | 24 | Normally idle meter, occasional bursts | tolerate |
| B392.KV1_VMM22 | iqr_hi 8d + flat 306d | spread | 23 + 1 | Idle meter with occasional usage | tolerate |
| B327.KV1_VMM21_V | spike 17 on 2026-02-03 | 2026-02-03 | 17 | Single-day blip; coincident with B389 spike — shared subnet? | correlate; possibly real load shift |
| B319.KV1_VMM21 | spike 14 on 2025-04-06 | 2025-04-06 | 14 | Single spike | operator review |
| B314.KV1_VMM21_V | flat_run 8d | 2025-12-30..2026-01-06 | 11 | Holiday shutdown | tolerate |
| B353.KV1_VMM21_V | flat_run 16d | 2025-10-02..2025-10-17 | 10 | Short outage | outage annotation |
| B310.KV1_VMM20_V | flat_run 115d + zero_w/sibling + spike | 2025-09-21..2026-01-14 | 9.5 + 8.9 + 8.6 | **2026-01-14 cluster** | **interpolate primitive** |
| B315.KV1_VMM21_V | flat_run 5d | 2025-04-17..2025-04-21 | 8 | Annotated swap meter, small gap | tolerate |
| B202.KV1_VMM21_V | spike 7.7 on 2025-01-30 | 2025-01-30 | 8 | Minor | operator review |
| B203.KV1_VMM22_V | flat_run 7d | 2026-02-09..2026-02-15 | 5 | Feb window | flag — affects facit |
| B304.KV1_VMM22_V | iqr_hi 2d | scattered | 5 | Minor | tolerate |
| B304.KV1_VMM21_V | flat_run 35 runs Σ=338d | 2025-08-16..2025-09-18 | 4 | Idle meter | tolerate |
| B317.KV1_VMM25_V | flat_run 279d + zero_w/sibling 279d | 2025-04-04..2026-01-07 | 4 + 4 | Annotated offline 2026-01-09 — extend valid_from back | amend annotation |
| B344.KV1_VMM21_V | spike 3.6 + flat 10d | 2025-10-15 + 2025-07-16 | 4 + 1 | Minor | tolerate |
| B305.KV1_VMM23_V | flat_run 30 runs Σ=244d | 2025-05-07..2025-05-27 | 3 | Pre-offline (annotated 2026-02-24) | extend annotation |
| B392.KV1_VMM21 | iqr_hi 11d + flat 77d | scattered | 3 | Idle | tolerate |
| B313.KV1_VMM21_V | flat_run 4d | 2025-01-03..2025-01-06 | 2 | Minor | tolerate |
| B326.KV1_VMM21 | flat_run 29 runs Σ=255d | 2025-11-20..2025-12-11 | 2 | Mostly idle | tolerate |
| B342.KV1_VMM21_V | flat_run 10d | 2025-04-17..2025-04-22 | 1 | Minor | tolerate |

*Not flagged but worth manual check*: the B308.KV1_VMM23_V "iqr_hi level-shift"
(2878 m³ across 12 days) is the most suspect real-world finding — it does not
match any existing anomaly archetype. The 52-day B203.KV1_VMM22_V band is
likely seasonal process water and should be left alone, but deserves a human
sanity check against B203's production schedule.

---

## snv_kyla

| meter | anomaly | date/range | magnitude (MWh) | context | primitive / new pattern |
|-------|---------|------------|----------------:|---------|-------------------------|
| B207.VENT | flat_run 111d + 7 shorter | 2025-10-26..2026-02-13 | 40 | Annotated offline `ann-snv-kyla-b207-vent-offline` | covered; no action |
| B339.KB1_KOLF | flat_run 38 runs Σ=320d | 2025-12-14..2026-01-08 (26d biggest) | 32 | Highly intermittent reporter on a small cooling load | intermittent pattern |
| B216.VENT | flat_run 37d | 2025-05-20..2025-06-13 | 26 | Annotated offline from 2025-09-27; pre-offline quiet period | extend annotation or sum-children |
| B209.KB1 | flat_run 9 runs Σ=106d | 2025-01-03..2025-03-06 (63d biggest) | 21 | Long winter-startup gap, not annotated | outage annotation (winter idle?) |
| B201.KB1_Elogg | flat_run Σ=171d | 2025-11-21..2025-12-18 (28d biggest) | 17 | Annotated offline 2026-02-17; pre-offline intermittent | extend annotation |
| B304.KB1 | flat_run 15 runs Σ=162d | 2025-01-30..2025-03-06 (36d) | 16 | Long winter gap, not annotated | outage or seasonal-idle annotation |
| B318.KB1 | flat_run 4 runs Σ=27d | 2025-11-29..2025-12-09 | 5 | Winter intermittent | seasonal-idle |

*Not flagged but worth manual check*: Kyla is inherently seasonal. Distinguishing
"winter-idle" from "offline" requires sibling check against B212.KB5 (chiller
trunk) — a kyla-specific "active_season" mask would suppress most of the
winter findings here. No spikes > 3×p99 were flagged; the 5–6× median
finding-set was below cutoff after tuning.

---

## snv_sjovatten

| meter | anomaly | date/range | magnitude (m³) | context | primitive / new pattern |
|-------|---------|------------|---------------:|---------|-------------------------|
| B339.V2_GF3_3 | flat_run 210d + zero_w/sibling 210d | 2025-05-20..2025-12-15 | 590 544 / 574 140 | **Unannotated major outage.** Peer B339.V2_GF3_4 flowing normally through much of the window; median 2734 m³/d lost | outage annotation + candidate for sum-sibling patch (split with GF3_4 via coefficient) |
| B339.V2_GF3_4 | flat_run 7 runs Σ=162d | 2025-08-26..2025-10-19 (55d) | 383 292 | Paired flatlines with GF3_3 — partially overlapping outages; not annotated | outage annotation; see if GF3_3+GF3_4 share a transducer |
| B339.V2_GF4 | flat_run 18d | 2025-05-07..2025-05-17 | 43 344 | Annotated offline 2025-05-19; 11d pre-offline window | extend annotation valid_from |
| B334.V2_VM90_V | flat_run 8 runs Σ=280d | 2025-05-30..2025-12-08 | 18 327 | Annotated offline `ann-snv-sv-b334-offline` + rolling_sum | covered |
| B339.V2_GF4_1 | flat_run 21d + zero_w/sibling 21d | 2025-07-15..2025-07-28 (14d) | 10 941 | Not annotated; sibling GF4 operating | outage annotation or sum-children |
| B229.V2_VMM51 | flat_run 63d + zero_w/sibling 63d | 2025-12-16..2026-02-16 | 1596 + 1187 | Annotated offline 2026-02-20; pre-offline quiet period | extend annotation valid_from to 2025-12-16 |

*Not flagged but worth manual check*: `B339.V2_GF3_3` and `B339.V2_GF3_4` behave
like a pair that alternates coverage. Their GF3 trunk plus GF4 network feeds
roughly equivalent of the site — an operator-level confirmation that "GF3_3"
going dark for 7 months during 2025 is a genuine outage (and not a re-routed
feed) would avoid mis-patching real zero-flow as data loss. No spikes ≥ 3×p99
were flagged.

---

## snv_varme

| meter | anomaly | date/range | magnitude (MWh) | context | primitive / new pattern |
|-------|---------|------------|----------------:|---------|-------------------------|
| B217.VP1_VMM61 | spike 662 831 on 2025-07-28 | 2025-07-28 | 662 831 | 662k garbage register value leaks into `:d` output — same class of bug as anga B217 bracket-regression. Segment-A valid_to is 2025-08-05 but garbage arrived 2025-07-28 | **REGRESSION** of `ann-snv-varme-b217-offline` / rolling_sum. Shift `:d.A` valid_to back to 2025-07-27, OR adopt `bracket` primitive for this meter too |
| B310.VP2_VMM61 | spike 1986.6 on 2026-01-14 + flat 116d + zero_w/sibling 116d | 2025-09-20..2026-01-14 | 1987 / 1925 / 1654 | **2026-01-14 cluster.** Primary värme distribution node; annotation `ann-snv-varme-b310-vp2-distribution` currently just flags as "healthy candidate for sum-children patch" | **interpolate primitive**, or sum-children patch using its 23 children |
| B313.VP1_VMM62 | spike 404.8 + flat 114d + zero_w/sibling 114d | 2025-09-22..2026-01-14 | 405 / 285 / 285 | **2026-01-14 cluster** | **interpolate primitive** |
| B217.VP1_VMM61 | flat_run 73d | 2025-07-29..2025-10-09 | 351 | Covered by 3-segment rolling_sum annotation (offline→swap→swap) | covered; but see regression above |
| B318.VP1_VMM61 | flat_run 3 runs Σ=71d | 2025-07-22..2025-09-01 (42d) | 179 | Long summer outage, not annotated | outage annotation or sum-children |
| B311.VP1_VMM64 | spike 45.6 + flat 121d | 2026-01-14 + 2025-09-20..2026-01-14 | 46 / 20 | **2026-01-14 cluster** | **interpolate primitive** |
| B313.VS1_VMM61 | flat_run 4 runs Σ=95d + zero_w/sibling Σ=42d | 2025-06-02..2025-07-13 (42d) | 34 / 32 | Unannotated intermittent — peer VP1_VMM62 active during some of these gaps | sum-sibling or outage annotation |
| B312.VP2_VMM61 | flat_run 6 runs Σ=193d + zero_w/sibling Σ=149d | 2025-04-28..2025-09-23 (149d) | 31 / 31 | Long 5-month outage, not annotated — peers active | outage annotation |
| B201.VP1_VMM61 | flat_run 4 runs Σ=292d | 2025-05-22..2026-02-18 | 16 | Covered by `ann-snv-varme-b201-swap` rolling_sum | tolerate (very low median flow 0.05 MWh/d) |
| B207.VP1_VMM61 | flat_run 9d | 2025-07-21..2025-07-29 | 15 | Mid-July cluster with anga; no annotation | outage annotation |
| B319.VP1_VMM61 | flat_run 4 runs Σ=69d | 2025-07-10..2025-09-03 (56d) | 15 | Long summer gap | outage annotation |
| B307.VS1_VMM61 | flat_run 4d | 2025-07-23..2025-07-26 | 14 | July cluster | outage annotation |
| B303.VP2_VMM61 | flat_run 8d + zero_w/sibling 8d | 2025-07-21..2025-07-28 | 12 | July cluster | outage annotation |
| B385.VP2_VMM61 | flat_run 11 runs Σ=190d | 2025-04-15..2025-06-14 (61d) | 10 | Very low-flow meter, mostly-idle | intermittent / tolerate |
| B314.VP1_VMM61 | flat_run 5d | 2025-04-17..2025-04-21 | 9 | Short April outage | outage annotation if material |
| B301.VP2_VMM61 | flat_run 15d + zero_w/sibling | 2025-07-22..2025-08-05 | 9 | July cluster | outage annotation |
| B325.VP1_VMM61 | flat_run 7d | 2025-07-15..2025-07-21 | 5 | July cluster | outage annotation |
| B310.VS2_VMM62, B315.VP1_VMM61, B381.VP1_VMM61, B312.VP2_VMM62 | flat_runs 5–27d | scattered | 0.6–3 | Minor outages | tolerate or bulk-annotate |

*Not flagged but worth manual check*: the mid-July 2025 cluster (B207, B303,
B301, B307, B325, with echoes in anga and B318) looks like a 7–10-day sitewide
värme maintenance window — correlate with Panna2/Panna3 flat runs in snv_anga.
If confirmed, a single `site_outage` annotation covering 2025-07-14..2025-07-24
would tidy ~8 separate meter-level flags into one row.

---

## Proposed new primitive — `interpolate`

The 2026-01-14 cluster is not covered by any existing primitive. Shape:

- Meter counter is frozen at value V_frozen from day d0 to day d1 (100+d)
- On day d1+1 the counter jumps to V_frozen + ΔC where ΔC ≫ p99
- Physical flow during [d0, d1] was real but lost to aggregation

Needed behaviour: a `interpolate` aggregation in views.sql that, over the
frozen window, distributes ΔC proportionally (uniform, or weighted by a sibling
meter's delta profile). `rolling_sum` doesn't help because there is no
rollover/reset/swap — the counter value never actually dropped. `sum`
children-patch only helps if children are healthy; for the 2026-01-14 cluster
most parents' children are on the same BMS poll path.

## Proposed new primitive — `bracket_stitch`

Distinct from the existing `bracket` (which operates within a single raw ref
by dropping samples outside [v_lo, v_hi]): when a raw counter's segment
contains a transient register-corruption event (e.g. 7000 → 805 000 → 7000
across a few days), the stitched `:d` output via `rolling_sum` still leaks the
corrupt daily deltas. Both B217 cases (anga Å1, värme VP1) are instances.
Either the bracket patch needs to run on the segment before rolling_sum
consumes it, or a dedicated `bracket_stitch` primitive should apply the value
window during stitching.
