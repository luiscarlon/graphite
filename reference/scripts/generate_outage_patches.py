#!/usr/bin/env python3
"""Generate patch timeseries refs for offline meters.

For each meter flagged as ``offline`` in ``meter_swaps.csv``, creates:

1. Renames the existing raw ref to ``{id}.raw`` with ``preferred=false``
2. A patch derived ref (``{id}.patch``) that reconstructs the meter's
   readings from its children's timeseries (``aggregation=sum``)
3. A stitched derived ref (``{id}``) that combines raw + patch via
   ``rolling_sum``, marked ``preferred=true``

For leaf meters (no children), no patch is generated — the outage is
left as a gap.

Modifies ``05_ontology/timeseries_refs.csv`` in place.

Usage:
    python generate_outage_patches.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({fn: r.get(fn, "") for fn in fieldnames})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    ws = args.workstream_dir
    swaps = read_csv_rows(ws / "01_extracted" / "meter_swaps.csv")
    relations = read_csv_rows(ws / "05_ontology" / "meter_relations.csv")
    ts_refs_path = ws / "05_ontology" / "timeseries_refs.csv"
    ts_refs = read_csv_rows(ts_refs_path)

    offline = [s for s in swaps if s["event_type"] == "offline"]
    if not offline:
        print("no offline meters to patch")
        return 0

    children_of: dict[str, list[str]] = {}
    for r in relations:
        children_of.setdefault(r["parent_meter_id"], []).append(r["child_meter_id"])

    # Map snowflake_id → facit_id via existing ts_refs
    xwalk = read_csv_rows(ws / "02_crosswalk" / "meter_id_map.csv")
    sf_to_facit = {r["snowflake_id"]: r["facit_id"] for r in xwalk}

    ts_fields = ["timeseries_id", "sensor_id", "aggregate", "reading_type", "kind",
                 "preferred", "valid_from", "valid_to", "database_id", "path",
                 "external_id", "device_id", "sources", "aggregation"]

    patched = 0
    for event in offline:
        sf_id = event["meter_id"]
        facit_id = sf_to_facit.get(sf_id)
        if not facit_id:
            print(f"  WARN: no facit_id for {sf_id}", file=sys.stderr)
            continue

        children = children_of.get(facit_id, [])
        if not children:
            print(f"  {facit_id}: leaf meter, no children to patch from — skipping")
            continue

        child_ts_ids = [f"{c}:d" for c in children]
        swap_date = event["swap_date"]
        raw_id = f"{facit_id}:d"
        raw_renamed = f"{facit_id}:d.raw"
        patch_id = f"{facit_id}:d.patch"
        stitched_id = f"{facit_id}:d"

        sensor_id = f"{facit_id}.energy"

        # Find the existing preferred ref for this meter
        existing = None
        for tr in ts_refs:
            if tr["timeseries_id"] == raw_id:
                existing = tr
                break

        if not existing:
            print(f"  WARN: no ref {raw_id} found", file=sys.stderr)
            continue

        # Add patch ref (sum of children, valid from outage date)
        ts_refs.append({
            "timeseries_id": patch_id,
            "sensor_id": sensor_id,
            "aggregate": "daily",
            "reading_type": "counter",
            "kind": "derived",
            "preferred": "False",
            "valid_from": swap_date,
            "valid_to": "",
            "database_id": "",
            "path": "",
            "external_id": "",
            "device_id": "",
            "sources": "|".join(child_ts_ids),
            "aggregation": "sum",
        })

        if existing["kind"] == "derived":
            # Already a multi-segment stitched ref (from build_ontology glitch handling).
            # Add the patch to its sources instead of creating a new stitched layer.
            old_sources = existing.get("sources", "")
            existing["sources"] = f"{old_sources}|{patch_id}" if old_sources else patch_id
        else:
            # Simple raw ref — rename to .raw and create stitched
            existing["timeseries_id"] = raw_renamed
            existing["preferred"] = "False"
            ts_refs.append({
                "timeseries_id": stitched_id,
                "sensor_id": sensor_id,
                "aggregate": "daily",
                "reading_type": "counter",
                "kind": "derived",
                "preferred": "True",
                "valid_from": "",
                "valid_to": "",
                "database_id": "",
                "path": "",
                "external_id": "",
                "device_id": "",
                "sources": f"{raw_renamed}|{patch_id}",
                "aggregation": "rolling_sum",
            })

        print(f"  {facit_id}: patched from {len(children)} children ({', '.join(children)})")
        patched += 1

    write_csv(ts_refs_path, ts_fields, ts_refs)
    print(f"wrote {ts_refs_path} ({len(ts_refs)} refs, {patched} patched)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
