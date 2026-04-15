"""Deterministic synthetic hourly readings for the Abbey Road site.

Generation model
----------------

For each real meter we synthesize an hourly *own* consumption profile:

    own(t) = baseline * (1 + a·daily(t)) * (1 + b·weekly(t))
                      * (1 + c·monthly(t)) * (1 + noise(t))

where

    daily(t)   - sin centered ~10:00, weekday-only business bump
    weekly(t)  - weekday/weekend factor
    monthly(t) - one slow cycle over the two-month span (heating tail
                 in Jan, cooler late Feb)
    noise(t)   - small gaussian, seeded

Each meter gets distinct (baseline, phase, amplitudes) so the chart
doesn't look stamped.

Then we propagate own consumption upward over `hasSubMeter` edges to get
each meter's *measured* hourly flow:

    flow(M) = own(M) + Σ flow(child)  for child in real hasSubMeter children

`feeds` edges to virtuals are model-level attributions and never add
back to the parent. Validity is respected: a meter contributes 0
outside `[valid_from, valid_to)` and an edge is skipped at hours
outside its own validity.

Supplier-side (I1+I2+I3) is generated as M0_flow scaled by a small
±0.1% drift, then split across the three intakes so the
reconciliation delta is a real but tiny signal.

Outputs
-------

For every TimeseriesRef on a real meter we emit one Reading per
period:

- counter (hourly): cumulative kWh index = per-meter offset + cumsum
- delta   (monthly): consumption summed over the calendar month
"""

from __future__ import annotations

import zlib
from datetime import date, datetime
from typing import cast

import numpy as np

from ontology import Dataset, Reading


def _det_seed(base: int, key: str) -> int:
    """Deterministic per-key seed (hash() is randomized across runs)."""
    return base + zlib.crc32(key.encode()) % 10_000

# Per-meter own-consumption baseline in kWh/h. Values picked so the
# upstream sums roughly match a small industrial site (~450 kWh/h at
# the intake) and so individual branches read plausibly.
OWN_BASELINE_KWH_H: dict[str, float] = {
    "M0": 1.0,    # tiny residual on the intake itself
    "M1": 5.0,    # B1 office trunk
    "M2": 8.0,    # B1 office sub a
    "M3": 6.0,    # B1 office sub b
    "M4": 8.0,    # B1 prod trunk own
    "M5": 6.0,    # B1 prod leaf own
    "M6": 12.0,   # B2 office
    "M7": 70.0,   # B2 prod trunk (heaviest single branch)
    "M8": 25.0,   # B5 warehouse + everything that hangs off it
    "M9": 18.0,   # B9 / shared warehouse
    "M10": 22.0,  # shared leaf to B10/B11
    # Declared in topology but not (yet) instrumented - produces true
    # consumption that propagates upstream but emits no readings of its
    # own. Exercises the "known but unmeasured" case.
    "M11": 3.0,   # B2 prod sub-panel, pending PME wiring
}

# Per-meter multiplicative measurement noise, applied to the *recorded*
# flow so the sum at a parent meter doesn't exactly equal the sum of its
# children. This is what makes reconciliation deltas a real signal
# instead of a bookkeeping tautology.
MEASUREMENT_NOISE_SD = 0.005  # ~0.5% per hour per meter

# M5 has a communication outage mid-January (PME collector lost the
# connection). Physical consumption continues - only the recorded rows
# are missing. Upstream meters still see the true flow.
M5_OUTAGE_START = datetime(2026, 1, 13, 14)  # Jan 13, 14:00
M5_OUTAGE_END = datetime(2026, 1, 13, 22)    # 8-hour gap

# M0's January manual reading was first entered early Feb, then
# corrected mid-March when the Avläsning operator found a misread
# digit on the bill. We emit both rows (same timestamp, different
# recorded_at) so the correction trail is visible.
M0_JAN_FIRST_RECORDED_AT = datetime(2026, 2, 5, 10)
M0_JAN_CORRECTION_RECORDED_AT = datetime(2026, 3, 15, 14)
M0_JAN_CORRECTION_FACTOR = 1.014  # the original underestimated by ~1.4%

