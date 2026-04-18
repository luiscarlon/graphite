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
import yaml

import calc
from app.graph import to_dot
from ontology import Dataset, Meter, load_dataset
from validation import validate

REPO_ROOT = Path(__file__).resolve().parents[4]
SITES_ROOT = REPO_ROOT / "data" / "sites"


def _load_site_meta(site_dir: Path) -> dict[str, str]:
    meta_path = site_dir / "site_meta.yaml"
    if meta_path.exists():
        return yaml.safe_load(meta_path.read_text())
    return {"name": site_dir.name, "summary": ""}


_ANNOTATION_COLORS = {
    "outage": "#e45756",
    "swap": "#4c78a8",
    "data_quality": "#f58518",
    "unknown": "#bab0ac",
    "calibration": "#72b7b2",
    "patch": "#54a24b",
}


def _annotation_layer(
    ds: Dataset,
    meter_ids: set[str] | None,
    building_ids: set[str] | None,
    date_range: tuple[date, date] | None,
) -> alt.Chart | None:
    rows = []
    for a in ds.annotations:
        if a.valid_from is None and a.valid_to is None:
            continue
        if meter_ids is not None and a.target_kind == "meter" and a.target_id not in meter_ids:
            continue
        if building_ids is not None and a.target_kind == "building" and a.target_id not in building_ids:
            continue
        start = pd.Timestamp(a.valid_from) if a.valid_from else pd.Timestamp("2024-01-01")
        end = pd.Timestamp(a.valid_to) if a.valid_to else pd.Timestamp("2027-01-01")
        if date_range:
            if end.date() < date_range[0] or start.date() > date_range[1]:
                continue
        rows.append({
            "start": start, "end": end,
            "category": a.category,
            "label": f"{a.target_id}: {a.description[:60]}",
            "color": _ANNOTATION_COLORS.get(a.category, "#bab0ac"),
        })
    if not rows:
        return None
    adf = pd.DataFrame(rows)
    return (
        alt.Chart(adf)
        .mark_rect(opacity=0.15)
        .encode(
            x="start:T",
            x2="end:T",
            color=alt.Color("category:N", scale=alt.Scale(
                domain=list(_ANNOTATION_COLORS.keys()),
                range=list(_ANNOTATION_COLORS.values()),
            )),
            tooltip=["category", "label"],
        )
    )


def _detect_granularity(ds: Dataset) -> str:
    for tr in ds.timeseries_refs:
        if tr.preferred and tr.reading_type == "counter":
            return tr.aggregate
    return "unknown"


def _detect_unit(ds: Dataset) -> str:
    units = {s.unit for s in ds.sensors}
    if len(units) == 1:
        return units.pop()
    return "mixed"


_UNIT_SHORT = {
    "KiloW-HR": "kWh",
    "Megawatt-Hour": "MWh",
    "M3": "m³",
}


def _unit_label(ds: Dataset) -> str:
    return _UNIT_SHORT.get(_detect_unit(ds), _detect_unit(ds))


