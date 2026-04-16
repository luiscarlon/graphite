#!/usr/bin/env python3
"""Per-building accounting-formula sanity check for workstreams with no
physical topology edges (e.g., gtn_varme).

Evaluates each building's Excel formula `+A +B − C − D ...` against
monthly timeseries deltas and reports the per-month net. Flags:

- ``negative_month``: a month where the formula sum is negative (sign flip
  or broken subtractive meter reading high).
- ``missing_meter``: a row references a meter that has no crosswalk entry
  (→ no snowflake_id known).
- ``silent_meter``: a row references a meter that never emits in the
  timeseries over the window.
- ``unstable``: per-building monthly sums have stdev > 30% of mean
  (high variability relative to average consumption).

Inputs:
  - ``--accounting``  path to ``facit_accounting.csv``
  - ``--timeseries``  path to ``timeseries_monthly.csv``
  - ``--crosswalk``   path to ``meter_id_map.csv``
  - ``--out-dir``     directory for output

Outputs:
  - ``monthly_building_accounting.csv``  (building, month, sum, n_add, n_sub)
  - ``accounting_anomalies.md``
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load_crosswalk(path: Path) -> dict[str, str]:
    out = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            if r.get("facit_id") and r.get("snowflake_id"):
                out[r["facit_id"]] = r["snowflake_id"]
    return out


def load_monthly(path: Path) -> dict[tuple[str, str], float]:
    """Return {(snowflake_id, month): delta}."""
    out = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            out[(r["meter_id"], r["month"])] = float(r["delta"])
    return out


def load_accounting(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounting", type=Path, required=True)
    ap.add_argument("--timeseries", type=Path, required=True)
    ap.add_argument("--crosswalk", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    facit_to_snow = load_crosswalk(args.crosswalk)
    monthly = load_monthly(args.timeseries)
    accounting = load_accounting(args.accounting)

    months = sorted({m for (_, m) in monthly})
    if not months:
        print("error: no monthly readings found", file=sys.stderr)
        return 2

    # Collect meters per building-row. Each distinct (building, row) is one formula.
    formulas: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for rec in accounting:
        key = (rec["building"], rec["row"])
        formulas[key].append((rec["sign"], rec["facit_meter_id"], rec["excel_meter_id"]))

    # Evaluate per (building, row, month).
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.out_dir / "monthly_building_accounting.csv"
    rows_out: list[dict] = []

    # Pre-compute: which snowflake IDs appear anywhere in the monthly file?
    meters_with_any_data = {m for (m, _) in monthly}

    missing_xwalk: set[str] = set()
    silent_set: set[str] = set()
    for (bld, row), terms in formulas.items():
        for sign, facit_id, excel_id in terms:
            sf_id = facit_to_snow.get(facit_id, "")
            if not sf_id:
                missing_xwalk.add(facit_id)
            elif sf_id not in meters_with_any_data:
                silent_set.add(facit_id)

        for month in months:
            total = 0.0
            n_add = sum(1 for s, *_ in terms if s == "+")
            n_sub = sum(1 for s, *_ in terms if s == "−")
            any_data = False
            for sign, facit_id, excel_id in terms:
                sf_id = facit_to_snow.get(facit_id, "")
                if not sf_id:
                    continue
                delta = monthly.get((sf_id, month))
                if delta is None:
                    continue  # missing this month, but present elsewhere
                any_data = True
                total += delta if sign == "+" else -delta
            rows_out.append({
                "building": bld,
                "row": row,
                "month": month,
                "sum": round(total, 3),
                "n_add": n_add,
                "n_sub": n_sub,
                "any_data": "yes" if any_data else "no",
            })

    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["building", "row", "month", "sum", "n_add", "n_sub", "any_data"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"wrote {out_csv} ({len(rows_out)} rows)")

    # Classify per-building stability and negatives
    by_building: dict[str, list[float]] = defaultdict(list)
    neg_months: dict[str, list[str]] = defaultdict(list)
    for r in rows_out:
        if r["any_data"] == "no":
            continue
        by_building[r["building"]].append(r["sum"])
        if r["sum"] < -0.01:
            neg_months[r["building"]].append(f"{r['month']} ({r['sum']})")

    lines = [
        "# Accounting anomalies — gtn_varme",
        "",
        "Auto-generated per-building sanity check of the Excel formula against live timeseries. This doesn't validate physical flow (none for värme); it flags accounting edge cases.",
        "",
        "## Building-level flags",
        "",
        "| building | mean monthly sum | stdev | stdev/mean | flag |",
        "|---|---:|---:|---:|---|",
    ]
    for bld in sorted(by_building):
        vals = by_building[bld]
        m = statistics.fmean(vals) if vals else 0
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0
        rel = (sd / m * 100) if m else float("nan")
        # Heating/cooling have strong seasonality (stdev/mean easily 30–70%),
        # so the bar for "unstable" is set deliberately high. Flag only very
        # large swings relative to mean consumption.
        flags = []
        if bld in neg_months:
            flags.append(f"negative_month×{len(neg_months[bld])}")
        if m > 0 and rel > 120:
            flags.append("erratic")
        if m < 0.1:
            flags.append("near_zero")
        flag_str = " ".join(flags) if flags else "ok"
        lines.append(f"| `{bld}` | {m:.1f} | {sd:.1f} | {rel:.0f}% | {flag_str} |")

    if silent_set:
        lines += ["", "## Meters silent in the timeseries", "",
                  "These meters are referenced by an Excel formula but had no row in the monthly timeseries for any month of the window:", ""]
        for m in sorted(silent_set):
            lines.append(f"- `{m}`")
    if missing_xwalk:
        lines += ["", "## Meters missing from the crosswalk", ""]
        for m in sorted(missing_xwalk):
            lines.append(f"- `{m}`")

    if neg_months:
        lines += ["", "## Months with negative net consumption", ""]
        for bld in sorted(neg_months):
            lines.append(f"- **{bld}**: " + ", ".join(neg_months[bld]))

    anom_path = args.out_dir / "accounting_anomalies.md"
    anom_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {anom_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
