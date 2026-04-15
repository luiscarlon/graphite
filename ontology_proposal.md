# Graphite Ontology Draft — WOP

> **Schema v2 update (2026-04-15).** Sections 5, 6, 7.5, 7.6, 8, and 9 have
> been revised to reflect decisions made while building the Abbey Road
> reference site. Key changes: `ext:flowCoefficient` now lives on the
> `feeds` edge (not the virtual sensor); timeseries references carry the
> full addressing triple `(database_id, path, external_id)`; derived series
> are declared in the ontology and materialized by the DW (new §9); readings
> support a `recorded_at` correction trail; `ext:meterStatus` dropped;
> validity may appear on both entities and relationships. Earlier wording
> is kept where correct and marked inline where superseded.


## 1. Objective

- Brick Schema implementation for AZ's metering landscape in Snäckviken and Gärtuna.
- Topology must be sufficient to automate all calculations from meter relations and the coefficients used for estimations in reporting.
- The model must handle changes in relationships and entities over time.
- The model should be good enough to produce the first models to exploit the data in EMS. Likely tweaks would come later.
- The proposal is a good instrument to discuss the design decisions rather than starting from scratch.

## 2. Design principles

- Stick to Brick standard classes and properties. Only use extensions when there is a business critical need that Brick cannot express. Where extensions are unavoidable:
  - Extensions live on side branches of the ontology, never in direct paths.
  - Investigate whether there is active debate or a proposed standard for the needed concept in the Brick community.
- Names for humans. All names should be readable and in English. Still, we can keep the existing meter names that carry a structural pattern (e.g. `B310.T27_12_2`) as `rdfs:label`.
- Separate physical and logical classes. Physical devices are likely to be replaced. The logical meter and its sensors are stable identities that must survive a hardware swap without losing history.
- Time is explicit. All relationships are time-bound with a start and an end (`ext:validFrom`, `ext:validTo`).
- Brick represents the physical world, not the business.
- Uniform meter classes. Use `brick:Electrical_Meter`, `brick:Thermal_Power_Meter`, `brick:Water_Meter` — never `Building_Electrical_Meter` or `Building_Meter`. Aggregation context (zone, building, site) comes from topology, not from the meter class.
- Canonical unit on sensor. `brick:hasUnit` on the sensor reflects the canonical (own) series unit. When external sources (TN) use a different unit, conversion is a pipeline concern — no `ext:hasUnit` on `TimeseriesReference`.

## 3. Core hierarchy

- Campus, `brick:Site`, *Södertälje*
  - Building, `brick:Building`, *B307*
    - Zone, `brick:Zone`, *API*, *Steriles*, *Engineering*, …
    - Logical meter, `brick:Electrical_Meter`, *B307.T10* (stable identity)
      - `brick:meters` → Zone / Building / Campus (what the meter measures)
      - `ext:mediaType` → `ext:MediaType`, *:media_EL*
      - Sensor, standard Brick path, via `brick:hasPoint`, `brick:Energy_Sensor`, *B307.T10.energy*
        - Unit, `brick:hasUnit`, `unit:KiloW-HR`
        - Timeseries reference, `ref:hasExternalReference` → `ref:TimeseriesReference`
          - ID (Brick instance), used as node IRI and via `dcterms:identifier`, *"B307.T10.energy.ref"*
          - External id, `ref:hasTimeseriesId`, *"631:129"*  *(key within the database)*
          - Database, `ref:storedAt` → `ref:Database`, *PME_SQL*
          - Path (schema.table within the database), `ext:path`, *"ingest.hourly"*
          - Kind, `ext:kind`, *"raw"* | *"derived"*
          - Device (optional, raw only), `ext:producedBy` → `ext:Device`, *MZ-1812A095-01*
            - Serial, `ext:serial`, *"MZ-1812A095-01"*
            - Manufacturer, `ext:manufacturer`, *"Schneider"*

Most buildings have a single zone (e.g. B307 belongs entirely to API). Some buildings contain several zones when the building is shared across production areas (e.g. B339 has zones for both API and Engineering).

### Core cardinality

- One campus contains many buildings.
- One building contains one or more zones.
- One building contains many systems, equipment, and meters.
- One piece of equipment has many sensors via `brick:hasPoint`.
- One sensor can carry many `ref:hasExternalReference` entries, for example, a one-minute timeseries in a TSDB and an hourly aggregate in PME, distinguished by `brick:aggregate`.
- One logical meter can be served by many devices: over time during a swap, or permanently for redundancy when hardware can only be replaced infrequently (see §7.10). When more than one is active at once, exactly one timeseries is marked `ref:preferred true` and reports filter on that flag — no double counting.

## 4. Class examples

