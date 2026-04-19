from collections import defaultdict
from datetime import date, datetime
from itertools import pairwise

from refsite import abbey_road
from refsite.readings import generate_readings


def test_abbey_road_builds() -> None:
    """End-to-end build of the reference site emits a coherent meter graph."""
    ds = abbey_road.build()
    assert len(ds.campuses) == 1
    assert len(ds.buildings) == 13
    assert {m.meter_id for m in ds.meters} >= {
        "I1",
        "I2",
        "I3",
        "POOL",
        "M0",
        "M1",
        "M9",
        "M10",
        "V1",
        "V4",
        "V5",
        "V6",
    }

    # Relations reference meters that exist.
    ids = {m.meter_id for m in ds.meters}
    for r in ds.relations:
        assert r.parent_meter_id in ids
        assert r.child_meter_id in ids

    # Every `feeds` relation carries a flow_coefficient; `hasSubMeter` never does.
    for r in ds.relations:
        if r.relation_type == "feeds":
            assert r.flow_coefficient is not None, (
                f"feeds edge {r} missing flow_coefficient"
            )
        else:
            assert r.flow_coefficient is None

    # Share invariant: outgoing flow_coefficients from each real parent sum to 1.0.
    virt_ids = {m.meter_id for m in ds.meters if m.is_virtual_meter}
    outgoing: dict[str, float] = defaultdict(float)
    for r in ds.relations:
        # Skip edges that FEED a virtual that is itself an aggregator (multi-parent).
        # Here we check share semantics per parent.
        if r.relation_type == "feeds" and r.child_meter_id in virt_ids:
            assert r.flow_coefficient is not None
            outgoing[r.parent_meter_id] += r.flow_coefficient
    # M11 (under M7) and M12 (under M8) are the dedicated metered split
    # points; M10 is the shared leaf. Their outgoing feeds to virtuals
    # must partition their flow exactly (coefs sum to 1.0). POOL's
    # parents sum to N (weights, not shares), so we only assert the
    # share case for dedicated split parents.
    for parent in ("M11", "M12", "M10"):
        assert abs(outgoing[parent] - 1.0) < 1e-9, f"{parent} outgoing feeds = {outgoing[parent]}"


def test_pool_is_aggregator() -> None:
    """POOL has three incoming feeds edges with weight 1.0 each."""
    ds = abbey_road.build()
    incoming = [r for r in ds.relations if r.child_meter_id == "POOL"]
    assert len(incoming) == 3
    assert {r.parent_meter_id for r in incoming} == {"I1", "I2", "I3"}
    assert all(r.relation_type == "feeds" for r in incoming)
    assert all(r.flow_coefficient == 1.0 for r in incoming)


def test_pool_reconciles_to_m0() -> None:
    """POOL's only hasSubMeter child is our real intake M0."""
    ds = abbey_road.build()
    subs = [
        r for r in ds.relations if r.parent_meter_id == "POOL" and r.relation_type == "hasSubMeter"
    ]
    assert [s.child_meter_id for s in subs] == ["M0"]
    # M0 fans out to the site branches.
    m0_children = {r.child_meter_id for r in ds.relations if r.parent_meter_id == "M0"}
    assert m0_children == {"M1", "M4", "M8", "M13"}


def test_virtual_with_real_submeter() -> None:
    """V4 has M9 as a real sub-meter — GTN Kyla B611 analog."""
    ds = abbey_road.build()
    edge = next(r for r in ds.relations if r.parent_meter_id == "V4" and r.child_meter_id == "M9")
    assert edge.relation_type == "hasSubMeter"
    assert edge.flow_coefficient is None


def test_b1_office_onboarding_validity() -> None:
    """B1 office (M1, M2, M3) comes online on 2026-02-01."""
    ds = abbey_road.build()
    onboarding = date(2026, 2, 1)
    for mid in ("M1", "M2", "M3"):
        m = next(m for m in ds.meters if m.meter_id == mid)
        assert m.valid_from == onboarding, f"{mid} expected valid_from={onboarding}"
        assert m.valid_to is None
    # Relations linking the office subtree share the same validity.
    edges = [
        ("M0", "M1"),
        ("M1", "M2"),
        ("M1", "M3"),
    ]
    for parent, child in edges:
        r = next(
            r for r in ds.relations if r.parent_meter_id == parent and r.child_meter_id == child
        )
        assert r.valid_from == onboarding, f"{parent}->{child} valid_from mismatch"
    # Meters outside the office subtree remain unbounded (valid_from is None).
    for mid in ("I1", "POOL", "M0", "M4", "M8", "M9"):
        m = next(m for m in ds.meters if m.meter_id == mid)
        assert m.valid_from is None


