# Reconciliation decisions — snv_sjovatten

No flow-schema PDF. Sjövatten is the most formula-complex SNV sheet —
a BPS (Block Pumping Station) fractional-split residual aggregator,
mixed unit/manual meter reads, and external consumers (Kringlan, Scania).

## 2026-04-20 — BPS fractional-split rows NOT materialised

Rows 19 (B301), 20 (B302), 21 (B303), 24 (B307), 55 (B344) use
`=R{n} * BPS_V2` where `BPS_V2` is a named range pointing at row 8
(`=SUM(C88:C89) - SUM(C90:C105)` — i.e. B342 inlet meters minus every
direct sjövatten consumer, leaving ~6000 m³ Jan of residual attributed
fractionally to 5 "API" buildings).

R factors sum to 1.0 (0.09+0.18+0.18+0.46+0.09). BPS_V2 is typically
small compared to total site flow — Jan 2026 BPS_V2 = 6003 m³ vs total
sjövatten ~484k m³.

**Decision:** DO NOT materialise the BPS virtual. Accept that B301,
B302, B303, B307, B344 will show Excel-only values with 0 ontology
attribution. Classify as `excel_cooked_coefficient` — the algorithm
is too chained (aggregate-then-split-by-row-factor) to mirror with
`views.sql::meter_net` primitives. B344 also appears as a formula only
here (no direct meter), same treatment.

**Impact:** 5 buildings × 2 months = 10 building-months mis-matched.
All by <3000 m³ each.

## 2026-04-20 — Row 51 (B339 kylmaskiner) 7-term formula

`+B339.V2_GF3_3 + B339.V2_GF3_4 + B339.V2_GF4 − B212 − B229 − B230 − B339.V2_GF4_1`.

Three + terms (all in B339) and four − terms. B212/B229/B230 are
"Acturum" external consumers also metered directly on their own rows
(80-82). B339.V2_GF4_1 is the + term in row 50 (B339 Kolfilter) but
subtracted here to isolate kylmaskiner-specific flow.

**Decision:** hasSubMeter edges from B339.V2_GF3_3 (principal +) to each
of the four − terms. Building B339 aggregates rows 50 and 51 (Kolfilter
+ kylmaskiner). Excel label normalised: `339 Kolfilter` →
`B339`, `339 kylmaskiner` → `B339` (rows summed during building_totals
extraction).

## 2026-04-20 — Cooked 0.5 splits

Rows 27/28 (B310/B311 split B310.V2_GF4_1) and rows 45/46
(B330/B331 split B330.V2_GF4_1). Both source meters are Snowflake-
absent (STRUX-only manual reads), so the feeds will flow zero either
way — but the structural `B###.SJOVATTEN_VIRT` feeds remain for
faithful Excel encoding.

## 2026-04-20 — Fully-split source meters reattributed to campus

`B310.V2_GF4_1` and `B330.V2_GF4_1` each split 0.5/0.5 into a pair of
`B###.SJOVATTEN_VIRT` virtuals (Σk = 1.0). Per reference-site
convention they sit at campus (`building_id=''`); the virtuals
carry the building labels. Both are Snowflake-absent anyway, so the
numeric impact is zero either way, but the graph intent is cleaner.

## 2026-04-20 — Building label normalisations

- `339 Kolfilter` → **B339**
- `339 kylmaskiner` → **B339** (same building; both rows summed)
- `409 Kylcentral` → **B409**
- `Kringlan` → **BKringlan** (Telge Nät external consumer, no B-prefix
  in Snowflake; keep the BKringlan label as-is).
- `Scania` → **BScania** (same external-consumer pattern).

## 2026-04-20 — `extract_building_totals` now skips summary / helper rows

Sjövatten row 8 has `B='BPS Beräkning'` (summary) which my earlier
"Total*"/"Summa*" filter didn't catch because col A is None. Rows
87-105 contain the BPS lookup helper (meter-ID strings as col B like
`B342.V2_VM90_V`, `TE-52-V2-GF4:1 Kringlan`, `B304-52-V2-AW026`).

**Decision:** did a post-hoc CSV cleanup instead of a parser change:
dedupe by (building, month), drop IDs matching `BB?\d+\.V2_`,
`BTE-52`, or `B\d+-\d+-` patterns (all are meter IDs, not buildings),
and drop `BBPS Beräkning`. Rename `339 Kolfilter`/`kylmaskiner` →
`B339` and `409 Kylcentral` → `B409` during the same dedup.

## 2026-04-20 — STRUX-only meters (6 Excel-used, Snowflake-absent)

`B304-52-V2-AW026`, `B308.V2_VM21-V`, `B310.V2_GF4_1`, `B330.V2_GF4_1`,
`B336.V2_GF4`, `B337.V2_GF4_1`, `TE-52-V2-GF4:1 Kringlan`,
`TE-52-V2-SCANIA` — all manually read. Classify affected building-
months as `strux_only_meter`.

## 2026-04-20 — Simplified crosswalk canonicalisation

Sjövatten meters use variable patterns: `B###.V2_VM##`,
`B###.V2_GF#_#`, dashed forms like `B304-52-V2-AW026`, and TE-prefixed
external. Shared canonicalisation (strip `_E`, normalise `_VM##`→
`_VMM##`) applied; dashed forms preserved verbatim since they don't
follow the standard pattern.

## 2026-04-21 — BPS_V2 virtual-pool revisit (still deferred)

Attempted to materialise the BPS_V2 virtual (5 building-share virtuals, 15
hasSubMeter drains, inlets aggregated via a `sum`-aggregation timeseries_ref
to avoid the multi-feeds double-count issue in `views.sql::meter_flow`'s
recursive CTE). The topology math and SQL wired up correctly: residual at
BPS_V2_VIRT was a clean per-timestamp value, 5 shares summed back to 100%
at the configured R-factors (0.09/0.18/0.18/0.46/0.09 sum=1.0).

**Blocker**: 8 of the 15 direct-consumer meters have no Snowflake counter
data — 6 are STRUX-only (B304-52-V2-AW026, B310.V2_GF4_1, B330.V2_GF4_1,
B337.V2_GF4_1, TE-52-V2-GF4:1 Kringlan, TE-52-V2-SCANIA) and 2 went
offline pre-2026-01 (B305.V2_VMM21, B339.V2_GF4). These 8 account for
~198k m³/month of real drain that the ontology can't see, so the computed
BPS residual is ~34× Excel's (~204k vs ~6k m³, Jan 2026). Building shares
become ~34× too large, worse than the prior zero-attribution.

**Revert.** Revisit once the 8 STRUX-only/offline meters get Snowflake
counter data. Until then, `excel_cooked_coefficient` remains the correct
reconciliation reason for B301/B302/B303/B307/B344 sjövatten.

Architectural take-away — preserved in memory (feedback_bps_v2_pool_revisit.md):

- `meter_flow`'s recursive CTE double-counts hasSubMeter subtractions when
  a virtual has ≥2 incoming `feeds` paths. Workaround is to aggregate
  upstream via a `sum`-aggregation timeseries_ref before the `feeds` hop.
- A fractional-pool attribution via virtuals only works when the drain
  side is complete in Snowflake. Incomplete drains inflate the residual
  and make the pattern worse than zero-attribution.
