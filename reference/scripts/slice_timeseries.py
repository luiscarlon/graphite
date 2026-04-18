#!/usr/bin/env python3
"""Slice a daily-aggregated Snowflake meter-readings CSV into a per-workstream view.

The Snowflake export (``Untitled 1_2026-04-16-1842.csv`` and similar) carries
every meter and every quantity across the full site. This script restricts it
to a given (quantity, meter-id-list) slice and computes per-meter, per-month
deltas using ``last − first`` sorted by timestamp, segmenting at any decrement
(counter reset / meter swap) so a single anomaly doesn't silently corrupt the
whole year's total.

Inputs:
  - ``readings_csv``   — the Snowflake export (METER_ID, QUANTITY, DAY, V_FIRST, V_LAST, ...)
  - ``--meters-csv``   — a CSV with at least one column naming the snowflake meter IDs
                         to keep.  Column can be ``snowflake_id`` (preferred) or ``meter_id``.
  - ``--quantity``     — exact quantity string to filter on, e.g. ``Active Energy Delivered(Mega)``

Outputs (written to ``--out-dir``):
  - ``timeseries_daily.csv``    — filtered daily rows, one per (meter, day)
  - ``timeseries_monthly.csv``  — per (meter, month): delta, n_days, zero_days,
                                   reset_days, first_day, last_day
  - ``timeseries_anomalies.csv`` — per-meter flags: non-monotonic days, long zero runs,
                                    coverage gaps, total year-flat meters

Delta semantics:
  - Monthly delta = ``last_day_of_month.V_LAST − first_day_of_month.V_FIRST`` so
    the register-difference captures the full month including the final hours
    of the last day (which would be lost if we summed per-day ``v_last − v_first``
    — we observed a systematic ~4.2% shortfall from the per-day-sum method in
    värme/ånga spot-checks, closed by switching to this register-difference).
  - If the register decreases between consecutive days (counter reset / swap),
    the month is split into monotonic segments; monthly delta = Σ per-segment
    ``(last.V_LAST − first.V_FIRST)``.
  - Per-day ``v_last − v_first`` is still kept in ``timeseries_daily.csv`` as
    a sanity signal and for intra-day anomaly detection.
  - A meter with every day's delta == 0 for the full window is flagged
    ``flat_all_window``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def load_meters(path: Path) -> list[str]:
    with path.open() as f:
        reader = csv.DictReader(f)
        col = "snowflake_id" if "snowflake_id" in reader.fieldnames else "meter_id"
        if col not in reader.fieldnames:
            raise SystemExit(
                f"error: {path} must have a 'snowflake_id' or 'meter_id' column; "
                f"found {reader.fieldnames}"
            )
        return [row[col].strip() for row in reader if row[col].strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("readings_csv", type=Path)
    ap.add_argument("--meters-csv", type=Path, required=True, help="CSV listing target meters (column: snowflake_id or meter_id)")
    ap.add_argument("--quantity", required=True, help="Exact quantity string, e.g. 'Active Energy Delivered(Mega)'")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    target_meters = set(load_meters(args.meters_csv))
    if not target_meters:
        print("error: --meters-csv had no meter IDs", file=sys.stderr)
        return 2

    daily: dict[str, list[tuple[str, float, float, int]]] = defaultdict(list)
    with args.readings_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["METER_ID"] not in target_meters:
                continue
            if row["QUANTITY"] != args.quantity:
                continue
            day = row["DAY"][:10]
            try:
                vf = float(row["V_FIRST"])
                vl = float(row["V_LAST"])
            except (TypeError, ValueError):
                # Empty/NaN readings are common in EL exports where a given
                # meter has partial days; skip these rows cleanly.
                continue
            try:
                n = int(row["N_READINGS"]) if row["N_READINGS"] else 0
            except (TypeError, ValueError):
                n = 0
            daily[row["METER_ID"]].append((day, vf, vl, n))

    if not daily:
        print(f"warning: no rows matched quantity={args.quantity!r} for any of {len(target_meters)} meters", file=sys.stderr)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # daily CSV
    daily_path = args.out_dir / "timeseries_daily.csv"
    with daily_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "day", "v_first", "v_last", "delta", "n_readings", "is_reset"])
        for m in sorted(daily):
            for day, vf, vl, n in sorted(daily[m]):
                delta = vl - vf
                is_reset = delta < 0
                w.writerow([m, day, vf, vl, delta, n, int(is_reset)])

    # monthly aggregation — register-difference, segmented at resets
    monthly: dict[tuple[str, str], dict] = {}
    for m, rows in daily.items():
        # Bucket rows per month, sorted by day
        per_month: dict[str, list] = defaultdict(list)
        for day, vf, vl, n in sorted(rows):
            per_month[day[:7]].append((day, vf, vl, n))

        for month, mrows in per_month.items():
            # Segment at any inter-day reset (curr.V_FIRST < prev.V_LAST with
            # tolerance) or intra-day reset (V_LAST < V_FIRST).
            segments: list[list] = [[mrows[0]]]
            for prev, curr in zip(mrows, mrows[1:]):
                _, _, prev_vl, _ = prev
                _, curr_vf, curr_vl, _ = curr
                intra = curr_vl < curr_vf - 1e-6
                inter = curr_vf < prev_vl - 1e-6
                if intra or inter:
                    segments.append([curr])
                else:
                    segments[-1].append(curr)

            # Sum per-segment register diff = last_V_LAST − first_V_FIRST.
            delta = 0.0
            for seg in segments:
                first_vf = seg[0][1]
                last_vl = seg[-1][2]
                if last_vl >= first_vf:
                    delta += last_vl - first_vf
                # else: segment itself is non-monotonic, skip (intra-day reset)

            reset_days = sum(1 for _, vf, vl, _ in mrows if vl < vf - 1e-6)
            # Count inter-day resets too
            for prev, curr in zip(mrows, mrows[1:]):
                if curr[1] < prev[2] - 1e-6:
                    reset_days += 1
            zero_days = sum(1 for _, vf, vl, _ in mrows if abs(vl - vf) < 1e-9)
            monthly[(m, month)] = {
                "delta": delta,
                "n_days": len(mrows),
                "zero_days": zero_days,
                "reset_days": reset_days,
                "first_day": mrows[0][0],
                "last_day": mrows[-1][0],
            }

    monthly_path = args.out_dir / "timeseries_monthly.csv"
    with monthly_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "month", "delta", "n_days", "zero_days", "reset_days", "first_day", "last_day"])
        for (m, mo), rec in sorted(monthly.items()):
            w.writerow([m, mo, f"{rec['delta']:.6f}", rec["n_days"], rec["zero_days"], rec["reset_days"], rec["first_day"], rec["last_day"]])

    # anomalies
    anomalies_path = args.out_dir / "timeseries_anomalies.csv"
    with anomalies_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "flag", "detail"])

        unmapped = sorted(target_meters - set(daily))
        for m in unmapped:
            w.writerow([m, "no_readings", f"quantity={args.quantity!r}"])

        for m in sorted(daily):
            rows = sorted(daily[m])
            total_days = len(rows)
            total_delta = sum(max(vl - vf, 0) for _, vf, vl, _ in rows)
            zero_days = sum(1 for _, vf, vl, _ in rows if vl - vf == 0)
            reset_days = sum(1 for _, vf, vl, _ in rows if vl - vf < 0)

            if total_days > 0 and total_delta == 0:
                w.writerow([m, "flat_all_window", f"{total_days} days, all zero delta"])
            if reset_days:
                reset_detail = "; ".join(f"{d} Δ={vl-vf:.3f}" for d, vf, vl, _ in rows if vl - vf < 0)
                w.writerow([m, "reset_days", f"{reset_days} day(s): {reset_detail}"])
            if zero_days / max(total_days, 1) > 0.5 and total_delta > 0:
                w.writerow([m, "mostly_zero", f"{zero_days}/{total_days} days Δ=0 (meter may be intermittent)"])

            # coverage gaps: compute expected day count
            if rows:
                first = rows[0][0]
                last = rows[-1][0]
                from datetime import date
                d0 = date.fromisoformat(first)
                d1 = date.fromisoformat(last)
                expected = (d1 - d0).days + 1
                if total_days < expected:
                    w.writerow([m, "coverage_gap", f"{total_days}/{expected} days present ({first}..{last})"])

    # summary
    print(f"wrote {daily_path} ({sum(len(v) for v in daily.values())} rows, {len(daily)} meters)")
    print(f"wrote {monthly_path} ({len(monthly)} meter-month rows)")
    print(f"wrote {anomalies_path}")

    matched_count = len(daily)
    print(f"\nmatched {matched_count}/{len(target_meters)} target meters")
    if len(daily) < len(target_meters):
        missing = target_meters - set(daily)
        print(f"  missing: {sorted(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
