"""CLI entry point for the reference site generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from ontology import write_dataset

from . import abbey_road
from .readings import generate_readings

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUT = REPO_ROOT / "data" / "reference_site" / "abbey_road"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reference site CSVs.")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for synthetic reading generation (default: 42)",
    )
    args = parser.parse_args()

    ds = abbey_road.build()
    ds.readings = generate_readings(ds, seed=args.seed)
    write_dataset(ds, args.out)
    print(
        f"Wrote {len(ds.meters)} meters and {len(ds.readings)} readings to {args.out}"
    )


if __name__ == "__main__":
    main()
