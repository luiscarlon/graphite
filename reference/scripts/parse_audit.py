#!/usr/bin/env python3
"""Diff a parsed flow_schema_relations.csv against a hand-curated
expected_relations.csv fixture.

Emits three categories of discrepancy to stdout and to a markdown audit file
under ``{workstream}/04_validation/parse_audit.md``:

- ``parser_missed`` — edges in the fixture not in the parser output.
- ``parser_extra`` — edges in the parser output not in the fixture.
- ``direction_flip`` — edges where both (from, to) and (to, from) are accepted
  by opposite sides (i.e. parser put A→B, fixture says B→A).

The expected_relations fixture columns are a strict subset of the parser's:
``from_meter,to_meter,coefficient,note`` (note is free text, human-readable).

Non-zero exit when any ``parser_missed`` or ``direction_flip`` is present.
``parser_extra`` alone is a warning (could be legitimate new edges the
fixture hasn't caught up to).

Usage:
    python parse_audit.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _load(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    with path.open() as f:
        reader = csv.DictReader(f)
        return [(r["from_meter"], r["to_meter"]) for r in reader]


def _diff(
    parsed: list[tuple[str, str]], expected: list[tuple[str, str]]
) -> tuple[list, list, list]:
    parsed_set = set(parsed)
    expected_set = set(expected)

    missed: list[tuple[str, str]] = []
    flipped: list[tuple[str, str, str, str]] = []
    for e in expected_set:
        if e in parsed_set:
            continue
        rev = (e[1], e[0])
        if rev in parsed_set:
            flipped.append((e[0], e[1], rev[0], rev[1]))
        else:
            missed.append(e)

    extra: list[tuple[str, str]] = []
    accounted_in_flip = {(a, b) for _, _, a, b in flipped}
    for p in parsed_set:
        if p in expected_set or p in accounted_in_flip:
            continue
        extra.append(p)

    return (
        sorted(missed),
        sorted(extra),
        sorted(flipped),
    )


def _write_md(
    path: Path,
    missed: list,
    extra: list,
    flipped: list,
    parsed_n: int,
    expected_n: int,
) -> None:
    lines = [
        "# parse audit",
        "",
        f"- parser edges:    **{parsed_n}**",
        f"- expected edges:  **{expected_n}**",
        f"- parser_missed:   **{len(missed)}**",
        f"- parser_extra:    **{len(extra)}**",
        f"- direction_flip:  **{len(flipped)}**",
        "",
    ]

    if missed:
        lines += [
            "## parser_missed — edges in fixture but not in parser output",
            "",
            "Parser needs to be improved, or the user should add an `add` row to",
            "`topology_overrides.csv` to close the gap.",
            "",
            "| from_meter | to_meter |",
            "|---|---|",
        ]
        for f, t in missed:
            lines.append(f"| `{f}` | `{t}` |")
        lines.append("")

    if flipped:
        lines += [
            "## direction_flip — parser got the direction wrong",
            "",
            "Expected: parent→child (flow direction). Add `force_direction` rows",
            "to `topology_overrides.csv`.",
            "",
            "| parser emitted | should be |",
            "|---|---|",
        ]
        for ef, et, pf, pt in flipped:
            lines.append(f"| `{pf}` → `{pt}` | `{ef}` → `{et}` |")
        lines.append("")

    if extra:
        lines += [
            "## parser_extra — parser has edges the fixture doesn't",
            "",
            "Either the fixture is incomplete (update it) or the parser is",
            "hallucinating. Review each one.",
            "",
            "| from_meter | to_meter |",
            "|---|---|",
        ]
        for f, t in extra:
            lines.append(f"| `{f}` | `{t}` |")
        lines.append("")

    if not (missed or extra or flipped):
        lines += [
            "## parser matches fixture ✓",
            "",
            "All expected edges present, no direction flips, no extras.",
        ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument(
        "--parsed",
        type=Path,
        help="Path to parsed relations CSV (default: 01_extracted/flow_schema_relations.csv)",
    )
    ap.add_argument(
        "--expected",
        type=Path,
        help="Path to expected relations fixture (default: 03_reconciliation/expected_relations.csv)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        help="Path to write audit markdown (default: 04_validation/parse_audit.md)",
    )
    args = ap.parse_args()

    ws: Path = args.workstream_dir
    parsed_path = args.parsed or ws / "01_extracted" / "flow_schema_relations.csv"
    expected_path = args.expected or ws / "03_reconciliation" / "expected_relations.csv"
    out_path = args.out or ws / "04_validation" / "parse_audit.md"

    if not expected_path.exists():
        print(
            f"no expected_relations.csv yet at {expected_path}; nothing to audit",
            file=sys.stderr,
        )
        return 0

    parsed = _load(parsed_path)
    expected = _load(expected_path)
    missed, extra, flipped = _diff(parsed, expected)
    _write_md(out_path, missed, extra, flipped, len(parsed), len(expected))

    print(
        f"parser: {len(parsed)} edges | expected: {len(expected)} edges | "
        f"missed: {len(missed)} | extra: {len(extra)} | flipped: {len(flipped)}"
    )
    print(f"wrote {out_path}")
    return 0 if not (missed or flipped) else 1


if __name__ == "__main__":
    sys.exit(main())
