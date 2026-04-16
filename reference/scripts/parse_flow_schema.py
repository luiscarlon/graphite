#!/usr/bin/env python3
"""Parse an AstraZeneca flödesschema PDF into meters.csv + relations.csv.

Takes a V###-##.#.8-*** flow-schema PDF (the detailed one with pipe routing,
not the .1 översiktsritning) and extracts:

- Meter list: every labeled `B### - Å1 V(M)M##` symbol.
- Meter-to-meter relations: parent/child derived from the pipe graph by BFS
  from user-supplied source meters.

Usage:
    python parse_flow_schema.py PDF --sources B600S.Å1_VMM71,B600N.Å1_VMM71 \\
        --out-dir reference/monthly_reporting_documents/outputs/from_pdf \\
        --preview /tmp/preview.html

Requires: pdftotext and pdftocairo (poppler) on PATH.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path


Point = tuple[float, float]
Segment = tuple[Point, Point]


# ---------- PDF extraction ----------

METER_LABEL_RE = re.compile(
    r"\bB(\d{3}[A-Z]?)\b\s*-?\s*([A-ZÅÄÖ]{1,3}\d?)\s+V(MM?\d{2})\b",
    re.DOTALL,
)
BLOCK_RE = re.compile(
    r'<block[^>]*xMin="([\d.]+)"\s+yMin="([\d.]+)"\s+xMax="([\d.]+)"\s+yMax="([\d.]+)">(.*?)</block>',
    re.DOTALL,
)
WORD_RE = re.compile(r"<word[^>]*>([^<]+)</word>")


def extract_meter_labels(pdf_path: Path) -> list[tuple[str, Point]]:
    """Return [(meter_id, (cx, cy)), ...] from the PDF's text bounding boxes."""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftotext", "-bbox-layout", str(pdf_path), str(tmp_path)],
            check=True,
            capture_output=True,
        )
        html = tmp_path.read_text()
    finally:
        tmp_path.unlink(missing_ok=True)

    out: list[tuple[str, Point]] = []
    for m in BLOCK_RE.finditer(html):
        xmin, ymin, xmax, ymax = (float(x) for x in m.groups()[:4])
        words = " ".join(WORD_RE.findall(m.group(5)))
        mm = METER_LABEL_RE.search(words)
        if not mm:
            continue
        meter_id = f"B{mm.group(1)}.{mm.group(2)}_V{mm.group(3)}"
        out.append((meter_id, ((xmin + xmax) / 2, (ymin + ymax) / 2)))
    return out


PATH_RE = re.compile(r"<path\s+([^/]+?)/>", re.DOTALL)
SVG_VIEWBOX_RE = re.compile(r'<svg[^>]*viewBox="\s*0\s+0\s+([\d.]+)\s+([\d.]+)"')


Arrow = tuple[Point, Point]  # (apex, unit direction vector)


def extract_arrows(svg: str) -> list[Arrow]:
    """Return list of (apex_point, direction_vector_normalised).

    AutoCAD flödesschema arrows (<, >, ^, v) are drawn as two filled-black
    parallelogram "barbs" that share the apex vertex. Pair them by that
    shared vertex; direction points from the combined centroid toward the
    apex. Unpaired filled shapes (≤4 of 80 seen in gtn_varme) are skipped —
    likely non-arrow glyphs.
    """
    path_re = re.compile(r"<path\s+([^/]+?)/>", re.DOTALL)
    barbs: list[list[Point]] = []
    for m in path_re.finditer(svg):
        attrs = m.group(1)
        d = _attr(attrs, "d")
        fill = _attr(attrs, "fill") or ""
        tx = _attr(attrs, "transform") or ""
        if not d or fill != "rgb(0%, 0%, 0%)":
            continue
        mx = re.search(r"matrix\(([^)]+)\)", tx)
        if not mx:
            continue
        a, b, c, dm, e, f = (float(x) for x in mx.group(1).split(","))

        def apply(x: float, y: float, a=a, b=b, c=c, dm=dm, e=e, f=f) -> Point:
            return (a * x + c * y + e, b * x + dm * y + f)

        tokens = re.findall(r"[MLZ]|-?\d+\.?\d*", d)
        verts: list[Point] = []
        seen: set[tuple[float, float]] = set()
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in ("M", "L"):
                p = apply(float(tokens[i + 1]), float(tokens[i + 2]))
                key = (round(p[0], 2), round(p[1], 2))
                if key not in seen:
                    seen.add(key)
                    verts.append(p)
                i += 3
            else:
                i += 1
        if verts:
            barbs.append(verts)

    def snap(p: Point, tol: float = 1.0) -> tuple[float, float]:
        return (round(p[0] / tol) * tol, round(p[1] / tol) * tol)

    barb_keys = [{snap(v) for v in b} for b in barbs]
    arrows: list[Arrow] = []
    used: set[int] = set()
    for i, ki in enumerate(barb_keys):
        if i in used:
            continue
        for j in range(i + 1, len(barb_keys)):
            if j in used:
                continue
            shared = ki & barb_keys[j]
            if len(shared) == 1:
                apex_key = next(iter(shared))
                # recover actual apex (unsnapped) from barbs[i]
                apex = next(v for v in barbs[i] if snap(v) == apex_key)
                all_verts = barbs[i] + barbs[j]
                cx = sum(v[0] for v in all_verts) / len(all_verts)
                cy = sum(v[1] for v in all_verts) / len(all_verts)
                dx, dy = apex[0] - cx, apex[1] - cy
                mag = (dx * dx + dy * dy) ** 0.5
                if mag > 0.1:
                    arrows.append((apex, (dx / mag, dy / mag)))
                used.add(i)
                used.add(j)
                break
    return arrows