def test_shared_leaf_m10() -> None:
    """M10 is a shared leaf with no building, splitting 0.5/0.5 to B10/B11."""
    ds = abbey_road.build()
    m10 = next(m for m in ds.meters if m.meter_id == "M10")
    assert m10.building_id is None
    assert not m10.is_virtual_meter
    children = [r for r in ds.relations if r.parent_meter_id == "M10"]
    assert {r.child_meter_id for r in children} == {"V5", "V6"}
    assert all(r.relation_type == "feeds" and r.flow_coefficient == 0.5 for r in children)


def test_timeseries_refs() -> None:
    """Each sensor has the timeseries refs the data sources actually provide."""
    ds = abbey_road.build()
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    refs_by_meter: dict[str, list] = defaultdict(list)
    for tr in ds.timeseries_refs:
        refs_by_meter[sensor_meter[tr.sensor_id]].append(tr)

    # I1, I2, I3 each get hourly (supplier EMS) + monthly (Avläsning).
    for mid in ["I1", "I2", "I3"]:
        refs = refs_by_meter[mid]
        assert len(refs) == 2
        by_agg = {tr.aggregate: tr for tr in refs}
        assert by_agg["hourly"].kind == "raw"
        assert by_agg["hourly"].database_id == "supplier_ems"
        assert by_agg["hourly"].preferred
        assert by_agg["monthly"].kind == "raw"
        assert by_agg["monthly"].database_id == "avlasning"
        assert by_agg["monthly"].reading_type == "delta"
        assert not by_agg["monthly"].preferred

    # M0 has internal hourly + external monthly.
    m0 = refs_by_meter["M0"]
    assert len(m0) == 2
    m0_monthly = next(tr for tr in m0 if tr.aggregate == "monthly")
    assert m0_monthly.database_id == "avlasning"
    m0_hourly = next(tr for tr in m0 if tr.aggregate == "hourly")
    assert m0_hourly.external_id == "631:129"  # proposal's example id

    # Downstream real M* (except M6) each have one internal hourly ref.
    for mid in ["M1", "M5", "M9", "M10"]:
        refs = refs_by_meter[mid]
        assert len(refs) == 1, f"{mid} has {len(refs)} refs"
        assert refs[0].kind == "raw"
        assert refs[0].database_id == "PME_SQL"

    # POOL and virtuals carry no sensor / ref.
    for mid in ["POOL", "V1", "V2", "V3", "V4", "V5", "V6"]:
        assert not refs_by_meter[mid]
        assert not [s for s in ds.sensors if s.meter_id == mid]


def test_readings_respect_validity() -> None:
    """M1 starts on 2026-02-01: no January readings, exactly 28*24 in Feb."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    m1_h = [r for r in rs if r.timeseries_id == "M1:h"]
    assert len(m1_h) == 28 * 24
    assert min(r.timestamp for r in m1_h).date() == date(2026, 2, 1)
    # M0 is unbounded — should cover the full two-month period.
    m0_h = [r for r in rs if r.timeseries_id == "M0:h"]
    assert len(m0_h) == (28 + 31) * 24


def test_readings_counter_monotonic() -> None:
    """Cumulative counters never tick down."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    by_series: dict[str, list[float]] = defaultdict(list)
    for r in sorted(rs, key=lambda r: (r.timeseries_id, r.timestamp)):
        by_series[r.timeseries_id].append(r.value)
    counter_ids = {tr.timeseries_id for tr in ds.timeseries_refs if tr.reading_type == "counter"}
    for sid in counter_ids:
        vals = by_series[sid]
        diffs = [b - a for a, b in pairwise(vals)]
        assert all(d >= 0 for d in diffs), f"{sid} non-monotonic"


