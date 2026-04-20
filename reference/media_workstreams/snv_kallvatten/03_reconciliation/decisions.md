# Reconciliation decisions — snv_kallvatten

Excel-is-facit build. PDF (V390-52.B.8-001) parsed but yielded only
1 meter / 0 relations — not useful as a topology source; Excel is the
authoritative source.

## 2026-04-20 — Crosswalk: all 63 Excel meters match Snowflake

Shared VM→VMM normalisation + `_E` strip + preservation of `_V`
water-variant suffix handled every meter. 0 Excel-used meters are
Snowflake-absent. 9 PDF/STRUX-only catalog entries left in the crosswalk
with `excel_used=no`.

## 2026-04-20 — Dual-building labels

- `204/205` (row 12) → normalise to **B204** (+ term is `B204.KV1_VM22_V`).
- `330/331` (row 44 onwards) → normalise to **B330** (mirrors snv_anga / snv_varme).

## 2026-04-20 — Row 27 B311 is a 16-term distribution pool

B311's kallvatten accounting subtracts 15 downstream meters across
B310 (6 meters), B313, B315, B317 (4 meters), B337, B381. Principal
+ is `B311.KV1_VM26_V`.

Pattern identical to gtn_anga row 23 (B307 10-term pool) and
snv_varme row 22 (B310 27-term pool): principal + at the trunk
distribution meter, all downstream meters subtracted to prevent
double-attribution.

## 2026-04-20 — Two subtraction conflicts, resolved to shorter row

- `B313.KV1_VMM22_V` subtracted by row 26 (B310) and row 29 (B313 row
  with one sub, shorter). Kept child under B314 via the shorter row.
- `B315.KV1_VMM21_V` subtracted by row 27 (B311, 16-term) and row 26
  (B310, shorter). Kept under B310.

Both create small per-month residuals on the loser (B311 in the first
case — oh wait, actually the loser is the LONGER row which gets its
subtraction skipped). Annotate as `excel_bug` if residuals exceed 0.1%.

## 2026-04-20 — Sub-only meters attributed to campus

Five meters appear only as `−` terms in Excel (no `+` anywhere). They
become children of their respective parents but their own meter_net
delta must not re-add to any building. Attributed to campus:

- B202.KV1_VMM22_V, B302.KV1_VMM21_V, B305.KV1_VMM21_V,
  B310.KV1_VMM24_V, B311.KV1_VMM27_V