| Concept | Brick class | Standard |
|---|---|---|
| Campus | `brick:Site` | Yes |
| Building | `brick:Building` | Yes |
| Zone (production area within a building: API, Steriles, OSD, Engineering, …) | `brick:Zone` | Yes |
| Electrical meter | `brick:Electrical_Meter` | Yes |
| Water meter | `brick:Water_Meter` / `brick:Hot_Water_Meter` / `brick:Chilled_Water_Meter` | Yes |
| Thermal meter | `brick:Thermal_Power_Meter` | Yes |
| Virtual meter (calculated allocation) | `brick:Electrical_Meter` + `brick:isVirtualMeter true` | Yes |
| Weather station | `brick:Weather_Station` | Yes |
| Photovoltaic array | `brick:Photovoltaic_Array` | Yes |
| Media type (operational grouping) | `ext:MediaType` | Extension |
| Heat pump | `brick:Heat_Pump` | Yes |
| Chiller | `brick:Chiller` | Yes |
| Heat exchanger | `brick:Heat_Exchanger` | Yes |
| Energy sensor | `brick:Energy_Sensor` | Yes |
| Power sensor | `brick:Power_Sensor` | Yes |
| Flow sensor | `brick:Water_Flow_Sensor` | Yes |
| Temperature sensor | `brick:Temperature_Sensor` | Yes |
| Frequency sensor | `brick:Frequency_Sensor` | Yes |
| Voltage / current / PQ sensors | `brick:Voltage_Sensor`, `brick:Current_Sensor`, `brick:Power_Factor_Sensor`, etc. | Yes |
| Fault status point | `brick:Fault_Status` | Yes |
| Timeseries reference | `ref:TimeseriesReference` | Yes |
| Database | `ref:Database` | Yes |
| Physical device (on timeseries) | `ext:Device` | Extension |
| Media type (operational grouping instance: `:media_EL`, `:media_KYLA`, …) | `ext:MediaType` | Extension |
| Installation system (Vatten / Kyla / Värme) | `ext:System` | Extension, deferred |

## 5. Relationship examples

| Concept | Brick relationship | Standard |
|---|---|---|
| Campus contains building | `brick:hasPart` | Yes |
| Building contains zone | `brick:hasPart` | Yes |
| Building contains equipment / meter | `brick:hasPart` | Yes |
| Main meter → sub-meter | `brick:hasSubMeter` | Yes |
| Meter feeds building / virtual meter | `brick:feeds` | Yes |
| Meter measures equipment / building | `brick:meters` | Yes |
| Equipment has sensor | `brick:hasPoint` | Yes |
| Sensor → timeseries | `ref:hasExternalReference` | Yes |
| Timeseries → database | `ref:storedAt` | Yes |
| Equipment carries substance | `brick:hasSubstance` | Yes |
| Timeseries produced by physical device | `ext:producedBy` | Extension |
| Meter belongs to media category | `ext:mediaType` | Extension |

## 6. Properties examples

| Concept | Property | Standard |
|---|---|---|
| Human-readable name | `rdfs:label` | Yes |
| Free-text description | `rdfs:comment` | Yes |
| External / business identifier | `dcterms:identifier` | Yes |
| Unit (MWh, m³, °C, Hz, …) | `brick:hasUnit` → QUDT | Yes |
| Aggregation function and interval | `brick:aggregate` | Yes |
| Year built | `brick:yearBuilt` | Yes |
| Electrical phases | `brick:electricalPhases` | Yes |
| Virtual meter flag | `brick:isVirtualMeter` | Yes |
| Timeseries external id (key within `path` in the database) | `ref:hasTimeseriesId` | Yes |
| DB path (schema.table within the database) | `ext:path` | Extension |
| Timeseries kind (`raw` \| `derived`) | `ext:kind` | Extension |
| Derived-ref source list | `ext:sources` | Extension |
| Derived-ref aggregation (`sum` \| `rolling_sum`) | `ext:aggregation` | Extension |
| Reading correction trail timestamp | `ext:recordedAt` | Extension |
| Preferred external reference (multi-source) | `ref:preferred` | Yes (standard `ref-schema`) |
| Allocation factor for virtual meters (on the `feeds` edge) | `ext:flowCoefficient` | Extension |
| Validity start | `ext:validFrom` | Extension |
| Validity end | `ext:validTo` | Extension |
| Device serial number | `ext:serial` | Extension |

## 7. Questions and Decisions

### 7.1 `brick:Site` and the production-area question

**Decision (resolved).** The campus is the single `brick:Site`. Production areas (API, Steriles, OSD, Engineering, …) — what people internally call "sites" — are modelled as `brick:Zone` instances inside each building, not as nested `brick:Site` levels.

This eliminates the "one building, one site" problem from the earlier draft. Buildings that are shared across production areas (e.g. B339 serving both API and Engineering) simply contain multiple zones. No fabricated buildings, no antipatterns in the building list, and every building appears exactly once in the graph.

The hierarchy is now: **Campus (`brick:Site`) → Building (`brick:Building`) → Zone (`brick:Zone`)**.

Most buildings have a single zone and therefore belong to one production area. The handful of split buildings get as many zones as needed. Equipment and meters inside a building can be assigned to a specific zone via `brick:isPartOf` when the distinction matters.

