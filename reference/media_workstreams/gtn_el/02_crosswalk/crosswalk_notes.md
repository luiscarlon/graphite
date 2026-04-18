# crosswalk_notes — gtn_el

Electricity meter IDs in Excel and Snowflake mostly agree literally
(``B611.T1``, ``B611.T4-A3``, ``B622.T2-3-1-B1``). Canonicalisation is near-
trivial: strip trailing ``_E`` if present, otherwise use as-is.

**Coverage:** Excel references a small subset of Snowflake's ~500 EL meters —
only the ones billed and rolled up per-building. The other ~400 are sub-
meters, individual transformer feeders, or tenant-specific meters not in
the campus accounting rollup.

**Site scalar:** EL sheet has ``$F$5 = 0.001`` applied to every formula to
convert kWh → MWh. The formula-term parser resolves this automatically via
``_workbook_scalar_cells`` (needs ``data_only=True`` view).
