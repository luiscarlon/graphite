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

    # Merge curated Excel-comparison annotations (reason + explanation per building-month)
    all_excel_annotations: list[dict] = []
    for ws_dir in args.workstreams:
        ann_path = ws_dir / "05_ontology" / "excel_comparison_annotations.csv"
        if ann_path.exists():
            all_excel_annotations.extend(read_csv_rows(ann_path))
    if all_excel_annotations:
        write_csv(
            out / "excel_comparison_annotations.csv",
            ["media", "building_id", "month", "excel_kwh", "onto_kwh",
             "diff_kwh", "reason", "explanation"],
            all_excel_annotations,
        )

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

        # Materialize derived refs.
        #   sum         — children-sum patch (source = other real meter refs)
        #   bracket     — monotone value-range clip (parameter-free)
        #   interpolate — linear counter fill between source-derived endpoints
        #   rolling_sum — stitch raw + patch segments, preserving the offset
        #
        # Order matters: sum/bracket/interpolate produce readings that
        # rolling_sum may consume; all three run before rolling_sum.
        readings_by_ts: dict[str, list[dict]] = {}
        for r in readings:
            readings_by_ts.setdefault(r["timeseries_id"], []).append(r)

        _AGG_ORDER = {"sum": 0, "bracket": 1, "interpolate": 2, "rolling_sum": 3}
        for dr in sorted(derived_refs, key=lambda d: _AGG_ORDER.get(d.get("aggregation", ""), 99)):
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

            elif agg == "bracket":
                # Monotone value-range clip. Within [valid_from, valid_to)
                # keep source samples whose value lies between the source
                # values just outside the window. Parameter-free — the
                # bracket endpoints come from the source's last reading
                # strictly before valid_from and its first reading at or
                # after valid_to. Requires exactly one source ref.
                if len(source_ids) != 1:
                    print(f"  WARN: bracket ref {dr['timeseries_id']} expects "
                          f"1 source, got {len(source_ids)} — skipping",
                          file=sys.stderr)
                    continue
                vf = dr.get("valid_from", "")
                vt = dr.get("valid_to", "")
                if not vf or not vt:
                    print(f"  WARN: bracket ref {dr['timeseries_id']} needs "
                          f"both valid_from and valid_to — skipping",
                          file=sys.stderr)
                    continue
                src = sorted(
                    readings_by_ts.get(source_ids[0], []),
                    key=lambda r: r["timestamp"],
                )
                before = [r for r in src if r["timestamp"] < vf]
                atafter = [r for r in src if r["timestamp"] >= vt]
                if not before or not atafter:
                    print(f"  WARN: bracket ref {dr['timeseries_id']} cannot "
                          f"anchor endpoints (no source reading before "
                          f"{vf!r} or at/after {vt!r}) — skipping",
                          file=sys.stderr)
                    continue
                v_lo = float(before[-1]["value"])
                v_hi = float(atafter[0]["value"])
                lo, hi = (v_lo, v_hi) if v_lo <= v_hi else (v_hi, v_lo)
                new_readings = []
                for sr in src:
                    if not (vf <= sr["timestamp"] < vt):
                        continue
                    val = float(sr["value"])
                    if lo <= val <= hi:
                        new_readings.append({
                            "timeseries_id": dr["timeseries_id"],
                            "timestamp": sr["timestamp"],
                            "value": sr["value"],
                            "recorded_at": "",
                        })
                readings.extend(new_readings)
                readings_by_ts[dr["timeseries_id"]] = new_readings

            elif agg == "interpolate":
                # Linear counter fill. Between the source's last reading
                # strictly before valid_from and its first reading at or
                # after valid_to, emit one reading per day (or whatever
                # the aggregate cadence is) on the source's grid that
                # linearly interpolates the counter across time.
                if len(source_ids) != 1:
                    print(f"  WARN: interpolate ref {dr['timeseries_id']} "
                          f"expects 1 source, got {len(source_ids)} — skipping",
                          file=sys.stderr)
                    continue
                vf = dr.get("valid_from", "")
                vt = dr.get("valid_to", "")
                if not vf or not vt:
                    print(f"  WARN: interpolate ref {dr['timeseries_id']} "
                          f"needs both valid_from and valid_to — skipping",
                          file=sys.stderr)
                    continue
                src = sorted(
                    readings_by_ts.get(source_ids[0], []),
                    key=lambda r: r["timestamp"],
                )
                before = [r for r in src if r["timestamp"] < vf]
                atafter = [r for r in src if r["timestamp"] >= vt]
                if not before or not atafter:
                    print(f"  WARN: interpolate ref {dr['timeseries_id']} "
                          f"cannot anchor endpoints — skipping",
                          file=sys.stderr)
                    continue
                t_lo_s = before[-1]["timestamp"]
                v_lo = float(before[-1]["value"])
                t_hi_s = atafter[0]["timestamp"]
                v_hi = float(atafter[0]["value"])
                # Days assume ISO yyyy-mm-dd strings for timestamps; fall
                # back to exact-string compare if parsing fails.
                try:
                    from datetime import date as _date
                    t_lo = _date.fromisoformat(t_lo_s[:10])
                    t_hi = _date.fromisoformat(t_hi_s[:10])
                    vf_d = _date.fromisoformat(vf[:10])
                    vt_d = _date.fromisoformat(vt[:10])
                    span_days = (t_hi - t_lo).days
                    if span_days <= 0:
                        print(f"  WARN: interpolate ref {dr['timeseries_id']} "
                              f"degenerate span — skipping", file=sys.stderr)
                        continue
                    new_readings = []
                    cur = vf_d
                    from datetime import timedelta as _td
                    while cur < vt_d:
                        frac = (cur - t_lo).days / span_days
                        val = v_lo + (v_hi - v_lo) * frac
                        new_readings.append({
                            "timeseries_id": dr["timeseries_id"],
                            "timestamp": cur.isoformat(),
                            "value": f"{val:.3f}",
                            "recorded_at": "",
                        })
                        cur = cur + _td(days=1)
                    readings.extend(new_readings)
                    readings_by_ts[dr["timeseries_id"]] = new_readings
                except ValueError:
                    print(f"  WARN: interpolate ref {dr['timeseries_id']} "
                          f"non-ISO timestamps — skipping", file=sys.stderr)
                    continue

            elif agg == "rolling_sum":
                # Stitch: concatenate source segments at their validity
                # boundaries. Two boundary types to distinguish:
                #
                #   (a) Device swap — new device starts counting from
                #       some arbitrary offset. We want the stitched
                #       counter to stay flat across the boundary; only
                #       deltas from the new device add. Achieved by
                #       anchoring on the new source's first raw reading
                #       (stitched = prev + (raw - anchor) = prev on
                #       boundary; subsequent readings add delta).
                #
                #   (b) Register rollover (Schneider PowerLogic / ION
                #       default ceiling 10,000,000) — same device, its
                #       accumulator wrapped. The new source's first raw
                #       IS consumption since the wrap, so we must add
                #       both the pre-wrap remainder (ceiling - prev_raw)
                #       and the new raw value itself to the cumulative.
                #       Without this, the reset-day's consumption is
                #       silently lost (the stitched counter stays flat
                #       across the rollover day, producing a visible
                #       zero-delta dip in rate views).
                #
                # Heuristic to distinguish: prev_raw is within 1% below
                # a known Schneider ceiling AND new raw is much smaller.
                # Mirrors detect_meter_swaps.py classification.
                ROLLOVER_CEILINGS = (1_000_000.0, 10_000_000.0, 100_000_000.0)
                ROLLOVER_TOLERANCE = 0.01

                def _rollover_ceiling(prev_val: float, new_val: float) -> float | None:
                    if new_val >= prev_val * 0.5:
                        return None
                    for C in ROLLOVER_CEILINGS:
                        if (1.0 - ROLLOVER_TOLERANCE) * C <= prev_val <= C:
                            return C
                    return None

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
                prev_raw = 0.0
                new_readings = []
                for sr in source_readings:
                    raw_val = float(sr["value"])
                    if sr["timeseries_id"] != prev_source:
                        ceiling = _rollover_ceiling(prev_raw, raw_val)
                        if ceiling is not None:
                            # Rollover: add the pre-wrap remainder to
                            # offset and anchor at 0 so the new raw is
                            # counted as additional consumption.
                            offset = prev_stitched + (ceiling - prev_raw)
                            anchor = 0.0
                        else:
                            # Plain swap: new device's first raw is the
                            # anchor; stitched flat across boundary.
                            offset = prev_stitched
                            anchor = raw_val
                        prev_source = sr["timeseries_id"]
                    stitched = offset + (raw_val - anchor)
                    prev_stitched = stitched
                    prev_raw = raw_val
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
