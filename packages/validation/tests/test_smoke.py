"""Structural validator tests.

Each rule has a minimal failing fixture; we also verify Abbey Road is clean.
"""

from __future__ import annotations

from datetime import date

from ontology import (
    Building,
    Campus,
    Database,
    Dataset,
    Meter,
    MeterRelation,
    Sensor,
    TimeseriesRef,
)
from refsite import abbey_road
from validation import Violation, validate

# ---- helpers ---------------------------------------------------------------

C = Campus(campus_id="C", name="Test")
B = Building(building_id="B1", name="B1", campus_id="C")


def _raw_ref(**overrides: object) -> TimeseriesRef:
    """Minimal valid raw ref for tests; override fields as needed."""
    base: dict[str, object] = {
        "timeseries_id": "A:1",
        "sensor_id": "A.energy",
        "aggregate": "hourly",
        "reading_type": "counter",
        "kind": "raw",
        "preferred": True,
        "database_id": "d",
        "path": "ingest.hourly",
        "external_id": "a1",
    }
    base.update(overrides)
    return TimeseriesRef(**base)


def _rules(violations: list[Violation]) -> set[str]:
    return {v.rule for v in violations}


# ---- rules ----------------------------------------------------------------


def test_abbey_road_is_clean() -> None:
    """The reference Abbey Road dataset must pass every structural rule."""
    assert validate(abbey_road.build()) == []


def test_cycle_detected() -> None:
    """Two meters that hasSubMeter each other form a cycle and must be flagged."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="A", name="A", building_id="B1", media_type_id="EL"),
            Meter(meter_id="B", name="B", building_id="B1", media_type_id="EL"),
        ],
        relations=[
            MeterRelation(parent_meter_id="A", child_meter_id="B", relation_type="hasSubMeter"),
            MeterRelation(parent_meter_id="B", child_meter_id="A", relation_type="hasSubMeter"),
        ],
    )
    assert "no_cycles" in _rules(validate(ds))


def test_feeds_requires_flow_coefficient() -> None:
    """A `feeds` edge without a flow_coefficient is meaningless and must error."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="P", name="P", building_id="B1", media_type_id="EL"),
            Meter(
                meter_id="V", name="V", building_id="B1", media_type_id="EL", is_virtual_meter=True
            ),
        ],
        relations=[
            # Missing flow_coefficient on a feeds edge.
            MeterRelation(parent_meter_id="P", child_meter_id="V", relation_type="feeds"),
        ],
    )
    assert "feeds_requires_flow_coefficient" in _rules(validate(ds))


def test_hassubmeter_forbids_flow_coefficient() -> None:
    """`hasSubMeter` is a physical containment edge — flow_coefficients don't apply."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="P", name="P", building_id="B1", media_type_id="EL"),
            Meter(meter_id="Q", name="Q", building_id="B1", media_type_id="EL"),
        ],
        relations=[
            MeterRelation(
                parent_meter_id="P",
                child_meter_id="Q",
                relation_type="hasSubMeter",
                flow_coefficient=0.5,  # should not be set
            ),
        ],
    )
    assert "hassubmeter_forbids_flow_coefficient" in _rules(validate(ds))


def test_feeds_flow_coefficients_sum_to_one() -> None:
    """Outgoing share weights from one parent must partition flow exactly."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="P", name="P", building_id="B1", media_type_id="EL"),
            Meter(
                meter_id="V1",
                name="V1",
                building_id="B1",
                media_type_id="EL",
                is_virtual_meter=True,
            ),
            Meter(
                meter_id="V2",
                name="V2",
                building_id="B1",
                media_type_id="EL",
                is_virtual_meter=True,
            ),
        ],
        relations=[
            MeterRelation(
                parent_meter_id="P", child_meter_id="V1", relation_type="feeds", flow_coefficient=0.3
            ),
            MeterRelation(
                parent_meter_id="P", child_meter_id="V2", relation_type="feeds", flow_coefficient=0.3
            ),  # sums to 0.6
        ],
    )
    assert "feeds_flow_coefficients_sum_to_one" in _rules(validate(ds))


def test_feeds_flow_coefficient_positive() -> None:
    """Negative shares are physically nonsensical and must be rejected."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="P", name="P", building_id="B1", media_type_id="EL"),
            Meter(
                meter_id="V", name="V", building_id="B1", media_type_id="EL", is_virtual_meter=True
            ),
        ],
        relations=[
            MeterRelation(
                parent_meter_id="P", child_meter_id="V", relation_type="feeds", flow_coefficient=-0.5
            ),
        ],
    )
    assert "feeds_flow_coefficient_positive" in _rules(validate(ds))


def test_referential_integrity_missing_meter() -> None:
    """Every relation endpoint must resolve to an existing meter id."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id="B1", media_type_id="EL")],
        relations=[
            MeterRelation(parent_meter_id="A", child_meter_id="ghost", relation_type="hasSubMeter"),
        ],
    )
    rules = _rules(validate(ds))
    assert "referential_integrity" in rules


