# Schneider PME @ Gartuna / Snäckviken — Reference

## 1. Setup observed

**Stack**: Schneider **Power Monitoring Expert (PME)** on-prem, server `SESOWABMSPD03`. Primary data store is the `ION_Data` SQL Server warehouse with the canonical PME schema:

- `Source` — devices + system/virtual sources (~1,525 rows; NamespaceID=1, TimeZoneID=1 uniformly)
- `Quantity` — ION quantity dictionary (~7,100 standard ION registers)
- `SourceQuantity` — per-stream inventory with `MinTimestampUtc` / `MaxTimestampUtc`
- `DataLog2` — raw readings (not in the reference export)
- `Events` — device / PQ / alarm events (not currently ingested)

**Ingestion path**: Device → ION protocol / pulse inputs → PME LogInserter → `ION_Data` → Snowflake export (`OPS_WRK.ION_SWEDEN.DATALOG2`), pre-rolled to daily `V_FIRST` / `V_LAST` / `V_MIN` / `V_MAX` / `V_AVG` / `N_READINGS` with N≈96 implying 15-min native polling.

**Aggregation layer**: `VIP.*` (Virtual ION Processor) sources host software-only virtual meters / PQ analytics; this is where PME dashboards compute "clean" consumption. The `Dummy_energi_0_värde` / `Dummy_volym_0_värde` placeholders are VIP sources.

**Device mix** (SourceTypeID, inferred from signature patterns):

| ID | Class | Behavior |
|---|---|---|
| 4 | Utility revenue meter (H-series) | Provider-driven scheduled resets (bi-monthly / quarterly) |
| 5 | Main trunk / summary meter (ION, `-S` / `_1_1`) | ION 1e7 integrator ceiling |
| 6 | ION sub-meter, no SN | Not currently in Snowflake export |
| 7 | PowerLogic / iEM sub-meter (8-digit SN) | Standard pulse / Modbus sub-meter |
| 8 | ION-native process / WAGES meter | Bulk of fleet; 1e7 ceiling |
| 9 | M-Bus sub-meter (hex SN) | |
| 13, 19 | KNX / Modbus sub-meter (12-digit `540…` SN) | Sparse polling on some |
| 14, 15 | Ställverk gateway + sub-feeders (shared `1001-001` signature) | Some are STRUX-only, no BMS stream |
| 16 | 3-phase branch-circuit monitor | |
| 17 | UPS / smart PDU | |
| 18 | Secondary branch monitor | |

Authoritative names available via `SELECT ID, Name FROM ION_Data..SourceType` — not yet run.

**Pipeline posture decision**: series-derived, system-agnostic detection is primary. PME-specific signals (`SourceQuantity` endpoints, `Events` table, diagnostic quantities 254-260 / 979 / 995) are reserved for optional verification and annotation enrichment, never as pipeline dependencies. Accuracy cost is small (minute → day truncation the ontology discards anyway); portability gain is real (onboarding a non-Schneider site becomes a non-event).

---

## 2. Behavioral caveats for processing

Support legend:
- **Auto**: mechanical, ETL creates segments + derived union + annotation without human input
- **Flag**: ETL emits a flag; human creates the ontology rows
- **Manual**: no automation; human decision required
- **Ontology**: ✅ pattern exists in abbey_road; ⚠ partial / workaround; ❌ no primitive

