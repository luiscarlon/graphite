#!/usr/bin/env python3
"""For every orphan meter in a workstream's parsed output, ask Claude (vision)
which nearby meters it actually connects to in the flödesschema PDF.

This is **one extractor among several** (alongside `parse_flow_schema.py`,
`excel_relations.py`, and `parse_meter_names.py`). It writes a sibling
artifact at ``01_extracted/vlm_edge_suggestions.csv`` and does **not** make
reconciliation decisions. Cross-source agreement is `source_conflicts.py`'s
job; the human reconciler consumes that and writes `decisions.md` +
`topology_overrides.csv`.

One PNG crop per orphan is written to ``04_validation/vlm_crops/{meter_id}.png``
so the VLM's reasoning can be re-checked later.

Environment:
  ``ANTHROPIC_API_KEY`` must be set.

Cost control:
  - Calls are cached by (pdf_stem, meter_id, crop_sha256) under
    ``04_validation/vlm_cache/``. Re-runs are free.
  - ``--limit N`` caps the number of meters to process in one run.
  - ``--dry-run`` produces crops and prompts without calling the API.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python vlm_edge_check.py reference/media_workstreams/gtn_varme
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT_TEMPLATE = """\
You are reviewing an AstraZeneca district-heating flödesschema (flow diagram).
The image below is a crop centred on the meter labeled **{meter_id}**. Meters
are drawn as ⊗ circles; the label is the "B### - XX" text next to each.

Goal: identify which OTHER labeled meter(s) in this crop are **directly
connected** to {meter_id} by a continuous pipe (possibly passing through a
heat exchanger (VVX rectangle), valve, or pump, but with no intervening
meter on the same pipe).

Use the ARROWS on the pipes to determine direction: the meter the arrow
points AWAY from is the parent; the meter it points TOWARD is the child.

Return STRICT JSON of the form:
{{
  "connections": [
    {{"neighbour_meter_id": "B###.XXX_VMM##", "direction": "parent_of_me" | "child_of_me" | "unknown", "evidence": "short reason citing the arrow / pipe segment"}}
  ],
  "notes": "any caveats — e.g. pipe leaves the crop without reaching a visible meter"
}}

Candidate neighbour meter IDs you may see in this crop (pick only the ones
actually pipe-connected to {meter_id}): {candidates}

