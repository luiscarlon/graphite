# Decisions — gtn_el

### 2026-04-19 — No flow-schema PDF exists for electricity

**Question:** Which source is authoritative for EL topology?

**Sources:**
- `00_inputs/README.md`: confirmed via HF Rörsystem master index — no PDF for EL
- `01_extracted/excel_formulas.csv`: 101 meter references across 39 building rows
- `01_extracted/timeseries_monthly.csv`: 68 meters in Snowflake BMS

**Decision:** Topology from naming hierarchy (T## → T##-#-#) supplemented by Excel formula structure. No PDF parser output exists.

### 2026-04-19 — Naming hierarchy determines physical topology

**Question:** How to derive parent-child edges without a PDF?

**Sources:**
- EL meters use `B###.T##-#-#` naming where T## is the transformer station and dashes indicate feeder hierarchy
- `01_extracted/timeseries_monthly.csv`: confirmed via monthly delta comparison for all major cases:
  - B612.T8-S (244k kWh) > T8-B5 + T8-B6 + T8-A3 (74k kWh) — 70% residual ✓
  - B641.T8-A3 (69k) > B652.T8-A3-A14-112 (19k) — 73% residual ✓
  - B821.T39-1 (164k) > T39-5-1 + T39-5-2 + T39-5-3 + T39-6-2 (71k) — 57% residual ✓
  - B643.T37 (169k) > T37-2-1 (128k) — 24% residual ✓
  - B833.T44-S (242k) > T44-6-1 (18k) — 93% residual ✓
  - B653.T17 (154k) > T17-A7 (7k) — 95% residual ✓

**Decision:** `T##` is the physical parent of `T##-X-Y` when the transformer number is a strict prefix. This produces 21 `el_naming_hierarchy` edges. All validated by data (parent > child in every case).

### 2026-04-19 — B821.T39-1 sub-feeder edges from Excel formula

**Question:** T39-1 and T39-5-1 are NOT strict naming prefixes (T39-1 ≠ prefix of T39-5-1). Are they parent-child?

**Sources:**
- `01_extracted/excel_formulas.csv` row 48: B821 = T39-1 − T39-5-1 − T39-5-2 − T39-5-3 − T39-6-2
- `01_extracted/timeseries_monthly.csv`: T39-1 (164k) > sum of subs (71k). T39-1 is the main breaker meter.
- Physical interpretation: T39-1 = main incoming meter (position 1 = main breaker); T39-5-* = outgoing feeder meters

**Decision:** T39-1 → {T39-5-1, T39-5-2, T39-5-3, T39-6-2} as hasSubMeter edges. Derived from `excel_formula_B821` (not naming hierarchy). T39-1 is the aggregate measurement; sub-feeders serve B869.

### 2026-04-19 — excel_relations.csv rejected for EL topology

**Question:** Can the `excel_relations.py` output be used?

**Sources:**
- `01_extracted/excel_relations.csv`: picks the first + term as "inlet" for each building
- Example: B611 formula has T1+T2+T3+T4+T41 as add terms → extractor picks T1 as inlet
- Result: T1 → T4-A3 (WRONG: T4-A3 is a sub-feeder of T4, not T1)

**Decision:** Reject `excel_relations.csv` for EL. The extractor assumes one principal inlet per building, but EL buildings have multiple independent transformers. The naming hierarchy is the correct source for parent-child relationships.

### 2026-04-19 — timeseries_relations.csv rejected for EL

**Question:** Are the timeseries residual-fit edges valid?

**Sources:**
- `01_extracted/timeseries_relations.csv`: 8 proposed edges
  - B611.T1 → T2 (67%), T1 → T3 (54%), T1 → T4 (69%), T1 → T41 (27%)
  - B616.T31 → T32, T31 → T33
  - B650.T23 → T24
  - B653.T17 → T55

**Decision:** Reject all. These propose parent-child between SIBLING transformers in the same building. T1, T2, T3, T4, T41 are independent transformer stations — residual-fit found seasonal correlation (same building), not physical hierarchy.

### 2026-04-19 — 0.001 coefficient is unit conversion, not allocation

**Question:** How to classify the 0.001 factor on every formula term?

**Sources:**
- `00_inputs/README.md`: "Snowflake quantity: Active Energy Delivered (kWh, scaled ×0.001 by the EL sheet's $F$5 cell to report MWh)"
- `01_extracted/excel_formulas.csv`: all 101 terms have faktor=0.001

**Decision:** The 0.001 factor is universal kWh→MWh unit conversion applied via the $F$5 cell. It is NOT a physical allocation coefficient. All hasSubMeter edges carry NULL coefficient (not 0.001). Differs from kyla where 0.38/0.9 are genuine allocation factors.

### 2026-04-19 — B659.T28-3-5 subtracted but not attributed

**Question:** B659 formula subtracts T28-3-5, but T28-3-5 never appears as a + term for any building.

**Sources:**
- `01_extracted/excel_formulas.csv`: B659 row 39: sub T28-3-5
- `01_extracted/excel_meters_used.csv`: T28-3-5 roles=sub only, building=659
- `01_extracted/timeseries_monthly.csv`: B659.T28-3-5 has consistent readings (~8k kWh/month)

**Decision:** Keep in ontology. Assign to building B659 (physical location). Document as unattributed sub-feeder — likely serves non-tenant infrastructure (outdoor lighting, utility, or parking). The meter IS live and measures real consumption.

### 2026-04-19 — Provider meters (H-prefix) without BMS data

**Question:** Include B660.H23-1, B660.H3-1, B951.H3-B in ontology?

**Sources:**
- `02_crosswalk/meter_id_map.csv`: no Snowflake match for these three
- `01_extracted/excel_formulas.csv`: B660 intake row, B921 row
- B951.H4-A DOES have BMS data despite H-prefix

**Decision:** Include all in facit_meters.csv but they will have no timeseries_refs in the ontology. They are provider/utility meters with manual readings only. B660 is the campus EL intake point (like B600 for steam).

### 2026-04-19 — B621.T5 and B621.T6 parent transformers without BMS

**Question:** Include these in the topology even though they have no Snowflake data?

**Sources:**
- `01_extracted/excel_formulas.csv`: B621 row 18 — both are add terms
- `02_crosswalk/meter_id_map.csv`: no Snowflake match for either
- Their sub-feeders (T5-2-5, T6-2-5, T6-3-1) DO have BMS data

**Decision:** Include in facit_meters.csv and facit_relations.csv (as parents of their sub-feeders). They will have no timeseries_refs but the topology edges are valid. B621's building total cannot be fully computed from Snowflake.

### 2026-04-19 — B616.T33-6-1 completely dead (424 days zero delta)

**Sources:**
- `01_extracted/timeseries_anomalies.csv`: "424 days, all zero delta"
- `01_extracted/excel_formulas.csv`: subtracted from B616, added to B835

**Decision:** Keep in ontology. Mark as offline from 2025-01-01. The meter is real (exists in Snowflake) but produces zero readings for the entire observation window. B835's EL consumption via this feeder is zero.

### 2026-04-19 — Counter resets are device swaps, not outages

**Sources:**
- `01_extracted/meter_swaps.csv`: 11 swap events, all with old_last_value ≈ 10M
- The ~10M counter values and immediate resume pattern indicate counter register rollover or device replacement, not outage

**Decision:** All 11 swap events modeled as device swaps (A/B segments + rolling_sum derived ref). One offline event: B616.T31-6-2 offline 2026-02-12. `slice_timeseries.py` already segments at these resets; `build_ontology.py` will create the multi-segment timeseries refs.
