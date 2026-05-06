# SNV adjustment plan — KYLA

Detailed plan for SNV KYLA. **No code or data changes have been made;
this file is the contract.**

## Context

SNV KYLA current state:
- 32 meters (28 real, 4 virtual) across 16 buildings
- **100 % match (139/139 rows) — no non-match Excel-comparison rows**
- 10 annotations: 8 open, 2 resolved
- No KYLA section in Total SNV tab — there is no central kyla intake;
  cooling is generated on-site by distributed chillers per building

Topology: most buildings have their own chiller meters (B216.KB1,
B217.KB1, B312.KB1, etc.). Four sub-meters (B304.KB2, B305.KB1,
B307.KB1, B307.KB1_VMM52) carry fractional-share splits via `feeds`
edges to 4 building virtuals (B302/B303/B305/B307.KYLA_VIRT).

## Key structural finding

**KYLA does not have a centralized intake pattern.** Cooling is
distributed per-building via on-site chillers. The conservation panel
concept (intake vs buildings) doesn't apply meaningfully:
- Campus master = sum of 4 fall-through campus meters = 99 MWh Jan
- Σ building KYLA = 505 MWh Jan (most via direct chiller meters at
  each building)
- The 99 vs 505 ratio is meaningless — the campus meters represent
  only the cross-building fractional-pool sources; the other ~80 %
  of cooling comes from direct building chillers that aren't
  "intake".

**Pattern matches GTN's 2f563df precedent** ("trim non-intake KYLA
campus tags") and the SNV KV / VARME `B385.VP2_VMM62` pattern: drop
the fall-through campus tags so the conservation panel skips KYLA
entirely (correct outcome — there's no meaningful campus master to
display).

---

## 1. Drop 4 fall-through campus tags

The 4 campus-attributed KYLA meters all have **no incoming
hasSubMeter relations** → currently land at "top campus" and inflate
the panel master with meaningless flow. Per the GTN precedent, drop
the campus tag.

**How:** set `building_id` in `meters.csv` so `assemble_site`
auto-generates building (not campus) `meter_measures` rows. This
survives re-runs (manual `meter_measures.csv` edits get clobbered
on the next assemble).

| Meter | New building_id | Why this building |
|---|---|---|
| `B304.KB2` | B304 | Meter is named B304; fed by B304's chiller |
| `B305.KB1` | B305 | Meter is named B305 |
| `B307.KB1` | B307 | Meter is named B307 |
| `B307.KB1_VMM52` | B307 | Meter is named B307 |

**Side effect on building totals:** all 4 have feeds-out k=1.0 (or
k=0.5+0.5=1.0 for B304.KB2 split) → their `meter_net` = 0 → they
contribute 0 to their building's total. Building rollups unchanged.

**Side effect on panel:** KYLA loses all 4 "top campus" meters →
conservation panel skips KYLA entirely. Correct outcome.

### Existing curated entries to verify

The classifier curated entries for `snv_kyla` already include:
```python
('B302', 'excel_cooked_coefficient', '0.5 × B304.KB2 tenant split'),
('B303', 'excel_cooked_coefficient', '0.5 × B304.KB2 tenant split'),
('B305', 'excel_cooked_coefficient', 'B305.KB1 + 0.5 × B307.KB1'),
('B307', 'excel_cooked_coefficient', 'B307.KB1_VMM52 + 0.5 × B307.KB1'),
```

These all match correctly (Excel = 0 and onto = 0 → match by floor).
After 1.x, these stay as `match` rows (no change).

---

## 2. Annotation sweep

10 annotations: 8 open, 2 resolved.

| annotation_id | verdict |
|---|---|
| `ann-snv-kyla-b203-kb1-offline` | **resolve** — leaf meter, ref carries valid_to=2025-10-17, no recovery possible, well-documented |
| `ann-snv-kyla-b203-kb5-offline` | **resolve** — same as above |
| `ann-snv-kyla-b209-kb4-offline` | **resolve** — same upstream-event family, leaf meter, well-documented |
| `ann-snv-kyla-b201-kb1-elogg-offline` | keep open — Feb 2026 outage inside facit window, may need patch later |
| `ann-snv-kyla-b207-vent-offline` | keep open — Feb 2026 outage |
| `ann-snv-kyla-b216-vent-offline` | **resolve** — outside Jan/Feb 2026 window, no facit impact |
| `ann-snv-kyla-fractional-splits` | keep open — calibration / fractional-subtract primitive blocker |
| `ann-snv-kyla-ref-doc-marks-all-na` | keep open — documentation note |

**Net: 4 resolved → 4 open.**

---

## 3. No new meters / virtuals / sensors

Nothing to add. Existing topology is correct.

---

## 4. Status banner

Current (`green`, 2 sentences):
> "Ontology matches Excel exactly. Fractional KYLA tenant splits
> (B302/B303/B305/B307) are routed via `feeds` k<1 edges; physical
> justification thin but math reconciles within rounding."

Proposed (`green`, 2 sentences):
> "Ontology matches Excel at 100 percent (139/139 rows). KYLA is "
> "distributed chillers per building (no centralized intake), so "
> "the campus conservation panel skips KYLA by design after dropping "
> "4 fall-through campus tags (B304.KB2, B305.KB1, B307.KB1, "
> "B307.KB1_VMM52). Fractional tenant splits routed via feeds k<1 "
> "edges (B302/B303 share B304.KB2, B305/B307 share B307.KB1)."

Stays `green` — KYLA is already in great shape.

---

## 5. No conservation panel for SNV KYLA (by design)

After the campus-tag drop, SNV KYLA will have **zero campus-targeted
meters** → panel skips KYLA. This is the correct outcome — distributed
chillers don't have a meaningful "intake" master to compare against.

---

## 6. Suggested commit shape

Single commit:
> "SNV KYLA: drop 4 fall-through campus tags + annotation sweep"

Files touched:
- `data/sites/snackviken/meters.csv` (4 building_id changes)
- `data/sites/snackviken/meter_measures.csv` (auto-regenerates from
  meters.csv on next assemble; until then, manual edit to switch the
  4 rows from `campus,SNV` → `building,B30X`)
- `data/sites/snackviken/annotations.csv` (4 resolved)
- `packages/app/src/app/status_board.py` (1 banner)
- `reference/media_workstreams/snv_kyla/05_ontology/meters.csv` (mirror)
- `reference/media_workstreams/snv_kyla/05_ontology/annotations.csv` (mirror)

**No readings.csv touched.** Smallest commit possible — hand-edit
4 rows in meters.csv + 4 annotations + 1 banner + mirrors.

---

## 7. Decisions to confirm

1. **Drop the 4 fall-through campus tags by retargeting to building?**
   Recommended yes — matches GTN 2f563df precedent and SNV
   B385.VP2_VMM62 / B324.H3 patterns. Building totals unchanged
   (net=0 due to feeds-out drain).
2. **Resolve the 4 outside-facit-window outage annotations?**
   Recommended yes (B203.KB1, B203.KB5, B209.KB4, B216.VENT — all
   well-documented leaf meters with no recovery possible).
3. **No new ingests / no virtual aggregator** — KYLA is already
   100 % match.
