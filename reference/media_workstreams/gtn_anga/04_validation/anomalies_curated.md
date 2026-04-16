# Conservation anomalies — curated

Human-annotated companion to `anomalies.md`. The auto-classifier is the starting point; this file layers in cross-evidence from `01_extracted/timeseries_anomalies.csv`, the flow schema, and the Excel formulas to explain *why* each parent lands where it does.

## Summary

| parent | auto flag | curator's read | action |
|---|---|---|---|
| `B600S.Å1_VMM71` | `losses_stable` | **confirmed** — 9-child south main with steady 15% residual is real steam loss. Nov dip to ~1% is one-off; likely a reading issue on B821 or B841, not a structural change. | document loss rate; no action |
| `B611.Å1_VMM73` | `losses_stable` | **confirmed** — 37% loss between `B611.VMM73` inlet and its two downstream taps (`B611.VMM72` side-tap + `B622.VMM72`). Could also include the unmetered `B611.VMM72`-internal consumption (Excel formula doesn't wire it in). Worth a second look. | document; cross-check `B611.VMM72` behaviour |
| `B612.Å1_VMM71` | `dead_children` | **confirmed** — both `B613.VMM71` and `B641.VMM71` flat for 367/367 days (see `01_extracted/timeseries_anomalies.csv`). Physical meters exist and report, but report zero. | operations follow-up on whether buildings 613 and 641 actually consume steam |
| `B600N.Å1_VMM71` | `swap_event` | **partial** — the 36pp Oct→Nov jump is mechanically caused by `B616.Å1_VMM71_E`'s reset on 2025-11-05. Before that, the +60–80% residual is *still* abnormally high for a 4-child branch; smells like a missing downstream consumer that varies seasonally. | separate the swap effect from the underlying drift by excluding Nov data; re-run to see if pre-Nov residual classifies as `drift_seasonal` |
| `B614.Å1_VMM71` | `swap_event` | **confirmed** — the wild negative residuals Jan–Jun (child > parent by 7833%) reverse to +90% from Jul onwards. Driving event is `B642.Å1_VM72`'s reset on 2025-07-31. Suggests B642.VMM72 was replaced in July. | confirm swap date; before-and-after totals should not be summed. |
| `B642.Å1_VMM72` | `swap_event` | **partial** — auto flag triggers because of the Nov shift caused by `B642.Å1_VMM71` coming online mid-year (readings go from always-0 to meaningful ~ Nov). This is a **commissioning** event, not a replacement. | record commissioning date; treat B642.VMM71 as not-yet-installed before ~Nov 2025 |

## Detailed notes per parent

### `B600S.Å1_VMM71` — steady losses on the south main

- **12 months** with residual 10%..22%, mean 15.1%, stdev 4.9.
- The +1% November outlier is driven by a single low-reading month across multiple children. No structural change.
- Physical interpretation: a 12 BAR south main feeding 9 buildings, at roughly 2 km total length, with a steady ~15% thermal/flash-steam loss is well within published industry figures.
- **No action** beyond recording the loss rate. Later, if the ontology wants a per-edge loss coefficient, derive it from this mean.

### `B611.Å1_VMM73` — 37% loss, but one unmetered meter on the branch

- Parent `B611.VMM73` sits inline on the x=1476 vertical; its only two registered children are `B611.VMM72` (side-tap) and `B622.VMM72` (dead-end).
- `B611.VMM72` does read live in the BMS (`B611.Å1_VM72`) but is **not** in any Excel accounting row (see `decisions.md` entry 4).
- The 37% residual plausibly splits into: (a) real losses on the 12 BAR→3 BAR pressure reduction, (b) consumption at `B611.VMM72` that is counted here but attributed to building 611 via a different path.
- **Action:** after the first ontology iteration, compare B611.VMM72's own readings to the B611.VMM73 residual to quantify the split.

### `B612.Å1_VMM71` — dead submeters, not a topology error

- Parent `B612.VMM71` has 12 months of positive flow.
- Children `B613.VMM71` and `B641.VMM71` **both read exactly zero** for all 367 days in the export (see `01_extracted/timeseries_anomalies.csv`).
- The Excel formula for B612 uses both meters as subtractive (`− B613.VM71 − B641.VM71`), meaning the accounting correctly attributes all of B612.VMM71's flow to building 612 when the children read 0. But the drawings say those meters should be alive.
- **Most likely cause:** physical meters are frozen / broken / not transmitting. Low probability that the drawings are wrong (the topology has been validated against the flow schema).
- **Action:** operations ticket — verify meters B613.VMM71 and B641.VMM71 are physically operational; if not, flag for replacement.

### `B600N.Å1_VMM71` — swap masks underlying drift

- Residual 60–80% Jan–Oct, 33% Nov–Jan. Classifier flags `swap_event` on the 36pp Nov drop.
- Cause of the shift: `B616.Å1_VMM71_E` (a B600N child) was reset on 2025-11-05, losing 17 758 MWh cumulative. Post-swap the meter reports normal daily deltas, which shows up as higher children sum and hence lower parent-minus-children.
- **Sub-finding:** pre-Nov, the 60–80% residual is *still too high* for a 4-child north spine. Summer months touch 80%. That smells like a missing consumer — possibly a summer-only process.
- **Action:** after operations confirms the `B616` swap date, re-run the conservation check excluding Nov-Dec and see whether the pre-swap residual is stable (pure losses) or seasonal (missing consumer). Answer goes in `decisions.md`.

### `B614.Å1_VMM71` — clear swap event, split the year

- Jan–Jun: residual wildly negative (e.g. −7743% in March), meaning child `B642.VMM72` read *more* than parent `B614.VMM71`. Physically impossible unless one of them is mis-counting.
- 2025-07-31: `B642.Å1_VM72` logged a −31 533 MWh reset (see `01_extracted/timeseries_anomalies.csv`).
- Jul–Dec: residual flips to +90–100% (child now reads ≈0 while parent still reads; the replacement meter is re-accumulating from 0).
- **Interpretation:** `B642.VMM72` meter was **replaced** around 2025-07-31. The old meter had a cumulative value ~31 533 MWh before replacement; the new meter started at 0.
- **Action:** treat the year as two segments. Pre-2025-07-31 residual is uninterpretable with current data; post-replacement residual (90–100%) suggests B642's new meter is either dead or hasn't registered significant flow yet. Confirm with operations.

### `B642.Å1_VMM72` — `B642.VMM71` commissioning

- Only child is `B642.VMM71`. It reads zero Jan–Oct, non-zero Nov–Jan.
- Interpretation: `B642.VMM71` was **commissioned** in late 2025, not swapped. Before commissioning, there's no child signal so residual is 100%; after commissioning, residual drops to ~50–66%.
- Consistent with the finding above that `B642.VMM72` itself was replaced 2025-07-31 and its downstream submeter (`B642.VMM71`) was brought online later to complete the instrumentation of that branch.
- **Action:** record commissioning date. For the pre-2025-Nov window, treat B642.VMM71 as not-yet-existent (this explains the Excel formula's omission — if the meter didn't exist when the spreadsheet was designed, there'd be no XLOOKUP for it).

## Cross-cutting open items

- We're treating 2025 as one topology. At minimum, two events (B642 swap in July, B616 swap in November) mean the network instrumentation changed. The `05_ontology` stage should represent each meter with an installation window, not an always-valid assumption.
- Commissioning of `B642.VMM71` in late 2025 means it might appear in a refreshed flow schema or Excel file in 2026. Revalidate both sources if new drawings arrive.
