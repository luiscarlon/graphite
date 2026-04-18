#!/usr/bin/env python3
"""Derive candidate parent→child meter relations from the Excel monthly-
reporting formulas.

This is **one extractor among several** (alongside `parse_flow_schema.py`,
`slice_timeseries.py`, and naming-convention parsing). It writes a sibling
artifact into ``01_extracted/excel_relations.csv`` and does **not** make
reconciliation decisions. Per-edge agreement/conflict across sources is
the job of `source_conflicts.py` → ``04_validation/source_conflicts.md``;
actual merging into ``facit_relations.csv`` is the human reconciler's job,
logged in ``decisions.md``.

## The signal

Each Excel formula row is ``building_use = Σ(+ inputs) − Σ(− pass_through)``.
A ``−`` term is a meter that carries heat leaving the building toward a
downstream child. Therefore every `−` meter is a child of the building,
and the main `+` inlet is the most-likely parent.

## Caveats (recorded so the reconciler can weight this source correctly)

1. Excel is **authoritative for accounting, not topology** (`docs_to_bric_parsing.md` §3).
   The `+` side is a *sum*; Excel alone can't tell you which specific `+`
   meter physically feeds a given `−` child. We pick a principal inlet
   (role=VP1 for heating by default) so the emitted edges form a tree,
   but the specific inlet is a guess — cross-check with the flow-schema.
2. Excel formulas can encode transitive shortcuts (``B614 = … − B642``
   even though the PDF's pipe path goes ``B614 → B615 → B642``). The
   emitted edge in that case is a legitimate *accounting* relation but
   not a physical pipe. The reconciler must check whether the parser's
   chain supersedes it.
3. Meter ID normalisation: strip ``_E`` suffix; align ``VM##`` → ``VMM##``.
   Meters referenced in Excel that are not in ``01_extracted/flow_schema_meters.csv``
   are emitted to a separate ``_dropped`` file for review (usually
   naming drift).

Usage:
    python excel_relations.py WORKSTREAM_DIR [--primary-role VP1]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


# ---------- meter-id normalisation ----------


def normalise(meter: str) -> str:
    """Strip ``_E`` suffix; align ``VM##`` → ``VMM##`` to parser convention."""
    m = re.match(r"(B\d+[A-Z]?)\.([A-ZÅÄÖ]+\d*)_V(MM?)(\d+)(?:_E)?$", meter)
    if not m:
        return meter
    building, role, _, digits = m.group(1), m.group(2), m.group(3), m.group(4)
    return f"{building}.{role}_VMM{digits}"


# ---------- principal inlet selection ----------


def building_main_inlet(meters: list[str], primary_role: str | None) -> str | None:
    """Pick a single principal inlet meter for a building.

    Priority (stop at first non-empty bucket):
      1. role == ``primary_role`` (e.g. VP1 for värme). Lowest VMM number.
      2. role starts with VP → primary heating.
      3. role starts with VS → secondary heating.
      4. role starts with Å → steam.
      5. First + meter declared.
    """
    def _mnum(meter: str) -> int:
        m = re.search(r"VMM(\d+)", meter)
        return int(m.group(1)) if m else 999

    if primary_role:
        hits = sorted([m for m in meters if f".{primary_role}_" in m], key=_mnum)
        if hits:
            return hits[0]
    for prefix in ("VP", "VS", "Å"):
        hits = sorted(
            [m for m in meters if re.search(rf"\.{prefix}\d*_", m)], key=_mnum,
        )
        if hits:
            return hits[0]
    return meters[0] if meters else None


# ---------- derivation ----------