Remaining questions:

- For split buildings like B339, confirm the exact zone breakdown (which parts are API, which are Engineering).
- `621 (I&L)` and `621 (T)` — are these genuinely different zones within B621, or just labelling artefacts?

### 7.2 `brick:Zone`

**Decision (resolved).** `brick:Zone` is a core part of the model. Every building contains at least one zone, representing the production area (API, Steriles, OSD, Engineering, …) that occupies that part of the building. `brick:Zone` is a standard Brick class constrained to be `isPartOf` exactly one `brick:Building`, so a zone is unambiguously "a part of a single building, smaller than the whole."

For the majority of buildings, the single zone is effectively synonymous with the building itself. For shared buildings, multiple zones express the split cleanly without duplicating the building entity.

### 7.3 `ext:System`

`ext:System` represents the installation/discipline grouping inside a building. The layer that EBO uses for system numbers (52 = Vatten, 55 = Kyla, 56 = Värme, …) plus the subsystem code below it (FV1, VP1, KB1, KV1, …). Brick has no class between Building and Equipment for this kind of trade and discipline classification, but could be useful for reporting.

| System | Description (en) | Distinct subsystems |
|---|---|---|
| 52 | Water | KV1, VV1, VVC1, VV2, BRV1, V2, V4, V9, S1, PPD, PRPD |
| 54 | Air | L1 |
| 55 | Cooling | KB1–KB6, KB1_KOLF, KB1_VVS, KM3, CHO2210/11/12, V2, VENT, VKA8, Total |
| 56 | Heating | FV1, VP1, VP2, VP3, VP12, VPU1, VS1, VS2, VS12, VÅ2, VÅ9, Å1, K1, VMM1, VV1 |
| 80 | Outdoor | UTE |
| ÅNGA | Steam | IGELSTA, INFRA_NORR, INFRA_SYD |
| EL | Electricity | (none — meters at the system level) |
| TOTAL | Total | (none) |
| YTA1/2/3 | Solar panel areas | (none) |

Why this matters for reporting. Six of the seven reporting categories map to a single (system, subsystem) tuple: `Kyla` is system 55, `FV` is 56/FV1, `VÅ9` is 56/VÅ9, `Kallvatten` is 52/KV1, `Ånga` is system ÅNGA (or 56/Å1), `EL` is system EL. Only `Kyltornsvatten` has no direct subsystem code. So if `ext:System` exists in the model with both layers, the reporting axis falls out of it almost for free, no substance lookups, no topology walks needed for the bulk of the reports. More about this explained later.

**Decision.** `ext:System` will be adopted with both system and subsystem levels, but **deferred** from the initial TTL conversion. EL meters (276) have 0% subsystem coverage and need manual assignment. In the interim, `ext:mediaType` (see §8) provides the operational grouping axis for reporting.

Remaining questions (deferred):

- How do we handle the PME-only timeseries with no system/subsystem? Substance + meter class as fallback (see 7.7), or accept that they live outside the report machinery?
- Confirm option single class with code properties versus two-class or hierarchy alternatives.

### 7.4 `ext:Device`

`ext:Device` represents the physical hardware that performs measurements at a logical meter location — a specific Schneider unit with a serial number, a manufacturer, a firmware version, and a lifecycle. Brick deliberately does not model devices separately from logical meters (it merges physical and logical into a single Equipment entity), so this is one of the few places we genuinely need an extension.

We need to model devices because:

1. Devices are replaceable more often than logical meters. The meter at `B307.T10` may have had three different physical devices over its lifetime. The logical meter identity (`B307.T10`) must stay stable across those swaps so historical queries don't fragment.
2. Parallel runs, temporary or permanent. During a replacement, two devices may run side-by-side for a calibration period. Sometimes (steam, where sensors can only be replaced once a year) we install multiple devices at the same intake permanently for redundancy. Each device produces its own timeseries. Exactly one is marked `ref:preferred true`. See §7.10.
3. Device-level metadata (serial, manufacturer, firmware) is the only way to answer "which Schneider PM5xxx units need a firmware update" or "which device is still under warranty".

**Modelling: device on the timeseries, not on the meter.** The device connects to the timeseries reference via `ext:producedBy`, not to the meter. This keeps the standard Brick chain (Meter → Sensor → Timeseries) completely untouched. The device lives one level deeper:

```
Meter → hasPoint → Sensor → hasExternalReference → [
    ref:hasTimeseriesId "6:1" ;
    ref:storedAt :PME_SQL ;
    ext:producedBy :device_MZ1812A095 ;
]
```

This is better than the earlier `ext:servedBy` (device on meter) approach because:

- One meter has many timeseries (accumulated energy, delta, power, frequency, rolling sums). The device produces all of them. Linking device to each timeseries reference makes the provenance explicit.
- During a swap, old timeseries refs point to the old device (with `ext:validTo`), new timeseries refs point to the new device (with `ext:validFrom`). No ambiguity about which device produced which data.
- During parallel runs, two timeseries refs on the same sensor, each with its own device, one marked `ref:preferred true`. Clean.
- The standard Brick tree is never touched. `ext:producedBy` is a leaf on the timeseries reference node, invisible to any Brick-only consumer.

