#!/usr/bin/env python3
"""Run the full multi-source extraction + validation pipeline for a workstream.

Usage:
    python regenerate_workstream.py WORKSTREAM_DIR [--skip-ontology]

Reads the workstream's config (hard-coded per (site, media) at the top of
this file — kept small; add new rows when new workstreams arrive). Then
drives every extractor and validator in dependency order.

Pipeline (per `docs_to_bric_parsing.md` §11.7):

  01_extracted/    ← extractors (parser, xlsx, timeseries, excel_relations, names, VLM[optional])
  02_crosswalk/    ← human-curated (not regenerated)
  03_reconciliation/
      facit_relations.csv  ← apply_topology_overrides.py (parser + human overrides)
      decisions.md         ← human-authored, never touched
      open_questions.md    ← human-authored, never touched
  04_validation/   ← source_conflicts, parse_audit, conservation, accounting, audit PNG
  05_ontology/     ← build_ontology.py (optional)
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "reference" / "scripts"
TIMESERIES_CSV = REPO / "reference" / "snowflake_meter_readings" / "Untitled 1_2026-04-16-1842.csv"


@dataclass
class Config:
    name: str            # workstream folder name, e.g. "gtn_varme"
    site: str            # "GTN" or "SNV"
    media: str           # Excel sheet name — "Värme" / "Ånga" / ...
    media_slug: str      # ontology short name — "VARME" / "ANGA"
    pdf_sources: list[str]  # --sources for parse_flow_schema.py
    primary_role: str    # principal inlet role for excel_relations.py
    quantity: str        # Snowflake QUANTITY filter
    unit: str = "Megawatt-Hour"  # Brick/QUDT unit for sensors
    has_pdf: bool = True         # whether a flow schema PDF exists


CONFIGS: dict[str, Config] = {
    "gtn_varme": Config(
        name="gtn_varme",
        site="GTN",
        media="Värme",
        media_slug="VARME",
        pdf_sources=["B600.VP1_VMM61", "B600.VS1_VMM61"],
        primary_role="VP1",
        quantity="Active Energy Delivered(Mega)",
    ),
    "gtn_anga": Config(
        name="gtn_anga",
        site="GTN",
        media="Ånga",
        media_slug="ANGA",
        pdf_sources=["B600S.Å1_VMM71", "B600N.Å1_VMM71"],
        primary_role="Å1",
        quantity="Active Energy Delivered(Mega)",  # steam meters report as energy on Snowflake
    ),
    "gtn_kyla": Config(
        name="gtn_kyla",
        site="GTN",
        media="Kyla",
        media_slug="KYLA",
        pdf_sources=[],
        primary_role="KB1",
        quantity="Active Energy Delivered(Mega)",
        has_pdf=False,
    ),
    "gtn_el": Config(
        name="gtn_el",
        site="GTN",
        media="EL",
        media_slug="EL",
        pdf_sources=[],
        primary_role="T1",
        quantity="Active Energy Delivered",
        unit="KiloW-HR",
        has_pdf=False,
    ),
}


def run(cmd: list[str], *, optional: bool = False) -> None:
    pretty = " ".join(shlex.quote(c) for c in cmd)
    print(f"\n$ {pretty}", flush=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        if optional:
            print(f"  (optional step failed with exit {e.returncode}; continuing)", file=sys.stderr)
        else:
            raise
    except FileNotFoundError as e:
        if optional:
            print(f"  (optional input missing: {e}; continuing)", file=sys.stderr)
        else:
            raise


def pipeline(ws: Path, cfg: Config, *, skip_ontology: bool) -> None:
    py = sys.executable

    print(f"\n=========== {cfg.name}: extractors ===========")

    # Layer 1 — Flow schema PDF
    pdf = ws / "00_inputs" / "flow_schema.pdf"
    if pdf.exists():
        run([
            py, str(SCRIPTS / "parse_flow_schema.py"),
            str(pdf),
            "--sources", ",".join(cfg.pdf_sources),
            "--out-dir", str(ws / "01_extracted"),
            "--prefix", "flow_schema",
            "--preview", str(ws / "01_extracted" / "flow_schema_preview.html"),
        ])
    else:
        print(f"  (no flow_schema.pdf at {pdf}; skipping layer 1)")

    # Layer 2a — Excel raw extraction
    xlsx = ws / "00_inputs" / "excel_source.xlsx"
    if xlsx.exists():
        run([
            py, str(SCRIPTS / "parse_reporting_xlsx.py"),
            str(xlsx),
            "--media", cfg.media,
            "--out-dir", str(ws / "01_extracted"),
        ])
    else:
        print(f"  (no excel_source.xlsx at {xlsx}; skipping layer 2a)")

    # Layer 2b — Excel → candidate relations
    run([
        py, str(SCRIPTS / "excel_relations.py"),
        str(ws),
        "--primary-role", cfg.primary_role,
    ], optional=True)

    # Layer 3 — Timeseries slice
    crosswalk = ws / "02_crosswalk" / "meter_id_map.csv"
    if TIMESERIES_CSV.exists() and crosswalk.exists():
        run([
            py, str(SCRIPTS / "slice_timeseries.py"),
            str(TIMESERIES_CSV),
            "--meters-csv", str(crosswalk),
            "--quantity", cfg.quantity,
            "--out-dir", str(ws / "01_extracted"),
        ], optional=True)
    else:
        print("  (timeseries or crosswalk missing; skipping layer 3)")

    # Detect meter swaps/glitches/offlines from daily timeseries
    daily = ws / "01_extracted" / "timeseries_daily.csv"
    if daily.exists():
        run([py, str(SCRIPTS / "detect_meter_swaps.py"), str(ws)], optional=True)

    # Naming — meter roles + canonical IDs
    run([py, str(SCRIPTS / "parse_meter_names.py"), str(ws)], optional=True)

    # Layer 3 — Naming-derived relations (uses meter_roles.csv)
    run([py, str(SCRIPTS / "naming_relations.py"), str(ws)], optional=True)

    print(f"\n=========== {cfg.name}: merge layers 1–3 ===========")

    # First merge: PDF + Excel + naming (no timeseries yet)
    run([
        py, str(SCRIPTS / "apply_topology_overrides.py"),
        str(ws),
    ])

    # Layer 4 — Timeseries-derived relations (needs merged facit from layers 1–3)
    ts_monthly = ws / "01_extracted" / "timeseries_monthly.csv"
    facit_rel = ws / "03_reconciliation" / "facit_relations.csv"
    if ts_monthly.exists() and facit_rel.exists():
        run([py, str(SCRIPTS / "timeseries_relations.py"), str(ws)], optional=True)

        print(f"\n=========== {cfg.name}: re-merge with layer 4 ===========")
        # Re-merge: now includes timeseries_relations.csv
        run([
            py, str(SCRIPTS / "apply_topology_overrides.py"),
            str(ws),
        ])

    # Building-level virtual meters (from accounting formulas)
    facit_acc = ws / "03_reconciliation" / "facit_accounting.csv"
    if facit_acc.exists():
        run([
            py, str(SCRIPTS / "generate_building_virtuals.py"),
            str(ws),
            "--media", cfg.media_slug,
        ], optional=True)

    print(f"\n=========== {cfg.name}: validation ===========")

    # 04_validation — source_conflicts (reads 01_extracted)
    run([py, str(SCRIPTS / "source_conflicts.py"), str(ws)])

    # 04_validation — parse_audit (only if expected_relations.csv exists)
    expected = ws / "03_reconciliation" / "expected_relations.csv"
    if expected.exists():
        run([py, str(SCRIPTS / "parse_audit.py"), str(ws)], optional=True)
    else:
        print("  (no expected_relations.csv; skipping parse_audit)")

    # 04_validation — conservation (needs facit_relations + timeseries)
    facit_rel = ws / "03_reconciliation" / "facit_relations.csv"
    ts_monthly = ws / "01_extracted" / "timeseries_monthly.csv"
    if facit_rel.exists() and ts_monthly.exists() and crosswalk.exists():
        run([
            py, str(SCRIPTS / "validate_conservation.py"),
            "--facit-relations", str(facit_rel),
            "--timeseries-monthly", str(ts_monthly),
            "--crosswalk", str(crosswalk),
            "--out-dir", str(ws / "04_validation"),
        ], optional=True)

    # 04_validation — accounting (only if facit_accounting.csv exists — gtn_varme does, gtn_anga doesn't)
    facit_acc = ws / "03_reconciliation" / "facit_accounting.csv"
    if facit_acc.exists() and ts_monthly.exists() and crosswalk.exists():
        run([
            py, str(SCRIPTS / "validate_accounting.py"),
            "--accounting", str(facit_acc),
            "--timeseries", str(ts_monthly),
            "--crosswalk", str(crosswalk),
            "--out-dir", str(ws / "04_validation"),
        ], optional=True)

    # 04_validation — audit PNG
    if pdf.exists():
        run([
            py, str(SCRIPTS / "render_audit_png.py"),
            str(ws),
            "--relations", str(facit_rel),
        ], optional=True)

    # 05_ontology
    if not skip_ontology:
        print(f"\n=========== {cfg.name}: ontology ===========")
        run([
            py, str(SCRIPTS / "build_ontology.py"),
            str(ws),
            "--campus", cfg.site,
            "--media", cfg.media_slug,
            "--database", "ion_sweden_bms",
            "--unit", cfg.unit,
            "--emit-shared",
        ], optional=True)

        # Phase 6: outage patches
        swaps_file = ws / "01_extracted" / "meter_swaps.csv"
        if swaps_file.exists():
            print(f"\n=========== {cfg.name}: outage patches ===========")
            run([py, str(SCRIPTS / "generate_outage_patches.py"), str(ws)], optional=True)

    print(f"\n=========== {cfg.name}: done ===========\n")
    print("  NOTE: Annotations are curated by the analyst, not auto-generated.")
    print("  Review meter_swaps.csv, conservation, and source_conflicts manually.")
    print("  Write annotations with specific evidence in 05_ontology/annotations.csv.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workstream_dir", type=Path)
    ap.add_argument("--skip-ontology", action="store_true")
    args = ap.parse_args()

    ws = args.workstream_dir.resolve()
    name = ws.name
    if name not in CONFIGS:
        print(f"error: no config for workstream {name!r}; edit CONFIGS in this script",
              file=sys.stderr)
        return 2
    pipeline(ws, CONFIGS[name], skip_ontology=args.skip_ontology)
    return 0


if __name__ == "__main__":
    sys.exit(main())
