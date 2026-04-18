#!/usr/bin/env python3
"""Parse meter IDs into structured fields using AstraZeneca naming conventions.

One sibling extractor among several; writes ``01_extracted/meter_roles.csv``.
The output lets source_conflicts.py / reconciliation treat the ``_E`` energy-
variant, ``VM`` vs ``VMM`` drift, and role semantics (VP1 primary supply, VS1
secondary, Å1 steam inlet, VÅ9 heat-pump recovery) as first-class fields.

## Naming convention (per `docs_to_bric_parsing.md` §7)

- Flow schema:   uniform ``VMM##`` (no suffix).
- Excel labels:  inconsistent; often ``VM##`` or ``VMM##_E`` variants.
- Snowflake:     ``VM##`` flow meters and ``VMM##_E`` energy meters.
  ``_E`` is a naming variant, not a separate meter.

## Role vocabulary observed

| role  | media / meaning                                       |
|-------|-------------------------------------------------------|
| VP1   | Värme Primär 1 — primary heating supply (tillopp)     |
| VP2   | Värme Primär 2 — primary return (retur), or secondary |
| VS1   | Värme Sekundär 1 — secondary heating (radiators)      |
| VS2   | Värme Sekundär 2                                      |
| VÅ9   | Återvinning Värmepump — heat-pump recovery circuit    |
| VÅ2   | Alt recovery circuit                                  |
| Å1    | Ånga 1 — steam inlet                                  |
| KV1–5 | Tappvatten — domestic water                           |

The role prefix tells a reconciler which inlet to treat as principal on each
building's accounting formula and which orphan-meters are expected to be
terminal leaves (most VÅ9 are fed by off-page mains).

## Canonical form

For each observed meter we emit the canonical parser form
``B{building}.{role}_VMM{n}`` plus the raw variant(s) seen. This is what
``02_crosswalk/meter_id_map.csv`` uses as its facit_id.

Usage:
    python parse_meter_names.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# role → (media, description, expected_topology)
ROLE_CATALOG: dict[str, tuple[str, str, str]] = {
    "VP1": ("värme", "primary supply (tillopp)",
            "inline on primary main; usual principal inlet per building"),
    "VP2": ("värme", "primary return (retur) / alt primary",
            "often downstream of VP1 on the same loop"),
    "VP3": ("värme", "alt primary circuit",
            "usually parallel to VP1 on the + side of accounting formula"),
    "VS1": ("värme", "secondary heating (radiators, luftbeh)",
            "standalone secondary loop; typically terminal leaf"),
    "VS2": ("värme", "alt secondary heating",
            "standalone secondary loop; typically terminal leaf"),
    "VÅ9": ("värme", "heat-pump recovery (återvinning)",
            "usually terminal leaf fed by off-page mains"),
    "VÅ2": ("värme", "alt recovery circuit",
            "usually terminal leaf"),
    "Å1":  ("ånga",  "steam inlet",
            "primary inlet for steam; root of site-level steam tree"),
    "KV1": ("kallvatten", "tappvatten domestic cold",
            "intake meter; off-page upstream"),
    "VV1": ("tappvatten", "varmvatten supply", ""),
    "VVC1":("tappvatten", "varmvatten circulation", ""),
}


CANON_RE = re.compile(r"^(B\d+[A-Z]?)\.([A-ZÅÄÖ]+\d*)_V(MM?)(\d+)(?:_(E))?$")


def parse(meter: str) -> dict | None:
    """Return parsed fields, or None if the meter ID doesn't match."""
    m = CANON_RE.match(meter)
    if not m:
        return None
    building, role, mprefix, digits, e_suffix = m.groups()
    canonical = f"{building}.{role}_VMM{digits}"
    cat = ROLE_CATALOG.get(role, ("unknown", "", ""))
    return {
        "meter_id": meter,
        "canonical_id": canonical,
        "building": building.lstrip("B").rstrip("NSEW"),
        "role": role,
        "vmm_index": int(digits),
        "is_energy_variant": 1 if e_suffix == "E" else 0,
        "media": cat[0],
        "role_description": cat[1],
        "topology_hint": cat[2],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    ws: Path = args.workstream_dir

    # Gather meter IDs from every extractor we know about
    sources: list[tuple[str, Path]] = [
        ("flow_schema", ws / "01_extracted" / "flow_schema_meters.csv"),
        ("excel_formulas", ws / "01_extracted" / "excel_formulas.csv"),
        ("excel_intake", ws / "01_extracted" / "excel_intake_meters.csv"),
        ("excel_meters_used", ws / "01_extracted" / "excel_meters_used.csv"),
    ]

    raw_to_sources: dict[str, set[str]] = {}
    for label, path in sources:
        if not path.exists():
            continue
        with path.open() as f:
            reader = csv.DictReader(f)
            for r in reader:
                for col in ("meter_id", "canonical_id", "intake_meter"):
                    mid = r.get(col)
                    if mid:
                        raw_to_sources.setdefault(mid, set()).add(label)
                        break

    # Parse each; canonicalise
    parsed_rows: dict[str, dict] = {}
    unparseable: list[tuple[str, set[str]]] = []
    for raw, src in raw_to_sources.items():
        p = parse(raw)
        if p is None:
            unparseable.append((raw, src))
            continue
        can = p["canonical_id"]
        if can not in parsed_rows:
            parsed_rows[can] = {**p, "raw_variants": set(), "seen_in": set()}
        parsed_rows[can]["raw_variants"].add(raw)
        parsed_rows[can]["seen_in"].update(src)

    out = ws / "01_extracted" / "meter_roles.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "canonical_id", "building", "role", "vmm_index",
        "has_energy_variant", "media", "role_description", "topology_hint",
        "raw_variants", "seen_in",
    ]
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for can in sorted(parsed_rows):
            r = parsed_rows[can]
            has_e = int(any(v.endswith("_E") for v in r["raw_variants"]))
            w.writerow([
                can,
                r["building"],
                r["role"],
                r["vmm_index"],
                has_e,
                r["media"],
                r["role_description"],
                r["topology_hint"],
                "|".join(sorted(r["raw_variants"])),
                "|".join(sorted(r["seen_in"])),
            ])

    print(f"wrote {out} ({len(parsed_rows)} canonical meters across "
          f"{len({r['building'] for r in parsed_rows.values()})} buildings)")
    if unparseable:
        print(f"  {len(unparseable)} meter IDs did not match the canonical form — review:")
        for raw, src in unparseable[:10]:
            print(f"    {raw}  (seen in {'|'.join(sorted(src))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
