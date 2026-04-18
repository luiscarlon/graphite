"""CSV load and write for Dataset."""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from .schema import (
    Annotation,
    Building,
    Campus,
    Database,
    Dataset,
    Device,
    MediaType,
    Meter,
    MeterMeasures,
    MeterRelation,
    Reading,
    Sensor,
    TimeseriesRef,
    Zone,
)

FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "campuses": ("campuses.csv", Campus),
    "buildings": ("buildings.csv", Building),
    "zones": ("zones.csv", Zone),
    "media_types": ("media_types.csv", MediaType),
    "meters": ("meters.csv", Meter),
    "relations": ("meter_relations.csv", MeterRelation),
    "meter_measures": ("meter_measures.csv", MeterMeasures),
    "databases": ("databases.csv", Database),
    "devices": ("devices.csv", Device),
    "sensors": ("sensors.csv", Sensor),
    "timeseries_refs": ("timeseries_refs.csv", TimeseriesRef),
    "readings": ("readings.csv", Reading),
    "annotations": ("annotations.csv", Annotation),
}


def _read_csv[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    """Empty cells are dropped so pydantic falls back to each field's default."""
    if not path.exists():
        return []
    rows: list[T] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            cleaned = {k: v for k, v in raw.items() if v != ""}
            rows.append(model.model_validate(cleaned))
    return rows


def _encode(value: object) -> str:
    """CSV cell encoding: None → '', list → pipe-joined, else str()."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(str(x) for x in value)
    return str(value)


def _write_csv(path: Path, rows: list[BaseModel], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            d = r.model_dump()
            writer.writerow({k: _encode(d[k]) for k in fields})


def load_dataset(root: Path) -> Dataset:
    """Load a Dataset from a directory of CSVs."""
    return Dataset(
        campuses=_read_csv(root / FILES["campuses"][0], Campus),
        buildings=_read_csv(root / FILES["buildings"][0], Building),
        zones=_read_csv(root / FILES["zones"][0], Zone),
        media_types=_read_csv(root / FILES["media_types"][0], MediaType),
        meters=_read_csv(root / FILES["meters"][0], Meter),
        relations=_read_csv(root / FILES["relations"][0], MeterRelation),
        meter_measures=_read_csv(root / FILES["meter_measures"][0], MeterMeasures),
        databases=_read_csv(root / FILES["databases"][0], Database),
        devices=_read_csv(root / FILES["devices"][0], Device),
        sensors=_read_csv(root / FILES["sensors"][0], Sensor),
        timeseries_refs=_read_csv(root / FILES["timeseries_refs"][0], TimeseriesRef),
        readings=_read_csv(root / FILES["readings"][0], Reading),
        annotations=_read_csv(root / FILES["annotations"][0], Annotation),
    )


def write_dataset(ds: Dataset, root: Path) -> None:
    """Write a Dataset to a directory as one CSV per table."""
    root.mkdir(parents=True, exist_ok=True)
    _write_csv(root / FILES["campuses"][0], list(ds.campuses), list(Campus.model_fields))
    _write_csv(root / FILES["buildings"][0], list(ds.buildings), list(Building.model_fields))
    _write_csv(root / FILES["zones"][0], list(ds.zones), list(Zone.model_fields))
    _write_csv(
        root / FILES["media_types"][0], list(ds.media_types), list(MediaType.model_fields)
    )
    _write_csv(root / FILES["meters"][0], list(ds.meters), list(Meter.model_fields))
    _write_csv(
        root / FILES["relations"][0], list(ds.relations), list(MeterRelation.model_fields)
    )
    _write_csv(
        root / FILES["meter_measures"][0],
        list(ds.meter_measures),
        list(MeterMeasures.model_fields),
    )
    _write_csv(root / FILES["databases"][0], list(ds.databases), list(Database.model_fields))
    _write_csv(root / FILES["devices"][0], list(ds.devices), list(Device.model_fields))
    _write_csv(root / FILES["sensors"][0], list(ds.sensors), list(Sensor.model_fields))
    _write_csv(
        root / FILES["timeseries_refs"][0],
        list(ds.timeseries_refs),
        list(TimeseriesRef.model_fields),
    )
    _write_csv(root / FILES["readings"][0], list(ds.readings), list(Reading.model_fields))
    _write_csv(root / FILES["annotations"][0], list(ds.annotations), list(Annotation.model_fields))
