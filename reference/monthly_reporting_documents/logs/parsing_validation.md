# Parsing Validation

## Purpose
Verify that our parsed meters and relations tables reproduce the same building consumption values as the Excel formulas. This confirms we correctly extracted the meter topology.

## Method
For each building with meters, compute consumption from the raw STRUX data using the **original Excel formula** (not our tree). Compare against the Excel's cached value for a reference month.

### Steps
1. Load STRUX sheet from the source workbook (data_only=True for calculated values)
2. For each building row in the tab, reconstruct the formula: sum of `+meter` readings minus sum of `-meter` readings, multiplied by the unit factor
3. Compare against the Excel's stored value (column D = February, or whichever reference month)
4. Tolerance: < 0.001 MWh

### What this validates
- Correct extraction of meter IDs from columns S–AA
- Correct sign parsing (+/-) from the formula text
- Correct coefficient extraction (hardcoded and column R)
- That STRUX meter names match exactly between the tab formulas and the STRUX sheet

### What this does NOT validate
- The tree structure (parent-child relations) — those are for topology only
- Virtual meter naming — those are our convention, not in the Excel
- Building ownership — the Excel doesn't encode this directly

## Reference month
February (column D in the tab, column I in STRUX) — chosen because it has data for most meters.

## How to run validation for a new tab

```python
# Pseudocode for validating tab X from source file Y
for each building in parsed formulas:
    calc = 0
    for meter, sign, coeff in building_terms:
        strux_val = lookup(meter, STRUX sheet, reference_month, media_filter)
        calc += sign * coeff * strux_val
    calc *= unit_factor
    compare(calc, excel_cached_value)
```

Key details per tab:
- **EL**: media filter = "El", unit factor from F5 (0.001 for MWh), no coefficients
- **Kyla**: media filter by meter name (STRUX has mixed media), unit factor may differ, coefficients from column R and hardcoded in formulas. B600-KB2 is computed (row 8) — validate it as a formula too. Prod-600 is a summary — skip.
- Coefficient formulas reference B600-KB2 via ANCHORARRAY — for validation, compute B600-KB2 first from its own formula, then use that value.

## Results

### gtn.xlsx — EL (Feb)
- **38/38 buildings match** (0 mismatches) — validated from graph (DAG), not from formulas
- 1 meter with 2 parents (B652.T8-A3-A14-112): both required for correct calculation

### gtn.xlsx — Kyla (Feb)
- **17/17 buildings match from graph** (0 mismatches, Prod-600 skipped as summary)
- B634.KB1_PKYL has a post-XLOOKUP unit conversion (`*24*31/1000`, kW→MWh) — to be fixed in source data
- B600-KB2 is a virtual meter computed from other buildings' meters (`B623+B653+B654-B658-B661-B821`). Its composition cannot be stored in the relations table because those meters also belong to their own buildings. Its value is computed separately from STRUX before graph traversal — this is a known gap in the graph model.
- Virtual meters with matching-coefficient children validated correctly

### gtn.xlsx — Värme (Feb)
- **28/28 buildings match from graph** (0 mismatches)
- Initial parse used columns S-X (6) but Värme extends to Z — fixed to scan S-AA for all tabs

### gtn.xlsx — Ånga (Feb)
- **11/11 buildings match from graph** (0 mismatches)

### gtn.xlsx — Kallvatten (Feb)
- **37/37 buildings match from graph** (0 mismatches)

### gtn.xlsx — Kyltornsvatten (Feb)
- **3/3 buildings match from graph** (0 mismatches, 4 buildings had 0 Feb values)

### snv.xlsx — EL (Feb)
- Formula validation: **42/42 match** (0 mismatches, 26 zero buildings skipped)
- All 6 complex buildings (305, 307, 310, 311, 317, 339) validated from expanded sections
- Graph validation: **37/42 match** — 5 failures are model limitations (see below)
- Meters/relations CSVs rebuilt (see corrections below)

#### Source data errors (confirmed against formula_document.xlsx)

1. **B318 sign error**: snv.xlsx adds B318.T21-6-2-A (+), formula doc subtracts it (-). T21-6-2-A feeds B344, not B318. Corrected in CSV: building=344. B318's cached Excel values are wrong (overcount by 4.4 MWh/month).
2. **B317 parenthesis error**: snv.xlsx col C has `(T49-SUM(subs))*0.5` (correct), cols D–N have `T49-SUM(subs)*0.5` (wrong — 0.5 only applies to SUM). Formula doc confirms C-style. B317 cached values are wrong for Feb–Dec.
3. **B392 meter discrepancy**: formula doc says `B334.T87_5_2 + B334.T88_4_2`, snv.xlsx says `B339.T77-4-5 + B334.T88-4-2`. Meters changed between documents — not a simple typo, left as-is.

#### Graph validation failures