def orient_segments(arrows: list[Arrow], segments: list[Segment], match_radius: float = 30.0) -> dict[Segment, Point]:
    """Return {segment: downstream_endpoint}.

    For each axis-aligned pipe segment near an arrow whose direction is
    roughly parallel to the segment, mark which of the segment's two
    endpoints is downstream (i.e., closer to the arrow's apex along the
    arrow-direction line).
    """
    directed: dict[Segment, Point] = {}
    for apex, (adx, ady) in arrows:
        is_arrow_h = abs(adx) > abs(ady) * 2
        is_arrow_v = abs(ady) > abs(adx) * 2
        if not (is_arrow_h or is_arrow_v):
            continue
        best: tuple[float, Segment, Point] | None = None
        for seg in segments:
            (x1, y1), (x2, y2) = seg
            seg_is_h = abs(y1 - y2) < 0.5
            seg_is_v = abs(x1 - x2) < 0.5
            # direction must align with segment orientation
            if is_arrow_h and not seg_is_h:
                continue
            if is_arrow_v and not seg_is_v:
                continue
            # arrow apex must lie "on" the segment (within match_radius)
            if seg_is_h:
                # distance to segment y
                dy = abs(apex[1] - y1)
                if dy > match_radius:
                    continue
                xmin, xmax = sorted((x1, x2))
                if apex[0] < xmin - match_radius or apex[0] > xmax + match_radius:
                    continue
                score = dy + max(0, xmin - apex[0], apex[0] - xmax)
            else:  # seg_is_v
                dx = abs(apex[0] - x1)
                if dx > match_radius:
                    continue
                ymin, ymax = sorted((y1, y2))
                if apex[1] < ymin - match_radius or apex[1] > ymax + match_radius:
                    continue
                score = dx + max(0, ymin - apex[1], apex[1] - ymax)
            if best is None or score < best[0]:
                best = (score, seg, apex)
        if best is None:
            continue
        _, seg, apex = best
        (x1, y1), (x2, y2) = seg
        # Downstream endpoint is the one matching arrow direction
        if seg_is_h := abs(y1 - y2) < 0.5:
            downstream = (x2, y2) if ((x2 - x1) * adx) > 0 else (x1, y1)
        else:
            downstream = (x2, y2) if ((y2 - y1) * ady) > 0 else (x1, y1)
        directed[seg] = downstream
    return directed


