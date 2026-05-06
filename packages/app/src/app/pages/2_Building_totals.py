"""Building totals 2025 — one row per building × site, one column per media."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import calc
from ontology import load_dataset

REPO_ROOT = Path(__file__).resolve().parents[5]
SITES_ROOT = REPO_ROOT / "data" / "sites"


@st.cache_data(show_spinner="Computing 2025 totals...")
def _build_totals() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for site_dir in sorted(p for p in SITES_ROOT.iterdir() if p.is_dir()):
        site = site_dir.name
        ds = load_dataset(site_dir)
        if not ds.meters:
            continue

        # A (building, media) cell is "valid" only when there's at least one
        # building-targeted meter for that pair. Otherwise leave it blank —
        # the building genuinely has no metering for that medium, which is
        # different from "has metering but consumption summed to 0".
        meter_media = {m.meter_id: m.media_type_id for m in ds.meters}
        valid: set[tuple[str, str]] = {
            (mm.target_id, meter_media[mm.meter_id])
            for mm in ds.meter_measures
            if mm.target_kind == "building" and mm.meter_id in meter_media
        }

        conn = calc.connect(ds)
        df = conn.execute("""
            SELECT mm.target_id AS building, m.media_type_id AS media,
                   SUM(mn.net_kwh) AS total
            FROM meter_net mn
            JOIN meter_measures mm
              ON mm.meter_id = mn.meter_id AND mm.target_kind = 'building'
            JOIN meters m ON m.meter_id = mn.meter_id
            WHERE mn.timestamp >= '2025-01-01' AND mn.timestamp < '2026-01-01'
            GROUP BY mm.target_id, m.media_type_id
        """).fetchdf()
        df["site"] = site

        # Pivot to one column per media.
        pv = (
            df.pivot_table(index=["building", "site"], columns="media",
                           values="total", aggfunc="sum")
            .reset_index()
        )

        # Add buildings that have meters but no readings for any media in 2025
        # so they still get a row (with 0s on their valid cells).
        all_buildings = sorted({m.building_id for m in ds.meters if m.building_id})
        missing = [b for b in all_buildings if b not in set(pv["building"])]
        if missing:
            pv = pd.concat(
                [pv, pd.DataFrame({"building": missing, "site": site})],
                ignore_index=True,
            )

        # Mask: blank if (building, media) not valid; 0 if valid but no readings.
        media_cols = [c for c in pv.columns if c not in ("building", "site")]
        for col in media_cols:
            mask_invalid = ~pv["building"].map(lambda b, c=col: (b, c) in valid)
            mask_missing = pv[col].isna() & ~mask_invalid
            pv.loc[mask_invalid, col] = pd.NA
            pv.loc[mask_missing, col] = 0.0

        frames.append(pv)

    combined = pd.concat(frames, ignore_index=True)
    media_cols = sorted([c for c in combined.columns if c not in ("building", "site")])
    combined = combined[["building", "site", *media_cols]]
    return combined.sort_values(["site", "building"]).reset_index(drop=True)


st.set_page_config(page_title="Building totals 2025", layout="wide")
st.title("Building totals 2025")
st.caption(
    "One row per building. Cells show the building's 2025 net consumption "
    "for that medium (raw units per the sensor). "
    "🟥 blank = no metering · 🟨 0 = metered but reported zero · 🟩 has value."
)

df = _build_totals()
sites = sorted(df["site"].unique())
selected = st.sidebar.selectbox("Site", ["All", *sites], index=0)
if selected != "All":
    df = df[df["site"] == selected].reset_index(drop=True)

media_cols = [c for c in df.columns if c not in ("building", "site")]
fmt = {c: "{:,.0f}" for c in media_cols}


def _color(v: object) -> str:
    if pd.isna(v):
        return "background-color: #f8c5c5; color: black"
    if v == 0:
        return "background-color: #f6e7a3; color: black"
    return "background-color: #c5e8c5; color: black"


styler = df.style.format(fmt, na_rep="").map(_color, subset=media_cols)
st.dataframe(
    styler,
    hide_index=True,
    width="stretch",
    height=min(36 * (len(df) + 1) + 2, 800),
)