Do not guess. If no meter is pipe-connected, return an empty array.
"""


def _load_meters(path: Path) -> dict[str, tuple[float, float]]:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftotext", "-bbox-layout", str(path), str(tmp_path)],
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


def _viewbox(pdf: Path) -> tuple[float, float]:
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        svg = Path(tmp.name)
    try:
        subprocess.run(
            ["pdftocairo", "-svg", str(pdf), str(svg)],
            check=True, capture_output=True,
        )
        content = svg.read_text()
    finally:
        svg.unlink(missing_ok=True)
    m = re.search(r'<svg[^>]*viewBox="\s*0\s+0\s+([\d.]+)\s+([\d.]+)"', content)
    return (float(m.group(1)), float(m.group(2))) if m else (2384.0, 1684.0)


def _crop_png(pdf: Path, cx: float, cy: float, vb: tuple[float, float],
              half_extent: float, dpi: int, out: Path) -> list[str]:
    """Render PDF at `dpi`, crop around (cx, cy) in viewBox coords.
    Returns list of meter IDs visible in the crop (for prompt candidates)."""
    from PIL import Image, ImageDraw, ImageFont
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "full"
        subprocess.run(
            ["pdftocairo", "-png", "-r", str(dpi), str(pdf), str(prefix)],
            check=True, capture_output=True,
        )
        rendered = Path(f"{prefix}-1.png")
        im = Image.open(rendered).convert("RGB")
    w_px, h_px = im.size
    sx, sy = w_px / vb[0], h_px / vb[1]

    px_cx, px_cy = int(cx * sx), int(cy * sy)
    px_h = int(half_extent * sx)
    l = max(0, px_cx - px_h)
    t = max(0, px_cy - px_h)
    r = min(w_px, px_cx + px_h)
    b = min(h_px, px_cy + px_h)
    crop = im.crop((l, t, r, b))
    # Mark the target meter in the crop for clarity
    d = ImageDraw.Draw(crop)
    tx, ty = px_cx - l, px_cy - t
    d.ellipse([tx - 20, ty - 20, tx + 20, ty + 20], outline=(220, 30, 30), width=4)
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out)
    return [l, t, r, b]


def _candidates_in_crop(
    meter_xy: dict[str, tuple[float, float]],
    target: str,
    half_extent: float,
) -> list[str]:
    tx, ty = meter_xy[target]
    near = []
    for mid, (x, y) in meter_xy.items():
        if mid == target:
            continue
        if abs(x - tx) <= half_extent and abs(y - ty) <= half_extent:
            near.append(mid)
    return sorted(near)


def _call_claude(prompt: str, png_path: Path, model: str) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        raise SystemExit("error: `anthropic` package not installed (uv add anthropic)")
    client = Anthropic()
    img_b64 = base64.standard_b64encode(png_path.read_bytes()).decode()
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    # Tolerate code fences
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"connections": [], "notes": f"non-JSON response: {text[:200]}"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"connections": [], "notes": f"JSON parse failed: {text[:200]}"}


def _cache_key(pdf_stem: str, meter_id: str, png_path: Path) -> str:
    sha = hashlib.sha256(png_path.read_bytes()).hexdigest()[:16]
    return f"{pdf_stem}__{meter_id}__{sha}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--pdf", type=Path, help="default: 00_inputs/flow_schema.pdf")
    ap.add_argument("--relations", type=Path,
                    help="default: 01_extracted/flow_schema_relations.csv")
    ap.add_argument("--meters", type=Path,
                    help="default: 01_extracted/flow_schema_meters.csv")
    ap.add_argument("--out", type=Path,
                    help="default: 01_extracted/vlm_edge_suggestions.csv")
    ap.add_argument("--cache-dir", type=Path,
                    help="default: 04_validation/vlm_cache")
    ap.add_argument("--crop-dir", type=Path,
                    help="default: 04_validation/vlm_crops")
    ap.add_argument("--half-extent", type=float, default=280.0,
                    help="PDF-space crop half-width around the target meter")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--model", default="claude-opus-4-6")
    ap.add_argument("--limit", type=int, default=0, help="cap number of meters; 0 = all")
    ap.add_argument("--dry-run", action="store_true",
                    help="write crops and prompts but don't call the API")
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    pdf = args.pdf or ws / "00_inputs" / "flow_schema.pdf"
    rel_path = args.relations or ws / "01_extracted" / "flow_schema_relations.csv"
    meters_path = args.meters or ws / "01_extracted" / "flow_schema_meters.csv"
    out_path = args.out or ws / "01_extracted" / "vlm_edge_suggestions.csv"
    cache_dir = args.cache_dir or ws / "04_validation" / "vlm_cache"
    crop_dir = args.crop_dir or ws / "04_validation" / "vlm_crops"

    if not pdf.exists():
        print(f"error: {pdf} missing", file=sys.stderr); return 2

    meter_xy = _load_meters(pdf)
    vb = _viewbox(pdf)

    # Known meters from CSV (deduped); orphan = not in any relation
    known = set()
    with meters_path.open() as f:
        for r in csv.DictReader(f):
            known.add(r["meter_id"])
    relations = []
    with rel_path.open() as f:
        for r in csv.DictReader(f):
            relations.append((r["from_meter"], r["to_meter"]))
    in_relation = {m for pair in relations for m in pair}
    orphans = sorted(m for m in known if m not in in_relation)

    if args.limit:
        orphans = orphans[: args.limit]
    print(f"{len(orphans)} orphan meters to check", file=sys.stderr)

    cache_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)

    today = "todo"  # replaced below
    import datetime
    today = datetime.date.today().isoformat()

    out_rows: list[dict] = []
    import time
    for i, meter in enumerate(orphans, start=1):
        if meter not in meter_xy:
            print(f"[{i}/{len(orphans)}] {meter}: no xy in PDF, skipping",
                  file=sys.stderr)
            continue
        cx, cy = meter_xy[meter]
        candidates = _candidates_in_crop(meter_xy, meter, args.half_extent)
        if not candidates:
            print(f"[{i}/{len(orphans)}] {meter}: no candidate meters in crop, skipping",
                  file=sys.stderr)
            continue

        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", meter)
        crop_png = crop_dir / f"{safe}.png"
        _crop_png(pdf, cx, cy, vb, args.half_extent, args.dpi, crop_png)
        prompt = PROMPT_TEMPLATE.format(
            meter_id=meter,
            candidates=", ".join(candidates),
        )

        cache_key = _cache_key(pdf.stem, meter, crop_png)
        cache_file = cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            result = json.loads(cache_file.read_text())
            src = "cache"
        elif args.dry_run:
            result = {"connections": [], "notes": "dry-run skipped"}
            src = "dry-run"
        else:
            print(f"[{i}/{len(orphans)}] {meter} → Claude ({args.model})",
                  file=sys.stderr)
            try:
                result = _call_claude(prompt, crop_png, args.model)
                cache_file.write_text(json.dumps(result, indent=2))
                src = "fresh"
            except Exception as exc:
                print(f"  error: {exc}", file=sys.stderr)
                continue
            time.sleep(0.3)

        for c in result.get("connections", []) or []:
            nb = c.get("neighbour_meter_id")
            direction = c.get("direction", "unknown")
            ev = c.get("evidence", "")
            if not nb or nb == meter:
                continue
            if direction == "parent_of_me":
                f, t = nb, meter
            elif direction == "child_of_me":
                f, t = meter, nb
            else:
                # direction unknown — write two symmetric rows for review
                out_rows.append({
                    "action": "add",
                    "from_meter": meter, "to_meter": nb,
                    "reason": f"VLM ({src}): direction unclear; {ev}",
                    "date": today, "author": "vlm",
                    "confidence": "low",
                })
                out_rows.append({
                    "action": "add",
                    "from_meter": nb, "to_meter": meter,
                    "reason": f"VLM ({src}): direction unclear; {ev}",
                    "date": today, "author": "vlm",
                    "confidence": "low",
                })
                continue
            out_rows.append({
                "action": "add",
                "from_meter": f, "to_meter": t,
                "reason": f"VLM ({src}): {ev}",
                "date": today, "author": "vlm",
                "confidence": "medium",
            })

    cols = ["from_meter", "to_meter", "coefficient", "derived_from", "direction", "evidence", "confidence"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        import datetime
        today = datetime.date.today().isoformat()
        for r in out_rows:
            w.writerow({
                "from_meter": r["from_meter"],
                "to_meter": r["to_meter"],
                "coefficient": "1.0",
                "derived_from": f"vlm_edge_check_{today}",
                "direction": "as_stated" if r.get("confidence") != "low" else "unclear",
                "evidence": r["reason"],
                "confidence": r.get("confidence", "medium"),
            })
    print(f"wrote {out_path} ({len(out_rows)} candidate edges; source_conflicts.py will surface these vs other extractors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
