# Parsing Notes

## General approach

### Goal
Extract from Excel consumption workbooks:
1. **Meters table** — each meter, which building it belongs to, and whether it is real or virtual
2. **Relations table** — how meters feed each other, with coefficients where applicable

These two tables fully describe the metering topology. Building-level connections can be derived from them.

### Output format

**meters** (`{source}_{tab}_meters.csv`):
| Column | Description |
|--------|-------------|
| meter_id | Meter name as it appears in the Excel (e.g. B611.T4-A3) |
| building | Building the meter's consumption is assigned to |
| meter_type | `real` = physical meter with timeseries; `virtual` = calculated meter, no physical device |

**relations** (`{source}_{tab}_relations.csv`):
| Column | Description |
|--------|-------------|
| from_meter | Parent meter |
| to_meter | Child meter |
| coefficient | Multiplier applied to the parent's reading. 1.0 = full reading; <1.0 = fraction |
| derived_from | How the relation was determined: `formula` or `naming` |

### How the Excel formulas work — and how NOT to misread them

Each building row has a formula calculating that building's **net** monthly consumption in a single cell:
```
building_consumption = unit_factor * ( ±coeff*XLOOKUP(meter1) ± coeff*XLOOKUP(meter2) ± ... )
```
- `+meter` = meter's reading is added (contributes to this building)
- `-meter` = meter's reading is subtracted (belongs to another building downstream)

**Critical: the Excel formula is an accounting shortcut, not a wiring diagram.** Each building's formula must contain the entire upstream chain to compute its net consumption in one cell. This means:
- A building's formula subtracts ALL downstream meters, even those several levels deep in the chain
- This does NOT mean all subtracted meters are direct children of the `+` meters in that formula
- The same meter may be subtracted in multiple building formulas (once per level in the chain)

To find the **direct** parent of a subtracted meter, we look for it in the formula closest to it — where the subtraction appears alongside the most specific `+` meter.

**When coefficients are involved** (e.g. `0.38 * B600-KB2 - B631.KB1_INTE_VERK2`):
- The coefficient (0.38) determines the building's SHARE — this creates a virtual meter
- The subtracted real meters (-B631...) feed from the PARENT meter (B600-KB2), NOT from the virtual share
- The Excel subtracts them from the share formula because it needs to compute the net in one cell, but the physical feed is with the parent
- **Virtual meters are always end of chain** — no real meters feed from a virtual meter

To verify: when coefficients match between `+` and `-` terms (e.g. B612: `+0.9*parent -0.9*child`), the coefficient applies to the whole sub-tree. When they don't match (e.g. B611: `+0.38*parent -1.0*child`), the subtracted meter is independently metered and connects directly to the source.

### Building ownership
- A meter with `+` in a building belongs to that building
- A meter that only appears as `-` (orphan) gets no building assignment (building='') — it represents unmeasured pass-through or losses

### Deriving meter relations

**Formulas are the primary source.** They tell us which meters pass through which buildings.

**Naming is used only to disambiguate** within a single formula when there are multiple `+` meters and we need to determine which one feeds a specific `-` meter. The disambiguation uses the transformer root: the first segment after the dot (e.g. `T4` in `B611.T4-A3`). We match each `-` meter to the `+` meter sharing the same root.

This gives two certainty levels recorded in `derived_from`:
- **`formula`**: the building formula has exactly one `+` meter, so it must be the parent of all `-` meters. No naming needed.
- **`naming`**: multiple `+` meters in the formula; transformer root used to pick the right one.

### The graph is a DAG, not a tree
A meter may be subtracted in multiple building formulas (because upstream formulas subtract the entire downstream chain). We record **all** parent-child relationships from all formulas — a meter can have multiple parents.

Example: B652.T8-A3-A14-112 is subtracted from both B612 (under T8) and B641 (under T8-A3). Both relationships are recorded:
- B612.T8 → B652.T8-A3-A14-112
- B641.T8-A3 → B652.T8-A3-A14-112

This is necessary for correct calculation: each building subtracts its children from its meter readings. If we picked only one parent, the other building's calculation would be wrong.

