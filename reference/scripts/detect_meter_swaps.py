#!/usr/bin/env python3
"""Detect counter resets in daily timeseries and classify them.

Reads ``01_extracted/timeseries_daily.csv`` (which already flags resets
via ``is_reset=1``) and classifies each into:

- ``swap``     — counter resets but readings resume (device replacement).
- ``rollover`` — counter resets because the accumulator wrapped at a
                 known register ceiling. Same stitching as ``swap``,
                 but labelled honestly so downstream annotations don't
                 claim a physical device change that didn't happen.
- ``offline``  — counter resets and stays near zero (meter decommissioned).
- ``glitch``   — counter drops and reverts within a few days.

Schneider PowerLogic / ION meters have a built-in rollover at
10,000,000 by default: the integrator modules that accumulate energy
carry a ``rollover value`` setup register whose default for most
integrator modules is 10,000,000 (the module could run higher — it
uses 32-bit float — but precision degrades at large values, so
Schneider caps it by default). When the accumulated value reaches the
cap it wraps back to zero and continues. Other common caps we recognise
are 1,000,000 (some legacy firmware) and 100,000,000 (newer ION
configurations). See `reference/docs/` for the investigation that led
to this classification.

Output: ``01_extracted/meter_swaps.csv`` consumed by ``build_ontology.py``
to generate the Abbey Road M6-style multi-ref pattern (two raw refs with
validity windows + one derived rolling_sum ref marked preferred).
``rollover`` and ``swap`` produce the same stitched ref shape — the
classification only changes what downstream annotations say.

Usage:
    python detect_meter_swaps.py WORKSTREAM_DIR
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Known Schneider PowerLogic / ION rollover ceilings. Default for most
# ION integrator modules is 10,000,000; a few configurations use 1e6 or
# 1e8. A pre-reset v_last within ROLLOVER_TOLERANCE below any of these
# values is strong evidence the reset is a register wrap, not a device
# change.
ROLLOVER_CEILINGS = (1_000_000.0, 10_000_000.0, 100_000_000.0)
# 3% — reset happens mid-day at a value just shy of the ceiling.
# Originally set to 1% but real utility-meter patterns (B660.H23_1)
# show operator/rollover resets landing anywhere from 97.8% to 99.5%
# of the ceiling depending on when in the day the meter was read;
# widening to 3% catches all observed near-ceiling resets without
# introducing false positives (no non-ceiling resets sit in the 1–3%
# band across any of the workstreams).
ROLLOVER_TOLERANCE = 0.03


def _looks_like_rollover(pre_reset_v_last: float) -> float | None:
    """Return the matched ceiling if `pre_reset_v_last` is within
    `ROLLOVER_TOLERANCE` below one of the known Schneider ceilings.
    Return None otherwise.
    """
    for ceiling in ROLLOVER_CEILINGS:
        lower = ceiling * (1.0 - ROLLOVER_TOLERANCE)
        if lower <= pre_reset_v_last <= ceiling:
            return ceiling
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workstream_dir", type=Path)
    args = ap.parse_args()

    daily_path = args.workstream_dir / "01_extracted" / "timeseries_daily.csv"
    out_path = args.workstream_dir / "01_extracted" / "meter_swaps.csv"

    if not daily_path.exists():
        print(f"no timeseries_daily.csv in {args.workstream_dir}", file=sys.stderr)
        return 1

    with daily_path.open() as f:
        rows = list(csv.DictReader(f))

    by_meter: dict[str, list[dict]] = {}
    for r in rows:
        by_meter.setdefault(r["meter_id"], []).append(r)

    swaps: list[dict] = []
    for meter_id, meter_rows in by_meter.items():
        meter_rows.sort(key=lambda r: r["day"])
        for i, r in enumerate(meter_rows):
            if r["is_reset"] != "1":
                continue

            swap_date = r["day"]
            old_last = float(r["v_first"])

            post_reset = meter_rows[i + 1 : i + 15]
            nonzero_days = sum(1 for pr in post_reset if float(pr["delta"]) > 0.1)

            if nonzero_days >= 3:
                # Counter reset with resumed activity — either a real
                # device swap or a register rollover. Distinguish by
                # whether `old_last` sits just below a known Schneider
                # rollover ceiling. If it does, the reset is explained
                # by register wrap and we label honestly.
                ceiling = _looks_like_rollover(old_last)
                event_type = "rollover" if ceiling is not None else "swap"
            else:
                event_type = "offline"

            swaps.append({
                "meter_id": meter_id,
                "swap_date": swap_date,
                "event_type": event_type,
                "old_last_value": f"{old_last:.4f}",
            })

    # Detect frozen counters: counter stuck at end of data window.
    # Only flags permanent offlines — intermittent flat periods are ignored.
    already_frozen: dict[str, str] = {}
    for meter_id, meter_rows in by_meter.items():
        meter_rows.sort(key=lambda r: r["day"])
        last_active = len(meter_rows) - 1
        while last_active >= 0 and float(meter_rows[last_active]["delta"]) == 0:
            last_active -= 1
        frozen_tail = len(meter_rows) - 1 - last_active
        if frozen_tail >= 5 and last_active >= 0:
            freeze_start = last_active + 1
            already_frozen[meter_id] = meter_rows[freeze_start]["day"]
            swaps.append({
                "meter_id": meter_id,
                "swap_date": meter_rows[freeze_start]["day"],
                "event_type": "offline",
                "old_last_value": meter_rows[freeze_start]["v_last"],
            })

    # Update is_reset offline events with earlier frozen dates
    for s in swaps:
        if s["event_type"] == "offline" and s["meter_id"] in already_frozen:
            frozen_date = already_frozen[s["meter_id"]]
            if frozen_date < s["swap_date"]:
                s["swap_date"] = frozen_date

    # Deduplicate: keep earliest offline per meter
    seen_offline: dict[str, dict] = {}
    deduped: list[dict] = []
    for s in swaps:
        key = (s["meter_id"], s["event_type"])
        if s["event_type"] == "offline":
            if s["meter_id"] not in seen_offline or s["swap_date"] < seen_offline[s["meter_id"]]["swap_date"]:
                seen_offline[s["meter_id"]] = s
        else:
            deduped.append(s)
    deduped.extend(seen_offline.values())
    swaps = deduped

    # Detect glitches: V_LAST drops significantly across days then reverts.
    already_handled = {(s["meter_id"], s["swap_date"]) for s in swaps}
    for meter_id, meter_rows in by_meter.items():
        meter_rows.sort(key=lambda r: r["day"])
        i = 1
        while i < len(meter_rows) - 1:
            prev_vlast = float(meter_rows[i - 1]["v_last"])
            curr_vlast = float(meter_rows[i]["v_last"])
            drop = curr_vlast - prev_vlast
            if drop >= -100 or (meter_id, meter_rows[i]["day"]) in already_handled:
                i += 1
                continue
            for j in range(i + 1, min(i + 6, len(meter_rows))):
                post_vlast = float(meter_rows[j]["v_last"])
                if abs(post_vlast - prev_vlast) < abs(drop) * 0.1:
                    glitch_start = meter_rows[i]["day"]
                    glitch_end = meter_rows[j + 1]["day"] if j + 1 < len(meter_rows) else meter_rows[j]["day"]
                    swaps.append({
                        "meter_id": meter_id,
                        "swap_date": glitch_start,
                        "event_type": "glitch",
                        "old_last_value": f"{prev_vlast:.4f}",
                        "glitch_end": glitch_end,
                    })
                    i = j + 1
                    break
            else:
                i += 1
                continue
            continue

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["meter_id", "swap_date", "event_type", "old_last_value", "glitch_end"])
        w.writeheader()
        w.writerows(swaps)

    for s in swaps:
        print(f"  {s['meter_id']}: {s['event_type']} on {s['swap_date']}")
    print(f"wrote {out_path} ({len(swaps)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
