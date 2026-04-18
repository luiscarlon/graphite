# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B611.VARME_BUILDING` | `no_data` | no monthly residuals available | B613.VP1_VMM61, B622.VP2_VMM61, B631.VP1_VMM62, B631.VP1_VMM63 |
| `B611.VP1_VMM61` | `swap_event` | max adjacent-month jump 464pp; mean=-216.2%, sd=242.2 | B611.VARME_BUILDING, B611.VÅ9_VMM41, B611.VÅ9_VMM43, B613.VP1_VMM61, B622.VP2_VMM61, B631.VP1_VMM61, B631.VP1_VMM63 |
| `B611.VP2_VMM61` | `swap_event` | max adjacent-month jump 137pp; mean=-184.9%, sd=69.0 | B611.VARME_BUILDING, B611.VÅ9_VMM41, B611.VÅ9_VMM43 |
| `B611.VÅ9_VMM41` | `swap_event` | max adjacent-month jump 28pp; mean=+62.5%, sd=10.9 | B611.VARME_BUILDING, B611.VÅ9_VMM43 |
| `B612.VARME_BUILDING` | `no_data` | no monthly residuals available | B613.VP2_VMM61, B637.VP2_VMM61, B641.VP2_VMM61, B654.VP2_VMM61 |
| `B612.VP2_VMM61` | `no_data` | no monthly residuals available | B612.VP2_VMM62, B612.VP2_VMM63, B612.VÅ9_VMM41, B613.VP1_VMM62, B637.VP2_VMM61, B654.VP2_VMM61 |
| `B612.VP2_VMM62` | `swap_event` | max adjacent-month jump 208pp; mean=-42.7%, sd=67.2 | B612.VARME_BUILDING, B612.VP2_VMM63, B637.VP2_VMM61, B641.VP2_VMM61, B654.VP2_VMM61 |
| `B612.VP2_VMM63` | `swap_event` | max adjacent-month jump 148pp; mean=-594.0%, sd=89.6 | B612.VARME_BUILDING, B612.VP2_VMM64, B641.VP2_VMM61 |
| `B612.VP2_VMM64` | `swap_event` | max adjacent-month jump 968pp; mean=-679.9%, sd=238.4 | B612.VARME_BUILDING, B612.VP2_VMM65 |
| `B612.VP2_VMM65` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B612.VARME_BUILDING |
| `B613.VP1_VMM61` | `swap_event` | max adjacent-month jump 38pp; mean=-34.2%, sd=20.4 | B613.VARME_BUILDING, B613.VP1_VMM62, B613.VP2_VMM61 |
| `B613.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B613.VARME_BUILDING |
| `B614.VARME_BUILDING` | `no_data` | no monthly residuals available | B615.VS1_VMM61, B642.VS1_VMM61 |
| `B614.VS1_VMM61` | `swap_event` | max adjacent-month jump 76pp; mean=-91.0%, sd=40.8 | B614.VARME_BUILDING, B614.VÅ9_VMM41, B615.VS1_VMM61, B642.VS1_VMM61 |
| `B614.VÅ9_VMM41` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B614.VARME_BUILDING |
| `B615.VS1_VMM61` | `swap_event` | max adjacent-month jump 2271pp; mean=-1755.0%, sd=730.4 | B615.VARME_BUILDING, B642.VS1_VMM61 |
| `B616.VARME_BUILDING` | `no_data` | no monthly residuals available | B661.VP1_VMM61 |
| `B616.VP1_VMM61` | `swap_event` | max adjacent-month jump 1016pp; mean=-313.4%, sd=329.8 | B616.VARME_BUILDING, B616.VP1_VMM62, B616.VS1_VMM61, B616.VS2_VMM61, B616.VÅ9_VMM41 |
| `B616.VP1_VMM62` | `swap_event` | max adjacent-month jump 187157pp; mean=-13308.5%, sd=48223.3 | B616.VARME_BUILDING, B616.VS1_VMM61, B616.VS2_VMM61, B661.VS1_VMM61 |
| `B616.VS1_VMM61` | `no_data` | no monthly residuals available | B616.VÅ9_VMM41 |
| `B616.VS2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B616.VARME_BUILDING |
| `B616.VÅ9_VMM41` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B616.VARME_BUILDING |
| `B621.VP1_VMM61` | `review` | mean=+91.5%, sd=3.3 | B621.VÅ9_VMM41, B621T.VARME_BUILDING, B622.VP1_VMM61, B623.VP1_VMM61, B658.VP1_VMM61 |
| `B621T.VARME_BUILDING` | `no_data` | no monthly residuals available | B622.VP1_VMM61, B623.VP1_VMM61, B658.VP1_VMM61 |
| `B622.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B622.VARME_BUILDING |
| `B622.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B622.VARME_BUILDING |
| `B623.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B623.VARME_BUILDING |
| `B625.VS1_VMM61` | `swap_event` | max adjacent-month jump 27pp; mean=+60.6%, sd=20.9 | B625.VARME_BUILDING, B625.VÅ9_VMM41 |
| `B625.VÅ9_VMM41` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B625.VARME_BUILDING |
| `B631.VP1_VMM61` | `no_data` | no monthly residuals available | B611.VÅ9_VMM41, B631.VP1_VMM62 |
| `B631.VP1_VMM62` | `swap_event` | max adjacent-month jump 72pp; mean=+14.3%, sd=37.8 | B631.VARME_BUILDING, B631.VP1_VMM63 |
| `B631.VP1_VMM63` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B631.VARME_BUILDING |
| `B634.VP1_VMM61` | `swap_event` | max adjacent-month jump 67pp; mean=+31.0%, sd=37.5 | B634.VARME_BUILDING, B634.VÅ9_VMM41 |
| `B637.VARME_BUILDING` | `no_data` | no monthly residuals available | B638.VP2_VMM61 |
| `B637.VP2_VMM61` | `swap_event` | max adjacent-month jump 34pp; mean=+75.6%, sd=9.6 | B637.VARME_BUILDING, B638.VP2_VMM61 |
| `B638.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B638.VARME_BUILDING |
| `B641.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B641.VARME_BUILDING |
| `B642.VS1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B642.VARME_BUILDING |
| `B643.VP1_VMM61` | `swap_event` | max adjacent-month jump 27pp; mean=+23.0%, sd=25.0 | B643.VARME_BUILDING, B643.VÅ9_VMM41, B643.VÅ9_VMM42 |
| `B643.VP2_VMM61` | `swap_event` | max adjacent-month jump 3674pp; mean=-655.4%, sd=909.8 | B643.VARME_BUILDING, B643.VÅ9_VMM41, B643.VÅ9_VMM42 |
| `B643.VÅ9_VMM41` | `swap_event` | max adjacent-month jump 928pp; mean=-572.5%, sd=288.1 | B643.VÅ9_VMM42 |
| `B643.VÅ9_VMM42` | `swap_event` | max adjacent-month jump 145pp; mean=-77.3%, sd=84.0 | B643.VP1_VMM61 |
| `B650.VARME_BUILDING` | `no_data` | no monthly residuals available | B655.VP1_VMM61 |
| `B650.VP1_VMM61` | `swap_event` | max adjacent-month jump 35pp; mean=+36.9%, sd=37.4 | B650.VARME_BUILDING, B655.VP1_VMM61 |
| `B650.VP3_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B650.VARME_BUILDING |
| `B652.VS1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B652.VARME_BUILDING |
| `B654.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B654.VARME_BUILDING |
| `B655.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B655.VARME_BUILDING |
| `B658.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B658.VARME_BUILDING |
| `B661.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B661.VARME_BUILDING, B661.VS1_VMM61 |
| `B674.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B674.VARME_BUILDING, B674.VÅ9_VMM41, B674.VÅ9_VMM42 |
| `B674.VP2_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B674.VARME_BUILDING, B674.VÅ9_VMM41, B674.VÅ9_VMM42 |
| `B674.VÅ9_VMM41` | `no_data` | no monthly residuals available | B674.VP1_VMM61, B674.VÅ9_VMM42 |
| `B674.VÅ9_VMM42` | `no_data` | no monthly residuals available | B674.VP2_VMM61 |
| `B821.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B821.VARME_BUILDING, B821.VS1_VMM61 |
| `B833.VARME_BUILDING` | `no_data` | no monthly residuals available | B834.VP1_VMM61 |
| `B833.VP1_VMM61` | `swap_event` | max adjacent-month jump 92pp; mean=+21.2%, sd=32.4 | B833.VARME_BUILDING, B833.VP1_VMM62, B833.VÅ9_VMM41, B834.VP1_VMM61 |
| `B833.VP1_VMM62` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B833.VARME_BUILDING |
| `B834.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B834.VARME_BUILDING |
| `B841.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B841.VARME_BUILDING |
| `B921.VP1_VMM61` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B921.VARME_BUILDING |

## Flag breakdown

- **`dead_children`** (26): B612.VP2_VMM65, B613.VP2_VMM61, B614.VÅ9_VMM41, B616.VS2_VMM61, B616.VÅ9_VMM41, B622.VP1_VMM61, B622.VP2_VMM61, B623.VP1_VMM61, B625.VÅ9_VMM41, B631.VP1_VMM63, B638.VP2_VMM61, B641.VP2_VMM61, B642.VS1_VMM61, B650.VP3_VMM61, B652.VS1_VMM61, B654.VP2_VMM61, B655.VP1_VMM61, B658.VP1_VMM61, B661.VP1_VMM61, B674.VP1_VMM61, B674.VP2_VMM61, B821.VP1_VMM61, B833.VP1_VMM62, B834.VP1_VMM61, B841.VP1_VMM61, B921.VP1_VMM61
- **`no_data`** (13): B611.VARME_BUILDING, B612.VARME_BUILDING, B612.VP2_VMM61, B614.VARME_BUILDING, B616.VARME_BUILDING, B616.VS1_VMM61, B621T.VARME_BUILDING, B631.VP1_VMM61, B637.VARME_BUILDING, B650.VARME_BUILDING, B674.VÅ9_VMM41, B674.VÅ9_VMM42, B833.VARME_BUILDING
- **`review`** (1): B621.VP1_VMM61
- **`swap_event`** (21): B611.VP1_VMM61, B611.VP2_VMM61, B611.VÅ9_VMM41, B612.VP2_VMM62, B612.VP2_VMM63, B612.VP2_VMM64, B613.VP1_VMM61, B614.VS1_VMM61, B615.VS1_VMM61, B616.VP1_VMM61, B616.VP1_VMM62, B625.VS1_VMM61, B631.VP1_VMM62, B634.VP1_VMM61, B637.VP2_VMM61, B643.VP1_VMM61, B643.VP2_VMM61, B643.VÅ9_VMM41, B643.VÅ9_VMM42, B650.VP1_VMM61, B833.VP1_VMM61

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
