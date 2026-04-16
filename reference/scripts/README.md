# reference/scripts

Scripts that operate on the raw PDFs and XLSX files under `reference/`.

## `parse_flow_schema.py`

Parses an AstraZeneca *flödesschema* PDF (the `V###-##.#.8-***` drawings, not
the `.1` *översiktsritning* site maps) into:

- `<prefix>_meters.csv` — every labeled `B### - Å1 V(M)M##` meter symbol
- `<prefix>_relations.csv` — `from_meter → to_meter` edges derived from the
  pipe graph by BFS from user-supplied source meters

### Usage

```sh
.venv/bin/python reference/scripts/parse_flow_schema.py \
  reference/flow_charts/V600-52.E.8-001.pdf \
  --sources B600S.Å1_VMM71,B600N.Å1_VMM71 \
  --out-dir reference/monthly_reporting_documents/outputs/from_pdf \
  --prefix gtn_anga \
  --preview /tmp/v600_anga_preview.html
```

Sources are the meters where steam/water enters the system (usually the ones
tagged with the highest supply pressure in the schema). Pass all of them —
BFS won't reach meters that aren't downstream of a declared source. If meters
are reported as unreached, either add the missing source or inspect the
preview HTML to understand the disconnect.

### How it works

1. `pdftotext -bbox-layout` → meter label coordinates.
2. `pdftocairo -svg` → vector pipe paths. The Cairo SVG embeds a
   `matrix(0.12, 0, 0, -0.12, 0, 1684)` transform that maps raw AutoCAD
   units into the same coordinate frame as the text bboxes.
3. Keep only axis-aligned black-stroke paths with `fill=none`. Drop the
   drawing frame and the right-side title block.
4. Split every H segment at every V crossing (and vice-versa) so
   T-junctions become graph nodes.
5. A meter symbol is either a stub dead-end or a gap in an otherwise
   continuous pipe. For each meter label, collect degree-1 endpoints within
   `--radius` of the label and keep either the tightest eligible gap-pair
   (flanks must not be directly connected by an edge) or the single closest
   endpoint. Merged flanks become a single node carrying the meter ID.
6. BFS from `--sources` to derive a parent tree; each meter's nearest
   upstream meter becomes its parent in the relations output.

### Tuning

- `--radius` (default 100): how far from a label to look for its pipe
  endpoints. Raise it if a distant-label meter is unreached.
- The hard-coded `gap_max` inside `assign_meter_endpoints` (110) limits how
  far apart the two flanks of an inline or corner meter can be. The
  tightest-pair-wins rule keeps it robust against overclaiming.

### Caveats

- Coefficients are always `1.0`; the schema expresses flow routing, not
  accounting weights. Virtual-meter formulas (cf. the B611 Excel case) are
  an accounting concern and layer on top of this topology.
- Sources must be declared. There is no auto-detect — the correct source
  set depends on domain knowledge (e.g. B600S/B600N for GTN ånga,
  B390.VMM70 for the SNV ånga head end).
- When a meter in the schema is drawn as a ⊗ overlaid on a continuous pipe
  line (rather than inside a gap), the parser treats it as a dead-end stub
  meter. This is usually the right interpretation — the east tap at
  `B611.VMM72` in `V600-52.E.8-001` is an example.
