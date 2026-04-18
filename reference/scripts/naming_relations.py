#!/usr/bin/env python3
"""Derive intra-building parent→child edges from meter naming conventions.

Two rule families:

1. **Role hierarchy** — within the same building, the primary supply inlet
   feeds secondary and recovery loops:
   - VP1 → VS1, VS2 (primary heating feeds secondary radiator circuits)
   - VP1 → VÅ9 (primary feeds heat-pump recovery)
   - KB1 → KB2 (kyla batt 1 feeds kyla batt 2) — tentative

2. **Index chain** — meters with the same building + role prefix and
   consecutive VMM indices are likely in series on the same pipe:
   - B612.VP2_VMM61 → B612.VP2_VMM62 (lower index feeds higher)

Reads ``01_extracted/meter_roles.csv`` (from ``parse_meter_names.py``) and
``01_extracted/flow_schema_meters.csv`` (if present) for the full meter list.
Writes ``01_extracted/naming_relations.csv``.

Does not look at existing edges — dedup happens in ``apply_topology_overrides.py``.

Usage:
    python naming_relations.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


ROLE_FEEDS: dict[str, list[str]] = {
    "VP1": ["VS1", "VS2", "VÅ9"],
    "VP2": ["VÅ9"],
    "VS1": ["VÅ9"],
}


def load_meters(ws: Path) -> list[dict]:
    """Load from meter_roles.csv + flow_schema_meters.csv + facit_meters.csv
    to get the broadest possible meter list."""
    meters: dict[str, dict] = {}

    roles_path = ws / "01_extracted" / "meter_roles.csv"
    if roles_path.exists():
        for r in csv.DictReader(roles_path.open()):
            meters[r["canonical_id"]] = {
                "meter_id": r["canonical_id"],
                "building": r["building"],
                "role": r["role"],
                "vmm_index": int(r["vmm_index"]),
            }

    for src in ("01_extracted/flow_schema_meters.csv", "03_reconciliation/facit_meters.csv"):
        p = ws / src
        if not p.exists():
            continue
        for r in csv.DictReader(p.open()):
            mid = r["meter_id"]
            if mid in meters:
                continue
            m = re.match(r"B(\d+[A-Z]?)\.([A-ZÅÄÖ]+\d*)_VMM(\d+)$", mid)
            if m:
                meters[mid] = {
                    "meter_id": mid,
                    "building": m.group(1),
                    "role": m.group(2),
                    "vmm_index": int(m.group(3)),
                }
    return list(meters.values())


def derive_role_edges(meters: list[dict]) -> list[tuple[str, str, str]]:
    """Return [(from, to, provenance), ...] from role hierarchy."""
    by_building: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for m in meters:
        by_building[m["building"]][m["role"]].append(m)

    edges: list[tuple[str, str, str]] = []
    for _b, roles in by_building.items():
        for parent_role, child_roles in ROLE_FEEDS.items():
            parents = roles.get(parent_role, [])
            if not parents:
                continue
            parent = min(parents, key=lambda m: m["vmm_index"])
            for cr in child_roles:
                for child in roles.get(cr, []):
                    edges.append((parent["meter_id"], child["meter_id"], "naming_role_hierarchy"))
    return edges


def derive_index_edges(meters: list[dict]) -> list[tuple[str, str, str]]:
    """Return [(from, to, provenance), ...] from consecutive VMM indices."""
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for m in meters:
        by_key[(m["building"], m["role"])].append(m)

    edges: list[tuple[str, str, str]] = []
    for (_b, _r), group in by_key.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda m: m["vmm_index"])
        for a, b in zip(group, group[1:]):
            if b["vmm_index"] - a["vmm_index"] <= 2:
                edges.append((a["meter_id"], b["meter_id"], "naming_index_chain"))
    return edges


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    meters = load_meters(ws)
    if not meters:
        print("no canonical meters found; skipping naming relations", file=sys.stderr)
        return 0

    role_edges = derive_role_edges(meters)
    index_edges = derive_index_edges(meters)
    all_edges = role_edges + index_edges

    # Dedup
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for f, t, prov in all_edges:
        if (f, t) not in seen:
            seen.add((f, t))
            unique.append((f, t, prov))

    out = ws / "01_extracted" / "naming_relations.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from_meter", "to_meter", "coefficient", "derived_from"])
        for f, t, prov in sorted(unique):
            w.writerow([f, t, "1.0", prov])

    print(f"wrote {out} ({len(unique)} edges: "
          f"{sum(1 for _,_,p in unique if p=='naming_role_hierarchy')} role-hierarchy, "
          f"{sum(1 for _,_,p in unique if p=='naming_index_chain')} index-chain)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
