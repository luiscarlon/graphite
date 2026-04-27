"""Streamlit app entry point."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import json

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml

import calc
from app.graph import to_dot
from app.status_board import render_status_banner
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
    "rollover": "#b279a2",
}

# Status board moved to `app.status_board` — shared with the Work status
# page under `pages/`.


def _annotation_layer(
    ds: Dataset,
    meter_ids: set[str] | None,
    building_ids: set[str] | None,
    date_range: tuple[date, date] | None,
) -> alt.Chart | None:
    rows = []
    for a in ds.annotations:
        if a.valid_from is None or a.valid_to is None:
            # Annotation CSVs now always carry dates (1900-01-01 /
            # 9999-01-01 sentinels for open-ended windows). Anything
            # still None here is malformed data; skip defensively.
            continue
        if meter_ids is not None and a.target_kind == "meter" and a.target_id not in meter_ids:
            continue
        if building_ids is not None and a.target_kind == "building" and a.target_id not in building_ids:
            continue
        start = pd.Timestamp(a.valid_from)
        end = pd.Timestamp(a.valid_to)
        # Widen single-date events (e.g. rollovers) to 1 day so the
        # rect has visible width.
        if end == start:
            end = start + pd.Timedelta(days=1)
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
    "Kilowatt-Hour": "kWh",
    "Megawatt-Hour": "MWh",
    "M3": "m³",
}


def _unit_label(ds: Dataset) -> str:
    return _UNIT_SHORT.get(_detect_unit(ds), _detect_unit(ds))


def _readings_section(
    ds: Dataset,
    ann_bands: pd.DataFrame | None = None,
    ann_hints: dict | None = None,
) -> tuple[list[str], tuple[date, date]] | None:
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

    granularity = _detect_granularity(ds)
    unit = _unit_label(ds)
    rate_label = f"{unit}/{granularity}" if granularity != "unknown" else unit

    cols = st.columns([3, 2])
    with cols[0]:
        timeseries_ids = sorted(df["timeseries_id"].unique())
        # Annotation hints carry meter IDs (ontology layer); map them to
        # timeseries IDs so the "Isolate" toggle still works in the raw
        # readings view. No-op if no hints or no overlap.
        if ann_hints and ann_hints["meters"]:
            hinted = {sensor_meter[refs[t].sensor_id] for t in timeseries_ids}
            hinted_ts = sorted(
                t for t in timeseries_ids
                if sensor_meter[refs[t].sensor_id] in ann_hints["meters"]
            )
            default_ts = hinted_ts if hinted_ts else timeseries_ids
        else:
            default_ts = timeseries_ids
        sel_timeseries = st.multiselect(
            "Timeseries", timeseries_ids, default=default_ts,
            help="Raw counter and delta series. Ontology projections (building, meter, campus) are applied in the Consumption section.",
        )
    with cols[1]:
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

    # sel_meters is derived purely for downstream helpers that key off
    # meter (validity bands, annotation overlap) — it is NOT a user
    # filter on the readings view.
    sel_meters = sorted({sensor_meter[refs[t].sensor_id] for t in sel_timeseries})

    view = st.radio(
        "Counter view",
        ["cumulative (index)", f"rate ({rate_label})"],
        index=1,
        horizontal=True,
        help="Counters store the cumulative meter index. 'Rate' takes the per-step difference.",
    )

    df_sel = df[
        df["timeseries_id"].isin(sel_timeseries)
        & (df["timestamp"].dt.date >= date_range[0])
        & (df["timestamp"].dt.date <= date_range[1] + timedelta(days=1))
    ].copy()
    if df_sel.empty:
        st.warning("No readings for the current selection.")
        return sel_timeseries, date_range

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

        pick = alt.selection_point(fields=["timeseries_id"], name="picked", on="click")
        line = (
            alt.Chart(counters)
            .mark_line()
            .encode(
                x=alt.X("timestamp:T", title=None),
                y=alt.Y("value:Q", title=y_title),
                color=alt.Color("timeseries_id:N", title="Series"),
                opacity=alt.condition(pick, alt.value(1.0), alt.value(0.15)),
                tooltip=["timeseries_id", "timestamp", "value"],
            )
            .add_params(pick)
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
        chart = _inject_ann_bands(chart, filtered_bands).interactive()
        event = st.altair_chart(
            chart, width="stretch", on_select="rerun",
            selection_mode=["picked"], key="counter_chart",
        )
        picked_ts: list[str] = []
        if event and event.selection:
            for row in event.selection.get("picked", []):
                if ts := row.get("timeseries_id"):
                    picked_ts.append(ts)
        if picked_ts:
            st.caption(f"Filtered to: {', '.join(picked_ts)}")
            deltas = deltas[deltas["timeseries_id"].isin(picked_ts)]

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
            .interactive()
        )
        st.altair_chart(bars, width="stretch")

    return sel_timeseries, date_range


def _tables_section(ds: Dataset) -> None:
    meters = list(ds.meters)
    relations = list(ds.relations)
    zones = list(ds.zones)
    meter_measures = list(ds.meter_measures)
    media_types = ds.media_types
    buildings = list(ds.buildings)
    sensors = list(ds.sensors)
    timeseries_refs = list(ds.timeseries_refs)
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
        ann_filter = st.selectbox(
            "Status",
            options=["All", "Resolved only", "Unresolved only"],
            index=0,
            key="tables_ann_resolved_filter",
        )
        if ann_filter == "Resolved only":
            ann_view = [a for a in annotations if a.is_resolved]
        elif ann_filter == "Unresolved only":
            ann_view = [a for a in annotations if not a.is_resolved]
        else:
            ann_view = list(annotations)
        st.dataframe([a.model_dump() for a in ann_view], width="stretch")
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


def _topology_chart(dot: str, height: int = 640) -> None:
    """Render a DOT graph with mouse-wheel zoom and drag-to-pan.

    Uses d3-graphviz in the browser (same WASM renderer Streamlit's
    built-in graphviz_chart uses) with d3-zoom layered on top.
    """
    dot_json = json.dumps(dot)
    html = f"""
