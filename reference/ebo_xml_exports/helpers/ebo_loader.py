#!/usr/bin/env python3
"""Parse EBO XML exports and load meter data into DuckDB."""

import argparse
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

KEEP_TYPES = {"trend.ETLog", "trend.TLog", "server.point.AV", "system.base.Folder"}

MODE_MAP = {"normal": "Standard", "bibliotek": "Library", "special": "Special"}

FILENAME_RE = re.compile(
    r"Export (normal|bibliotek|special) Mätare (.+) (\d{8})\.xml"
)


def parse_filename(path: Path) -> dict:
    m = FILENAME_RE.match(unicodedata.normalize("NFC", path.name))
    if not m:
        raise ValueError(f"Unexpected filename format: {path.name}")
    return {
        "file_name": path.name,
        "export_mode": MODE_MAP[m.group(1)],
        "location": m.group(2),
        "export_date": m.group(3),
    }


def parse_ebo_xml(filepath: Path) -> tuple[dict, list[dict]]:
    """Parse an EBO XML export, return (meta_dict, list_of_row_dicts)."""
    meta = {"server_path": None, "runtime_version": None}
    rows: list[dict] = []

    folder_stack: list[str] = []
    skip_depth = 0
    current_oi: dict | None = None

    for event, elem in ET.iterparse(str(filepath), events=("start", "end")):
        tag = elem.tag

        # -- MetaInformation fields --
        if tag == "ServerFullPath" and event == "start":
            meta["server_path"] = elem.get("Value")
            continue
        if tag == "RuntimeVersion" and event == "start":
            meta["runtime_version"] = elem.get("Value")
            continue

        # -- OI handling --
        if tag == "OI":
            if event == "start":
                if skip_depth > 0:
                    skip_depth += 1
                    continue

                oi_type = elem.get("TYPE", "")

                if oi_type not in KEEP_TYPES:
                    skip_depth = 1
                    continue

                if oi_type == "system.base.Folder":
                    folder_stack.append(elem.get("NAME", ""))
                else:
                    building_idx = _building_index(folder_stack)
                    current_oi = {
                        "oi_name": elem.get("NAME"),
                        "oi_type": oi_type,
                        "oi_description": elem.get("DESCR"),
                        "folder_path": "/".join(folder_stack),
                        "building": _safe_get(folder_stack, building_idx),
                        "system_number": _safe_get(folder_stack, building_idx + 1),
                        "subsystem": _safe_get(folder_stack, building_idx + 2),
                        "meter_folder": _safe_get(folder_stack, building_idx + 3),
                    }

            else:  # end
                if skip_depth > 0:
                    skip_depth -= 1
                    elem.clear()
                    continue

                oi_type = elem.get("TYPE", "")
                if oi_type == "system.base.Folder":
                    if folder_stack:
                        folder_stack.pop()
                elif current_oi is not None:
                    rows.append(current_oi)
                    current_oi = None

                elem.clear()

        # -- PI handling (only on end, so child Reference is available) --
        elif tag == "PI" and event == "end":
            if skip_depth > 0 or current_oi is None:
                elem.clear()
                continue

            pi_name = elem.get("Name", "")
            pi_value = elem.get("Value")
            pi_unit = elem.get("Unit")
            ref = elem.find("Reference")

            _map_pi(current_oi, pi_name, pi_value, pi_unit, ref)
            elem.clear()

    return meta, rows


def _building_index(folder_stack: list[str]) -> int:
    """Determine which folder_stack index holds the building code."""
    if len(folder_stack) > 1 and not re.match(r"^B\d+", folder_stack[1]):
        return 2
    return 1


def _safe_get(lst: list, idx: int) -> str | None:
    return lst[idx] if 0 <= idx < len(lst) else None


def _map_pi(oi: dict, name: str, value: str | None, unit: str | None, ref) -> None:
    """Map a PI element's data into the row dict."""
    if name == "ForceReadTimeout":
        oi["force_read_timeout"] = value
    elif name == "LastTransferredTimestamp":
        oi["last_transferred_ts"] = value
    elif name == "LogArray":
        oi["log_array_unit"] = unit
    elif name == "LogSize":
        oi["log_size"] = value
    elif name == "Threshold":
        oi["threshold"] = value
    elif name == "MonitoredLog":
        if ref is not None:
            oi["monitored_log_object"] = ref.get("Object")
            oi["monitored_log_locked"] = ref.get("Locked")
    elif name == "TriggerSignal":
        if ref is not None:
            oi["trigger_signal_object"] = ref.get("Object")
            oi["trigger_signal_property"] = ref.get("Property")
    elif name == "MeterStartTime":
        oi["meter_start_time"] = value
    elif name == "MeterEndTime":
        oi["meter_end_time"] = value
    elif name == "MeterTime":
        oi["meter_time"] = value
    elif name == "MeterChangeUser":
        oi["meter_change_user"] = value
    elif name == "MeterConstant":
        oi["meter_constant"] = value
    elif name == "MeterStartValue":
        oi["meter_start_value"] = value
    elif name == "MeterEndValue":
        oi["meter_end_value"] = value
    elif name == "MeterMaxValue":
        oi["meter_max_value"] = value
    elif name == "MeterMinValue":
        oi["meter_min_value"] = value
    elif name == "SmartLogEnabled":
        oi["smart_log_enabled"] = value
    # TLog-specific
    elif name == "DeltaValue":
        oi["delta_value"] = value
        oi["delta_value_unit"] = unit
    elif name == "Enabled":
        oi["enabled"] = value
    elif name == "Interval":
        oi["interval_ms"] = value
    elif name == "LogPoint":
        oi["log_point_unit"] = unit
        if ref is not None:
            oi["log_point_ref_object"] = ref.get("Object")
    elif name == "StartTime":
        oi["start_time"] = value
    # server.point.AV
    elif name == "Value":
        oi["av_value"] = value
        oi["av_unit"] = unit
        if ref is not None:
            oi["av_ref_object"] = ref.get("Object")
            oi["av_ref_property"] = ref.get("Property")


