-- Base views for topological net calculations.
--
-- Three layered views, built once on connection open:
--
--   measured_flow : per-meter delta kWh, derived from the preferred
--                   counter timeseries via LAG diff. Works with any
--                   granularity (hourly, daily, monthly). Only real
--                   meters with a counter ref appear here.
--
--   meter_flow    : measured_flow union'd with flow synthesized for
--                   virtual meters via feeds edges. A virtual child V
--                   fed by parent P with coefficient k receives
--                   k × (flow(P) - Σ hasSubMeter children of P). The
--                   aggregator case (POOL ← I1+I2+I3, each k=1.0) and
--                   the share case (M11 → V1/V2 at 0.7/0.3) fall out
--                   of the same rule — aggregators accumulate across
--                   multiple incoming feeds rows that a final GROUP BY
--                   sums.
--
--   meter_net     : each meter's OWN consumption = flow(M) − Σ flow(c)
--                   for every child c (hasSubMeter or feeds). Attached
--                   to a single target (campus/building/zone) via
--                   meter_measures. Downstream aggregations consume
--                   this view.
--
-- Temporal relations
-- ------------------
-- Every meter_relations row carries a [valid_from, valid_to) interval
-- (NULLs = unbounded). A relation contributes to flow calculations at
-- timestamp t only while t is inside that window, so a parent/child
-- flip like `A→B (valid_to=T)` + `B→A (valid_from=T)` fires exactly one
-- edge at any given t instead of both. The temporal predicate is
-- reused across every join on meter_relations below.

CREATE OR REPLACE VIEW measured_flow AS
SELECT
    s.meter_id,
    r.timestamp,
    r.value - LAG(r.value) OVER (
        PARTITION BY r.timeseries_id ORDER BY r.timestamp
    ) AS delta_kwh
FROM readings r
JOIN timeseries_refs tr
    ON tr.timeseries_id = r.timeseries_id
   AND tr.preferred = TRUE
   AND tr.reading_type = 'counter'
JOIN sensors s ON s.sensor_id = tr.sensor_id
QUALIFY delta_kwh IS NOT NULL;

CREATE OR REPLACE VIEW meter_flow AS
WITH RECURSIVE
-- Σ hasSubMeter children's measured flow, per real parent+hour.
-- Used by the recursive term to strip out the already-metered portion
-- of a parent's flow before sharing the remainder to virtual children.
sub_total AS (
    SELECT
        r.parent_meter_id,
        mf.timestamp,
        SUM(mf.delta_kwh) AS total
    FROM meter_relations r
    JOIN measured_flow mf ON mf.meter_id = r.child_meter_id
    WHERE r.relation_type = 'hasSubMeter'
      AND (r.valid_from IS NULL OR r.valid_from <= mf.timestamp)
      AND (r.valid_to   IS NULL OR r.valid_to   >  mf.timestamp)
    GROUP BY r.parent_meter_id, mf.timestamp
),
flow(meter_id, timestamp, delta_kwh, hop) AS (
    -- Base: measured real meters.
    SELECT meter_id, timestamp, delta_kwh, 0 AS hop FROM measured_flow

    UNION ALL

    -- Recurse: feed each `feeds` child a share of the parent residual.
    -- `hop < 10` is a defensive cap; Abbey Road needs at most 2 hops
    -- (POOL → M0 side of the graph has no feeds-chain virtual depth;
    -- M12 → V4 → M9 side stops at 1 feeds hop).
    SELECT
        rel.child_meter_id AS meter_id,
        parent.timestamp,
        rel.flow_coefficient * (
            parent.delta_kwh - COALESCE(subs.total, 0)
        ) AS delta_kwh,
        parent.hop + 1 AS hop
    FROM flow parent
    JOIN meter_relations rel
        ON rel.parent_meter_id = parent.meter_id
       AND rel.relation_type = 'feeds'
       AND (rel.valid_from IS NULL OR rel.valid_from <= parent.timestamp)
       AND (rel.valid_to   IS NULL OR rel.valid_to   >  parent.timestamp)
    LEFT JOIN sub_total subs
        ON subs.parent_meter_id = parent.meter_id
       AND subs.timestamp = parent.timestamp
    WHERE parent.hop < 10
)
SELECT
    meter_id,
    timestamp,
    SUM(delta_kwh) AS delta_kwh
FROM flow
GROUP BY meter_id, timestamp;

CREATE OR REPLACE VIEW meter_net AS
-- Own consumption per meter:
--   net(M) = (flow(M) − Σ hasSubMeter flow) × (1 − Σ outgoing feeds k)
--
-- A feeds edge is an outbound delivery of k × parent.residual, not a
-- measurement of a child's own draw — so feeds children do NOT
-- participate in the child-sum like hasSubMeter children do. Instead
-- they drain the parent's residual in proportion to their coefficient.
--
-- Examples:
--   intake (I1 → POOL, k=1.0): net(I1) = (flow(I1) - 0) × 0 = 0
--   share point (M11 → V1/V2, 0.7+0.3): net(M11) = flow(M11) × 0 = 0
--   partial share (k<1): the unshared fraction stays at M as its own
--   no feeds children: net(M) = flow(M) − Σ hasSubMeter flow
--
-- Both hs_total and feeds_k_sum are per-timestamp: each filters
-- meter_relations by the edge's validity window so temporal flips
-- (A→B then B→A) and retired feeds edges don't double-apply.
WITH
hs_total AS (
    SELECT
        r.parent_meter_id,
        mf.timestamp,
        SUM(mf.delta_kwh) AS total
    FROM meter_relations r
    JOIN meter_flow mf ON mf.meter_id = r.child_meter_id
    WHERE r.relation_type = 'hasSubMeter'
      AND (r.valid_from IS NULL OR r.valid_from <= mf.timestamp)
      AND (r.valid_to   IS NULL OR r.valid_to   >  mf.timestamp)
    GROUP BY r.parent_meter_id, mf.timestamp
),
feeds_k_sum AS (
    SELECT
        r.parent_meter_id,
        mf.timestamp,
        SUM(r.flow_coefficient) AS total_k
    FROM meter_relations r
    JOIN meter_flow mf ON mf.meter_id = r.parent_meter_id
    WHERE r.relation_type = 'feeds'
      AND (r.valid_from IS NULL OR r.valid_from <= mf.timestamp)
      AND (r.valid_to   IS NULL OR r.valid_to   >  mf.timestamp)
    GROUP BY r.parent_meter_id, mf.timestamp
)
SELECT
    mf.meter_id,
    mf.timestamp,
    (mf.delta_kwh - COALESCE(hs.total, 0))
        * (1 - COALESCE(fk.total_k, 0)) AS net_kwh
FROM meter_flow mf
LEFT JOIN hs_total hs
    ON hs.parent_meter_id = mf.meter_id
   AND hs.timestamp = mf.timestamp
LEFT JOIN feeds_k_sum fk
    ON fk.parent_meter_id = mf.meter_id
   AND fk.timestamp = mf.timestamp;