def extract_pipe_segments(pdf_path: Path) -> tuple[list[Segment], list[Arrow], Point]:
    """Return (segments, arrows, (viewbox_w, viewbox_h)).

    Segments are axis-aligned black-stroke pipe runs. Arrows are
    extracted from filled-black chevron shapes; each has an apex point
    and a unit direction vector. Both are transformed into the SVG
    viewBox coordinate space (same frame as the text bboxes).
    """
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftocairo", "-svg", str(pdf_path), str(tmp_path)],
            check=True,
            capture_output=True,
        )
        svg = tmp_path.read_text()
    finally:
        tmp_path.unlink(missing_ok=True)

    vb = SVG_VIEWBOX_RE.search(svg)
    viewbox = (float(vb.group(1)), float(vb.group(2))) if vb else (2384.0, 1684.0)

    segments: list[Segment] = []
    for m in PATH_RE.finditer(svg):
        attrs = m.group(1)
        d = _attr(attrs, "d")
        fill = _attr(attrs, "fill") or ""
        stroke = _attr(attrs, "stroke") or ""
        tx = _attr(attrs, "transform") or ""
        if not d or fill != "none" or not stroke.startswith("rgb(0%"):
            continue
        mx = re.search(r"matrix\(([^)]+)\)", tx)
        if not mx:
            continue
        a, b, c, dm, e, f = (float(x) for x in mx.group(1).split(","))

        def apply(x: float, y: float) -> Point:
            return (a * x + c * y + e, b * x + dm * y + f)

        tokens = re.findall(r"[MLZ]|-?\d+\.?\d*", d)
        i = 0
        cur: Point | None = None
        start: Point | None = None
        while i < len(tokens):
            t = tokens[i]
            if t == "M":
                cur = apply(float(tokens[i + 1]), float(tokens[i + 2]))
                start = cur
                i += 3
            elif t == "L":
                nxt = apply(float(tokens[i + 1]), float(tokens[i + 2]))
                if cur is not None:
                    segments.append((cur, nxt))
                cur = nxt
                i += 3
            elif t == "Z":
                if cur and start:
                    segments.append((cur, start))
                cur = start
                i += 1
            else:
                i += 1

    arrows = extract_arrows(svg)
    return segments, arrows, viewbox


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


# ---------- Filtering ----------


def _len(s: Segment) -> float:
    return ((s[0][0] - s[1][0]) ** 2 + (s[0][1] - s[1][1]) ** 2) ** 0.5


def _is_h(s: Segment) -> bool:
    return abs(s[0][1] - s[1][1]) < 0.5


def _is_v(s: Segment) -> bool:
    return abs(s[0][0] - s[1][0]) < 0.5


def filter_pipe_segments(
    segments: list[Segment], viewbox: Point, frame_margin: float = 60.0
) -> list[Segment]:
    """Drop drawing-frame lines, decorative strokes, and non-axis-aligned paths."""
    w, h = viewbox

    def touches_frame(s: Segment) -> bool:
        return (
            all(abs(p[0]) < frame_margin or abs(p[0] - w) < frame_margin for p in s)
            or all(abs(p[1]) < frame_margin or abs(p[1] - h) < frame_margin for p in s)
        )

    def in_title_block(s: Segment) -> bool:
        # Flödesschema template has its title block in the right ~15% of the page.
        return s[0][0] > 0.84 * w and s[1][0] > 0.84 * w

    return [
        s
        for s in segments
        if _len(s) > 10 and (_is_h(s) or _is_v(s)) and not touches_frame(s) and not in_title_block(s)
    ]


# ---------- Graph ----------


def snap(pt: Point, tol: float = 2.0) -> Point:
    return (round(pt[0] / tol) * tol, round(pt[1] / tol) * tol)


def split_at_tees(segments: list[Segment], tol: float = 2.0) -> list[Segment]:
    """Split H/V segments at every perpendicular that crosses or tees them."""
    splits: dict[int, set[float]] = defaultdict(set)
    for h in segments:
        if not _is_h(h):
            continue
        (x1, y1), (x2, _) = h
        hxmin, hxmax = sorted((x1, x2))
        for v in segments:
            if not _is_v(v):
                continue
            vx = v[0][0]
            vymin, vymax = sorted((v[0][1], v[1][1]))
            if hxmin - tol <= vx <= hxmax + tol and vymin - tol <= y1 <= vymax + tol:
                splits[id(h)].add(vx)
                splits[id(v)].add(y1)

    out: list[Segment] = []
    for s in segments:
        (x1, y1), (x2, y2) = s
        if _is_h(s):
            xs = sorted({x1, x2, *splits.get(id(s), set())})
            out.extend(((xs[i], y1), (xs[i + 1], y1)) for i in range(len(xs) - 1))
        elif _is_v(s):
            ys = sorted({y1, y2, *splits.get(id(s), set())})
            out.extend(((x1, ys[i]), (x1, ys[i + 1])) for i in range(len(ys) - 1))
    return out