| Building | Diff (MWh) | Cause |
|---|---|---|
| 311 | 5.0 | T26S subtraction subset (see below) |
| 313 | 8.1 | T49 subtraction subset (see below) |
| 317 | 116.2 | T49 subset + cached value wrong (parenthesis typo, correct value ~58.6) |
| 318 | 4.4 | Cached value wrong (sign typo, correct value ~106.9). Graph can't model accounting subtraction of T21-6-2-A — no parent in B318's meter tree |
| 392 | 43.4 | Shared meter B339.T77-4-5 (building=305 in B305 aggregation, also serves 392) |

Root causes:
- **Per-building subtraction subsets (B311, B313, B317)**: B310/B311 subtract different subsets of T26S children (10 vs 8). B310/B313/B317 subtract different subsets of T49 children (13 vs 5). Both documents (snv.xlsx and formula_document.xlsx) confirm these are different — not typos. The graph model computes one parent_net from ALL children, but each formula computes its own net from a building-specific subset. Unresolved — needs a modeling decision on how to represent per-building subtraction sets in the relations table.
- **B318 accounting subtraction**: T21-6-2-A has no parent among B318's meters (transformer root T21 vs T78/T19/T20). Can't model as parent→child relation.
- **B392 shared meter**: T77-4-5 is + in both B305 (aggregation building) and B392. Possibly T77-4-5 should be building=392 and B305 shouldn't own individual submeters.

#### Per-building subtraction subsets — raw data