def test_supplier_reconciles_to_intake_within_drift() -> None:
    """I1+I2+I3 ≈ M0 over each month, within seasonal drift budget (~3%)."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    # When the same (ts_id, timestamp) has multiple rows (backdated
    # corrections), take the latest recorded_at.
    by_key: dict[tuple[str, datetime], tuple[datetime | None, float]] = {}
    for r in rs:
        if r.timeseries_id not in {"I1:m", "I2:m", "I3:m", "M0:m"}:
            continue
        key = (r.timeseries_id, r.timestamp)
        existing = by_key.get(key)
        if existing is None or (
            r.recorded_at is not None and (existing[0] is None or r.recorded_at > existing[0])
        ):
            by_key[key] = (r.recorded_at, r.value)
    monthly = {ts_id: val for (ts_id, stamp), (_rec, val) in by_key.items() if stamp.month == 1}
    supplier = monthly["I1:m"] + monthly["I2:m"] + monthly["I3:m"]
    intake = monthly["M0:m"]
    rel_diff = abs(supplier - intake) / intake
    # Seasonal drift caps at ~2% plus measurement noise; allow 3%.
    assert rel_diff < 0.03, f"reconciliation drift too large: {rel_diff:.4%}"


def test_m6_device_replacement_shape() -> None:
    """M6's sensor carries three refs: device A, device B, derived canonical."""
    ds = abbey_road.build()
    m6_refs = {tr.timeseries_id: tr for tr in ds.timeseries_refs if tr.sensor_id == "M6.energy"}
    assert set(m6_refs) == {"M6:h.A", "M6:h.B", "M6:h"}

    a = m6_refs["M6:h.A"]
    b = m6_refs["M6:h.B"]
    derived = m6_refs["M6:h"]

    # Device refs are raw; their windows are contiguous.
    assert a.kind == "raw" and a.device_id == "M6-DEV-A" and a.sources == []
    assert b.kind == "raw" and b.device_id == "M6-DEV-B" and b.sources == []
    assert a.valid_to == b.valid_from == date(2026, 2, 10)
    # Raw refs carry the addressing triple.
    assert a.database_id == "PME_SQL" and a.path == "ingest.hourly"
    assert a.external_id and b.external_id and a.external_id != b.external_id

    # Derived ref: no addressing, no device, rolling_sum over the two devices.
    assert derived.kind == "derived"
    assert derived.device_id is None
    assert derived.database_id is None
    assert derived.path is None
    assert derived.external_id is None
    assert derived.sources == ["M6:h.A", "M6:h.B"]
    assert derived.aggregation == "rolling_sum"
    # And it's the preferred ref for M6's sensor.
    assert derived.preferred
    assert not a.preferred and not b.preferred


