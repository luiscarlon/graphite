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

from ontology import Dataset, Reading, TimeseriesRef


def _det_seed(base: int, key: str) -> int:
    """Deterministic per-key seed (hash() is randomized across runs)."""
    return base + zlib.crc32(key.encode()) % 10_000

# Per-meter own-consumption baseline in kWh/h. Keys include BOTH real
# meters and virtuals — each entity carries the physical own consumption
# of whatever it stands in for. Pass-through sub-panels (M11, M12, M10)
# have own=0 because their reading is entirely downstream flow. Virtuals
# (V1..V6) hold the consumption of the unmetered buildings they
# represent; at query time, coefficient shares on feeds edges resolve
# those values back against the parent's residual.
#
# Values are chosen so coefficients partition parent flow EXACTLY:
#   M11 → V1 (0.7 × 50 = 35), V2 (0.3 × 50 = 15), flow(M11) = 50
#   M12 → V3 (0.4 × 70 = 28), V4 (0.6 × 70 = 42), flow(M12) = 70
#   M10 → V5 (0.5 × 22 = 11), V6 (0.5 × 22 = 11), flow(M10) = 22
# where flow(V4) = own(V4) + flow(M9) = 2 + 40 = 42.
OWN_BASELINE_KWH_H: dict[str, float] = {
    # Real meters
    "M0": 1.0,    # tiny residual on the intake itself
    "M1": 5.0,    # B1 office trunk
    "M2": 8.0,    # B1 office sub a
    "M3": 6.0,    # B1 office sub b
    "M4": 8.0,    # B1 prod trunk own
    "M5": 6.0,    # B1 prod leaf own
    "M6": 12.0,   # B2 office
    "M7": 20.0,   # B2 prod trunk own (excludes M11 sub-panel chain)
    "M8": 8.0,    # B5 warehouse own (excludes M12 sub-panel chain)
    "M9": 18.0,   # B9 own
    "M10": 0.0,   # shared leaf — pass-through to V5/V6
    "M11": 0.0,   # B2 sub-panel — pass-through to V1/V2
    "M12": 0.0,   # B5 sub-panel — pass-through to V3/V4 (and V4→M9 chain)
    "M13": 5.0,   # B12 factory own
    "M14": 15.0,  # B12 multi-event sub own
    "M15": 8.0,   # B13 office sub
    "M16": 10.0,  # B14 frozen counter
    "R1": 25.0,   # B15 parallel root A
    "R2": 20.0,   # B16 parallel root B
    "M17": 15.0,  # campus-level, BMS register corruption analog
    # Virtuals holding unmetered-building consumption
    "V1": 35.0,   # B3
    "V2": 15.0,   # B4
    "V3": 28.0,   # B7
    "V4": 2.0,    # B8 own, excluding M9 sub-branch (kept small so
                  # flow(V4) = 42 sits just above flow(M9) = 40 and the
                  # "V4 net goes slightly negative on noisy hours"
                  # calibration-alert pattern is exercised)
    "V5": 11.0,   # B10
    "V6": 11.0,   # B11
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
    # Pass-through sub-panels: profile doesn't matter (own baseline = 0)
    # but the key must exist for the generator loop.
    "M11": {"daily": 0.00, "weekly": 0.00, "monthly": 0.00, "noise": 0.00, "phase": 0.0},
    "M12": {"daily": 0.00, "weekly": 0.00, "monthly": 0.00, "noise": 0.00, "phase": 0.0},
    "M13": {"daily": 0.30, "weekly": 0.15, "monthly": 0.20, "noise": 0.06, "phase": 0.5},
    "M14": {"daily": 0.40, "weekly": 0.25, "monthly": 0.15, "noise": 0.06, "phase": -0.5},
    "M15": {"daily": 0.45, "weekly": 0.40, "monthly": 0.10, "noise": 0.07, "phase": 0.0},
    "M16": {"daily": 0.20, "weekly": 0.10, "monthly": 0.30, "noise": 0.08, "phase": 1.0},
    "R1":  {"daily": 0.35, "weekly": 0.20, "monthly": 0.15, "noise": 0.06, "phase": 0.0},
    "R2":  {"daily": 0.30, "weekly": 0.15, "monthly": 0.20, "noise": 0.07, "phase": 0.5},
    "M17": {"daily": 0.30, "weekly": 0.15, "monthly": 0.20, "noise": 0.06, "phase": 0.5},
    # Virtuals — synthesized as warehouse-like flat profiles so the
    # downstream buildings have plausible consumption curves.
    "V1":  {"daily": 0.30, "weekly": 0.15, "monthly": 0.20, "noise": 0.07, "phase": 0.5},
    "V2":  {"daily": 0.30, "weekly": 0.15, "monthly": 0.20, "noise": 0.07, "phase": -0.5},
    "V3":  {"daily": 0.25, "weekly": 0.15, "monthly": 0.25, "noise": 0.08, "phase": 1.0},
    "V4":  {"daily": 0.25, "weekly": 0.15, "monthly": 0.25, "noise": 0.08, "phase": -1.0},
    "V5":  {"daily": 0.25, "weekly": 0.15, "monthly": 0.25, "noise": 0.08, "phase": 0.5},
    "V6":  {"daily": 0.25, "weekly": 0.15, "monthly": 0.25, "noise": 0.08, "phase": -0.5},
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
    # Step 1: own-consumption profiles for every entity with a baseline
    # (both real meters and virtuals). Virtuals carry the unmetered-
    # building consumption they stand in for; pass-through sub-panels
    # have own=0 and contribute only via propagation.
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
    # Step 2: propagate flow bottom-up along ALL topology edges
    # (hasSubMeter + feeds). Virtual intermediaries are transparent:
    # their flow = own + Σ children's flow, and that aggregated value
    # propagates to the nearest real ancestor via the feeds edge feeding
    # it. A real parent's reading is therefore the sum of every own-
    # consumption below it, regardless of how many virtuals sit in
    # between (M8 → M12 → V4 → M9 correctly accumulates M9 into M8).
    # ------------------------------------------------------------------
    all_ids = set(OWN_BASELINE_KWH_H.keys())
    children_all: dict[str, list[str]] = {mid: [] for mid in all_ids}
    edge_validity: dict[tuple[str, str], tuple[date | None, date | None]] = {}
    for r in ds.relations:
        if r.parent_meter_id not in all_ids or r.child_meter_id not in all_ids:
            continue
        children_all[r.parent_meter_id].append(r.child_meter_id)
        edge_validity[(r.parent_meter_id, r.child_meter_id)] = (r.valid_from, r.valid_to)

    flow: dict[str, np.ndarray] = {mid: arr.copy() for mid, arr in own.items()}
    for mid in _topo_order(list(all_ids), children_all):
        for child in children_all[mid]:
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
    # Step 2.6: post-processing on specific meters' recorded readings.
    # ------------------------------------------------------------------

    # M14 conservation violation: undocumented extra feed adds ~6 kWh/h
    # to the recorded readings but NOT to M13's accumulated flow.
    extra_rng = np.random.default_rng(_det_seed(seed, "M14:extra_feed"))
    extra = 6.0 * _seasonal_profile(ts, SHAPE["M14"], extra_rng)
    extra = np.maximum(extra, 0.0)
    extra *= _validity_mask(ts, None, abbey_road.M14_OFFLINE)
    recorded_flow["M14"] = recorded_flow["M14"] + extra

    # M16 frozen counter: stop incrementing after freeze date.
    freeze_idx = int(np.searchsorted(ts, np.datetime64(abbey_road.M16_FREEZE_START, "h")))
    recorded_flow["M16"][freeze_idx:] = 0.0

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

    # ---- Pass 1.5: inject BMS register corruption on M17:h ----
    # Replace emitted hourly counter readings with artifacts during the
    # corruption window. Some hours stay real (for `bracket` to recover);
    # every hour inside the sub-gap is forced out-of-band so that `bracket`
    # leaves a real gap that `interpolate` has to bridge.
    _inject_m17_corruption(readings, seed)

    # Build a value index over emitted readings so derived dispatches that
    # read source *values* (bracket, interpolate) don't have to rescan the
    # full readings list per ref.
    values_by_ref: dict[str, dict[datetime, float]] = {}
    for r in readings:
        values_by_ref.setdefault(r.timeseries_id, {})[r.timestamp] = r.value

    # ---- Pass 2: derived refs (sum, bracket, interpolate, rolling_sum) ----
    # Order matters: sum feeds rolling_sum; bracket feeds interpolate; both
    # clean outputs can feed rolling_sum. Unknown aggregations sort last
    # so the dispatch below can raise a clear error.
    _AGG_ORDER = {"sum": 0, "bracket": 1, "interpolate": 2, "rolling_sum": 3}
    derived_refs = [r for r in ds.timeseries_refs if r.kind == "derived"]
    derived_refs.sort(key=lambda r: _AGG_ORDER.get(r.aggregation or "", 99))

    for ref in derived_refs:
        ref_mid = sensor_meter.get(ref.sensor_id)
        if ref_mid is None or ref_mid not in recorded_flow:
            continue
        meter_flow = recorded_flow[ref_mid]

        if ref.aggregation == "sum":
            window = _validity_mask(ts, ref.valid_from, ref.valid_to)
            total_delta = np.zeros(len(ts))
            for src_id in ref.sources:
                src_ref = refs_by_id[src_id]
                src_mid = sensor_meter.get(src_ref.sensor_id)
                if src_mid is None or src_mid not in recorded_flow:
                    continue
                total_delta += recorded_flow[src_mid]
            offset = 0.0
            offset_by_ref[ref.timeseries_id] = offset
            cum = offset + np.cumsum(total_delta * window)
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
                values_by_ref.setdefault(ref.timeseries_id, {})[
                    cast(datetime, t.astype("datetime64[s]").astype(object))
                ] = round(float(cum[i]), 3)

        elif ref.aggregation == "bracket":
            # Monotone-clip: within [valid_from, valid_to), keep source
            # samples whose value lies between the source values just
            # outside the window. Parameter-free — endpoints come from
            # the source readings straddling the ref's validity.
            new_rows = _emit_bracket(ref, values_by_ref)
            readings.extend(new_rows)
            values_by_ref.setdefault(ref.timeseries_id, {}).update(
                {r.timestamp: r.value for r in new_rows}
            )

        elif ref.aggregation == "interpolate":
            # Linear counter fill between two source-derived endpoints;
            # emits one reading per hour in [valid_from, valid_to).
            new_rows = _emit_interpolate(ref, values_by_ref, ts)
            readings.extend(new_rows)
            values_by_ref.setdefault(ref.timeseries_id, {}).update(
                {r.timestamp: r.value for r in new_rows}
            )

        elif ref.aggregation == "rolling_sum":
            src_refs = sorted(
                (refs_by_id[s] for s in ref.sources),
                key=lambda r: r.valid_from or date.min,
            )
            first = src_refs[0]
            first_offset = offset_by_ref[first.timeseries_id]

            if any(r.valid_from is None for r in src_refs):
                span_from = None
            else:
                span_from = min(r.valid_from for r in src_refs)  # type: ignore[type-var]
            if any(r.valid_to is None for r in src_refs):
                span_to = None
            else:
                span_to = max(r.valid_to for r in src_refs)  # type: ignore[type-var]
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


def _inject_m17_corruption(readings: list[Reading], seed: int) -> None:
    """Mutate `readings` in place: replace M17:h hourly values inside the
    corruption window with artifacts (low / high-stuck). Outside the
    sub-gap some hours remain real; inside the sub-gap every hour is
    forced out-of-band so `bracket` leaves a gap to be patched.

    Real-world analog: a BMS misconfiguration feeds the same stream from
    multiple registers, so consecutive hourly polls land on different
    registers with no rhyme. We model that as a per-hour independent
    three-way Bernoulli: real (k) / high-stuck / low-artifact.
    """
    from . import abbey_road

    corr_start = datetime(
        abbey_road.M17_CORRUPTION_START.year,
        abbey_road.M17_CORRUPTION_START.month,
        abbey_road.M17_CORRUPTION_START.day,
    )
    corr_end = datetime(
        abbey_road.M17_CORRUPTION_END.year,
        abbey_road.M17_CORRUPTION_END.month,
        abbey_road.M17_CORRUPTION_END.day,
    )
    gap_start = datetime(
        abbey_road.M17_SUBGAP_START.year,
        abbey_road.M17_SUBGAP_START.month,
        abbey_road.M17_SUBGAP_START.day,
    )
    gap_end = datetime(
        abbey_road.M17_SUBGAP_END.year,
        abbey_road.M17_SUBGAP_END.month,
        abbey_road.M17_SUBGAP_END.day,
    )
    rng = np.random.default_rng(_det_seed(seed, "M17:corruption"))
    high = abbey_road.M17_HIGH_STUCK_VALUE
    low = abbey_road.M17_LOW_ARTIFACT_VALUE

    for i, r in enumerate(readings):
        if r.timeseries_id != "M17:h.raw":
            continue
        if not (corr_start <= r.timestamp < corr_end):
            continue
        in_gap = gap_start <= r.timestamp < gap_end
        roll = rng.random()
        if in_gap:
            # 70% high-stuck, 30% low-artifact, never real.
            new_value = high if roll < 0.7 else low + rng.uniform(0, 20)
        else:
            # 40% real (keep), 40% high-stuck, 20% low-artifact.
            if roll < 0.4:
                continue
            if roll < 0.8:
                new_value = high
            else:
                new_value = low + rng.uniform(0, 20)
        readings[i] = Reading(
            timeseries_id=r.timeseries_id,
            timestamp=r.timestamp,
            value=round(float(new_value), 3),
            recorded_at=r.recorded_at,
        )


def _ref_endpoints(
    ref: TimeseriesRef, values_by_ref: dict[str, dict[datetime, float]]
) -> tuple[datetime, float, datetime, float]:
    """Resolve a derived ref's validity-anchored endpoints against its
    single source. Returns (t_lo, v_lo, t_hi, v_hi).

    - `v_lo` = the source's most recent reading strictly BEFORE valid_from.
    - `v_hi` = the source's first reading AT OR AFTER valid_to.

    Both endpoints must resolve; otherwise we raise so callers see a
    clear materialization failure rather than silently inventing values.
    """
    if ref.valid_from is None or ref.valid_to is None:
        raise ValueError(
            f"derived ref {ref.timeseries_id} ({ref.aggregation}) requires "
            f"both valid_from and valid_to to anchor its endpoints"
        )
    if len(ref.sources) != 1:
        raise ValueError(
            f"derived ref {ref.timeseries_id} ({ref.aggregation}) requires "
            f"exactly one source, got {len(ref.sources)}"
        )
    src_id = ref.sources[0]
    src_values = values_by_ref.get(src_id, {})
    if not src_values:
        raise ValueError(
            f"derived ref {ref.timeseries_id} has source {src_id} with no "
            f"readings available"
        )
    vf = datetime(ref.valid_from.year, ref.valid_from.month, ref.valid_from.day)
    vt = datetime(ref.valid_to.year, ref.valid_to.month, ref.valid_to.day)
    before = [t for t in src_values if t < vf]
    atafter = [t for t in src_values if t >= vt]
    if not before:
        raise ValueError(
            f"derived ref {ref.timeseries_id}: source {src_id} has no reading "
            f"strictly before valid_from={vf}; can't anchor lo endpoint"
        )
    if not atafter:
        raise ValueError(
            f"derived ref {ref.timeseries_id}: source {src_id} has no reading "
            f"at or after valid_to={vt}; can't anchor hi endpoint"
        )
    t_lo = max(before)
    t_hi = min(atafter)
    return t_lo, src_values[t_lo], t_hi, src_values[t_hi]


def _emit_bracket(
    ref: TimeseriesRef, values_by_ref: dict[str, dict[datetime, float]]
) -> list[Reading]:
    """Parameter-free value-range filter. Within the ref's validity
    window, emit source samples whose value lies in [v_lo, v_hi] where
    (v_lo, v_hi) are the source readings just outside the window.

    Physical rationale: for a monotone cumulative counter, any reading
    between two known clean readings must itself lie between their
    values. Anything outside that band is necessarily an artifact.
    """
    _t_lo, v_lo, _t_hi, v_hi = _ref_endpoints(ref, values_by_ref)
    lo, hi = (v_lo, v_hi) if v_lo <= v_hi else (v_hi, v_lo)
    src_values = values_by_ref[ref.sources[0]]
    vf = datetime(ref.valid_from.year, ref.valid_from.month, ref.valid_from.day)  # type: ignore[union-attr]
    vt = datetime(ref.valid_to.year, ref.valid_to.month, ref.valid_to.day)        # type: ignore[union-attr]
    out: list[Reading] = []
    for t, v in sorted(src_values.items()):
        if not (vf <= t < vt):
            continue
        if lo <= v <= hi:
            out.append(
                Reading(timeseries_id=ref.timeseries_id, timestamp=t, value=v)
            )
    return out


def _emit_interpolate(
    ref: TimeseriesRef,
    values_by_ref: dict[str, dict[datetime, float]],
    ts: np.ndarray,
) -> list[Reading]:
    """Parameter-free linear interpolation. Between the two source
    readings that bracket the ref's validity window, emit one reading
    per hour in [valid_from, valid_to) with a counter value that
    linearly interpolates between the two endpoint values over wall
    time (not reading count — the two endpoints may be far apart).
    """
    t_lo, v_lo, t_hi, v_hi = _ref_endpoints(ref, values_by_ref)
    vf = datetime(ref.valid_from.year, ref.valid_from.month, ref.valid_from.day)  # type: ignore[union-attr]
    vt = datetime(ref.valid_to.year, ref.valid_to.month, ref.valid_to.day)        # type: ignore[union-attr]
    span_seconds = (t_hi - t_lo).total_seconds()
    if span_seconds <= 0:
        raise ValueError(
            f"interpolate ref {ref.timeseries_id}: degenerate endpoint span "
            f"(t_lo={t_lo}, t_hi={t_hi})"
        )
    out: list[Reading] = []
    for t_np in ts:
        t = cast(datetime, t_np.astype("datetime64[s]").astype(object))
        if not (vf <= t < vt):
            continue
        frac = (t - t_lo).total_seconds() / span_seconds
        value = v_lo + (v_hi - v_lo) * frac
        out.append(
            Reading(
                timeseries_id=ref.timeseries_id,
                timestamp=t,
                value=round(float(value), 3),
            )
        )
    return out
