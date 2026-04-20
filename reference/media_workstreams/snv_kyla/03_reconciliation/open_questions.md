# Open questions — snv_kyla

## B392.KB1_VM51_E is water-volume in Snowflake, not energy

The meter exists in Snowflake under quantity `Water Volume (m^3)` but
not `Active Energy Delivered(Mega)`. Excel treats it as a kyla energy
meter (row 73). Converting m³ → MWh requires a ΔT-based heat-capacity
calculation (`ρ × c_p × V × ΔT`), which isn't part of the ontology.

Effect: B392 kyla total will show 0 in the ontology vs whatever
STRUX has cached. Classify as `strux_only_meter`.

Resolution path (future): either add a second raw ref on the same meter
with an explicit ΔT-based derivation, or accept that Snowflake simply
lacks the pre-computed energy channel for this meter.

## B202.VENT, B331.KB1_VM51_E, B336.KB1 absent from BMS

All three are STRUX-only. Building totals will short by the STRUX
cached value. Classify as `strux_only_meter`.

## Fractional-coefficient residuals

Rows 19/20 (B302/B303 split of B304.KB2) and 22/23 (B305/B307 split of
B307.KB1) use 0.5 tenant coefficients. `views.sql::meter_net` has no
fractional-subtract primitive (see memory `feedback_kyla_fractional`).
Expect small (1–3 MWh) residuals on these four buildings.
