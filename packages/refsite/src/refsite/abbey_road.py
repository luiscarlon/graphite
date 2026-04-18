"""Abbey Road reference site - iteration 1.

Topology (electrical only):

    I1, I2, I3 (three supplier-side intakes, external)
     │   │   │
     ╌feeds(1.0)╌> POOL (virtual aggregator of supplier side)
                    │
                    └─ M0 (our real intake meter, just after the mixing station)
                        │
                        ├─ M1                               (B1 office)
                        │  ├─ M2                            (B1 office sub a)
                        │  └─ M3                            (B1 office sub b)
                        ├─ M4                               (B1 prod trunk)
                        │  └─ M5                            (B1 prod leaf)
                        │     ├─ M6                         (B2 office)
                        │     └─ M7                         (B2 prod trunk)
                        │        └─ M11                     (B2 sub-panel; split
                        │                                    point for B3/B4
                        │                                    with unknown
                        │                                    internal allocation)
                        │           ╌feeds(0.7)╌> V1        (B3, no real meter)
                        │           ╌feeds(0.3)╌> V2        (B4, no real meter)
                        └─ M8                               (B5 warehouse)
                           └─ M12                           (B5 sub-panel; split
                                                             point for B7/B8
                                                             branch, M9 hangs
                                                             under V4)
                              ╌feeds(0.4)╌> V3              (B7, no real meter)
                              ╌feeds(0.6)╌> V4              (B8, no real meter)
                                            └─ M9           (B9 warehouse; real
                                                             submeter under the
                                                             virtual - GTN Kyla
                                                             B611 analog)
                                               └─ M10       (shared leaf, no
                                                             building; splits
                                                             to B10 + B11)
                                                  ╌feeds(0.5)╌> V5   (B10)
                                                  ╌feeds(0.5)╌> V6   (B11)

Modelling rule: `feeds` coefficients only make sense when the parent is a
dedicated metered split point (i.e. a real meter measuring the exact flow
being divided). That is why V1/V2 feed from M11 (not M7) and V3/V4 feed
from M12 (not M8). Putting coefficients on a trunk meter's residual
silently hides the trunk's own consumption and any uninstrumented children.

M10 is a shared leaf meter physically serving B10 and B11 with no known split;
the 0.5/0.5 coefficients on V5/V6 are arbitrary defaults flagging an
uncalibrated attribution - B314/B315 analog.

Sample period runs for two months (2026-01-01 to 2026-03-01, exclusive end).
B1's office branch (M1, M2, M3 and their relations) came online on
2026-02-01, so it exists only in month 2. Everything else is valid for the
full period.

POOL.net = (I1 + I2 + I3) - M0 is the supplier-vs-demand reconciliation delta.
Expected ~0; non-zero means line loss, measurement drift, or an unmetered
supplier-side draw. M0.net is the site-level residual below M0 that isn't
captured by the M1/M4/M8 branches.

POOL demonstrates the aggregator pattern: multiple real meters feed a single
virtual with coefficients on edges, so POOL.value = Σ (k * net(parent)).
With all coefs = 1.0, this reduces to a pure sum (I1 + I2 + I3).

V1..V4 demonstrate the share pattern: a single real parent feeds multiple
virtuals whose coefficients sum to 1.0 (partitioning the parent's net).

Coefficients live on the `feeds` relations, not on meter nodes. Virtuals
carry no intrinsic coefficient - they're just `is_virtual_meter=True` meters.

flow(V4) hovers near flow(M9): if M9 exceeds 0.6 * M12 in a period, V4's
net goes negative — that is a calibration alert, not a model bug.
Coefficient estimation is an antipattern we expect to retire as real
sub-metering is installed.

Timeseries refs:
- I1, I2, I3 each have two refs: external hourly automated (preferred, from the
  supplier EMS) + external monthly manual (the billed number, human-entered
  from the monthly invoice). Manual readings are Avläsning-style.
- M0 has two refs: internal hourly automated (preferred, our panel) + external
  monthly manual (supplier's billed total for the whole site).
- M1..M5, M7..M12 each have one internal hourly automated ref.
- M6's field device was replaced on 2026-02-10, so its sensor carries three
  refs: M6:h.A (device A, valid to the swap), M6:h.B (device B, valid from
  the swap), and M6:h (preferred, derived, aggregation=stitch_counters over
  the two devices, spanning the full period).
- POOL and V* virtuals carry no ref - they derive from their parents.

Zones:
- Multi-meter buildings (B1, B2) split into production + office.
- Single-meter, virtual-only, and virtual-with-submeter buildings
  (B3, B4, B5, B7, B8, B9) are warehouse.
"""

