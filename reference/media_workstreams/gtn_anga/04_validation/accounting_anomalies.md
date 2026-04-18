# Accounting anomalies — gtn_varme

Auto-generated per-building sanity check of the Excel formula against live timeseries. This doesn't validate physical flow (none for värme); it flags accounting edge cases.

## Building-level flags

| building | mean monthly sum | stdev | stdev/mean | flag |
|---|---:|---:|---:|---|
| `600` | 4760.5 | 1132.8 | 24% | ok |
| `611` | 936.8 | 196.8 | 21% | ok |
| `612` | 609.4 | 148.3 | 24% | ok |
| `613` | 0.1 | 0.2 | 200% | erratic |
| `614` | -2120.2 | 7425.4 | -350% | negative_month×5 near_zero |
| `616` | 253.3 | 307.9 | 122% | erratic |
| `621 (T)` | 754.1 | 175.0 | 23% | ok |
| `622` | 17.7 | 14.2 | 80% | ok |
| `641` | 0.0 | 0.0 | nan% | near_zero |
| `642` | 2671.3 | 7439.6 | 279% | erratic |
| `643` | 49.8 | 50.8 | 102% | ok |
| `821` | 27.0 | 9.9 | 37% | ok |
| `833` | 121.4 | 71.4 | 59% | ok |
| `841` | 0.0 | 0.0 | nan% | near_zero |
| `921` | 378.4 | 116.2 | 31% | ok |

## Months with negative net consumption

- **614**: 2025-01 (-1457.356), 2025-03 (-28701.585), 2025-04 (-876.72), 2025-05 (-1578.876), 2025-06 (-1747.787)