# -- DuckDB schema & loading --

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS import_files (
    file_id          INTEGER PRIMARY KEY,
    file_name        VARCHAR NOT NULL,
    location         VARCHAR NOT NULL,
    export_mode      VARCHAR NOT NULL,
    export_date      VARCHAR,
    server_path      VARCHAR,
    runtime_version  VARCHAR,
    imported_at      TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS meter_points (
    point_id              INTEGER PRIMARY KEY,
    file_id               INTEGER NOT NULL,
    oi_name               VARCHAR NOT NULL,
    oi_type               VARCHAR NOT NULL,
    oi_description        VARCHAR,
    folder_path           VARCHAR NOT NULL,
    building              VARCHAR,
    system_number         VARCHAR,
    subsystem             VARCHAR,
    meter_folder          VARCHAR,
    force_read_timeout    VARCHAR,
    last_transferred_ts   VARCHAR,
    log_array_unit        VARCHAR,
    log_size              VARCHAR,
    threshold             VARCHAR,
    monitored_log_object  VARCHAR,
    monitored_log_locked  VARCHAR,
    trigger_signal_object VARCHAR,
    trigger_signal_property VARCHAR,
    meter_start_time      VARCHAR,
    meter_end_time        VARCHAR,
    meter_time            VARCHAR,
    meter_change_user     VARCHAR,
    meter_constant        VARCHAR,
    meter_start_value     VARCHAR,
    meter_end_value       VARCHAR,
    meter_max_value       VARCHAR,
    meter_min_value       VARCHAR,
    smart_log_enabled     VARCHAR,
    delta_value           VARCHAR,
    delta_value_unit      VARCHAR,
    enabled               VARCHAR,
    interval_ms           VARCHAR,
    log_point_unit        VARCHAR,
    log_point_ref_object  VARCHAR,
    start_time            VARCHAR,
    av_value              VARCHAR,
    av_unit               VARCHAR,
    av_ref_object         VARCHAR,
    av_ref_property       VARCHAR
);
"""

ALL_POINT_COLS = [
    "oi_name", "oi_type", "oi_description", "folder_path",
    "building", "system_number", "subsystem", "meter_folder",
    "force_read_timeout", "last_transferred_ts", "log_array_unit",
    "log_size", "threshold", "monitored_log_object", "monitored_log_locked",
    "trigger_signal_object", "trigger_signal_property",
    "meter_start_time", "meter_end_time", "meter_time",
    "meter_change_user", "meter_constant", "meter_start_value",
    "meter_end_value", "meter_max_value", "meter_min_value",
    "smart_log_enabled",
    "delta_value", "delta_value_unit", "enabled", "interval_ms",
    "log_point_unit", "log_point_ref_object", "start_time",
    "av_value", "av_unit", "av_ref_object", "av_ref_property",
]


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in SCHEMA_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            con.execute(stmt)


def load_file(con: duckdb.DuckDBPyConnection, filepath: Path, file_id: int) -> int:
    file_info = parse_filename(filepath)
    meta, rows = parse_ebo_xml(filepath)

    con.execute(
        "INSERT INTO import_files VALUES (?, ?, ?, ?, ?, ?, ?, current_timestamp)",
        [
            file_id,
            file_info["file_name"],
            file_info["location"],
            file_info["export_mode"],
            file_info["export_date"],
            meta["server_path"],
            meta["runtime_version"],
        ],
    )

    if not rows:
        return 0

    point_id_start = con.execute(
        "SELECT COALESCE(MAX(point_id), 0) FROM meter_points"
    ).fetchone()[0] + 1

    placeholders = ", ".join(["?"] * (2 + len(ALL_POINT_COLS)))
    insert_sql = f"INSERT INTO meter_points VALUES ({placeholders})"

    params = []
    for i, row in enumerate(rows):
        vals = [point_id_start + i, file_id]
        vals.extend(row.get(col) for col in ALL_POINT_COLS)
        params.append(vals)

    con.executemany(insert_sql, params)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Load EBO XML exports into DuckDB")
    parser.add_argument("--db", default="ebo.duckdb", help="DuckDB file path")
    parser.add_argument(
        "--dir", default="Exporter EBO", help="Directory with XML exports"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    xml_dir = Path(args.dir)
    xml_files = sorted(xml_dir.glob("*.xml"))
    if not xml_files:
        log.error("No XML files found in %s", xml_dir)
        return

    con = duckdb.connect(args.db)
    create_schema(con)

    # Clear existing data for a clean load
    con.execute("DELETE FROM meter_points")
    con.execute("DELETE FROM import_files")

    total = 0
    for file_id, filepath in enumerate(xml_files, start=1):
        log.info("Loading %s ...", filepath.name)
        count = load_file(con, filepath, file_id)
        log.info("  -> %d meter points", count)
        total += count

    log.info("")
    log.info("Done. %d files, %d total meter points -> %s", len(xml_files), total, args.db)

    # Quick summary
    log.info("")
    log.info("=== Summary ===")
    for row in con.execute(
        "SELECT export_mode, location, COUNT(*) FROM import_files GROUP BY 1, 2 ORDER BY 2, 1"
    ).fetchall():
        log.info("  %s / %s: %d file(s)", row[1], row[0], row[2])

    log.info("")
    for row in con.execute(
        "SELECT oi_type, COUNT(*) FROM meter_points GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        log.info("  %s: %d points", row[0], row[1])

    con.close()


if __name__ == "__main__":
    main()