| # | Caveat | Signal | Handling | Ontology |
|---|---|---|---|---|
| 1 | **Counter rollover at Schneider 1e7** | `delta < -0.5·v_prev` and `v_prev > 9×10⁶` | Auto: split to `:d.A` / `:d.B`, union via `rolling_sum`, annotate `category=rollover` | ✅ (M6 pattern) |
| 2 | **Device swap / config reset** | `delta < -0.5·v_prev` and `v_prev < 9×10⁶` | Auto stitching, annotate `category=swap`; add `devices.csv` row — **Flag** | ✅ (M6 + `devices.csv`) |
| 3 | **Extended offline (reporting stops)** | `N_READINGS=0` for > threshold, or `MaxTimestampUtc` stale | Auto if meter has children: `:d.patch` with `aggregation=sum` over children. Flag if leaf | ✅ (M14 patch) |
| 4 | **Frozen counter (polling continues, value static)** | `delta=0` for > threshold; `N_READINGS` remains normal | Flag only — distinguishes "dead" from "summer shutdown" requires judgment | ⚠ annotation only |
| 5 | **Summer shutdown / legitimate flat** | Same signal as frozen, but self-recovers | Manual classification (annotation context) | ⚠ annotation only |
| 6 | **Utility meter scheduled reset (H-series)** | Periodic `delta < 0` with regular cadence | Auto-stitch like rollover; annotate `category=rollover, subtype=utility_reset` once cadence known | ✅ (same primitive) |
| 7 | **BMS multi-register corruption (M17 pattern)** | Values alternate between real counter and near-zero / stuck-high | Flag — requires manual `:d.raw` + `:d.clip` (bracket) + `:d.patch` (interpolate) construction | ✅ (M17 pattern; manual) |
| 8 | **Near-zero spurious reads (B217 `14.764` pattern)** | Isolated single-sample dips with monotonic recovery | Flag. Either import as-is and let clip handle it, or treat as single-sample glitch and bracket | ✅ (clip primitive) |
| 9 | **Offline leaf meter (no children to patch)** | Offline + no `hasSubMeter` children | Flag only — no recovery possible | ⚠ annotation only; reading is permanent gap |
| 10 | **New source appears in PME** | Source ID not in `timeseries_refs.external_id` | Flag. Needs manual `meters.csv` / `sensors.csv` / `timeseries_refs.csv` rows (building, media, topology role) | n/a (human decision) |
| 11 | **New quantity on existing source** | Known source, new `(SourceID, QuantityID)` in `SourceQuantity` | Flag. Decide whether to ingest | n/a |
| 12 | **STRUX-only meter (no BMS stream)** | Name in STRUX / Excel but absent from PME `Source.Name` | Manual — annotation only; cannot synthesize | ⚠ (`snv_el_strux_only_*` pattern) |
| 13 | **Fractional subtraction in Excel formula** (e.g. `0.9×(S−T−U)`) | Excel parser output with non-unit coefficients on subtractions | Manual workaround — topology gives 1.0 subtraction, residual absorbed at campus | ❌ no primitive; known gap |
| 14 | **Sparse bi-daily sensors** (reading every other day) | `N_READINGS` cadence halved vs peers | Manual annotation. `hasSubMeter` only subtracts children on days parent has a reading → partial-day gaps | ❌ no interpolation layer |
| 15 | **Virtual meter double-counting** (same meter in two formulas) | Excel parser detects same ID in multiple + terms | Manual 50/50 feeds split or routing decision | ⚠ (feeds primitive; manual split) |
| 16 | **Power quality events / disturbances** | PME `Events` table or quantities 979 / 995 / 1011 | Not in pipeline today. Could be imported as complementary annotations (see §3) | n/a |
| 17 | **Device alarms (over-current, breaker trip)** | PME `Events` table | Same as above | n/a |
| 18 | **Parallel trunks mis-inferred as series** | Naming heuristic wrong (B600N / B600S) | Manual topology override | ✅ via `meter_relations.csv` + annotation |
| 19 | **Crosswalk ambiguity** (`<id>_E` vs `<id>`) | Two near-identical Snowflake names for same logical meter | Manual — prefer STRUX / Excel variant | ⚠ (`feedback_crosswalk_prefer_e_variant`) |
| 20 | **`(Mega)` pre-scaled quantity confusion** | QuantityID 744 vs 129 | No action — pre-scaled at VIP; do not double-scale | n/a |

---

## 3. Future improvements / follow-ups

Ranked roughly by leverage-to-effort.

1. **Run `SELECT ID, Name FROM ION_Data..SourceType`.** Replace inferred friendly names with the authoritative catalog before baking into tooling. One-shot query.

2. **Add `device_class` + behavioral properties to `devices.csv`.** `integrator_ceiling`, `scheduled_reset_cadence_days`, `expected_poll_interval_s`, `bms_available`. Lets the rollover / offline detectors branch per device instead of one-size-fits-all thresholds. Keep class vocabulary semantic (`utility_meter`, `sub_meter`, `gateway`), not vendor-branded. Per existing guidance, keep this as a sidecar extension off `device`, not inlined in Brick's `Equipment → hasPoint → Sensor` path.

3. **Import PME `Events` table as complementary annotations.** Device-unreachable, breaker, PQ-event, alarm rows become `annotations.csv` entries with a `source=pme_events` provenance marker. **Dedup rule**: if an event matches an existing derived annotation (same target, overlapping window), enrich the existing `description` with the precise timestamp rather than create a parallel row. Filter to severity ≥ warning to control volume.

4. **Add `source` / `origin` column to `annotations.csv`.** Values: `derived` / `pme_events` / `pme_sourcequantity` / `manual`. Unblocks reconciliation when PME signals and series-derived detection disagree. Low-cost schema change.

5. **Audit the Snowflake export filter.** The pipeline drops 30 SourceTypeID=6 sources (ION sub-meters with blank signatures) and ~70 KNX / UPS / branch-monitor streams (types 13 / 19 / 16 / 17 / 18). Some may fill current STRUX-only gaps. One-query check.

6. **Opt-in ingest of diagnostic quantities.** Status Change Counters (254-260) detect device config resets directly. Power Quality Event Status (979 / 995) correlates with consumption anomalies. Not needed for baseline accounting but adds diagnostic richness.

7. **Nightly `SourceQuantity` diff as a reconciliation check.** Not a dependency — a second opinion. If derived offline detection disagrees with `MaxTimestampUtc` by > 1 day, produce a diff report. Catches false negatives in either direction.

8. **Fractional-subtract primitive in `views.sql`.** Currently known to cause ±1-3 MWh residuals on Kyla buildings using `0.9×` / `0.1×` formulas. Would close that gap structurally instead of absorbing it at campus level.

9. **Sensor-interpolation layer for sparse bi-daily sensors.** Would resolve the `B612` / `B641` / `B833` partial-day subtraction gaps. Design question: interpolate at ingest vs at query time. Non-trivial.

10. **Replicate device-offline alarm as a first-class annotation.** Currently inferred from flat counter + heuristics. Once `Events` is parsed (#3), lifts to primary evidence for `outage` annotations.

11. **PME → non-PME portability test.** Onboard a second-site integration that isn't Schneider (even a mocked Metasys feed) to verify the ETL is genuinely system-agnostic and the PME-specific pieces are cleanly optional.
