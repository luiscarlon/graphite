#!/usr/bin/env python3
"""Render the flödesschema PDF as a PNG with the parser's topology overlaid.

Produces ``04_validation/flow_schema_audit.png`` — the PDF rendered to PNG at
150dpi with parser-inferred meter positions, parent→child edges coloured by
component, orphans ringed in red, and the "what broke where" legend at the
top.

Unlike the HTML preview this is a single flat PNG, which is easier to share
and to annotate in image-review tools.

Requires ``pdftocairo`` on PATH (for PNG rendering) and ``Pillow``
(for image compositing) — already in the workstream's env.

Usage:
    python render_audit_png.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _load_meters(path: Path) -> dict[str, tuple[float, float]]:
    """The parser's meters.csv doesn't carry x/y; we recover them by re-parsing
    the PDF's bbox-layout text output. Cheaper than changing the parser's CSV."""
    return {}


def _parse_meter_xy(pdf_path: Path) -> dict[str, tuple[float, float]]:
    """Extract {meter_id: (cx, cy)} from the PDF via pdftotext -bbox-layout."""
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

    meter_re = re.compile(
        r"\bB(\d{3}[A-Z]?)\b\s*-?\s*([A-ZÅÄÖ]{1,3}\d?)\s+V(MM?\d{2})\b",
        re.DOTALL,
    )
    block_re = re.compile(
        r'<block[^>]*xMin="([\d.]+)"\s+yMin="([\d.]+)"\s+xMax="([\d.]+)"\s+yMax="([\d.]+)">(.*?)</block>',
        re.DOTALL,
    )
    word_re = re.compile(r"<word[^>]*>([^<]+)</word>")

    out: dict[str, tuple[float, float]] = {}
    for m in block_re.finditer(html):
        xmin, ymin, xmax, ymax = (float(x) for x in m.groups()[:4])
        words = " ".join(word_re.findall(m.group(5)))
        mm = meter_re.search(words)
        if not mm:
            continue
        meter_id = f"B{mm.group(1)}.{mm.group(2)}_V{mm.group(3)}"
        out[meter_id] = ((xmin + xmax) / 2, (ymin + ymax) / 2)
    return out


def _pdf_viewbox(pdf_path: Path) -> tuple[float, float]:
    """SVG viewBox matches bbox-layout coords; pull it from a pdftocairo dump."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        svg_path = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftocairo", "-svg", str(pdf_path), str(svg_path)],
            check=True,
            capture_output=True,
        )
        svg = svg_path.read_text()
    finally:
        svg_path.unlink(missing_ok=True)
    m = re.search(r'<svg[^>]*viewBox="\s*0\s+0\s+([\d.]+)\s+([\d.]+)"', svg)
    return (float(m.group(1)), float(m.group(2))) if m else (2384.0, 1684.0)