def assign_meter_endpoints(
    meters: list[tuple[str, Point]],
    adj: dict[Point, set[Point]],
    radius: float = 100.0,
    gap_max: float = 110.0,
) -> dict[Point, str]:
    """Assign degree-1 pipe endpoints to meter labels.

    Three-pass matcher. Each degree-1 endpoint first claims the closest
    meter within `radius`. Per meter we pick the tightest eligible flank
    pair (endpoints not directly connected, within `gap_max`) — that gives
    the clean inline/corner-meter case. Pass 2 handles orphans: endpoints
    that claimed a meter but were not used in its pair get re-offered to
    their next-nearest meter within radius. Pass 3 gives any still-empty
    meter its closest remaining endpoint as a dead-end stub. This prevents
    the "tight pair eats a stub another meter needs" failure mode.
    """
    degree = {n: len(nb) for n, nb in adj.items()}
    deg1 = [n for n, d in degree.items() if d == 1]

    # ranked meter list per endpoint (within radius, nearest first)
    ep_to_ranked: dict[Point, list[tuple[float, str]]] = {}
    for ep in deg1:
        ranked = sorted(
            ((((ep[0] - mx) ** 2 + (ep[1] - my) ** 2) ** 0.5, name)
             for name, (mx, my) in meters),
            key=lambda t: t[0],
        )
        ranked = [(d, n) for d, n in ranked if d <= radius]
        if ranked:
            ep_to_ranked[ep] = ranked

    # pass 1: each endpoint claims its closest meter
    claims: dict[str, list[tuple[float, Point]]] = defaultdict(list)
    for ep, ranked in ep_to_ranked.items():
        claims[ranked[0][1]].append((ranked[0][0], ep))

    ep_to_meter: dict[Point, str] = {}
    used_eps: set[Point] = set()
    claimed: set[str] = set()

    def _try_assign(name: str, cs: list[tuple[float, Point]]) -> tuple[bool, list[Point]]:
        """Try to assign meter `name` from candidates `cs`. Return (ok, leftover_eps).

        Pair ranking:
          rank 0 — same-axis (|Δx| < 3 OR |Δy| < 3): the canonical inline
                   meter gap (pipe with a break in the middle)
          rank 1 — corner / diagonal pairs (like B643 in gtn_anga where the
                   flanks straddle a pipe bend)
        Same-axis pairs always win over diagonal pairs, regardless of
        absolute gap. Without this, closely-spaced rectangle corners
        inside a VVX symbol get misread as meter flanks.
        """
        avail = [(d, ep) for d, ep in sorted(cs) if ep not in used_eps]
        if not avail:
            return False, []
        pairs: list[tuple[int, float, Point, Point]] = []
        for i, (_, a) in enumerate(avail):
            for _, b in avail[i + 1 :]:
                if b in adj.get(a, set()):
                    continue
                gap = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
                if gap <= gap_max:
                    # Same-axis means truly collinear (both endpoints split
                    # from the same pipe). Use a tolerance below the 2u snap
                    # grid so we don't falsely rank diagonally-close pairs
                    # (e.g. rectangle corners inside a VVX) as collinear.
                    rank = 0 if (abs(a[0] - b[0]) < 0.5 or abs(a[1] - b[1]) < 0.5) else 1
                    pairs.append((rank, gap, a, b))
        if pairs:
            pairs.sort()
            _, _, a, b = pairs[0]
            ep_to_meter[a] = name
            ep_to_meter[b] = name
            used_eps.add(a); used_eps.add(b)
            claimed.add(name)
            return True, [ep for _, ep in avail if ep not in (a, b)]
        # single dead-end
        ep_to_meter[avail[0][1]] = name
        used_eps.add(avail[0][1])
        claimed.add(name)
        return True, [ep for _, ep in avail[1:]]

    orphans: list[Point] = []
    for name, cs in claims.items():
        _, leftover = _try_assign(name, cs)
        orphans.extend(leftover)

    # pass 2: re-offer orphans to their next-nearest unclaimed meter
    for ep in orphans:
        if ep in used_eps:
            continue
        for _, name in ep_to_ranked.get(ep, []):
            if name in claimed:
                continue
            ep_to_meter[ep] = name
            used_eps.add(ep)
            claimed.add(name)
            break

    # pass 3: final fallback — any still-unsatisfied meter grabs its closest unused endpoint
    stub_candidates: list[tuple[float, str, Point]] = []
    for name, (mx, my) in meters:
        if name in claimed:
            continue
        for ep in deg1:
            if ep in used_eps:
                continue
            d = ((ep[0] - mx) ** 2 + (ep[1] - my) ** 2) ** 0.5
            if d <= radius:
                stub_candidates.append((d, name, ep))
    stub_candidates.sort()
    for _, name, ep in stub_candidates:
        if name in claimed or ep in used_eps:
            continue
        ep_to_meter[ep] = name
        used_eps.add(ep)
        claimed.add(name)

    return ep_to_meter


