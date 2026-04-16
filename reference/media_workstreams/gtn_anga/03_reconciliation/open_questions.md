# Open questions — gtn_anga

Unresolved items. When resolved, move the entry to `decisions.md` with a closing date.

---

### Is `B611.Å1_VMM72` ever reconciled against consumption?

Per the Excel accounting formula, `B611.VMM72`'s flow is implicitly inside `B611.VMM73`'s inlet reading minus `B622.VMM72`. But that means `B611.VMM72`'s own meter is **not** being compared to anything else — it's live in the BMS but unused in allocation.

- **Risk:** if `B611.VMM72` drifts or fails, the accounting wouldn't notice.
- **Next step:** check with the data-quality team whether the BMS has a separate reconciliation for this meter, or whether it's a known orphan. If orphan, flag it for monitoring.

---

### What do the `faktor` column (col R) values encode?

The Ånga sheet has a `Faktor` column (col R) at row 7 but no values populated on any row. Other media sheets may use it for coefficients. Unclear whether it's reserved for tenant splits, unit conversions, or something else.

- **Next step:** check Kyla and Värme sheets once those workstreams open; if the column is populated there, document its semantics and add a `coefficient` column to `facit_relations.csv` accordingly.

---

### Commissioning events detected in 2025 — which meters were swapped?

The timeseries anomalies flag two meter swaps:
- `B616.Å1_VMM71_E` — reset on 2025-11-05 (Δ=−17758 MWh)
- `B642.Å1_VM72` — reset on 2025-07-31 (Δ=−31533 MWh)

Neither is reflected in any source document (no comment, no drawing annotation). Is this a counter-rollover, physical replacement, or recalibration?

- **Risk:** a counter rollover preserves cumulative consumption; a replacement breaks the continuity. Our conservation check handles both, but the meaning differs.
- **Next step:** ask the BMS / operations team; record the answer in `04_validation/anomalies.md`.

---

### Three meters appear dead for all of 2025 — is that real?

Timeseries analysis flags:
- `B613.Å1_VM71` — 308/367 days with zero delta
- `B641.Å1_VM71` — all 367 days zero delta
- `B841.Å1_VMM71_E` — all 367 days zero delta

These are physically real meters per the flow schema and Excel. Either the buildings they serve are idle (possible — e.g. a test bay that's currently unused) or the meters are broken.

- **Risk:** treating a broken meter as "zero consumption" under-attributes to the downstream building.
- **Next step:** confirm with site operations whether buildings 613, 641, and 841 actually consume no steam. If they do, the meters need replacement and the conservation check should exclude them until fixed.

---

### Boiler-side meters live above the flödesschema

The `Evidence Gärtuna` sheet (and the `Rapport Site` rollup) almost certainly reference boiler/plant meters that sit *upstream* of `B600S` and `B600N`. The flow schema doesn't show them — it starts at the site entry.

- **Next step:** when extracting the Evidence and Total GTN tabs for the ontology layer, enumerate any meters above the flow-schema root and represent them as a `source_plant` node in `05_ontology/` that feeds both `B600S` and `B600N`.