# Per-meter shaping coefficients. Production-heavy meters have a sharper
# weekday/business-hours profile; office meters lean weekday; warehouses
# are flatter. Phase shifts the daily peak slightly.
SHAPE: dict[str, dict[str, float]] = {
    # mid: {daily_amp, weekly_amp, monthly_amp, noise_sd, phase_h}
    "M0":  {"daily": 0.10, "weekly": 0.10, "monthly": 0.10, "noise": 0.05, "phase": 0.0},
    "M1":  {"daily": 0.45, "weekly": 0.40, "monthly": 0.10, "noise": 0.06, "phase": 0.0},
    "M2":  {"daily": 0.45, "weekly": 0.40, "monthly": 0.10, "noise": 0.07, "phase": 0.5},
    "M3":  {"daily": 0.45, "weekly": 0.40, "monthly": 0.10, "noise": 0.07, "phase": -0.5},
    "M4":  {"daily": 0.55, "weekly": 0.30, "monthly": 0.15, "noise": 0.06, "phase": 0.0},
    "M5":  {"daily": 0.55, "weekly": 0.30, "monthly": 0.15, "noise": 0.06, "phase": 0.0},
    "M6":  {"daily": 0.45, "weekly": 0.40, "monthly": 0.10, "noise": 0.06, "phase": 0.0},
    "M7":  {"daily": 0.60, "weekly": 0.25, "monthly": 0.20, "noise": 0.05, "phase": 0.0},
    "M8":  {"daily": 0.20, "weekly": 0.10, "monthly": 0.30, "noise": 0.08, "phase": 1.0},
    "M9":  {"daily": 0.20, "weekly": 0.10, "monthly": 0.30, "noise": 0.08, "phase": -1.0},
    "M10": {"daily": 0.25, "weekly": 0.15, "monthly": 0.25, "noise": 0.08, "phase": 0.5},
    "M11": {"daily": 0.50, "weekly": 0.30, "monthly": 0.15, "noise": 0.06, "phase": 0.0},
}

# How the supplier-side splits across the three intakes (must sum to 1).
INTAKE_SHARES: dict[str, float] = {"I1": 0.40, "I2": 0.35, "I3": 0.25}


def _hourly_index(start: date, end: date) -> np.ndarray:
    """Hourly timestamps in [start, end) as a numpy datetime64 array."""
    n_hours = (end - start).days * 24
    base = np.datetime64(start, "h")
    return base + np.arange(n_hours, dtype="int64").astype("timedelta64[h]")


def _validity_mask(
    ts: np.ndarray, valid_from: date | None, valid_to: date | None
) -> np.ndarray:
    """Boolean mask: True at hours where [valid_from, valid_to) holds."""
    mask = np.ones(len(ts), dtype=bool)
    if valid_from is not None:
        mask &= ts >= np.datetime64(valid_from, "h")
    if valid_to is not None:
        mask &= ts < np.datetime64(valid_to, "h")
    return mask


def _seasonal_profile(
    ts: np.ndarray, shape: dict[str, float], rng: np.random.Generator
) -> np.ndarray:
    """Multiplicative shape factor: daily * weekly * monthly * noise."""
    # Hour of day (0..23) and day of week (Mon=0..Sun=6) from the
    # numpy datetime64 array. Compute via integer division off epoch.
    epoch_hours = ts.astype("datetime64[h]").astype("int64")
    hour_of_day = epoch_hours % 24
    # 1970-01-01 was a Thursday (=3 in Mon=0 convention).
    day_of_year = epoch_hours // 24
    day_of_week = (day_of_year + 3) % 7

    # Daily: sin centered on the chosen phase, with a hard weekday gate
    # so weekends stay flat-ish (still get a residual baseline).
    peak_hour = 10.0 + shape["phase"]
    daily_raw = np.sin(2 * np.pi * (hour_of_day - (peak_hour - 6.0)) / 24.0)
    daily_raw = np.clip(daily_raw, 0.0, 1.0)  # only the bump, no negative dip
    is_weekday = (day_of_week < 5).astype(float)
    daily = shape["daily"] * daily_raw * (0.3 + 0.7 * is_weekday)

    # Weekly: weekdays high, weekends low (always-on loads remain).
    weekly = shape["weekly"] * (is_weekday - 0.5) * 2.0  # +amp weekday, -amp weekend

    # Monthly: one slow cosine across the two-month span. Aligned so it's
    # high in early Jan (heating) and ~0 by end of Feb.
    period_start_day = ts[0].astype("datetime64[D]").astype("int64")
    days_in = (epoch_hours / 24.0) - period_start_day
    span_days = (ts[-1].astype("datetime64[D]").astype("int64") - period_start_day) + 1
    monthly = shape["monthly"] * np.cos(np.pi * days_in / span_days)

    noise = rng.normal(0.0, shape["noise"], size=len(ts))

    profile: np.ndarray = (
        (1.0 + daily) * (1.0 + weekly) * (1.0 + monthly) * (1.0 + noise)
    )
    return profile


