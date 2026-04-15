"""Streamlit app entry point."""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from app.graph import to_dot
from ontology import Dataset, Meter, load_dataset
from refsite import abbey_road
from validation import validate

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "reference_site" / "abbey_road"


def _readings_section(
    ds: Dataset,
) -> tuple[list[str], list[str], tuple[date, date]] | None:
    """Interactive chart over the synthetic reading series.

    Counters are drawn as lines (cumulative kWh index or per-period
    derivative). Monthly deltas are drawn as bars. Hours outside each
    meter's `[valid_from, valid_to)` are rendered as a shaded backdrop
    so onboarding/decommissioning is visible at a glance.

    Returns the chosen (buildings, meters, date_range) so the Tables
    section can narrow to the same scope.
    """
    if not ds.readings:
        st.info("No readings loaded — run `make seed` to regenerate.")
        return None

    refs = {r.timeseries_id: r for r in ds.timeseries_refs}
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    meters_by_id = {m.meter_id: m for m in ds.meters}

    df = pd.DataFrame([r.model_dump() for r in ds.readings])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["meter_id"] = df["timeseries_id"].map(
        lambda t: sensor_meter[refs[t].sensor_id]
    )
    df["aggregate"] = df["timeseries_id"].map(lambda t: refs[t].aggregate)
    df["reading_type"] = df["timeseries_id"].map(lambda t: refs[t].reading_type)
    df["kind"] = df["timeseries_id"].map(lambda t: refs[t].kind)
    df["building_id"] = df["meter_id"].map(
        lambda m: meters_by_id[m].building_id or "(campus)"
    )

    cols = st.columns([1, 1, 2])
    with cols[0]:
        buildings = sorted(df["building_id"].unique())
        sel_buildings = st.multiselect("Building", buildings, default=buildings)
    with cols[1]:
        df_b = df[df["building_id"].isin(sel_buildings)]
        meter_ids = sorted(df_b["meter_id"].unique())
        # Default to the supplier reconciliation triplet + intake if present.
        default_meters = [m for m in ("I1", "I2", "I3", "M0") if m in meter_ids]
        if not default_meters:
            default_meters = meter_ids[: min(3, len(meter_ids))]
        sel_meters = st.multiselect("Meter", meter_ids, default=default_meters)
    with cols[2]:
        tmin = df["timestamp"].min().date()
        tmax = df["timestamp"].max().date()
        date_range = st.slider(
            "Date range", min_value=tmin, max_value=tmax, value=(tmin, tmax)
        )

    view = st.radio(
        "Counter view",
        ["cumulative (kWh index)", "hourly rate (kWh/h)"],
        horizontal=True,
        help=(
            "Counters store the cumulative meter index. "
            "'Hourly rate' takes the per-step difference."
        ),
    )

    df_sel = df[
        df["meter_id"].isin(sel_meters)
        & (df["timestamp"].dt.date >= date_range[0])
        & (df["timestamp"].dt.date <= date_range[1] + timedelta(days=1))
    ].copy()
    if df_sel.empty:
        st.warning("No readings for the current selection.")
        return sel_buildings, sel_meters, date_range

    counters = df_sel[df_sel["reading_type"] == "counter"].copy()
    deltas = df_sel[df_sel["reading_type"] == "delta"].copy()

    if not counters.empty:
        if view.startswith("hourly"):
            counters = counters.sort_values(["timeseries_id", "timestamp"])
            counters["value"] = counters.groupby("timeseries_id")["value"].diff()
            counters = counters.dropna(subset=["value"])
            y_title = "kWh / hour"
        else:
            y_title = "Counter index (kWh)"

        line = (
            alt.Chart(counters)
            .mark_line()
            .encode(
                x=alt.X("timestamp:T", title=None),
                y=alt.Y("value:Q", title=y_title),
                color=alt.Color("timeseries_id:N", title="Series"),
                tooltip=["timeseries_id", "timestamp", "value"],
            )
            .properties(height=320)
        )

        # Validity backdrop: one rectangle per (selected meter, invalid
        # interval) inside the view window. Shading lives behind the line.
        bands = _validity_bands(
            sel_meters, meters_by_id, date_range[0], date_range[1]
        )
        if not bands.empty:
            backdrop = (
                alt.Chart(bands)
                .mark_rect(opacity=0.10, color="#888")
                .encode(
                    x="start:T",
                    x2="end:T",
                    tooltip=["meter_id", "reason"],
                )
            )
            chart = backdrop + line
        else:
            chart = line

        st.altair_chart(chart, width="stretch")

    if not deltas.empty:
        st.caption("Monthly manual readings (Avläsning, delta)")
        bars = (
            alt.Chart(deltas)
            .mark_bar()
            .encode(
                x=alt.X("yearmonth(timestamp):T", title=None),
                y=alt.Y("value:Q", title="kWh / month"),
                color=alt.Color("timeseries_id:N", title="Series"),
                xOffset="timeseries_id:N",
                tooltip=["timeseries_id", "timestamp", "value"],
            )
            .properties(height=200)
        )
        st.altair_chart(bars, width="stretch")

    return sel_buildings, sel_meters, date_range


