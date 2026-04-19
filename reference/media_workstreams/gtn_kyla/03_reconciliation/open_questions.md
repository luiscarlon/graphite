# Open questions — gtn_kyla

Known unknowns; explicitly unresolved. Each entry states the question, the evidence so far, and the impact on the ontology.

---

### B661.KB1_Pkyl_Ack — suspicious magnitude (4500 MWh/month)

**Question:** B661.KB1_Pkyl_Ack reports 4400–4590 MWh/month from Apr 2025 onwards. For reference, B653.KB2_WVÄRME_ACK (the main plant meter for KB2 cooling) peaks at ~1210 MWh/month. Is B661.Pkyl_Ack measured in a different unit (kWh? kJ?) or is it measuring a different quantity (e.g., total chiller heat rejection)?

**Evidence:**
- `01_extracted/timeseries_monthly.csv`: B661.KB1_Pkyl_Ack monthly deltas: Jan=0, Feb=1, Mar=2720, Apr=4441, May=4589, Jun=4441, Jul=4589, Aug=4589, Sep=4441, Oct=1050, Nov=0, Dec=2162, Jan26=4589, Feb26=4144.
- The Prod-600 formula sums B661.Pkyl_Ack with B653.ACK (~600–1200), B654.KylEffekt_Ack (~25–38), and B654.KB2_Pkyl_Ack (dead, 0). No per-term coefficient. If all are in MWh, B661 dominates by 10×.
- The monthly pattern (near-constant 4441/4589, alternating 30/31 day months) suggests a fixed-rate device, ~6.2 MW continuous. This is consistent with a chiller compressor running at constant load.
- `01_extracted/excel_intake_meters.csv` row 21: B661.KB1_Pkyl_Ack is "Automatisk", unit "MWh". BUT the STRUX table may not have been updated if the meter was recently commissioned.

**Impact:** If the unit is wrong, the Prod-600 virtual total and any conservation checks involving it are invalid. The meter IS included in the facit and ontology, but its values should be treated with suspicion until confirmed with operations.

**Status:** Open. Needs on-site confirmation of meter unit/configuration.

---

### B612.KB1_PKYL — sporadic readings

**Question:** B612.KB1_PKYL reports in only 4 of 14 months (Jan=197, Apr=201, Jun=473, Sep=2049 MWh; all others=0). Is this a quarterly-read manual meter, a BMS meter with connectivity issues, or a counter that wraps erratically?

**Evidence:**
- `01_extracted/excel_intake_meters.csv`: B612.KB1_PKYL is listed both as "Automatisk" and "Manuell" (under the `B612-KB1-PKYL` label). Dual listing suggests it has both a BMS feed and a manual backup.
- `01_extracted/timeseries_monthly.csv`: When it does read, zero_days=n_days, meaning the per-day deltas are all 0 but the monthly register difference is nonzero. This is consistent with a counter that only gets read/updated at intervals, not daily.
- The Sep spike to 2049 MWh is anomalous (10× the Jan/Apr values). Could be a missed read causing accumulation, or a counter error.

**Impact:** Conservation of B612.KB1_PKYL vs children B637+B638 cannot be validated reliably. The B612/B641 allocation formulas depend on this meter. Timeseries in the ontology will have validity gaps.

**Status:** Open. Consider requesting BMS log from operations to verify counter behaviour.

---

### B833.KB1_GF4 — same sporadic pattern as B612.KB1_PKYL

**Question:** B833.KB1_GF4 reads only in Jan=141, Apr=292, Jun=143, Sep=986 MWh; all others=0. Same pattern as B612.KB1_PKYL.

**Evidence:**
- Same zero_days=n_days pattern. Both meters appear to be on the same read schedule (quarterly?).
- B833 formula: `B833 = B833.GF4 − B834.INT_VERK`. B834 reads normally (0.8–10 MWh/month). Conservation cannot be validated for the months B833 reads 0.

**Impact:** Same as B612.KB1_PKYL. Conservation between B833.GF4 and B834 only checkable for 4 months.

**Status:** Open.

---

### B821.KB2_VMM1 and B841.KB2_VMM51 — both dead, no Snowflake data

**Question:** B821.KB2_VMM1 has no Snowflake match at all. B841.KB2_VMM51 has a Snowflake match (`B841.KB2_VM51`) but reads all-zero for 14 months. Are these meters decommissioned? Is there a replacement under a different ID?

**Evidence:**
- B821 building has `B821.FV1_INT_VERK` (district heating, 4–58 MWh/month), `B821.KB2_VMM50_E` (dead), `B821.KB2_VMM51` (dead).
- B841 has `B841.FV1_INT_VERK` (district heating, 0–16 MWh/month), `B841.KB2_VM51` (dead), `B841.KB2_VMM50_E` (dead).
- Excel still references these meters in the accounting formulas. Either the Excel hasn't been updated to reflect decommissioning, or the meters are provider-read (manual) and not on BMS.

**Impact:** The B821→B841 edge exists in the facit but generates zero consumption. Buildings 821 and 841 will show 0 kyla consumption.

**Status:** Open.

---

### B654.KB2_Pkyl_Ack — dead since Feb 2025

**Question:** B654.KB2_Pkyl_Ack is referenced in both B600-KB2 and Prod-600 formulas but reads all-zero (last Snowflake data Feb 10, 2025). What happened to it?

**Evidence:**
- `01_extracted/timeseries_monthly.csv`: Jan=0, Feb=0 (only 10 days of data). No subsequent months.
- It's one of the "production" meters in Prod-600. With it dead, Prod-600 is missing one input.

**Impact:** Minor since it was already reading zero before going offline. The accounting formula is unaffected as long as it continues reading 0.

**Status:** Open. Low priority — the meter was contributing nothing anyway.
