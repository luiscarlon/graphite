# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B600N.Å1_VMM71` | `swap_event` | max adjacent-month jump 109pp; mean=-95.2%, sd=42.7 | B600.ANGA_BUILDING, B600S.Å1_VMM71, B616.Å1_VMM71, B643.Å1_VMM71, B833.Å1_VMM71, B921.Å1_VMM71 |
| `B600S.Å1_VMM71` | `swap_event` | max adjacent-month jump 172pp; mean=+1.9%, sd=45.5 | B600.ANGA_BUILDING, B611.Å1_VMM71, B611.Å1_VMM73, B612.Å1_VMM71, B612.Å1_VMM72, B614.Å1_VMM71, B614.Å1_VMM72, B621.Å1_VMM70, B821.Å1_VMM71, B841.Å1_VMM71 |
| `B611.ANGA_BUILDING` | `no_data` | no monthly residuals available | B622.Å1_VMM72 |
| `B611.Å1_VMM71` | `review` | mean=+69.8%, sd=4.9 | B611.ANGA_BUILDING, B611.Å1_VMM72, B622.Å1_VMM72 |
| `B611.Å1_VMM72` | `review` | mean=-71.4%, sd=7.3 | B611.Å1_VMM73 |
| `B611.Å1_VMM73` | `losses_stable` | mean=+36.3%, sd=4.8 — steady steam/energy losses | B611.ANGA_BUILDING, B611.Å1_VMM72, B622.Å1_VMM72 |
| `B612.ANGA_BUILDING` | `no_data` | no monthly residuals available | B613.Å1_VMM71, B641.Å1_VMM71 |
| `B612.Å1_VMM71` | `review` | mean=+71.0%, sd=2.3 | B612.ANGA_BUILDING, B612.Å1_VMM72, B613.Å1_VMM71, B641.Å1_VMM71 |
| `B612.Å1_VMM72` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B612.ANGA_BUILDING |
| `B613.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B613.ANGA_BUILDING |
| `B614.ANGA_BUILDING` | `no_data` | no monthly residuals available | B642.Å1_VMM72 |
| `B614.Å1_VMM71` | `swap_event` | max adjacent-month jump 7582pp; mean=-664.8%, sd=1927.1 | B614.ANGA_BUILDING, B614.Å1_VMM72, B642.Å1_VMM72 |
| `B614.Å1_VMM72` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B614.ANGA_BUILDING |
| `B616.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B616.ANGA_BUILDING |
| `B621.Å1_VMM70` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B621T.ANGA_BUILDING |
| `B622.Å1_VMM72` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B622.ANGA_BUILDING |
| `B641.Å1_VMM71` | `no_data` | no monthly residuals available | B641.ANGA_BUILDING |
| `B642.Å1_VMM71` | `swap_event` | max adjacent-month jump 70pp; mean=-99.1%, sd=50.6 | B642.Å1_VMM72 |
| `B642.Å1_VMM72` | `swap_event` | max adjacent-month jump 36pp; mean=+84.8%, sd=25.0 | B642.ANGA_BUILDING, B642.Å1_VMM71 |
| `B643.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B643.ANGA_BUILDING |
| `B821.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B821.ANGA_BUILDING |
| `B833.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B833.ANGA_BUILDING |
| `B841.Å1_VMM71` | `no_data` | no monthly residuals available | B841.ANGA_BUILDING |
| `B921.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B921.ANGA_BUILDING |

## Flag breakdown

- **`dead_children`** (10): B612.Å1_VMM72, B613.Å1_VMM71, B614.Å1_VMM72, B616.Å1_VMM71, B621.Å1_VMM70, B622.Å1_VMM72, B643.Å1_VMM71, B821.Å1_VMM71, B833.Å1_VMM71, B921.Å1_VMM71
- **`losses_stable`** (1): B611.Å1_VMM73
- **`no_data`** (5): B611.ANGA_BUILDING, B612.ANGA_BUILDING, B614.ANGA_BUILDING, B641.Å1_VMM71, B841.Å1_VMM71
- **`review`** (3): B611.Å1_VMM71, B611.Å1_VMM72, B612.Å1_VMM71
- **`swap_event`** (5): B600N.Å1_VMM71, B600S.Å1_VMM71, B614.Å1_VMM71, B642.Å1_VMM71, B642.Å1_VMM72

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
