# Open questions — snv_anga

## B307 building total is +Δ(B330.Å1_VMM71) higher than Excel

The Excel formula at row 23 subtracts 10 meters including B330.Å1_VMM71.
The ontology can only attach B330.Å1_VMM71 to one parent — chosen as
B337.Å1_VMM71 (row 46). Consequence: B307's topology-computed building
total is over-estimated by the B330.Å1_VMM71 monthly delta. Expected
magnitude: proportional to B330's Ånga consumption (unknown until
validation run).

Mitigation: annotate as `excel_bug` in `excel_comparison_annotations.csv`
after the first validation pass. No fix possible without a virtual
meter.

## B200.Å1_VMM71 emits on BMS but is not in any Excel formula

PDF has no VMM71 node on the B200 trunk (only VMM70). Snowflake has
readings for `B200.Å1_VMM71`. Unknown role — distribution-trunk check
meter, or redundant backup. Not included in the ontology until an
evidence line is established.

## B310 has 4 PDF-only sub-meters (VMM71, VMM72, VMM73, VMM74)

Excel row 26 uses `VMM70` as the single + and subtracts 5 meters from
other buildings (B311.VMM72, B317.VMM72/71, B313.VM71/VMM72). The PDF
has B310.VMM71/VMM72/VMM73/VMM74 as downstream taps inside B310.
Snowflake has readings for all four. Their role in Excel is unclear —
they may represent further internal taps whose consumption is already
captured by VMM70 (no accounting needed) or alternative tenant splits
not currently encoded. Not in the current ontology.

## B337.Å1_VMM72 emits on BMS but is not in any Excel formula

Similar to B200.VMM71: PDF has it, Snowflake has readings, Excel
doesn't use it. Possibly a secondary internal tap to B337.VMM71.
Excluded for now.
