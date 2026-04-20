#!/usr/bin/env python3
"""Build the Abbey Road-shaped ontology CSVs for a workstream.

Reads from ``03_reconciliation/`` + ``02_crosswalk/`` + ``01_extracted/``
and writes ``05_ontology/`` with these tables (compatible with the schema
used in ``data/reference_site/abbey_road/``):

- ``meters.csv``           — one row per meter in the facit
- ``meter_relations.csv``  — ``parent → child`` edges (populated from
                              ``facit_relations.csv``; may be empty for
                              workstreams without physical topology)
- ``meter_allocations.csv`` — per-building accounting formulas (extension
                               beyond Abbey Road). Populated when a
                               ``facit_accounting.csv`` is present.
- ``sensors.csv``          — one sensor per meter (energy/flow sensor on
                              the physical meter)
- ``timeseries_refs.csv``  — sensor → Snowflake meter ID mapping, so a
                              downstream system can join readings

Usage:
    python build_ontology.py reference/media_workstreams/gtn_anga \\
        --campus GTN --media ANGA --database ion_sweden_bms

Each run targets one workstream directory. Shared reference tables
(``campuses.csv``, ``buildings.csv``, ``media_types.csv``, ``databases.csv``)
are **not** generated here — they're site-level and live in a shared
location; use ``--emit-shared`` to dump a per-workstream copy of the
building list for later merging.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def read_csv_rows(path: Path) -> list[dict]:
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
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--campus", required=True, help="Campus ID, e.g. GTN")
    ap.add_argument("--media", required=True, help="Media type ID, e.g. ANGA or VARME")
    ap.add_argument("--database", required=True, help="Database ID, e.g. ion_sweden_bms")
    ap.add_argument("--unit", default="Megawatt-Hour", help="Brick/QUDT unit for sensors")
    ap.add_argument("--emit-shared", action="store_true", help="Also emit buildings.csv and media_types.csv stubs for later merging")
    args = ap.parse_args()

    ws = args.workstream_dir
    out = ws / "05_ontology"
    recon = ws / "03_reconciliation"
    crosswalk = ws / "02_crosswalk"
    extracted = ws / "01_extracted"

    # Safety: warn if overwriting existing ontology files that may have manual edits
    manual_edit_files = ["timeseries_refs.csv", "meter_relations.csv"]
    for fname in manual_edit_files:
        fpath = out / fname
        if fpath.exists():
            print(f"  WARNING: overwriting {fpath} — re-apply manual edits (device swaps, relation fixes) after this run!",
                  file=sys.stderr)

    # 1) Facit meters
    meters_src = read_csv_rows(recon / "facit_meters.csv")

    # 2) Crosswalk — facit_id → snowflake_id, strux_id, etc.
    xwalk = {r["facit_id"]: r for r in read_csv_rows(crosswalk / "meter_id_map.csv")}

    # 3) Timeseries monthly for optional valid_from/valid_to hints
    ts_rows = read_csv_rows(extracted / "timeseries_monthly.csv") if (extracted / "timeseries_monthly.csv").exists() else []
    ts_by_meter: dict[str, list[dict]] = defaultdict(list)
    for r in ts_rows:
        ts_by_meter[r["meter_id"]].append(r)

    # ---------------- meters.csv ----------------
    # Skip virtual building meters (ANGA_BUILDING etc.) — they were
    # invented to encode Excel accounting formulas but are redundant
    # with the physical hasSubMeter topology + meter_measures. The
    # accounting formulas are preserved in meter_allocations.csv.
    meters_out: list[dict] = []
    for rec in meters_src:
        fid = rec["meter_id"]
        is_virtual = rec.get("meter_type") == "virtual"
        # Keep non-_BUILDING virtuals (e.g. building pool virtuals like
        # B611.KYLA_VIRT). Skip only the legacy _BUILDING virtuals that
        # encode full Excel formulas — those are redundant with
        # meter_measures + physical topology.
        if is_virtual and fid.endswith("_BUILDING"):
            continue
        if is_virtual:
            # Virtual meter — no Snowflake crosswalk, no sensor/timeseries.
            meters_out.append({
                "meter_id": fid,
                "name": f"{rec['building']} {args.media} virtual {fid}",
                "building_id": f"B{rec['building']}" if rec["building"] else "",
                "media_type_id": args.media,
                "is_virtual_meter": "True",
                "identifier": "",
                "valid_from": "",
                "valid_to": "",
            })
            continue
        xw = xwalk.get(fid, {})
        sf_id = xw.get("snowflake_id", "")
        valid_from = ""
        valid_to = ""
        ts = ts_by_meter.get(sf_id, [])
        if ts:
            months = sorted({t["month"] for t in ts})
            if months and months[0] > "2025-02":
                valid_from = ts[0]["first_day"]
            all_zero = all(float(t["delta"]) == 0 for t in ts)
            if all_zero:
                valid_to = ts[0]["first_day"]
        identifier_parts = [
            f"snowflake={sf_id}" if sf_id else "",
            f"strux={xw.get('strux_id')}" if xw.get("strux_id") else "",
            f"excel={xw.get('excel_label')}" if xw.get("excel_label") else "",
        ]
        identifier = "; ".join(p for p in identifier_parts if p)
        meters_out.append(
            {
                "meter_id": fid,
                "name": f"{rec['building']} {args.media} meter {fid.split('.', 1)[1]}" if "." in fid else fid,
                "building_id": f"B{rec['building']}" if rec["building"] else "",
                "media_type_id": args.media,
                "is_virtual_meter": str(is_virtual),
                "identifier": identifier,
                "valid_from": valid_from,
                "valid_to": valid_to,
            }
        )

    write_csv(
        out / "meters.csv",
        ["meter_id", "name", "building_id", "media_type_id", "is_virtual_meter", "identifier", "valid_from", "valid_to"],
        meters_out,
    )

    # ---------------- meter_relations.csv ----------------
    relations_src = read_csv_rows(recon / "facit_relations.csv")
    relations_out: list[dict] = []
    for r in relations_src:
        derived_from = r.get("derived_from", "")
        if derived_from.startswith("building_virtual"):
            continue
        coeff = float(r.get("coefficient", "1.0") or "1.0")
        # Use explicit relation_type if present in facit; otherwise infer from coefficient
        explicit_type = r.get("relation_type", "")
        if explicit_type in ("feeds", "hasSubMeter"):
            relation_type = explicit_type
            flow_coefficient = str(coeff) if relation_type == "feeds" else ""
        elif coeff not in (1.0, 0.001):
            relation_type = "feeds"
            flow_coefficient = str(coeff)
        else:
            relation_type = "hasSubMeter"
            flow_coefficient = ""
        relations_out.append(
            {
                "parent_meter_id": r["from_meter"],
                "child_meter_id": r["to_meter"],
                "relation_type": relation_type,
                "flow_coefficient": flow_coefficient,
                "valid_from": "",
                "valid_to": "",
                "derived_from": derived_from,
            }
        )
    write_csv(
        out / "meter_relations.csv",
        ["parent_meter_id", "child_meter_id", "relation_type", "flow_coefficient", "valid_from", "valid_to", "derived_from"],
        relations_out,
    )

    # ---------------- meter_allocations.csv (extension) ----------------
    acct_path = recon / "facit_accounting.csv"
    if acct_path.exists():
        acct = read_csv_rows(acct_path)
        alloc_out = []
        for a in acct:
            alloc_out.append(
                {
                    "building_id": (lambda b: b if not b[0].isdigit() else f"B{b}")(str(a['building']).split()[0]),
                    "formula_row": a["row"],
                    "column_ref": a["formula_column"],
                    "sign": a["sign"],
                    "role": a["role"],
                    "meter_id": a["facit_meter_id"],
                    "excel_meter_id": a["excel_meter_id"],
                    "faktor": a.get("faktor", ""),
                    "n_terms": a["n_terms"],
                    "derived_from": "excel_Värme" if args.media == "VARME" else f"excel_{args.media}",
                }
            )
        write_csv(
            out / "meter_allocations.csv",
            ["building_id", "formula_row", "column_ref", "sign", "role", "meter_id", "excel_meter_id", "faktor", "n_terms", "derived_from"],
            alloc_out,
        )

    # ---------------- sensors.csv ----------------
    sensors_out = []
    for rec in meters_src:
        if rec.get("meter_type") == "virtual":
            continue
        fid = rec["meter_id"]
        sensors_out.append(
            {
                "sensor_id": f"{fid}.energy",
                "meter_id": fid,
                "point_type": "Energy_Sensor",
                "unit": args.unit,
                "identifier": "",
            }
        )
    write_csv(
        out / "sensors.csv",
        ["sensor_id", "meter_id", "point_type", "unit", "identifier"],
        sensors_out,
    )

    # ---------------- timeseries_refs.csv ----------------
    # Load meter swap events (from detect_meter_swaps.py).
    swap_rows = read_csv_rows(extracted / "meter_swaps.csv") if (extracted / "meter_swaps.csv").exists() else []
    swaps_by_sf: dict[str, dict] = {r["meter_id"]: r for r in swap_rows}

    ts_refs_out = []
    ts_fields = ["timeseries_id", "sensor_id", "aggregate", "reading_type", "kind",
                 "preferred", "valid_from", "valid_to", "database_id", "path",
                 "external_id", "device_id", "sources", "aggregation"]
    for rec in meters_src:
        if rec.get("meter_type") == "virtual":
            continue
        fid = rec["meter_id"]
        sf_id = xwalk.get(fid, {}).get("snowflake_id", "")
        if not sf_id:
            continue

        meter_events = sorted(
            [s for s in swap_rows if s["meter_id"] == sf_id],
            key=lambda s: s["swap_date"],
        )

        base = {
            "sensor_id": f"{fid}.energy",
            "aggregate": "daily",
            "reading_type": "counter",
            "database_id": args.database,
            "path": "OPS_WRK.ION_SWEDEN.DATALOG2",
            "external_id": sf_id,
            "device_id": "", "sources": "", "aggregation": "",
        }

        if not meter_events:
            ts_refs_out.append({**base, "timeseries_id": f"{fid}:d", "kind": "raw",
                                "preferred": "True", "valid_from": "", "valid_to": ""})
        else:
            # Build segments from events chronologically.
            # Each event either splits the timeline (swap/glitch) or ends it (offline).
            segments: list[tuple[str, str]] = []  # (valid_from, valid_to)
            cursor = ""  # start of current segment
            for ev in meter_events:
                if ev["event_type"] in ("swap", "rollover"):
                    # `swap` is a physical device replacement; `rollover`
                    # is a register wrap at a known ceiling (Schneider
                    # PowerLogic / ION meters default to a rollover at
                    # 10,000,000). The stitching is identical for both —
                    # we anchor on delta, so the absolute counter wrap
                    # is absorbed cleanly. Only the event label differs,
                    # so downstream annotations don't claim a physical
                    # device change that didn't happen.
                    #
                    # If the meter was offline, the swap/rollover just
                    # brings it back online — don't emit an empty
                    # (None, swap_date) segment, which would be written
                    # as blank valid_from and overlap prior segments.
                    # Start a fresh segment from swap_date.
                    if cursor is not None:
                        segments.append((cursor, ev["swap_date"]))
                    cursor = ev["swap_date"]
                elif ev["event_type"] == "glitch":
                    if cursor is not None:
                        segments.append((cursor, ev["swap_date"]))
                    cursor = ev.get("glitch_end", ev["swap_date"])
                elif ev["event_type"] == "offline":
                    if cursor is not None:
                        segments.append((cursor, ev["swap_date"]))
                    cursor = None
            if cursor is not None:
                segments.append((cursor, ""))

            if len(segments) == 1:
                vf, vt = segments[0]
                ts_refs_out.append({**base, "timeseries_id": f"{fid}:d", "kind": "raw",
                                    "preferred": "True", "valid_from": vf, "valid_to": vt})
            else:
                seg_ids = []
                for idx, (vf, vt) in enumerate(segments):
                    label = chr(ord("A") + idx)
                    seg_id = f"{fid}:d.{label}"
                    seg_ids.append(seg_id)
                    ts_refs_out.append({**base, "timeseries_id": seg_id, "kind": "raw",
                                        "preferred": "False", "valid_from": vf, "valid_to": vt})
                ts_refs_out.append({
                    "timeseries_id": f"{fid}:d", "sensor_id": f"{fid}.energy",
                    "aggregate": "daily", "reading_type": "counter",
                    "kind": "derived", "preferred": "True",
                    "valid_from": "", "valid_to": "",
                    "database_id": "", "path": "", "external_id": "",
                    "device_id": "", "sources": "|".join(seg_ids),
                    "aggregation": "rolling_sum",
                })
    write_csv(
        out / "timeseries_refs.csv",
        ["timeseries_id", "sensor_id", "aggregate", "reading_type", "kind", "preferred", "valid_from", "valid_to", "database_id", "path", "external_id", "device_id", "sources", "aggregation"],
        ts_refs_out,
    )

    # ---------------- shared stub (optional) ----------------
    if args.emit_shared:
        buildings = sorted({f"B{r['building']}" for r in meters_src if r.get("building")})
        write_csv(
            out / "buildings.csv",
            ["building_id", "name", "campus_id", "identifier"],
            [{"building_id": b, "name": f"Building {b[1:]}", "campus_id": args.campus, "identifier": ""} for b in buildings],
        )
        media_names = {
            "ANGA": "Steam",
            "VARME": "Heating (district)",
            "KYLA": "Cooling (district)",
            "EL": "Electrical",
        }
        media_descs = {
            "ANGA": "Steam energy (MWh) distributed via the site steam main.",
            "VARME": "District heating energy (MWh) delivered to per-building substations.",
            "KYLA": "Cooling energy (MWh) delivered to per-building substations.",
            "EL": "Electrical energy (kWh / MWh).",
        }
        meter_classes = {
            "ANGA": "Steam_Meter",
            "VARME": "Heating_Meter",
            "KYLA": "Chilled_Water_Meter",
            "EL": "Electrical_Meter",
        }
        substances = {
            "KYLA": "Chilled_Water",
            "VARME": "Hot_Water",
            "ANGA": "Steam",
        }
        media_types = [
            {
                "media_type_id": args.media,
                "name": media_names.get(args.media, args.media),
                "description": media_descs.get(args.media, ""),
                "brick_meter_class": meter_classes.get(args.media, ""),
                "brick_substance": substances.get(args.media, ""),
            }
        ]
        write_csv(out / "media_types.csv",
                  ["media_type_id", "name", "description", "brick_meter_class", "brick_substance"],
                  media_types)

    print(f"wrote {out / 'meters.csv'} ({len(meters_out)})")
    print(f"wrote {out / 'meter_relations.csv'} ({len(relations_out)})")
    if acct_path.exists():
        print(f"wrote {out / 'meter_allocations.csv'}")
    print(f"wrote {out / 'sensors.csv'} ({len(sensors_out)})")
    print(f"wrote {out / 'timeseries_refs.csv'} ({len(ts_refs_out)})")
    if args.emit_shared:
        print(f"wrote {out / 'buildings.csv'}, {out / 'media_types.csv'} (shared stubs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
