# Conservation anomalies

Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.

| parent | flag | note | children |
|---|---|---|---|
| `B600-KB2` | `no_data` | no monthly residuals available | B631.KB1_INTE_VERK2, B631.KB1_VMM51 |
| `B600.KB2` | `no_data` | no monthly residuals available | B611.KYLA_BUILDING, B613.KYLA_BUILDING, B621T.KYLA_BUILDING, B622.KYLA_BUILDING |
| `B611.KB2_VMM50` | `no_data` | no monthly residuals available | B611.KB2_VMM51 |
| `B611.KB2_VMM51` | `swap_event` | max adjacent-month jump 94pp; mean=-12.2%, sd=37.0 | B611.KB2_VMM52 |
| `B611.KYLA_BUILDING` | `no_data` | no monthly residuals available | B631.KB1_INTE_VERK2, B631.KB1_VMM51 |
| `B612-KB1-PKYL` | `no_data` | no monthly residuals available | B637.KB2_INT_VERK, B638.KB1_INT_VERK1 |
| `B612.KB1_PKYL` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B612.KYLA_BUILDING, B641.KYLA_BUILDING |
| `B612.KB1_VMM50` | `swap_event` | max adjacent-month jump 33629pp; mean=-3508.2%, sd=10009.0 | B612.KB1_VMM51 |
| `B612.KYLA_BUILDING` | `no_data` | no monthly residuals available | B637.KB2_INT_VERK, B638.KB1_INT_VERK1 |
| `B614.KB1_INT_VERK` | `review` | mean=+95.9%, sd=1.6 | B614.KYLA_BUILDING, B615.KB1_INT_VERK1, B642.KB1_INT_VERK_1 |
| `B614.KB1_VMM50` | `swap_event` | max adjacent-month jump 2556746pp; mean=-1004647.6%, sd=1072242.3 | B614.KB1_VMM51 |
| `B614.KYLA_BUILDING` | `no_data` | no monthly residuals available | B615.KB1_INT_VERK1, B642.KB1_INT_VERK_1 |
| `B615.KB1_INT_VERK1` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B615.KYLA_BUILDING |
| `B616.KB1_PKYL` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B616.KYLA_BUILDING |
| `B621.KB2_VMM50` | `swap_event` | max adjacent-month jump 5610pp; mean=-2207.7%, sd=2406.2 | B621.KB2_VMM51 |
| `B622.KB2_VMM50` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B622.KB2_VMM51 |
| `B623.KB1_INT_VERK1` | `swap_event` | max adjacent-month jump 132597pp; mean=-14651.9%, sd=34442.2 | B623.KYLA_BUILDING, B658.KB2_VMM51, B661.KB1_INTVERK, B821.KB2_VMM1, BB600-KB2.KYLA_BUILDING |
| `B631.KB1_INTE_VERK2` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B631.KYLA_BUILDING |
| `B631.KB1_VMM50` | `swap_event` | max adjacent-month jump 34333pp; mean=-177721.0%, sd=17166.5 | B631.KB1_VMM51 |
| `B634.KB1_PKYL` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B634.KYLA_BUILDING |
| `B634.KB1_VMM50` | `swap_event` | max adjacent-month jump 45168pp; mean=-8942.7%, sd=18074.1 | B634.KB1_VMM51 |
| `B637.KB2_INT_VERK` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B637.KYLA_BUILDING |
| `B638.KB1_INT_VERK1` | `no_data` | no monthly residuals available | B638.KYLA_BUILDING |
| `B641.KYLA_BUILDING` | `no_data` | no monthly residuals available | B637.KB2_INT_VERK, B638.KB1_INT_VERK1 |
| `B642.KB1_INT_VERK_1` | `no_data` | no monthly residuals available | B642.KYLA_BUILDING |
| `B643.KB1_INT_VERK` | `no_data` | no monthly residuals available | B643.KYLA_BUILDING |
| `B653.KB2_WVÄRME_ACK` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | BB600-KB2.KYLA_BUILDING, BProd-600.KYLA_BUILDING |
| `B654.KB1_KylEffekt_Ack` | `swap_event` | max adjacent-month jump 383pp; mean=+23.8%, sd=97.1 | B612.KYLA_BUILDING, B613.KYLA_BUILDING, B637.KB2_INT_VERK, B638.KB1_INT_VERK1, BProd-600.KYLA_BUILDING |
| `B654.KB2_Pkyl_Ack` | `no_data` | no monthly residuals available | BB600-KB2.KYLA_BUILDING, BProd-600.KYLA_BUILDING |
| `B658.KB2_VMM51` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B658.KYLA_BUILDING |
| `B661.KB1_INTVERK` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B661.KYLA_BUILDING |
| `B661.KB1_Pkyl_Ack` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | BProd-600.KYLA_BUILDING |
| `B674.KB1_PKYL2_Ack` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B674.KYLA_BUILDING |
| `B821-55-KB2-VMM1` | `no_data` | no monthly residuals available | B841.KB2_VMM51 |
| `B821.55_KB2_VMM1` | `no_data` | no monthly residuals available | B821.KYLA_BUILDING |
| `B821.KB2_VMM50` | `no_data` | no monthly residuals available | B821.KB2_VMM51 |
| `B821.KYLA_BUILDING` | `no_data` | no monthly residuals available | B841.KB2_VMM51 |
| `B833-55-KB1-GF4` | `no_data` | no monthly residuals available | B834.KB2_INT_VERK |
| `B833.55_KB1_GF4` | `no_data` | no monthly residuals available | B833.KYLA_BUILDING |
| `B833.KYLA_BUILDING` | `no_data` | no monthly residuals available | B834.KB2_INT_VERK |
| `B834.KB2_INT_VERK` | `dead_children` | residual = 100% every month (mean=100%, sd=0.0) | B834.KYLA_BUILDING |
| `B841.KB2_VMM50` | `no_data` | no monthly residuals available | B841.KB2_VMM51 |
| `B841.KB2_VMM51` | `no_data` | no monthly residuals available | B841.KYLA_BUILDING |
| `BB600-KB2.KYLA_BUILDING` | `no_data` | no monthly residuals available | B658.KB2_VMM51, B661.KB1_INTVERK, B821.KB2_VMM1 |

