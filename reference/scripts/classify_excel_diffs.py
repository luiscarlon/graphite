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
        # Fractional 0.9 / 0.1 split of B637 (and B638) is modelled via
        # `hasSubMeter k=0.9` / `k=0.1` on B612.KYLA_VIRT and B641.KYLA_VIRT —
        # matches Excel exactly. Curated `match` override needed for B641
        # because the classifier's noise-floor branches don't fire on negative
        # Excel cells (B641 KYLA = -1.75 / -1.80 — net consumer of the
        # B637 sub).
        ('B612', 'match', 'Fractional 0.9×B637 + 0.9×B638 subs modelled via hasSubMeter k=0.9 on B612.KYLA_VIRT — matches Excel exactly.'),
        ('B641', '2026-01', 'match', 'Fractional 0.1×B637 + 0.1×B638 subs modelled via hasSubMeter k=0.1 on B641.KYLA_VIRT — matches Excel exactly (diff 0.00 MWh; curated override because classifier doesn\'t auto-match negative Excel cells).'),
        ('B641', '2026-02', 'trailing_day_gap', 'Trailing single-day gap: the B612.KB1_PKYL daily-fill derived ref (interpolate) ends 2026-02-27 because its valid_to anchor is the 2026-02-28 source reading itself. The 0.1 × B637 sub on Feb 28 (~0.04 MWh) is therefore not applied to B641 and ends up in B612 instead. Negligible. Will resolve once a March 2026 raw reading lands and we extend valid_to.'),
        ('B611', 'data_quality_artifact', 'Dead pool meter (B653 died 2025-10-09) combined with active downstream sub-meters yields physically-nonsensical negative value. Topology faithful to the source.'),
        ('B833', '2026-01', 'match', 'Bi-daily BMS sensor (B833.KB1_GF4 reads ~31 times over 59 days). Diff exactly 0.00 — curated override because classifier doesn\'t auto-match negative Excel cells.'),
        ('B833', '2026-02', 'trailing_day_gap', 'Trailing single-day gap: the B833.KB1_GF4 daily-fill ref ends 2026-02-27. The B834 sub on Feb 28 (~0.03 MWh) isn\'t applied. Will resolve once a March 2026 raw reading lands.'),
    ],
    'gtn_el': [
        ('B664', 'excel_stale', 'Excel missed T42-2-1, so it lands 0 here. PME has the meter (~4.9 MWh/mo); ontology credits B664. Mirror of B665.'),
        ('B665', 'excel_stale', 'Excel missed T42-2-1, so its subtract is a no-op and B665 keeps the full T42. PME has T42-2-1; ontology subtracts it. Mirror of B664.'),
        ('B612', 'excel_bug', 'Excel subtracts T8-A3-A14-112 twice (once via T8-A3, once on its own line), so B612 is short by ~21 MWh/mo. Ontology walks the T8 → T8-A3 → T8-A3-A14-112 chain and subtracts only once.'),
        ('B652', 'data_source_drift', '~0.6 MWh / 3% gap between Excel\'s cached T8-A3-A14-112 value and the PME daily sum. Same meter, slightly different aggregation.'),
        ('B660', '2026-02', 'under_investigation', 'Jan matches within 609 kWh, Feb drifts -141 MWh (-2.2%). Root cause not yet diagnosed.'),
    ],
    'snv_el': [
        # STRUX-only buildings
        ('B209', 'strux_only_meter', 'B209.T21 / T32 / T83 STRUX-only; topology cannot contribute BMS flow.'),
        ('B304', 'strux_only_meter', 'B304 EL formula has only 2 +terms — B313.T26S-3-12 and B336.T40-3-1 — and neither meter ID exists in the Snowflake BMS dump at all (verified: zero rows). Onto = 0 because both ts_refs would need readings we don\'t have. Excel\'s ~4.5 MWh/mo comes entirely from STRUX manual entries. Same family as B334 T87-T92 and the B313.T26S residual feeding B310/B311. Could be closed by injecting STRUX values for these meters via a structured extraction pipeline — see open_questions.md §5.'),
        ('B334', 'strux_only_meter', 'T87-T92 summaries are STRUX-only (no BMS data); ~95% gap vs Excel.'),
        # Cross-building fractional pools (T32-4-2, T26S, T29, T49) are modelled
        # via fractional `feeds` k<1.0 edges — same primitive GTN KYLA uses.
        # B204, B205, B313, B317-Jan all match within noise floor → no entry needed.
        # B310/B311 keep small drift from B313.T26S summary missing in BMS (only
        # its 10 sub-meters report) — STRUX captures the unmetered residual we
        # can't see. Same family as B334 T87-T92.
        ('B310', 'strux_only_meter', 'Drift = 0.5 × B313.T26S unmetered residual. Verified by per-component reconstruction: Excel B310 = 0.5 × (T26S_strux − 10 BMS subs in B310 row) + 0.333×T29 + 0.4×T49.net + T27.net + T28.net = 225,234 implies T26S_strux ≈ 74.6 MWh/mo. BMS sub-feeders sum to ~63 MWh, leaving ~12 MWh STRUX-only residual that splits 50/50 with B311 — both buildings reconcile to the same implied T26S_strux. Mechanism: the `B313.T26S → B310.EL_VIRT feeds k=0.5` edge in meter_relations is dead because T26S has no measured flow; views.sql\'s recursive `flow` requires a measured base for feeds to fire, and T26S never enters the recursion. Same family as B304 (T26S-3-12 / T40-3-1 absent) and B334 T87-T92. Could be closed by injecting STRUX value for B313.T26S as a virtual ts_ref — see open_questions.md §5.'),
        ('B311', 'strux_only_meter', 'Drift = 0.5 × B313.T26S unmetered residual. Same root cause as B310: T26S has no measured flow in Snowflake so the `feeds k=0.5` edge to B311.EL_VIRT is dead. Excel B311 reconstructs as 0.5 × (T26S_strux − 8 BMS subs in B311 row) + 0.667×T29 + extras + T56.net + T79 + T80.net + T99-4-5 = 334,463 with the same T26S_strux ≈ 74.6 MWh/mo. The 8-kWh agreement between B310 and B311 drifts (5985 vs 5977) is the fingerprint of a single shared upstream cause.'),
        ('B317', '2026-02', 'under_investigation', 'B317 EL Jan matches Excel within 5 kWh; Feb shows -75 MWh (-56%). All BMS data (T49 + 13 subs, T26S-3-16/3-20) is internally consistent and reproduces Excel-Jan exactly via `0.5 × (T49 - 5 subs) + T49-5-9 + T26S-3-16 + T26S-3-20`. Excel\'s extra 75 MWh in Feb is unaccounted for by BMS — likely a STRUX-side Feb entry on T26S-3-16/3-20 (both flat in BMS) or a STRUX value diverging from BMS for one T49 term. Needs facit spot-check.'),
        ('B305', 'excel_bug', 'Excel uses B339.T77-4-5 at +1.0 in both B305 (row 22) and B392 (row 81). Ontology splits 0.5/0.5 across the two buildings to avoid double-count; B305 therefore receives 0.5 × T77-4-5 ≈ 23 MWh/mo less than Excel. The other 10 +terms in B305\'s formula deliver their full flow correctly (T10-7-3 / T10-7-7 carry no BMS data but Excel values for them appear ≈0). Same 50/50-split remediation as B318/B344. See snv_el_T77_4_5_double_plus.'),
        ('B392', 'excel_bug', 'Excel uses B339.T77-4-5 at +1.0 in both B392 (row 81) and B305 (row 22). Ontology splits 0.5/0.5; B392 therefore receives 0.5 × T77-4-5 ≈ 23 MWh/mo less than Excel. The other +term (B334.T88-4-2) contributes correctly. Same 50/50-split remediation as B318/B344. See snv_el_T77_4_5_double_plus.'),
        ('B330', 'ontology_drift', 'Small drift (−4 to −11 MWh, ~0.5–1.7%). Cause not yet diagnosed.'),
        ('B337', 'ontology_drift', 'Small drift (−11 MWh Jan only, ~2.4%). Cause not yet diagnosed.'),
        ('B318', 'excel_bug', 'Excel uses B318.T21-6-2-A at +1.0 in both B318 (row 34) and B344 (row 53). Ontology splits 0.5/0.5 to avoid double-count; the 0.5 × T21-6-2-A ≈ 2.3 MWh/mo missing from B318 is the observed −1.9 % drift. Same family as B327 / B326.VS1_VMM61. See snv_el_T21_6_2_A_double_plus.'),
        ('B342', 'data_source_drift', 'Consistent +0.7 % gap (~810 kWh/mo) between ontology (BMS daily sum) and Excel cached value. None of the 3 +term meters (B308.T58-8-3, B342.T66, B342.T67) has anomalies, double-counting, or 2026-01-14 cluster impact. Same shape as GTN B652 data_source_drift.'),
        ('B307', 'under_investigation', 'Complex-formula overcount (+35%). Hypothesis: T10-1/T11-1 summary meters diverge from their children sum in Snowflake. See open_questions.md §2.'),
        ('B339', 'under_investigation', 'Complex-formula overcount (+45% to +50%). Same pattern as B307. See open_questions.md §4.'),
        ('B344', 'excel_bug', 'Excel uses B318.T21-6-2-A at +1.0 in both B344 (row 53) and B318 (row 34). Ontology splits 0.5/0.5; the missing 0.5 × T21-6-2-A ≈ 2.3 MWh/mo from B344 is part of the observed −4 % drift (also compounded by T57-4-7 hasSubMeter chain). See snv_el_T21_6_2_A_double_plus.'),
        ('B341', 'match', 'B341 formula W-column literal "Reservkraft pl7" (not a meter ID). Accidentally evaluates to zero; matches within 0.002%.'),
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
        ('B313', '2026-01', 'meter_outage', '2026-01-14 catch-up cluster: B313.KV1_VMM22_V flat 114d 2025-09-21 → 2026-01-14, single-day flush absorbed by interpolate. Same family as VARME B313.VP1_VMM62.'),
        ('B317', '2026-01', 'meter_outage', '2026-01-14 catch-up cluster: B317.KV1_VMM21_V flat 114d 2025-09-21 → 2026-01-14, single-day flush absorbed by interpolate. Same family as VARME B311.VP1_VMM64.'),
        ('B389', 'meter_outage', 'Winter offline + catch-up flush: B389.BRV1_VMM21 flat 47d 2025-12-16 → 2026-02-03 with single-day flush on Feb 3. Patched via 3-segment slice/interpolate/slice + rolling_sum. The Jan +163 m³ / Feb -245 m³ ontology-vs-Excel split reflects the patch spreading consumption across the gap while Excel sees only the Feb 3 spike. Same family as the 2026-01-14 sitewide cluster. See ann-snv-kv-b389-swap (mislabeled — actually outage, no register swap).'),
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
        ('B310', '2026-02', 'match', 'Negative Excel value (−155 MWh) — B310 is the 27-term distribution pool. Ontology mirrors Excel exactly (diff ≈ 0).'),
        ('B310', '2026-01', 'meter_outage', 'B310 = +VP2_VMM61 − B311.VP1_VMM64 − B313.VP1_VMM62 − subs. All three patched via slice/interpolate/slice across the 2025-09 → 2026-01-14 freeze; the interpolates spread each meter\'s catch-up flush linearly across the freeze window for plausible daily Sept-Jan reporting, which removes those flushes from Jan 2026 monthly totals. Excel STRUX register-diff books all three flushes in Jan. Net diff −1353 MWh ≈ VP2 spread (~1987 MWh) net of sub spreads (~450 MWh). Patch is intentional. See ann-snv-varme-b310-vp2-offline-fall.'),
        ('B311', '2026-01', 'meter_outage', 'Patched via slice/interpolate/slice 2025-09-20 → 2026-01-14: B311.VP1_VMM64 flat 117 days then flushed +45.6 MWh on 2026-01-14. Interpolate distributes the flush linearly across the freeze window for plausible daily reporting, which removes it from Jan 2026 monthly totals; Excel STRUX register-diff books the full flush in Jan. ~40 MWh diff = the share of the flush attributed to Sept-Dec by the patch. Patch is intentional. See ann-snv-varme-b311-vmm64-offline-fall.'),
        ('B313', '2026-01', 'meter_outage', 'Patched via slice/interpolate/slice 2025-09-22 → 2026-01-14: B313.VP1_VMM62 flat 114 days then flushed +404.8 MWh on 2026-01-14. Interpolate distributes the flush linearly across the freeze window for plausible daily reporting, which removes it from Jan 2026 monthly totals; Excel STRUX register-diff books the full flush in Jan. ~356 MWh diff = the share of the flush attributed to Sept-Dec by the patch. Patch is intentional. See ann-snv-varme-b313-vmm62-offline-fall.'),
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


def classify(bldg: str, month: str, excel: float, onto: float,
             curated: dict, bldgs_with_meters: set[str], media_id: str):
    diff = onto - excel
    absd = abs(diff)
    pct = abs(diff / excel * 100) if excel else 0.0
    # Noise-level first — even curated "problem buildings" match for months where they're actually fine.
    # When excel > 0, use percent; when excel == 0, any non-trivial onto is a real gap (not noise).
    # Noise-level matches — `reason='match'` alone conveys the meaning;
    # the boilerplate explanation just clutters the app view.
    if excel == 0 and onto == 0:
        return ('match', '')
    # Noise floor for relative drift: 0.25%. Below this, the difference
    # is at the level of Excel cached aggregation vs PME daily-sum
    # rounding and isn't worth flagging.
    if excel > 0 and pct < 0.25:
        return ('match', '')
    if excel == 0 and absd < 10:  # native-unit: < 10 kWh / 10 MWh / 10 m³
        return ('match', '')
    # Building has no meters targeting it for this media — its Excel line
    # is a campus-intake reading attributed to the campus in the ontology.
    # Don't flag as drift; explain the topology choice.
    if bldg not in bldgs_with_meters and excel > 0 and onto == 0:
        return ('campus_attributed',
                f"No {media_id} meter targets {bldg} in the ontology — all meters tied to this Excel line are bucketed at campus level. Excel and ontology measure the same reading at different scopes.")
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
            # When valid_from/valid_to columns are all-empty, duckdb
            # infers VARCHAR which breaks comparisons against TIMESTAMP
            # in views.sql. Force DATE where present.
            date_hint = ""
            if name in ('meter_relations', 'timeseries_refs', 'meters', 'meter_measures'):
                date_hint = ", types={'valid_from': 'DATE', 'valid_to': 'DATE'}"
            con.execute(
                f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto('{site_dir / f}', HEADER=TRUE, ALL_VARCHAR=FALSE{date_hint})"
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
    rows = con.execute(q).fetchall()
    bldgs_with_meters = {
        r[0] for r in con.execute(
            f"SELECT DISTINCT mm.target_id "
            f"FROM meters m JOIN meter_measures mm "
            f"  ON mm.meter_id = m.meter_id AND mm.target_kind='building' "
            f"WHERE m.media_type_id = '{media_id}'"
        ).fetchall()
    }
    return rows, bldgs_with_meters


def process(ws_name: str, site: str, media_id: str) -> dict:
    site_dir = REPO / 'data/sites' / site
    ws_dir = REPO / 'reference/media_workstreams' / ws_name
    out_path = ws_dir / '05_ontology/excel_comparison_annotations.csv'

    curated = build_lookup(CURATED.get(ws_name, []))
    rows, bldgs_with_meters = compute_diffs(site_dir, media_id)

    out_rows = []
    for bldg, month, excel, onto in rows:
        reason, expl = classify(bldg, month, excel, onto, curated, bldgs_with_meters, media_id)
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
