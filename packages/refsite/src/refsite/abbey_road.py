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
# M14 multi-event meter: counter glitch in January, then offline in February.
M14_GLITCH_START = date(2026, 1, 20)
M14_GLITCH_END = date(2026, 1, 22)
M14_OFFLINE = date(2026, 2, 15)
# M16 frozen counter: stops incrementing late February.
M16_FREEZE_START = date(2026, 2, 20)
# M17 BMS register corruption: mid-span window where the raw source
# randomly alternates between the real counter register, a low-value
# artifact register, and a stuck-high register. Inside the window we
# also create a sub-gap (Jan 27–30) where every hourly sample is an
# artifact, so the `bracket` ref's in-band output has a real gap that
# an `interpolate` patch needs to bridge.
M17_CORRUPTION_START = date(2026, 1, 20)
M17_CORRUPTION_END = date(2026, 2, 15)   # exclusive; first clean day after
M17_SUBGAP_START = date(2026, 1, 27)
M17_SUBGAP_END = date(2026, 1, 30)       # exclusive
M17_HIGH_STUCK_VALUE = 805175.296
M17_LOW_ARTIFACT_VALUE = 0.2
# F1/F2 direction flip: physical re-wiring on 2026-02-01.
# Before this date F2 is a sub-meter of F1 (F1 reads F1_own + F2_own);
# after it the wiring is reversed and F1 becomes a sub-meter of F2.
# Exists to exercise temporal `meter_relations` validity in the calc.
FLIP_DATE = date(2026, 2, 1)


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
    (
        "Outage + children-sum patch (M14 offline → M15 patch)",
        "Meter goes offline mid-period; derived patch ref reconstructs "
        "counter from children's readings via sum aggregation.",
    ),
    (
        "Multi-event meter (M14: glitch Jan 20 + offline Feb 15)",
        "One meter with both a counter glitch and a later permanent "
        "offline. Three segments (A, B, patch) stitched via rolling_sum.",
    ),
    (
        "Glitch exclusion (M14, 2-day counter drop Jan 20–22)",
        "Raw counter drops and reverts; validity split excludes the "
        "bad days so consumption has no spike.",
    ),
    (
        "Frozen counter (M16, delta=0 after Feb 20)",
        "Counter stops incrementing but device keeps reporting the same "
        "value. Upstream M13 still reflects the true flow.",
    ),
    (
        "Parallel intakes (R1, R2 — independent roots)",
        "Two campus-level root meters with no parent-child relationship; "
        "demonstrates sibling intakes like B600N/B600S.",
    ),
    (
        "Conservation violation (M14 exceeds M13 allocation)",
        "Child meter with undocumented extra feed; recorded consumption "
        "exceeds topology-allocated share. Annotated as unknown.",
    ),
    (
        "Annotations (outage, swap, data_quality, patch, calibration, unknown)",
        "Reference annotations covering every category, attached to "
        "meters and timeseries refs.",
    ),
    (
        "Topology direction flip (F1↔F2 on 2026-02-01)",
        "Two meters whose parent/child relation reverses mid-period — "
        "mirrors the GTN B614/B642 ÅNGA case. Exercises temporal "
        "`meter_relations.valid_from/valid_to` in the calc layer.",
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

    building_ids = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14]
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
        Zone(zone_id="B12.warehouse", name="Warehouse", building_id="B12", zone_type="warehouse"),
        Zone(zone_id="B13.office", name="Office", building_id="B13", zone_type="office"),
        Zone(zone_id="B14.warehouse", name="Warehouse", building_id="B14", zone_type="warehouse"),
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
        # New pattern meters: outage+patch, glitch, frozen, parallel.
        Meter(meter_id="M13", name="Factory", building_id="B12", media_type_id="EL"),
        Meter(meter_id="M14", name="Multi-event sub", building_id="B12", media_type_id="EL"),
        Meter(meter_id="M15", name="Office sub", building_id="B13", media_type_id="EL"),
        Meter(meter_id="M16", name="Frozen counter", building_id="B14", media_type_id="EL"),
        Meter(meter_id="R1", name="Parallel root A", building_id=None, media_type_id="EL"),
        Meter(meter_id="R2", name="Parallel root B", building_id=None, media_type_id="EL"),
        # F1/F2 direction flip: parent/child reverses on FLIP_DATE.
        Meter(meter_id="F1", name="Flip meter A", building_id=None, media_type_id="EL"),
        Meter(meter_id="F2", name="Flip meter B", building_id=None, media_type_id="EL"),
        # M17 stands in for the B217 steam-meter pattern: a single
        # campus-level counter whose upstream source is corrupted inside
        # a known window by a multi-register BMS misconfig. Raw samples
        # alternate between the real register, a near-zero artifact, and
        # a stuck-high register. Kept campus-level so it stays isolated
        # from the other topology invariants.
        Meter(meter_id="M17", name="BMS corruption", building_id=None, media_type_id="EL"),
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
        # M13 branch under M0: outage+patch, multi-event, frozen counter.
        MeterRelation(parent_meter_id="M0", child_meter_id="M13", relation_type="hasSubMeter"),
        MeterRelation(parent_meter_id="M13", child_meter_id="M14", relation_type="hasSubMeter"),
        MeterRelation(parent_meter_id="M14", child_meter_id="M15", relation_type="hasSubMeter"),
        MeterRelation(parent_meter_id="M13", child_meter_id="M16", relation_type="hasSubMeter"),
        # Direction flip: F1 is the parent until FLIP_DATE, F2 after.
        # A correct calc requires BOTH edges to be filtered by the event
        # date; otherwise each sub_total pair cancels the other's flow
        # and one meter's net goes wildly negative in each half.
        MeterRelation(
            parent_meter_id="F1",
            child_meter_id="F2",
            relation_type="hasSubMeter",
            valid_to=FLIP_DATE,
        ),
        MeterRelation(
            parent_meter_id="F2",
            child_meter_id="F1",
            relation_type="hasSubMeter",
            valid_from=FLIP_DATE,
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
        MeterMeasures(meter_id="M13", target_kind="zone", target_id="B12.warehouse"),
        MeterMeasures(meter_id="M14", target_kind="zone", target_id="B12.warehouse"),
        MeterMeasures(meter_id="M15", target_kind="zone", target_id="B13.office"),
        MeterMeasures(meter_id="M16", target_kind="zone", target_id="B14.warehouse"),
        MeterMeasures(meter_id="R1", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="R2", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="F1", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="F2", target_kind="campus", target_id=CAMPUS_ID),
        MeterMeasures(meter_id="M17", target_kind="campus", target_id=CAMPUS_ID),
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
        "M13",
        "M14",
        "M15",
        "M16",
        "R1",
        "R2",
        "F1",
        "F2",
        "M17",
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
        "M13", "M15", "M16", "R1", "R2", "F1", "F2",
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
        "M13": "631:260",
        "M14": "631:261",
        "M15": "631:262",
        "M16": "631:263",
        "R1": "631:300",
        "R2": "631:301",
        "F1": "631:310",
        "F2": "631:311",
        "M17": "631:270",
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
        # M14 multi-event: glitch (A→B) + offline (B→patch).
        + [
            TimeseriesRef(
                timeseries_id="M14:h.A",
                sensor_id="M14.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M14"],
                valid_from=PERIOD_START,
                valid_to=M14_GLITCH_START,
            ),
            TimeseriesRef(
                timeseries_id="M14:h.B",
                sensor_id="M14.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M14"],
                valid_from=M14_GLITCH_END,
                valid_to=M14_OFFLINE,
            ),
            TimeseriesRef(
                timeseries_id="M14:h.patch",
                sensor_id="M14.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=False,
                sources=["M15:h"],
                aggregation="sum",
                valid_from=M14_OFFLINE,
            ),
            TimeseriesRef(
                timeseries_id="M14:h",
                sensor_id="M14.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=True,
                sources=["M14:h.A", "M14:h.B", "M14:h.patch"],
                aggregation="rolling_sum",
            ),
        ]
        # M17 register-corruption pattern. The raw ref carries the
        # corrupted samples as they arrive from upstream. Two derived
        # refs clean them up, and the canonical M17:h stitches the
        # clean counter for the full period — which is what the app
        # and downstream analytics should consume by default.
        #   - M17:h.raw (raw, non-preferred): full-period counter whose
        #     values inside [CORRUPTION_START, CORRUPTION_END) alternate
        #     between the real counter, a low artifact, and a stuck-high
        #     register. Preserved as-is for audit and diagnostics.
        #   - M17:h.clip (bracket): keeps only in-band samples of
        #     M17:h.raw within the corruption window. Parameter-free.
        #   - M17:h.patch (interpolate): linear counter fill across the
        #     sub-gap where every raw sample is out-of-band, so clip
        #     leaves a real gap that interpolate has to bridge.
        #   - M17:h (derived, preferred): rolling_sum over the segments
        #     above, giving the canonical clean counter the UI defaults to.
        + [
            TimeseriesRef(
                timeseries_id="M17:h.raw",
                sensor_id="M17.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="raw",
                preferred=False,
                database_id="PME_SQL",
                path="ingest.hourly",
                external_id=pme_external["M17"],
            ),
            TimeseriesRef(
                timeseries_id="M17:h.clip",
                sensor_id="M17.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=False,
                sources=["M17:h.raw"],
                aggregation="bracket",
                valid_from=M17_CORRUPTION_START,
                valid_to=M17_CORRUPTION_END,
            ),
            TimeseriesRef(
                timeseries_id="M17:h.patch",
                sensor_id="M17.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=False,
                sources=["M17:h.clip"],
                aggregation="interpolate",
                valid_from=M17_SUBGAP_START,
                valid_to=M17_SUBGAP_END,
            ),
            TimeseriesRef(
                timeseries_id="M17:h",
                sensor_id="M17.energy",
                aggregate="hourly",
                reading_type="counter",
                kind="derived",
                preferred=True,
                sources=["M17:h.raw", "M17:h.clip", "M17:h.patch"],
                aggregation="rolling_sum",
            ),
        ]
    )

    annotations = [
        Annotation(
            annotation_id="ann-m6-swap",
            target_kind="meter",
            target_id="M6",
            category="swap",
            valid_from=M6_DEVICE_SWAP,
            valid_to=M6_DEVICE_SWAP,
            description="Device A replaced by device B.",
            related_refs=["M6:h.A", "M6:h.B", "M6:h"],
        ),
        Annotation(
            annotation_id="ann-m5-outage",
            target_kind="meter",
            target_id="M5",
            category="outage",
            valid_from=date(2026, 1, 13),
            valid_to=date(2026, 1, 14),
            description="8-hour communication gap; physical consumption continues.",
        ),
        Annotation(
            annotation_id="ann-m14-glitch",
            target_kind="meter",
            target_id="M14",
            category="data_quality",
            valid_from=M14_GLITCH_START,
            valid_to=M14_GLITCH_END,
            description="Counter drop and revert; 2-day window excluded from raw segments.",
            related_refs=["M14:h.A", "M14:h.B"],
        ),
        Annotation(
            annotation_id="ann-m14-outage",
            target_kind="meter",
            target_id="M14",
            category="outage",
            valid_from=M14_OFFLINE,
            description="Permanent offline; patched from child M15.",
            related_refs=["M14:h.patch"],
        ),
        Annotation(
            annotation_id="ann-m14-patch",
            target_kind="timeseries",
            target_id="M14:h.patch",
            category="patch",
            valid_from=M14_OFFLINE,
            description="Children-sum patch for M14 from M15.",
            related_refs=["M15:h"],
        ),
        Annotation(
            annotation_id="ann-m14-conservation",
            target_kind="meter",
            target_id="M14",
            category="unknown",
            description="M14 recorded consumption exceeds M13 allocation; undocumented extra feed suspected.",
        ),
        Annotation(
            annotation_id="ann-m16-freeze",
            target_kind="meter",
            target_id="M16",
            category="data_quality",
            valid_from=M16_FREEZE_START,
            description="Counter frozen (delta=0); device reports same value.",
        ),
        Annotation(
            annotation_id="ann-v4-calibration",
            target_kind="meter",
            target_id="V4",
            category="calibration",
            description="V4.net occasionally negative when M9 exceeds 0.6×M12; coefficient may need recalibration.",
        ),
        Annotation(
            annotation_id="ann-m17-corruption",
            target_kind="meter",
            target_id="M17",
            category="data_quality",
            valid_from=M17_CORRUPTION_START,
            valid_to=M17_CORRUPTION_END,
            description=(
                "BMS multi-register misconfig: raw samples alternate between the "
                "real counter, a near-zero artifact, and a stuck-high register."
            ),
            related_refs=["M17:h.raw", "M17:h.clip", "M17:h.patch"],
        ),
        Annotation(
            annotation_id="ann-m17-clip",
            target_kind="timeseries",
            target_id="M17:h.clip",
            category="patch",
            valid_from=M17_CORRUPTION_START,
            valid_to=M17_CORRUPTION_END,
            description=(
                "Value-range clip (bracket): keep M17:h.raw samples whose value lies "
                "between the clean endpoint values at the corruption-window "
                "boundaries; drop the rest."
            ),
            related_refs=["M17:h.raw"],
        ),
        Annotation(
            annotation_id="ann-m17-patch",
            target_kind="timeseries",
            target_id="M17:h.patch",
            category="patch",
            valid_from=M17_SUBGAP_START,
            valid_to=M17_SUBGAP_END,
            description=(
                "Linear counter interpolation across the sub-gap where every raw "
                "sample is out-of-band; endpoints read from M17:h.clip at the "
                "ref's validity boundaries."
            ),
            related_refs=["M17:h.clip"],
        ),
    ]

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
        annotations=annotations,
    )
