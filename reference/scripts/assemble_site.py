#!/usr/bin/env python3
"""Assemble workstream 05_ontology outputs into a single site Dataset.

Merges per-media ontology CSVs into one directory loadable by
``ontology.load_dataset()``. Shared tables (campuses, databases) are
generated; per-media tables (meters, relations, sensors, timeseries_refs)
are concatenated. Optionally extracts readings from a Snowflake dump.

Usage:
    python assemble_site.py \
        --campus GTN --campus-name Gärtuna \
        --database ion_sweden_bms \
        --workstreams reference/media_workstreams/gtn_anga \
        --snowflake-readings "reference/snowflake_meter_readings/Untitled 1_2026-04-16-1842.csv" \
        --output data/sites/gartuna
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({fn: r.get(fn, "") for fn in fieldnames})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campus", required=True)
    ap.add_argument("--campus-name", required=True)
    ap.add_argument("--database", required=True)
    ap.add_argument("--workstreams", nargs="+", type=Path, required=True)
    ap.add_argument("--snowflake-readings", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    all_meters: list[dict] = []
    all_relations: list[dict] = []
    all_sensors: list[dict] = []
    all_ts_refs: list[dict] = []
    all_media_types: list[dict] = []
    buildings_by_id: dict[str, dict] = {}

    for ws_dir in args.workstreams:
        onto = ws_dir / "05_ontology"
        if not onto.exists():
            print(f"WARN: {onto} does not exist, skipping", file=sys.stderr)
            continue

        all_meters.extend(read_csv_rows(onto / "meters.csv"))
        all_relations.extend(read_csv_rows(onto / "meter_relations.csv"))
        all_sensors.extend(read_csv_rows(onto / "sensors.csv"))
        all_ts_refs.extend(read_csv_rows(onto / "timeseries_refs.csv"))

        for mt in read_csv_rows(onto / "media_types.csv"):
            all_media_types.append(mt)

        for b in read_csv_rows(onto / "buildings.csv"):
            buildings_by_id[b["building_id"]] = b

    # --- per-media tables (concatenated) ---
    write_csv(
        out / "meters.csv",
        ["meter_id", "name", "building_id", "media_type_id",
         "is_virtual_meter", "identifier", "valid_from", "valid_to"],
        all_meters,
    )
    write_csv(
        out / "meter_relations.csv",
        ["parent_meter_id", "child_meter_id", "relation_type",
         "flow_coefficient", "valid_from", "valid_to", "derived_from"],
        all_relations,
    )
    write_csv(
        out / "sensors.csv",
        ["sensor_id", "meter_id", "point_type", "unit", "identifier"],
        all_sensors,
    )
    write_csv(
        out / "timeseries_refs.csv",
        ["timeseries_id", "sensor_id", "aggregate", "reading_type", "kind",
         "preferred", "valid_from", "valid_to", "database_id", "path",
         "external_id", "device_id", "sources", "aggregation"],
        all_ts_refs,
    )

    # --- shared tables (union + dedup or generated) ---
    seen_media = set()
    deduped_media: list[dict] = []
    for mt in all_media_types:
        if mt["media_type_id"] not in seen_media:
            seen_media.add(mt["media_type_id"])
            deduped_media.append(mt)
    write_csv(
        out / "media_types.csv",
        ["media_type_id", "name", "description", "brick_meter_class", "brick_substance"],
        deduped_media,
    )

    write_csv(
        out / "buildings.csv",
        ["building_id", "name", "campus_id", "identifier"],
        sorted(buildings_by_id.values(), key=lambda b: b["building_id"]),
    )

    write_csv(out / "campuses.csv",
              ["campus_id", "name", "identifier"],
              [{"campus_id": args.campus, "name": args.campus_name, "identifier": ""}])

    write_csv(out / "databases.csv",
              ["database_id", "name", "kind", "identifier"],
              [{"database_id": args.database, "name": "ION Sweden BMS",
                "kind": "external", "identifier": ""}])

    write_csv(out / "zones.csv",
              ["zone_id", "name", "building_id", "zone_type", "identifier"], [])

    write_csv(out / "devices.csv",
              ["device_id", "serial", "manufacturer", "identifier"], [])

    # --- annotations: concatenate from workstreams + manual ---
    all_annotations: list[dict] = []
    for ws_dir in args.workstreams:
        ann_path = ws_dir / "05_ontology" / "annotations.csv"
        if ann_path.exists():
            media_slug = ws_dir.name.split("_", 1)[1].upper()
            for row in read_csv_rows(ann_path):
                row.setdefault("media", media_slug)
                all_annotations.append(row)
    manual_ann = out / "annotations_manual.csv"
    if manual_ann.exists():
        all_annotations.extend(read_csv_rows(manual_ann))
    write_csv(
        out / "annotations.csv",
        ["annotation_id", "target_kind", "target_id", "category",
         "valid_from", "valid_to", "description", "related_refs", "media"],
        all_annotations,
    )

    # Merge Excel cached building totals from all workstreams
    all_excel_totals: list[dict] = []
    for ws_dir in args.workstreams:
        totals_path = ws_dir / "01_extracted" / "excel_building_totals.csv"
        if not totals_path.exists():
            continue
        media_slug = ws_dir.name.split("_", 1)[1].upper()
        for row in read_csv_rows(totals_path):
            all_excel_totals.append({
                "building_id": row["building_id"],
                "month": row["month"],
                "excel_mwh": row["excel_kwh"],
                "media": media_slug,
            })
    if all_excel_totals:
        write_csv(out / "excel_building_totals.csv",
                  ["building_id", "month", "excel_mwh", "media"],
                  all_excel_totals)

    # Copy meter_allocations (Excel accounting formulas) for comparison views
    all_allocations: list[dict] = []
    for ws_dir in args.workstreams:
        alloc_path = ws_dir / "05_ontology" / "meter_allocations.csv"
        if alloc_path.exists():
            all_allocations.extend(read_csv_rows(alloc_path))
    if all_allocations:
        write_csv(out / "meter_allocations.csv",
                  list(all_allocations[0].keys()), all_allocations)

    # --- meter_measures: auto-generate from meters ---
    # Include all meters (real and virtual). Physical meters that feed 100%
    # into a virtual building meter will have net=0, contributing nothing
    # to the building total. The virtual building meter's net captures the
    # actual building consumption.
    meter_measures: list[dict] = []
    for m in all_meters:
        bid = m.get("building_id", "")
        if bid:
            meter_measures.append({
                "meter_id": m["meter_id"],
                "target_kind": "building",
                "target_id": bid,
                "valid_from": "",
                "valid_to": "",
            })
        else:
            meter_measures.append({
                "meter_id": m["meter_id"],
                "target_kind": "campus",
                "target_id": args.campus,
                "valid_from": "",
                "valid_to": "",
            })
    write_csv(
        out / "meter_measures.csv",
        ["meter_id", "target_kind", "target_id", "valid_from", "valid_to"],
        meter_measures,
    )

    # --- readings: extract from Snowflake dump ---
    if args.snowflake_readings and args.snowflake_readings.exists():
        # Build map: external_id → list of timeseries refs (may be >1 for swaps)
        refs_by_ext: dict[str, list[dict]] = {}
        derived_refs: list[dict] = []
        for tr in all_ts_refs:
            eid = tr.get("external_id", "")
            if eid:
                refs_by_ext.setdefault(eid, []).append(tr)
            if tr.get("kind") == "derived":
                derived_refs.append(tr)

        readings: list[dict] = []
        with args.snowflake_readings.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                meter_id = row["METER_ID"]
                ref_list = refs_by_ext.get(meter_id)
                if not ref_list:
                    continue
                v_last = row.get("V_LAST", "")
                if not v_last:
                    continue
                day = row["DAY"]
                for tr in ref_list:
                    vf = tr.get("valid_from", "")
                    vt = tr.get("valid_to", "")
                    if vf and day < vf:
                        continue
                    if vt and day >= vt:
                        continue
                    readings.append({
                        "timeseries_id": tr["timeseries_id"],
                        "timestamp": day,
                        "value": v_last,
                        "recorded_at": "",
                    })

        # Materialize derived refs. Process `sum` first (patches depend on
        # raw children), then `rolling_sum` (stitches raw + patch segments).
        readings_by_ts: dict[str, list[dict]] = {}
        for r in readings:
            readings_by_ts.setdefault(r["timeseries_id"], []).append(r)

        for dr in sorted(derived_refs, key=lambda d: d.get("aggregation", "") != "sum"):
            source_ids = [s for s in (dr.get("sources", "") or "").split("|") if s]
            if not source_ids:
                continue
            agg = dr.get("aggregation", "")

            if agg == "sum":
                # Patch: build synthetic counter = cumulative sum of children's deltas.
                # Only from valid_from onwards (before that, the raw ref covers).
                vf = dr.get("valid_from", "")
                by_day: dict[str, float] = {}
                for sid in source_ids:
                    src_rows = sorted(readings_by_ts.get(sid, []), key=lambda r: r["timestamp"])
                    prev_val = None
                    for sr in src_rows:
                        val = float(sr["value"])
                        if prev_val is not None and (not vf or sr["timestamp"] >= vf):
                            delta = max(val - prev_val, 0.0)
                            by_day[sr["timestamp"]] = by_day.get(sr["timestamp"], 0.0) + delta
                        prev_val = val
                new_readings = []
                counter = 0.0
                for day in sorted(by_day):
                    counter += by_day[day]
                    new_readings.append({
                        "timeseries_id": dr["timeseries_id"],
                        "timestamp": day,
                        "value": str(counter),
                        "recorded_at": "",
                    })
                readings.extend(new_readings)
                readings_by_ts[dr["timeseries_id"]] = new_readings

            elif agg == "rolling_sum":
                # Stitch: concatenate source segments. When switching to a
                # new segment, carry forward the last stitched value and
                # subtract the new segment's first raw reading (its anchor)
                # so only deltas from the new device are added.
                source_readings = []
                for sid in source_ids:
                    source_readings.extend(
                        sorted(readings_by_ts.get(sid, []), key=lambda r: r["timestamp"])
                    )
                source_readings.sort(key=lambda r: r["timestamp"])
                if not source_readings:
                    continue
                offset = 0.0
                anchor = 0.0
                prev_source = source_readings[0]["timeseries_id"]
                prev_stitched = 0.0
                new_readings = []
                for sr in source_readings:
                    raw_val = float(sr["value"])
                    if sr["timeseries_id"] != prev_source:
                        offset = prev_stitched
                        anchor = raw_val
                        prev_source = sr["timeseries_id"]
                    stitched = offset + (raw_val - anchor)
                    prev_stitched = stitched
                    new_readings.append({
                        "timeseries_id": dr["timeseries_id"],
                        "timestamp": sr["timestamp"],
                        "value": str(stitched),
                        "recorded_at": "",
                    })
                readings.extend(new_readings)
                readings_by_ts[dr["timeseries_id"]] = new_readings

        write_csv(
            out / "readings.csv",
            ["timeseries_id", "timestamp", "value", "recorded_at"],
            readings,
        )
        n_meters = len({r["timeseries_id"] for r in readings})
        print(f"wrote {out / 'readings.csv'} ({len(readings)} rows, {n_meters} meters)")
    else:
        write_csv(out / "readings.csv",
                  ["timeseries_id", "timestamp", "value", "recorded_at"], [])

    print(f"assembled {len(all_meters)} meters, {len(all_relations)} relations, "
          f"{len(all_sensors)} sensors, {len(all_ts_refs)} ts_refs "
          f"from {len(args.workstreams)} workstream(s) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
