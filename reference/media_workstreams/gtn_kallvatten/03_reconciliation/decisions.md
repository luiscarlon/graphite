# decisions — gtn_kallvatten (built 2026-04-19)

Built from scratch following RESOLVE_ONTOLOGY.md's Excel-is-facit workflow. PDF (`V600-52.B.8-001.pdf`) is linked in 00_inputs but not used — Excel formula structure is sufficient and authoritative.

## 2026-04-19 — Crosswalk: 62/63 meters match Snowflake exactly

Kallvatten meter IDs are already in the canonical form (e.g. `B611.KV1_VM21`, `B921.KV1_VM21_V`). No dash-to-dot normalization, no `-S` suffix quirks, no VM↔VMM drift. 62 of 63 match Snowflake exactly on first try.

**Single unmatched:** `B869.KV1_VM21`. STRUX catalog has it listed as `Automatisk` (auto-read) but with 0 values for Jan and Feb 2026. Snowflake has no entries for any B869 meter (0 rows in the dump). Excel cache for building B869 kallvatten = 0 for Jan–Feb. Marked in crosswalk with `snowflake_id=""` and treated as inactive; no topology impact during the comparison window.

## 2026-04-19 — Excel-facit topology: hasSubMeter from first + term to each − term

All kallvatten formulas have all-1.0 coefficients (no fractional shares, no virtual aggregators like kyla's B600-KB2). The − terms are always other-building meters being excluded from this building's accounting (tenant splits, sub-panels).

**Decision:** For each building with − terms, make the − meters hasSubMeter children of the building's first + term. 11 edges total:

| building | first + term (parent) | − terms (children) |
|---|---|---|
| B611 | B611.KV1_VM21 | B622.KV1_VM22_V, B613.KV1_VM21_V |
| B612 | B612.KV1_VM21 | B613.KV1_VM23_V, B637.KV1_VM21, B638.KV1_VM21 |
| B614 | B614.KV1_VM21 | B615.KV1_VM21_V |
| B621 (T) | B621.KV1_VM21 | B622.KV1_VM21_V, B623.KV1_VM21_V |
| B821 | B821.KV1_VM21 | B626.KV1_VM20, B626.KV1_VM21 |
| B833 | B833.KV1_VM21 | B834.KV1_VM21 |

Since all coefficients are 1.0, hasSubMeter (k=1) exactly reproduces Excel arithmetic. The approach that failed on kyla (fractional coefficients) doesn't apply here.

## 2026-04-19 — Building label normalization

Excel row 19 uses `621 (T)` (tenant building); row 55 uses `850/662` (combined 850+662). `parse_reporting_xlsx._normalize_building_id` maps `621 (T)` → `B621` correctly but returns `B850/662` unchanged for the slash form.

**Decision:**
- `621 (T)` → `B621` via the parser's existing (T) logic.
- `850/662` → `B850` via post-processing in `01_extracted/excel_building_totals.csv` (manually renamed 12 rows). Physical meter `B850.KV1_VM21` attributes to building B850; building 662 has no kallvatten meter of its own.

Canonical building set has 39 unique buildings.

## 2026-04-19 — Result

- 63 meters (62 with Snowflake data + 1 STRUX-only inactive B869).
- 11 hasSubMeter edges, 0 feeds (no fractional shares).
- **50/50 buildings match Excel within ±0.5 MWh for 2026-01; 48/50 for 2026-02 initially — after the B850/662 normalization, 50/50 both months.**
- 0 Brick validation violations.