def _readings_section(
    ds: Dataset,
    ann_bands: pd.DataFrame | None = None,
    ann_hints: dict | None = None,
) -> tuple[list[str], list[str], tuple[date, date]] | None:
    if not ds.readings:
        st.info("No readings loaded.")
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

    granularity = _detect_granularity(ds)
    unit = _unit_label(ds)
    rate_label = f"{unit}/{granularity}" if granularity != "unknown" else unit

    cols = st.columns([1, 1, 2])
    with cols[0]:
        buildings = sorted(df["building_id"].unique())
        if ann_hints and ann_hints["buildings"]:
            default_buildings = sorted(b for b in ann_hints["buildings"] if b in buildings)
        else:
            default_buildings = buildings
        sel_buildings = st.multiselect("Building", buildings, default=default_buildings)
    with cols[1]:
        df_b = df[df["building_id"].isin(sel_buildings)]
        meter_ids = sorted(df_b["meter_id"].unique())
        if ann_hints and ann_hints["meters"]:
            default_meters = sorted(m for m in ann_hints["meters"] if m in meter_ids)
        else:
            default_meters = meter_ids[: min(3, len(meter_ids))]
        if not default_meters:
            default_meters = meter_ids[: min(3, len(meter_ids))]
        sel_meters = st.multiselect("Meter", meter_ids, default=default_meters)
    with cols[2]:
        tmin = df["timestamp"].min().date()
        tmax = df["timestamp"].max().date()
        if ann_hints and ann_hints["date_range"]:
            dmin = max(ann_hints["date_range"][0], tmin)
            dmax = min(ann_hints["date_range"][1], tmax)
        else:
            dmin, dmax = tmin, tmax
        date_range = st.slider(
            "Date range", min_value=tmin, max_value=tmax, value=(dmin, dmax)
        )

    view = st.radio(
        "Counter view",
        ["cumulative (index)", f"rate ({rate_label})"],
        horizontal=True,
        help="Counters store the cumulative meter index. 'Rate' takes the per-step difference.",
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
        if view.startswith("rate"):
            counters = counters.sort_values(["timeseries_id", "timestamp"])
            counters["value"] = counters.groupby("timeseries_id")["value"].diff()
            counters = counters.dropna(subset=["value"])
            y_title = rate_label
        else:
            y_title = "Counter index"

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

        dr = (pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
        filtered_bands = _filter_ann_bands(ann_bands, data_range=dr, meter_ids=set(sel_meters), ds=ds)
        chart = _inject_ann_bands(chart, filtered_bands)
        st.altair_chart(chart, width="stretch")

    if not deltas.empty:
        st.caption("Delta readings")
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
    if selection is None:
        sel_buildings: list[str] | None = None
        sel_meters: list[str] | None = None
    else:
        sel_buildings, sel_meters, _date_range = selection

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
    media_types = ds.media_types
    buildings = [b for b in ds.buildings if keep_building(b.building_id)]
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    sensors = [s for s in ds.sensors if keep_meter(s.meter_id)]
    timeseries_refs = [
        tr for tr in ds.timeseries_refs
        if keep_meter(sensor_meter.get(tr.sensor_id))
    ]

    annotations = ds.annotations

    tabs = st.tabs(
        [
            f"meters ({len(meters)})",
            f"relations ({len(relations)})",
            f"annotations ({len(annotations)})",
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
        st.dataframe([a.model_dump() for a in annotations], width="stretch")
    with tabs[3]:
        st.dataframe([z.model_dump() for z in zones], width="stretch")
    with tabs[4]:
        st.dataframe([mm.model_dump() for mm in meter_measures], width="stretch")
    with tabs[5]:
        st.dataframe([b.model_dump() for b in buildings], width="stretch")
    with tabs[6]:
        st.dataframe([s.model_dump() for s in sensors], width="stretch")
    with tabs[7]:
        st.dataframe([tr.model_dump() for tr in timeseries_refs], width="stretch")
    with tabs[8]:
        st.dataframe([mt.model_dump() for mt in media_types], width="stretch")
    with tabs[9]:
        st.dataframe([d.model_dump() for d in ds.databases], width="stretch")


def _validity_bands(
    meter_ids: list[str],
    meters_by_id: dict[str, Meter],
    window_start: date,
    window_end: date,
) -> pd.DataFrame:
    rows = []
    for mid in meter_ids:
        m = meters_by_id[mid]
        if m.valid_from is not None and m.valid_from > window_start:
            rows.append(
                {
                    "meter_id": mid,
                    "start": pd.Timestamp(window_start),
                    "end": pd.Timestamp(min(m.valid_from, window_end)),
                    "reason": f"{mid} not yet online (valid_from={m.valid_from})",
                }
            )
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

    if not SITES_ROOT.exists():
        st.error(f"No sites directory at `{SITES_ROOT}`.")
        return

    sites = sorted(p.name for p in SITES_ROOT.iterdir() if p.is_dir())
    if not sites:
        st.error("No sites found.")
        return

    selected_site = st.sidebar.selectbox("Site", sites)
    site_dir = SITES_ROOT / selected_site
    site_meta = _load_site_meta(site_dir)

    ds_full = load_dataset(site_dir)

    available_media = sorted({m.media_type_id for m in ds_full.meters})
    if not available_media:
        st.warning("No meters found for this site.")
        return

    selected_media = st.sidebar.selectbox("Media", available_media)
    ds = ds_full.filter_by_media(selected_media)

    st.caption(site_meta.get("summary", ""))

    st.sidebar.markdown("### Counts")
    st.sidebar.write(
        {
            "buildings": len(ds.buildings),
            "meters": len(ds.meters),
            "relations": len(ds.relations),
            "readings": len(ds.readings),
        }
    )

    violations = validate(ds)
    if violations:
        with st.expander(f"{len(violations)} validation violation(s)", expanded=False):
            st.dataframe([v.model_dump() for v in violations], width="stretch")

    st.subheader("Topology")
    st.graphviz_chart(to_dot(ds), width="stretch")

    ann_bands = None
    ann_hints = None
    if ds.annotations:
        with st.expander(f"Annotations ({len(ds.annotations)})", expanded=False):
            ann_bands, ann_hints = _annotations_picker(ds)

    st.subheader("Readings")
    selection = _readings_section(ds, ann_bands, ann_hints)

    with st.expander("Tables"):
        _tables_section(ds, selection)

    st.subheader("Consumption")
    _consumption_section(ds, selection, ann_bands)

    st.subheader("Excel comparison")
    _excel_comparison_section(ds, site_dir)

    st.subheader("Tests")
    _tests_section()


def _consumption_section(
    ds: Dataset,
    selection: tuple[list[str], list[str], tuple[date, date]] | None,
    ann_bands: pd.DataFrame | None = None,
) -> None:
    granularity = _detect_granularity(ds)
    unit = _unit_label(ds)
    rate_label = f"{unit}/{granularity}" if granularity != "unknown" else unit

    conn = calc.connect(ds)
    default_sql = calc.sql("consumption")

    with st.expander("SQL", expanded=False):
        query = st.text_area(
            "consumption.sql",
            value=default_sql,
            height=320,
            key="consumption_sql",
            label_visibility="collapsed",
        )
        with st.expander("Base views (`views.sql`)", expanded=False):
            st.code(calc.sql("views"), language="sql")

    try:
        df = conn.execute(query).fetchdf()
    except Exception as e:  # noqa: BLE001
        st.error(f"SQL error: {e}")
        return

    # Series view: preferred timeseries flow per meter
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    series_df = conn.execute(
        "SELECT meter_id, timestamp, delta_kwh FROM measured_flow"
    ).fetchdf()
    series_df["timestamp"] = pd.to_datetime(series_df["timestamp"])

    levels = sorted(df["level"].unique()) if not df.empty else []
    all_levels = ["series"] + levels
    default_idx = all_levels.index("building") if "building" in all_levels else 0
    level = st.radio("Group by", all_levels, index=default_idx, horizontal=True)

    # Apply filters from Readings section
    if selection is not None:
        sel_buildings, sel_meters, date_range = selection
        bld_set = {b for b in sel_buildings if b != "(campus)"}
        meter_building = {m.meter_id: m.building_id or "(campus)" for m in ds.meters}
    else:
        sel_buildings = sel_meters = None
        date_range = None
        bld_set = None

    if level == "series":
        scoped = series_df.copy()
        if sel_meters:
            scoped = scoped[scoped["meter_id"].isin(sel_meters)]
        if date_range:
            scoped = scoped[
                (scoped.timestamp.dt.date >= date_range[0])
                & (scoped.timestamp.dt.date <= date_range[1])
            ]
        if scoped.empty:
            st.info("No data for current selection.")
            return
        totals = (
            scoped.groupby("meter_id", as_index=False)["delta_kwh"]
            .sum()
            .sort_values("delta_kwh", ascending=False)
            .rename(columns={"delta_kwh": "net_kwh", "meter_id": "target_id"})
        )
        totals["target_name"] = totals["target_id"]
        chart_color = "meter_id:N"
        chart_y = "delta_kwh:Q"
        chart_tooltip = ["meter_id", "timestamp", "delta_kwh"]
        y_title = f"Flow {rate_label}"
    else:
        if df.empty:
            st.info("Query returned no rows.")
            return
        scoped = df[df["level"] == level].copy()
        scoped["timestamp"] = pd.to_datetime(scoped["timestamp"])
        if level == "building" and bld_set:
            scoped = scoped[scoped["target_id"].isin(bld_set)]
        if date_range:
            scoped = scoped[
                (scoped.timestamp.dt.date >= date_range[0])
                & (scoped.timestamp.dt.date <= date_range[1])
            ]
        if scoped.empty:
            st.info("No data for current selection.")
            return
        totals = (
            scoped.groupby(["target_id", "target_name"], as_index=False)["net_kwh"]
            .sum()
            .sort_values("net_kwh", ascending=False)
        )
        chart_color = "target_id:N"
        chart_y = "net_kwh:Q"
        chart_tooltip = ["target_id", "target_name", "timestamp", "net_kwh"]
        y_title = f"Net {rate_label}"

    cols = st.columns([1, 3])
    with cols[0]:
        st.caption(f"Total ({unit}, selected period)")
        st.dataframe(
            totals.assign(net_kwh=totals["net_kwh"].round(0)),
            hide_index=True,
            width="stretch",
            height=min(36 * (len(totals) + 1) + 2, 400),
        )
    with cols[1]:
        chart = (
            alt.Chart(scoped)
            .mark_line()
            .encode(
                x=alt.X("timestamp:T", title=None),
                y=alt.Y(chart_y, title=y_title),
                color=alt.Color(chart_color, title=level),
                tooltip=chart_tooltip,
            )
            .properties(height=360)
        )
        cons_dr = (scoped["timestamp"].min(), scoped["timestamp"].max()) if not scoped.empty else None
        filtered_bands = _filter_ann_bands(ann_bands, data_range=cons_dr)
        chart = _inject_ann_bands(chart, filtered_bands)
        st.altair_chart(chart, width="stretch")


def _annotations_picker(ds: Dataset) -> tuple[pd.DataFrame | None, dict | None]:
    """Returns (bands_df, filter_hints) where filter_hints has meters, buildings, date_range."""
    cols = st.columns([1, 1])
    with cols[0]:
        select_all = st.checkbox("Select all", key="ann_select_all")
    with cols[1]:
        isolate = st.checkbox("Isolate selection", key="ann_isolate",
                              help="Filter readings and consumption to only show data relevant to selected annotations")
    adf = pd.DataFrame([a.model_dump() for a in ds.annotations])
    adf["select"] = select_all
    adf["patched"] = adf["related_refs"].apply(lambda r: "yes" if r else "no")
    display_cols = ["select", "annotation_id", "description", "patched", "category",
                    "target_kind", "target_id", "valid_from", "valid_to"]
    edited = st.data_editor(
        adf[display_cols],
        hide_index=True,
        width="stretch",
        column_config={"select": st.column_config.CheckboxColumn("", default=False, width="small")},
        key="ann_editor",
    )

    selected = edited[edited["select"] == True]  # noqa: E712
    if selected.empty:
        return None, None

    sel_annotations = [ds.annotations[i] for i in selected.index]
    rows = []
    for a in sel_annotations:
        if a.valid_from is None:
            continue
        rows.append({
            "start": pd.Timestamp(a.valid_from),
            "end": pd.Timestamp(a.valid_to) if a.valid_to else pd.Timestamp("2026-03-01"),
            "label": a.annotation_id,
            "description": a.description,
            "category": a.category,
        })
    bands = pd.DataFrame(rows) if rows else None

    hints = None
    if isolate:
        meter_ids: set[str] = set()
        building_ids: set[str] = set()
        date_min = date(2026, 3, 1)
        date_max = date(2025, 1, 1)
        for a in sel_annotations:
            if a.target_kind == "meter":
                meter_ids.add(a.target_id)
                m = next((m for m in ds.meters if m.meter_id == a.target_id), None)
                if m and m.building_id:
                    building_ids.add(m.building_id)
            elif a.target_kind == "building":
                building_ids.add(a.target_id)
                meter_ids.update(m.meter_id for m in ds.meters if m.building_id == a.target_id)
            elif a.target_kind == "campus":
                building_ids.update(b.building_id for b in ds.buildings)
                meter_ids.update(m.meter_id for m in ds.meters)
            if a.valid_from and a.valid_from < date_min:
                date_min = a.valid_from
            if a.valid_to and a.valid_to > date_max:
                date_max = a.valid_to
        hints = {
            "meters": meter_ids,
            "buildings": building_ids,
            "date_range": None,
        }

    return bands, hints


def _filter_ann_bands(
    ann_bands: pd.DataFrame | None,
    data_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    meter_ids: set[str] | None = None,
    ds: Dataset | None = None,
) -> pd.DataFrame | None:
    """Filter annotation bands by date range and selected meters/buildings."""
    if ann_bands is None or ann_bands.empty:
        return None
    filtered = ann_bands.copy()
    if data_range:
        filtered = filtered[
            (filtered["start"] >= data_range[0]) & (filtered["start"] <= data_range[1])
        ]
    if meter_ids and ds:
        meter_buildings = {m.meter_id: m.building_id for m in ds.meters}
        sel_buildings = {meter_buildings.get(m) for m in meter_ids} - {None}
        keep = []
        for _, row in filtered.iterrows():
            ann = next((a for a in ds.annotations if a.annotation_id == row["label"]), None)
            if ann is None:
                continue
            if ann.target_kind == "meter" and ann.target_id in meter_ids:
                keep.append(True)
            elif ann.target_kind == "building" and ann.target_id in sel_buildings:
                keep.append(True)
            elif ann.target_kind == "campus":
                keep.append(True)
            else:
                keep.append(False)
        filtered = filtered[keep] if keep else filtered.iloc[0:0]
    return filtered if not filtered.empty else None


def _inject_ann_bands(chart: alt.Chart, ann_bands: pd.DataFrame | None) -> alt.Chart:
    """Add annotation highlight bands to an existing chart without stretching the axis."""
    if ann_bands is None or ann_bands.empty:
        return chart
    rules = []
    for _, row in ann_bands.iterrows():
        desc = row.get("description", "")
        rules.append({"timestamp": row["start"], "category": row["category"], "label": row["label"], "description": desc, "edge": "start"})
        if row["end"] != row["start"]:
            rules.append({"timestamp": row["end"], "category": row["category"], "label": row["label"], "description": desc, "edge": "end"})
    rules_df = pd.DataFrame(rules)
    if rules_df.empty:
        return chart
    rule_layer = (
        alt.Chart(rules_df)
        .mark_rule(strokeDash=[4, 4], strokeWidth=3, opacity=0.7)
        .encode(
            x=alt.X("timestamp:T"),
            color=alt.Color("category:N", scale=alt.Scale(
                domain=list(_ANNOTATION_COLORS.keys()),
                range=list(_ANNOTATION_COLORS.values()),
            ), legend=None),
            tooltip=["label", "description", "category", "edge"],
        )
    )
    starts = rules_df[rules_df["edge"] == "start"]
    text_layer = (
        alt.Chart(starts)
        .mark_text(align="left", dx=4, dy=0, fontSize=10, fontWeight="bold", opacity=0.8, baseline="top", angle=270)
        .encode(
            x="timestamp:T",
            text="label:N",
            color=alt.Color("category:N", scale=alt.Scale(
                domain=list(_ANNOTATION_COLORS.keys()),
                range=list(_ANNOTATION_COLORS.values()),
            ), legend=None),
            tooltip=["label", "description", "category"],
        )
    )
    return alt.layer(chart, rule_layer, text_layer).resolve_scale(color="independent")


def _excel_comparison_section(ds: Dataset, site_dir: Path) -> None:
    alloc_path = site_dir / "meter_allocations.csv"
    if not alloc_path.exists():
        st.info("No meter_allocations.csv — Excel comparison not available.")
        return

    import csv as _csv
    with alloc_path.open() as f:
        alloc_rows = list(_csv.DictReader(f))

    formulas: dict[str, dict[str, list[str]]] = {}
    for row in alloc_rows:
        bid = row["building_id"]
        formulas.setdefault(bid, {"add": [], "sub": []})
        if row["sign"] == "+":
            formulas[bid]["add"].append(row["meter_id"])
        else:
            formulas[bid]["sub"].append(row["meter_id"])

    conn = calc.connect(ds)
    mf = conn.execute("SELECT meter_id, timestamp, delta_kwh FROM measured_flow").fetchdf()
    mf["timestamp"] = pd.to_datetime(mf["timestamp"])
    mf["month"] = mf["timestamp"].dt.to_period("M")
    monthly = mf.groupby(["meter_id", "month"])["delta_kwh"].sum().reset_index()

    consumption = conn.execute(calc.sql("consumption")).fetchdf()
    consumption["timestamp"] = pd.to_datetime(consumption["timestamp"])
    consumption["month"] = consumption["timestamp"].dt.to_period("M")
    onto = consumption[consumption["level"] == "building"].groupby(
        ["target_id", "month"]
    )["net_kwh"].sum().reset_index()

    months = sorted(monthly["month"].unique())
    if len(months) < 2:
        st.info("Need at least 2 months of data for comparison.")
        return
    compare_months = months[:2]

    rows = []
    for bid in sorted(formulas):
        row: dict[str, object] = {"building": bid}
        for m in compare_months:
            excel_val = 0.0
            for mid in formulas[bid]["add"]:
                v = monthly[(monthly.meter_id == mid) & (monthly.month == m)]["delta_kwh"].sum()
                excel_val += v
            for mid in formulas[bid]["sub"]:
                v = monthly[(monthly.meter_id == mid) & (monthly.month == m)]["delta_kwh"].sum()
                excel_val -= v
            onto_val = onto[(onto.target_id == bid) & (onto.month == m)]["net_kwh"].sum()
            row[f"excel_{m}"] = round(excel_val, 1)
            row[f"onto_{m}"] = round(onto_val, 1)
            row[f"diff_{m}"] = round(onto_val - excel_val, 1)
        rows.append(row)

    cdf = pd.DataFrame(rows)
    for m in compare_months:
        cdf[f"diff%_{m}"] = cdf.apply(
            lambda r: round(r[f"diff_{m}"] / r[f"excel_{m}"] * 100, 1)
            if r[f"excel_{m}"] != 0 else None, axis=1,
        )

    unit = _unit_label(ds)
    st.caption(f"Monthly building consumption ({unit}): ontology vs Excel ({compare_months[0]} / {compare_months[1]})")
    st.dataframe(cdf, hide_index=True, width="stretch")


def _tests_section() -> None:
    if st.button("Re-run tests", help="Clear cache and re-run pytest"):
        _run_pytest.clear()

    with st.spinner("Running pytest..."):
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
    df["status"] = df["outcome"].map({"passed": "pass", "failed": "FAIL", "skipped": "skip"})

    table = df[["status", "package", "test", "explains", "duration"]].rename(
        columns={"duration": "s"}
    )
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        height=36 * (len(table) + 1) + 2,
    )


def _package_of(nodeid: str) -> str:
    parts = nodeid.split("/")
    if len(parts) >= 2 and parts[0] == "packages":
        return parts[1]
    return parts[0] if parts else "(root)"


@st.cache_data(show_spinner=False)
def _collect_docstrings(repo_root: Path) -> dict[str, str]:
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
