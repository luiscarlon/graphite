#!/usr/bin/env python3
"""Discover candidate parent→child edges from timeseries conservation residuals.

For each orphan meter (present in ``facit_meters`` but not in any edge of
``facit_relations``), test whether adding it as a child of an existing parent
**in the same building** reduces that parent's monthly conservation residual.

Runs AFTER layers 1–3 are already merged into ``facit_relations.csv`` so the
residuals reflect the best-known topology — avoiding rediscovery of edges
that naming or Excel already found.

Writes ``01_extracted/timeseries_relations.csv``.

Usage:
    python timeseries_relations.py WORKSTREAM_DIR \\
        [--threshold 0.20] [--min-months 6]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


def building(m: str) -> str:
    x = re.match(r"B(\d+)", m)
    return x.group(1) if x else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--threshold", type=float, default=0.20,
                    help="Minimum fractional residual reduction to accept (default 0.20 = 20%%)")
    ap.add_argument("--min-months", type=int, default=6,
                    help="Require this many overlapping months for a fit")
    ap.add_argument("--months-range", default="2025-01,2025-12",
                    help="Start,end months to use (YYYY-MM format)")
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    start, end = args.months_range.split(",")
    months = []
    y, m = int(start[:4]), int(start[5:7])
    while f"{y:04d}-{m:02d}" <= end:
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1; y += 1

    # Load crosswalk
    cw: dict[str, str] = {}
    cw_path = ws / "02_crosswalk" / "meter_id_map.csv"
    if cw_path.exists():
        for r in csv.DictReader(cw_path.open()):
            cw[r["facit_id"]] = r.get("snowflake_id") or r["facit_id"]

    # Load timeseries
    ts: dict[tuple[str, str], float] = {}
    ts_path = ws / "01_extracted" / "timeseries_monthly.csv"
    if not ts_path.exists():
        print("no timeseries_monthly.csv; skipping", file=sys.stderr)
        return 0
    for r in csv.DictReader(ts_path.open()):
        ts[(r["meter_id"], r["month"])] = float(r["delta"])

    def series(canonical: str) -> dict[str, float]:
        snow = cw.get(canonical)
        if not snow:
            return {}
        return {m: v for (mid, m), v in ts.items() if mid == snow}

    # Load current facit (merged layers 1–3)
    facit_path = ws / "03_reconciliation" / "facit_relations.csv"
    if not facit_path.exists():
        print("no facit_relations.csv; skipping", file=sys.stderr)
        return 0
    parent_children: dict[str, set[str]] = defaultdict(set)
    for r in csv.DictReader(facit_path.open()):
        parent_children[r["from_meter"]].add(r["to_meter"])

    # All meters
    all_meters: set[str] = set()
    fm_path = ws / "03_reconciliation" / "facit_meters.csv"
    if fm_path.exists():
        for r in csv.DictReader(fm_path.open()):
            all_meters.add(r["meter_id"])

    in_rel = set()
    for p, ch in parent_children.items():
        in_rel.add(p)
        in_rel.update(ch)
    orphans = sorted(all_meters - in_rel)

    # Compute per-parent monthly residuals
    parent_residuals: dict[str, dict[str, float]] = {}
    for p, children in parent_children.items():
        ps = series(p)
        if not ps:
            continue
        cs = [(c, series(c)) for c in children]
        resids: dict[str, float] = {}
        for m_key in months:
            pv = ps.get(m_key)
            if pv is None:
                continue
            cv = sum(s.get(m_key, 0) for _, s in cs)
            resids[m_key] = pv - cv
        if len(resids) >= args.min_months:
            parent_residuals[p] = resids

    # Fit orphans (same-building only)
    candidates: list[tuple[float, str, str, float]] = []
    for o in orphans:
        o_building = building(o)
        os = series(o)
        if len(os) < args.min_months:
            continue
        for p, resids in parent_residuals.items():
            if building(p) != o_building:
                continue
            common = [m_key for m_key in months if m_key in resids and m_key in os]
            if len(common) < args.min_months:
                continue
            before = sum(abs(resids[m_key]) for m_key in common)
            after = sum(abs(resids[m_key] - os[m_key]) for m_key in common)
            if before < 5:
                continue
            improvement = (before - after) / before
            if improvement >= args.threshold:
                avg_o = sum(os[m_key] for m_key in common) / len(common)
                candidates.append((improvement, p, o, avg_o))

    # For each orphan keep only the best parent
    best: dict[str, tuple[float, str, float]] = {}
    for imp, p, o, avg_o in candidates:
        if o not in best or imp > best[o][0]:
            best[o] = (imp, p, avg_o)

    out = ws / "01_extracted" / "timeseries_relations.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from_meter", "to_meter", "coefficient", "derived_from"])
        for o in sorted(best):
            imp, p, avg_o = best[o]
            tag = f"timeseries_residual_fit(improvement={imp:.0%})"
            w.writerow([p, o, "1.0", tag])

    print(f"wrote {out} ({len(best)} edges from {len(orphans)} orphans tested "
          f"against {len(parent_residuals)} parents, threshold={args.threshold:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
