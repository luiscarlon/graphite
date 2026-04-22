"""Work status page — overview of every (site, media) workstream."""

from __future__ import annotations

import streamlit as st

from app.status_board import STATUS_BOARD, STATUS_STYLE

# The file is named `1_Work_status.py` so Streamlit orders it first in
# the sidebar. The display title is set here.
st.set_page_config(page_title="Work status", layout="wide")
st.title("Work status")
st.caption(
    "Per-workstream status board. Each row is one (site, media) "
    "combination; the same status chip is mirrored at the top of the "
    "corresponding main-page view."
)

# Group by site, then render one labelled card per media.
by_site: dict[str, list[tuple[str, str, str]]] = {}
for (site_id, media_id), (status, comment) in STATUS_BOARD.items():
    by_site.setdefault(site_id, []).append((media_id, status, comment))

for site_id in sorted(by_site):
    st.header(site_id)
    rows = sorted(by_site[site_id], key=lambda r: r[0])
    for media_id, status, comment in rows:
        style = STATUS_STYLE.get(status)
        if style is None:
            continue
        bg, fg = style
        st.markdown(
            f'<div style="padding: 0.6rem 0.9rem; margin: 0.3rem 0 0.6rem 0; '
            f'border-radius: 4px; background: {bg}; color: {fg}; '
            f'border-left: 4px solid {fg}; font-size: 0.92rem;">'
            f'<strong>{media_id}</strong> &nbsp; '
            f'<span style="text-transform: uppercase; font-size: 0.8rem; '
            f'letter-spacing: 0.05em; opacity: 0.85;">[{status}]</span>'
            f'<br><span style="opacity: 0.95;">{comment}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
