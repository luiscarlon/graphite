#!/usr/bin/env python3
"""Materialize building-level virtual meters from Excel accounting formulas.

Each building row in the Excel is an implicit virtual meter:
``B611_VARME = 0.38 × VP1 + VÅ9 + VP2 − B613.VP1 − B631.VP1 × 2 − B622.VP2``

This script creates:
1. A virtual meter entry per building (appended to ``facit_meters.csv``)
2. Relations: each ``+`` meter feeds the virtual (with coefficient);
   virtual feeds each ``−`` meter (with coefficient).
   Tag: ``derived_from = building_virtual_B{N}``

Reads ``03_reconciliation/facit_accounting.csv``.
Appends to ``03_reconciliation/facit_meters.csv`` and ``facit_relations.csv``.

Usage:
    python generate_building_virtuals.py WORKSTREAM_DIR --media VARME
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


def normalise(m: str) -> str:
    x = re.sub(r"_E$", "", m)
    x = re.sub(r"\.(\w+?)_V(M)(\d+)$", r".\1_VMM\3", x)
    return x


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--media", required=True, help="Media slug: ANGA, VARME, KYLA, EL")
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    acc_path = ws / "03_reconciliation" / "facit_accounting.csv"
    meters_path = ws / "03_reconciliation" / "facit_meters.csv"
    rels_path = ws / "03_reconciliation" / "facit_relations.csv"

    if not acc_path.exists():
        print(f"no facit_accounting.csv at {acc_path}; nothing to do", file=sys.stderr)
        return 0

    # Parse accounting formulas
    by_building: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(
        lambda: {"add": [], "sub": []}
    )
    for r in csv.DictReader(acc_path.open()):
        mid = r.get("facit_meter_id") or normalise(r.get("excel_meter_id", r.get("meter_id", "")))
        faktor = 1.0
        for col in ("faktor", "coefficient"):
            fs = r.get(col, "")
            if fs:
                try:
                    faktor = float(fs)
                except (TypeError, ValueError):
                    pass
                break
        role = r.get("role", "add")
        by_building[r["building"]][role].append((mid, faktor))

    # Load existing meters + relations to avoid duplicates
    existing_meters: set[str] = set()
    if meters_path.exists():
        for r in csv.DictReader(meters_path.open()):
            existing_meters.add(r["meter_id"])

    existing_rels: set[tuple[str, str]] = set()
    existing_rel_rows: list[dict] = []
    if rels_path.exists():
        for r in csv.DictReader(rels_path.open()):
            existing_rels.add((r["from_meter"], r["to_meter"]))
            existing_rel_rows.append(r)

    # Generate virtual meters + relations
    new_meters: list[dict] = []
    new_rels: list[dict] = []

    for b, sides in sorted(by_building.items()):
        # Virtual meter ID: B{building}.{MEDIA}_BUILDING
        b_clean = b.replace(" ", "").replace("(", "").replace(")", "")
        vid = f"B{b_clean}.{args.media}_BUILDING"

        if vid not in existing_meters:
            building_num = re.match(r"(\d+)", b_clean)
            new_meters.append({
                "meter_id": vid,
                "building": building_num.group(1) if building_num else b_clean,
                "meter_type": "virtual",
            })

        # + meters → virtual (inputs)
        for mid, coeff in sides["add"]:
            edge = (normalise(mid), vid)
            if edge not in existing_rels:
                existing_rels.add(edge)
                new_rels.append({
                    "from_meter": edge[0],
                    "to_meter": edge[1],
                    "coefficient": str(coeff) if abs(coeff - 1.0) > 1e-9 else "1.0",
                    "derived_from": f"building_virtual_B{b_clean}",
                })

        # virtual → − meters (pass-through)
        for mid, coeff in sides["sub"]:
            edge = (vid, normalise(mid))
            if edge not in existing_rels:
                existing_rels.add(edge)
                new_rels.append({
                    "from_meter": edge[0],
                    "to_meter": edge[1],
                    "coefficient": str(coeff) if abs(coeff - 1.0) > 1e-9 else "1.0",
                    "derived_from": f"building_virtual_B{b_clean}",
                })

    # Append to facit_meters.csv
    if new_meters:
        with meters_path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["meter_id", "building", "meter_type"])
            for m in new_meters:
                w.writerow(m)

    # Rewrite facit_relations.csv with new + existing
    all_rels = existing_rel_rows + new_rels
    cols = ["from_meter", "to_meter", "coefficient", "derived_from"]
    with rels_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(all_rels, key=lambda r: (r["from_meter"], r["to_meter"])):
            w.writerow({c: r.get(c, "") for c in cols})

    print(f"wrote {len(new_meters)} virtual meters, {len(new_rels)} new relations "
          f"({len(all_rels)} total in facit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