def _render_pdf_to_png(pdf_path: Path, dpi: int, out_png: Path) -> tuple[int, int]:
    # pdftocairo writes "{prefix}-1.png" for single-page PDFs
    prefix = out_png.with_suffix("")
    subprocess.run(
        ["pdftocairo", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
    )
    rendered = Path(f"{prefix}-1.png")
    rendered.rename(out_png)
    from PIL import Image
    im = Image.open(out_png)
    return im.size


def _overlay(
    pdf_png: Path,
    meter_xy: dict[str, tuple[float, float]],
    relations: list[tuple[str, str, str]],
    pdf_vb: tuple[float, float],
    out_png: Path,
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(pdf_png).convert("RGBA")
    overlay = Image.new("RGBA", im.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    w_px, h_px = im.size
    vb_w, vb_h = pdf_vb
    sx, sy = w_px / vb_w, h_px / vb_h

    def xy(pt: tuple[float, float]) -> tuple[int, int]:
        return (int(pt[0] * sx), int(pt[1] * sy))

    # Color each edge by provenance
    prov_color = {
        "flow_schema": (31, 119, 180, 220),  # steel blue
        "arrow": (44, 160, 44, 220),  # green
        "auto_root_degree": (255, 127, 14, 220),  # orange
        "override": (214, 39, 40, 220),  # red
        "vlm_bridge": (148, 103, 189, 220),  # purple
        "same_axis": (140, 140, 140, 200),
        "ray_walk": (0, 180, 180, 220),  # cyan
        "arrow_ray": (44, 160, 44, 220),
    }

    def _provkey(tag: str) -> str:
        if tag.startswith("override_"):
            return "override"
        if tag.startswith("vlm_bridge"):
            return "vlm_bridge"
        if "/arrow" in tag:
            return "arrow"
        if "/auto_root_degree" in tag:
            return "auto_root_degree"
        if tag.startswith("flow_schema"):
            return "flow_schema"
        return "flow_schema"

    # Edges
    for src, dst, tag in relations:
        if src not in meter_xy or dst not in meter_xy:
            continue
        c = prov_color.get(_provkey(tag), (100, 100, 100, 220))
        x1, y1 = xy(meter_xy[src])
        x2, y2 = xy(meter_xy[dst])
        d.line([(x1, y1), (x2, y2)], fill=c, width=3)
        # arrowhead
        dx, dy = x2 - x1, y2 - y1
        mag = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / mag, dy / mag
        ah = 14
        hx, hy = x2 - int(ux * ah), y2 - int(uy * ah)
        px, py = -uy, ux
        d.polygon(
            [
                (x2, y2),
                (hx + int(px * 6), hy + int(py * 6)),
                (hx - int(px * 6), hy - int(py * 6)),
            ],
            fill=c,
        )

    # Meter dots
    connected = set()
    for s, t, _ in relations:
        connected.add(s); connected.add(t)

    for mid, pt in meter_xy.items():
        cx, cy = xy(pt)
        is_orphan = mid not in connected
        ring = (220, 30, 30, 240) if is_orphan else (20, 20, 20, 200)
        d.ellipse(
            [cx - 9, cy - 9, cx + 9, cy + 9],
            outline=ring,
            width=3,
            fill=(255, 255, 255, 60),
        )

    # Legend
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except OSError:
        font = ImageFont.load_default()

    legend_items = [
        ("flow_schema (parser)", prov_color["flow_schema"]),
        ("arrow-confirmed", prov_color["arrow"]),
        ("auto_root_degree (low conf.)", prov_color["auto_root_degree"]),
        ("override", prov_color["override"]),
        ("VLM bridge", prov_color["vlm_bridge"]),
        ("ORPHAN meter", (220, 30, 30, 240)),
    ]
    lx, ly = 30, 30
    bg = Image.new("RGBA", (460, 30 * len(legend_items) + 20), (255, 255, 255, 220))
    overlay.paste(bg, (lx - 10, ly - 10), bg)
    for text, color in legend_items:
        d.line([(lx, ly + 12), (lx + 40, ly + 12)], fill=color, width=4)
        d.text((lx + 50, ly - 2), text, fill=(20, 20, 20, 255), font=font)
        ly += 30

    Image.alpha_composite(im, overlay).save(out_png)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--pdf", type=Path, help="Default: 00_inputs/flow_schema.pdf")
    ap.add_argument("--relations", type=Path, help="Default: 01_extracted/flow_schema_relations.csv")
    ap.add_argument("--out", type=Path, help="Default: 04_validation/flow_schema_audit.png")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    pdf = args.pdf or ws / "00_inputs" / "flow_schema.pdf"
    rel_path = args.relations or ws / "01_extracted" / "flow_schema_relations.csv"
    out = args.out or ws / "04_validation" / "flow_schema_audit.png"

    if not pdf.exists():
        print(f"error: {pdf} not found", file=sys.stderr)
        return 2

    meter_xy = _parse_meter_xy(pdf)
    vb = _pdf_viewbox(pdf)

    relations = []
    if rel_path.exists():
        with rel_path.open() as f:
            for r in csv.DictReader(f):
                relations.append((r["from_meter"], r["to_meter"], r.get("derived_from", "")))

    out.parent.mkdir(parents=True, exist_ok=True)
    _render_pdf_to_png(pdf, args.dpi, out)
    _overlay(out, meter_xy, relations, vb, out)
    print(f"wrote {out} ({len(meter_xy)} meters, {len(relations)} edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
