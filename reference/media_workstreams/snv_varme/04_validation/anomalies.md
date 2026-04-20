# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B203.VP1_VMM61` | `no_data` | no monthly residuals available | B201.VP1_VMM61, B207.VP1_VMM61, B216.VP1_VMM61 |
| `B217.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B217.VS1_VMM61 |
| `B308.VS1_VMM61` | `swap_event` | max adjacent-month jump 23pp; mean=+41.5%, sd=11.0 | B307.VS1_VMM61, B327.VS1_VMM61 |
| `B310.VP1_VMM61` | `review` | mean=+90.9%, sd=3.0 | B311.VP1_VMM64, B311.VS2_VMM61 |
| `B310.VP1_VMM62` | `swap_event` | max adjacent-month jump 85pp; mean=+55.3%, sd=20.8 | B313.VS1_VMM61, B317.VP1_VMM61, B317.VP1_VMM63 |
| `B310.VP2_VMM61` | `swap_event` | max adjacent-month jump 5531pp; mean=-700.5%, sd=1540.0 | B301.VP2_VMM61, B301.VP2_VMM62, B302.VP2_VMM61, B302.VP2_VMM62, B303.VP2_VMM61, B304.VP2_VMM61, B304.VP2_VMM62, B305.VP2_VMM61, B312.VP2_VMM61, B312.VP2_VMM62, B341.VS1_VMM61, B385.VP2_VMM61, B385.VP2_VMM62 |
| `B311.VP1_VMM62` | `swap_event` | max adjacent-month jump 39pp; mean=+92.5%, sd=19.1 | B311.VP1_VMM61 |
| `B311.VP1_VMM65` | `dead_children` | residual = 100% every month (mean=99%, sd=0.6) | B381.VP1_VMM61 |
| `B311.VS2_VMM61` | `swap_event` | max adjacent-month jump 1678pp; mean=-1319.5%, sd=643.2 | B310.VP1_VMM62, B310.VS2_VMM61, B310.VS2_VMM62, B311.VP1_VMM62, B311.VP1_VMM65, B313.VP1_VMM62 |
| `B313.VP1_VMM62` | `swap_event` | max adjacent-month jump 226pp; mean=-29.0%, sd=50.0 | B314.VP1_VMM61, B317.VP1_VMM62 |
| `B314.VP1_VMM61` | `drift_seasonal` | mean=+64.5%, sd=12.9 — variable residual, check seasonal consumer | B315.VP1_VMM61 |
| `B318.VP1_VMM61` | `swap_event` | max adjacent-month jump 39pp; mean=+88.2%, sd=9.6 | B319.VP1_VMM61 |
| `B327.VS1_VMM61` | `review` | mean=+95.2%, sd=2.8 | B326.VS1_VMM61 |

## Flag breakdown

- **`dead_children`** (2): B217.VP1_VMM61, B311.VP1_VMM65
- **`drift_seasonal`** (1): B314.VP1_VMM61
- **`no_data`** (1): B203.VP1_VMM61
- **`review`** (2): B310.VP1_VMM61, B327.VS1_VMM61
- **`swap_event`** (7): B308.VS1_VMM61, B310.VP1_VMM62, B310.VP2_VMM61, B311.VP1_VMM62, B311.VS2_VMM61, B313.VP1_VMM62, B318.VP1_VMM61

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
