# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B200.Å1_VMM70` | `no_data` | no monthly residuals available | B216.Å1_VMM71, B302.Å1_VMM73, B304.Å1_VMM70, B307.Å1_VMM71, B308.Å1_VMM70, B308.Å1_VMM71, B311.Å1_VMM71, B327.Å1_VMM70, B330.Å1_VMM71, B334.Å1_VMM71, B337.Å1_VMM71, B339.Å1_VMM70 |
| `B216.Å1_VMM71` | `swap_event` | max adjacent-month jump 2018464pp; mean=-338108.9%, sd=707169.6 | B216.Å1_VMM72, B217.Å1_VMM71 |
| `B302.Å1_VMM71` | `review` | mean=+97.0%, sd=1.1 | B301.Å1_VMM71, B302.Å1_VMM72 |
| `B302.Å1_VMM72` | `no_data` | no monthly residuals available | B303.Å1_VMM70, B310.Å1_VMM70, B330.Å1_VMM73, B392.Å1_VMM71 |
| `B304.Å1_VMM70` | `no_data` | no monthly residuals available | B304.Å1_VMM71 |
| `B307.Å1_VMM71` | `swap_event` | max adjacent-month jump 106324pp; mean=-51040.2%, sd=60301.7 | B302.Å1_VMM71, B305.Å1_VMM71, B307.Å1_VMM72, B341.Å1_VMM71, B385.Å1_VMM71 |
| `B308.Å1_VMM71` | `swap_event` | max adjacent-month jump 443pp; mean=-332.5%, sd=483.8 | B390.Å1_VMM70 |
| `B310.Å1_VMM70` | `swap_event` | max adjacent-month jump 978134pp; mean=-217313.6%, sd=286454.8 | B310.Å1_VMM71, B310.Å1_VMM72, B311.Å1_VMM72 |
| `B310.Å1_VMM72` | `swap_event` | max adjacent-month jump 292pp; mean=+15.0%, sd=73.0 | B310.Å1_VMM73, B310.Å1_VMM74, B313.Å1_VMM71, B313.Å1_VMM72, B317.Å1_VMM71, B317.Å1_VMM72 |
| `B311.Å1_VMM71` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B311.Å1_VMM70 |
| `B313.Å1_VMM71` | `review` | mean=-2709.3%, sd=0.0 | B315.Å1_VMM71 |
| `B327.Å1_VMM70` | `no_data` | no monthly residuals available | B327.Å1_VMM71 |
| `B337.Å1_VMM71` | `review` | mean=+86.4%, sd=7.3 | B330.Å1_VMM72, B337.Å1_VMM72 |

## Flag breakdown

- **`dead_children`** (1): B311.Å1_VMM71
- **`no_data`** (4): B200.Å1_VMM70, B302.Å1_VMM72, B304.Å1_VMM70, B327.Å1_VMM70
- **`review`** (3): B302.Å1_VMM71, B313.Å1_VMM71, B337.Å1_VMM71
- **`swap_event`** (5): B216.Å1_VMM71, B307.Å1_VMM71, B308.Å1_VMM71, B310.Å1_VMM70, B310.Å1_VMM72

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