**Initial implementation: device defaults to meter identity.** For the first version, every timeseries reference will carry `ext:producedBy` pointing to a device whose ID matches the logical meter name (e.g. meter `B307.T10` → device `B307.T10`). This is a placeholder that keeps the model structurally complete without requiring a full hardware inventory upfront. When actual device data becomes available (serials, manufacturers, swap dates), the placeholder devices get replaced with real ones — one at a time, no schema change needed.

### 7.5 Virtual meters and `ext:flowCoefficient`

In several buildings the energy total is computed today from a hardcoded spreadsheet formula like:

```
B310 = B310.T27 + B310.T28 - B310.T27_12_2 - B310.T28_23_2
     + 0.33 * B311.T29
     + 0.4  * B317.T49 - 0.4 * B317.T49_4_2 - 0.4 * B317.T49_4_3 - …
     + 0.5  * B313.T26S - 0.5 * B313.T26S_2_32 - …
```

The coefficients (`0.4`, `0.33`, `0.5`, …) are not properties of any individual meter. They are weights applied to the net unmetered remainder of a meter tree, used because no real meter exists at the physical split point. The line measured by `B317.T49` serves more than one building, and B310's share of the unmetered remainder is estimated at 0.4. There is no physical meter at the split, so the coefficient stands in for one.

Every time a sub-meter is added or removed, someone has to find every building formula referencing the parent and manually update the term. Miss one and the energy balance silently breaks.

The model. The physical meter hierarchy is captured with standard `brick:hasSubMeter`. For each unmetered split, a virtual meter is created in each receiving building. The virtual meter is a normal `brick:Electrical_Meter` (or equivalent) with `brick:isVirtualMeter true`. The allocation factor lives on the `brick:feeds` **edge** from the real parent to the virtual child as `ext:flowCoefficient` — not on the virtual's sensor. (Earlier drafts placed it on the sensor; that was revised because virtuals in our model carry no sensor and because the coefficient is a property of the split, not of any measurement point.)

```turtle
# Physical topology, standard Brick
:B317_T49
    a               brick:Electrical_Meter ;
    rdfs:label      "B317.T49" ;
    brick:hasPoint  :B317_T49_energy ;
    brick:hasSubMeter  :B317_T49_4_2 ,
                       :B317_T49_4_3 ,
                       :B317_T49_4_4 ,
                       :B317_T49_5_5 .       # …and the rest of the real T49 sub-meters

:B317_T49_energy
    a               brick:Energy_Sensor ;
    brick:hasUnit   unit:KiloW-HR ;
    ref:hasExternalReference  [
        ref:hasTimeseriesId  "317:49" ;       # illustrative PME SourceID:QuantityID
        ref:storedAt         :PME_SQL
    ] .

# B310's virtual share, standard Brick + one extension property on the feeds edge
:B310_T49_virtual
    a                     brick:Electrical_Meter ;
    rdfs:label            "B310 share of B317.T49" ;
    brick:isVirtualMeter  true ;
    brick:isPartOf        :B310 .
    # Virtuals carry no sensor and no own series - they are a model
    # declaration. The DW materializes the value by multiplying the
    # parent's net by ext:flowCoefficient on the feeds edge.

# Allocation factor lives on the feeds relation, not on a sensor.
# Using RDF-star annotations so ext:flowCoefficient attaches to the
# specific edge instance.
<< :B317_T49  brick:feeds  :B310_T49_virtual >>
    ext:flowCoefficient  0.4 .
```

The calculation engine walks `brick:hasSubMeter` to compute the net remainder (`T49 − T49_4_2 − T49_4_3 − …`), follows `brick:feeds` to find the virtual meter in each receiving building, and multiplies by that meter's `ext:flowCoefficient`.

When a real meter is later installed at the physical split, the virtual meter receives a `validTo` date and the real meter takes over with `validFrom`. Historical queries continue to work.

Questions:

- Verify that this is actually the case: estimates are only needed at the end of a line where there is a physical split without meters.

### 7.6 Temporal validity (`ext:validFrom` / `ext:validTo`)

