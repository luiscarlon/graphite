"""Render an ontology Dataset as a Graphviz DOT string."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ontology import Dataset, Meter, MeterRelation, Zone

COLOR_SUB = "#586e75"
COLOR_FEEDS = "#b58900"

ZONE_FILL = {
    "production": "#eaf4ff",
    "office": "#f0f7ea",
    "warehouse": "#f4efe4",
}
ZONE_FILL_DEFAULT = "#f0f0f0"


def _meter_node(m: Meter) -> str:
    if m.is_virtual_meter:
        style = 'shape=ellipse, style="dashed,filled", fillcolor="#fdf6e3"'
    else:
        style = 'shape=box, style="rounded,filled", fillcolor="#eef7ff"'
    return f'  "{m.meter_id}" [label="{m.meter_id}", {style}];'


def _active(valid_from: date | None, valid_to: date | None, as_of: date) -> bool:
    """Schema semantics: [valid_from, valid_to) with NULLs unbounded."""
    if valid_from is not None and valid_from > as_of:
        return False
    if valid_to is not None and valid_to <= as_of:
        return False
    return True


def to_dot(ds: Dataset, as_of: date | None = None) -> str:
    """Build a DOT topology diagram grouped by building.

    When `as_of` is provided, meters and relations outside their
    [valid_from, valid_to) window are excluded — letting the viewer
    inspect how the topology looked at a specific date (e.g. before or
    after a re-parenting event). `as_of=None` keeps every edge so
    non-app callers see the full history.
    """
    meters: list[Meter] = list(ds.meters)
    relations: list[MeterRelation] = list(ds.relations)
    if as_of is not None:
        meters = [m for m in meters if _active(m.valid_from, m.valid_to, as_of)]
        active_ids = {m.meter_id for m in meters}
        relations = [
            r for r in relations
            if _active(r.valid_from, r.valid_to, as_of)
            and r.parent_meter_id in active_ids
            and r.child_meter_id in active_ids
        ]
    lines: list[str] = [
        "digraph G {",
        "  rankdir=TB;",
        '  graph [fontname="Helvetica", labelloc="t"];',
        '  node [fontname="Helvetica", fontsize=10];',
        '  edge [fontname="Helvetica", fontsize=9];',
    ]

    # Campus-level meters (no building) sit outside any cluster.
    for m in meters:
        if m.building_id is None:
            lines.append(_meter_node(m))

    # Index zones and meter→zone membership.
    zones_by_building: dict[str, list[Zone]] = defaultdict(list)
    for z in ds.zones:
        zones_by_building[z.building_id].append(z)
    # A meter's zone (for clustering) comes from its `meters` relation when
    # the target_kind is a zone. Campus/building targets don't cluster.
    meter_to_zone = {
        mm.meter_id: mm.target_id
        for mm in ds.meter_measures
        if mm.target_kind == "zone"
    }

    # Group meters by (building, zone). Unzoned meters get key None.
    by_bz: dict[str, dict[str | None, list[Meter]]] = defaultdict(lambda: defaultdict(list))
    for m in meters:
        if m.building_id is None:
            continue
        by_bz[m.building_id][meter_to_zone.get(m.meter_id)].append(m)

    # One cluster per building, with nested sub-clusters per zone.
    for b in ds.buildings:
        lines.append(f'  subgraph "cluster_{b.building_id}" {{')
        lines.append(f'    label="{b.building_id}";')
        lines.append('    style="rounded,filled"; fillcolor="#f6f6f6"; color="#bbbbbb";')

        zones = zones_by_building.get(b.building_id, [])
        bmeters = by_bz.get(b.building_id, {})

        if not zones and not bmeters:
            lines.append(
                f'    "_empty_{b.building_id}" [label="(no meters)", shape=plaintext, '
                f'fontcolor="#999999"];'
            )

        # Zoned meters: one sub-cluster per zone.
        for z in zones:
            fill = ZONE_FILL.get(z.zone_type, ZONE_FILL_DEFAULT)
            lines.append(f'    subgraph "cluster_{z.zone_id}" {{')
            lines.append(f'      label="{z.name}"; fontsize=9; fontcolor="#666666";')
            lines.append(f'      style="rounded,filled"; fillcolor="{fill}"; color="#d0d0d0";')
            zmeters = bmeters.get(z.zone_id, [])
            if not zmeters:
                lines.append(
                    f'      "_empty_{z.zone_id}" [label="(empty)", shape=plaintext, '
                    f'fontcolor="#bbbbbb", fontsize=9];'
                )
            else:
                for m in zmeters:
                    lines.append("    " + _meter_node(m).lstrip())
            lines.append("    }")

        # Meters with no zone assignment land directly inside the building cluster.
        for m in bmeters.get(None, []):
            lines.append("  " + _meter_node(m).lstrip())

        lines.append("  }")

    # Edges. flow_coefficient lives on the feeds relation.
    for r in relations:
        if r.relation_type == "feeds":
            label = (
                f', label="k={r.flow_coefficient}"'
                if r.flow_coefficient is not None
                else ""
            )
            attrs = f'style=dashed, color="{COLOR_FEEDS}"{label}'
        else:  # hasSubMeter
            attrs = f'color="{COLOR_SUB}"'
        lines.append(f'  "{r.parent_meter_id}" -> "{r.child_meter_id}" [{attrs}];')

    lines.append("}")
    return "\n".join(lines)
