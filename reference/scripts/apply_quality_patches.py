#!/usr/bin/env python3
"""Apply hand-authored data-quality patches to a workstream.

Reads ``quality_patches.yaml`` from the workstream root and appends
annotations + derived timeseries_refs to the corresponding CSVs under
``05_ontology/``.

The YAML is the single source of truth for manual patches: deleting an
entry from the file and re-running the pipeline rolls that patch back.
Runs AFTER ``build_ontology.py`` and ``generate_outage_patches.py`` so
that the auto-generated refs are already in place when we merge.

The script is idempotent: running it twice does not duplicate rows. It
overwrites existing annotations / refs by id when the YAML defines a
row with the same key, so edits are applied on the next run.

Usage:
    python apply_quality_patches.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "error: PyYAML not installed. "
        "Run `uv pip install pyyaml` or add it to the environment.",
        file=sys.stderr,
    )
    sys.exit(2)


ANNOTATION_FIELDS = [
    "annotation_id",
    "target_kind",
    "target_id",
    "category",
    "valid_from",
    "valid_to",
    "description",
    "related_refs",
]

REF_FIELDS = [
    "timeseries_id",
    "sensor_id",
    "aggregate",
    "reading_type",
    "kind",
    "preferred",
    "valid_from",
    "valid_to",
    "database_id",
    "path",
    "external_id",
    "device_id",
    "sources",
    "aggregation",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({fn: r.get(fn, "") for fn in fieldnames})


def _stringify(value: Any) -> str:
    """Normalize a YAML value to the CSV string form the rest of the
    pipeline expects. Lists become pipe-joined; None / missing → empty."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, list):
        return "|".join(str(x) for x in value)
    return str(value)


def _to_row(entry: dict[str, Any], fields: list[str]) -> dict[str, str]:
    return {fn: _stringify(entry.get(fn)) for fn in fields}


def merge_rows(
    existing: list[dict[str, str]],
    new: list[dict[str, str]],
    key: str,
) -> tuple[list[dict[str, str]], int, int]:
    """Overwrite rows whose ``key`` matches an entry in ``new``; append
    the rest. Returns (merged_rows, n_overwritten, n_appended)."""
    by_key = {row[key]: i for i, row in enumerate(existing) if row.get(key)}
    merged = list(existing)
    overwritten = 0
    appended = 0
    for row in new:
        k = row[key]
        if k in by_key:
            merged[by_key[k]] = row
            overwritten += 1
        else:
            merged.append(row)
            appended += 1
    return merged, overwritten, appended


def apply(ws: Path) -> int:
    patches_path = ws / "quality_patches.yaml"
    if not patches_path.exists():
        print(f"no {patches_path.name} in {ws.name} — nothing to do")
        return 0

    with patches_path.open() as f:
        data = yaml.safe_load(f) or {}

    annotations_yaml = data.get("annotations") or []
    refs_yaml = data.get("refs") or []
    delete_cfg = data.get("delete") or {}
    delete_refs = set(delete_cfg.get("refs") or [])
    delete_annotations = set(delete_cfg.get("annotations") or [])

    if not annotations_yaml and not refs_yaml and not delete_refs and not delete_annotations:
        print(f"{patches_path.name}: empty — nothing to apply")
        return 0

    # Validate references up front so we fail before mutating files.
    ref_fieldnames = set(REF_FIELDS)
    for entry in refs_yaml:
        unknown = set(entry) - ref_fieldnames
        if unknown:
            print(
                f"error: ref {entry.get('timeseries_id', '?')} has unknown "
                f"fields {sorted(unknown)}",
                file=sys.stderr,
            )
            return 2
    ann_fieldnames = set(ANNOTATION_FIELDS)
    for entry in annotations_yaml:
        unknown = set(entry) - ann_fieldnames
        if unknown:
            print(
                f"error: annotation {entry.get('annotation_id', '?')} has "
                f"unknown fields {sorted(unknown)}",
                file=sys.stderr,
            )
            return 2

    onto = ws / "05_ontology"

    if annotations_yaml or delete_annotations:
        ann_path = onto / "annotations.csv"
        existing = read_rows(ann_path)
        if delete_annotations:
            before = len(existing)
            existing = [r for r in existing if r.get("annotation_id") not in delete_annotations]
            removed = before - len(existing)
        else:
            removed = 0
        new_rows = [_to_row(e, ANNOTATION_FIELDS) for e in annotations_yaml]
        merged, over, app = merge_rows(existing, new_rows, key="annotation_id")
        write_rows(ann_path, ANNOTATION_FIELDS, merged)
        print(
            f"  annotations.csv: +{app} new, {over} overwritten, "
            f"{removed} removed (total {len(merged)})"
        )

    if refs_yaml or delete_refs:
        ref_path = onto / "timeseries_refs.csv"
        existing = read_rows(ref_path)
        if delete_refs:
            before = len(existing)
            existing = [r for r in existing if r.get("timeseries_id") not in delete_refs]
            removed = before - len(existing)
        else:
            removed = 0
        new_rows = [_to_row(e, REF_FIELDS) for e in refs_yaml]
        merged, over, app = merge_rows(existing, new_rows, key="timeseries_id")
        write_rows(ref_path, REF_FIELDS, merged)
        print(
            f"  timeseries_refs.csv: +{app} new, {over} overwritten, "
            f"{removed} removed (total {len(merged)})"
        )

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()
    return apply(args.workstream_dir.resolve())


if __name__ == "__main__":
    sys.exit(main())