T26S (B310 vs B311):
- Common (subtracted by both): T26S-2-32, T26S-2-6, T26S-2-XX, T26S-3-12, T26S-3-16, T26S-3-20, T26S-3-32
- B310 only: T26S-2-12 (10058 kWh), T26S-3-24 (16 kWh) — also T26S-3-28 (29821 kWh, discrepancy: snv.xlsx B311 subtracts it, formula doc doesn't)
- Formula doc B311 ADDS +0.5*T26S_3_24 (other buildings subtract it)

T49 (B310 vs B313/B317):
- Common (subtracted by all three): T49-4-2, T49-4-3, T49-5-5, T49-5-6
- T49-5-9: subtracted by B310 and B313, but ADDED by B317 (net +0.5 in B317's formula)
- B310 only (8 submeters, all orphan): T49-3-9, T49-4-4, T49-4-6, T49-4-7, T49-4-9, T49-5-1, T49-5-2, T49-5-7

#### CSV corrections applied (2026-04-13)

**Meters** (153 entries: 143 real, 10 virtual, 124 with building, 29 orphans):
- Added 11 missing real meters from expanded sections (6 B307→B305, 4 B307 orphans, 1 B339 orphan)
- Added 2 virtual meters: VIRT.B310.B311.T29 (0.33333), VIRT.B311.B311.T29 (0.66667)
- Removed VIRT.B313.B310.T27-12-2 — B313 gets 100% of T27-12-2, the 0.1 coefficient was for T49 not T27-12-2
- Fixed building: B307.T10-5-2 (307→387), B307.T11-8-5 (307→305), B312.T34-2-3 (→305), B312.T34-2-4 (→305), B339.T77-5-1 (339→orphan)
- Set shared meters to building='': B209.T32-4-2, B311.T29, B312.T34, B313.T26S, B317.T49 (prevents double-counting with virtual shares)
- Fixed B318.T21-6-2-A: building 318→344 (sign typo in snv.xlsx confirmed by formula_document.xlsx)

**Relations** (67 entries, rebuilt from scratch):
- Fixed 14 wrong-parent relations from initial parse:
  - B209.T32 submeters were under T21 → moved to T32 (naming: T32 root)
  - B308.T58-4-2 was under T57 → moved to T58 (naming: T58 root)
  - B310.T28-23-2 was under T27 → moved to T28 (naming: T28 root)
  - B317.T49 submeters (×5) were under T27-12-2 → moved to T49 (from B313 formula misparse: S + R*(T-subs) read as "S is parent of subs")
  - B311.T56-4-7 was under T29 → moved to T56 (formula: T56-T56-4-7)
  - B311.T80-2-3 was under T29 → moved to T80 (formula: T80-T80-2-3)
  - B334.T88-4-2 was under T87 → moved to T88 (naming: T88 root)
  - Removed VIRT.B313.B310.T27-12-2 relation
- Added 33 new relations: B307 T10-1/T11-1 → 14 submeters, B339 T77-1/T78-1 → 4 submeters, B311.T29 → 2 virtual splits, plus the corrected parent assignments above

#### Coefficient splits

| Shared meter | Split | Total |
|---|---|---|
| B209.T32-4-2 | 204:75% + 205:25% | 100% ✓ |
| B313.T26S | 310:50% + 311:50% | 100% ✓ |
| B311.T29 | 310:33% + 311:67% | 100% ✓ |
| B317.T49 | 310:40% + 313:10% + 317:50% | 100% ✓ |
| B312.T34 | 312:85% | 85% — 15% unaccounted |

#### Open questions

1. **B317 formula inconsistency**: col C `(T49-SUM(subs))*0.5` vs col D `T49-SUM(subs)*0.5` — different parentheses give different results (58.6 vs 134.1 MWh). Col D matches cached value.
2. **B312.T34 at 85%**: remaining 15% not assigned to any building.
3. **B318.T21-6-2-A**: + in both B318 and B344 at 1.0 — shared meter, no coefficient split.
4. **B339.T77-4-5**: + in both B305 and B392 at 1.0 — shared meter, no coefficient split.

---

### snv.xlsx — Kyla (Feb)
- Formula validation: **17/17 match** (0 mismatches, 54 zero buildings skipped)
- Graph validation: **17/17 match** (0 mismatches)
- No unit factor (STRUX values already in MWh)
- No subtracted meters in any formula (no parent-child relations from subtraction)
- Two coefficient splits: B304.KB2 (50/50 → B302/B303), B307.KB1 (50/50 → B305/B307)

---

### snv.xlsx — Värme (Feb)
- Formula validation: **30/30 match** (0 mismatches, 1 zero building skipped)
- Graph validation: **28/30 match** (2 model limitations — see below)
- No unit factor (STRUX values already in MWh)
- No coefficients, no virtual meters
- STRUX col D = Mätarbeteckning (meter ID), col I = Feb values

#### Graph validation failures

| Building | Diff (MWh) | Cause |
|---|---|---|
| 310 | 787.7 | Zone-level aggregation: formula subtracts 22 meters but graph only models VP2 (12) and VP1 (7) children. Missing: 2 VS1 meters (B341.VS1, B313.VS1) with no prefix match among B310's + meters, plus B311.VS2 which is upstream (cross-subtraction, cycle avoided). B310 cached = -154.72 (negative = zone residual). |
| 327 | 15.2 | B327's formula adds both B327.VS1_VMM61 + B326.VS1_VMM61 (=213.36), but our model assigns B326.VS1 to building=326. Graph calc = 198.20 (B327.VS1 only). Diff = B326's Feb reading (15.16). Model choice, not error. |

#### B310/B311 VS2 cycle resolution
B310 and B311 mutually subtract each other's VS2 meters. Resolution: B311's formula is more specific (3 subtractions vs 22), so B311.VS2_VMM61_E is upstream → children B310.VS2_VMM61_E, B310.VS2_VMM62_E. The reverse direction (B310→B311.VS2) was removed to break the cycle.

---

### snv.xlsx — Ånga (Feb)
- Formula validation: **19/19 match** (0 mismatches, 5 zero buildings skipped)
- Graph validation: **19/19 match** (0 mismatches, 5 zero-skipped)
- No unit factor (STRUX values already in MWh)
- All naming disambiguation inconclusive (shared Å1 prefix, non-ASCII not matched by regex)
- B325→B390 relation missing (no naming match between Panna and Å1 prefix); passes because B390 Feb=0
- B302.Å1_VMM72_E is self-subtracted within B302 (intra-building), not an inter-building relation

---

### snv.xlsx — Kallvatten (Feb)
- Formula validation: **39/39 match** (0 mismatches, 1 zero building skipped)
- Graph validation: **38/39 match** (1 model limitation — see below)
- No unit factor (STRUX values in m³)
- All naming disambiguation inconclusive (shared KV1 prefix)
- B311 is super-aggregation: 1 `+` meter, 15 subtractions (formula-derived)

#### Graph validation failure

| Building | Diff (m³) | Cause |
|---|---|---|
| 314 | 15.2 | B315.KV1_VM21_V is `+` in both B314 and B315 without coefficient split. Assigned to building=315 per naming. B314's formula includes it but graph does not. Diff = B315's Feb reading. Model choice, not error. |

---

### snv.xlsx — Sjövatten (Feb)
- Formula validation: **17/17 match** (0 mismatches, 7 zero buildings skipped)
- Graph validation: **12/17 match** (5 failures are BPS virtual meters — see below)
- No unit factor (STRUX values in m³)
- 3 formula types: BPS allocation (5 buildings), R*XLOOKUP shared meter (4 buildings), standard XLOOKUP (10 buildings)
- BPS_V2 Feb cached = 29,829 m³. Coefficient sum = 1.00 ✓
- Shared meter splits: B310.V2_GF4_1 (50/50), B330.V2_GF4_1 (50/50)

#### Graph validation failures

| Building | Diff (m³) | Cause |
|---|---|---|
| 301 | 2,685 | BPS virtual meter — BPS_V2 is computed (not in STRUX), graph can't resolve |
| 302 | 5,369 | BPS virtual meter |
| 303 | 5,369 | BPS virtual meter |
| 307 | 13,721 | BPS virtual meter |
| 344 | 2,685 | BPS virtual meter |

Root cause: BPS_V2 is a site-level computed value (`=SUM(C88:C89)-SUM(C90:C105)`) analogous to B600-KB2 in GTN Kyla. Cannot be represented in the graph model. Each BPS building's consumption = `faktor × BPS_V2`, validated via formula validation (17/17 ✓).
