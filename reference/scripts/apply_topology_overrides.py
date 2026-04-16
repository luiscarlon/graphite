#!/usr/bin/env python3
"""Apply per-workstream manual overrides to the parsed flow-schema relations.

Reads ``01_extracted/flow_schema_relations.csv`` (the parser's output) plus
an optional ``03_reconciliation/topology_overrides.csv`` file and produces
the final ``03_reconciliation/facit_relations.csv``. Overrides let a human
correct parser mistakes without losing the provenance trail:

- ``add``              — add an edge the parser missed
- ``remove``           — drop an edge the parser produced (must exist or the
                          script errors)
- ``force_direction``  — reverse a parsed edge's direction (parent ↔ child)

Every override row must carry ``reason``, ``date``, and ``author`` so the
reasoning stays attached to the artifact. Overrides are tagged in the final
CSV's ``derived_from`` column as ``override_{date}_{author}`` so downstream
consumers can colour-code confidence.

Overrides CSV columns:
    action,from_meter,to_meter,coefficient,reason,date,author

Usage:
    python apply_topology_overrides.py WORKSTREAM_DIR

If the overrides file is missing, the script simply copies the parsed
output verbatim (making it safe to run unconditionally at the end of a
regeneration pass).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REQUIRED_COLS = {"action", "from_meter", "to_meter", "reason", "date", "author"}
OPTIONAL_COLS = {"coefficient"}
VALID_ACTIONS = {"add", "remove", "force_direction"}


def load_relations(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def load_overrides(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                f"error: {path} missing required columns: {sorted(missing)}"
            )
        rows = list(reader)
    for i, r in enumerate(rows, start=2):
        if r["action"] not in VALID_ACTIONS:
            raise SystemExit(
                f"error: {path} line {i}: action {r['action']!r} must be one of {VALID_ACTIONS}"
            )
        for c in REQUIRED_COLS:
            if not r.get(c):
                raise SystemExit(
                    f"error: {path} line {i}: column {c!r} must be non-empty"
                )
    return rows


def apply_overrides(
    parsed: list[dict], overrides: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Return (final_relations, audit_log).

    audit_log has one entry per override applied: ``action``, the edge it
    affected, and a ``result`` field (``applied`` or an error reason).
    """
    # Index parsed edges for quick lookup
    by_pair: dict[tuple[str, str], dict] = {
        (r["from_meter"], r["to_meter"]): dict(r) for r in parsed
    }
    final: dict[tuple[str, str], dict] = dict(by_pair)
    audit: list[dict] = []

    for ov in overrides:
        action = ov["action"]
        f, t = ov["from_meter"], ov["to_meter"]
        tag = f"override_{ov['date']}_{ov['author']}"
        base = {
            "action": action,
            "from_meter": f,
            "to_meter": t,
            "reason": ov["reason"],
            "date": ov["date"],
            "author": ov["author"],
        }

        if action == "add":
            if (f, t) in final:
                audit.append({**base, "result": "skipped (edge already present)"})
                continue
            final[(f, t)] = {
                "from_meter": f,
                "to_meter": t,
                "coefficient": ov.get("coefficient") or "1.0",
                "derived_from": tag,
            }
            audit.append({**base, "result": "applied"})

        elif action == "remove":
            if (f, t) not in final:
                audit.append({**base, "result": "error (edge not present to remove)"})
                continue
            removed = final.pop((f, t))
            audit.append(
                {
                    **base,
                    "result": f"applied (removed {removed.get('derived_from', '?')})",
                }
            )

        elif action == "force_direction":
            if (f, t) in final:
                # The parser emitted (f, t); override says flip it to (t, f)
                orig = final.pop((f, t))
                final[(t, f)] = {
                    "from_meter": t,
                    "to_meter": f,
                    "coefficient": orig.get("coefficient", "1.0"),
                    "derived_from": f"{tag} [was {orig.get('derived_from','?')}]",
                }
                audit.append({**base, "result": "applied (flipped parser edge)"})
            elif (t, f) in final:
                audit.append(
                    {**base, "result": "skipped (edge already in forced direction)"}
                )
            else:
                audit.append(
                    {
                        **base,
                        "result": "error (no edge between these meters in parser output)",
                    }
                )

    return list(final.values()), audit


def write_relations(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["from_meter", "to_meter", "coefficient", "derived_from"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["from_meter"], r["to_meter"])):
            w.writerow({c: r.get(c, "") for c in cols})


def write_audit(path: Path, audit: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# topology_overrides — audit log", ""]
    if not audit:
        lines.append("_(no overrides applied)_")
    else:
        lines.append("| action | from | to | result | reason | date | author |")
        lines.append("|---|---|---|---|---|---|---|")
        for a in audit:
            lines.append(
                f"| `{a['action']}` | `{a['from_meter']}` | `{a['to_meter']}` | {a['result']} | {a['reason']} | {a['date']} | {a['author']} |"
            )
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    parsed_path = args.workstream_dir / "01_extracted" / "flow_schema_relations.csv"
    overrides_path = args.workstream_dir / "03_reconciliation" / "topology_overrides.csv"
    facit_path = args.workstream_dir / "03_reconciliation" / "facit_relations.csv"
    audit_path = args.workstream_dir / "03_reconciliation" / "overrides_audit.md"

    if not parsed_path.exists():
        print(f"error: {parsed_path} not found", file=sys.stderr)
        return 2

    parsed = load_relations(parsed_path)
    overrides = load_overrides(overrides_path)
    final, audit = apply_overrides(parsed, overrides)
    write_relations(facit_path, final)
    write_audit(audit_path, audit)

    n_applied = sum(1 for a in audit if a["result"].startswith("applied"))
    n_skipped = sum(1 for a in audit if a["result"].startswith("skipped"))
    n_error = sum(1 for a in audit if a["result"].startswith("error"))
    print(f"wrote {facit_path} ({len(final)} edges)")
    print(
        f"overrides: {len(overrides)} declared → "
        f"{n_applied} applied, {n_skipped} skipped, {n_error} error"
    )
    if audit:
        print(f"audit log: {audit_path}")
    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