**Calculation from the graph**: building consumption = sum over its owned meters of (STRUX_reading − sum of children's STRUX_readings) × unit_factor. This was validated against all buildings.

### Virtual meters and coefficients

Some tabs use coefficients to assign a **fraction** of a meter's reading to a building. Coefficients appear in two ways:
- **Column R ("Faktor")**: e.g. R=0.38 for building 611 in Kyla
- **Hardcoded in the formula**: e.g. `0.8*XLOOKUP(...)` or `0.9*XLOOKUP(...)`

When a coefficient < 1.0 is applied to a meter for a building:
- A **virtual meter** is created representing that building's share
- The virtual meter has no physical device — it is a calculated fraction
- The relation records the coefficient (e.g. 0.38)
- Virtual meters **can have children** when real meters in the building's zone are subtracted

Naming convention: `VIRT.{building}.{source_meter}`. Example: `VIRT.B611.B600-KB2` = building 611's 38% share of B600-KB2.

### Where subtracted meters go: matching vs non-matching coefficients

When a formula has coefficient shares and subtracted meters, the coefficient determines where the child goes:

- **Matching coefficients** (e.g. B612: `+PKYL ×0.9 -B637 ×0.9`): the child goes on the **real parent** (B612-KB1-PKYL → B637). The virtual share picks up the subtraction via `coeff × parent_net`.
- **Non-matching coefficients** (e.g. B611: `+B600-KB2 ×0.38 -B631 ×1.0`): the child goes on the **virtual share** (VIRT.B611.B600-KB2 → B631). The child reduces the virtual meter's value directly.

### Calculation from the graph

```
meter_net(real_meter) = STRUX_reading - sum(real children's readings)
meter_net(virtual_meter) = coefficient × meter_net(parent) - sum(real children's readings)
building_total = sum(meter_net(m) for m in building's owned meters)
```

Computed meters (like B600-KB2) that aggregate other meters' readings are pre-computed from their composition formula before graph traversal.

When multiple buildings share a meter, the coefficients should sum to 1.0 (verified during parsing). If they don't, it is flagged as a problem.

---

## gtn.xlsx — EL tab (Gärtuna electricity)

**Outputs:** `gtn_el_meters.csv`, `gtn_el_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "EL", rows 8–61, one row per building (54 rows, all Gärtuna site)
- Column C: ArrayFormula with XLOOKUPs against STRUX_Mätare/STRUX_data
- Columns S–AA: meter IDs (up to 9 per building)
- Column R ("Faktor"): empty for all rows — no coefficients, no virtual meters in EL

### Disambiguation validation
19 cases required naming to disambiguate (multiple `+` meters). All 19 resolved to exactly one transformer-root match, zero conflicts.

### Problems and exceptions
1. **B652.T14-B3-J** — subtracted in B652 but on a different transformer (T14) than the only `+` meter (T8). No root match needed: B652 has a single `+` meter so this is formula-certain. It is a cross-transformer outgoing line from B652 to B602.
2. **B659.T28-3-5** — subtracted in B659, never added in any building. Orphan meter representing unmeasured pass-through or losses.
3. **B616.T31 and B616.T31-6-2** — both `+` in B616 despite similar naming. They are independent meters (if one fed the other, adding both would double-count).
4. **B621** — split into "621 (T)" and "621 (I&L)" in the Excel (two zones). I&L has no meters.
5. **15 buildings with no meters** and 0 consumption: 603, 604, 620, 621 (I&L), 623, 656, 660, 662, 663, 682, 842, 850, 951, Trädgård, Summa Ställverk.

### Summary
- **76 meters** (all real)
- **26 relations** (all coefficient=1.0; 8 formula-derived, 18 naming-assisted; 1 meter has 2 parents: B652.T8-A3-A14-112)
- **Graph-validated**: 38/38 buildings match Excel (Feb)

---

## gtn.xlsx — Kyla tab (Gärtuna cooling)

**Outputs:** `gtn_kyla_meters.csv`, `gtn_kyla_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Kyla", rows 8–54, all Gärtuna site
- Same formula structure as EL but with coefficients
- Column R ("Faktor"): used for B600-KB2 distribution (0.38, 0.03, 0.5, 0.09)
- Hardcoded coefficients in formulas: 0.8, 0.9, 0.2, 0.1

### Special rows
- **B600-KB2 (row 8)**: computed virtual meter representing the distributable cooling pool. Its formula DEFINES B600-KB2 from production meters minus direct consumers. Subtractions here are components of the definition, not downstream feeds.
- **Prod-600 (row 9)**: summary of production meters. Skipped — not a building.

### Disambiguation approach
Naming-based disambiguation (used in EL) does not work for Kyla — meter names use KB1/KB2 circuit prefixes that don't form parent-child naming hierarchies. Instead:
- **Tier 1 (single + meter)**: used where applicable
- **Coefficient matching**: when a `-` meter has the same coefficient as a `+` meter, they belong to the same sub-tree. Example: B612 has `+B612-KB1-PKYL ×0.9` and `-B637 ×0.9` → B612-KB1-PKYL feeds B637.

### Coefficient distributions (verified sums = 1.0)
- **B600-KB2**: B611 38% + B613 3% + B621 50% + B622 9% = 100% ✓
- **B654.KB1_KylEffekt_Ack**: B612 80% + B613 20% = 100% ✓
- **B612-KB1-PKYL**: B612 90% + B641 10% = 100% ✓

### Problems and exceptions
1. **B634.KB1_PKYL**: has a post-XLOOKUP unit conversion `*24*31/1000` (kW→MWh). The meter reads in kW, not kWh like other STRUX meters. This conversion is specific to this one meter.
2. **B821→B841 at ×0.8**: B841.KB2_VM51 is subtracted with coefficient 0.8 from B821, but B841 adds it at 1.0. The 20% gap is unexplained — either B841 has another source, or the coefficient is an estimation.
3. **B631.KB1_VMM51_E**: orphan — subtracted from B611's formula, never added in any building.
4. **B821.KB2_VMM1**: orphan — subtracted in B600-KB2's definition, never added in any building.

### Summary
- **34 meters** (24 real, 10 virtual including B600-KB2)
- **16 relations** (all formula-derived)
- **Graph-validated**: 17/17 buildings match Excel (Feb)

---

## gtn.xlsx — Värme tab (Gärtuna heating)

**Outputs:** `gtn_varme_meters.csv`, `gtn_varme_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Värme", rows 8–60, all Gärtuna site
- No coefficients (column R empty), no virtual meters
- Same structure as EL

### Disambiguation
Naming uses circuit prefixes (VP1, VP2, VS1, VÅ9). 4 cases had multiple `+` meters sharing the same root — parent pick is arbitrary but doesn't affect building ownership or validation:
- B612: 4 VP2 meters, can't determine which feeds B641/B637
- B616: 2 VP1 meters, can't determine which feeds B661
- B833: 2 VP1 meters, can't determine which feeds B834

### Column range
Värme uses columns S–Z (not just S–X like Kyla). Always scan S–AA to be safe.

### Summary
- **46 meters** (all real)
- **17 relations** (all coefficient=1.0; 6 naming-ambiguous)
- **Graph-validated**: 28/28 buildings match Excel (Feb)

---

## gtn.xlsx — Ånga tab (Gärtuna steam)

**Outputs:** `gtn_anga_meters.csv`, `gtn_anga_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Ånga", rows 8–60, all Gärtuna site
- No coefficients, no virtual meters
- Columns S–V (4 max)

### Special rows
- **Row 8 (building "600")**: aggregates B600N and B600S steam intake meters. Not a real building — reporting construct like B600-KB2 in Kyla, but here it only adds meters (no subtraction, no coefficient distribution), so it works as a normal building in the graph.

### Disambiguation
4 cases with ambiguous naming root (Å1 prefix shared across multiple + meters):
- B611: 2 Å1 meters, can't determine which feeds B622
- B612: 2 Å1 meters, can't determine which feeds B613/B641
- B614: 2 Å1 meters, can't determine which feeds B642

### Summary
- **19 meters** (all real)
- **4 relations** (all coefficient=1.0; 4 naming-ambiguous)
- **Graph-validated**: 11/11 buildings match Excel (Feb)

---

## gtn.xlsx — Kallvatten tab (Gärtuna cold water)

**Outputs:** `gtn_kallvatten_meters.csv`, `gtn_kallvatten_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Kallvatten", rows 8–57, all Gärtuna site
- No coefficients, no virtual meters
- Columns S–Y (7 max)

### Special rows
- **Row 8 (building "600")**: aggregates B600N and B600S water intake. Same pattern as Ånga — works as normal building.
- **"850/662"**: combined building row — stored as-is.

### Disambiguation
9 cases with ambiguous naming root (KV1 prefix shared across all meters):
- B611, B612, B614, B821, B833: multiple KV1 meters per building

### Summary
- **63 meters** (all real)
- **11 relations** (all coefficient=1.0; 9 naming-ambiguous)
- **Graph-validated**: 37/37 buildings match Excel (Feb)

---

## gtn.xlsx — Kyltornsvatten tab (Gärtuna cooling tower water)

**Outputs:** `gtn_kyltornsvatten_meters.csv`, `gtn_kyltornsvatten_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Kyltornsvatten", rows 8–55, all Gärtuna site
- No coefficients, no virtual meters, no subtracted meters
- Column S only (1 meter per building)

### Summary
- **7 meters** (all real)
- **0 relations**
- **Graph-validated**: 3/3 buildings with Feb data match (4 buildings had 0 values)

---

## snv.xlsx — EL tab (Snäckviken electricity)

**Outputs:** `snv_el_meters.csv`, `snv_el_relations.csv`
**Date:** 2026-04-13
**Status:** formula validation 42/42 ✓, graph validation 37/42 (5 model limitations — see parsing_validation.md)

### Structural differences from GTN
This workbook has a fundamentally different design:
1. **Complex formulas**: 6 buildings (305, 307, 310, 311, 317, 339) have formulas referencing expanded meter sections in rows 79–183 via cell references (SUM, individual cells), not via XLOOKUP columns S–AA.
2. **Per-column formulas**: complex buildings have individual formulas in each month column (C–N), NOT array formulas. B317 has different parenthesization between columns (see problems below).
3. **Coefficient sub-expressions**: coefficients apply to entire net expressions (e.g. `(T26S_net)*0.5`), not to individual meters. Multiple buildings share the same meter tree with different coefficient splits.
4. **Multi-building coefficient splits**: B313.T26S split 50%/50% between B310/B311. B317.T49 split 40%/50%/10% between B310/B317/B313. B209.T32-4-2 split 75%/25% between B204/B205. B311.T29 split 33%/67% between B310/B311.
5. **Shared meters**: some meters appear as + in multiple buildings without coefficient splits (B318.T21-6-2-A in both 318 and 344; B339.T77-4-5 in both 305 and 392).
6. **Column range**: meters extend to column AA (row 51 B342 uses AA). Always scan S–AA.

### Formula validation
**42/42 match** (0 mismatches, 26 zero buildings skipped). All 6 complex buildings validated by replaying their expanded-section formulas against cached Feb values.

Previous session had 40/42: the B313 mismatch was a validator bug (coefficient detection), not a data issue. B317's D-column formula matches the cached value; the C-column formula gives a different result due to parentheses (see problems).

### Complex building formulas (rows 79–183)

| Building | Formula (col C) | Expanded rows |
|---|---|---|
| 305 | `$F$5*SUM(C80:C90)` | 80–90: all + |
| 307 | `$F$5*(SUM(C93:C94)-SUM(C95:C108))` | 93–94: +, 95–108: - |
| 310 | `$F$5*((C111-SUM(C112:C121))*0.5+(C122-C123)+(C124-C125)+(C126*1/3)+(C127-SUM(C128:C140))*0.4)` | 111–140 |
| 311 | `$F$5*((C143-SUM(C144:C151))*0.5+(C152*2/3)+(C153-C154)+C155+(C156-C157)+C158)` | 143–158 |
| 317 | C: `$F$5*(SUM(C161:C163)+(C164-SUM(C165:C169))*0.5)` / D: `$F$5*(SUM(D161:D163)+(D164-SUM(D165:D169)*0.5))` | 161–169 |
| 339 | `$F$5*(SUM(C172:C179)-SUM(C180:C183))` | 172–183 |

B310's sub-expressions: T26S_net×0.5, T27_net, T28_net, T29×1/3, T49_net×0.4.
B311's sub-expressions: T26S_net×0.5, T29×2/3, T56_net, T79, T80_net, T99-4-5.

### Meters CSV status

141 entries (132 real, 9 virtual). Issues:

**11 meters missing** (from expanded sections):
- 6 are B307 submeters that feed B305: B307.T10-6-9, T10-7-3, T10-7-4, T10-7-5, T10-7-7, B307.T11-7-10
- 4 are B307 orphans (- in 307 only, tiny values <0.02 kWh): B307.T10-5-3, T10-6-2, T10-6-5, B307.T11-7-7
- 1 is B339 orphan: B339.T78-4-1 (~14 kWh)

**2 wrong building assignments:**
- B307.T10-5-2: CSV=307, should be 387 (+ in 387 formula, - in 307)
- B307.T11-8-5: CSV=307, should be 305 (+ in B305 expanded rows 87, - in 307)

**2 missing building assignments:**
- B312.T34-2-3, B312.T34-2-4: CSV has building='', should be 305 (+ in B305 expanded rows 88–89)

### Relations CSV status

48 entries. Relations for XLOOKUP buildings are correct. Missing:

- **B307.T10-1 →** T10-5-2, T10-5-3, T10-6-2, T10-6-5, T10-6-8, T10-6-9, T10-7-3, T10-7-4, T10-7-5, T10-7-6, T10-7-7 (11 children). Disambiguation: all share T10 root, single + meter.
- **B307.T11-1 →** T11-7-7, T11-7-10, T11-8-5 (3 children). Single + meter.
- **B339.T77-1 →** B339.T77-4-5, B339.T77-5-1 (naming: T77 root)
- **B339.T78-1 →** B339.T78-4-1, B339.T78-4-2 (naming: T78 root)
- **B311.T29 split**: needs VIRT.B310.B311.T29 (coeff=0.333) and VIRT.B311.B311.T29 (coeff=0.667)
- **B307.T77-4-5-B**: parent unclear — could be T10-1 or T11-1 (naming doesn't help, different transformer prefix)

### Problems and exceptions

1. **B317 parenthesis typo (confirmed)**: col C has correct `(T49-SUM(subs))*0.5`, cols D–N have wrong `T49-SUM(subs)*0.5` (misplaced paren during copy-paste). formula_document.xlsx confirms C-style with `0.5` on each term. Col C = 58.6 MWh, col D = 134.1 MWh. All cached values for Feb–Dec are wrong.
2. **B318 sign typo (confirmed)**: snv.xlsx adds B318.T21-6-2-A (+), formula_document.xlsx subtracts it (-). T21-6-2-A feeds B344, B318 should subtract it. CSV corrected: building=344. B318's cached values overcount by ~4.4 MWh/month.
3. **B392 meter discrepancy**: formula_document.xlsx says `B334.T87_5_2 + B334.T88_4_2`, snv.xlsx says `B339.T77-4-5 + B334.T88-4-2`. Not a simple typo — meters were reassigned between documents. T77-4-5 is also + in B305 (aggregation building), creating double-count at site level.
4. **B312.T34 at 85%**: R=0.85, remaining 15% not assigned to any building. Not a parsing error — the Excel simply doesn't account for it.
5. **Per-building subtraction subsets**: B310/B311 subtract different subsets of T26S children (10 vs 8). B310/B313/B317 subtract different subsets of T49 children (13 vs 5). The graph model computes one `parent_net` from ALL children, but each formula computes its own net from a building-specific subset. formula_document.xlsx confirms: B311 even ADDS `+0.5*T26S_3_24` while B310 subtracts it. This is a genuine structural difference, not a typo.
6. **B305 is an aggregation building**: its formula (SUM rows 80–90) collects submeters from B307 (T10/T11 subtree), B312 (T34-2-3, T34-2-4), and B339 (T77-4-5). These are physically sub-areas measured within larger transformer feeds.
7. **4 orphan meters** in B307 with negligible values (all <0.02 kWh/month): T10-5-3, T10-6-2, T10-6-5, T11-7-7. Likely inactive or decommissioned meters.
8. **B339.T78-4-1**: orphan (- in B339, never + anywhere), ~14 kWh. Small but not negligible.

### Summary
- **153 meters** (143 real, 10 virtual, 124 with building, 29 orphans)
- **67 relations** (rebuilt from scratch: 14 wrong-parent fixes, 33 additions)
- **Formula-validated**: 42/42 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 37/42 match (5 failures are model limitations / source data errors — see parsing_validation.md)

---

## snv.xlsx — Kyla tab (Snäckviken cooling)

**Outputs:** `snv_kyla_meters.csv`, `snv_kyla_relations.csv`
**Date:** 2026-04-13

### Source structure
- Sheet "Kyla", rows 8–78, all Snäckviken site
- All ArrayFormula with XLOOKUP (no complex/expanded sections)
- Column R ("Faktor"): used by B302 (0.5), B303 (0.5), B305 (0.5), B307 (0.5)
- Columns S–U: meter IDs. Columns V–X referenced in formula template but empty for all rows
- No unit factor (F5 is empty); STRUX values already in MWh
- STRUX media filter: 'Kyla'
- 71 building rows total; 23 have meters, 48 have no meters (zero consumption)

### Formula structure
All formulas follow the same ArrayFormula template:
```
=±R*XLOOKUP(S)+XLOOKUP(T)+XLOOKUP(U)-XLOOKUP(V)-XLOOKUP(W)-XLOOKUP(X)
```
Since V–X are empty for all rows, there are **no subtracted meters** in any formula. Every building only adds meters. This means no parent-child relations come from formula subtraction.

### Coefficient distributions (verified sums = 1.0)
- **B304.KB2**: B302 50% + B303 50% = 100% ✓
  - B302: `R19*XLOOKUP(S)` — R applies to S=B304.KB2
  - B303: `R20*XLOOKUP(S)` — R applies to S=B304.KB2
- **B307.KB1**: B305 50% + B307 50% = 100% ✓
  - B305: `XLOOKUP(S) + R22*XLOOKUP(T)` — R applies to T=B307.KB1, S=B305.KB1 at 1.0
  - B307: `XLOOKUP(S) + R23*XLOOKUP(T)` — R applies to T=B307.KB1, S=B307.KB1_VM52_E at 1.0

### Building ownership notes
- **B330** uses meter B331.KB1_VM51_E (named after B331 but assigned to B330 in the formula)
- **B304.KB2** and **B307.KB1**: not added at coeff=1.0 in any building; they are shared sources → building=''
- **B339 Kolfilter**: separate reporting row with its own meter (B339.KB1_KOLF)

### STRUX meters not used in Kyla tab (5)
- B209.KB6 (0.0) — B209 uses B209.KB6_VMM51 instead
- B305.KB1_VM52_E (25.69) — present in STRUX but not referenced in any building formula
- B313.KB1_VM51_E (0.59) — B313 has no meters in Kyla tab
- B318.KB3_INTVERK1_E (75.37) — B318 only uses KB1, not KB3
- B318.KB3_INTVERK2_E (69.09) — same as above

### formula_document.xlsx comparison
The KYLA sheet in formula_document.xlsx lists all SNV buildings as "N/A" (rows 3–39). No formulas documented for SNV Kyla, so no discrepancies to check. The GTN Kyla formulas (rows 40+) were already validated in the gtn_kyla section.

### Summary
- **32 meters** (28 real, 4 virtual)
- **4 relations** (all coefficient=0.5, all formula-derived)
- **Formula-validated**: 17/17 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 17/17 non-zero buildings match Excel cached Feb values

---

## snv.xlsx — Värme tab (Snäckviken heating)

**Outputs:** `snv_varme_meters.csv`, `snv_varme_relations.csv`
**Date:** 2026-04-14

### Source structure
- Sheet "Värme", rows 8–71, all Snäckviken site
- All ArrayFormula with XLOOKUP (no complex/expanded sections)
- Column R ("Faktor"): present but empty for all rows — no coefficients, no virtual meters
- Meter columns: most rows S–W (5 slots). Row 22 (B310) extends to AR (col 44) — 26 slots, 4 additive + 22 subtractive. Row 23 (B311) uses S–Y (7 slots).
- No unit factor; STRUX values already in MWh
- STRUX media filter: 'Värme' (col D = Mätarbeteckning, col I = Feb)
- 64 building rows total; 31 have meters, 33 have no meters (zero consumption)

### Formula structure
Standard template: `=+XLOOKUP(S)+XLOOKUP(T)+XLOOKUP(U)-XLOOKUP(V)-XLOOKUP(W)`

### Disambiguation
Circuit prefix matching (VP1, VP2, VS1, VS2, VS12, VP12). Used for all multi-`+` meter buildings. 4 cases could not be resolved:

- **B310: B341.VS1_VMM61_E and B313.VS1_VMM61** — subtracted from B310 but B310 has no VS1 `+` meter (only VP2, VP1, VS2). These are accounting subtractions (B341 and B313 are in B310's zone) with no determinable parent. No relation created.
- **B311: B381.VP1_VMM61_E** — subtracted from B311 which has 3 VP1 `+` meters (VMM65, VMM62, VMM64). Naming-ambiguous; assigned to B311.VP1_VMM65_E (first match).

### B310/B311 VS2 cross-subtraction
B310 subtracts B311.VS2_VMM61_E and B311 subtracts B310.VS2_VMM61_E + B310.VS2_VMM62_E — a mutual subtraction on the VS2 circuit. This creates a cycle. Resolution: B311's formula is more specific (3 subtractions vs B310's 22), so B311.VS2 is upstream. Kept: B311.VS2_VMM61_E → B310.VS2_VMM61_E, B310.VS2_VMM62_E. Removed: B310.VS2_VMM61_E → B311.VS2_VMM61_E.

### B310 as zone-level aggregation
B310's formula (4 `+` meters, 22 `-` meters) subtracts the entire downstream tree across VP2, VP1, and VS2 circuits, plus two VS1 meters from other buildings (B341, B313). The Excel computes B310's net as a zone-level residual. The graph model captures VP2 (12 children) and VP1 (7 children) chains correctly but cannot represent the VS1 accounting subtractions since there is no VS1 parent meter in B310.

### Building "202,203,204,205,209"
Row 9 has a combined building label with a single meter B203.VP1_VMM61_E. This meter serves the entire group. Building assigned as "202,203,204,205,209" (matching Excel label).

### B327 aggregation
B327's formula adds both B327.VS1_VMM61 and B326.VS1_VMM61 (both `+`). B326 has its own row with B326.VS1_VMM61. In our model, B326.VS1_VMM61 is assigned to building=326 (naming convention). B327's cached value includes B326's meter reading — a known model choice, not an error.

### Problems and exceptions
1. **B385.VP2_VMM62_E**: orphan — subtracted in B310, never added in any building.
2. **B310 cached = -154.72 MWh**: negative value, confirming B310 is a zone-level residual (subtractions exceed additions because VS1/VS2 accounting items are not modeled as children).
3. **B326.VS1_VMM61**: added in both B326 (row 37) and B327 (row 38). Assigned to building=326 per naming convention. B327's total includes B326's reading — see graph validation note.

### Summary
- **46 meters** (all real, no virtual meters)
- **27 relations** (all coefficient=1.0; 4 formula-derived, 23 naming-derived; 2 unresolvable VS1 meters, 1 naming-ambiguous VP1)
- **Formula-validated**: 30/30 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 28/30 match (2 model limitations — see parsing_validation.md)

---

## snv.xlsx — Ånga tab (Snäckviken steam)

**Outputs:** `snv_anga_meters.csv`, `snv_anga_relations.csv`
**Date:** 2026-04-14

### Source structure
- Sheet "Ånga", rows 8–75, all Snäckviken site
- All ArrayFormula with XLOOKUP (no complex/expanded sections)
- Column R ("Faktor"): present but empty for all rows — no coefficients, no virtual meters
- Meter columns: most rows S–W (5 slots). Row 23 (B307) uses S–AB (10 slots, 2 additive + 8 subtractive).
- No unit factor; STRUX values already in MWh
- STRUX media filter: 'Ånga'
- 68 building rows total; 24 have meters, 44 have no meters

### Disambiguation
All Ånga meters share the Å1 prefix (e.g. `B307.Å1_VMM71_E`). The `Å` character is not matched by the circuit prefix regex, so ALL meters get an empty prefix. Naming disambiguation is therefore **entirely inconclusive** for this tab — all subtractions are assigned to the first `+` meter arbitrarily. This does not affect building-level graph validation (because meter_net sums are building-invariant), but individual meter-level parent assignments are uncertain.

Specific ambiguities:
- **B307** (2 `+`, 8 `-`): all 8 subtractions assigned to B307.Å1_VMM71_E. Some may belong to B307.Å1_VMM72_E.
- **B216** (2 `+`, 1 `-`): B217.Å1_VM71 assigned to B216.Å1_VM71. Could be B216.Å1_VMM72_E.
- **B302** (2 `+`, 2 `-`): B302.Å1_VMM72_E and B301.Å1_VMM71_E both assigned to B302.Å1_VMM71_E.
- **B310** (1 `+`, 5 `-`): single `+` meter → all formula-derived, no ambiguity.
- **B325** (2 `+`: Panna2_MWH, Panna3_MWH, 1 `-`: B390.Å1_VMM70_E): no prefix match (Panna vs Å1). No relation created. Graph still validates because B390 has zero Feb consumption.

### Special rows
- **"204/205"** (row 11): merged building label, no meters
- **"330/331"** (row 44): merged building, 3 meters (B330.Å1_VMM71_E, VMM72, VMM73)
- **"339 Kolfilter"** (row 48): separate sub-building with B339.Å1_VMM70_E
- **B325** (row 40): non-standard meter names (B325.Panna2_MWH, B325.Panna3_MWH — boiler-based metering)

### B307 as super-aggregation
B307 adds 2 meters and subtracts 8 downstream meters covering B339, B302, B311, B334, B304, B330, B337, and B216. This is the main steam distribution node for the site.

### Problems and exceptions
1. **B302.Å1_VMM72_E**: self-subtracted — appears as `-` in B302's own formula while B302 adds VMM71 and VMM73. Orphan in the sense that it has no parent outside B302. Assigned to building=302 as an intra-building subtraction.
2. **B390.Å1_VMM70_E**: subtracted from B325 but no prefix match among B325's Panna meters. No relation created. B390 has its own building row (row 71). Feb reading = 0 so graph validation unaffected, but this relation is missing and would cause a mismatch in months with non-zero B390 consumption.
3. **B337 → B330**: B337 subtracts B330.Å1_VMM71_E (single `+` meter in B337 → formula-derived). B330 is also `+` in "330/331". So B330.Å1_VMM71_E has two parents: B307.Å1_VMM71_E (from B307's formula) and B337.Å1_VMM71_E (from B337's formula). This is valid — the DAG allows multiple parents.

### Summary
- **34 meters** (all real, no virtual meters)
- **18 relations** (all coefficient=1.0; 3 formula-derived, 15 naming-derived but all naming-ambiguous due to shared Å1 prefix)
- **Formula-validated**: 19/19 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 19/19 match (0 mismatches, 5 zero-skipped)

---

## snv.xlsx — Kallvatten tab (Snäckviken cold water)

**Outputs:** `snv_kallvatten_meters.csv`, `snv_kallvatten_relations.csv`
**Date:** 2026-04-14

### Source structure
- Sheet "Kallvatten", rows 9–76, all Snäckviken site (row 8 = aggregation "Total från 'under'-mätare", skipped)
- All ArrayFormula with XLOOKUP (no complex/expanded sections)
- Column R ("Faktor"): empty for all rows — no coefficients, no virtual meters
- Meter columns: most rows S–W (5 slots). Row 27 (B311) extends to AH (16 slots, 1 additive + 15 subtractive).
- No unit factor; STRUX values already in m³
- STRUX media filter: 'Kallvatten'
- 68 building rows total; 40 have meters, 28 have no meters

### Disambiguation
All KV meters share the KV1 prefix. Naming disambiguation is entirely inconclusive — all subtractions assigned to the first `+` meter. Same pattern as GTN Kallvatten and SNV Ånga.

10 naming-ambiguous cases: B202 (3 candidates), B302 (2), B305 (2), B310 (5), B314 (3).

### B311 as super-aggregation
B311.KV1_VM26_V (single `+` meter) subtracts 15 downstream meters spanning B317 (×4), B337, B381, B310 (×6), B313, B315, and 2 orphans (B311.KV1_VM27_V, B310.KV1_VM24_V). All formula-derived (single `+` meter).

### B314/B315 shared meter
B315.KV1_VM21_V is `+` in both B314 (row 30) and B315 (row 32). Assigned to building=315 per naming convention. B314's formula adds it, so B314's cached value includes B315's reading — causes graph validation mismatch of 15.22 m³ (= B315's Feb reading).

### Special rows
- Row 8: aggregation row "Total från 'under'-mätare" = SUM of building rows. Skipped.
- **"339 Kolfilter"** (row 48): separate sub-building, no meters
- **"Acturum"** (row 75): non-standard building name, has meter B390.KV1_VM25_V

### Chained subtractions
B339 → B318 → B319/B353: B339.KV1_VM23_V subtracts B318.KV1_VM21_V, which in turn subtracts B353.KV1_VM21_V and B319.KV1_VM21. Three-level chain.

### Problems and exceptions
1. **5 orphan meters** (only `-`, never `+`):
   - B202.KV1_VM22_V: self-subtracted in B202
   - B302.KV1_VM21_V: subtracted in B302
   - B305.KV1_VM21_V: subtracted in B305
   - B310.KV1_VM24_V: subtracted in B311, never `+` in B310 or anywhere
   - B311.KV1_VM27_V: self-subtracted in B311
2. **B315.KV1_VM21_V**: `+` in both B314 and B315 (no coefficient split). Assigned to building=315 → B314 graph mismatch.

### Summary
- **63 meters** (all real, no virtual meters)
- **35 relations** (all coefficient=1.0; 25 formula-derived, 10 naming-derived but all naming-ambiguous)
- **Formula-validated**: 39/39 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 38/39 match (1 model limitation — see parsing_validation.md)

---

## snv.xlsx — Sjövatten tab (Snäckviken lake water)

**Outputs:** `snv_sjovatten_meters.csv`, `snv_sjovatten_relations.csv`
**Date:** 2026-04-14

### Source structure
- Sheet "Sjövatten", rows 9–84, all Snäckviken site (row 8 = BPS aggregation "BPS Beräkning", skipped)
- Mix of formula types: ArrayFormula XLOOKUP, `R*BPS_V2`, and `R*XLOOKUP(S)+XLOOKUP(T)-...`
- Column R ("Faktor"): used for BPS allocation and shared meter splits
- Meter columns: S–Y (7 max, row 51 B339 kylmaskiner)
- No unit factor; STRUX values already in m³
- STRUX media filter: 'Sjövatten'
- Rows 87–107: hidden BPS computation section (not parsed as building rows)
- 76 building rows; 19 have real meters, 5 are BPS-only, 52 have no meters

### Three formula patterns

1. **BPS-only** (`=R*BPS_V2`): B301 (0.09), B302 (0.18), B303 (0.18), B307 (0.46), B344 (0.09). No physical meter — fraction of site-level BPS computed value. Coefficient sum = 1.00 ✓

2. **R*XLOOKUP** (`=R*XLOOKUP(S)+XLOOKUP(T)-...`): B310/B311 share B310.V2_GF4_1 (50/50), B330/B331 share B330.V2_GF4_1 (50/50). Creates virtual meters for each building's share.

3. **Standard XLOOKUP**: 14 buildings with direct STRUX meter lookups.

### BPS_V2 computed meter
BPS_V2 (row 8) formula: `=SUM(C88:C89)-SUM(C90:C105)`. A site-level computed total (intake minus distributed consumption) analogous to B600-KB2 in GTN Kyla. Its value cannot be stored in the relations table because the component meters belong to their own buildings. BPS_V2 Feb cached = 29,829 m³. BPS virtual meters are standalone — no relations in the CSV.

### Coefficient distributions (verified sums = 1.0)
- **BPS_V2**: B301 9% + B302 18% + B303 18% + B307 46% + B344 9% = 100% ✓
- **B310.V2_GF4_1**: B310 50% + B311 50% = 100% ✓
- **B330.V2_GF4_1**: B330 50% + B331 50% = 100% ✓

### B339 sub-buildings
B339 has 3 sub-rows:
- Row 49 "339": no meters
- Row 50 "339 Kolfilter": B339.V2_GF4_1 (single meter)
- Row 51 "339 kylmaskiner": 3 `+` meters, 4 `-` meters (only subtraction row in the tab)

### External tenants
- Row 83 "Kringlan": meter TE-52-V2-GF4:1 Kringlan (non-standard naming)
- Row 84 "Scania": meter TE-52-V2-SCANIA

### Special rows
- Row 78 "409 Kylcentral": B409.V2_GF4
- Rows 80–82: B212, B229, B230 — separate buildings below the main building range

### Problems and exceptions
1. **B339 kylmaskiner subtractions**: 4 subtracted meters assigned to B339.V2_GF3_3 (first `+` meter) — all naming-ambiguous (3 `+` candidates with empty prefix match). B339.V2_GF4_1 (Kolfilter's meter) is subtracted from kylmaskiner.
2. **BPS virtual meters**: not representable in the graph model (BPS_V2 is computed, not in STRUX). Known gap — same as GTN Kyla B600-KB2.
3. **Row 55 (B345)**: formula references R55 but R55 is empty → zero result. Missing factor.

### Summary
- **28 meters** (19 real, 9 virtual — 5 BPS + 4 shared-meter splits)
- **8 relations** (4 coefficient splits at 0.5, 4 subtraction-derived from B339 kylmaskiner)
- **Formula-validated**: 17/17 non-zero buildings match Excel cached Feb values
- **Graph-validated**: 12/17 match (5 failures are BPS virtual meters — see parsing_validation.md)
