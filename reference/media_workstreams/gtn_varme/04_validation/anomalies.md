# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B611.VP1_VMM61` | `review` | mean=+80.2%, sd=8.9 | B613.VP1_VMM61, B631.VP1_VMM61, B631.VP1_VMM63 |
| `B612.VP2_VMM61` | `no_data` | no monthly residuals available | B613.VP1_VMM62, B637.VP2_VMM61, B654.VP2_VMM61 |
| `B612.VP2_VMM62` | `review` | mean=+46.6%, sd=7.4 | B612.VP2_VMM61, B612.VP2_VMM63, B641.VP2_VMM61 |
| `B614.VS1_VMM61` | `review` | mean=+95.8%, sd=1.7 | B615.VS1_VMM61 |
| `B615.VS1_VMM61` | `swap_event` | max adjacent-month jump 2332pp; mean=-1879.5%, sd=646.0 | B642.VS1_VMM61 |
| `B616.VP1_VMM62` | `swap_event` | max adjacent-month jump 412pp; mean=+29.1%, sd=136.7 | B616.VS1_VMM61, B616.VS2_VMM61, B661.VS1_VMM61 |
| `B621.VP1_VMM61` | `review` | mean=+90.9%, sd=3.1 | B622.VP1_VMM61, B623.VP1_VMM61, B658.VP1_VMM61 |
| `B631.VP1_VMM61` | `no_data` | no monthly residuals available | B611.VÅ9_VMM41 |
| `B637.VP2_VMM61` | `swap_event` | max adjacent-month jump 22pp; mean=+76.4%, sd=7.9 | B638.VP2_VMM61 |
| `B643.VP1_VMM61` | `swap_event` | max adjacent-month jump 32pp; mean=+28.7%, sd=18.6 | B643.VÅ9_VMM42 |
| `B650.VP1_VMM61` | `swap_event` | max adjacent-month jump 35pp; mean=+49.0%, sd=29.8 | B655.VP1_VMM61 |
| `B674.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B674.VÅ9_VMM41 |
| `B674.VÅ9_VMM42` | `no_data` | no monthly residuals available | B674.VP2_VMM61 |
| `B833.VP1_VMM61` | `swap_event` | max adjacent-month jump 92pp; mean=+21.1%, sd=33.8 | B833.VP1_VMM62, B833.VÅ9_VMM41, B834.VP1_VMM61 |

## Flag breakdown

- **`dead_children`** (1): B674.VP1_VMM61
- **`no_data`** (3): B612.VP2_VMM61, B631.VP1_VMM61, B674.VÅ9_VMM42
- **`review`** (4): B611.VP1_VMM61, B612.VP2_VMM62, B614.VS1_VMM61, B621.VP1_VMM61
- **`swap_event`** (6): B615.VS1_VMM61, B616.VP1_VMM62, B637.VP2_VMM61, B643.VP1_VMM61, B650.VP1_VMM61, B833.VP1_VMM61

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
