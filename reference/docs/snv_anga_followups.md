# Snäckviken ånga — follow-up patch opportunities

This file lists data-quality improvements that the current pass of
`quality_patches.yaml` **did not apply**, separated from annotations so
the user can review and decide each independently.

Each entry: the pattern, the meter affected, the primitive that would
fix it, and the pipeline work required to execute the patch.

---

## 1. B217 — RESOLVED 2026-04-21 via slice+interpolate+slice pattern.

Superseded by the fix described in `annotations.csv::ann-snv-anga-b217-register-corruption`. interpolate across the corruption window doesn't depend on any in-window samples — only the two outside-window endpoints — so it sidesteps the bracket/rolling_sum composition problem entirely. Stitched `:d` is now monotone with cumulative preserved at both endpoints and ~5.56 MWh/day linear fill across the 86-day gap. Original design notes below preserved for historical context.

---

The `bracket` restructure (full-period raw + bracket clip + preferred
rolling_sum overlay) was written, applied, and reverted after the
regenerated Snäckviken readings showed the stitched `:d` producing
garbage — including negative values at the raw→clip→raw transitions
inside the corruption window.

**Why it didn't work at daily resolution:**  
At daily V_LAST aggregation, most corruption-window days have V_LAST
landing on an artifact register (either the near-zero or the stuck-
high). Of 87 corruption-window days, only ~5 days have V_LAST in the
real-register band. `bracket` correctly keeps those 5 samples but
`rolling_sum`'s concat-with-anchor-offset stitch semantics can't
compose a bracket-overlay with a full-period raw source: it sorts all
source readings by timestamp and switches anchor/offset on each
source change, producing artefacts when the stream alternates between
5 in-band clip samples and 82 out-of-band raw samples.

**Current state (reverted):**  
`build_ontology.py` auto-generates 14 raw segments (`:d.A` through
`:d.N`) from the 14 `is_reset=1` days the detector finds in B217's
daily extract. `rolling_sum` stitches them. The resulting `:d`
accumulates through artifact-level deltas across the corruption
window — the 2026-02-28 stitched value is on the order of 4 million,
when the real meter is in the ~8 thousand band. This was ALSO broken
before the bracket attempt (pre-work 2026-02-28 committed value was
~804 thousand — different shape, same class of garbage), so the
revert returns the meter to its pre-existing broken state, not a
regression.

**To actually fix B217 we need one of:**

1. **Hourly source data.** The raw CSV at
   `reference/snowflake_meter_readings/B217.Å1_VM71.csv` (5830 rows,
   tri-modal <100 / 1k–10k / ~800k with zero band overlap) has
   53 of 87 corruption-window days with ≥1 real-register sample.
   Ingesting hourly readings into the pipeline (replacing daily
   V_LAST with hourly) would make `bracket` keep ~53 days' worth of
   clean counter samples — enough density for `rolling_sum` to
   stitch correctly. Requires adding hourly extraction + changing the
   ontology's `aggregate` field.

2. **A new `overlay` aggregation kind** that picks the most-restrictive-
   validity source at each timestamp, and emits nothing (gap) if the
   most-restrictive source has no reading there. This lets `:d.clip`
   shadow `:d.raw` inside its validity — clip wins when present, gap
   elsewhere — without mixing source values the way `rolling_sum`
   does. Scope: ~50 lines in `assemble_site.py` plus validation
   rule, plus tests.

3. **Accept the broken state** and document every downstream
   consumer (Excel comparison, annual totals) that B217's Jul–Oct
   2025 is un-reconstructable at daily resolution and should be
   pulled from Excel's cached STRUX value rather than topology.

None are applied here.

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