def _topo_order(meters: list[str], children_of: dict[str, list[str]]) -> list[str]:
    """Topological sort with leaves first (post-order)."""
    visited: set[str] = set()
    order: list[str] = []

    def visit(m: str) -> None:
        if m in visited:
            return
        visited.add(m)
        for c in children_of.get(m, []):
            visit(c)
        order.append(m)

    for m in meters:
        visit(m)
    return order


def generate_readings(ds: Dataset, seed: int = 42) -> list[Reading]:
    """Generate hourly + monthly readings for the Abbey Road dataset.

    Walks the meter graph to compute each real meter's measured hourly
    flow, then writes one Reading per timeseries_ref according to its
    `reading_type` (counter for hourly, delta for monthly).
    """
    rng = np.random.default_rng(seed)

    meter_by_id = {m.meter_id: m for m in ds.meters}

    # Establish the time axis from the first ref's period - we hardcode to
    # the abbey_road PERIOD here via the validity of M0 (its valid_from /
    # valid_to are the broadest internal series; otherwise fall back to
    # the abbey_road default).
    from . import abbey_road

    ts = _hourly_index(abbey_road.PERIOD_START, abbey_road.PERIOD_END)

    # ------------------------------------------------------------------
    # Step 1: own-consumption profiles for each real downstream meter.
    # ------------------------------------------------------------------
    own: dict[str, np.ndarray] = {}
    for mid, baseline in OWN_BASELINE_KWH_H.items():
        m = meter_by_id[mid]
        # Independent RNG stream per meter so the same meter is stable
        # across runs even if we add new meters above it.
        meter_rng = np.random.default_rng(_det_seed(seed, mid))
        profile = baseline * _seasonal_profile(ts, SHAPE[mid], meter_rng)
        # Clip to non-negative - noise can dip a slow profile below zero
        # near the trough; physical counters never tick down.
        profile = np.maximum(profile, 0.0)
        # Mask out hours outside the meter's validity window.
        profile *= _validity_mask(ts, m.valid_from, m.valid_to)
        own[mid] = profile

    # ------------------------------------------------------------------
    # Step 2: propagate up `hasSubMeter` edges to get measured flow.
    # ------------------------------------------------------------------
    real_ids = set(OWN_BASELINE_KWH_H.keys())
    children_real: dict[str, list[str]] = {mid: [] for mid in real_ids}
    edge_validity: dict[tuple[str, str], tuple[date | None, date | None]] = {}
    for r in ds.relations:
        if r.relation_type != "hasSubMeter":
            continue
        if r.parent_meter_id not in real_ids or r.child_meter_id not in real_ids:
            continue
        children_real[r.parent_meter_id].append(r.child_meter_id)
        edge_validity[(r.parent_meter_id, r.child_meter_id)] = (r.valid_from, r.valid_to)

    flow: dict[str, np.ndarray] = {mid: arr.copy() for mid, arr in own.items()}
    for mid in _topo_order(list(real_ids), children_real):
        for child in children_real[mid]:
            child_flow = flow[child]
            # Skip child contribution outside the *edge*'s validity even
            # if the child meter itself is valid (defensive; child_flow
            # is already zero outside child's window).
            vf, vt = edge_validity[(mid, child)]
            edge_mask = _validity_mask(ts, vf, vt)
            flow[mid] = flow[mid] + child_flow * edge_mask

    # ------------------------------------------------------------------
    # Step 2.5: measurement noise on each meter's *recorded* flow.
    # The truth is additive (Kirchhoff / mass balance) but each sensor
    # reads it with small independent error. Without this the parent
    # always exactly equals the sum of its children and reconciliation
    # is a tautology.
    # ------------------------------------------------------------------
    recorded_flow: dict[str, np.ndarray] = {}
    for mid, true in flow.items():
        noise_rng = np.random.default_rng(_det_seed(seed, mid + ":measurement"))
        noise = noise_rng.normal(0.0, MEASUREMENT_NOISE_SD, size=len(ts))
        recorded_flow[mid] = np.maximum(true * (1.0 + noise), 0.0)

    # ------------------------------------------------------------------
    # Step 3: supplier side. I1+I2+I3 ≈ M0 with seasonal drift (higher
    # in winter), split by fixed shares with a touch of per-meter wobble.
    # ------------------------------------------------------------------
    span_days = (abbey_road.PERIOD_END - abbey_road.PERIOD_START).days
    days_in = (np.arange(len(ts), dtype=float)) / 24.0
    # Cosine envelope: peaks near start (heating season), trails off by
    # end of period. Amplitude 2% + small gaussian jitter.
    seasonal_drift = 0.02 * np.cos(np.pi * days_in / span_days)
    drift_noise = rng.normal(0.0, 0.003, size=len(ts))
    drift = seasonal_drift + drift_noise
    supplier_total = recorded_flow["M0"] * (1.0 + drift)
    supplier_total = np.maximum(supplier_total, 0.0)

    # Generate raw shares with a small per-meter modulation, then
    # renormalize so they sum exactly to supplier_total.
    raw_shares: dict[str, np.ndarray] = {}
    for mid, share in INTAKE_SHARES.items():
        wobble_rng = np.random.default_rng(_det_seed(seed, mid))
        wobble = 1.0 + wobble_rng.normal(0.0, 0.02, size=len(ts))  # ~2%
        raw_shares[mid] = share * wobble
    share_sum = sum(raw_shares.values())
    for mid in INTAKE_SHARES:
        recorded_flow[mid] = supplier_total * raw_shares[mid] / share_sum

    # ------------------------------------------------------------------
    # Step 4: emit Reading rows per timeseries_ref.
    # Two passes so derived refs can read measured-ref offsets.
    # ------------------------------------------------------------------
    readings: list[Reading] = []
    refs_by_id = {r.timeseries_id: r for r in ds.timeseries_refs}
    # Refs hang off sensors; sensors hang off meters. Build the lookup.
    sensor_meter = {s.sensor_id: s.meter_id for s in ds.sensors}
    # Cache the starting offset of each measured counter ref so the
    # stitched derived ref can anchor on its first source's offset.
    offset_by_ref: dict[str, float] = {}

    # ---- Pass 1: raw refs (counter + delta) ----
    for ref in ds.timeseries_refs:
        if ref.kind == "derived":
            continue
        ref_mid = sensor_meter.get(ref.sensor_id)
        if ref_mid is None or ref_mid not in recorded_flow:
            continue  # virtuals / POOL have no synthesized series
        m = meter_by_id[ref_mid]
        meter_flow = recorded_flow[ref_mid]

        # The window for this ref: prefer the ref's own validity (device
        # window), fall back to the meter's (onboarding / retirement).
        window_from = ref.valid_from or m.valid_from
        window_to = ref.valid_to or m.valid_to
        window = _validity_mask(ts, window_from, window_to)

        if ref.reading_type == "counter":
            # Per-device (or per-meter when no device) counter offset. A
            # freshly-installed field device usually reads near zero at
            # install; long-lived meters have large accumulated totals.
            offset_key = ref.device_id or ref_mid
            offset_rng = np.random.default_rng(_det_seed(seed, offset_key + ":offset"))
            if ref.device_id is not None:
                offset = float(offset_rng.uniform(0, 5_000))
            else:
                offset = float(offset_rng.uniform(50_000, 500_000))
            offset_by_ref[ref.timeseries_id] = offset

            # Counter only advances while the ref is valid. We cumsum the
            # masked flow so hours outside the window contribute nothing.
            cum = offset + np.cumsum(meter_flow * window)
            for i, t in enumerate(ts):
                if not window[i]:
                    continue
                readings.append(
                    Reading(
                        timeseries_id=ref.timeseries_id,
                        timestamp=cast(datetime, t.astype("datetime64[s]").astype(object)),
                        value=round(float(cum[i]), 3),
                    )
                )
        elif ref.reading_type == "delta":
            # Monthly aggregate. Stamp at month start.
            t0 = ts[0].astype("datetime64[D]").astype(object)
            assert isinstance(t0, date)
            month = t0
            month_starts: list[date] = []
            while month < abbey_road.PERIOD_END:
                month_starts.append(month)
                # advance to first of next month
                if month.month == 12:
                    month = date(month.year + 1, 1, 1)
                else:
                    month = date(month.year, month.month + 1, 1)
            for ms in month_starts:
                me = (
                    date(ms.year + 1, 1, 1)
                    if ms.month == 12
                    else date(ms.year, ms.month + 1, 1)
                )
                in_month = (ts >= np.datetime64(ms, "h")) & (ts < np.datetime64(me, "h"))
                in_window = in_month & window
                if not in_window.any():
                    continue
                month_kwh = float(meter_flow[in_window].sum())
                readings.append(
                    Reading(
                        timeseries_id=ref.timeseries_id,
                        timestamp=datetime(ms.year, ms.month, ms.day),
                        value=round(month_kwh, 1),
                    )
                )
        else:
            raise ValueError(f"unknown reading_type: {ref.reading_type}")

    # ---- Pass 2: derived refs ----
    for ref in ds.timeseries_refs:
        if ref.kind != "derived":
            continue
        ref_mid = sensor_meter.get(ref.sensor_id)
        if ref_mid is None or ref_mid not in recorded_flow:
            continue
        meter_flow = recorded_flow[ref_mid]

        if ref.aggregation == "rolling_sum":
            # "As if never replaced" cumulative: anchor on the earliest
            # source's offset, then cumsum the meter's flow across the
            # union of all source windows. Because flow[mid] is the
            # meter-point's hourly consumption (not per-device), the
            # cumulative series is simply offset_first + cumsum(flow).
            src_refs = sorted(
                (refs_by_id[s] for s in ref.sources),
                key=lambda r: r.valid_from or date.min,
            )
            first = src_refs[0]
            first_offset = offset_by_ref[first.timeseries_id]

            # Span = earliest source valid_from → latest source valid_to.
            span_from = min(
                (r.valid_from for r in src_refs if r.valid_from is not None),
                default=None,
            )
            span_to = max(
                (r.valid_to for r in src_refs if r.valid_to is not None),
                default=None,
            )
            span = _validity_mask(ts, span_from, span_to)

            cum = first_offset + np.cumsum(meter_flow * span)
            for i, t in enumerate(ts):
                if not span[i]:
                    continue
                readings.append(
                    Reading(
                        timeseries_id=ref.timeseries_id,
                        timestamp=cast(datetime, t.astype("datetime64[s]").astype(object)),
                        value=round(float(cum[i]), 3),
                    )
                )
        elif ref.aggregation == "sum":
            # Cross-series sum at each timestep. Assumes sources share
            # the time grid; we union all their timestamps and sum values
            # per timestamp. Not exercised yet in Abbey Road - vocab
            # support only.
            raise NotImplementedError(
                "sum aggregation is declared in the schema but no test-site "
                "derived ref uses it yet"
            )
        else:
            raise ValueError(
                f"unsupported derived aggregation: {ref.aggregation!r}"
            )

    # ------------------------------------------------------------------
    # Step 5: realism post-processing.
    # ------------------------------------------------------------------

    # M5 communication outage: drop the readings in the window. Physical
    # flow continues (upstream M4/M0 still reflect it), only M5's DW
    # reporting has a gap.
    readings = [
        r for r in readings
        if not (
            r.timeseries_id == "M5:h"
            and M5_OUTAGE_START <= r.timestamp < M5_OUTAGE_END
        )
    ]

    # M0:m January correction. The original monthly reading was entered
    # on 2026-02-05 (slightly low); the correction was re-entered on
    # 2026-03-15 after the Avläsning operator re-checked the bill.
    # Tag the original with its recorded_at and append the correction.
    m0_jan = datetime(2026, 1, 1)
    for i, reading in enumerate(readings):
        if reading.timeseries_id == "M0:m" and reading.timestamp == m0_jan:
            original_value = reading.value / M0_JAN_CORRECTION_FACTOR
            readings[i] = Reading(
                timeseries_id="M0:m",
                timestamp=m0_jan,
                value=round(original_value, 1),
                recorded_at=M0_JAN_FIRST_RECORDED_AT,
            )
            readings.append(
                Reading(
                    timeseries_id="M0:m",
                    timestamp=m0_jan,
                    value=reading.value,
                    recorded_at=M0_JAN_CORRECTION_RECORDED_AT,
                )
            )
            break

    return readings
