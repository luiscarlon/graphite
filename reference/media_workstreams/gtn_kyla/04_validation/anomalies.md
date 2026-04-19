# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B612.KB1_PKYL` | `review` | mean=+95.2%, sd=3.0 | B637.KB2_INT_VERK, B638.KB1_INT_VERK1 |
| `B614.KB1_INT_VERK` | `review` | mean=+95.9%, sd=1.6 | B615.KB1_INT_VERK1, B642.KB1_INT_VERK_1 |
| `B821.KB2_VMM1` | `no_data` | no monthly residuals available | B841.KB2_VMM51 |
| `B833.KB1_GF4` | `dead_children` | residual = 100% every month (mean=99%, sd=1.3) | B834.KB2_INT_VERK |

## Flag breakdown

- **`dead_children`** (1): B833.KB1_GF4
- **`no_data`** (1): B821.KB2_VMM1
- **`review`** (2): B612.KB1_PKYL, B614.KB1_INT_VERK

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
