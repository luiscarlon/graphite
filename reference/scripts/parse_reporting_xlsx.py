#!/usr/bin/env python3
"""Extract a media-specific slice of an AstraZeneca monthly-reporting workbook.

The workbooks (``gtn.xlsx`` / ``snv.xlsx``) carry one sheet per media (Ånga,
Kyla, Värme, Kallvatten, Kyltornsvatten, EL).  Each building row follows a
fixed pattern:

  col B           building number
  cols C..N       monthly consumption (pulled via XLOOKUP from the STRUX sheet)
  col O           yearly total (SUM)
  col P           Kommentar (human-readable note)
  cols S..W       meter IDs used in the accounting formula
                  formula = XLOOKUP(S) + XLOOKUP(T) − XLOOKUP(U) − XLOOKUP(V) − XLOOKUP(W)

The S/T columns are *additive* supply meters; U/V/W are *subtractive* — they
represent downstream consumers whose flow should not be attributed to this
building (they get accounted on their own row).  That asymmetry is what
encodes allocation; preserving it is the whole point of this extractor.

Outputs (written to the ``--out-dir`` directory):

- ``excel_formulas.csv``     — one row per (building, role, meter_id)
- ``excel_comments.md``      — cell comments + Kommentar column contents
- ``excel_tabs_inventory.md`` — every sheet in the workbook with dimensions and role
- ``excel_meters_used.csv``  — unique meter IDs referenced on the selected sheet
- ``excel_intake_meters.csv`` — STRUX rows for this media (the meter catalog)

Usage::

    python parse_reporting_xlsx.py \\
        reference/monthly_reporting_documents/inputs/gtn.xlsx \\
        --media Ånga \\
        --out-dir reference/media_workstreams/gtn_anga/01_extracted
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import warnings
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.formula import ArrayFormula

# openpyxl warns about conditional-formatting and unsupported extensions for
# these workbooks; the warnings are noise for our purposes.
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# Match each XLOOKUP term with its sign in the formula. First term has no
# leading sign (implicit +); subsequent terms carry + or −. Cell ref is a
# column-letters-plus-row, e.g. ``S11`` or ``AA11``.
FORMULA_TERM_RE = re.compile(
    r"([+\-−])?\s*(?:_xlfn\.)?XLOOKUP\s*\(\s*([A-Z]+)(\d+)\s*,",
)


def _column_letter_to_index(letters: str) -> int:
    """A → 1, B → 2, ..., Z → 26, AA → 27, etc."""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def parse_formula_signs(formula_text: str, row: int) -> dict[str, str]:
    """Return {column_letter: '+' | '−'} for every XLOOKUP term referencing `row`.

    The first term in the formula has no leading sign and is treated as '+'.
    """
    out: dict[str, str] = {}
    first = True
    for m in FORMULA_TERM_RE.finditer(formula_text):
        raw_sign, col_letters, term_row = m.group(1), m.group(2), int(m.group(3))
        if term_row != row:
            continue
        if first and not raw_sign:
            sign = "+"
        else:
            sign = "−" if raw_sign in ("-", "−") else "+"
        out[col_letters] = sign
        first = False
    return out


def extract_building_formulas(ws) -> list[dict]:
    """Scan a media sheet and return one record per referenced meter cell.

    Unlike ånga, where every row uses the 5-term S+T−U−V−W accounting
    pattern, other media sheets (e.g. Värme) have variable-length formulas
    with different sign combinations. Each row's formula is parsed and the
    sign per column is taken from the formula text itself.
    """
    records: list[dict] = []
    for row in range(8, ws.max_row + 1):
        building = ws.cell(row=row, column=2).value  # col B
        if building is None:
            continue
        comment_cell = ws.cell(row=row, column=16).value  # col P
        factor_cell = ws.cell(row=row, column=18).value  # col R

        c_val = ws.cell(row=row, column=3).value
        formula_text = ""
        if isinstance(c_val, ArrayFormula):
            formula_text = c_val.text or ""
        elif isinstance(c_val, str) and c_val.startswith("="):
            formula_text = c_val

        col_signs = parse_formula_signs(formula_text, row)
        if not col_signs:
            continue

        for col_letter, sign in sorted(col_signs.items(), key=lambda kv: _column_letter_to_index(kv[0])):
            v = ws[f"{col_letter}{row}"].value
            if v is None or v == "":
                continue
            role = "add" if sign == "+" else "sub"
            records.append(
                {
                    "row": row,
                    "building": building,
                    "role": role,
                    "sign": sign,
                    "column": col_letter,
                    "meter_id": str(v),
                    "kommentar": comment_cell if comment_cell else "",
                    "faktor": factor_cell if factor_cell is not None else "",
                    "n_terms": len(col_signs),
                }
            )
    return records


def extract_cell_comments(ws) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in ws.iter_rows():
        for cell in row:
            if cell.comment:
                out.append((cell.coordinate, cell.comment.text))
    return out


def extract_strux_media(wb, media_label: str) -> list[dict]:
    """Return rows from the STRUX sheet matching the given media label."""
    if "STRUX" not in wb.sheetnames:
        return []
    ws = wb["STRUX"]
    header = [ws.cell(row=2, column=c).value for c in range(1, ws.max_column + 1)]
    out: list[dict] = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        if not any(row):
            continue
        rec = dict(zip(header, row, strict=False))
        mediaslag = (rec.get("Mediaslag") or "").strip()
        if mediaslag.lower() == media_label.lower():
            out.append(
                {
                    "anlaggning": rec.get("Anläggning") or "",
                    "mediaslag": mediaslag,
                    "avlasning": rec.get("Avläsning") or "",
                    "matarbeteckning": rec.get("Mätarbeteckning") or "",
                    "betjanar": rec.get("Betjänar") or "",
                    "matarstallning_eller_forbrukning": rec.get("Mätarställning eller förbrukning") or "",
                    "enhet": rec.get("Enhet") or "",
                }
            )
    return out


def inventory_sheets(wb) -> list[dict]:
    out: list[dict] = []
    for name in wb.sheetnames:
        ws = wb[name]
        out.append(
            {
                "sheet": name,
                "rows": ws.max_row,
                "cols": ws.max_column,
                "hidden": ws.sheet_state != "visible",
            }
        )
    return out


def write_formulas_csv(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["building", "row", "role", "sign", "column", "meter_id", "kommentar", "faktor", "n_terms"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow({c: r.get(c, "") for c in cols})


def write_meters_used_csv(path: Path, records: list[dict]) -> None:
    seen: dict[str, dict] = {}
    for r in records:
        mid = r["meter_id"]
        if mid not in seen:
            seen[mid] = {
                "meter_id": mid,
                "roles": set(),
                "buildings": set(),
            }
        seen[mid]["roles"].add(r["role"])
        seen[mid]["buildings"].add(str(r["building"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meter_id", "roles", "buildings"])
        for mid in sorted(seen):
            rec = seen[mid]
            w.writerow(
                [mid, "|".join(sorted(rec["roles"])), "|".join(sorted(rec["buildings"]))]
            )


def write_intake_meters_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("# no STRUX rows matched; skip\n")
        return
    cols = list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_comments_md(path: Path, media: str, sheet_comments: list[tuple[str, str]], kommentar_entries: list[dict]) -> None:
    lines = [f"# Excel comments — {media} sheet", ""]
    if sheet_comments:
        lines += ["## Cell comments (openpyxl .comment)", ""]
        for coord, text in sheet_comments:
            text_clean = text.replace("\n", " · ")
            lines.append(f"- **{coord}** — {text_clean}")
        lines.append("")
    else:
        lines += ["## Cell comments (openpyxl .comment)", "", "_(none)_", ""]
    lines += ["## `Kommentar` column (col P) non-empty entries", ""]
    any_entry = False
    for e in kommentar_entries:
        if not e.get("kommentar"):
            continue
        any_entry = True
        lines.append(f"- row {e['row']} (building {e['building']}) — {e['kommentar']}")
    if not any_entry:
        lines.append("_(none)_")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def write_tabs_inventory_md(path: Path, media: str, sheets: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Excel tabs inventory",
        "",
        f"Workbook slice relevant for **{media}**. The `{media}` sheet carries the per-building accounting formulas; STRUX is the meter catalog; Avläsning/PME/PME_EL are the underlying reading sources that the accounting formulas XLOOKUP into.",
        "",
        "| sheet | rows | cols | hidden | role |",
        "|---|---:|---:|:---:|---|",
    ]
    roles = {
        "Intro": "workbook documentation — what each tab does",
        "Rapport Site": "site-level rollup",
        "Rapport Byggnad": "per-building rollup",
        "Total GTN": "purchased-energy totals for external reporting",
        "EL": "electricity per-building accounting",
        "Kyla": "cooling per-building accounting",
        "Värme": "heating per-building accounting",
        "Ånga": "steam per-building accounting — this workstream",
        "Kallvatten": "cold-water per-building accounting",
        "Kyltornsvatten": "cooling-tower-water per-building accounting",
        "STRUX": "meter catalog — one row per meter with monthly values; XLOOKUP target for all media sheets",
        "Kontroll FV-mätare": "district-heating meter verification",
        "Evidence Gärtuna": "stakeholder evidence dump",
        "VÅ9 alla mätare": "VÅ9 (heat-pump recovery) meter inventory",
        "VÅ9 Nyckeltal": "VÅ9 KPIs",
        "PME_EL": "automatic electricity readings",
        "PME": "automatic non-electricity readings (energy, flow meters)",
        "Avläsning": "manual readings (e.g. sea-water meters not connected)",
        "Site": "building → site lookup (hidden)",
        "Lista": "enumeration: media types, units (hidden)",
    }
    for s in sheets:
        marker = "hidden" if s["hidden"] else ""
        role = roles.get(s["sheet"], "")
        lines.append(f"| {s['sheet']} | {s['rows']} | {s['cols']} | {marker} | {role} |")
    lines += ["", "**Named ranges of interest:**", ""]
    lines += [
        "- `STRUX_Mätare` = `STRUX!$D$3:$D$4923` — meter ID column; XLOOKUP target from all media sheets.",
        "- `STRUX_data` = `STRUX!$H$3:$S$4923` — monthly values (Jan..Dec) for every meter in STRUX.",
        "- `STRUX_mån` = `STRUX!$H$2:$S$2` — monthly header row.",
        "- `Avläs_data` / `Avläs_mätare` / `Avläs_mån` — the same pattern for manually-recorded meters.",
        "- `PME_data` / `PME_mätare` / `PME_mån` — the same for automatic (BMS) meters.",
        "- `EL_data` / `EL_mätare` / `EL_mån` — same for electricity meters.",
        "- `Site_GTN` = `Site!$A$1:$B$64` — building → site lookup used by the media sheets' col A.",
        "",
        "**Per-row accounting formula used on every media sheet (col C..N):**",
        "",
        "```",
        "= XLOOKUP(S{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)",
        "+ XLOOKUP(T{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)",
        "− XLOOKUP(U{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)",
        "− XLOOKUP(V{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)",
        "− XLOOKUP(W{row}, STRUX_Mätare, STRUX_data, 0, 0, 1)",
        "```",
        "",
        "Semantics: S/T are *additive* supply meters (flows into this building); U/V/W are *subtractive* — meters downstream of the supply that belong to other buildings and get attributed in their own rows. The subtraction is what encodes topology in the accounting view.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("--media", required=True, help="Sheet name: Ånga, Kyla, Värme, Kallvatten, Kyltornsvatten, EL")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    if not args.xlsx.exists():
        print(f"error: {args.xlsx} not found", file=sys.stderr)
        return 2

    wb = load_workbook(args.xlsx, data_only=False)
    if args.media not in wb.sheetnames:
        print(f"error: sheet {args.media!r} not found. Available: {wb.sheetnames}", file=sys.stderr)
        return 3
    ws = wb[args.media]

    records = extract_building_formulas(ws)
    cell_comments = extract_cell_comments(ws)
    strux_rows = extract_strux_media(wb, args.media)
    sheets = inventory_sheets(wb)

    out = args.out_dir
    write_formulas_csv(out / "excel_formulas.csv", records)
    write_meters_used_csv(out / "excel_meters_used.csv", records)
    write_intake_meters_csv(out / "excel_intake_meters.csv", strux_rows)
    write_comments_md(out / "excel_comments.md", args.media, cell_comments, records)
    write_tabs_inventory_md(out / "excel_tabs_inventory.md", args.media, sheets)

    n_terms_distribution: dict[int, int] = {}
    for r in records:
        n_terms_distribution[r["n_terms"]] = n_terms_distribution.get(r["n_terms"], 0) + 1
    print(f"wrote {out / 'excel_formulas.csv'} ({len(records)} meter refs from {len({r['building'] for r in records})} buildings)")
    print(f"wrote {out / 'excel_meters_used.csv'} ({len({r['meter_id'] for r in records})} unique meters)")
    print(f"wrote {out / 'excel_intake_meters.csv'} ({len(strux_rows)} STRUX rows matching mediaslag={args.media!r})")
    print(f"wrote {out / 'excel_comments.md'} ({len(cell_comments)} cell comments, "
          f"{sum(1 for r in records if r.get('kommentar'))} Kommentar entries)")
    print(f"wrote {out / 'excel_tabs_inventory.md'}")
    if len(n_terms_distribution) > 1:
        dist = ", ".join(f"{k}-term: {v}" for k, v in sorted(n_terms_distribution.items()))
        print(f"formula term counts: {dist}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
