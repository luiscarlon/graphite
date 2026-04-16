# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B600N.Å1_VMM71` | `swap_event` | max adjacent-month jump 36pp; mean=+61.0%, sd=16.3 | B616.Å1_VMM71, B643.Å1_VMM71, B833.Å1_VMM71, B921.Å1_VMM71 |
| `B600S.Å1_VMM71` | `losses_stable` | mean=+15.1%, sd=4.9 — steady steam/energy losses | B611.Å1_VMM71, B611.Å1_VMM73, B612.Å1_VMM71, B612.Å1_VMM72, B614.Å1_VMM71, B614.Å1_VMM72, B621.Å1_VMM70, B821.Å1_VMM71, B841.Å1_VMM71 |
| `B611.Å1_VMM73` | `losses_stable` | mean=+36.8%, sd=3.6 — steady steam/energy losses | B611.Å1_VMM72, B622.Å1_VMM72 |
| `B612.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B613.Å1_VMM71, B641.Å1_VMM71 |
| `B614.Å1_VMM71` | `swap_event` | max adjacent-month jump 7833pp; mean=-684.6%, sd=2055.1 | B642.Å1_VMM72 |
| `B642.Å1_VMM72` | `swap_event` | max adjacent-month jump 34pp; mean=+90.0%, sd=18.5 | B642.Å1_VMM71 |

## Flag breakdown

- **`dead_children`** (1): B612.Å1_VMM71
- **`losses_stable`** (2): B600S.Å1_VMM71, B611.Å1_VMM73
- **`swap_event`** (3): B600N.Å1_VMM71, B614.Å1_VMM71, B642.Å1_VMM72

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
