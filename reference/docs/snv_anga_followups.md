# Snäckviken ånga — follow-up patch opportunities

This file lists data-quality improvements that the current pass of
`quality_patches.yaml` **did not apply**, separated from annotations so
the user can review and decide each independently.

Each entry: the pattern, the meter affected, the primitive that would
fix it, and the pipeline work required to execute the patch.

---

## 1. B217 — bracket replaces A|B|C|D segment split  ✓ **APPLIED**

The 4-segment raw split (:d.A|:d.B|:d.C|:d.D) has been replaced with
- `:d.raw` — single full-period raw ref (non-preferred)
- `:d.clip` — `bracket` derived ref scoped to the corruption window
  (2025-07-15 → 2025-10-10)
- `:d` — preferred `rolling_sum` stitching :d.raw with :d.clip

See `reference/media_workstreams/snv_anga/quality_patches.yaml` for
the exact `delete` + `refs` blocks. The `apply_quality_patches.py`
script was extended with deletion support to make this possible.

**Outcome:** bracket filters the multi-register artifacts (< 100 and
> 100k) from the corruption window while preserving days whose daily
V_LAST landed on the real counter register. Days where V_LAST landed
on an artifact drop out as gaps; downstream LAG-diff views treat them
as cross-gap accumulation (total is conserved).

**Not yet applied:** `interpolate` sub-gap patches. At daily V_LAST
aggregation we don't know a priori which days will have artifact
V_LAST values, so we can't pre-author per-stretch interpolate refs.
Revisit if the Jul–Oct 2025 monthly residuals prove meaningful once
the production pipeline re-runs with the new structure.

**Raw-data evidence:**  
`reference/snowflake_meter_readings/B217.Å1_VM71.csv` — 5830 hourly
rows, tri-modal value histogram (<100 / 1k–10k / ~800k) with zero
overlap between bands. At hourly resolution, 53 of 87 corruption-
window days have ≥1 real-register sample.

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
