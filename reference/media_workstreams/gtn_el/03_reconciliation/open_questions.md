# Open questions — gtn_el

### B612 formula double-subtracts T8-A3-A14-112

**Issue:** The B612 accounting formula subtracts BOTH T8-A3 and T8-A3-A14-112:

```
B612 = T48 + T7 + T8 + T9 − T8-B5 − T8-B6 − T7-A2-257 − T8-A3 − T8-A3-A14-112
```

T8-A3 physically includes T8-A3-A14-112 (confirmed: T8-A3 ≈ 69k kWh/month, A14-112 ≈ 19k kWh/month, parent > child). Subtracting both creates a ~19 MWh/month conservation gap at the campus level.

**Evidence:**
- `01_extracted/excel_formulas.csv` row 12: both T8-A3 (col Z) and T8-A3-A14-112 (col AA) are sub terms
- Campus conservation: net appearance of T8-A3-A14-112 across all buildings = −1−1+1 = −1 (should be 0)
- B612 is understated by ~19 MWh/month (3% of its ~511 MWh total)

**Impact:** B612's per-building total in the Excel is systematically lower than physical reality. Campus-level total also understated. Does NOT affect other buildings' per-building totals.

**Possible explanations:**
1. Intentional accounting choice (the ~19 MWh is "lost in transit")
2. Formula error that went unnoticed (small relative to total)
3. My physical hierarchy assumption is wrong (T8-A3 does NOT include T8-A3-A14-112)

**Status:** Open. Needs on-site verification of whether T8-A3 is physically upstream of T8-A3-A14-112.

### B659.T28-3-5 consumption not attributed to any building

**Issue:** B659.T28-3-5 (~8k kWh/month) is subtracted from B659's formula but does not appear as an add term in any building row. This consumption is "lost" from the building-level rollup.

**Evidence:**
- `01_extracted/excel_formulas.csv`: T28-3-5 appears only as sub in B659 row 39
- `01_extracted/excel_meters_used.csv`: roles=sub, buildings=659

**Impact:** ~8 MWh/month not attributed to any building. Small but real.

**Status:** Open. Likely serves non-tenant infrastructure.

### B611.T4 sub-feeders (T4-A3, T4-C1, T4-C4) have no BMS data

**Issue:** Three sub-feeders of B611.T4 appear in the Excel formula but have no Snowflake timeseries. Buildings B631 and B613 depend entirely on these meters for their EL consumption.

**Evidence:**
- `02_crosswalk/meter_id_map.csv`: no Snowflake match
- B631 formula: T4-A3 + T4-C4 (both missing)
- B613 formula: T4-C1 (missing)

**Impact:** Cannot validate B631 or B613 EL consumption from BMS data. Their building totals will be zero in Snowflake-derived calculations despite having Excel-reported consumption.

**Status:** Open. Need to check if these meters report via a different system (PME, Avläsning).

### B621.T5 and B621.T6 have no BMS data

**Issue:** Two parent transformers for B621 are not in Snowflake. Their sub-feeders (T5-2-5, T6-2-5, T6-3-1) ARE in BMS.

**Evidence:**
- `02_crosswalk/meter_id_map.csv`: no Snowflake match for T5 or T6

**Impact:** B621's building total cannot be fully computed from Snowflake (only T29 + T30 are available, T5 + T6 are missing). Buildings B651, B655, B658 are unaffected (their meters have BMS data).

**Status:** Open.
