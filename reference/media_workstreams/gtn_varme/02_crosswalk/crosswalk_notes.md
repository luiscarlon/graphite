# crosswalk_notes — gtn_varme

## Normalisation rules applied

1. **Strip `_E` suffix.** Energy-variant meters in Snowflake carry `_E`; canonical facit IDs omit it.
2. **VMM form is standard.** Unlike ånga (which had VM→VMM drift), all värme meters already use VMM## in both PDF and Snowflake. No VM→VMM normalisation needed.
3. **Role merges (VS1→VP1):** Two buildings have a role labeling disagreement between the PDF (VS1) and Excel/Snowflake (VP1). Merged to VP1:
   - B661.VS1_VMM61 → B661.VP1_VMM61
   - B821.VS1_VMM61 → B821.VP1_VMM61

## Meter universe

- **53 Snowflake meters** with timeseries data
- **6 PDF-only meters** with no Snowflake data: B613.VP1_VMM62, B616.VS1_VMM61, B621.VÅ9_VMM41, B631.VP1_VMM61, B674.VÅ9_VMM41, B674.VÅ9_VMM42
- **46 Excel-used meters** (appearing in Värme tab accounting formulas)
- **2 merged meters** (VS1→VP1 for B661 and B821)
- **Total: 59 unique facit meters**

## Notable mappings

| facit_id | issue |
|---|---|
| B612.VP2_VMM61 | PDF root of VP2 circuit but not in Excel; flat for 35 days in Snowflake |
| B631.VP1_VMM61 | PDF routing node (B611→B631→B611.VÅ9); no Snowflake data |
| B674.VÅ9_VMM41/42 | PDF-only; arrow-confirmed upstream of VP1/VP2; heat recovery output |
| B661.VP1_VMM61 | Snowflake/Excel VP1; PDF labels it VS1 |
| B821.VP1_VMM61 | Same as B661 — VP1/VS1 role disagreement |

## Excel-only meter (not in crosswalk)

- `B621.VÅ9_VMM44_E`: appears in `excel_intake_meters.csv` but NOT in any formula, NOT in Snowflake. Catalog-only entry; excluded from crosswalk.
