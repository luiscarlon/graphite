"""DuckDB setup for the calc layer.

A calc `Connection` is an in-memory DuckDB with the ontology tables
registered and the views from `sql/views.sql` created. Everything
downstream — the Streamlit consumption section, unit tests, future
dbt ports — reads against this same surface.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from ontology import Dataset
from ontology.schema import (
    Annotation, Building, Campus, Database, Device, MediaType, Meter,
    MeterMeasures, MeterRelation, Reading, Sensor, TimeseriesRef, Zone,
)

SQL_DIR = Path(__file__).parent / "sql"

_MODELS: dict[str, type] = {
    "campuses": Campus,
    "buildings": Building,
    "zones": Zone,
    "media_types": MediaType,
    "meters": Meter,
    "relations": MeterRelation,
    "meter_measures": MeterMeasures,
    "databases": Database,
    "devices": Device,
    "sensors": Sensor,
    "timeseries_refs": TimeseriesRef,
    "readings": Reading,
    "annotations": Annotation,
}

# Canonical table name per Dataset attribute. These names are what the
# SQL files reference; keep them in sync with `sql/views.sql`.
_TABLE_NAMES: dict[str, str] = {
    "campuses": "campuses",
    "buildings": "buildings",
    "zones": "zones",
    "media_types": "media_types",
    "meters": "meters",
    "relations": "meter_relations",
    "meter_measures": "meter_measures",
    "databases": "databases",
    "devices": "devices",
    "sensors": "sensors",
    "timeseries_refs": "timeseries_refs",
    "readings": "readings",
    "annotations": "annotations",
}


def connect(ds: Dataset) -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB with the dataset + calc views loaded."""
    conn = duckdb.connect()
    _register(conn, ds)
    conn.execute((SQL_DIR / "views.sql").read_text())
    return conn


def sql(name: str) -> str:
    """Return the contents of a named .sql file under `calc/sql/`."""
    return (SQL_DIR / f"{name}.sql").read_text()


def _register(conn: duckdb.DuckDBPyConnection, ds: Dataset) -> None:
    """Register each Dataset list as a DuckDB virtual table."""
    for attr, table in _TABLE_NAMES.items():
        rows = getattr(ds, attr)
        # pandas DataFrame from a list of pydantic models. Empty list
        # still needs to register as an empty table so SQL referring to
        # it doesn't 'table not found' — we construct with explicit
        # columns from the pydantic model.
        if rows:
            df = pd.DataFrame([r.model_dump() for r in rows])
        else:
            model = _MODELS.get(attr)
            columns = list(model.model_fields) if model else []
            df = pd.DataFrame(columns=columns)
        conn.register(table, df)