Brick is a snapshot model. Without explicit temporal bounds, the question "what was B307's energy in 2023?" fails as soon as the meter has been moved or replaced, the old state is gone. This is an open issue in the Brick community (issue #447, open since 2022, no consensus). Three positions are debated:

1. Add `validFrom` / `validTo` properties on relationships (the proposal in #447).
2. Version the entire graph at points in time (Gabe Fierro, Brick maintainer).
3. Make temporal qualifiers optional so consumers that don't need history aren't burdened (Erik Paulson).

Our approach: attach a validity interval to any relationship **or entity**, optional and only declared when used.

- On a **relationship** (e.g. `brick:hasSubMeter M0 → M1`): the edge becomes active / inactive at the given dates. Most topology validity lives here.
- On an **entity** (e.g. `brick:Electrical_Meter M1`): the meter point itself came online / was retired. Useful for "M1 was installed 2026-02-01", without needing to decorate every incident edge.
- On a **timeseries reference**: a device's in-service window. The key use case is device replacement — see §7.10 and §9.

All three are optional; omitting them means "always valid during the period of interest."

Questions:

- Manage expectations: Brick temporal validity is beyond current use. Representing changes of direction in flows is not in the realm of Brick.

### 7.7 Substances and water types

Brick has a substance taxonomy (`brick:hasSubstance`) for what flows through equipment: `brick:Hot_Water`, `brick:Chilled_Water`, `brick:Domestic_Water`, `brick:Steam`, `brick:Condenser_Water`, `brick:Potable_Water`, `brick:Makeup_Water`.

With `ext:System` as the primary reporting axis (7.3), substances become a complementary, secondary signal. They are still useful for two cases:

1. Cross-cutting queries that ignore the system grouping: "everything carrying chilled water campus-wide regardless of which system it belongs to".
2. Fallback for the power-quality timeseries and others that have no `ext:System` metadata. Substance + meter class is the only path for those.

Subsystem-to-substance mapping for the EBO-matched meters:

| Subsystem | Substance |
|---|---|
| KB1–KB6, KM3, CHO (chillers) | `brick:Chilled_Water` |
| Kyltorn / KT (cooling tower water) | `brick:Condenser_Water` |
| VV1 (varmvatten) | `brick:Hot_Water` |
| BRV1 (bruksvatten) | `brick:Domestic_Water` |
| Å1 (ånga) | `brick:Steam` |
| VÅ9 (värmeåtervinning) | `brick:Hot_Water` |
| VP1–VP3 (heat pumps) | `brick:Hot_Water` |
| FV1 (district heating, fjärrvärme) | `brick:Hot_Water` |

Same substance, different sources. Notice that VV1, VÅ9, VP1–VP3, and FV1 all carry `brick:Hot_Water`. The substance class only describes what flows, not where it comes from. The (system, subsystem) tuple from 7.3 distinguishes them; substance alone cannot.

**Decision.** Two cases that the earlier draft flagged as needing extensions have been resolved without extensions:

- KV1 (kallvatten) — use `brick:Chilled_Water`. While Brick defines this as mechanically cooled water, the class is the closest standard match and avoids introducing `ext:Cold_Water`. The subsystem code (KV1) distinguishes it from chiller-loop chilled water in practice.
- V2 (sjövatten) — use `brick:Water`. Standard Brick class, no extension needed. The subsystem code (V2) distinguishes it from other water types.

No extensions required for substances. The `ext:Lake_Water` and `ext:Cold_Water` extensions proposed in the earlier draft are dropped.

### 7.8 Reporting categories and how the model supports them

**On hold.** The reporting mapping depends on how equipment and system/subsystem are resolved in the model. Revisit once those decisions are made.

For reference, the seven reporting categories are: EL, Kyla, FV, VÅ9, Ånga, Kallvatten, Kyltornsvatten.

### 7.9 Non-building infrastructure

The campus has entities that are not production buildings but carry meters. From the data, these fall into four categories.

**1. Campus-level intake meters.** These are the boundary points where utilities enter the campus from external suppliers. They do not belong to any building — they measure what flows into the site as a whole.

| Entity | Meters | What it is |
|---|---|---|
| B600N | KV1_VM20, Å1_VMM71_E | Gärtuna water and steam intake, north pumphouse |
| B600S | KV1_VM20, Å1_VMM71_E | Gärtuna water and steam intake, south pumphouse |
| B390 | KV1_VM25_V, S1_VM20_V, Å1_VMM70_E | Snäckviken water intake, spillwater, steam main |
| B660 | H23-1, H3-1 | Gärtuna electricity intake (ställverk) |
| B324 | H3, H4-1, T14 | Snäckviken electricity intake (elpanna) |

These are modelled as `brick:Meter` instances hanging directly off the campus `brick:Site` via `brick:meters`. They are not buildings and do not get a `brick:Building` entity. B600N/B600S are physical pumphouses but their purpose is purely intake infrastructure — they have no production zone. B390 and B600 are aggregate calculation points, not physical locations; their meters roll up building-level data for campus totals.

**2. Acturum (utility/technical rooms).** Four entities labelled "Acturum" in the formula data: B212, B229, B230, B409. These are physical structures housing utility infrastructure (cooling centrals, sjövatten pumps) but are not production buildings with a zone like API or Engineering.

| Entity | Meters | What it is |
|---|---|---|
| B212 | KB5, V2_VM51 | Cooling and lake water |
| B229 | V2_VM51 | Lake water |
| B230 | V2_VM51 | Lake water |
| B409 | KV1_VM21, V2_GF4 | Kylcentral — water intake, lake water cooling |

These are modelled as `brick:Building` with zone "Acturum". They are real physical structures with meters. Whether "Acturum" should be a proper zone alongside API, Engineering, etc. or a separate classification is an open question, but for now it works as a zone label.

**3. External parties.** Two external consumers of campus lake water appear in the sjövatten data:

| Entity | Meter | What it is |
|---|---|---|
| KRINGLAN | TE-52-V2-GF4:1 | Telge Nät cooling (Kringlan) |
| SCANIA | TE-52-V2-SCANIA | Scania lake water |

These are not AZ entities. They are modelled as external `ref:Database` sources or as separate `brick:Site` instances outside the campus, referenced via `brick:feeds` from the shared lake water infrastructure. Their meters are manual readings.

**4. Other non-building infrastructure.** From the source data but not yet in our meter tables:

| Concept | Brick class | Status |
|---|---|---|
| Solar panel areas (YTA1, YTA2, YTA3) | `brick:Photovoltaic_Array` | No meters in current data, listed in building data as SOLPARK |
| Parking / EV charging | `brick:Parking_Lot` / `brick:Electric_Vehicle_Charging_Station` | One meter (B653.T17-A7 = "Parkering gympahall"), low priority |
| Weather stations | `brick:Weather_Station` | Two in DATALOG (B390.MS01_GT41, B600.MS01_GT41), not yet in our meter tables |

All hang directly off the campus `brick:Site` as siblings of buildings. No extensions needed — standard Brick classes cover every case.

**5. Supplier meters (Telge Nät).** 27 TN district heating and steam meters (101172, 101192, etc.) have no building assignment. These are external reference meters, not physical infrastructure on the campus. They attach to AZ intake meters as additional `ref:hasExternalReference` entries per §7.10. They do not need a place in the spatial hierarchy.

Open decisions:

**B600N/B600S: buildings or equipment?** They are physical pumphouses — real structures with walls and a roof. But they exist solely to house intake infrastructure (water mains, steam mains), not production activity. Two options:

- Model as `brick:Building` with no zone. Simple, honest ("it's a building"), and consistent with how the source data treats them. The absence of a zone already distinguishes them from production buildings. Meters hang off them normally. Recommended.
- Model as `brick:Equipment` at campus level. Treats them as infrastructure rather than buildings, which is closer to their function. But then B600N.KV1_VM20 has no building parent, which breaks any query that walks the Building → Meter path. Not recommended unless there's a reason to exclude them from building counts.

**Acturum as a zone.** "Acturum" appears consistently for B212, B229, B230, and B409 across KYLA, SJÖVATTEN, and KALLVATTEN sheets. These four buildings house shared utility infrastructure (cooling centrals, lake water pumps, water intakes) that serves the wider campus rather than one production area. Modelling options:

- Keep "Acturum" as a zone alongside API, Engineering, etc. Pragmatic — the data already uses it consistently, queries for "all Acturum buildings" work out of the box, and it groups the utility infrastructure naturally. The name is established internally. Recommended.
- Replace with "Infrastructure" or similar. Clearer in English, but loses the term people already use. No practical benefit.
- Don't assign a zone at all. The four buildings become orphans in zone-based queries. Not recommended.

**Solar park and weather stations in v1.** Both are standard Brick with no extensions needed, but neither is critical for the energy reporting use case.

- Weather stations (B390.MS01_GT41 at Snäckviken, B600.MS01_GT41 at Gärtuna). Both are active in Snowflake with recent data. Include in v1 — temperature data is essential for normalising energy consumption (degree-day calculations) and the cost is just two `brick:Weather_Station` entities at campus level with `brick:Temperature_Sensor` points. No reason to defer.
- Solar park (SOLPARK / YTA1, YTA2, YTA3). Four meters exist (SOLPARK.TOTAL_ENERGY, YTA1/2/3_ENERGY), all MWh. Included as `brick:Photovoltaic_Array` at campus level with `brick:Electrical_Meter` and `brick:Energy_Sensor` + `unit:MegaW-HR`.
- Parking / EV charging. One meter exists (B653.T17-A7, "Parkering gympahall") but it's already captured as a sub-meter of B653. No separate infrastructure entity needed for v1.

### 7.10 Manual references and external meters (intake meters, supplier comparison, redundancy)

There is a need to control suppliers: comparing our own metering to what the supplier bills or reports. We also fold in two related cases here: manual monthly readings from invoices, and redundant devices on a single meter (steam, where sensors can only be replaced once a year so a backup is needed).

All of these collapse to the same pattern: one logical meter at the intake, with multiple `ref:hasExternalReference` entries on its sensor, one per data source. Exactly one is marked `ref:preferred true`. Reports filter on that flag. No double counting, by construction.

`ref:preferred` is standard Brick (`ref-schema` PR #4, May 2022). A SHACL shape (`ref:PreferredShape`) enforces a maximum of one preferred per entity, so the no-double-counting rule is structurally guaranteed.

**Confirmed from data.** All three sub-cases appear in the real meter landscape:

1. Supplier meters (Telge Nät). 27 TN district heating and steam meters (IDs like 101172, 101192, 101543-0, etc.) from TN consumption reports. These cover both Snäckviken (8 meters) and Gärtuna (19 meters). In the model, each attaches as an additional `ref:hasExternalReference` on the corresponding AZ intake meter's sensor, with `ref:storedAt` pointing to the TN report source. AZ's own PME timeseries carries `ref:preferred true`; the TN reference is for reconciliation only.

2. Manual readings. Meters read manually from physical displays or invoices, not polled by PME. Examples from the data:
   - `B656.KV1_VM21` — manually read water meter at Gärtuna (source: "Mätaravläsning driften").
   - `B304-52-V2-AW026` — lake water meter at Snäckviken (source: "Mejl energigruppen").
   - `B612.KB1_PKYL` — cooling meter at Gärtuna (source: "Vista Produktion").
   - TN intake water meters (`B310-KV1-VM21_1`, `B334-KV1-VM21_1`, `B409-KV1-VM21_1`) — serial-based IDs from TN, read manually.
   - Spillwater meters (`B390.S1_VM20_V`, `B600.S1_VM20`) — wastewater, manual.
   These attach as `ref:hasExternalReference` with `ref:storedAt` pointing to a manual-entries database and `brick:aggregate` set to the reading frequency (typically monthly).

3. Meter replacements and renames. `B616.Å1_VM71` was renamed to `B616.Å1_VMM71_E` — all historical data migrated to the new timeseries ID, old ID pending deletion from SQL. In the model, the logical meter stays the same; the old `ref:hasExternalReference` gets a `validTo` date, the new one gets a `validFrom`. Six other decommissioned meters follow the same pattern (B641.KV1_VM → B641.KV1_VM21, B653.KV1_VM21_2 → B653.KV1_VM22_V, etc.).

The "exception case" from the earlier draft (two physically distinct meters at the same intake, e.g. supplier revenue meter AND AZ check meter as separate hardware) has not been observed in the data. All real cases collapse to the single-meter, multiple-references pattern.

Net new extensions: zero.

Example. District heating intake at Gärtuna with AZ's own PME timeseries and a TN supplier reference:

```turtle
:B600N_Å1_intake
    a               brick:Thermal_Power_Meter ;
    rdfs:label      "Steam intake north — Gärtuna" ;
    ext:mediaType   :media_ÅNGA ;
    brick:hasSubstance  brick:Steam ;
    brick:hasPoint  :B600N_Å1_energy .

:B600N_Å1_energy
    a              brick:Energy_Sensor ;
    brick:hasUnit  unit:MegaW-HR ;

    # AZ internal (preferred for reporting)
    ref:hasExternalReference  [
        a                    ref:TimeseriesReference ;
        ref:hasTimeseriesId  "B600N.Å1_VMM71_E" ;
        ref:storedAt         :PME_SQL ;
        ref:preferred        true
    ] ,

    # Telge Nät supplier report (for reconciliation)
    [
        a                    ref:TimeseriesReference ;
        ref:hasTimeseriesId  "101192" ;
        ref:storedAt         :TN_FV_rapport
    ] .
```

### 7.11 Management for bad data

Failures in meters can take days to correct, sometimes months. In extreme cases, like steam, sensors are only replaced once a year. We need a discipline.

Three options:

- Patching with fabricated data. Not recommended. It pollutes the historical record with data consumers cannot tell from real readings.
- Nulling the data and its derivatives for the bad period (recommended). Mark the period as invalid so reports skip it. The meter exists, the gap exists, the truth is honest. Two mechanisms cover this, both already in the proposal:
  - `ext:validFrom` / `ext:validTo` on the timeseries reference (§7.6 + §7.4). When a device starts emitting bad data on date X, set `ext:validTo "X"` on its `ref:hasExternalReference`. When fixed or replaced, add a new timeseries reference with `ext:validFrom` and the new device via `ext:producedBy`. Best for human-marked "we know this period was bad" cases.
  - `brick:Fault_Status` as a point on the meter. Standard Brick, no extension. A fault status sensor records when the meter is faulted. Reports correlate with the energy timeseries and exclude fault-true periods. Use this when the meter has automated fault detection.
- Implementing redundancy at critical or hard-to-replace intakes (recommended). Multiple devices serving one logical meter, all running. When the active fails, flip `ref:preferred` to the backup. See §7.10 for the full pattern. Same machinery, no new extension.

Net new extensions: zero. `brick:Fault_Status` is standard Brick. The validity properties and `ref:preferred` are already covered.

Questions:

- Confirm the policy: nulling preferred over patching. Hard rule, not a guideline.
- Which intakes are critical enough to justify a permanent backup? Steam is obvious. Others?
- Does Schneider EMS produce a fault signal we can ingest as `brick:Fault_Status`, or do we have to mark fault periods manually via validity intervals?
- Who owns the operational task of recording "this meter went bad on date X" in the graph when a failure is discovered after the fact?

## 8. Extension summary

If every extension recommended in 7 + 9 is adopted, the model carries the following non-Brick concepts:

| Extension | Kind | Purpose |
|---|---|---|
| `ext:Device` | Class | Physical hardware identity, separate from logical meter |
| `ext:producedBy` | Relationship (on timeseries ref) | Timeseries reference → physical device that produced the data |
| `ext:serial` | Property | Device serial number (or borrow `sdo:serialNumber`) |
| `ext:manufacturer` | Property | Device manufacturer (or borrow `sdo:manufacturer`) |
| `ext:flowCoefficient` | Property (on the `feeds` edge, RDF-star) | Allocation factor for a share split to a virtual meter |
| `ext:validFrom` / `ext:validTo` | Properties on relationships or entities (RDF-star on edges) | Temporal validity, aligned with Brick issue #447 |
| `ext:MediaType` | Class | Operational media category (EL, KYLA, VÄRME, KALLVATTEN, etc.) |
| `ext:mediaType` | Property (on meter) | Meter → `ext:MediaType` instance for arbitrary grouping |
| `ext:path` | Property (on timeseries ref) | `schema.table` within a database — completes the addressing triple (see §9) |
| `ext:kind` | Property (on timeseries ref) | `raw` (points at upstream data) or `derived` (declaration, materialized by the DW) |
| `ext:sources` | Property (on derived ref) | List of source timeseries ids aggregated by the derived ref |
| `ext:aggregation` | Property (on derived ref) | Aggregation rule: `sum` or `rolling_sum` (see §9) |
| `ext:recordedAt` | Property (on reading) | Timestamp a value was entered; distinct from the reading's period `timestamp`. Enables correction trails for Avläsning-style inputs |
| `ext:System` | Class | Installation discipline and subsystem (Vatten / Kyla / Värme) — deferred |

## 9. Addressing and derived timeseries

Decisions made while building the reference site (Abbey Road) that aren't in the original draft above.

### 9.1 Addressing triple on timeseries references

Every timeseries reference has two levels of identity:

- **Ontology-level id** — the node's own IRI, emitted as `dcterms:identifier` when appropriate. Example: `M6:h`.
- **Upstream key** — where to find the data outside the ontology. Captured by the triple:
  - `ref:storedAt` → `ref:Database` *(e.g. `PME_SQL`)*
  - `ext:path` — `schema.table` within that database *(e.g. `ingest.hourly`)*
  - `ref:hasTimeseriesId` — row/column key within that table *(e.g. `"631:129"`)*

The triple is required for raw refs and absent on derived refs.

### 9.2 Raw vs. derived references

A `ref:TimeseriesReference` is one of two kinds, distinguished by `ext:kind`:

- **`raw`** — points at pre-existing upstream data via the addressing triple. May carry `ext:producedBy` if the producing device is known. Most refs are raw.
- **`derived`** — a declaration. Carries `ext:sources` (a list of other ts-ref ids) and `ext:aggregation` (the rule). No addressing triple; the DW layer reads this declaration and materializes the series on demand (typically into a conventional `marts.derived_series` view keyed by the ontology id).

The two shapes are disjoint. Validators enforce this.

### 9.3 Aggregation vocabulary

Two operators only:

- **`sum`** — combine sources at the same timestep. Example use: building-level rollup `B1.office:m = M1:m + M2:m + M3:m` per month.
- **`rolling_sum`** — accumulate per-period deltas over time, respecting each source's validity. Counter semantics fall out: a stitched "as if never replaced" counter for a meter that saw a device swap is `rolling_sum` over the device-scoped refs.

Additional operators (`weighted_sum`, `diff`, rolling aggregations beyond sum) are deferred — the two we have cover zone rollups and device replacement. Rollups over time are a special case of derived, not a separate category.

### 9.4 Device replacement pattern

When a device at a meter point is replaced mid-period (physical swap, logical meter identity stable):

1. The old `ref:TimeseriesReference` has its `ext:validTo` set to the swap date; `ext:producedBy` still points at the retired device.
2. A new `ref:TimeseriesReference` is added with `ext:validFrom` on the swap date and the new device.
3. A single derived ref, `ext:kind = "derived"`, `ext:aggregation = "rolling_sum"`, `ext:sources = [old, new]`, sits alongside. This is the canonical series consumers read (`ref:preferred true`). The DW materializes it.

Abbey Road demonstrates this on `M6`: `M6:h.A` (device A, Jan 1 – Feb 10), `M6:h.B` (device B, Feb 10 – Mar 1), `M6:h` (derived, preferred, rolling_sum).

### 9.5 Correction trails on readings

Readings carry an optional `ext:recordedAt`. Two rows sharing `(timeseries_id, timestamp)` but differing in `recordedAt` form a correction trail; the latest `recordedAt` wins for reporting. Used for backdated Avläsning corrections (a January monthly reading re-entered in March).

This is orthogonal to the §7.11 "nulling" discipline: `recordedAt` is for corrections that overwrite a previously accepted value; nulling via `ext:validTo` is for marking periods as invalid.
