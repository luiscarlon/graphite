"""Workstream status board.

Hardcoded per (site_id, media_id) status chip and comment. Single
source of truth for:

- the banner rendered at the top of the main page when a site + media
  are selected (see `app.main`); and
- the `pages/1_Work_status.py` page that lists the whole board.

Edit entries here as the workstreams progress. Status is one of
"green" | "yellow" | "orange" | "red"; anything else (or a missing
entry) renders nothing.
"""

from __future__ import annotations

import streamlit as st

STATUS_BOARD: dict[tuple[str, str], tuple[str, str]] = {
    ("gartuna", "ANGA"): (
        "yellow",
        "Ontology matches Excel at the monthly level, but ~31 percent of "
        "site steam intake isn't captured by downstream meters (60 "
        "percent gap on the north spine alone). Needs on-site "
        "verification of suspected unmetered or undocumented branches; "
        "details in annotations.",
    ),
    ("gartuna", "EL"): (
        "yellow",
        "Ontology matches Excel at the monthly level modulo sub-kWh "
        "rounding drifts, plus ~9 percent of campus intake unaccounted "
        "by any building meter and a couple of small Excel-side formula "
        "bugs. Open items need Excel-side cleanup; details in "
        "annotations.",
    ),
    ("gartuna", "KALLVATTEN"): (
        "green",
        "Ontology matches Excel at the monthly level. The B600 intake "
        "and B921 avräkning rows are routed through dedicated virtuals "
        "by design.",
    ),
    ("gartuna", "KYLA"): (
        "yellow",
        "Ontology matches Excel at the monthly level. Two known Excel-"
        "side issues remain (stale STRUX cache on B658 and a double-"
        "count on B623); both need Excel workbook fixes rather than "
        "ontology changes.",
    ),
    ("gartuna", "KYLTORNSVATTEN"): (
        "green",
        "Ontology matches Excel at the monthly level. The bi-daily "
        "B614-V2-GF4 reporting cadence is unconfirmed (sensor sampling "
        "versus physical duty-cycling) but doesn't affect monthly totals.",
    ),
    ("gartuna", "VARME"): (
        "green",
        "Ontology matches Excel at the monthly level after the major "
        "data-quality events were patched. Structural caveat: B621 has "
        "~91 percent of intake unaccounted by downstream meters, "
        "suggesting unmetered branches that need on-site verification.",
    ),
    ("snackviken", "ANGA"): (
        "yellow",
        "B217.Å1_VMM71 register-corruption window patched via "
        "slice+interpolate+slice. Persistent negative residuals on the B310 "
        "pool are an Excel accounting design, not an ontology error. "
        "B307.Å1_VMM71 trunk counter frozen Jan–Oct 2025 then ticks normally; "
        "post-unfreeze totals lag Excel by ~3 months — both annotated, not "
        "patched.",
    ),
    ("snackviken", "EL"): (
        "red",
        "Raw readings look clean, but the Excel workbook and the topology "
        "derived from it are arbitrary and partly cooked: heavy reliance on "
        "STRUX-only trunk meters (B209/B304/B313/B334) that have no BMS "
        "equivalent, literal placeholder strings (‘Reservkraft pl7’) in "
        "formula slots, typo'd meter IDs, and fractional-split coefficients "
        "(R-factors) that the workbook applies to whole net formulas "
        "rather than individual terms. Ontology mirrors the Excel shape "
        "faithfully, but neither side is a reliable ground truth on its own.",
    ),
    ("snackviken", "KALLVATTEN"): (
        "yellow",
        "Raw readings look good. A few Excel-side bugs (formula structure "
        "and +/− term handling) produce small per-building discrepancies; "
        "ontology matches within noise once those are accounted for.",
    ),
    ("snackviken", "KYLA"): (
        "green",
        "Ontology matches Excel. Some fractional-split coefficients "
        "(feeds edges with k<1 into KYLA virtuals) are still suspicious "
        "and worth a second pass — the math works out but the physical "
        "justification is thin.",
    ),
    ("snackviken", "SJOVATTEN"): (
        "yellow",
        "Ontology looks reasonable. Certain buildings show negative net in "
        "specific windows when the parent trunk's reading drops below its "
        "childrens' sum. Remaining −100% rows in the Excel comparison are "
        "on STRUX-only manual-entry meters (BScania, BKringlan, B304) and "
        "the BPS_V2 fractional pool — accepted at this stage.",
    ),
    ("snackviken", "VARME"): (
        "yellow",
        "Ontology looks good with a minor Excel-side bug still to chase. "
        "B310/B311/B313 synchronized 117-day offline patched via "
        "interpolate; B310 Jan 2026 net negative is expected (distribution "
        "pool). A few building-level totals remain distorted by outage "
        "windows that aren't fully reconstructable from sub-meters.",
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