def test_exactly_one_preferred_ref() -> None:
    """A sensor with multiple `preferred=True` series is ambiguous for queries."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(timeseries_id="A:1", external_id="a1", preferred=True),
            _raw_ref(timeseries_id="A:2", external_id="a2", preferred=True),
        ],
    )
    rules = _rules(validate(ds))
    assert "exactly_one_preferred_ref" in rules


def test_validity_overlap() -> None:
    """Two relations between the same pair must have disjoint validity windows."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="A", name="A", building_id=None, media_type_id="EL"),
            Meter(meter_id="B", name="B", building_id="B1", media_type_id="EL"),
        ],
        relations=[
            MeterRelation(
                parent_meter_id="A",
                child_meter_id="B",
                relation_type="hasSubMeter",
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 3, 1),
            ),
            MeterRelation(
                parent_meter_id="A",
                child_meter_id="B",
                relation_type="hasSubMeter",
                valid_from=date(2026, 2, 1),  # overlaps the first interval
                valid_to=date(2026, 4, 1),
            ),
        ],
    )
    assert "validity_non_overlapping" in _rules(validate(ds))


def test_standalone_campus_meter() -> None:
    """A campus-level meter with no relations is valid."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="I", name="Standalone", building_id=None, media_type_id="EL")],
        relations=[],
    )
    assert "orphan_meter" not in _rules(validate(ds))


def test_ref_raw_missing_addressing() -> None:
    """A raw ref must carry the full (database_id, path, external_id) triple."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(path=None),  # missing path
        ],
    )
    assert "ref_raw_missing_addressing" in _rules(validate(ds))


def test_ref_derived_has_addressing() -> None:
    """A derived ref must not carry database_id/path/external_id/device_id."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(preferred=True),  # anchor so preferred rule passes
            TimeseriesRef(
                timeseries_id="A:derived",
                sensor_id="A.energy",
                aggregate="hourly",
                kind="derived",
                preferred=False,
                sources=["A:1"],
                aggregation="rolling_sum",
                database_id="d",  # illegal on derived
            ),
        ],
    )
    assert "ref_derived_has_addressing" in _rules(validate(ds))


def test_ref_aggregation_vocabulary() -> None:
    """Derived refs must use an aggregation from the allowed vocabulary."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(preferred=True),
            TimeseriesRef(
                timeseries_id="A:derived",
                sensor_id="A.energy",
                aggregate="hourly",
                kind="derived",
                preferred=False,
                sources=["A:1"],
                aggregation="weighted_sum",  # not in vocabulary
            ),
        ],
    )
    assert "ref_aggregation_vocabulary" in _rules(validate(ds))


def test_ref_source_missing() -> None:
    """A derived ref that references a non-existent source must be flagged."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(preferred=True),
            TimeseriesRef(
                timeseries_id="A:derived",
                sensor_id="A.energy",
                aggregate="hourly",
                kind="derived",
                preferred=False,
                sources=["ghost"],
                aggregation="rolling_sum",
            ),
        ],
    )
    assert "ref_source_missing" in _rules(validate(ds))


def test_ref_validity_non_overlapping() -> None:
    """Two raw refs on the same sensor+aggregate+database+path can't overlap."""
    db = Database(database_id="d", name="d", kind="internal")
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[Meter(meter_id="A", name="A", building_id=None, media_type_id="EL")],
        databases=[db],
        sensors=[Sensor(sensor_id="A.energy", meter_id="A")],
        timeseries_refs=[
            _raw_ref(
                timeseries_id="A:1",
                external_id="a1",
                device_id="DEV-1",
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 3, 1),
                preferred=False,
            ),
            _raw_ref(
                timeseries_id="A:2",
                external_id="a2",
                device_id="DEV-2",
                valid_from=date(2026, 2, 1),  # overlaps A:1
                valid_to=date(2026, 4, 1),
                preferred=False,
            ),
        ],
    )
    assert "ref_validity_non_overlapping" in _rules(validate(ds))


def test_media_consistency() -> None:
    """A submeter must carry the same medium (EL, KYLA, …) as its parent."""
    ds = Dataset(
        campuses=[C],
        buildings=[B],
        meters=[
            Meter(meter_id="A", name="A", building_id="B1", media_type_id="EL"),
            Meter(meter_id="B", name="B", building_id="B1", media_type_id="KYLA"),
        ],
        relations=[
            MeterRelation(parent_meter_id="A", child_meter_id="B", relation_type="hasSubMeter"),
        ],
    )
    assert "media_consistency" in _rules(validate(ds))
