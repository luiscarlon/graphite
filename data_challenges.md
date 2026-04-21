# Data quality issues

# Building calculations don't add up
  (double-counted meters, missing meters, fudge coefficients that mask
   real gaps — the spreadsheet totals are plausible but not reproducible)
  → b611_negative_consumption_artifact   (B611 kyla = −20.88 MWh Jan 2026;
    a pool of 3 inputs has 2 dead, Excel produces a negative bill,
    topology matches Excel exactly — physically nonsensical)
    gartuna/annotations.csv

# How buildings are accounted for is implied by formulas, not written down
  (and the formulas are lossy — you can't always tell a real subtraction
   from a shortcut, a parallel feed from a series one, or a legitimate
   shared meter from a bookkeeping double-count)
  → B615_B642_independent   (PDF drawing says series, Excel says parallel)
  → B661_role_merge         (PDF labels VS1, Excel labels VP1, same meter)
  → B600NS_parallel         (naming convention wrongly inferred parent→child)
    gartuna/annotations.csv

# The same building has three different "correct" consumption numbers
  (the Excel report, the live meter, and what the topology computes from
   scratch — when they disagree there's no rule for who wins)
  → b658_excel_zero_meter_live   (Excel cache = 0, Snowflake live stream =
    10-12 MWh/month of real cooling)
  → B833_61_offline         (topology more accurate than Excel; Excel reads
    a frozen counter and misses 23 MWh of post-Feb-19 consumption)
    gartuna/annotations.csv

# Excel does arbitrary accounting the ontology can't reproduce faithfully
  (the spreadsheet uses allocation shortcuts that don't correspond to any
   physical reality — coefficients, literal month constants, fractional
   splits applied differently to the same pair of meters depending on
   which row you're in. The ontology represents the real wiring, not the
   accountant's bookkeeping, and can't close these gaps without adopting
   the same arbitrary rules)
  → b612_641_fractional_subtraction   (same pair of meters subtracted at
    k=0.9 from one building and k=0.1 from another — an allocation rule,
    not a physical split)
  → B634_power_to_energy    (kW reading "converted" to MWh via ×24×31/1000:
    a literal 31-day month baked into the coefficient for every month
    of the year)
    gartuna/annotations.csv

# Rollovers, swaps, dropouts, and glitches all look the same in raw data
  (and they each need different handling — we currently handle them
   after the fact, per-meter, by hand)
  → B611_T1_rollover        (counter rollover at 9,993,343 — expected)
  → B616_swap               (device replaced, counter jumped 19693 → 1934)
  → B642_72_glitch          (counter dropped 25231 → 10890 for 3 days then
    reverted — register glitch, not a real event)
  → B600S_offline           (froze Jan 17, reset to 0 Feb 2 — looks like
    a rollover, is actually a dying meter)
    gartuna/annotations.csv

# Some meters only report every other day but get used in daily sums
  (and in monthly sums when the window falls wrong — the net for those
   buildings is half-right at best, and nothing warns you)
  → sparse_bidaily_sensors   (campus-level annotation documenting the pattern)
  → b833_negative_sparse    (B833.KB1_GF4: 15 readings in Jan, 16 in Feb)
  → b641_negative_sparse    (B612.KB1_PKYL: 31 readings over 59 days,
    zero delta on every recorded day)
    gartuna/annotations.csv

# Readings that span month-end get assigned to whichever month logged them
  (so a meter that rolls up its counter on the 1st credits 2 days of
   December to January — month-over-month charts look noisier than reality)
  → snv_el_B330_T65_swap    (swap 2026-01-04 → −3728 kWh drift vs Excel,
    flagged as "stitch-boundary timing offset")
  → snv_el_B337_T43_swap    (swap 2026-01-29 → −11023 kWh drift vs Excel)
    snackviken/annotations.csv

# We can't track how the building got wired up the way it is today
  (meters get added, moved, retired, swapped — and there's no history
   of these changes anywhere we can query)
  → B616_swap               (meter replaced 2025-11-05, no history record
    other than this annotation)
  → b642_vmm72_reset_refix  (offline + swap on same meter, originally
    mis-patched, caught five months later)
    gartuna/annotations.csv

# Nobody notices when meters are added, swapped, or die
  (until the monthly reconciliation fails weeks later; no proactive alert
   that a new meter appeared or an existing one stopped)
  → B613_dead               (frozen since 2025-03-12, caught at reconciliation)
  → B641_dead  /  B841_dead (at zero for entire observation window)
  → B658_offline            (reset to 0 in Feb 2026 — only noticed because
    Excel still showed Feb = 0)
    gartuna/annotations.csv

# The same meter has different names in different systems
  (Excel calls it one thing, the BMS calls it another, the PDF drawing
   a third — matching them is manual and occasionally wrong, which
   quietly mis-attributes consumption to the wrong building)
  → el_t4_strux_only        (B611.T4-A3/C1/C4 in Excel + STRUX, absent
    from BMS — created a 46 GWh Excel gap for B611)
  → feedback_crosswalk_prefer_e_variant
                            (<id>_E vs <id> as two separate Snowflake
    sensors; wrong choice cost ~250 MWh/month on SNV värme)
  → snv_el_strux_only_B313_T26S   (Ställverk summary: in STRUX, not in BMS)

# We guess when meters break instead of asking the system
  (the EMS already knows when a device went offline or a breaker tripped,
   we just aren't reading that log — so outage dates are inferred from
   flat readings with a few days of slack)
  → B833_offline, B600S_offline, B658_offline
                            (all valid_from dates inferred from when the
    counter went flat, not from the EMS's own device-offline event log)

# How we mitigate all of this

# The ontology is decoupled from any one source system
  Meters, sensors, relations, readings, and annotations describe physical
  and logical reality in vendor-neutral terms. The EMS could be Schneider
  today and Honeywell tomorrow and the ontology wouldn't change. Source
  specificity lives only at the ingestion boundary — the timeseries layer
  points at whatever database holds the current data, hardware identity
  is tracked separately from logical meters, and every downstream consumer
  sees the same shape regardless of who produced the data.

# Excel is the source of truth (until proven otherwise), and every disagreement with it is classified
  (mitigates: building calculations don't add up)
  For each (building, media, month) we compare the ontology's bottom-up
  sum against Excel's cached value and either match it or tag the diff
  with a documented reason. Unclassified disagreements block ship. Silent
  drift becomes visible state.

# Topology is an explicit graph with provenance on every edge
  (mitigates: how buildings are accounted for is implied by formulas)
  Relations are reconstructed from several independent sources — physical
  drawings, accounting formulas, naming convention, and conservation
  residuals in the readings — and merged with conflict detection. Every
  edge records which source proposed it, so "why is this meter a child of
  that one" has a traceable answer. Implied becomes explicit.

# Disagreements between sources are surfaced, not adjudicated silently
  (mitigates: same building has three different "correct" numbers)
  When the spreadsheet, the live meter, and the reconstructed topology
  disagree, we don't pick a winner silently. The divergence is recorded,
  tagged (stale cache, frozen counter, accounting bug, etc.), and shown
  side-by-side in the UI. You can always see what we trusted and why.

# Accounting lives in its own layer, separate from physical topology
  (mitigates: Excel does arbitrary accounting we can't reproduce)
  Spreadsheet formulas — fractional subtractions, literal month constants,
  cross-building pool splits — are preserved alongside the ontology as
  auditable documentation but don't pollute the physical graph. Where a
  rule can be expressed honestly (constant-coefficient splits), we encode
  it. Where it can't, we accept the residual and label it. The ontology
  stays physically honest; the arbitrary stays quarantined.

# Timeseries are segmented explicitly, raw data is never modified
  (mitigates: rollovers, swaps, dropouts, glitches all look the same)
  Each counter event — rollover, device swap, outage, glitch — is
  classified and becomes its own segment in the timeseries layer, stitched
  into a smooth canonical series. A swap produces two segments; a glitch
  produces a validity-window split; an offline parent with live children
  can be patched from them. Annotations explain what happened. The raw
  source data is never overwritten.

# Sparse-sensor failures are visible but not structurally fixed
  (mitigates: some meters only report every other day — partial)
  Bi-daily cadence is flagged at campus level and affected buildings are
  tagged in the reconciliation, so their "wrong at daily, half-right at
  monthly" behaviour is documented rather than silent. A minimum-resolution
  primitive that refuses to emit finer-than-cadence nets is on the follow-up
  list.

# Month-boundary effects are reduced, not eliminated
  (mitigates: readings that span month-end get misattributed — partial)
  Monthly deltas are computed against the full month window rather than
  summed from daily rollups, which captures the boundary day cleanly. When
  a swap happens inside a month the residual noise is flagged as an
  annotation rather than swept aside.

# Validity windows plus separate device identity capture hardware history
  (mitigates: can't track how the building got wired up today — partial)
  Timeseries segments carry their own validity period; physical devices
  are tracked independently of logical meters, so a swap means the logical
  meter persists across a hardware change and the history is in the data
  model, not just prose. Still missing: a cross-site topology-change log
  that's queryable at scale; today it's reconstructable per-meter.

# An analyst-in-the-loop process keeps the ontology current
  (mitigates: nobody notices when meters are added, swapped, or die — partial)
  The reconciliation is explicitly not run-and-done. Every update forces
  a review: new conservation residuals, candidate counter events, and new
  accounting disagreements all require classification before the workstream
  ships. New and dead meters surface as crosswalk mismatches. Caught by
  process rather than by proactive alerting; making it proactive is on the
  follow-up list.

# One canonical ID reconciliation artifact per workstream
  (mitigates: same meter has different names in different systems)
  A single crosswalk ties the meter's identity across every source system
  (spreadsheet, BMS, drawing, etc.) with evidence for each mapping and a
  confidence level. Fuzzy matching follows a documented procedure rather
  than being ad-hoc. Recurring surprises get promoted to persistent rules
  so the next workstream inherits them.

# Followup