def bridge_pipe_gaps(
    adj: dict[object, set[object]],
    ep_to_meter: dict[Point, str],
    max_gap: float = 20.0,
) -> tuple[dict[object, set[object]], int]:
    """Bridge small same-axis gaps between pipe-only dead-end nodes.

    AutoCAD flödesschema pipes often pass through a heat exchanger (VVX)
    symbol drawn as a rectangle; the pipe "enters" the rectangle on one side
    and "exits" on the opposite side, leaving a small (≈14-20u) gap in the
    pipe graph where the rectangle interior sits. This function adds an
    explicit edge between dead-end pipe nodes that are:
      - on the same axis (tolerance 3)
      - within ``max_gap`` of each other
      - not already adjacent
      - not meter IDs (already paired by assign_meter_endpoints)
    Returns (modified adj, number_of_bridges_added).
    """
    degree = {n: len(nb) for n, nb in adj.items()}
    pipe_ends = [
        n for n, d in degree.items()
        if d == 1 and not isinstance(n, str)
    ]
    pipe_ends.sort()

    added = 0
    for i, a in enumerate(pipe_ends):
        for b in pipe_ends[i + 1 :]:
            # Early exit on x-sorted list
            if b[0] - a[0] > max_gap:
                break
            same_x = abs(a[0] - b[0]) < 3
            same_y = abs(a[1] - b[1]) < 3
            if not (same_x or same_y):
                continue
            d = abs(a[1] - b[1]) if same_x else abs(a[0] - b[0])
            if d < 1 or d > max_gap:
                continue
            if b in adj.get(a, set()):
                continue
            # Re-check degrees — earlier bridges may have promoted endpoints above degree 1
            if len(adj[a]) != 1 or len(adj[b]) != 1:
                continue
            adj[a].add(b)
            adj[b].add(a)
            added += 1
    return adj, added


def build_graph(
    segments: list[Segment],
    meters: list[tuple[str, Point]],
    radius: float = 100.0,
    bridge_gaps: float = 20.0,
) -> tuple[dict[object, set[object]], dict[Point, str], int]:
    """Split at tees, snap nodes, merge meter endpoints, then bridge VVX gaps."""
    split_segs = split_at_tees(segments)

    raw_adj: dict[Point, set[Point]] = defaultdict(set)
    for a, b in split_segs:
        na, nb = snap(a), snap(b)
        if na != nb:
            raw_adj[na].add(nb)
            raw_adj[nb].add(na)

    ep_to_meter = assign_meter_endpoints(meters, raw_adj, radius=radius)

    def node_id(pt: Point) -> object:
        return ep_to_meter.get(pt, pt)

    adj: dict[object, set[object]] = defaultdict(set)
    for a, neighbours in raw_adj.items():
        for b in neighbours:
            na, nb = node_id(a), node_id(b)
            if na != nb:
                adj[na].add(nb)
                adj[nb].add(na)

    bridges = 0
    if bridge_gaps > 0:
        # Iterate: bridging may expose new dead-ends that weren't degree-1 initially
        for _ in range(4):
            adj, added = bridge_pipe_gaps(adj, ep_to_meter, max_gap=bridge_gaps)
            bridges += added
            if added == 0:
                break
    return adj, ep_to_meter, bridges


def find_components(adj: dict[object, set[object]]) -> list[set[object]]:
    """Return the list of connected components in the undirected pipe graph."""
    visited: set[object] = set()
    components: list[set[object]] = []
    for seed in adj:
        if seed in visited:
            continue
        comp: set[object] = set()
        q: deque[object] = deque([seed])
        while q:
            u = q.popleft()
            if u in visited:
                continue
            visited.add(u)
            comp.add(u)
            for v in adj[u]:
                if v not in visited:
                    q.append(v)
        components.append(comp)
    return components


def pick_component_root(
    component: set[object],
    adj: dict[object, set[object]],
    meters: set[str],
    declared_sources: list[str],
    arrow_sources: set[str] | None = None,
) -> tuple[object | None, str]:
    """For a component, choose a BFS root. Priority order:
    1. a user-declared ``--sources`` meter in this component → ``explicit``
    2. a meter derived from arrow direction (0 incoming, ≥1 outgoing) → ``arrow``
    3. highest pipe-graph degree (tie-break alphabetical) → ``auto_root_degree``
    """
    meter_nodes = [n for n in component if isinstance(n, str) and n in meters]
    if not meter_nodes:
        return None, "none"
    for s in declared_sources:
        if s in component:
            return s, "explicit"
    if arrow_sources:
        for s in arrow_sources:
            if s in component:
                return s, "arrow"
    ranked = sorted(meter_nodes, key=lambda n: (-len(adj[n]), n))
    return ranked[0], "auto_root_degree"


