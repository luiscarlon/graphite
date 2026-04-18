#!/usr/bin/env python3
"""Compare every topology-bearing artifact in ``01_extracted/`` and write a
per-edge report to ``04_validation/source_conflicts.md``.

This tool **does not make reconciliation decisions**. It surfaces:

- edges **confirmed** by ≥2 independent sources
- edges **only one source has** (candidate for reconciliation)
- edges with **direction disagreement** across sources (needs a decision)
- meter IDs where **naming drift** is implicated (e.g. Excel uses `_E`
  variant but no canonical form exists in PDF)

The human reconciler reads this and writes ``decisions.md`` +
``topology_overrides.csv`` accordingly. Nothing here auto-applies.

## Sources consumed (all from 01_extracted/)

- ``flow_schema_relations.csv`` — PDF topology (PRIMARY authority per §3)
- ``excel_relations.csv``       — Excel-accounting-implied edges
- ``naming_relations.csv``      — meter-naming convention edges
- ``timeseries_relations.csv``  — timeseries-derived edges
- ``vlm_edge_suggestions.csv``  — Claude vision crops (optional)

Plus ``01_extracted/meter_roles.csv`` for canonical-ID alignment.

Usage:
    python source_conflicts.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


# ---------- loaders ----------


def _load_edges(path: Path, label: str) -> list[tuple[str, str, str]]:
    """Return [(from_meter, to_meter, source_label), ...]"""
    if not path.exists():
        return []
    out: list[tuple[str, str, str]] = []
    with path.open() as f:
        for r in csv.DictReader(f):
            f_m, t_m = r.get("from_meter"), r.get("to_meter")
            if not (f_m and t_m):
                continue
            out.append((f_m, t_m, label))
    return out


def _load_canonical_map(roles_path: Path) -> dict[str, str]:
    """Map every raw_variant → canonical_id so cross-source comparison is
    apples-to-apples regardless of ``_E`` or ``VM``/``VMM`` drift."""
    mp: dict[str, str] = {}
    if not roles_path.exists():
        return mp
    with roles_path.open() as f:
        for r in csv.DictReader(f):
            can = r["canonical_id"]
            mp[can] = can
            for v in (r.get("raw_variants") or "").split("|"):
                v = v.strip()
                if v:
                    mp[v] = can
    return mp


def _canon(m: str, mp: dict[str, str]) -> str:
    return mp.get(m, m)


# ---------- comparison ----------


def compare(
    all_edges: list[tuple[str, str, str]], mp: dict[str, str]
) -> dict[str, list]:
    """Return categorised edges.

    Categories:
      - confirmed:     edge present in ≥2 sources, same direction
      - source_only:   edge present in exactly 1 source
      - direction_conflict: source A has (f→t), source B has (t→f)
    """
    by_undirected: dict[frozenset, dict[tuple[str, str], set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for f, t, src in all_edges:
        fc, tc = _canon(f, mp), _canon(t, mp)
        by_undirected[frozenset({fc, tc})][(fc, tc)].add(src)

    confirmed: list[dict] = []
    source_only: list[dict] = []
    direction_conflict: list[dict] = []

    for _, directed in by_undirected.items():
        if len(directed) == 2:
            # both (f,t) and (t,f) present → direction conflict
            (da, sa), (db, sb) = list(directed.items())
            direction_conflict.append({
                "pair": tuple(sorted({da[0], da[1]})),
                "direction_A": da, "sources_A": sorted(sa),
                "direction_B": db, "sources_B": sorted(sb),
            })
            continue
        ((edge, sources),) = directed.items()
        if len(sources) >= 2:
            confirmed.append({"edge": edge, "sources": sorted(sources)})
        else:
            source_only.append({"edge": edge, "sources": sorted(sources)})

    return {
        "confirmed": sorted(confirmed, key=lambda r: r["edge"]),
        "source_only": sorted(source_only, key=lambda r: (r["sources"][0], r["edge"])),
        "direction_conflict": sorted(direction_conflict, key=lambda r: r["pair"]),
    }


# ---------- orphan analysis ----------


def orphan_report(
    meters: set[str], edges: list[tuple[str, str, str]], mp: dict[str, str],
    excel_inputs: dict[str, set[str]], excel_children: dict[str, set[str]],
) -> list[dict]:
    """For each meter with no parent in any source, classify using Excel."""
    connected = set()
    for f, t, _ in edges:
        connected.add(_canon(t, mp))  # `t` = child = has a parent

    orphans = sorted(_canon(m, mp) for m in meters if _canon(m, mp) not in connected)
    out: list[dict] = []
    for m in orphans:
        excel_plus = excel_inputs.get(m, set())
        excel_minus = excel_children.get(m, set())
        if excel_plus and not excel_minus:
            verdict = "terminal_leaf_per_excel"
            detail = f"+input to B{','.join(sorted(excel_plus))}; no downstream in Excel"
        elif excel_minus:
            verdict = "missing_parent"
            detail = f"child in B{','.join(sorted(excel_minus))} formula but no source emits an edge"
        else:
            verdict = "absent_from_excel"
            detail = "not referenced in any Excel formula — PDF/sensor-only"
        out.append({"meter": m, "verdict": verdict, "detail": detail})
    return out


# ---------- writer ----------


def write_md(
    path: Path, categories: dict, orphans: list[dict],
    edge_counts_per_source: dict[str, int],
) -> None:
    lines = [
        "# source_conflicts",
        "",
        "Per-edge agreement/conflict across every extractor in `01_extracted/`.",
        "This file is **advisory** — nothing is applied. Use it to inform",
        "the human reconciliation in `03_reconciliation/decisions.md`.",
        "",
        "## Sources consumed",
        "",
    ]
    for src, n in sorted(edge_counts_per_source.items()):
        lines.append(f"- `{src}`: **{n}** edges")
    lines += [
        "",
        "## Summary",
        "",
        f"- confirmed (≥2 sources, same direction): **{len(categories['confirmed'])}**",
        f"- single-source (1 source only):          **{len(categories['source_only'])}**",
        f"- direction conflicts (A↔B):              **{len(categories['direction_conflict'])}**",
        "",
    ]

    if categories["direction_conflict"]:
        lines += [
            "## Direction conflicts — require a `force_direction` decision",
            "",
            "| meters | source(s) saying A→B | source(s) saying B→A |",
            "|---|---|---|",
        ]
        for c in categories["direction_conflict"]:
            a, b = c["pair"]
            dA = f"{c['direction_A'][0]} → {c['direction_A'][1]}"
            sA = "/".join(c["sources_A"])
            dB = f"{c['direction_B'][0]} → {c['direction_B'][1]}"
            sB = "/".join(c["sources_B"])
            lines.append(f"| `{a}` ↔ `{b}` | `{dA}` [{sA}] | `{dB}` [{sB}] |")
        lines.append("")

    if categories["confirmed"]:
        lines += [
            "## Confirmed — ≥2 independent sources agree",
            "",
            "| from | to | sources |",
            "|---|---|---|",
        ]
        for c in categories["confirmed"]:
            f_m, t_m = c["edge"]
            lines.append(f"| `{f_m}` | `{t_m}` | {', '.join(c['sources'])} |")
        lines.append("")

    if categories["source_only"]:
        lines += [
            "## Single-source — candidates for reconciliation review",
            "",
            "Grouped by source so the reviewer can weight them against §3's",
            "authority rules (PDF is authoritative for topology; Excel for",
            "accounting; VLM requires human confirmation).",
            "",
        ]
        by_src: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for c in categories["source_only"]:
            by_src[c["sources"][0]].append(c["edge"])
        for src, eds in sorted(by_src.items()):
            lines += [f"### {src} ({len(eds)} edges)", "",
                      "| from | to |", "|---|---|"]
            for f_m, t_m in sorted(eds):
                lines.append(f"| `{f_m}` | `{t_m}` |")
            lines.append("")

    if orphans:
        lines += [
            "## Orphans — meters with no parent edge in any source",
            "",
            "Excel's formulas classify these:",
            "- `terminal_leaf_per_excel`: input-only to a building with no",
            "  downstream term. Parser orphaning is correct.",
            "- `missing_parent`: listed as a child in an Excel formula but no",
            "  source emits a specific parent edge. Candidate for `add`.",
            "- `absent_from_excel`: not referenced anywhere in Excel formulas.",
            "  Needs a PDF walk-through; likely sensor-only or naming drift.",
            "",
            "| meter | verdict | detail |",
            "|---|---|---|",
        ]
        for o in orphans:
            lines.append(f"| `{o['meter']}` | `{o['verdict']}` | {o['detail']} |")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


# ---------- main ----------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    ex = ws / "01_extracted"
    out = ws / "04_validation" / "source_conflicts.md"

    mp = _load_canonical_map(ex / "meter_roles.csv")

    sources: list[tuple[str, Path]] = [
        ("flow_schema", ex / "flow_schema_relations.csv"),
        ("excel_formula", ex / "excel_relations.csv"),
        ("naming", ex / "naming_relations.csv"),
        ("timeseries", ex / "timeseries_relations.csv"),
        ("vlm_edge_check", ex / "vlm_edge_suggestions.csv"),
    ]

    all_edges: list[tuple[str, str, str]] = []
    edge_counts: dict[str, int] = {}
    for label, p in sources:
        eds = _load_edges(p, label)
        edge_counts[label] = len(eds)
        all_edges.extend(eds)

    categories = compare(all_edges, mp)

    # Orphan analysis using Excel formula structure
    excel_inputs: dict[str, set[str]] = defaultdict(set)
    excel_children: dict[str, set[str]] = defaultdict(set)
    formulas_path = ex / "excel_formulas.csv"
    if formulas_path.exists():
        # Normalise via canonical_map
        with formulas_path.open() as f:
            for r in csv.DictReader(f):
                mid = _canon(r["meter_id"], mp)
                b = r["building"].strip()
                if r["role"] == "add":
                    excel_inputs[mid].add(b)
                elif r["role"] == "sub":
                    excel_children[mid].add(b)

    meters: set[str] = set()
    mp_path = ex / "flow_schema_meters.csv"
    if mp_path.exists():
        with mp_path.open() as f:
            for r in csv.DictReader(f):
                meters.add(r["meter_id"])

    orphans = orphan_report(meters, all_edges, mp, excel_inputs, excel_children)

    write_md(out, categories, orphans, edge_counts)

    n_conf = len(categories["confirmed"])
    n_solo = len(categories["source_only"])
    n_flip = len(categories["direction_conflict"])
    n_orph = len(orphans)
    print(
        f"wrote {out}: confirmed={n_conf} single_source={n_solo} "
        f"direction_conflicts={n_flip} orphans={n_orph}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