def test_m6_stitched_matches_devices() -> None:
    """The derived series equals device A inside A's window, and reconciles
    to A_final + (B_final - offset_B) at end of period."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    by_series: dict[str, dict[date, float]] = defaultdict(dict)
    for r in rs:
        by_series[r.timeseries_id][r.timestamp] = r.value

    a = by_series["M6:h.A"]
    b = by_series["M6:h.B"]
    s = by_series["M6:h"]

    # Inside A's window, stitched equals A exactly.
    for t in a:
        assert s[t] == a[t], f"stitched diverged from A at {t}"

    # B is a fresh device, so its first reading ≈ offset + one hour of flow.
    # Reconciliation: A_final + sum(hourly flow in B's window) == stitched_final.
    # We back out offset_B from B's first reading, then verify the identity.
    from refsite.abbey_road import M6_DEVICE_SWAP

    a_final = a[max(a)]
    b_first_ts = min(b)
    s_first_b = s[b_first_ts]
    # In B's window stitched = A_final + meter_flow_so_far_in_B;
    # at first hour that's A_final + flow[swap_hour].
    flow_swap_hour = s_first_b - a_final
    b_offset = b[b_first_ts] - flow_swap_hour
    b_final = b[max(b)]
    assert abs((a_final + (b_final - b_offset)) - s[max(s)]) < 1e-6
    # Sanity: the swap is on the declared date.
    assert b_first_ts.date() == M6_DEVICE_SWAP


def test_reconciliation_is_nontrivial() -> None:
    """With independent measurement noise, I1+I2+I3 ≠ M0 exactly.

    If the supplier triplet were generated as a deterministic function
    of M0 (as in the old tautological model), the monthly reconciliation
    delta would be exactly zero. The seasonal drift + per-meter noise
    make it a non-zero signal in the 0.3-3% range.
    """
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    monthly = defaultdict(dict)
    for r in rs:
        if r.timeseries_id in {"I1:m", "I2:m", "I3:m", "M0:m"}:
            # Take the latest correction (by recorded_at, None = earliest).
            existing = monthly[r.timestamp].get(r.timeseries_id)
            if existing is None or (
                r.recorded_at is not None and (existing[0] is None or r.recorded_at > existing[0])
            ):
                monthly[r.timestamp][r.timeseries_id] = (r.recorded_at, r.value)
    for stamp, vals in monthly.items():
        supplier = vals["I1:m"][1] + vals["I2:m"][1] + vals["I3:m"][1]
        intake = vals["M0:m"][1]
        rel_diff = abs(supplier - intake) / intake
        assert rel_diff > 0.0001, (
            f"{stamp}: reconciliation is suspiciously clean ({rel_diff:.6%}) - likely a tautology"
        )


def test_m5_outage_gap() -> None:
    """M5:h has no readings during its declared 8-hour outage window."""
    from refsite.readings import M5_OUTAGE_END, M5_OUTAGE_START

    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    m5 = [r for r in rs if r.timeseries_id == "M5:h"]
    in_window = [r for r in m5 if M5_OUTAGE_START <= r.timestamp < M5_OUTAGE_END]
    assert in_window == []
    # And we should have exactly (total_hours - outage_hours) readings.
    total_hours = (date(2026, 3, 1) - date(2026, 1, 1)).days * 24
    outage_hours = int((M5_OUTAGE_END - M5_OUTAGE_START).total_seconds() // 3600)
    assert len(m5) == total_hours - outage_hours


def test_m0_backdated_correction() -> None:
    """January M0:m has two rows: an original and a correction."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    jan = datetime(2026, 1, 1)
    m0_jan = [r for r in rs if r.timeseries_id == "M0:m" and r.timestamp == jan]
    assert len(m0_jan) == 2
    recorded_ats = [r.recorded_at for r in m0_jan]
    assert all(ra is not None for ra in recorded_ats)
    assert min(recorded_ats).month == 2  # type: ignore[operator]
    assert max(recorded_ats).month == 3  # type: ignore[operator]
    # The latest recorded_at carries the higher (corrected) value.
    latest = max(m0_jan, key=lambda r: r.recorded_at)  # type: ignore[arg-type,return-value]
    earliest = min(m0_jan, key=lambda r: r.recorded_at)  # type: ignore[arg-type,return-value]
    assert latest.value > earliest.value


def test_readings_deterministic() -> None:
    """Same seed -> identical readings (no hash() randomization leak)."""
    ds = abbey_road.build()
    a = generate_readings(ds, seed=42)
    b = generate_readings(ds, seed=42)
    assert [(r.timeseries_id, r.timestamp, r.value) for r in a] == [
        (r.timeseries_id, r.timestamp, r.value) for r in b
    ]


def test_outage_patch() -> None:
    """M14 goes offline Feb 15; M14:h.patch reconstructs from child M15."""
    ds = abbey_road.build()
    m14_refs = {tr.timeseries_id: tr for tr in ds.timeseries_refs if tr.sensor_id == "M14.energy"}
    assert "M14:h.patch" in m14_refs
    patch = m14_refs["M14:h.patch"]
    assert patch.kind == "derived"
    assert patch.aggregation == "sum"
    assert patch.sources == ["M15:h"]
    assert patch.valid_from == abbey_road.M14_OFFLINE
    assert not patch.preferred

    stitched = m14_refs["M14:h"]
    assert stitched.kind == "derived"
    assert stitched.aggregation == "rolling_sum"
    assert "M14:h.patch" in stitched.sources
    assert stitched.preferred

    rs = generate_readings(ds, seed=42)
    patch_readings = [r for r in rs if r.timeseries_id == "M14:h.patch"]
    assert len(patch_readings) > 0
    assert min(r.timestamp for r in patch_readings).date() == abbey_road.M14_OFFLINE
    values = [r.value for r in sorted(patch_readings, key=lambda r: r.timestamp)]
    assert all(b >= a for a, b in pairwise(values))