def _tables_section(
    ds: Dataset,
    selection: tuple[list[str], list[str], tuple[date, date]] | None,
) -> None:
    """Render the ontology tables, narrowed to the Readings filter scope.

    - building-scoped tables (buildings, zones) filter on sel_buildings
    - meter-scoped tables (meters, meter_measures, timeseries_refs) filter
      on sel_meters
    - relations keep edges where either endpoint is in sel_meters so
      adjacency is visible
    - databases always show in full (not scoped by building or meter)
    """
    if selection is None:
        sel_buildings: list[str] | None = None
        sel_meters: list[str] | None = None
    else:
        sel_buildings, sel_meters, _date_range = selection

    # "(campus)" is the placeholder used in the readings filter for
    # meters with no building; translate back to the None used in ds.
    include_campus = sel_buildings is None or "(campus)" in sel_buildings
    building_filter = (
        None if sel_buildings is None else [b for b in sel_buildings if b != "(campus)"]
    )

    def keep_meter(mid: str | None) -> bool:
        if sel_meters is None:
            return True
        return mid is not None and mid in sel_meters

    def keep_building(bid: str | None) -> bool:
        if building_filter is None:
            return True
        if bid is None:
            return include_campus
        return bid in building_filter

    meters = [m for m in ds.meters if keep_building(m.building_id)]
    if sel_meters is not None:
        meters = [m for m in meters if m.meter_id in sel_meters]
    relations = [
        r for r in ds.relations
        if sel_meters is None
        or r.parent_meter_id in sel_meters
        or r.child_meter_id in sel_meters
    ]
    zones = [z for z in ds.zones if keep_building(z.building_id)]
    meter_measures = [mm for mm in ds.meter_measures if keep_meter(mm.meter_id)]
    media_types = ds.media_types  # small table, show in full
    buildings = [b for b in ds.buildings if keep_building(b.building_id)]
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    sensors = [s for s in ds.sensors if keep_meter(s.meter_id)]
    timeseries_refs = [
        tr for tr in ds.timeseries_refs
        if keep_meter(sensor_meter.get(tr.sensor_id))
    ]

    tabs = st.tabs(
        [
            f"meters ({len(meters)})",
            f"relations ({len(relations)})",
            f"zones ({len(zones)})",
            f"meter_measures ({len(meter_measures)})",
            f"buildings ({len(buildings)})",
            f"sensors ({len(sensors)})",
            f"timeseries_refs ({len(timeseries_refs)})",
            f"media_types ({len(media_types)})",
            f"databases ({len(ds.databases)})",
        ]
    )
    with tabs[0]:
        st.dataframe([m.model_dump() for m in meters], width="stretch")
    with tabs[1]:
        st.dataframe([r.model_dump() for r in relations], width="stretch")
    with tabs[2]:
        st.dataframe([z.model_dump() for z in zones], width="stretch")
    with tabs[3]:
        st.dataframe([mm.model_dump() for mm in meter_measures], width="stretch")
    with tabs[4]:
        st.dataframe([b.model_dump() for b in buildings], width="stretch")
    with tabs[5]:
        st.dataframe([s.model_dump() for s in sensors], width="stretch")
    with tabs[6]:
        st.dataframe([tr.model_dump() for tr in timeseries_refs], width="stretch")
    with tabs[7]:
        st.dataframe([mt.model_dump() for mt in media_types], width="stretch")
    with tabs[8]:
        st.dataframe([d.model_dump() for d in ds.databases], width="stretch")


