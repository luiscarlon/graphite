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

    A class with instances, per ontology_proposal.md §7.3 + §8 + §10.
    Meters point at a MediaType via `media_type_id`; the TTL emission
    becomes `ext:mediaType :media_<id>`.

    Carries the Brick meter class (`brick_meter_class`) and optional
    substance (`brick_substance`) so the TTL converter can derive each
    meter's `rdf:type` and `brick:hasSubstance` from its media type
    without a hard-coded lookup. See §10.
    """

    media_type_id: str
    name: str
    description: str | None = None
    # Brick class name (no namespace prefix) for meters of this media,
    # e.g. "Electrical_Meter", "Chilled_Water_Meter",
    # "Thermal_Power_Meter", "Water_Meter".
    brick_meter_class: str | None = None
    # Brick substance name (no namespace prefix), e.g. "Chilled_Water",
    # "Hot_Water", "Steam", "Water". Null when the medium has no
    # substance (electricity).
    brick_substance: str | None = None


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
    # Required for `feeds` (share or aggregator weight). Null for
    # `hasSubMeter`. Emitted to TTL as `ext:flowCoefficient` on the
    # `feeds` edge (RDF-star annotation). See §7.5 + §10.
    flow_coefficient: float | None = None
    # Validity interval (inclusive from, exclusive to). Null = unbounded.
    valid_from: date | None = None
    valid_to: date | None = None
    derived_from: str | None = None


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
    kind: str  # internal | external → ext:databaseKind
    identifier: str | None = None


class Device(BaseModel):
    """Physical hardware identity, separate from the logical meter.

    `ext:Device`, per ontology_proposal.md §7.4 + §10. A timeseries ref
    points at a Device via `ext:producedBy`. Multiple timeseries refs
    on the same sensor may point at the same or different devices
    (device replacement, redundancy).

    v1 ships with stub rows: one row per distinct `device_id` currently
    referenced by `timeseries_refs`, with `serial` / `manufacturer` null
    until the hardware inventory lands. Placeholder device IDs default
    to the logical meter name.
    """

    device_id: str
    serial: str | None = None
    manufacturer: str | None = None
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
    # QUDT identifier fragment (no namespace prefix). E.g. "KiloW-HR",
    # "MegaW-HR", "M3", "DEG_C", "HZ". TTL emission wraps as `unit:<value>`.
    # See §10.
    unit: str = "KiloW-HR"
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
    aggregation: str | None = None   # sum | rolling_sum | bracket | interpolate | slice

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


class Annotation(BaseModel):
    annotation_id: str
    target_kind: str  # meter | building | campus | timeseries
    target_id: str
    category: str  # outage | swap | calibration | data_quality | patch | unknown
    valid_from: date | None = None
    valid_to: date | None = None
    description: str = ""
    related_refs: list[str] = Field(default_factory=list)
    media: str | None = None
    # True = documented/understood, no open action; False = investigation
    # pending, calibration recommended, topology conflict unresolved, etc.
    is_resolved: bool = True

    @field_validator("related_refs", mode="before")
    @classmethod
    def _split_refs(cls, v: object) -> object:
        if isinstance(v, str):
            return [x for x in v.split("|") if x]
        return v

    @field_validator("is_resolved", mode="before")
    @classmethod
    def _coerce_resolved(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("", "true", "1", "yes"):
                return True
            if s in ("false", "0", "no"):
                return False
        return v


class Dataset(BaseModel):
    campuses: list[Campus] = Field(default_factory=list)
    buildings: list[Building] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    media_types: list[MediaType] = Field(default_factory=list)
    meters: list[Meter] = Field(default_factory=list)
    relations: list[MeterRelation] = Field(default_factory=list)
    meter_measures: list[MeterMeasures] = Field(default_factory=list)
    databases: list[Database] = Field(default_factory=list)
    devices: list[Device] = Field(default_factory=list)
    sensors: list[Sensor] = Field(default_factory=list)
    timeseries_refs: list[TimeseriesRef] = Field(default_factory=list)
    readings: list[Reading] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)

    def filter_by_media(self, media_type_id: str) -> "Dataset":
        """Return a new Dataset scoped to a single media type."""
        meter_ids = {m.meter_id for m in self.meters if m.media_type_id == media_type_id}
        sensor_ids = {s.sensor_id for s in self.sensors if s.meter_id in meter_ids}
        ts_ids = {tr.timeseries_id for tr in self.timeseries_refs if tr.sensor_id in sensor_ids}
        building_ids = {m.building_id for m in self.meters
                        if m.media_type_id == media_type_id and m.building_id}
        return Dataset(
            campuses=self.campuses,
            buildings=[b for b in self.buildings if b.building_id in building_ids],
            zones=[z for z in self.zones if z.building_id in building_ids],
            media_types=[mt for mt in self.media_types if mt.media_type_id == media_type_id],
            meters=[m for m in self.meters if m.meter_id in meter_ids],
            relations=[r for r in self.relations
                       if r.parent_meter_id in meter_ids or r.child_meter_id in meter_ids],
            meter_measures=[mm for mm in self.meter_measures if mm.meter_id in meter_ids],
            databases=self.databases,
            devices=[d for d in self.devices
                     if any(tr.device_id == d.device_id for tr in self.timeseries_refs
                            if tr.sensor_id in sensor_ids and tr.device_id)],
            sensors=[s for s in self.sensors if s.sensor_id in sensor_ids],
            timeseries_refs=[tr for tr in self.timeseries_refs if tr.sensor_id in sensor_ids],
            readings=[r for r in self.readings if r.timeseries_id in ts_ids],
            annotations=[a for a in self.annotations
                         if (a.target_id in meter_ids | ts_ids | building_ids
                             or a.target_kind == "campus")
                         and (a.media is None or a.media.upper() == media_type_id.upper())],
        )