def derive_edges(
    formula_rows: list[dict],
    primary_role: str | None,
    known_meters: set[str] | None = None,
) -> tuple[list[tuple], list[tuple]]:
    """Return (tree_edges, dropped_edges).

    Each row: (from_meter, to_meter, building, inlet_role, coefficient)
    Coefficient comes from the Excel formula's per-term factor.
    """
    by_building: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(
        lambda: {"add": [], "sub": []}
    )
    for r in formula_rows:
        faktor = 1.0
        fs = r.get("faktor") or ""
        try:
            if fs:
                faktor = float(fs)
        except (TypeError, ValueError):
            pass
        by_building[r["building"]][r["role"]].append((normalise(r["meter_id"]), faktor))

    edges: list[tuple] = []
    dropped: list[tuple] = []
    for b, sides in by_building.items():
        plus, minus = sides["add"], sides["sub"]
        if not minus:
            continue
        plus_meters = [m for m, _ in plus]
        inlet = building_main_inlet(plus_meters, primary_role)
        if inlet is None:
            continue
        inlet_role_m = re.search(r"\.([A-ZÅÄÖ]+\d*)_", inlet)
        inlet_role = inlet_role_m.group(1) if inlet_role_m else ""
        # Get the inlet's own coefficient (allocation factor for virtual meters)
        inlet_coeff = next((f for m, f in plus if m == inlet), 1.0)
        for child, child_coeff in minus:
            if inlet == child:
                continue
            # Use the child's coefficient (from the − term's factor)
            coeff = child_coeff if abs(child_coeff - 1.0) > 1e-9 else inlet_coeff
            rec = (inlet, child, b, inlet_role, coeff)
            if known_meters is not None and (
                inlet not in known_meters or child not in known_meters
            ):
                dropped.append(rec)
            else:
                edges.append(rec)
    return edges, dropped


# ---------- I/O ----------


def write_edges_csv(path: Path, edges: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str]] = set()
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_meter", "to_meter", "coefficient", "derived_from", "note"])
        for src, dst, b, role, coeff in sorted(edges):
            if (src, dst) in seen:
                continue
            seen.add((src, dst))
            coeff_s = f"{coeff}" if abs(coeff - 1.0) > 1e-9 else "1.0"
            w.writerow([
                src, dst, coeff_s,
                f"excel_formula_B{b.strip()}",
                f"inlet role {role}; child is − term in B{b.strip()} formula"
                + (f"; allocation factor {coeff}" if abs(coeff - 1.0) > 1e-9 else ""),
            ])


def write_dropped_csv(path: Path, dropped: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str]] = set()
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_meter", "to_meter", "building", "reason"])
        for rec in sorted(dropped):
            src, dst, b = rec[0], rec[1], rec[2]
            if (src, dst) in seen:
                continue
            seen.add((src, dst))
            reason_parts = []
            if src not in _known_meters:
                reason_parts.append(f"{src} not in flow_schema_meters")
            if dst not in _known_meters:
                reason_parts.append(f"{dst} not in flow_schema_meters")
            w.writerow([src, dst, b.strip(), "; ".join(reason_parts) or "meter missing"])


# Module-level state set during main() — read by write_dropped_csv
_known_meters: set[str] = set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument(
        "--primary-role",
        help='main-inlet role per media: "VP1" for värme, "VS1" for kyla, '
             '"Å1" for ånga. Auto-selected if unspecified.',
    )
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    formulas_path = ws / "01_extracted" / "excel_formulas.csv"
    meters_path = ws / "01_extracted" / "flow_schema_meters.csv"
    rel_out = ws / "01_extracted" / "excel_relations.csv"
    dropped_out = ws / "01_extracted" / "excel_relations_dropped.csv"

    if not formulas_path.exists():
        print(f"error: {formulas_path} missing — run parse_reporting_xlsx.py first", file=sys.stderr)
        return 2

    global _known_meters
    if meters_path.exists():
        for r in csv.DictReader(meters_path.open()):
            _known_meters.add(r["meter_id"])

    formula_rows = list(csv.DictReader(formulas_path.open()))
    edges, dropped = derive_edges(
        formula_rows, args.primary_role,
        known_meters=_known_meters or None,
    )
    write_edges_csv(rel_out, edges)
    write_dropped_csv(dropped_out, dropped)

    unique_edges = len({(f, t) for f, t, _, _ in edges})
    unique_dropped = len({(f, t) for f, t, _, _ in dropped})
    print(f"wrote {rel_out} ({unique_edges} edges from {len({b for _, _, b, _ in edges})} buildings with children)")
    print(f"wrote {dropped_out} ({unique_dropped} edges dropped — meter absent from PDF)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