from __future__ import annotations

from datetime import date

from ontology import (
    Building,
    Campus,
    Database,
    Dataset,
    Device,
    MediaType,
    Meter,
    MeterMeasures,
    MeterRelation,
    Sensor,
    TimeseriesRef,
    Zone,
)

CAMPUS_ID = "ABBEY"

# Sample data period covers two months.
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 3, 1)  # exclusive
# B1 office came online on the first day of the second month.
B1_OFFICE_ONLINE = date(2026, 2, 1)
# M6's original device was retired and replaced mid-February.
M6_DEVICE_SWAP = date(2026, 2, 10)


SUMMARY = (
    "Synthetic 11-building electrical site exercising the ontology's "
    "topology and telemetry primitives."
)

# (label, why) - features the test site exercises. Rendered as a list in
# the Streamlit "About this test site" expander; sourced once here so
# the viz copy and the build code never drift apart.
FEATURES: list[tuple[str, str]] = [
    (
        "Aggregator (POOL ← I1+I2+I3)",
        "Multiple supplier intakes feed a single virtual; lets us "
        "reconcile supplier-side total vs. internal intake.",
    ),
    (
        "Hierarchical sub-metering (M0 → M4 → M5 → M6/M7)",
        "Serial wiring chain; upstream meters accumulate everything downstream.",
    ),
    (
        "Share-split at dedicated sub-panels (M11 → V1/V2 at 0.7/0.3; "
        "M12 → V3/V4 at 0.4/0.6)",
        "Coefficients live on dedicated instrumented split points, "
        "not on trunk remainders — M11 under M7, M12 under M8. Each "
        "set of outgoing shares partitions the sub-panel's flow to "
        "the unmetered downstream buildings.",
    ),
    (
        "Virtual with real submeter (V4 → M9)",
        "Partial real metering coexists with estimates; coefficients "
        "can be non-matching, surfacing calibration drift.",
    ),
    (
        "Shared leaf, arbitrary split (M10 → V5/V6 at 0.5/0.5)",
        "Physical meter serving multiple buildings with no known "
        "attribution; flagged as antipattern to retire as real "
        "sub-metering is installed.",
    ),
    (
        "Onboarding mid-period (M1/M2/M3 from 2026-02-01)",
        "Meters come online during the reporting window; validity "
        "respected in propagation and viz.",
    ),
    (
        "Device replacement (M6 swap on 2026-02-10)",
        "Two device-scoped measured refs (M6:h.A, M6:h.B) under the same "
        "sensor + a derived canonical ref (M6:h) that stitches them "
        "counter-style across the full period.",
    ),
    (
        "Independent per-meter measurement noise (~0.5%)",
        "Parent ≠ exact sum of children; the reconciliation delta is a "
        "real signal, not a bookkeeping tautology.",
    ),
    (
        "Seasonal supplier drift (~2%, higher in winter)",
        "I1+I2+I3 vs. M0 drifts more in early January and tails to near "
        "zero by end of February, matching a plausible heating-season "
        "line-loss pattern.",
    ),
    (
        "Communication outage (M5, 8 hours on 2026-01-13)",
        "Physical consumption continues but M5's readings have a gap; "
        "upstream M4/M0 still reflect M5's draw.",
    ),
    (
        "Backdated Avläsning correction (M0:m January)",
        "Manual reading entered 2026-02-05 was re-entered on 2026-03-15 "
        "after the operator found a misread digit; both rows are kept, "
        "distinguished by recorded_at.",
    ),
    (
        "Dual data sources (internal hourly counter + external monthly delta)",
        "Same physical meter, two recordings; needed to reconcile billed vs. measured.",
    ),
    (
        "Counter vs. delta reading types",
        "Cumulative meter index vs. per-period consumption; different "
        "upstream systems produce different shapes.",
    ),
    (
        "Zoning (production / office / warehouse)",
        "Buildings further partitioned for stakeholder reporting.",
    ),
    (
        "Seasonal synthesis (daily + weekly + monthly + noise)",
        "Synthetic data has realistic patterns so viz and seasonal analysis can be exercised.",
    ),
    (
        "Supplier reconciliation drift (~0.1%)",
        "I1+I2+I3 ≠ M0 by design; demonstrates the line-loss / measurement-drift signal.",
    ),
]

