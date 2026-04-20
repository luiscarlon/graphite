# Open questions — snv_sjovatten

## BPS fractional allocation unsolved

B301, B302, B303, B307, B344 will show Excel-only values with 0
ontology attribution until a BPS virtual meter is wired up. The
semantics are:

```
BPS_V2 = B342.V2_VM90_V + B342.V2_VM91_V − (sum of 15 direct consumer meters)
B301 = 0.09 × BPS_V2
B302 = 0.18 × BPS_V2
B303 = 0.18 × BPS_V2
B307 = 0.46 × BPS_V2
B344 = 0.09 × BPS_V2
```

Building a `SNV.BPS_V2_VIRT` would need:
1. Virtual meter attributed to campus with incoming `feeds` from
   B342.V2_VM90_V (k=1.0) and B342.V2_VM91_V (k=1.0), and outgoing
   `hasSubMeter` to the 15 direct consumers (so their flow drains).
2. Outgoing `feeds` to 5 B###.SJOVATTEN_VIRT building virtuals with
   R factors (0.09/0.18/0.18/0.46/0.09).

Deferred because the R factors are MONTHLY variables (stored in col R
of the sheet), not constants — `views.sql::meter_flow` expects
constant coefficients. Revisit if per-month coefficient support is
added to the calc engine.

## Row 8 residual reconciliation

BPS_V2 is literally "whatever's left" after subtracting direct
consumers. When a direct consumer is under-reporting, the residual
inflates — and that inflation attributes entirely to the 5 BPS-split
buildings. This is a known Excel artefact, not an ontology issue.
