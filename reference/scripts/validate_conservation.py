#!/usr/bin/env python3
"""Conservation check: parent monthly delta vs sum of children monthly deltas.

Takes the facit relations and the per-workstream monthly timeseries and emits
a per-parent-per-month residual table plus a human-readable anomalies
markdown. Classifies each parent's behaviour into one of:

  - ``losses_stable``    — non-trivial residual that is steady across months
                           (within ±5pp of its own mean). Real losses.
  - ``dead_children``    — residual ≈ 100% every month because every child
                           reads near-zero. Children are broken/frozen or the
                           topology points at non-emitting meters.
  - ``swap_event``       — residual shifts >20pp between adjacent months,
                           signalling a meter replacement / commissioning.
  - ``drift_seasonal``   — residual correlates with season (summer/winter) but
                           not with any obvious swap. Likely missing children.
  - ``clean``            — residual stays within ±5pp of zero. Perfect match.

Inputs (paths resolved relative to CWD):
  - ``facit_relations_csv`` — ``from_meter, to_meter`` (+ optional coefficient)
  - ``timeseries_monthly_csv`` — ``meter_id, month, delta, ...`` in Snowflake IDs
  - ``meter_id_map_csv``  — to translate facit ids to snowflake ids

Outputs (``--out-dir``):
  - ``monthly_conservation.csv``
  - ``anomalies.md`` (draft classification)
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load_crosswalk(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            if r.get("snowflake_id"):
                out[r["facit_id"]] = r["snowflake_id"]
    return out


def load_relations(path: Path) -> list[tuple[str, str]]:
    with path.open() as f:
        return [(r["from_meter"], r["to_meter"]) for r in csv.DictReader(f)]


def load_monthly(path: Path) -> dict[tuple[str, str], float]:
    """Return {(meter_id, month): delta}."""
    out: dict[tuple[str, str], float] = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            out[(r["meter_id"], r["month"])] = float(r["delta"])
    return out


def classify(residuals_pct: list[float]) -> tuple[str, str]:
    """Given a sequence of monthly residual percentages, emit (flag, note)."""
    if not residuals_pct:
        return "no_data", "no monthly residuals available"
    vals = [v for v in residuals_pct if v == v]  # drop NaN
    if not vals:
        return "no_data", "all residuals NaN (parent had zero flow)"

    mean = statistics.fmean(vals)
    stdev = statistics.pstdev(vals) if len(vals) > 1 else 0.0

    # dead children: residual ~100% every month
    if all(abs(v - 100) < 5 for v in vals):
        return "dead_children", f"residual = 100% every month (mean={mean:.0f}%, sd={stdev:.1f})"

    # clean: near zero and stable
    if abs(mean) < 5 and stdev < 5:
        return "clean", f"mean={mean:+.1f}%, sd={stdev:.1f} — within tolerance"

    # stable losses
    if stdev < 5 and 5 <= mean <= 50:
        return "losses_stable", f"mean={mean:+.1f}%, sd={stdev:.1f} — steady steam/energy losses"

    # swap event: look for an adjacent-month jump > 20pp
    max_jump = max((abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)), default=0)
    if max_jump > 20:
        return "swap_event", f"max adjacent-month jump {max_jump:.0f}pp; mean={mean:+.1f}%, sd={stdev:.1f}"

    # drift: moderate spread without a single jump
    if stdev > 10:
        return "drift_seasonal", f"mean={mean:+.1f}%, sd={stdev:.1f} — variable residual, check seasonal consumer"

    return "review", f"mean={mean:+.1f}%, sd={stdev:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--facit-relations", type=Path, required=True)
    ap.add_argument("--timeseries-monthly", type=Path, required=True)
    ap.add_argument("--crosswalk", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    facit_to_snow = load_crosswalk(args.crosswalk)
    relations = load_relations(args.facit_relations)
    monthly = load_monthly(args.timeseries_monthly)

    children_of: dict[str, list[str]] = defaultdict(list)
    for p, c in relations:
        children_of[p].append(c)

    months = sorted({m for (_, m) in monthly})
    if not months:
        print("error: no monthly rows found", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.out_dir / "monthly_conservation.csv"

    per_parent_residuals: dict[str, list[float]] = defaultdict(list)
    per_parent_rows: list[dict] = []

    for parent in sorted(children_of):
        p_sf = facit_to_snow.get(parent)
        for month in months:
            dp = monthly.get((p_sf, month), 0.0) if p_sf else 0.0
            kids = children_of[parent]
            dk_total = 0.0
            dead_kids = 0
            for c in kids:
                c_sf = facit_to_snow.get(c)
                dk = monthly.get((c_sf, month), 0.0) if c_sf else 0.0
                dk_total += dk
                if dk == 0:
                    dead_kids += 1
            residual = dp - dk_total
            pct = (100 * residual / dp) if dp > 0.01 else float("nan")
            if pct == pct:
                per_parent_residuals[parent].append(pct)
            per_parent_rows.append({
                "parent": parent,
                "month": month,
                "delta_parent": round(dp, 3),
                "sum_children": round(dk_total, 3),
                "residual": round(residual, 3),
                "residual_pct": round(pct, 1) if pct == pct else "",
                "n_children": len(kids),
                "dead_children_this_month": dead_kids,
            })

    with out_csv.open("w", newline="") as f:
        cols = ["parent", "month", "delta_parent", "sum_children", "residual", "residual_pct", "n_children", "dead_children_this_month"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(per_parent_rows)
    print(f"wrote {out_csv} ({len(per_parent_rows)} rows)")

    # anomalies.md
    anomalies_path = args.out_dir / "anomalies.md"
    lines = [
        "# Conservation anomalies",
        "",
        "Auto-generated classification from `monthly_conservation.csv`. **Review and annotate** — treat the flag column as a starting point, not gospel.",
        "",
        "| parent | flag | note | children |",
        "|---|---|---|---|",
    ]
    by_flag: dict[str, list[str]] = defaultdict(list)
    for parent in sorted(children_of):
        flag, note = classify(per_parent_residuals[parent])
        by_flag[flag].append(parent)
        kids = ", ".join(children_of[parent])
        lines.append(f"| `{parent}` | `{flag}` | {note} | {kids} |")

    lines += ["", "## Flag breakdown", ""]
    for flag in sorted(by_flag):
        lines.append(f"- **`{flag}`** ({len(by_flag[flag])}): {', '.join(by_flag[flag])}")

    lines += [
        "",
        "## Flag meanings",
        "",
        "- `clean` — parent and Σ children agree within ±5pp every month. No issue.",
        "- `losses_stable` — steady positive residual (5–50%, low stdev). Consistent with genuine heat/steam losses through pipes, traps, radiation. Action: document the loss rate; no topology concern.",
        "- `dead_children` — residual ≈ 100% every month because every child reads near-zero. Either the children's meters are broken/frozen, or the flow-schema topology points at non-emitting devices. Action: check with operations; flag the specific meters in `01_extracted/timeseries_anomalies.csv`.",
        "- `swap_event` — adjacent-month residual jump > 20pp. A meter was replaced or recommissioned mid-year. Action: identify the swap date from the daily reset anomaly and confirm with the BMS.",
        "- `drift_seasonal` — residual varies >10pp stdev with no single jump. Candidate cause: seasonal consumer downstream of parent that isn't metered as a child. Action: look for summer/winter pattern and cross-check with Excel's subtractive terms.",
        "- `review` — didn't fit any category neatly. Inspect manually.",
        "- `no_data` — parent had zero flow, so percentage is undefined. Report the absolute residual instead.",
    ]
    anomalies_path.write_text("\n".join(lines) + "\n")
    print(f"wrote {anomalies_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