## Flag breakdown

- **`dead_children`** (13): B612.KB1_PKYL, B615.KB1_INT_VERK1, B616.KB1_PKYL, B622.KB2_VMM50, B631.KB1_INTE_VERK2, B634.KB1_PKYL, B637.KB2_INT_VERK, B653.KB2_WVÄRME_ACK, B658.KB2_VMM51, B661.KB1_INTVERK, B661.KB1_Pkyl_Ack, B674.KB1_PKYL2_Ack, B834.KB2_INT_VERK
- **`no_data`** (22): B600-KB2, B600.KB2, B611.KB2_VMM50, B611.KYLA_BUILDING, B612-KB1-PKYL, B612.KYLA_BUILDING, B614.KYLA_BUILDING, B638.KB1_INT_VERK1, B641.KYLA_BUILDING, B642.KB1_INT_VERK_1, B643.KB1_INT_VERK, B654.KB2_Pkyl_Ack, B821-55-KB2-VMM1, B821.55_KB2_VMM1, B821.KB2_VMM50, B821.KYLA_BUILDING, B833-55-KB1-GF4, B833.55_KB1_GF4, B833.KYLA_BUILDING, B841.KB2_VMM50, B841.KB2_VMM51, BB600-KB2.KYLA_BUILDING
- **`review`** (1): B614.KB1_INT_VERK
- **`swap_event`** (8): B611.KB2_VMM51, B612.KB1_VMM50, B614.KB1_VMM50, B621.KB2_VMM50, B623.KB1_INT_VERK1, B631.KB1_VMM50, B634.KB1_VMM50, B654.KB1_KylEffekt_Ack

## Flag meanings

- `clean` — parent and Σ children agree within ±5pp every month. No issue.
- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.
- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.
- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.
- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.
- `review` — didn't fit any category neatly. Inspect manually.
- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.
