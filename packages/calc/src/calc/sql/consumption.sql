-- Net consumption at three roll-up levels: zone, building, campus.
--
-- Each meter is assigned to exactly one target via `meter_measures`
-- (zone, building, or campus). To answer "what did building X consume"
-- we also need to climb zone → building, because a meter on a zone
-- contributes to that zone's building total. Campus totals are
-- everything — zone-targeted, building-targeted, and campus-targeted
-- meters under that campus.
--
-- Output: one row per (level, target_id, period).
--   level      ∈ 'zone' | 'building' | 'campus'
--   target_id  = zone_id | building_id | campus_id
--   target_name = friendly name from the corresponding table
--   net_kwh    = net consumption per period summed across all
--                contributing meters
--
-- Edit this query live in the app to experiment; the file on disk is
-- the canonical starting point and your edits are session-only.

WITH attributed AS (
    -- Each meter's hourly net plus the chain up to campus.
    SELECT
        mn.timestamp,
        mn.net_kwh,
        mm.target_kind,
        mm.target_id,
        CASE
            WHEN mm.target_kind = 'building' THEN mm.target_id
            WHEN mm.target_kind = 'zone'     THEN z.building_id
        END AS building_id,
        CASE
            WHEN mm.target_kind = 'campus'   THEN mm.target_id
            WHEN mm.target_kind = 'building' THEN b_direct.campus_id
            WHEN mm.target_kind = 'zone'     THEN b_from_zone.campus_id
        END AS campus_id
    FROM meter_net mn
    JOIN meter_measures mm       ON mm.meter_id = mn.meter_id
                                AND (mm.valid_from IS NULL OR mm.valid_from <= mn.timestamp)
                                AND (mm.valid_to   IS NULL OR mm.valid_to   >  mn.timestamp)
    LEFT JOIN zones z            ON mm.target_kind = 'zone'
                                AND z.zone_id = mm.target_id
    LEFT JOIN buildings b_direct ON mm.target_kind = 'building'
                                AND b_direct.building_id = mm.target_id
    LEFT JOIN buildings b_from_zone
                                 ON b_from_zone.building_id = z.building_id
)
SELECT 'zone' AS level, z.zone_id AS target_id, z.name AS target_name,
       a.timestamp, SUM(a.net_kwh) AS net_kwh
FROM attributed a
JOIN zones z ON z.zone_id = a.target_id
WHERE a.target_kind = 'zone'
GROUP BY z.zone_id, z.name, a.timestamp

UNION ALL

SELECT 'building', b.building_id, b.name, a.timestamp, SUM(a.net_kwh)
FROM attributed a
JOIN buildings b ON b.building_id = a.building_id
WHERE a.building_id IS NOT NULL
GROUP BY b.building_id, b.name, a.timestamp

UNION ALL

SELECT 'campus', c.campus_id, c.name, a.timestamp, SUM(a.net_kwh)
FROM attributed a
JOIN campuses c ON c.campus_id = a.campus_id
WHERE a.campus_id IS NOT NULL
GROUP BY c.campus_id, c.name, a.timestamp

ORDER BY timestamp, level, target_id;