def trace_parents(
    adj: dict[object, set[object]],
    sources: list[str],
    meters: set[str],
    arrow_sources: set[str] | None = None,
) -> tuple[dict[object, object | None], dict[object, str], list[str]]:
    """BFS over every connected component; return (parent, root_source, unreached_meters).

    ``root_source`` records, for each BFS root, whether it came from the
    user-declared ``--sources`` list, was derived from an arrow-direction
    vote, or was auto-picked by the in-component heuristic. Downstream code
    attaches this to each edge so the output is auditable.
    """
    parent: dict[object, object | None] = {}
    root_source: dict[object, str] = {}
    visited: set[object] = set()

    # Warn about declared sources that aren't in the graph at all
    for s in sources:
        if s not in adj:
            print(f"warning: source '{s}' not wired to any pipe", file=sys.stderr)

    for comp in find_components(adj):
        root, why = pick_component_root(comp, adj, meters, sources, arrow_sources)
        if root is None:
            continue
        q: deque[object] = deque([root])
        visited.add(root)
        parent[root] = None
        root_source[root] = why
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    parent[v] = u
                    q.append(v)

    unreached = [m for m in meters if m not in visited]
    return parent, root_source, unreached


def nearest_upstream_meter(
    parent: dict[object, object | None], node: object, meters: set[str]
) -> str | None:
    cur = parent.get(node)
    while cur is not None and cur not in meters:
        cur = parent.get(cur)
    return cur if isinstance(cur, str) else None


# ---------- Output ----------


def write_meters_csv(path: Path, meters: list[tuple[str, Point]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "building", "meter_type"])
        for meter_id, _ in sorted(meters):
            building = meter_id.split(".")[0][1:].rstrip("NSEW")
            w.writerow([meter_id, building, "real"])


