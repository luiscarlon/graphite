# Snäckviken — cross-media patch follow-ups

Scenarios discovered during the Snäckviken annotation pass that **are
NOT yet applied** as patches. They fall into three categories:

1. **Existing primitive, restructuring required** — the fix fits a
   primitive we already have (`bracket`, `interpolate`, `sum`,
   `rolling_sum`) but applying it would require touching pre-existing
   auto-generated refs.
2. **New primitive candidate** — the fix needs a compute-layer
   primitive we haven't built yet.
3. **Not fixable in the ontology** — structural Excel features we
   can only document, not replicate.

---

## 1. Existing-primitive, restructuring required

### 1.1 B217.Å1_VMM71 bracket + interpolate upgrade — **HIGH VALUE**
See `reference/docs/snv_anga_followups.md` for the full analysis.
Deferred because it requires removing the pre-existing :d.A|B|C|D
segmentation. Recovers ~484 MWh of real Jul–Oct 2025 consumption.

### 1.2 B217.VP1_VMM61 (värme) — 60-day flat-carry gap, children sum candidate
B217 värme went offline 2025-08-05 and resumed via device swap
2025-10-04. The current `rolling_sum` over :d.A|:d.B|:d.C flat-carries
across the 60-day gap, losing the real consumption during that window.

Fix options:
- **`sum` children-patch** if B217 has downstream värme meters that
  captured the flow. Topology says B217 has no children in värme — so
  this path is closed.
- **`interpolate`** between the pre-outage and post-swap counter
  endpoints. Pre-outage value 662831.21; post-swap first value needs
  to be read from the new device's offset. The interpolate window is
  60 days — long, so the linear-ramp shape assumption is weak and the
  integral recovered is an estimate, not a measurement.

**Status:** worth discussing. The 60-day outage is outside the Jan/Feb
2026 reference period so no facit impact, but the 2025 annual total
for B217 värme is under-reported.

### 1.3 B217.Å1_VMM71 Aug 6 glitch — micro-gap currently carried flat
Inside the big register-corruption window, segment :d.B covers
2025-08-03 → 2025-08-06 and :d.C starts 2025-08-07. The 1-day gap
between Aug 6 and Aug 7 is flat-carried. Subsumed by the larger B217
bracket+interpolate upgrade (item 1.1) if we take that on.

### 1.4 B307.T10-5-2 / T10-6-5 / T10-7-3 (el) — Feb 2026 offlines, low impact
Three B307 el sub-meters went offline late February 2026 at near-zero
values (0.39 / 0.284 / 0.295 kWh). The impact is negligible and the
existing ref validity handles them correctly; not a patch candidate.

### 1.5 B201.KB1_Elogg, B207.VENT, B317.KV1_* — Feb 2026 offlines
Six meters across kyla and kallvatten went offline during February
2026. None of them have children suitable for `sum`-patching (they're
leaves). The lost consumption from offline-date to end-of-February is
unrecoverable without external reference. `interpolate` would require
a post-window endpoint we don't have; these remain documented outages
only.

---

## 2. New primitive candidates

### 2.1 Fractional-subtract / weighted-sum
Affects: SNV kyla (B302/B303/B305/B307 tenant splits), SNV sjövatten
(BPS_V2 pool distributed 0.09/0.18/0.18/0.46 to B301/B302/B303/B307),
SNV el (T26S 0.5 pool, T29 1/3 split, T49 0.4 pool, T32-4-2 75/25
split, T21-6-2-A 50/50 split, T77-4-5 50/50 split).

**Pattern:** a parent meter's reading gets `k × meter.net` subtracted
at multiple children, where k < 1. Current topology model only
supports `hasSubMeter` (full subtraction) or `feeds` with coefficient
(which distributes the PARENT's residual, not a fraction of an
independent meter's reading).

**Compute-layer requirement:** `meter_net` view needs a fractional
subtraction primitive on top of `hasSubMeter`:
```
net(M) = flow(M) − Σ hasSubMeter k × flow(child)
```
where `k` defaults to 1.0 but can be a per-edge coefficient.

**Impact if built:** resolves ~22 MWh of persistent Snäckviken
residuals (kyla + sjövatten + el fractional pools). Worth doing, but
is a `views.sql` change, not just an ontology ref.

### 2.2 Counter-reset / rollover handling
Not observed in Snäckviken — counters roll over by device swap
(which we handle via `rolling_sum` segment split). But noted as a
theoretically missing primitive: if a single device's counter
mechanically overflows (e.g. hits 9999999 and returns to 0) without
a device change, our grammar has no way to represent it.

### 2.3 Multi-source bracket (intersect)
A meter whose raw signal is corrupt, but has a trustworthy sibling
that replicates the same physical flow. `bracket` currently accepts
one source. A multi-source variant could use the sibling as
additional evidence for the valid range. No clear Snäckviken
candidate, but worth noting.

---

## 3. Not fixable in the ontology (document only)

### 3.1 STRUX-only meters (SNV el, SNV sjövatten)
Meters that exist in Excel / STRUX but have no Snowflake equivalent.
Per project convention, we do not synthesize Snowflake readings from
STRUX values. The ontology reads zero; Excel has the cached STRUX
figure; the residual is persistent.

**Affected:** B209.T21/T32, B304 T26S/T40 family, B313.T26S summary,
B334 T87–T92 summary (snv el); B304-52-V2-AW026 (snv sjövatten);
B202.VENT, B331.KB1, B336.KB1 (snv kyla).

### 3.2 Triple-meter Excel attribution conflicts (SNV kallvatten)
B313.KV1_VMM22_V and B315.KV1_VMM21_V each appear in multiple Excel
formula rows as +term or −term. Our one-parent-per-meter rule picks
one attribution; the others absorb as residuals. Documented in
annotations. Not fixable.

### 3.3 Excel-cooked coefficients (SNV el, SNV sjövatten)
Some Excel rows bake month-variable coefficients into hidden R-column
or use monthly R-factors. Not reproducible from static ontology
coefficients. Documented.

### 3.4 B307 ånga / B330 double-subtraction (SNV ånga)
Same family as 3.2 but for steam. Annotated.

---

## Priorities (objective read)

Most-impactful if taken on:
1. **B217.Å1_VMM71 bracket+interpolate** (~484 MWh recovered, Jul–Oct
   2025, no Jan/Feb facit impact) — see §1.1.
2. **Fractional-subtract compute primitive** (~22 MWh aggregate
   Snäckviken residuals resolved) — see §2.1.
3. **B217.VP1_VMM61 värme 60-day interpolate** (2025 annual accuracy
   only; no facit impact; weak linear assumption) — see §1.2.

Everything else is either already covered by annotations, structural
Excel features that can't be mirrored, or too low-impact to prioritize.