def _validity_bands(
    meter_ids: list[str],
    meters_by_id: dict[str, Meter],
    window_start: date,
    window_end: date,
) -> pd.DataFrame:
    """Return one row per invalid interval that overlaps the view window.

    Used to render the grey 'out-of-validity' backdrop on the chart. We
    only emit a band when at least one selected meter is *not* valid for
    that interval, so a fully-valid window draws nothing.
    """
    rows = []
    for mid in meter_ids:
        m = meters_by_id[mid]
        # Pre-validity gap.
        if m.valid_from is not None and m.valid_from > window_start:
            rows.append(
                {
                    "meter_id": mid,
                    "start": pd.Timestamp(window_start),
                    "end": pd.Timestamp(min(m.valid_from, window_end)),
                    "reason": f"{mid} not yet online (valid_from={m.valid_from})",
                }
            )
        # Post-validity gap.
        if m.valid_to is not None and m.valid_to < window_end:
            rows.append(
                {
                    "meter_id": mid,
                    "start": pd.Timestamp(max(m.valid_to, window_start)),
                    "end": pd.Timestamp(window_end),
                    "reason": f"{mid} retired (valid_to={m.valid_to})",
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="graphite", layout="wide")
    st.title("graphite")
    st.caption(abbey_road.SUMMARY)

    data_root = Path(
        st.sidebar.text_input("Data root", str(DEFAULT_DATA_ROOT))
    )

    if not data_root.exists():
        st.warning(
            f"No CSVs found at `{data_root}`. Run `make seed` or "
            f"`uv run refsite-generate`."
        )
        return

    ds = load_dataset(data_root)

    st.sidebar.markdown("### Counts")
    st.sidebar.write(
        {
            "campuses": len(ds.campuses),
            "buildings": len(ds.buildings),
            "zones": len(ds.zones),
            "meters": len(ds.meters),
            "relations": len(ds.relations),
        }
    )

    violations = validate(ds)
    if violations:
        st.error(f"{len(violations)} validation violation(s)")
        st.dataframe([v.model_dump() for v in violations], width="stretch")

    with st.expander("About this test site", expanded=False):
        st.markdown(
            "Each item below is a real-world quirk the ontology has to "
            "handle. The Abbey Road dataset bakes one minimal example of "
            "each so the model, validators, and viz can be exercised "
            "end-to-end."
        )
        st.markdown(
            "\n".join(f"- **{label}** — {why}" for label, why in abbey_road.FEATURES)
        )

    st.subheader("Topology")
    st.caption(abbey_road.TOPOLOGY_CAPTION)
    st.graphviz_chart(to_dot(ds), width="stretch")

    st.subheader("Readings")
    st.caption(abbey_road.READINGS_CAPTION)
    selection = _readings_section(ds)

    with st.expander("Tables"):
        _tables_section(ds, selection)

    st.subheader("Tests")
    _tests_section()


def _tests_section() -> None:
    """Run pytest and render per-test pass/fail with human-readable docs."""
    if st.button("Re-run tests", help="Clear cache and re-run pytest"):
        _run_pytest.clear()

    with st.spinner("Running pytest…"):
        results = _run_pytest()

    if results.get("error"):
        st.error(results["error"])
        if results.get("stdout"):
            st.code(results["stdout"], language="text")
        return

    summary = results["summary"]
    cols = st.columns(4)
    cols[0].metric("Total", summary["total"])
    cols[1].metric("Passed", summary["passed"])
    cols[2].metric("Failed", summary["failed"])
    cols[3].metric("Duration (s)", f"{summary['duration']:.2f}")

    rows = results["tests"]
    if not rows:
        st.info("No tests collected.")
        return

    docs = _collect_docstrings(REPO_ROOT)
    df = pd.DataFrame(rows)
    df["package"] = df["nodeid"].map(_package_of)
    df["test"] = df["nodeid"].map(lambda n: n.split("::")[-1])
    df["explains"] = df["nodeid"].map(lambda n: docs.get(n, ""))
    df["status"] = df["outcome"].map({"passed": "✅", "failed": "❌", "skipped": "⏭"})

    table = df[["status", "package", "test", "explains", "duration"]].rename(
        columns={"duration": "s"}
    )
    # ~36px per row + header so the whole table is visible without scrolling.
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        height=36 * (len(table) + 1) + 2,
    )


def _package_of(nodeid: str) -> str:
    """`packages/foo/tests/test_x.py::test_y` → `foo`."""
    parts = nodeid.split("/")
    if len(parts) >= 2 and parts[0] == "packages":
        return parts[1]
    return parts[0] if parts else "(root)"


@st.cache_data(show_spinner=False)
def _collect_docstrings(repo_root: Path) -> dict[str, str]:
    """Map pytest nodeid → first line of the test function's docstring.

    Parsed straight from each test file via `ast` so the explanation
    *is* the docstring — no separate mapping to maintain. Tests with
    no docstring just get an empty string.
    """
    out: dict[str, str] = {}
    for path in repo_root.glob("packages/*/tests/test_*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = path.relative_to(repo_root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                doc = ast.get_docstring(node) or ""
                first_line = inspect.cleandoc(doc).splitlines()[0] if doc else ""
                out[f"{rel}::{node.name}"] = first_line
    return out


@st.cache_data(show_spinner=False)
def _run_pytest() -> dict[str, Any]:
    """Run pytest with the json-report plugin and return parsed results.

    Cached for the session so the page doesn't re-run pytest on every
    rerender; the 'Re-run tests' button clears the cache.
    """
    repo_root = REPO_ROOT
    report_path = repo_root / ".pytest-report.json"
    if report_path.exists():
        report_path.unlink()

    try:
        proc = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "--json-report",
                f"--json-report-file={report_path}",
                "--no-header",
                "-q",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        return {"error": f"Could not invoke pytest: {e}"}
    except subprocess.TimeoutExpired:
        return {"error": "pytest timed out after 120s"}

    if not report_path.exists():
        # json-report plugin missing or pytest blew up before writing.
        return {
            "error": (
                "pytest did not produce a JSON report. "
                "Install `pytest-json-report` (added to dev deps)."
            ),
            "stdout": proc.stdout + proc.stderr,
        }

    report = json.loads(report_path.read_text())
    summary = report.get("summary", {})
    return {
        "summary": {
            "total": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "duration": report.get("duration", 0.0),
        },
        "tests": [
            {
                "nodeid": t["nodeid"],
                "outcome": t["outcome"],
                "duration": round(
                    sum(t.get(phase, {}).get("duration", 0.0)
                        for phase in ("setup", "call", "teardown")),
                    3,
                ),
            }
            for t in report.get("tests", [])
        ],
    }


if __name__ == "__main__":
    main()
