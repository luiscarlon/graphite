# Snäckviken ånga — follow-up patch opportunities

This file lists data-quality improvements that the current pass of
`quality_patches.yaml` **did not apply**, separated from annotations so
the user can review and decide each independently.

Each entry: the pattern, the meter affected, the primitive that would
fix it, and the pipeline work required to execute the patch.

---

## 1. B217 — replace A|B|C|D segment split with bracket + interpolate

**What is today:**  
`B217.Å1_VMM71:d` is a `rolling_sum` over four raw segments
(:d.A, :d.B, :d.C, :d.D) whose validity windows skip the corruption
period (2025-07-15 → 2025-10-10). The rolling_sum flat-carries across
the skipped intervals, so the ~484 MWh of real consumption inside the
corruption window is lost from the canonical counter.

**What it should be:**  
A single full-period raw ref carrying the corrupted hourly data
unchanged, topped by:
- `B217.Å1_VMM71:d.clip` (bracket, valid_from=2025-07-15,
  valid_to=2025-10-10) — keeps in-band samples (~55 of 87 days based
  on the raw hourly inspection).
- One or more `B217.Å1_VMM71:d.patch.N` (interpolate) refs across
  sub-gaps where bracket output has zero samples (the longest observed
  stretch is 5 days; there are 14 such stretches).
- `B217.Å1_VMM71:d` (rolling_sum, preferred) combining the full raw
  with the clip and patch refs.

**Why deferred:**  
The existing :d.A|:d.B|:d.C|:d.D raw refs overlap validity with any
new full-period raw ref under the same `(sensor, database, path)`
triple, which violates `ref_validity_non_overlapping`. Restructuring
requires either:
- removing the B217 entries from `meter_swaps.csv` so build_ontology
  stops emitting the 4-segment split, then adding the full-period raw
  via `quality_patches.yaml`, or
- adding a deletion directive to `apply_quality_patches.py` and
  explicitly removing :d.A/:d.B/:d.C/:d.D in the YAML.

**Impact on Jan/Feb 2026 reconciliation:**  
None. The corruption window is Jul–Oct 2025. Monthly deltas after Oct
2025 are invariant; only the cumulative counter rises by ~484 MWh
earlier. The 2025 monthly totals (Jul–Oct) would shift from near-zero
(flat-carry) to recovering the real consumption.

**Raw-data evidence available:**  
`reference/snowflake_meter_readings/B217.Å1_VM71.csv` — 5830 hourly
rows covering 2025-07-01 → 2026-02-28. Tri-modal value histogram
(<100 / 1k–10k / ~800k) with zero overlap between bands; 53 days
recoverable by bracket, 34 need interpolate; longest sub-gap 5 days.

---

## 2. B216 — possibly also register-corrupt pre-freeze?

**Hypothesis:**  
B216.Å1_VM71 lives on the same EBO server as B217. If the BMS
misconfig affected both, the Feb-1 → Feb-18 window where B216 still
reported may contain the same tri-modal corruption before finally
freezing. We would not know without a raw hourly pull.

**Action:** pull raw hourly for `B216.Å1_VM71` across 2025-01-01 →
2026-02-28, scan for the multi-register value histogram. If present,
decide whether to apply the same bracket + interpolate approach to
B216's :d.raw pre-freeze segment. If absent, the current
children-sum patch from B217 is adequate.

---

## 3. B308 — dead or corrupt? No raw-data confirmation yet

Same hypothesis as B216: B308 is on the same server family. Counter
frozen at 12737.1533 for the entire window is consistent with either
(a) meter physically dead, or (b) register-corruption where every
sample landed on the stuck-high register (which coincidentally equals
the pre-freeze last value). A raw pull is needed to distinguish; if
(b), bracket can recover any real samples that landed on the correct
register.

---

## 4. B390, B313, B385 — leaf outages, no primitive helps

Leaf meters with no children available for a sum-patch. The only way
to recover their consumption is:
- external reference (another year's data, or a sibling branch
  estimator), or
- upstream meter's residual (the difference between the upstream
  intake and the other children's sum — this assumes conservation).

Neither fits `bracket` or `interpolate`. Documented here so future
work doesn't re-discover them as candidates.

---

## 5. B311.Å1_VMM70 direction conflict

Topology / source-conflict issue, not a data-quality issue. Resolve
via `decisions.md` once the physical flow direction is confirmed on
site; update `meter_relations.csv`. No primitive involved.