def test_glitch_exclusion() -> None:
    """M14:h.A ends before glitch, M14:h.B starts after. No spike in stitched."""
    ds = abbey_road.build()
    m14_refs = {tr.timeseries_id: tr for tr in ds.timeseries_refs if tr.sensor_id == "M14.energy"}
    assert m14_refs["M14:h.A"].valid_to == abbey_road.M14_GLITCH_START
    assert m14_refs["M14:h.B"].valid_from == abbey_road.M14_GLITCH_END

    rs = generate_readings(ds, seed=42)
    stitched = sorted(
        [r for r in rs if r.timeseries_id == "M14:h"],
        key=lambda r: r.timestamp,
    )
    diffs = [b.value - a.value for a, b in pairwise(stitched)]
    max_hourly = max(diffs)
    median_hourly = sorted(diffs)[len(diffs) // 2]
    assert max_hourly < median_hourly * 10, "spike in stitched M14:h during glitch"


def test_annotation_filter() -> None:
    """Dataset.filter_by_media() correctly filters annotations."""
    ds = abbey_road.build()
    assert len(ds.annotations) == 8
    filtered = ds.filter_by_media("EL")
    assert len(filtered.annotations) == 8
    categories = {a.category for a in filtered.annotations}
    assert categories >= {"outage", "swap", "data_quality", "patch", "calibration", "unknown"}


def test_rolling_sum_stitching() -> None:
    """M14:h stitched counter is monotonic across all segment boundaries."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    stitched = sorted(
        [r for r in rs if r.timeseries_id == "M14:h"],
        key=lambda r: r.timestamp,
    )
    total_hours = (abbey_road.PERIOD_END - abbey_road.PERIOD_START).days * 24
    assert len(stitched) == total_hours
    diffs = [b.value - a.value for a, b in pairwise(stitched)]
    assert all(d >= 0 for d in diffs), "M14:h stitched counter not monotonic"


def test_conservation_violation() -> None:
    """M14's recorded monthly consumption exceeds its share of M13 in January."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    by_ts: dict[str, list] = defaultdict(list)
    for r in rs:
        if r.timeseries_id in ("M13:h", "M14:h"):
            by_ts[r.timeseries_id].append(r)
    m13 = sorted(by_ts["M13:h"], key=lambda r: r.timestamp)
    m14 = sorted(by_ts["M14:h"], key=lambda r: r.timestamp)
    jan_end = datetime(2026, 2, 1)
    m13_jan = [r for r in m13 if r.timestamp < jan_end]
    m14_jan = [r for r in m14 if r.timestamp < jan_end]
    m13_consumption = m13_jan[-1].value - m13_jan[0].value
    m14_consumption = m14_jan[-1].value - m14_jan[0].value
    assert m14_consumption > m13_consumption * 0.6, (
        "M14 should exceed its natural share (~60%) of M13 due to extra feed"
    )


def test_parallel_roots() -> None:
    """R1 and R2 are independent roots with no relation between them."""
    ds = abbey_road.build()
    r1_parents = [r for r in ds.relations if r.child_meter_id == "R1"]
    r2_parents = [r for r in ds.relations if r.child_meter_id == "R2"]
    r1_children = [r for r in ds.relations if r.parent_meter_id == "R1"]
    r2_children = [r for r in ds.relations if r.parent_meter_id == "R2"]
    assert r1_parents == [] and r2_parents == []
    assert r1_children == [] and r2_children == []
    rs = generate_readings(ds, seed=42)
    r1_readings = [r for r in rs if r.timeseries_id == "R1:h"]
    r2_readings = [r for r in rs if r.timeseries_id == "R2:h"]
    total_hours = (abbey_road.PERIOD_END - abbey_road.PERIOD_START).days * 24
    assert len(r1_readings) == total_hours
    assert len(r2_readings) == total_hours


def test_frozen_counter() -> None:
    """M16's counter stops incrementing after the freeze date."""
    ds = abbey_road.build()
    rs = generate_readings(ds, seed=42)
    m16 = sorted(
        [r for r in rs if r.timeseries_id == "M16:h"],
        key=lambda r: r.timestamp,
    )
    freeze_dt = datetime(2026, 2, 20)
    after_freeze = [r for r in m16 if r.timestamp >= freeze_dt]
    assert len(after_freeze) > 24
    frozen_value = after_freeze[0].value
    assert all(r.value == frozen_value for r in after_freeze)
