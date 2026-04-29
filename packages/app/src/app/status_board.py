"""Workstream status board.

Hardcoded per (site_id, media_id) status chip and comment. Single
source of truth for:

- the banner rendered at the top of the main page when a site + media
  are selected (see `app.main`); and
- the `pages/1_Work_status.py` page that lists the whole board.

Each entry's text describes the open items remaining for that
workstream.

Edit entries here as the workstreams progress. Status is one of
"green" | "yellow" | "orange" | "red"; anything else (or a missing
entry) renders nothing.
"""

from __future__ import annotations

import streamlit as st

STATUS_BOARD: dict[tuple[str, str], tuple[str, str]] = {
    ("gartuna", "ANGA"): (
        "yellow",
        "B616 excel_stale: meter is live (~900 MWh/month) but Excel "
        "attributes 0 — Excel-side cleanup. Investigation of any "
        "remaining campus-vs-buildings gap (B600.ANGA_INTAKE virtual "
        "currently sums to a small negative residual that may indicate "
        "missing sub-meters or a counter-direction issue).",
    ),
    ("gartuna", "EL"): (
        "yellow",
        "(1) Excel-side cleanup of three small formula bugs (B664/B665 "
        "missed T42-2-1, B612 double-subtracts T8-A3-A14-112). (2) "
        "Either accept the ~9 percent campus intake unaccounted as "
        "typical industrial-park unmetered (lighting, signage, "
        "controls, transformer losses) or sweep BMS for unmodelled "
        "meters and ingest the safe ones.",
    ),
    ("gartuna", "KALLVATTEN"): (
        "green",
        "No open items. B600 substation intake virtual and B921 "
        "avräkning aggregator are intentional design choices reflecting "
        "Telge Nät's billing structure.",
    ),
    ("gartuna", "KYLA"): (
        "yellow",
        "(1) Excel-side fixes: refresh stale STRUX cache on B658 "
        "(attributes 0 but meter is live) and resolve the B623 "
        "double-count (appears as +term for B623 AND inside the "
        "B600-KB2 pool formula). (2) Investigate B621 and B622 "
        "Feb 2026 ontology_drift (uncategorized). (3) B611 negative "
        "data_quality_artifact: B653 pool meter died 2025-10-09; "
        "consider retiring the dead pool relation. The B641/B833 Feb "
        "trailing_day_gaps will resolve on next March 2026 raw "
        "reading.",
    ),
    ("gartuna", "KYLTORNSVATTEN"): (
        "green",
        "Investigate whether B614-V2-GF4's bi-daily reporting cadence "
        "is sensor sampling or physical duty-cycling. Doesn't affect "
        "monthly totals.",
    ),
    ("gartuna", "VARME"): (
        "green",
        "Matches Excel on 95 of 96 building-month rows. The single "
        "non-match is B833 Feb 2026, where the ontology's outage patch "
        "(B833.VP1 frozen) captures ~23 MWh that Excel's frozen "
        "counter misses — Excel-side counter refresh would close it.",
    ),
    ("snackviken", "ANGA"): (
        "yellow",
        "(1) Excel-side fix for B307 double-subtract of B330.Å1_VMM71 "
        "(rows 23 and 46 both list it as a − term). (2) Decide on "
        "B216/B308 frozen-counter handling — current ontology patches "
        "from child meters; Excel STRUX register-diff treats the "
        "freeze as zero post-freeze. Alignment requires either an "
        "ontology mode mirroring STRUX or accepting the documented "
        "~30 MWh divergence. (3) Investigate B317 Jan 2026 −119 MWh "
        "(−79 percent) drift, currently uncategorized. B310 negative "
        "residuals stay as documented pool-accounting design.",
    ),
    ("snackviken", "EL"): (
        "yellow",
        "(1) Excel-side cleanup of 4 double-plus formulas (B305/B318/"
        "B344/B392 each duplicate the same +meter; ontology splits "
        "50/50 to avoid double-count). (2) Inject STRUX values for 3 "
        "absent summary meters (B313.T26S, T26S-3-12, T40-3-1) — "
        "closes B304/B310/B311 strux_only_meter rows. (3) Spot-check "
        "the B317 February +75 MWh divergence (Jan reproduces Excel "
        "exactly via BMS; Feb diverges with no obvious cause). "
        "Substation conservation residual 6.7 percent is typical "
        "industrial-park unmetered — accept as-is.",
    ),
    ("snackviken", "KALLVATTEN"): (
        "yellow",
        "Excel-side cleanup of 6 double-subtract bugs (B313/B315 "
        "listed in multiple pool formulas — workbook fixes, not "
        "ontology). The 4 catch-up-cluster rows on B313/B317/B389 Jan "
        "2026 are accepted patch behavior (interpolate spreads the "
        "Jan 14 flush back across the freeze window). TN-billing 3 "
        "percent reconciliation documented in ann-snv-kv-tn-billing-"
        "reconciliation.",
    ),
    ("snackviken", "KYLA"): (
        "green",
        "100 percent match (139/139 rows). KYLA is distributed "
        "chillers per building, no centralized intake; the conservation "
        "panel correctly skips KYLA by design. No open items.",
    ),
    ("snackviken", "SJOVATTEN"): (
        "yellow",
        "STRUX injection for 10 absent meters — 7 BPS_V2 drain meters "
        "needed to reproduce the BPS_V2 sheet residual from BMS "
        "(B342 inlets minus 15 direct consumers, of which 7 are "
        "STRUX-only) plus the 3 STRUX-only consumers (BScania, "
        "BKringlan, B304). Lake intake side already matches Excel "
        "exactly. The 0.09/0.18/0.18/0.46/0.09 BPS_V2 fractional split "
        "would route correctly via `feeds k<1.0` once BPS_V2 is "
        "computable.",
    ),
    ("snackviken", "VARME"): (
        "green",
        "Excel-side fix for B327 double-count of B326.VS1_VMM61 (rows "
        "37+38 both list it as +term — workbook cleanup). The catch-up-"
        "cluster meter_outage rows on B310/B311/B313 Jan 2026 are "
        "accepted patch behavior (interpolate intentionally distributes "
        "the Jan 14 flush for daily reporting at the cost of monthly "
        "totals).",
    ),
}

STATUS_STYLE: dict[str, tuple[str, str]] = {
    "green":  ("#d4edda", "#155724"),
    "yellow": ("#fff3cd", "#856404"),
    "orange": ("#ffe0b2", "#8a4500"),
    "red":    ("#f8d7da", "#721c24"),
}


def render_status_banner(site_id: str, media_id: str) -> None:
    """Render the (site, media) status chip above the Topology section."""
    entry = STATUS_BOARD.get((site_id, media_id))
    if entry is None:
        return
    status, comment = entry
    style = STATUS_STYLE.get(status)
    if style is None:
        return
    bg, fg = style
    st.markdown(
        f'<div style="padding: 0.6rem 0.9rem; margin: 0.4rem 0 1rem 0; '
        f'border-radius: 4px; background: {bg}; color: {fg}; '
        f'border-left: 4px solid {fg}; font-size: 0.92rem;">'
        f'<strong>{status.upper()}</strong> &nbsp; {comment}'
        f'</div>',
        unsafe_allow_html=True,
    )
