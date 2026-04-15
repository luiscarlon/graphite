from pathlib import Path

from ontology import (
    Building,
    Campus,
    Database,
    Dataset,
    MediaType,
    Meter,
    MeterMeasures,
    Sensor,
    TimeseriesRef,
    load_dataset,
    write_dataset,
)


def test_roundtrip(tmp_path: Path) -> None:
    """A Dataset survives a write→read CSV roundtrip with no data loss."""
    ds = Dataset(
        campuses=[Campus(campus_id="C", name="Test")],
        buildings=[Building(building_id="B1", name="B1", campus_id="C")],
        media_types=[MediaType(media_type_id="EL", name="Electrical")],
        meters=[
            Meter(meter_id="I1", name="Intake", media_type_id="EL"),
            Meter(
                meter_id="V1",
                name="Virtual",
                building_id="B1",
                media_type_id="EL",
                is_virtual_meter=True,
            ),
        ],
        meter_measures=[
            MeterMeasures(meter_id="I1", target_kind="campus", target_id="C"),
        ],
        databases=[Database(database_id="d", name="d", kind="internal")],
        sensors=[Sensor(sensor_id="I1.energy", meter_id="I1")],
        timeseries_refs=[
            # raw ref: exercises the addressing triple
            TimeseriesRef(
                timeseries_id="I1:h",
                sensor_id="I1.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="d",
                path="ingest.hourly",
                external_id="I1",
            ),
            # derived ref: exercises sources + aggregation roundtrip
            TimeseriesRef(
                timeseries_id="I1:h.smooth",
                sensor_id="I1.energy",
                aggregate="hourly",
                kind="derived",
                preferred=True,
                sources=["I1:h"],
                aggregation="rolling_sum",
            ),
        ],
    )
    write_dataset(ds, tmp_path)
    reloaded = load_dataset(tmp_path)
    assert reloaded.model_dump() == ds.model_dump()
