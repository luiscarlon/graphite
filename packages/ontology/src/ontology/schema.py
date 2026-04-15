"""Pydantic table schemas for the ontology."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class Campus(BaseModel):
    campus_id: str
    name: str                          # → rdfs:label
    identifier: str | None = None      # → dcterms:identifier (None = use campus_id)


class Building(BaseModel):
    building_id: str
    name: str
    campus_id: str
    identifier: str | None = None


class Zone(BaseModel):
    zone_id: str
    name: str
    building_id: str
    zone_type: str  # e.g. production, office, warehouse
    identifier: str | None = None


class MediaType(BaseModel):
    """Operational media grouping (EL, KYLA, VÄRME, …).

    A class with instances, per ontology_proposal.md §7.3 + §8. Meters
    point at a MediaType via `media_type_id`; the TTL emission becomes
    `ext:mediaType :media_<id>`.
    """

    media_type_id: str
    name: str
    description: str | None = None


class Meter(BaseModel):
    meter_id: str
    name: str
    building_id: str | None = None      # None = campus-level (e.g. intake)
    media_type_id: str                  # → ext:mediaType
    is_virtual_meter: bool = False      # → brick:isVirtualMeter
    identifier: str | None = None
    # Validity interval (inclusive from, exclusive to). Null = unbounded.
    valid_from: date | None = None
    valid_to: date | None = None


class MeterRelation(BaseModel):
    parent_meter_id: str
    child_meter_id: str
    relation_type: str  # hasSubMeter | feeds
    # Required for `feeds` (share or aggregator weight). Null for `hasSubMeter`.
    coefficient: float | None = None
    # Validity interval (inclusive from, exclusive to). Null = unbounded.
    valid_from: date | None = None
    valid_to: date | None = None


class MeterMeasures(BaseModel):
    """`brick:meters` — what a meter measures.

    Generalizes the old `MeterZoneAssignment`. `target_kind` picks the
    entity namespace; `target_id` is the primary key there.
    """

    meter_id: str
    target_kind: str            # campus | building | zone | equipment
    target_id: str
    valid_from: date | None = None
    valid_to: date | None = None


class Database(BaseModel):
    database_id: str
    name: str
    kind: str  # internal | external
    identifier: str | None = None


class Sensor(BaseModel):
    """A measurement point on a meter.

    Corresponds to `brick:hasPoint` in the proposal. One meter can host
    many sensors (energy, power, temperature, …) but for the electrical
    test site each meter has one Energy_Sensor.
    """

    sensor_id: str
    meter_id: str
    point_type: str = "Energy_Sensor"  # brick class
    unit: str = "kWh"
    identifier: str | None = None


class TimeseriesRef(BaseModel):
    """A series attached to a sensor.

    Two kinds:

    - **raw**: points at pre-existing upstream data. Carries the
      addressing triple (`database_id`, `path`, `external_id`) and
      optionally a `device_id` for the field device that produced it.
    - **derived**: declaration only. Carries `sources` + `aggregation`.
      The DW layer materializes it from its sources on demand; the
      ontology never names a storage path for it.

    The two shapes are disjoint and enforced by the `ref_addressing`
    validator.
    """

    timeseries_id: str          # ontology-level IRI (Brick instance id)
    sensor_id: str
    aggregate: str              # hourly | monthly | ...
    reading_type: str = "counter"   # counter | delta
    kind: str = "raw"           # raw | derived
    preferred: bool = True
    # Validity of this particular ref - e.g. a device's in-service window.
    valid_from: date | None = None
    valid_to: date | None = None

    # --- raw-only: addressing triple + device ---
    database_id: str | None = None
    path: str | None = None          # schema.table within the database
    external_id: str | None = None   # row/column key - brick ref:hasTimeseriesId
    device_id: str | None = None

    # --- derived-only: declaration for the DW to materialize ---
    sources: list[str] = Field(default_factory=list)
    aggregation: str | None = None   # sum | rolling_sum

    @field_validator("sources", mode="before")
    @classmethod
    def _split_sources(cls, v: object) -> object:
        """CSV cells serialize list[str] as pipe-joined (`M6:h.A|M6:h.B`)."""
        if isinstance(v, str):
            return [x for x in v.split("|") if x]
        return v


class Reading(BaseModel):
    timeseries_id: str
    timestamp: datetime  # for counter: time of reading; for delta: period start
    value: float
    # When the value was recorded. Distinct from `timestamp` for backdated
    # corrections (e.g. Avläsning reading for Jan entered in March). Null
    # means "recorded at or near `timestamp`". Multiple rows sharing
    # (timeseries_id, timestamp) but with different `recorded_at` form a
    # correction trail; the latest `recorded_at` wins.
    recorded_at: datetime | None = None


class Dataset(BaseModel):
    campuses: list[Campus] = Field(default_factory=list)
    buildings: list[Building] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    media_types: list[MediaType] = Field(default_factory=list)
    meters: list[Meter] = Field(default_factory=list)
    relations: list[MeterRelation] = Field(default_factory=list)
    meter_measures: list[MeterMeasures] = Field(default_factory=list)
    databases: list[Database] = Field(default_factory=list)
    sensors: list[Sensor] = Field(default_factory=list)
    timeseries_refs: list[TimeseriesRef] = Field(default_factory=list)
    readings: list[Reading] = Field(default_factory=list)
