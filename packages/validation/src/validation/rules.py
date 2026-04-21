"""Structural validators - write-time gates on the ontology graph."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ontology import Dataset, MeterRelation

from .models import Violation

EPS = 1e-9


def check_cycles(ds: Dataset) -> list[Violation]:
    """No cycles in the meter graph at any single point in time.

    A cycle is a real violation only if every edge in it is simultaneously
    valid. A direction flip encoded as `A→B (valid_to=t)` + `B→A
    (valid_from=t)` is topologically a back-edge but has an empty
    temporal intersection — so it's not flagged.
    """
    adj: dict[str, list[tuple[str, MeterRelation]]] = defaultdict(list)
    for r in ds.relations:
        adj[r.parent_meter_id].append((r.child_meter_id, r))

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(lambda: WHITE)
    violations: list[Violation] = []

    def dfs(node: str, path: list[str], edges: list[MeterRelation]) -> None:
        color[node] = GRAY
        path.append(node)
        for nxt, rel in adj.get(node, []):
            if color[nxt] == GRAY:
                start = path.index(nxt)
                cycle_nodes = [*path[start:], nxt]
                cycle_edges = [*edges[start:], rel]
                if _edges_cotemporal(cycle_edges):
                    violations.append(
                        Violation(
                            rule="no_cycles",
                            message=f"cycle in meter graph: {' -> '.join(cycle_nodes)}",
                            context={"cycle": cycle_nodes},
                        )
                    )
            elif color[nxt] == WHITE:
                edges.append(rel)
                dfs(nxt, path, edges)
                edges.pop()
        path.pop()
        color[node] = BLACK

    for m in ds.meters:
        if color[m.meter_id] == WHITE:
            dfs(m.meter_id, [], [])
    return violations


def _edges_cotemporal(edges: list[MeterRelation]) -> bool:
    """True if every edge's validity window overlaps every other's.

    A cycle needs a moment in time where all its edges are active — i.e.
    the intersection of all `[valid_from, valid_to)` intervals is
    non-empty. Equivalent to: the max of all valid_from < the min of
    all valid_to.
    """
    lo = max((e.valid_from or date.min) for e in edges)
    hi = min((e.valid_to or date.max) for e in edges)
    return lo < hi


def check_feeds_coefficients(ds: Dataset) -> list[Violation]:
    """feeds edges require a positive flow_coefficient; hasSubMeter forbids one.
    Outgoing flow_coefficients from any parent must sum to 1.0 (± EPS).
    """
    violations: list[Violation] = []
    sums: dict[str, float] = defaultdict(float)

    for r in ds.relations:
        if r.relation_type == "feeds":
            if r.flow_coefficient is None:
                violations.append(
                    Violation(
                        rule="feeds_requires_flow_coefficient",
                        message=(
                            f"feeds {r.parent_meter_id}->{r.child_meter_id} "
                            f"missing flow_coefficient"
                        ),
                        context={
                            "parent": r.parent_meter_id,
                            "child": r.child_meter_id,
                        },
                    )
                )
                continue
            if r.flow_coefficient <= 0:
                violations.append(
                    Violation(
                        rule="feeds_flow_coefficient_positive",
                        message=(
                            f"feeds {r.parent_meter_id}->{r.child_meter_id} "
                            f"has non-positive flow_coefficient {r.flow_coefficient}"
                        ),
                        context={
                            "parent": r.parent_meter_id,
                            "child": r.child_meter_id,
                            "flow_coefficient": r.flow_coefficient,
                        },
                    )
                )
            sums[r.parent_meter_id] += r.flow_coefficient
        elif r.relation_type == "hasSubMeter" and r.flow_coefficient is not None:
            violations.append(
                Violation(
                    rule="hassubmeter_forbids_flow_coefficient",
                    message=(
                        f"hasSubMeter {r.parent_meter_id}->{r.child_meter_id} "
                        f"carries a flow_coefficient ({r.flow_coefficient})"
                    ),
                    context={
                        "parent": r.parent_meter_id,
                        "child": r.child_meter_id,
                        "flow_coefficient": r.flow_coefficient,
                    },
                )
            )

    for parent, total in sums.items():
        if abs(total - 1.0) > EPS:
            violations.append(
                Violation(
                    rule="feeds_flow_coefficients_sum_to_one",
                    message=(
                        f"outgoing flow_coefficients from {parent} sum to "
                        f"{total:.6f}, expected 1.0"
                    ),
                    context={"parent": parent, "sum": total},
                )
            )
    return violations


def check_referential_integrity(ds: Dataset) -> list[Violation]:
    """Every id referenced in a table must exist in its source table."""
    meter_ids = {m.meter_id for m in ds.meters}
    building_ids = {b.building_id for b in ds.buildings}
    zone_ids = {z.zone_id for z in ds.zones}
    campus_ids = {c.campus_id for c in ds.campuses}
    database_ids = {d.database_id for d in ds.databases}
    device_ids = {d.device_id for d in ds.devices}
    sensor_ids = {s.sensor_id for s in ds.sensors}
    media_type_ids = {mt.media_type_id for mt in ds.media_types}

    violations: list[Violation] = []

    def miss(table: str, field: str, value: str) -> None:
        violations.append(
            Violation(
                rule="referential_integrity",
                message=f"{table}.{field}={value!r} references a missing row",
                context={"table": table, "field": field, "missing": value},
            )
        )

    for m in ds.meters:
        if m.building_id is not None and m.building_id not in building_ids:
            miss("meters", "building_id", m.building_id)
        if media_type_ids and m.media_type_id not in media_type_ids:
            miss("meters", "media_type_id", m.media_type_id)
    for b in ds.buildings:
        if b.campus_id not in campus_ids:
            miss("buildings", "campus_id", b.campus_id)
    for z in ds.zones:
        if z.building_id not in building_ids:
            miss("zones", "building_id", z.building_id)
    for r in ds.relations:
        if r.parent_meter_id not in meter_ids:
            miss("relations", "parent_meter_id", r.parent_meter_id)
        if r.child_meter_id not in meter_ids:
            miss("relations", "child_meter_id", r.child_meter_id)
    for mm in ds.meter_measures:
        if mm.meter_id not in meter_ids:
            miss("meter_measures", "meter_id", mm.meter_id)
        # target_id must resolve to the declared target_kind's table.
        target_table: set[str]
        if mm.target_kind == "campus":
            target_table = campus_ids
        elif mm.target_kind == "building":
            target_table = building_ids
        elif mm.target_kind == "zone":
            target_table = zone_ids
        else:
            target_table = set()  # equipment not modeled yet
        if target_table and mm.target_id not in target_table:
            miss("meter_measures", f"{mm.target_kind}.target_id", mm.target_id)
    for s in ds.sensors:
        if s.meter_id not in meter_ids:
            miss("sensors", "meter_id", s.meter_id)
    for tr in ds.timeseries_refs:
        if tr.sensor_id not in sensor_ids:
            miss("timeseries_refs", "sensor_id", tr.sensor_id)
        if tr.database_id is not None and tr.database_id not in database_ids:
            miss("timeseries_refs", "database_id", tr.database_id)
        # Devices are only checked when the devices table is populated;
        # v1 allows bare device_id strings while the hardware inventory
        # is incomplete (per §7.4).
        if (
            tr.device_id is not None
            and device_ids
            and tr.device_id not in device_ids
        ):
            miss("timeseries_refs", "device_id", tr.device_id)
    return violations


def check_preferred_refs(ds: Dataset) -> list[Violation]:
    """Exactly one preferred=true per sensor (among its timeseries refs)."""
    refs_by_sensor: dict[str, list[bool]] = defaultdict(list)
    for tr in ds.timeseries_refs:
        refs_by_sensor[tr.sensor_id].append(tr.preferred)

    violations: list[Violation] = []
    for sensor_id, prefs in refs_by_sensor.items():
        count = sum(prefs)
        if count != 1:
            violations.append(
                Violation(
                    rule="exactly_one_preferred_ref",
                    message=(
                        f"sensor {sensor_id} has {count} preferred refs (expected 1)"
                    ),
                    context={"sensor_id": sensor_id, "preferred_count": count},
                )
            )
    return violations


def check_validity_overlap(ds: Dataset) -> list[Violation]:
    """Rows for the same (parent, child, relation_type) must not overlap in validity."""
    groups: dict[tuple[str, str, str], list[MeterRelation]] = defaultdict(list)
    for r in ds.relations:
        groups[(r.parent_meter_id, r.child_meter_id, r.relation_type)].append(r)

    violations: list[Violation] = []
    for key, rels in groups.items():
        if len(rels) < 2:
            continue
        for i in range(len(rels)):
            for j in range(i + 1, len(rels)):
                a, b = rels[i], rels[j]
                if _overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to):
                    violations.append(
                        Violation(
                            rule="validity_non_overlapping",
                            message=(
                                f"relation {key} has overlapping validity intervals"
                            ),
                            context={
                                "relation": list(key),
                                "a": [_d(a.valid_from), _d(a.valid_to)],
                                "b": [_d(b.valid_from), _d(b.valid_to)],
                            },
                        )
                    )
    return violations


def _overlap(
    a_from: date | None,
    a_to: date | None,
    b_from: date | None,
    b_to: date | None,
) -> bool:
    """[from, to) semantics, None = unbounded."""
    a_f = a_from or date.min
    a_t = a_to or date.max
    b_f = b_from or date.min
    b_t = b_to or date.max
    return a_f < b_t and b_f < a_t


def _d(d: date | None) -> str:
    return d.isoformat() if d is not None else "-"


def check_orphan_meters(ds: Dataset) -> list[Violation]:
    """A meter attached to a building should appear in at least one relation.
    Campus-level meters (building_id is None) may legitimately stand alone
    (external tenant / standalone intake pattern).
    """
    in_relation: set[str] = set()
    for r in ds.relations:
        in_relation.add(r.parent_meter_id)
        in_relation.add(r.child_meter_id)

    return [
        Violation(
            rule="orphan_meter",
            message=f"meter {m.meter_id} has a building but no relations",
            context={"meter_id": m.meter_id, "building_id": m.building_id},
        )
        for m in ds.meters
        if m.building_id is not None and m.meter_id not in in_relation
    ]


ALLOWED_AGGREGATIONS = {"sum", "rolling_sum", "bracket", "interpolate", "slice"}


def check_ref_shape(ds: Dataset) -> list[Violation]:
    """A ts ref is either kind=raw (addressing triple) or kind=derived
    (sources + aggregation). The two shapes are disjoint."""
    violations: list[Violation] = []
    for tr in ds.timeseries_refs:
        if tr.kind not in {"raw", "derived"}:
            violations.append(
                Violation(
                    rule="ref_kind_invalid",
                    message=f"ts ref {tr.timeseries_id} has invalid kind {tr.kind!r}",
                    context={"timeseries_id": tr.timeseries_id, "kind": tr.kind},
                )
            )
            continue

        if tr.kind == "raw":
            missing = [
                f for f in ("database_id", "path", "external_id")
                if getattr(tr, f) is None
            ]
            if missing:
                violations.append(
                    Violation(
                        rule="ref_raw_missing_addressing",
                        message=(
                            f"raw ts ref {tr.timeseries_id} is missing "
                            f"{', '.join(missing)}"
                        ),
                        context={"timeseries_id": tr.timeseries_id, "missing": missing},
                    )
                )
            if tr.sources or tr.aggregation is not None:
                violations.append(
                    Violation(
                        rule="ref_raw_has_derived_fields",
                        message=(
                            f"raw ts ref {tr.timeseries_id} must not carry "
                            f"sources / aggregation"
                        ),
                        context={"timeseries_id": tr.timeseries_id},
                    )
                )

        else:  # derived
            if not tr.sources or tr.aggregation is None:
                violations.append(
                    Violation(
                        rule="ref_derived_missing_declaration",
                        message=(
                            f"derived ts ref {tr.timeseries_id} requires "
                            f"sources and aggregation"
                        ),
                        context={"timeseries_id": tr.timeseries_id},
                    )
                )
            for field in ("database_id", "path", "external_id", "device_id"):
                if getattr(tr, field) is not None:
                    violations.append(
                        Violation(
                            rule="ref_derived_has_addressing",
                            message=(
                                f"derived ts ref {tr.timeseries_id} must not "
                                f"carry {field} (the DW materializes it)"
                            ),
                            context={
                                "timeseries_id": tr.timeseries_id,
                                "field": field,
                            },
                        )
                    )
            if (
                tr.aggregation is not None
                and tr.aggregation not in ALLOWED_AGGREGATIONS
            ):
                violations.append(
                    Violation(
                        rule="ref_aggregation_vocabulary",
                        message=(
                            f"derived ts ref {tr.timeseries_id} uses "
                            f"aggregation {tr.aggregation!r}; must be one of "
                            f"{sorted(ALLOWED_AGGREGATIONS)}"
                        ),
                        context={
                            "timeseries_id": tr.timeseries_id,
                            "aggregation": tr.aggregation,
                        },
                    )
                )
    return violations


def check_ref_sources_resolve(ds: Dataset) -> list[Violation]:
    """Every source id on a derived ref resolves to another ts ref."""
    ts_ids = {tr.timeseries_id for tr in ds.timeseries_refs}
    violations: list[Violation] = []
    for tr in ds.timeseries_refs:
        for src in tr.sources:
            if src not in ts_ids:
                violations.append(
                    Violation(
                        rule="ref_source_missing",
                        message=(
                            f"derived ref {tr.timeseries_id} references "
                            f"missing source {src!r}"
                        ),
                        context={"timeseries_id": tr.timeseries_id, "source": src},
                    )
                )
            elif src == tr.timeseries_id:
                violations.append(
                    Violation(
                        rule="ref_source_self",
                        message=(
                            f"derived ref {tr.timeseries_id} lists itself "
                            f"as a source"
                        ),
                        context={"timeseries_id": tr.timeseries_id},
                    )
                )
    return violations


def check_ref_validity_non_overlapping(ds: Dataset) -> list[Violation]:
    """Measured ts refs on the same meter + aggregate must not overlap in time.

    Derived refs are skipped: they're computed from sources, not measured,
    so the "two meters reading the same thing at the same time" concern
    doesn't apply to them. Refs that differ in database/source (e.g.
    internal hourly counter + external monthly delta on the same meter)
    are intentionally separate data feeds and also don't conflict.
    """
    from ontology import TimeseriesRef

    # Group by (sensor, aggregate, database, path). Two refs that differ
    # in any of those are different data feeds and don't conflict.
    groups: dict[tuple[str, str, str | None, str | None], list[TimeseriesRef]] = (
        defaultdict(list)
    )
    for tr in ds.timeseries_refs:
        if tr.kind != "raw":
            continue
        groups[(tr.sensor_id, tr.aggregate, tr.database_id, tr.path)].append(tr)

    violations: list[Violation] = []
    for (sensor_id, aggregate, _db, _path), refs in groups.items():
        if len(refs) < 2:
            continue
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                a = refs[i]
                b = refs[j]
                if _overlap(a.valid_from, a.valid_to, b.valid_from, b.valid_to):
                    violations.append(
                        Violation(
                            rule="ref_validity_non_overlapping",
                            message=(
                                f"ts refs {a.timeseries_id} and "
                                f"{b.timeseries_id} on sensor "
                                f"{sensor_id}/{aggregate} have "
                                f"overlapping validity"
                            ),
                            context={
                                "sensor_id": sensor_id,
                                "a": a.timeseries_id,
                                "b": b.timeseries_id,
                            },
                        )
                    )
    return violations


def check_media_consistency(ds: Dataset) -> list[Violation]:
    """Parent and child of an edge must share the same media type."""
    by_id = {m.meter_id: m for m in ds.meters}
    violations: list[Violation] = []
    for r in ds.relations:
        p = by_id.get(r.parent_meter_id)
        c = by_id.get(r.child_meter_id)
        if p is None or c is None:
            continue  # referential integrity handles the missing side
        if p.media_type_id != c.media_type_id:
            violations.append(
                Violation(
                    rule="media_consistency",
                    message=(
                        f"media mismatch {r.parent_meter_id}({p.media_type_id}) -> "
                        f"{r.child_meter_id}({c.media_type_id})"
                    ),
                    context={
                        "parent": r.parent_meter_id,
                        "parent_media_type_id": p.media_type_id,
                        "child": r.child_meter_id,
                        "child_media_type_id": c.media_type_id,
                    },
                )
            )
    return violations


RULES = [
    check_cycles,
    check_feeds_coefficients,
    check_referential_integrity,
    check_preferred_refs,
    check_validity_overlap,
    check_ref_shape,
    check_ref_sources_resolve,
    check_ref_validity_non_overlapping,
    check_media_consistency,
]


def validate(ds: Dataset) -> list[Violation]:
    """Run all structural validators and return all violations (empty = clean)."""
    return [v for rule in RULES for v in rule(ds)]