TOPOLOGY_CAPTION = (
    "Boxes are real meters, dashed ellipses are virtuals (modelled, no "
    "physical device). Solid edges are `hasSubMeter` (serial sub-metering); "
    "dashed yellow edges are `feeds` with a coefficient (aggregation when "
    "weights are 1.0, share-split when they sum to 1.0). Buildings are "
    "clustered with zone sub-clusters where present."
)

READINGS_CAPTION = (
    "Counters (hourly internal) are drawn as cumulative kWh lines — toggle "
    "to *hourly rate* for the per-step difference. Monthly manual "
    "Avläsning-style readings appear below as bars. Periods where a "
    "selected meter is outside its validity window are shaded grey "
    "(e.g. M1/M2/M3 before 2026-02-01). The synthesized profile combines "
    "weekday business-hour bumps, weekday/weekend ratio, a slow heating "
    "decay across the two months, and gaussian noise."
)


def build() -> Dataset:
    campuses = [Campus(campus_id=CAMPUS_ID, name="Abbey Road")]

    building_ids = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11]
    buildings = [
        Building(building_id=f"B{i}", name=f"Building {i}", campus_id=CAMPUS_ID)
        for i in building_ids
    ]

    zones = [
        Zone(zone_id="B1.production", name="Production", building_id="B1", zone_type="production"),
        Zone(zone_id="B1.office", name="Office", building_id="B1", zone_type="office"),
        Zone(zone_id="B2.production", name="Production", building_id="B2", zone_type="production"),
        Zone(zone_id="B2.office", name="Office", building_id="B2", zone_type="office"),
        Zone(zone_id="B3.warehouse", name="Warehouse", building_id="B3", zone_type="warehouse"),
        Zone(zone_id="B4.warehouse", name="Warehouse", building_id="B4", zone_type="warehouse"),
        Zone(zone_id="B5.warehouse", name="Warehouse", building_id="B5", zone_type="warehouse"),
        Zone(zone_id="B7.warehouse", name="Warehouse", building_id="B7", zone_type="warehouse"),
        Zone(zone_id="B8.warehouse", name="Warehouse", building_id="B8", zone_type="warehouse"),
        Zone(zone_id="B9.warehouse", name="Warehouse", building_id="B9", zone_type="warehouse"),
        Zone(zone_id="B10.warehouse", name="Warehouse", building_id="B10", zone_type="warehouse"),
        Zone(zone_id="B11.warehouse", name="Warehouse", building_id="B11", zone_type="warehouse"),
    ]

    meters = [
        # Three physical intakes mix at a station into POOL (virtual aggregator).
        Meter(meter_id="I1", name="Intake A", building_id=None, media_type_id="EL"),
        Meter(meter_id="I2", name="Intake B", building_id=None, media_type_id="EL"),
        Meter(meter_id="I3", name="Intake C", building_id=None, media_type_id="EL"),
        Meter(
            meter_id="POOL",
            name="Mixed supply",
            building_id=None,
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        # Our real intake, just after the mixing station.
        Meter(meter_id="M0", name="Site intake", building_id=None, media_type_id="EL"),
        # Real downstream meters.
        Meter(
            meter_id="M1",
            name="Office",
            building_id="B1",
            media_type_id="EL",
            valid_from=B1_OFFICE_ONLINE,
        ),
        Meter(
            meter_id="M2",
            name="Office sub a",
            building_id="B1",
            media_type_id="EL",
            valid_from=B1_OFFICE_ONLINE,
        ),
        Meter(
            meter_id="M3",
            name="Office sub b",
            building_id="B1",
            media_type_id="EL",
            valid_from=B1_OFFICE_ONLINE,
        ),
        Meter(meter_id="M4", name="Prod trunk", building_id="B1", media_type_id="EL"),
        Meter(meter_id="M5", name="Prod leaf", building_id="B1", media_type_id="EL"),
        Meter(meter_id="M6", name="Office", building_id="B2", media_type_id="EL"),
        Meter(meter_id="M7", name="Prod trunk", building_id="B2", media_type_id="EL"),
        # M11 is the instrumented split point that partitions flow to
        # B3 and B4 via V1/V2 (0.7/0.3). Sits under M7.
        Meter(
            meter_id="M11",
            name="Prod sub-panel (B3/B4 split)",
            building_id="B2",
            media_type_id="EL",
        ),
        Meter(meter_id="M8", name="Warehouse", building_id="B5", media_type_id="EL"),
        # M12 is the instrumented split point that partitions flow to
        # B7 and B8 (and everything hanging off V4→M9) via V3/V4
        # (0.4/0.6). Sits under M8.
        Meter(
            meter_id="M12",
            name="Warehouse sub-panel (B7/B8 split)",
            building_id="B5",
            media_type_id="EL",
        ),
        Meter(meter_id="M9", name="Warehouse", building_id="B9", media_type_id="EL"),
        # Shared leaf: no building, splits to B10 + B11 at arbitrary 0.5/0.5.
        Meter(meter_id="M10", name="Shared leaf", building_id=None, media_type_id="EL"),
        # Virtuals for unmetered buildings.
        Meter(
            meter_id="V1",
            name="Virtual",
            building_id="B3",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        Meter(
            meter_id="V2",
            name="Virtual",
            building_id="B4",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        Meter(
            meter_id="V3",
            name="Virtual",
            building_id="B7",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        Meter(
            meter_id="V4",
            name="Virtual",
            building_id="B8",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        Meter(
            meter_id="V5",
            name="Virtual",
            building_id="B10",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
        Meter(
            meter_id="V6",
            name="Virtual",
            building_id="B11",
            media_type_id="EL",
            is_virtual_meter=True,
        ),
    ]

    relations = [
        # Aggregator: three intakes feed POOL with weight 1.0 each -> POOL = I1+I2+I3.
        MeterRelation(
            parent_meter_id="I1", child_meter_id="POOL", relation_type="feeds", flow_coefficient=1.0
        ),
        MeterRelation(
            parent_meter_id="I2", child_meter_id="POOL", relation_type="feeds", flow_coefficient=1.0
        ),
        MeterRelation(
            parent_meter_id="I3", child_meter_id="POOL", relation_type="feeds", flow_coefficient=1.0
        ),
        # POOL has our real intake meter as a sub-meter. POOL.net = supplier - M0.
        MeterRelation(parent_meter_id="POOL", child_meter_id="M0", relation_type="hasSubMeter"),
        # M0 distributes to the real submeters at the top of each group.
        # M0→M1 only valid from the month B1 office came online.
        MeterRelation(
            parent_meter_id="M0",
            child_meter_id="M1",
            relation_type="hasSubMeter",
            valid_from=B1_OFFICE_ONLINE,
        ),
        MeterRelation(parent_meter_id="M0", child_meter_id="M4", relation_type="hasSubMeter"),
        MeterRelation(parent_meter_id="M0", child_meter_id="M8", relation_type="hasSubMeter"),
        # B1 internal topology (office came online in month 2).
        MeterRelation(
            parent_meter_id="M1",
            child_meter_id="M2",
            relation_type="hasSubMeter",
            valid_from=B1_OFFICE_ONLINE,
        ),
        MeterRelation(
            parent_meter_id="M1",
            child_meter_id="M3",
            relation_type="hasSubMeter",
            valid_from=B1_OFFICE_ONLINE,
        ),
        MeterRelation(parent_meter_id="M4", child_meter_id="M5", relation_type="hasSubMeter"),
        # M5 crosses into B2.
        MeterRelation(parent_meter_id="M5", child_meter_id="M6", relation_type="hasSubMeter"),
        MeterRelation(parent_meter_id="M5", child_meter_id="M7", relation_type="hasSubMeter"),
        # M11 sits under M7 and is the dedicated metered split point
        # for the B3/B4 allocation. Coefficients live here, not on M7.
        MeterRelation(parent_meter_id="M7", child_meter_id="M11", relation_type="hasSubMeter"),
        MeterRelation(
            parent_meter_id="M11", child_meter_id="V1", relation_type="feeds", flow_coefficient=0.7
        ),
        MeterRelation(
            parent_meter_id="M11", child_meter_id="V2", relation_type="feeds", flow_coefficient=0.3
        ),
        # M12 sits under M8 and is the dedicated metered split point
        # for the B7/B8 allocation. Coefficients live here, not on M8.
        MeterRelation(parent_meter_id="M8", child_meter_id="M12", relation_type="hasSubMeter"),
        MeterRelation(
            parent_meter_id="M12", child_meter_id="V3", relation_type="feeds", flow_coefficient=0.4
        ),
        MeterRelation(
            parent_meter_id="M12", child_meter_id="V4", relation_type="feeds", flow_coefficient=0.6
        ),
        # V4 has a real submeter M9 - non-matching coefficient pattern.
        MeterRelation(parent_meter_id="V4", child_meter_id="M9", relation_type="hasSubMeter"),
        # M9 has a shared leaf M10 downstream; M10 splits to B10+B11 arbitrarily.
        MeterRelation(parent_meter_id="M9", child_meter_id="M10", relation_type="hasSubMeter"),
        MeterRelation(
            parent_meter_id="M10", child_meter_id="V5", relation_type="feeds", flow_coefficient=0.5
        ),
        MeterRelation(
            parent_meter_id="M10", child_meter_id="V6", relation_type="feeds", flow_coefficient=0.5
        ),
    ]

    # `brick:meters` - what each meter measures. Campus-level meters
    # (intakes, site intake, shared leaf) measure the campus; meters
    # inside a single-zone or zone-less building measure the building;
    # meters with a specific zone measure that zone.
    meter_measures = [
        # Supplier-side intakes and site intake → campus.
        MeterMeasures(meter_id="I1", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="I2", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="I3", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="M0", target_kind="campus", target_id=CAMPUS_ID),
        # Shared leaf M10 splits to two buildings - no single target, so
        # we record it as measuring at the campus level too (physically
        # upstream of the unmetered split).
        MeterMeasures(meter_id="M10", target_kind="campus", target_id=CAMPUS_ID),
        # Zoned B1/B2 meters measure their zone.
        MeterMeasures(meter_id="M1", target_kind="zone", target_id="B1.office"),
        MeterMeasures(meter_id="M2", target_kind="zone", target_id="B1.office"),
        MeterMeasures(meter_id="M3", target_kind="zone", target_id="B1.office"),
        MeterMeasures(meter_id="M4", target_kind="zone", target_id="B1.production"),
        MeterMeasures(meter_id="M5", target_kind="zone", target_id="B1.production"),
        MeterMeasures(meter_id="M6", target_kind="zone", target_id="B2.office"),
        MeterMeasures(meter_id="M7", target_kind="zone", target_id="B2.production"),
        MeterMeasures(meter_id="M11", target_kind="zone", target_id="B2.production"),
        # Virtuals and warehouse meters measure their building's sole zone.
        MeterMeasures(meter_id="V1", target_kind="zone", target_id="B3.warehouse"),
        MeterMeasures(meter_id="V2", target_kind="zone", target_id="B4.warehouse"),
        MeterMeasures(meter_id="M8", target_kind="zone", target_id="B5.warehouse"),
        MeterMeasures(meter_id="M12", target_kind="zone", target_id="B5.warehouse"),
        MeterMeasures(meter_id="V3", target_kind="zone", target_id="B7.warehouse"),
        MeterMeasures(meter_id="V4", target_kind="zone", target_id="B8.warehouse"),
        MeterMeasures(meter_id="M9", target_kind="zone", target_id="B9.warehouse"),
        MeterMeasures(meter_id="V5", target_kind="zone", target_id="B10.warehouse"),
        MeterMeasures(meter_id="V6", target_kind="zone", target_id="B11.warehouse"),
    ]

    media_types = [
        MediaType(
            media_type_id="EL",
            name="Electrical",
            description="Electrical energy (kWh / MWh).",
            brick_meter_class="Electrical_Meter",
            # Electricity has no Brick substance.
            brick_substance=None,
        ),
    ]

    databases = [
        Database(database_id="PME_SQL", name="Internal PME", kind="internal"),
        Database(database_id="supplier_ems", name="Supplier EMS", kind="external"),
        Database(database_id="avlasning", name="Avläsning sheet", kind="external"),
    ]

    # Stub device rows for the two physical devices referenced by M6's
    # replacement pattern. Serial / manufacturer are unknown at v1 and
    # populated later when the hardware inventory lands (§7.4 + §10).
    # Other timeseries refs in Abbey Road do not set device_id, so no
    # further stubs are required to keep referential integrity green.
    devices = [
        Device(device_id="M6-DEV-A"),
        Device(device_id="M6-DEV-B"),
    ]

    # One Energy_Sensor per metered meter. Virtuals (POOL, V*) carry no
    # sensor - they're model-level, not physical measurement points.
    metered_ids = [
        "I1",
        "I2",
        "I3",
        "M0",
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "M6",
        "M7",
        "M8",
        "M9",
        "M10",
        "M11",
        "M12",
    ]
    sensors = [
        Sensor(
            sensor_id=f"{mid}.energy",
            meter_id=mid,
            point_type="Energy_Sensor",
            # QUDT identifier fragment for kWh.
            unit="KiloW-HR",
        )
        for mid in metered_ids
    ]

    # I1/I2/I3 get hourly (supplier EMS) + monthly manual (invoice).
    # M0 gets hourly (internal PME panel) + monthly manual (bill).
    # M1..M10 each have one internal hourly ref - except M6, whose field
    # device was replaced mid-February so it has three refs: two
    # device-scoped measured refs (old + new) and a derived canonical
    # ref that spans the full period via rolling_sum.
    external_intakes = ["I1", "I2", "I3"]
    internal_downstream = [
        "M1", "M2", "M3", "M4", "M5", "M7", "M8", "M9", "M10", "M11", "M12",
    ]
    # Synthetic PME external ids for downstream meters. M0 uses the
    # proposal's example id to keep the mapping recognizable.
    pme_external = {
        "M0": "631:129",
        "M1": "631:200",
        "M2": "631:201",
        "M3": "631:202",
        "M4": "631:210",
        "M5": "631:211",
        "M7": "631:220",
        "M8": "631:230",
        "M9": "631:231",
        "M10": "631:232",
        "M11": "631:240",
        "M12": "631:250",
        "M6-DEV-A": "631:215",
        "M6-DEV-B": "631:216",
    }

    timeseries_refs = (
        [
            TimeseriesRef(
                timeseries_id=f"{mid}:h",
                sensor_id=f"{mid}.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=True,
                database_id="supplier_ems",
                path="ems.hourly_counters",
                external_id=mid,
            )
            for mid in external_intakes
        ]
        + [
            TimeseriesRef(
                timeseries_id=f"{mid}:m",
                sensor_id=f"{mid}.energy",
                aggregate="monthly",
                reading_type="delta",
                kind="raw",
                preferred=False,
                database_id="avlasning",
                path="readings.monthly",
                external_id=mid,
            )
            for mid in external_intakes
        ]
        + [
            TimeseriesRef(
                timeseries_id="M0:h",
                sensor_id="M0.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=True,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M0"],
            ),
            TimeseriesRef(
                timeseries_id="M0:m",
                sensor_id="M0.energy",
                aggregate="monthly",
                reading_type="delta",
                kind="raw",
                preferred=False,
                database_id="avlasning",
                path="readings.monthly",
                external_id="M0",
            ),
        ]
        + [
            TimeseriesRef(
                timeseries_id=f"{mid}:h",
                sensor_id=f"{mid}.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=True,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external[mid],
            )
            for mid in internal_downstream
        ]
        # M6 replacement: two device-scoped measured refs (non-preferred)
        # + one derived canonical ref that spans the full period.
        + [
            TimeseriesRef(
                timeseries_id="M6:h.A",
                sensor_id="M6.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M6-DEV-A"],
                device_id="M6-DEV-A",
                valid_from=PERIOD_START,
                valid_to=M6_DEVICE_SWAP,
            ),
            TimeseriesRef(
                timeseries_id="M6:h.B",
                sensor_id="M6.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M6-DEV-B"],
                device_id="M6-DEV-B",
                valid_from=M6_DEVICE_SWAP,
                valid_to=PERIOD_END,
            ),
            # Derived canonical: no addressing triple, no device. The DW
            # materializes it from the sources on demand.
            TimeseriesRef(
                timeseries_id="M6:h",
                sensor_id="M6.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=True,
                sources=["M6:h.A", "M6:h.B"],
                aggregation="rolling_sum",
            ),
        ]
    )

    return Dataset(
        campuses=campuses,
        buildings=buildings,
        zones=zones,
        media_types=media_types,
        meters=meters,
        relations=relations,
        meter_measures=meter_measures,
        databases=databases,
        devices=devices,
        sensors=sensors,
        timeseries_refs=timeseries_refs,
    )