def write_relations_csv(
    path: Path, relations: list[tuple[str, str, str]], source_tag: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_meter", "to_meter", "coefficient", "derived_from"])
        for src, dst, why in sorted(relations):
            # Append the component-root provenance so edges with heuristic
            # direction are visible when auditing.
            derived = f"{source_tag}/{why}" if why != "explicit" else source_tag
            w.writerow([src, dst, "1.0", derived])


# ---------- Preview ----------


def write_preview_html(
    path: Path,
    segments: list[Segment],
    meters: list[tuple[str, Point]],
    parent: dict[object, object | None],
    sources: list[str],
    relations: list[tuple[str, str]],
    unreached: list[str],
    viewbox: Point,
    pdf_name: str,
) -> None:
    """Render a diagnostic HTML: pipe network + meters + inferred parent→child arrows.

    The visualization matches the PDF's coordinate frame 1:1 so you can
    side-by-side it against the flödesschema to sanity-check:
      - grey lines = pipe segments that were picked up
      - filled circles = meter glyphs (color = source root they descend from)
      - dashed arrows = inferred parent → child edges
      - red outline = meter not reached from any source
      - double ring = a declared source meter
    """
    w, h = viewbox
    src_of: dict[str, str] = {}
    for name, _ in meters:
        cur: object | None = name
        while cur is not None and cur not in sources:
            cur = parent.get(cur)
        src_of[name] = cur if isinstance(cur, str) else "—"
    palette = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#17becf"]
    src_color = {s: palette[i % len(palette)] for i, s in enumerate(sources)}
    src_color["—"] = "#bbb"
    pos = {name: xy for name, xy in meters}
    unreached_set = set(unreached)

    lines = [
        "<!doctype html><meta charset=utf-8>",
        f"<title>{pdf_name}</title>",
        "<style>",
        "body{font:13px system-ui;margin:12px;color:#222}",
        "svg{background:#fafafa;border:1px solid #ccc;display:block}",
        "text{font:10px monospace;pointer-events:none}",
        ".pipe{stroke:#999;stroke-width:1.2}",
        ".rel{stroke-width:1.2;stroke-dasharray:6 4;fill:none;opacity:.85}",
        ".meter-label{fill:#222}",
        ".legend{margin:8px 0}",
        ".legend span{margin-right:14px}",
        ".toggle{margin-right:10px}",
        "</style>",
        f"<h2>{pdf_name}</h2>",
        '<div class="legend">sources: '
        + ", ".join(
            f'<span style="color:{src_color[s]};font-weight:600">● {s}</span>' for s in sources
        )
        + "</div>",
        '<div class="legend">'
        f"<span>meters: <b>{len(meters)}</b></span>"
        f"<span>relations: <b>{len(relations)}</b></span>"
        + (
            f'<span style="color:#c00">unreached: <b>{len(unreached)}</b> — {", ".join(unreached)}</span>'
            if unreached
            else '<span style="color:#2a7">all meters reached ✓</span>'
        )
        + "</div>",
        '<div class="legend">'
        '<label class="toggle"><input type="checkbox" checked onchange="document.getElementById(\'pipes\').style.display=this.checked?\'\':\'none\'"> pipes</label>'
        '<label class="toggle"><input type="checkbox" checked onchange="document.getElementById(\'rels\').style.display=this.checked?\'\':\'none\'"> inferred relations</label>'
        '<label class="toggle"><input type="checkbox" checked onchange="document.getElementById(\'meters\').style.display=this.checked?\'\':\'none\'"> meters</label>'
        "</div>",
        f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-height:90vh">',
        '<defs>',
    ]
    # One arrowhead marker per source color
    for src, color in src_color.items():
        mid = _slug(src)
        lines.append(
            f'<marker id="arr-{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    lines.append("</defs>")

    # Pipes layer
    lines.append('<g id="pipes">')
    for (x1, y1), (x2, y2) in segments:
        lines.append(f'<line class="pipe" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    lines.append("</g>")

    # Relations layer
    lines.append('<g id="rels">')
    for rel in relations:
        # relations may be 2-tuples (parent, child) or 3-tuples (parent, child, why)
        src_m, dst_m = rel[0], rel[1]
        if src_m not in pos or dst_m not in pos:
            continue
        (sx, sy) = pos[src_m]
        (dx, dy) = pos[dst_m]
        color = src_color.get(src_of.get(dst_m, "—"), "#888")
        mid = _slug(src_of.get(dst_m, "—"))
        lines.append(
            f'<line class="rel" x1="{sx:.1f}" y1="{sy:.1f}" x2="{dx:.1f}" y2="{dy:.1f}" '
            f'stroke="{color}" marker-end="url(#arr-{mid})"><title>{src_m} → {dst_m}</title></line>'
        )
    lines.append("</g>")

    # Meters layer
    lines.append('<g id="meters">')
    for name, (cx, cy) in meters:
        color = src_color.get(src_of.get(name, "—"), "#888")
        stroke = "#c00" if name in unreached_set else color
        stroke_width = 2
        # Sources get a double ring
        if name in sources:
            lines.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="14" fill="none" stroke="{color}" stroke-width="2"/>'
            )
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="{color}" fill-opacity="0.15" '
            f'stroke="{stroke}" stroke-width="{stroke_width}"><title>{name}</title></circle>'
        )
        lines.append(
            f'<text class="meter-label" x="{cx:.1f}" y="{cy + 22:.1f}" text-anchor="middle" fill="{color}">'
            f"{name}</text>"
        )
    lines.append("</g>")

    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", s)


# ---------- CLI ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path, help="Flödesschema PDF (V###-##.#.8-*** style)")
    ap.add_argument(
        "--sources",
        required=True,
        help="Comma-separated source meter IDs (e.g. B600S.Å1_VMM71,B600N.Å1_VMM71)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reference/monthly_reporting_documents/outputs/from_pdf"),
        help="Directory for meters.csv and relations.csv",
    )
    ap.add_argument("--prefix", help="Output filename prefix (default: derived from PDF)")
    ap.add_argument("--preview", type=Path, help="Optional HTML preview path")
    ap.add_argument("--radius", type=float, default=100.0, help="Label→endpoint match radius")
    ap.add_argument("--bridge-gaps", type=float, default=20.0,
                    help="Max same-axis gap (units) between pipe dead-ends to auto-bridge (covers VVX/valve symbols); 0 disables")
    args = ap.parse_args()

    pdf_path: Path = args.pdf
    if not pdf_path.exists():
        print(f"error: {pdf_path} not found", file=sys.stderr)
        return 2

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    prefix = args.prefix or _derive_prefix(pdf_path.stem)

    meter_labels = extract_meter_labels(pdf_path)
    if not meter_labels:
        print("error: no meter labels found — is this a flödesschema PDF?", file=sys.stderr)
        return 3

    raw_segs, arrows, viewbox = extract_pipe_segments(pdf_path)
    segs = filter_pipe_segments(raw_segs, viewbox)
    pipe_directions = orient_segments(arrows, segs)
    adj, ep_to_meter, bridges = build_graph(segs, meter_labels, radius=args.radius, bridge_gaps=args.bridge_gaps)
    if bridges:
        print(f"bridged {bridges} pipe-gap pairs (VVX / valve symbols)", file=sys.stderr)

    # Map snapped pipe endpoints to a downstream-vote per node. A meter node
    # is "downstream" according to a given arrow-oriented segment when the
    # segment's downstream endpoint sits at/near that meter's position after
    # snap+merge. We accumulate votes per meter and use them below to seed
    # the BFS sources.
    from collections import defaultdict as _dd
    incoming_votes: dict[object, int] = _dd(int)
    outgoing_votes: dict[object, int] = _dd(int)

    def _node_of(pt: Point) -> object:
        sp = snap(pt)
        return ep_to_meter.get(sp, sp)

    for seg, downstream in pipe_directions.items():
        (a, b) = seg
        down_node = _node_of(downstream)
        up_node = _node_of(a) if _node_of(b) == down_node else _node_of(b)
        if up_node == down_node:
            continue
        incoming_votes[down_node] += 1
        outgoing_votes[up_node] += 1

    meter_ids = {name for name, _ in meter_labels}
    # Arrow-derived sources: meters with ≥1 outgoing vote and 0 incoming votes
    arrow_sources = [
        m for m in meter_ids
        if outgoing_votes.get(m, 0) > 0 and incoming_votes.get(m, 0) == 0
    ]
    # Merge: user-declared + arrow-derived (declared first so the parser
    # prefers them when both are in the same component)
    effective_sources = list(dict.fromkeys(sources + arrow_sources))

    print(
        f"arrows detected: {len(arrows)}; "
        f"pipes oriented: {len(pipe_directions)}; "
        f"arrow-derived sources: {len(arrow_sources)} (declared: {len(sources)})",
        file=sys.stderr,
    )

    parent, root_source, unreached = trace_parents(
        adj, sources, meter_ids, arrow_sources=set(arrow_sources)
    )

    # Tag every edge with the provenance of its component's root
    relations: list[tuple[str, str, str]] = []
    # Walk each meter to its parent-chain root to find which component it belongs to
    def component_root(m: object) -> object | None:
        cur: object | None = m
        while cur is not None and parent.get(cur) is not None:
            cur = parent[cur]
        return cur

    for name in meter_ids:
        up = nearest_upstream_meter(parent, name, meter_ids)
        if up is None:
            continue
        root = component_root(name)
        why = root_source.get(root, "unknown") if root is not None else "unknown"
        relations.append((up, name, why))

    out_dir: Path = args.out_dir
    meters_path = out_dir / f"{prefix}_meters.csv"
    relations_path = out_dir / f"{prefix}_relations.csv"
    write_meters_csv(meters_path, meter_labels)
    write_relations_csv(relations_path, relations, f"flow_schema_{pdf_path.stem}")

    # Counts per provenance
    from collections import Counter
    prov_counts = Counter(r[2] for r in relations)
    print(f"wrote {meters_path} ({len(meter_labels)} meters)")
    print(f"wrote {relations_path} ({len(relations)} relations; {dict(prov_counts)})")
    # Count components picked by each provenance
    comp_prov_counts = Counter(root_source.values())
    print(f"components rooted: {dict(comp_prov_counts)}", file=sys.stderr)
    if unreached:
        print(f"warning: {len(unreached)} meters not reached from any component root: {unreached}", file=sys.stderr)

    if args.preview:
        write_preview_html(
            args.preview,
            segs,
            meter_labels,
            parent,
            sources,
            relations,
            unreached,
            viewbox,
            pdf_path.name,
        )
        print(f"wrote {args.preview}")

    return 0 if not unreached else 1


def _derive_prefix(stem: str) -> str:
    # V600-52.E.8-001 → gtn_anga; V600-52.B.8-001 → gtn_varme; V390-56.8-001 → gtn_el; ...
    # 390/600 = Södertälje buildings, both map to "gtn"; subsystem comes from the middle token.
    # Fallback: lower-cased stem.
    m = re.match(r"V(\d+)-(\d+)\.?([A-Z]?)\.?(\d+)-(\d+)", stem)
    if not m:
        return stem.lower()
    # Leave building detection to a caller override if this gets uglier.
    return stem.lower()


if __name__ == "__main__":
    sys.exit(main())