<!doctype html>
<html>
<head>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script src="https://cdn.jsdelivr.net/npm/@hpcc-js/wasm@2.22.4/dist/graphviz.umd.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-graphviz@5.6.0/build/d3-graphviz.js"></script>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; background: #fff; }}
  #graph {{ width: 100%; height: {height}px; cursor: grab; }}
  #graph:active {{ cursor: grabbing; }}
  #graph svg {{ width: 100%; height: 100%; }}
  #reset {{
    position: absolute; top: 8px; right: 8px; z-index: 10;
    padding: 4px 10px; font: 12px Helvetica, sans-serif;
    background: #fff; border: 1px solid #ccc; border-radius: 4px;
    cursor: pointer;
  }}
  #reset:hover {{ background: #f0f0f0; }}
</style>
</head>
<body>
<button id="reset" title="Reset view">reset</button>
<div id="graph"></div>
<script>
  const dot = {dot_json};
  const gv = d3.select("#graph").graphviz().zoom(true).fit(true);
  gv.renderDot(dot);
  document.getElementById("reset").onclick = () => gv.resetZoom();
</script>
</body>
</html>
"""
    components.html(html, height=height + 20, scrolling=False)


def main() -> None:
    st.set_page_config(page_title="graphite", layout="wide")
    # Title updates dynamically once site + media are resolved below.
    title_slot = st.empty()

    if not SITES_ROOT.exists():
        st.error(f"No sites directory at `{SITES_ROOT}`.")
        return

    sites = sorted(p.name for p in SITES_ROOT.iterdir() if p.is_dir())
    if not sites:
        st.error("No sites found.")
        return

    default_site_idx = sites.index("gartuna") if "gartuna" in sites else 0
    selected_site = st.sidebar.selectbox("Site", sites, index=default_site_idx)
    site_dir = SITES_ROOT / selected_site
    site_meta = _load_site_meta(site_dir)

    ds_full = load_dataset(site_dir)

    available_media = sorted({m.media_type_id for m in ds_full.meters})
    if not available_media:
        st.warning("No meters found for this site.")
        return

    default_media_idx = available_media.index("ANGA") if "ANGA" in available_media else 0
    selected_media = st.sidebar.selectbox("Media", available_media, index=default_media_idx)
    ds = ds_full.filter_by_media(selected_media)

    site_label = site_meta.get("name", selected_site)
    title_slot.title(f"{site_label} — {selected_media}")
    render_status_banner(selected_site, selected_media)

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
    # Anchor date: topology reflects meters + relations valid at this date.
    # Default is today so the common "what's the wiring right now?" answer
    # is one click away; scrub backward to inspect historical structures
    # (e.g. the pre-July-2025 B614/B642 ÅNGA flip).
    topo_as_of = st.date_input(
        "Topology as of",
        value=date.today(),
        key="topology_as_of",
        help=(
            "Filters meters and relations by their [valid_from, valid_to) "
            "windows. Retired meters and inactive edges are hidden."
        ),
    )
    _topology_chart(to_dot(ds, as_of=topo_as_of))

    ann_bands = None
    ann_hints = None
    if ds.annotations:
        with st.expander(f"Annotations ({len(ds.annotations)})", expanded=False):
            ann_bands, ann_hints = _annotations_picker(ds)

    st.subheader("Readings")
    selection = _readings_section(ds, ann_bands, ann_hints)

    with st.expander("Tables"):
        _tables_section(ds)

    st.subheader("Consumption")
    _consumption_section(ds, selection, ann_bands)

    if any(mm.target_kind == "campus" for mm in ds.meter_measures):
        st.subheader("Campus conservation")
        _conservation_section(ds, selection)

    st.subheader("Excel comparison")
    _excel_comparison_section(ds, site_dir)


def _conservation_section(
    ds: Dataset,
    selection: tuple[list[str], tuple[date, date]] | None,
) -> None:
    """Trend campus master reading vs Σ building meters per medium.

    Renders one chart per media that has at least one campus-targeted
    meter. The "campus" line is the full draw measured at the campus
    scope (sum of `meter_flow` over campus-targeted meters); the
    "buildings" line is Σ `meter_net` over building-targeted meters in
    the same campus. Their gap is the unmetered residual (substation
    ancillaries, line losses, anything not captured by a building meter).
    """
    conn = calc.connect(ds)
    media_with_campus = sorted({
        m.media_type_id for m in ds.meters
        if any(mm.target_kind == "campus" and mm.meter_id == m.meter_id
               for mm in ds.meter_measures)
    })
    if not media_with_campus:
        st.info("No campus-targeted meters in the ontology.")
        return

    date_range = selection[1] if selection else None

    media_pick = st.radio(
        "Media", media_with_campus, index=0, horizontal=True,
        key="conservation_media",
    )

    # Campus-scope draw: meter_flow over the *top* campus-targeted
    # meters — those with no incoming relation, i.e. real intake roots.
    # Excludes virtual aggregators (which have incoming feeds from the
    # physical intake meters) and sub-feeders captured at campus scope
    # (which have incoming hasSubMeter from a building-level parent).
    # Without this filter, EL would triple-count (H23-1 + H3-1 + EL_INTAKE).
    campus_df = conn.execute("""
        SELECT mf.timestamp::DATE AS day, SUM(mf.delta_kwh) AS kwh
        FROM meter_flow mf
        JOIN meter_measures mm ON mm.meter_id = mf.meter_id AND mm.target_kind='campus'
        JOIN meters m ON m.meter_id = mf.meter_id
        WHERE m.media_type_id = ?
          AND NOT EXISTS (
              SELECT 1 FROM meter_relations r WHERE r.child_meter_id = mf.meter_id
          )
        GROUP BY 1 ORDER BY 1
    """, [media_pick]).fetchdf()

    # Σ buildings: meter_net over building-targeted meters in the campus.
    bldg_df = conn.execute("""
        SELECT mn.timestamp::DATE AS day, SUM(mn.net_kwh) AS kwh
        FROM meter_net mn
        JOIN meter_measures mm ON mm.meter_id = mn.meter_id AND mm.target_kind='building'
        JOIN meters m ON m.meter_id = mn.meter_id
        WHERE m.media_type_id = ?
        GROUP BY 1 ORDER BY 1
    """, [media_pick]).fetchdf()

    if campus_df.empty and bldg_df.empty:
        st.info(f"No data for {media_pick}.")
        return

    campus_df["day"] = pd.to_datetime(campus_df["day"])
    bldg_df["day"] = pd.to_datetime(bldg_df["day"])

    if date_range:
        campus_df = campus_df[
            (campus_df.day.dt.date >= date_range[0]) & (campus_df.day.dt.date <= date_range[1])
        ]
        bldg_df = bldg_df[
            (bldg_df.day.dt.date >= date_range[0]) & (bldg_df.day.dt.date <= date_range[1])
        ]

    cd = campus_df.assign(series="campus")
    bd = bldg_df.assign(series="Σ buildings")
    plot_df = pd.concat([cd, bd], ignore_index=True)
    if plot_df.empty:
        st.info(f"No {media_pick} data in selected date range.")
        return

    chart = (
        alt.Chart(plot_df)
        .mark_line()
        .encode(
            x=alt.X("day:T", title=None),
            y=alt.Y("kwh:Q", title=f"{media_pick} ({_unit_label(ds)}/day)"),
            color=alt.Color("series:N", title=None),
            tooltip=["day:T", "series:N", alt.Tooltip("kwh:Q", format=",.0f")],
        )
        .properties(height=280)
        .interactive()
    )
    st.altair_chart(chart, width="stretch")

    # Monthly residual summary (daily would be hundreds of rows).
    plot_df["month"] = plot_df["day"].dt.to_period("M").dt.to_timestamp()
    pivot = plot_df.groupby(["month", "series"], as_index=False)["kwh"].sum()
    pivot = pivot.pivot(index="month", columns="series", values="kwh").fillna(0)
    pivot["residual"] = pivot.get("campus", 0) - pivot.get("Σ buildings", 0)
    pivot["residual_pct"] = pivot.apply(
        lambda r: 100 * r["residual"] / r["campus"] if r.get("campus") else float("nan"),
        axis=1,
    )
    pivot = pivot.reset_index()
    pivot["month"] = pivot["month"].dt.strftime("%Y-%m")
    cols_order = ["month", "campus", "Σ buildings", "residual", "residual_pct"]
    pivot = pivot[[c for c in cols_order if c in pivot.columns]]
    st.dataframe(
        pivot.style.format({
            "campus": "{:,.0f}",
            "Σ buildings": "{:,.0f}",
            "residual": "{:,.0f}",
            "residual_pct": "{:.1f}%",
        }, na_rep="—"),
        hide_index=True, width="stretch",
    )


def _consumption_targets(ds: Dataset, level: str) -> tuple[list[str], list[str]]:
    """Return (options, default) for the consumption-section target picker.

    Each level reads from the ontology — not the readings — so virtual
    meters and campus-level intake aggregators appear without needing
    raw timeseries.
    """
    if level == "campus":
        ids = sorted(c.campus_id for c in ds.campuses)
    elif level == "building":
        ids = sorted(b.building_id for b in ds.buildings)
    elif level == "zone":
        ids = sorted(z.zone_id for z in ds.zones)
    elif level in ("meter", "series"):
        ids = sorted(m.meter_id for m in ds.meters)
    else:
        ids = []
    return ids, ids


def _consumption_section(
    ds: Dataset,
    selection: tuple[list[str], tuple[date, date]] | None,
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

    # Series view: raw measured flow (real meters only, LAG diff of
    # preferred counter timeseries). Virtuals don't appear here.
    series_df = conn.execute(
        "SELECT meter_id, timestamp, delta_kwh FROM measured_flow"
    ).fetchdf()
    series_df["timestamp"] = pd.to_datetime(series_df["timestamp"])

    # Meter view: synthesized flow including virtuals (EL_INTAKE etc.)
    # via the recursive feeds-aware meter_flow view.
    meter_df = conn.execute(
        "SELECT meter_id, timestamp, delta_kwh FROM meter_flow"
    ).fetchdf()
    meter_df["timestamp"] = pd.to_datetime(meter_df["timestamp"])

    levels = sorted(df["level"].unique()) if not df.empty else []
    all_levels = ["series", "meter"] + levels

    # Ontology-sourced filter row. Each level draws its target list
    # straight from the ontology (not from readings), so virtual meters
    # like B660.EL_INTAKE appear under campus alongside real intake
    # meters. Future ontology classes (zone, equipment, system) drop in
    # here as additional levels.
    fcols = st.columns([1, 4])
    with fcols[0]:
        level = st.radio("Group by", all_levels, index=0, horizontal=False)
    with fcols[1]:
        target_options, target_default = _consumption_targets(ds, level)
        sel_targets = st.multiselect(
            level.capitalize(), target_options, default=target_default,
            help="Filter the chart to these targets. Sourced from the ontology — virtuals included.",
        )

    date_range = selection[1] if selection else None

    if level in ("series", "meter"):
        scoped = (series_df if level == "series" else meter_df).copy()
        if sel_targets:
            scoped = scoped[scoped["meter_id"].isin(sel_targets)]
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
        if sel_targets:
            scoped = scoped[scoped["target_id"].isin(sel_targets)]
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
    field = "meter_id" if level == "series" else "target_id"
    pick = alt.selection_point(fields=[field], name="picked", on="click")
    chart = (
        alt.Chart(scoped)
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y(chart_y, title=y_title),
            color=alt.Color(chart_color, title=level),
            opacity=alt.condition(pick, alt.value(1.0), alt.value(0.15)),
            tooltip=chart_tooltip,
        )
        .add_params(pick)
        .properties(height=360)
    )
    cons_dr = (scoped["timestamp"].min(), scoped["timestamp"].max()) if not scoped.empty else None
    filtered_bands = _filter_ann_bands(ann_bands, data_range=cons_dr)
    chart = _inject_ann_bands(chart, filtered_bands).interactive()

    with cols[1]:
        event = st.altair_chart(
            chart, width="stretch", on_select="rerun",
            selection_mode=["picked"], key="consumption_chart",
        )

    picked_ids: list[str] = []
    if event and event.selection:
        for row in event.selection.get("picked", []):
            if v := row.get(field):
                picked_ids.append(v)

    totals_view = totals[totals["target_id"].isin(picked_ids)] if picked_ids else totals

    with cols[0]:
        st.caption(f"Total ({unit}, selected period)")
        if picked_ids:
            st.caption(f"Filtered: {', '.join(picked_ids)}")
        st.dataframe(
            totals_view.assign(net_kwh=totals_view["net_kwh"].round(0)),
            hide_index=True,
            width="stretch",
            height=min(36 * (len(totals_view) + 1) + 2, 400),
        )


def _annotations_picker(ds: Dataset) -> tuple[pd.DataFrame | None, dict | None]:
    """Returns (bands_df, filter_hints) where filter_hints has meters, buildings, date_range."""
    cols = st.columns([1, 1, 1])
    with cols[0]:
        select_all = st.checkbox("Select all", key="ann_select_all")
    with cols[1]:
        isolate = st.checkbox("Isolate selection", key="ann_isolate",
                              help="Filter readings and consumption to only show data relevant to selected annotations")
    with cols[2]:
        resolved_filter = st.selectbox(
            "Status",
            options=["All", "Resolved only", "Unresolved only"],
            index=0,
            key="ann_resolved_filter",
            help="Filter annotations by is_resolved flag",
        )
    ann_list = list(ds.annotations)
    if resolved_filter == "Resolved only":
        ann_list = [a for a in ann_list if a.is_resolved]
    elif resolved_filter == "Unresolved only":
        ann_list = [a for a in ann_list if not a.is_resolved]
    if not ann_list:
        st.info("No annotations match the current filter.")
        return None, None
    adf = pd.DataFrame([a.model_dump() for a in ann_list])
    adf["_orig_index"] = [ds.annotations.index(a) for a in ann_list]
    adf["select"] = select_all
    adf["patched"] = adf["related_refs"].apply(lambda r: "yes" if r else "no")
    display_cols = ["select", "annotation_id", "description", "patched", "is_resolved",
                    "category", "target_kind", "target_id", "valid_from", "valid_to"]
    edited = st.data_editor(
        adf[display_cols],
        hide_index=True,
        width="stretch",
        column_config={
            "select": st.column_config.CheckboxColumn("", default=False, width="small"),
            "is_resolved": st.column_config.CheckboxColumn("resolved", width="small", disabled=True),
        },
        key="ann_editor",
    )

    selected = edited[edited["select"] == True]  # noqa: E712
    if selected.empty:
        return None, None

    orig_indices = adf.loc[selected.index, "_orig_index"].tolist()
    sel_annotations = [ds.annotations[i] for i in orig_indices]
    rows = []
    for a in sel_annotations:
        # Annotation CSVs store sentinels (1900-01-01 / 9999-01-01)
        # for open-ended windows, so valid_from/valid_to are never None
        # by convention — but guard defensively.
        if a.valid_from is None or a.valid_to is None:
            continue
        start = pd.Timestamp(a.valid_from)
        end = pd.Timestamp(a.valid_to)
        # Single-date annotations (start == end, e.g. rollover events)
        # would otherwise render as a single zero-width rule that's
        # easy to miss. Widen to a 1-day band so both start and end
        # rules are drawn and the event is visible.
        if end == start:
            end = start + pd.Timedelta(days=1)
        rows.append({
            "start": start,
            "end": end,
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
                if m is not None:
                    # Campus-level meters (building_id is None) are
                    # rendered under the synthetic "(campus)" bucket in
                    # the reading view — isolate must include that
                    # bucket so the meter survives the building filter.
                    building_ids.add(m.building_id or "(campus)")
            elif a.target_kind == "building":
                building_ids.add(a.target_id)
                meter_ids.update(m.meter_id for m in ds.meters if m.building_id == a.target_id)
            elif a.target_kind == "campus":
                building_ids.update(b.building_id for b in ds.buildings)
                building_ids.add("(campus)")
                meter_ids.update(m.meter_id for m in ds.meters)
            elif a.target_kind == "timeseries":
                # Resolve the targeted ref back to its meter via sensor,
                # then to the meter's building bucket.
                sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
                ref = next(
                    (tr for tr in ds.timeseries_refs if tr.timeseries_id == a.target_id),
                    None,
                )
                if ref is not None:
                    mid = sensor_meter.get(ref.sensor_id)
                    if mid is not None:
                        meter_ids.add(mid)
                        m = next((m for m in ds.meters if m.meter_id == mid), None)
                        if m is not None:
                            building_ids.add(m.building_id or "(campus)")
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
    totals_path = site_dir / "excel_building_totals.csv"
    if not totals_path.exists():
        st.info("No excel_building_totals.csv — Excel comparison not available.")
        return

    media_ids = {m.media_type_id for m in ds.meters}
    if len(media_ids) != 1:
        st.info("Excel comparison requires a single media filter.")
        return
    media = next(iter(media_ids))

    excel_df = pd.read_csv(totals_path)
    excel_df = excel_df[excel_df["media"] == media].copy()
    excel_df["excel"] = pd.to_numeric(excel_df["excel_mwh"], errors="coerce").fillna(0.0)
    excel_df["month"] = pd.PeriodIndex(excel_df["month"], freq="M")
    excel_df = excel_df.rename(columns={"building_id": "building"})[
        ["building", "month", "excel"]
    ]

    conn = calc.connect(ds)
    mn = conn.execute(
        "SELECT mn.meter_id, mn.timestamp, mn.net_kwh, m.building_id "
        "FROM meter_net mn "
        "JOIN meters m ON m.meter_id = mn.meter_id "
        "WHERE m.building_id IS NOT NULL AND m.building_id != ''"
    ).fetchdf()
    mn["timestamp"] = pd.to_datetime(mn["timestamp"])
    mn["month"] = mn["timestamp"].dt.to_period("M")
    onto_df = (
        mn.groupby(["building_id", "month"])["net_kwh"]
        .sum()
        .reset_index()
        .rename(columns={"building_id": "building", "net_kwh": "onto"})
    )

    compare_months = [pd.Period("2026-01", freq="M"), pd.Period("2026-02", freq="M")]

    ex = excel_df[excel_df["month"].isin(compare_months)]
    on = onto_df[onto_df["month"].isin(compare_months)]
    merged = ex.merge(on, on=["building", "month"], how="outer").fillna(0.0)

    ann_path = site_dir / "excel_comparison_annotations.csv"
    ann_lookup: dict[tuple[str, str], dict[str, str]] = {}
    if ann_path.exists():
        # keep_default_na=False so empty cells read as "" not NaN; otherwise
        # str(NaN) == "nan" leaks into the rendered table.
        ann_df = pd.read_csv(ann_path, keep_default_na=False, na_filter=False)
        ann_df = ann_df[ann_df["media"] == media]
        for _, ar in ann_df.iterrows():
            ann_lookup[(str(ar["building_id"]), str(ar["month"]))] = {
                "reason": str(ar.get("reason", "")),
                "explanation": str(ar.get("explanation", "")),
            }

    rows: list[dict[str, object]] = []
    for bid, grp in merged.groupby("building"):
        row: dict[str, object] = {"building": bid}
        has_activity = False
        abs_diff_total = 0.0
        for m in compare_months:
            sel = grp[grp["month"] == m]
            ex_val = float(sel["excel"].sum())
            on_val = float(sel["onto"].sum())
            if ex_val != 0.0 or on_val != 0.0:
                has_activity = True
            diff = on_val - ex_val
            abs_diff_total += abs(diff)
            row[f"excel_{m}"] = round(ex_val, 2)
            row[f"onto_{m}"] = round(on_val, 2)
            if ex_val != 0:
                row[f"diff%_{m}"] = f"{(diff / ex_val * 100):.2f}%"
            else:
                row[f"diff%_{m}"] = ""
            ann = ann_lookup.get((bid, str(m)), {})
            row[f"reason_{m}"] = ann.get("reason", "") or ""
            row[f"explanation_{m}"] = ann.get("explanation", "") or ""
        # Combined |diff| across both months — sortable column for spotting
        # big discrepancies (signed-diff sums can cancel +/- across months).
        row["|Δ|_total"] = round(abs_diff_total, 2)
        if has_activity:
            rows.append(row)
    # Column order: building, per-month (excel, onto, diff%, reason, explanation),
    # then the absolute-diff total last so the sort handle is rightmost.
    col_order = ["building"]
    for m in compare_months:
        col_order += [f"excel_{m}", f"onto_{m}", f"diff%_{m}",
                       f"reason_{m}", f"explanation_{m}"]
    col_order += ["|Δ|_total"]
    # Sort by absolute total diff descending so biggest discrepancies are
    # on top; break ties by building id.
    cdf = pd.DataFrame(
        sorted(rows, key=lambda r: (-float(r["|Δ|_total"]), r["building"]))
    )[col_order]

    unit = _unit_label(ds)
    st.caption(
        f"Monthly building consumption ({unit}) — {media}: ontology vs cached Excel "
        f"({compare_months[0]} / {compare_months[1]})"
    )
    st.dataframe(cdf, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
