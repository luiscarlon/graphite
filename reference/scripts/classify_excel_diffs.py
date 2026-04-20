#!/usr/bin/env python3
"""Generate excel_comparison_annotations.csv for every workstream.

For each (site, media) workstream:
  - Load the assembled site bundle for that site.
  - Compute SUM(meter_net) per (building_id, month) restricted to media.
  - Join cached Excel values from excel_building_totals.csv.
  - Classify each row with a short `reason` tag and `explanation`.
  - Write reference/media_workstreams/{ws}/05_ontology/excel_comparison_annotations.csv.

Classification uses:
  - a magnitude threshold (<1000 kWh/m3 AND <0.1% → match),
  - hand-curated overrides keyed on (building_id, media) drawn from each
    workstream's decisions.md / open_questions.md / status table.

Keep the vocabulary flexible and short; these rows are snapshots, not targets.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import duckdb

REPO = Path('/Users/luis/dev/graphite')
VIEWS_SQL = REPO / 'packages/calc/src/calc/sql/views.sql'
MONTHS = ('2026-01', '2026-02')

WORKSTREAMS = [
    # (workstream_dir, site_dir, media_type_id)
    ('gtn_anga', 'gartuna', 'ANGA'),
    ('gtn_varme', 'gartuna', 'VARME'),
    ('gtn_kyla', 'gartuna', 'KYLA'),
    ('gtn_kallvatten', 'gartuna', 'KALLVATTEN'),
    ('gtn_kyltornsvatten', 'gartuna', 'KYLTORNSVATTEN'),
    ('gtn_el', 'gartuna', 'EL'),
    ('snv_el', 'snackviken', 'EL'),
    ('snv_anga', 'snackviken', 'ANGA'),
    ('snv_varme', 'snackviken', 'VARME'),
    ('snv_kyla', 'snackviken', 'KYLA'),
    ('snv_kallvatten', 'snackviken', 'KALLVATTEN'),
    ('snv_sjovatten', 'snackviken', 'SJOVATTEN'),
]

# Per-workstream curated overrides.
# Each entry: (building_id, reason, explanation_template). Applies to both months
# unless a month-specific tuple is given as (building_id, month, reason, explanation).
CURATED: dict[str, list] = {
    'gtn_anga': [
        ('B600', 'match_intake', 'B600 is the site intake; residual vs per-building sum is expected.'),
        ('B616', 'excel_stale', 'Meter live (~900 MWh/month) but Excel attributes 0 — known "Excel=0 but meter live" misallocation.'),
    ],
    'gtn_varme': [
        ('B833', 'meter_outage', 'B833 outage patch captures consumption that Excel\'s frozen VP1 counter misses.'),
    ],
    'gtn_kyla': [
        ('B658', 'excel_stale', 'Meter live but Excel attributes 0 — known "Excel=0 but meter live" misallocation.'),
        ('B623', 'excel_bug', 'B623 double-counted: appears as + term for B623 AND inside the B600-KB2 pool formula. Conservation violation in the source; topology can only match one side.'),
        ('B612', 'excel_cooked_coefficient', 'Excel uses fractional 0.9×B637 subtraction; views.sql has no fractional-subtract primitive so 1–3 MWh residuals are expected.'),
        ('B641', 'excel_cooked_coefficient', 'Excel uses fractional 0.1×B637 subtraction; views.sql has no fractional-subtract primitive so 1–3 MWh residuals are expected.'),
        ('B611', 'data_quality_artifact', 'Dead pool meter (B653 died 2025-10-09) combined with active downstream sub-meters yields physically-nonsensical negative value. Topology faithful to the source.'),
        ('B833', 'data_quality_artifact', 'Bi-daily BMS sensor (B833.KB1_GF4 reads ~31 times over 59 days). Negative residual is a sampling artifact.'),
    ],
    'gtn_el': [
        ('B631', 'strux_only_meter', 'B631.T4-A3 and B631.T4-C4 are STRUX-only (no BMS data). Ontology has nothing to attribute.'),
        ('B613', 'strux_only_meter', 'B613.T4-C1 is STRUX-only (no BMS data). Ontology has nothing to attribute.'),
        ('B611', 'strux_only_meter', 'B611.T4 trunk in BMS includes T4-A3/C1/C4 flow; Excel subtracts those via STRUX, ontology cannot.'),
        ('B664', 'excel_stale', 'Excel formula attributes 0 to B664; T42-2-1 actually feeds this building. Mirror delta vs B665.'),
        ('B665', 'excel_stale', 'Excel over-attributes T42-2-1 to B665. Mirror delta vs B664.'),
        ('B652', 'excel_bug', 'Residual from the B612 T8-A3-A14-112 double-subtraction mirror edge; ~0.6 MWh redistribution is approximate.'),
        ('B660', '2026-02', 'under_investigation', 'Jan matches within 609 kWh, Feb drifts -141 MWh (-2.2%). Root cause not yet diagnosed.'),
    ],
    'snv_el': [
        # STRUX-only buildings
        ('B209', 'strux_only_meter', 'B209.T21 / T32 / T83 STRUX-only; topology cannot contribute BMS flow.'),
        ('B304', 'strux_only_meter', 'B304 formula depends on STRUX-only summary meters absent from BMS.'),
        ('B334', 'strux_only_meter', 'T87-T92 summaries are STRUX-only (no BMS data); ~95% gap vs Excel.'),
        ('B204', 'excel_cooked_coefficient', 'Cross-building fractional pool: 0.75 × B209.T32-4-2. No views.sql primitive.'),
        ('B205', 'excel_cooked_coefficient', 'Cross-building fractional pool: 0.25 × B209.T32-4-2. No views.sql primitive.'),
        ('B310', 'excel_cooked_coefficient', 'Cross-building fractional pools: 0.5×T26S-net, 1/3×T29, 0.4×T49-net. No views.sql primitive.'),
        ('B311', 'excel_cooked_coefficient', 'Cross-building fractional pools: 0.5×T26S-net, 2/3×T29. No views.sql primitive.'),
        ('B313', 'excel_cooked_coefficient', 'Cross-building fractional pool: 0.1×T49-net. No views.sql primitive.'),
        ('B317', 'excel_cooked_coefficient', 'Cross-building fractional pool: 0.5×T49-net. No views.sql primitive.'),
        # Complex-formula anomalies from open_questions.md
        ('B305', 'under_investigation', 'Complex-formula undercount (−23/−21 MWh). Hypothesis: sub-meter +terms zeroed by hasSubMeter edges to T10 stems. See open_questions.md §3.'),
        ('B392', 'under_investigation', 'Complex-formula undercount (−23/−21 MWh) — same magnitude as B305, likely same root cause (helper-row sub-meters zeroed by hasSubMeter edges). See open_questions.md §3.'),
        ('B330', 'ontology_drift', 'Small drift (−4 to −11 MWh, ~0.5–1.7%). Cause not yet diagnosed.'),
        ('B337', 'ontology_drift', 'Small drift (−11 MWh Jan only, ~2.4%). Cause not yet diagnosed.'),
        ('B318', 'ontology_drift', 'Consistent −2.2 MWh drift both months (~1.9%). Cause not yet diagnosed.'),
        ('B342', 'ontology_drift', 'Consistent +0.8 MWh drift both months (~0.7%). Cause not yet diagnosed.'),
        ('B307', 'under_investigation', 'Complex-formula overcount (+35%). Hypothesis: T10-1/T11-1 summary meters diverge from their children sum in Snowflake. See open_questions.md §2.'),
        ('B339', 'under_investigation', 'Complex-formula overcount (+45% to +50%). Same pattern as B307. See open_questions.md §4.'),
        ('B344', 'under_investigation', '−8.6% drift; both + terms (T57-4-7, T21-6-2-A) also appear as hasSubMeter children of their naming parents. See open_questions.md §6.'),
        ('B341', 'excel_cooked_coefficient', 'B341 formula W-column literal "Reservkraft pl7" (not a meter ID). Accidentally evaluates to zero; matches within 0.002%.'),
    ],
    'snv_sjovatten': [
        ('B301', 'excel_cooked_coefficient', 'B301 = 0.09 × BPS_V2. BPS_V2 is a sheet-level residual (B342 inlets − 15 direct consumers) with monthly-variable R factors; not mirrored in the ontology. See open_questions.md.'),
        ('B302', 'excel_cooked_coefficient', 'B302 = 0.18 × BPS_V2. Same BPS fractional split — see B301.'),
        ('B303', 'excel_cooked_coefficient', 'B303 = 0.18 × BPS_V2. Same BPS fractional split — see B301.'),
        ('B307', 'excel_cooked_coefficient', 'B307 = 0.46 × BPS_V2 (largest share). Same BPS fractional split — see B301.'),
        ('B344', 'excel_cooked_coefficient', 'B344 = 0.09 × BPS_V2. Same BPS fractional split — see B301.'),
        ('B304', 'strux_only_meter', 'B304-52-V2-AW026 is a manually-read STRUX meter; no BMS data. Excel cached values come from manual STRUX entry.'),
        ('BKringlan', 'strux_only_meter', 'TE-52-V2-GF4:1 Kringlan is a manually-read external-consumer meter (Telge Nät); no BMS data.'),
        ('BScania', 'strux_only_meter', 'TE-52-V2-SCANIA is a manually-read external-consumer meter (Telge Nät / Scania); no BMS data.'),
    ],
    'snv_kallvatten': [
        ('B310', 'excel_bug', 'Row 26 subtracts B313.KV1_VMM22_V which is also subtracted by row 30 (B314). Meter can have only one hasSubMeter parent — attached to B314.KV1_VMM21_V per shorter-formula-wins rule. B310 over-counts by Δ(B313.KV1_VMM22_V) ≈ 120 MWh/month.'),
        ('B311', 'excel_bug', 'Row 27 (16-term pool) subtracts B315.KV1_VMM21_V which is also subtracted by row 26 (B310). Meter attached to B310.KV1_VMM23_V; B311 over-counts by Δ(B315.KV1_VMM21_V) ≈ 20 MWh/month.'),
        ('B314', 'excel_bug', 'Row 30 lists B315.KV1_VMM21_V as a + term but row 31 also lists it as the sole + term for B315. Meter attributed to B315 (prefix-match); B314 under-counts by Δ(B315.KV1_VMM21_V) ≈ 20 MWh/month. Combined with the B313.KV1_VMM22_V subtraction that lands here (excel_bug from row 26), diff may stack.'),
        ('B202', 'match', 'Negative Excel value (row 10 — B202 subtracts both B201 and B203 meters and under-counts by design). Ontology mirrors Excel exactly (diff = 0).'),
    ],
    'snv_kyla': [
        # All 140 building-months currently match; these curated entries
        # preserve context for buildings where the match is "Excel=0 and
        # ontology=0" rather than a live comparison.
        ('B202', 'strux_only_meter', 'B202.VENT is STRUX-only; neither Excel nor ontology report kyla for Jan/Feb 2026.'),
        ('B330', 'strux_only_meter', 'B331.KB1_VM51_E (row 44 + term) is STRUX-only; not in BMS.'),
        ('B336', 'strux_only_meter', 'B336.KB1 is STRUX-only; not in BMS.'),
        ('B392', 'strux_only_meter', 'B392.KB1_VM51_E exists in Snowflake only as Water Volume (m^3), not as energy; crosswalk cleared to prevent unit-mismatched attribution.'),
        ('B302', 'excel_cooked_coefficient', '0.5 × B304.KB2 tenant split (row 19). Ontology uses a feeds edge with k=0.5 — matches exactly within noise.'),
        ('B303', 'excel_cooked_coefficient', '0.5 × B304.KB2 tenant split (row 20). Ontology uses a feeds edge with k=0.5 — matches exactly within noise.'),
        ('B305', 'excel_cooked_coefficient', 'B305.KB1 + 0.5 × B307.KB1 (row 22). Both routed via feeds to B305.KYLA_VIRT.'),
        ('B307', 'excel_cooked_coefficient', 'B307.KB1_VM52_E + 0.5 × B307.KB1 (row 23). Routed via feeds to B307.KYLA_VIRT.'),
    ],
    'snv_varme': [
        ('B327', 'excel_bug', 'Excel row 38 double-counts B326.VS1_VMM61 (already + term in row 37 for B326). Meter can have only one building attribution; assigned to B326 per decisions.md. B327 under-counts by Δ(B326.VS1_VMM61) ≈ 17 MWh/month.'),
        ('B310', 'match', 'Negative Excel value (−155 MWh Feb) — B310 is the 27-term distribution pool. Ontology mirrors Excel exactly (diff ≈ 0).'),
    ],
    'snv_anga': [
        ('B216', 'meter_outage', 'B216.Å1_VM71 counter froze 2026-02-18; ontology patches post-outage from child B217 but captures pre-outage physical B216>B217 delta (~30 MWh). Excel uses STRUX register-diff which absorbs the freeze as zero consumption post-Feb 18.'),
        ('B307', 'excel_bug', 'Excel row 23 subtracts both B330.Å1_VMM71 (by B307) and the same meter (by B337 row 46). Double-subtraction cannot be mirrored in the ontology (one parent per meter); B330 attached to B337 per decisions.md 2026-04-20. B307 over-counts by Δ(B330) ≈ 0.9 MWh/month.'),
        ('B308', 'meter_outage', 'B308.Å1_VMM71 counter frozen since 2025 (v=12737.1533 throughout). Ontology patches from child B327 ≥ 2026-02-07, yielding meter_net ≈ 0 after patch; Excel formula (+B308−B327) = −30 MWh regardless. Pre-outage Jan matches Excel exactly; post-patch Feb diverges by 22 MWh.'),
        ('B310', 'match', 'Negative Excel value (−152 MWh Jan, −12 MWh Feb) from B310 being a pool accounting building. Ontology mirrors Excel exactly.'),
    ],
}

def build_lookup(entries: list) -> dict:
    """Index curated entries by (building_id[, month]) for quick lookup."""
    out = {}
    for e in entries:
        if len(e) == 3:
            bld, reason, expl = e
            out[bld] = (reason, expl)
        elif len(e) == 4:
            bld, month, reason, expl = e
            out[(bld, month)] = (reason, expl)
    return out


def classify(bldg: str, month: str, excel: float, onto: float, curated: dict):
    diff = onto - excel
    absd = abs(diff)
    pct = abs(diff / excel * 100) if excel else 0.0
    # Noise-level first — even curated "problem buildings" match for months where they're actually fine.
    # When excel > 0, use percent; when excel == 0, any non-trivial onto is a real gap (not noise).
    # Noise-level matches — `reason='match'` alone conveys the meaning;
    # the boilerplate explanation just clutters the app view.
    if excel == 0 and onto == 0:
        return ('match', '')
    if excel > 0 and pct < 0.1:
        return ('match', '')
    if excel == 0 and absd < 10:  # native-unit: < 10 kWh / 10 MWh / 10 m³
        return ('match', '')
    # Month-specific curated override
    if (bldg, month) in curated:
        return curated[(bldg, month)]
    # Building-level curated override
    if bldg in curated:
        return curated[bldg]
    # Default: drift
    return ('ontology_drift', f'Drift of {diff:.0f} ({pct:.1f}%). Cause not yet classified.')


def compute_diffs(site_dir: Path, media_id: str):
    con = duckdb.connect(':memory:')
    for f in os.listdir(site_dir):
        if f.endswith('.csv'):
            name = f[:-4]
            con.execute(
                f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto('{site_dir / f}', HEADER=TRUE, ALL_VARCHAR=FALSE)"
            )
    con.execute(VIEWS_SQL.read_text())
    q = f"""
    WITH mn AS (
      SELECT mn.meter_id, mm.target_id AS building_id,
             mn.timestamp::DATE AS day, mn.net_kwh
      FROM meter_net mn
      JOIN meter_measures mm ON mm.meter_id = mn.meter_id AND mm.target_kind='building'
      JOIN meters m ON m.meter_id = mn.meter_id
      WHERE m.media_type_id = '{media_id}'
    ),
    onto AS (
      SELECT building_id, strftime(day, '%Y-%m') AS month, SUM(net_kwh) AS onto
      FROM mn
      WHERE day >= DATE '2026-01-01' AND day < DATE '2026-03-01'
      GROUP BY 1,2
    ),
    ex AS (
      SELECT building_id, month, excel_mwh AS excel
      FROM excel_building_totals
      WHERE media='{media_id}' AND month IN ('2026-01','2026-02')
    )
    SELECT COALESCE(ex.building_id, onto.building_id) AS bldg,
           COALESCE(ex.month, onto.month) AS month,
           COALESCE(ex.excel, 0)::DOUBLE AS excel,
           COALESCE(onto.onto, 0)::DOUBLE AS onto
    FROM ex FULL OUTER JOIN onto USING (building_id, month)
    ORDER BY bldg, month
    """
    return con.execute(q).fetchall()


def process(ws_name: str, site: str, media_id: str) -> dict:
    site_dir = REPO / 'data/sites' / site
    ws_dir = REPO / 'reference/media_workstreams' / ws_name
    out_path = ws_dir / '05_ontology/excel_comparison_annotations.csv'

    curated = build_lookup(CURATED.get(ws_name, []))
    rows = compute_diffs(site_dir, media_id)

    out_rows = []
    for bldg, month, excel, onto in rows:
        reason, expl = classify(bldg, month, excel, onto, curated)
        out_rows.append({
            'media': media_id,
            'building_id': bldg,
            'month': month,
            'excel_kwh': f'{excel:.2f}',
            'onto_kwh': f'{onto:.2f}',
            'diff_kwh': f'{onto - excel:.2f}',
            'reason': reason,
            'explanation': expl,
        })

    with out_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['media', 'building_id', 'month',
                                          'excel_kwh', 'onto_kwh', 'diff_kwh',
                                          'reason', 'explanation'])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    from collections import Counter
    summary = Counter(r['reason'] for r in out_rows)
    return {'path': out_path, 'count': len(out_rows), 'by_reason': dict(summary)}


def main():
    for ws_name, site, media_id in WORKSTREAMS:
        try:
            res = process(ws_name, site, media_id)
            print(f"{ws_name}: {res['count']} rows → {res['path'].relative_to(REPO)}")
            for k, v in sorted(res['by_reason'].items(), key=lambda kv: -kv[1]):
                print(f"    {k}: {v}")
        except Exception as e:
            print(f"{ws_name}: ERROR — {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
