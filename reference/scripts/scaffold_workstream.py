#!/usr/bin/env python3
"""Create the directory structure for a new media workstream.

Generates the pipeline folder layout and a draft crosswalk from the
union of meter IDs found across all extraction sources.

Usage:
    python scaffold_workstream.py reference/media_workstreams/gtn_kyla
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


DIRS = [
    "00_inputs",
    "01_extracted",
    "02_crosswalk",
    "03_reconciliation",
    "04_validation",
    "05_ontology",
]


def read_csv_column(path: Path, column: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {r[column] for r in csv.DictReader(f) if r.get(column)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    ws = args.workstream_dir
    for d in DIRS:
        (ws / d).mkdir(parents=True, exist_ok=True)

    extracted = ws / "01_extracted"
    crosswalk = ws / "02_crosswalk" / "meter_id_map.csv"

    if crosswalk.exists():
        print(f"crosswalk already exists at {crosswalk}; not overwriting")
        return 0

    meter_ids: set[str] = set()
    meter_ids |= read_csv_column(extracted / "flow_schema_meters.csv", "meter_id")
    meter_ids |= read_csv_column(extracted / "excel_meters_used.csv", "meter_id")
    meter_ids |= read_csv_column(extracted / "excel_intake_meters.csv", "matarbeteckning")

    if not meter_ids:
        print("no meter IDs found in 01_extracted; run extractors first")
        crosswalk.parent.mkdir(parents=True, exist_ok=True)
        with crosswalk.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["facit_id", "snowflake_id", "strux_id", "excel_label",
                         "in_flow_schema", "in_excel", "confidence", "evidence"])
        print(f"wrote empty {crosswalk}")
        return 0

    rows = []
    for mid in sorted(meter_ids):
        rows.append({
            "facit_id": mid,
            "snowflake_id": mid,
            "strux_id": "",
            "excel_label": "",
            "in_flow_schema": "no",
            "in_excel": "no",
            "confidence": "draft",
            "evidence": f"scaffold: {mid}",
        })

    crosswalk.parent.mkdir(parents=True, exist_ok=True)
    with crosswalk.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {crosswalk} ({len(rows)} draft entries)")
    print("review and complete the crosswalk before running phases 3+")
    return 0


if __name__ == "__main__":
    sys.exit(main())
