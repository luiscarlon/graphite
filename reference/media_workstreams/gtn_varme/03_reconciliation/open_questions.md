# open_questions — gtn_varme

### B642.VS1 additional heating feed

B642.VS1_VMM61 consumption (438 MWh/month) far exceeds its PDF parent B615.VS1_VMM61 (29 MWh/month). The edge is arrow-confirmed in the PDF so the direction is correct. B642 must have additional heating feeds not shown on the 2025-02-26 flow schema.

**Impact:** Conservation validation for the B614→B615→B642 chain is meaningless until the additional feed is identified. Building-level accounting unaffected (Excel handles this by subtracting B642 directly from B614, not from B615).

**Next step:** On-site inspection to identify additional heating feeds to B642 not shown on the flow schema.

---

### B616.VP1_VMM62 children exceed parent

B616.VP1_VMM62 is the auto_root_degree root for a connected component including VS1, VS2, and B661. But the children's total consumption far exceeds VP1_VMM62. The parser connected them based on pipe proximity, not flow direction arrows.

**Impact:** Conservation validation for B616.VP1_VMM62 → {VS1, VS2, B661} is invalid. Building-level accounting unaffected (Excel adds all four B616 meters and subtracts B661 directly).

**Next step:** Review flow_schema_preview.html for B616 area. The auto_root_degree connections may be pipe adjacency rather than parent-child flow. Consider VLM edge check for B616 section of the PDF.

---

### B612.VP2_VMM61 flat data

B612.VP2_VMM61 is the PDF root for the VP2 circuit through B612 but reported zero delta for 35 days during the observation window. It's not in any Excel formula. The meter might be decommissioned, intermittent, or measuring a different quantity.

**Impact:** Conservation validation for the B612.VP2_VMM61 sub-tree is unreliable during flat periods. The Excel accounting bypasses VMM61 by starting from VMM62.

**Next step:** Verify meter status with operations.

---

### B621.VP1_VMM61 high unaccounted flow (91.5%)

B621.VP1_VMM61 shows 91.5% mean conservation residual. Its children are B622, B623, B658, and B621.VÅ9_VMM41 (PDF-only, no data). Most flow goes to unmetered consumers or through the VÅ9 recovery meter (which has no Snowflake data).

**Impact:** Building-level accounting unaffected (Excel handles this). But conservation shows most of B621's heating flow is unaccounted.

**Next step:** Check if B621.VÅ9_VMM41 was recently connected to BMS or if the meter was decommissioned.

---

### B643.VP1_VMM61 high unaccounted flow (89.4%)

Similar to B621: B643.VP1_VMM61 shows 89.4% residual. Its only child is VÅ9_VMM41 (small recovery meter). Most of VP1's flow goes to building consumption (not through VÅ9_41).

**Impact:** Expected — VP1 is the main building intake and VÅ9_41 is a small recovery circuit. The residual represents building consumption, not missing meters.

---

### B658.VP1_VMM61 counter reset Feb 2 — swap or offline?

B658.VP1_VMM61_E had a counter reset on 2026-02-02 (Δ=-1308.996). The detect_meter_swaps script classified it as `offline`. The Excel shows B658 Jan=14.27 MWh, Feb=0.00 MWh. So the meter stopped reporting in February.

**Impact:** B658 is a leaf meter (no children) so no patch is possible. Feb 2026 reading is lost.
