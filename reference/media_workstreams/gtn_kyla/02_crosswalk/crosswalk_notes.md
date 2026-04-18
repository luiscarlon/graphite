# crosswalk_notes — gtn_kyla

Seed crosswalk generated automatically by canonicalising meter IDs across the
two sources (no flow schema for kyla):
- Excel `Kyla` sheet formula terms (`01_extracted/excel_meters_used.csv`)
- Snowflake `Active Energy Delivered(Mega)` meters matching kyla-role naming

Canonicalisation rule: strip trailing ``_E``, then ``VM##`` → ``VMM##`` on the
trailing index. Buildings without a naming-compliant canonical form (e.g.
``B654.KB1_KylEffekt_Ack``, ``B612-KB1-PKYL``) are kept as-is — the kyla
sheet uses a looser tagging convention than värme/ånga.

**confidence:** `high` = seen in both sources; `medium` = only one source.
Review `medium` rows manually; they are typically the "accounting-only"
meters (no Snowflake feed) or "field-only" (meter exists in BMS but isn't
rolled up in the Kyla formula).

## 2026-04-17 — crosswalk rebuilt with B8 buildings + dash/dot normalisation

- Previous seed filtered Snowflake IDs to B2/B3/B6 prefixes, silently
  dropping B8 buildings (B821/B833/B834/B841). Fixed.
- Canonicalisation now handles:
  - dash separator (`B600-KB2` → `B600.KB2`)
  - trailing `_E` energy-variant suffix
  - `VM##` → `VMM##`
- Current coverage: 21 Excel meters matched to Snowflake (`confidence=high`);
  4 Excel-only (decommissioned or naming drift — see `open_questions.md`);
  95 Snowflake-only meters exist on campus in kyla roles but aren't
  referenced in Kyla formulas (probably historical or sub-meters).
