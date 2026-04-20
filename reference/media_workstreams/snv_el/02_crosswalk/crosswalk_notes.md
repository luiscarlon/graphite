# snv_el crosswalk notes

**144 unique Excel-referenced meters** (97 single-line XLOOKUP terms + 47 additional helper-row terms from complex formulas spanning rows 79–183).

## Match results

| class | count | treatment |
|---|---|---|
| Exact Snowflake match | 125 | `snowflake_id = facit_id` |
| Normalized match (dash↔underscore) | 2 | `B334.T87-5-2 → B334.T87_5_2`; `B334.T88-4-2 → B334.T88_4_2` |
| `-1` summary-suffix match | 2 | `B209.T21 → B209.T21-1`; `B209.T32 → B209.T32-1` (BMS convention: bare trunk ID + `-1` is the summary feed, analogous to GTN's `-S` suffix). STRUX T21 = 7293.8 kWh Jan matches BMS T21-1 = 7287 kWh (0.08% agreement). |
| `_1_1` trunk match | 5 | `B334.T87 → B334.T87_1_1` (and .T88, .T89, .T91, .T92 similarly). BMS T87_1_1 = 94528 Jan matches STRUX T87 = 94561 Jan (0.04%). The underscore-separated sub-meters `T87_2_2, T87_4_1, ...` are downstream taps, NOT to be summed. |
| STRUX-only (truly dormant) | 8 | `snowflake_id=""`, no BMS equivalent under any naming variant tested |
| Genuinely absent (not in Snowflake, not in STRUX) | 2 | `B307.T77-4-5-B` (likely Excel typo for `B339.T77-4-5`), `Reservkraft pl7` (literal placeholder) |

**Per 2026-04-20 revision**: earlier crosswalk had 15 STRUX-only entries; extended fuzzy-match reduced this to 8 by discovering the `-1` and `_1_1` summary conventions. Added to the spec's fuzzy-match rule set under §7.

## SNV-specific naming patterns (differ from GTN)

**No `-S` summary-suffix convention on SNV main transformers.** GTN adds `-S` to bare transformer IDs in Snowflake (e.g. `B611.T1-S`), but no SNV meter needs this transform. 0 matches via the `-S` probe.

**Underscore vs dash separator on B334.** Snowflake uses `B334.T87_5_2` (underscores); Excel/STRUX use `B334.T87-5-2` (dashes). Affects all B334 sub-meter IDs. The canonical `facit_id` keeps the dash form (matches Excel); `snowflake_id` carries the underscore form.

**`T26S` suffix on B313 transformers.** The `S` in `B313.T26S` is part of the meter ID (stands for "Ställverk"), not the GTN `-S` convention. Snowflake has `B313.T26S-2-12` etc. as sub-meter variants, but bare `B313.T26S`, `B313.T26S-2-6`, `B313.T26S-3-12` are STRUX-only.

**Helper-row meter blocks.** Rows 79–183 of the EL sheet list per-term meters for complex-formula rows:

| helper block | rows | building formulas referencing it |
|---|---|---|
| `B305` | 80–90 | row 22 (B305) |
| `B307` | 93–108 | row 23 (B307) |
| `B310` | 111–140 | row 26 (B310) |
| `B311` | 143–158 | row 27 (B311) |
| `B317` | 161–169 | row 33 (B317) |
| `B339` | 172–183 | row 48 (B339) |

The XLOOKUP-substitution parser in `parse_reporting_xlsx.py` does NOT expand these blocks — it only picks up single-line XLOOKUP/S..AA meter lists. For the complex rows, the per-term meter IDs must be read from column B of the helper rows, and the coefficients from the formula text via `openpyxl.ArrayFormula.text` (see below).

## Per-term coefficient reconstruction (complex rows)

These are NOT captured correctly by `excel_formulas.csv` — re-parse manually when writing `facit_accounting.csv`:

**Row 22 (B305)** `=$F$5*SUM(C80:C90)`
→ all 11 members (C80..C90) at **+1.0**

**Row 23 (B307)** `=$F$5*(SUM(C93:C94) - SUM(C95:C108))`
→ C93, C94 at **+1.0** (`B307.T10-1`, `B307.T11-1`); C95..C108 at **−1.0** (14 sub-feeders)

**Row 26 (B310)** `=$F$5*((C111-SUM(C112:C121))*0.5 + (C122-C123) + (C124-C125) + (C126*1/3) + (C127-SUM(C128:C140))*0.4)`
- C111=`B313.T26S` at **+0.5**; C112..C121 (T26S sub-meters) at **−0.5**
- C122=`B310.T27` at **+1.0**; C123=`B310.T27-12-2` at **−1.0**
- C124=`B310.T28` at **+1.0**; C125=`B310.T28-23-2` at **−1.0**
- C126=`B311.T29` at **+(1/3)**
- C127=`B317.T49` at **+0.4**; C128..C140 (T49 sub-meters) at **−0.4**

**Row 27 (B311)** `=$F$5*((C143-SUM(C144:C151))*0.5 + (C152*2/3) + (C153-C154) + C155 + (C156-C157) + C158)`
- C143=`B313.T26S` at **+0.5**; C144..C151 at **−0.5**
- C152=`B311.T29` at **+(2/3)**
- C153=`B311.T56` at **+1.0**; C154=`B311.T56-4-7` at **−1.0**
- C155=`B311.T79` at **+1.0**
- C156=`B311.T80` at **+1.0**; C157=`B311.T80-2-3` at **−1.0**
- C158=`B360.T99-4-5` at **+1.0**

**Row 33 (B317)** `=$F$5*(SUM(C161:C163) + (C164-SUM(C165:C169))*0.5)`
- C161..C163 at **+1.0** (`B313.T26S-3-16`, `B313.T26S-3-20`, `B317.T49-5-9`)
- C164=`B317.T49` at **+0.5**; C165..C169 at **−0.5** (5 T49 sub-meters)

**Row 48 (B339)** `=$F$5*(SUM(C172:C179) - SUM(C180:C183))`
- C172..C179 at **+1.0** (8 T71..T78 summaries)
- C180..C183 at **−1.0** (`B339.T77-5-1`, `B339.T77-4-5`, `B339.T78-4-1`, `B339.T78-4-2`)

**Inline fractions on simple rows** (parser handles these correctly):
- Row 11 (B204): R11=0.75 on S term only (B209.T32-4-2 at 0.75)
- Row 12 (B205): R12=0.25 on S term only (B209.T32-4-2 at 0.25) — complement of row 11, total 1.0
- Row 28 (B312): R28=0.85 on whole net (S − T − U − V)
- Row 29 (B313): R29=0.1 applied only to inner (T − U − V − W − X − Y) net; S (=B310.T27-12-2) at +1.0 outside the factor

**Cross-building fractional splits** (critical for validation):

| pool meter | sum of shares | allocation |
|---|---|---|
| `B313.T26S` net | 1.0 | B310 @ 0.5, B311 @ 0.5 |
| `B311.T29` | 1.0 | B310 @ 1/3, B311 @ 2/3 |
| `B317.T49` net | 1.0 | B310 @ 0.4, B317 @ 0.5, B313 @ 0.1 |
| `B209.T32-4-2` | 1.0 | B204 @ 0.75, B205 @ 0.25 |

These multi-building allocations will need **virtual pool meters** in the ontology (same pattern as `B600-KB2` on GTN kyla).

## Known-absent meters

- `B307.T77-4-5-B`: row 69 (B385) references it as `+` term. No Snowflake presence, no STRUX catalog entry. Likely a typo for `B339.T77-4-5` (which exists) but keep as-is; B385's total will read low by this meter's contribution until the Excel is corrected.
- `Reservkraft pl7`: row 50 (B341) W column. Literal placeholder string for a backup-power allocation not (yet) assigned to a concrete meter.
- 15 STRUX-catalog meters with empty `STRUX_data` values — all dormant during 2026-01/2026-02 window:
  `B209.T21`, `B209.T32`, `B307.T11-7-7`, `B313.T26S`, `B313.T26S-2-6`, `B313.T26S-3-12`, `B334.T87`, `B334.T88`, `B334.T89`, `B334.T91`, `B334.T92`, `B336.T40-3-1`, `B371.T23-4-4`, `B371.T31-4-4`, `B371.T31-5`.

Their Excel cached building-totals consequently exclude their (zero) contribution, so the topology match still holds.
