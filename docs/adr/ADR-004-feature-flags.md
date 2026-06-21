# ADR-004: Feature Flags — Separate Table vs Extension of Experiments

## Status
Accepted

## Context

The platform needs feature flag management: kill switches, gradual rollout
(0% → 100%), targeting by segment, and independent of A/B experiments.

Feature flags and A/B experiments share some concepts:
- Variant assignment (deterministic bucketing by user_id)
- Traffic percentage
- Segments/targeting

But they differ in critical ways:
- Flags are ON/OFF (boolean) or variant (multi-way), not statistical tests
- Flags have no "end date" — they are persistent toggles
- Flags have a kill switch (instant off for all users)
- Flags change independently of experiment lifecycle
- Flags may have 100% rollout (everyone gets treatment) — experiments by
  definition split traffic

The existing `experiments` table has: status (DRAFT/RUNNING/PAUSED/COMPLETED),
started_at, ended_at, traffic_percentage, mutex_group_id. It is designed for
time-boxed statistical tests.

## Decision

**Feature flags are a separate entity** with its own table `feature_flags`
and `flag_rules`. They are NOT an extension of `experiments`.

### Data model
```sql
feature_flags (
  id UUID PK,
  key TEXT UNIQUE NOT NULL,       -- e.g. "new_checkout_flow"
  name TEXT NOT NULL,
  description TEXT,
  enabled BOOL DEFAULT true,     -- master kill switch
  rollout_percentage FLOAT DEFAULT 0,
  created_by UUID FK → users,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

flag_rules (
  id UUID PK,
  flag_id UUID FK → feature_flags ON DELETE CASCADE,
  segment_id UUID FK → segments,
  rollout_percentage FLOAT NOT NULL,  -- override flag-level rollout for this segment
  variant TEXT,                        -- optional: variant name if flag has variants
  priority INT NOT NULL DEFAULT 0,     -- rules evaluated in priority order
  enabled BOOL DEFAULT true
)
```

### Assignment logic
- If `flag.enabled = false` → return `false` for all users (kill switch)
- Evaluate rules in priority order: first matching segment rule wins
- If no rule matches → use flag-level `rollout_percentage`
- Bucketing reuses existing `get_bucket(user_id, flag_key)` from bucketing.py
  — same deterministic SHA256 hash, different key namespace

### Relationship to experiments
- A feature flag CAN be linked to an experiment (optional `experiment_id` on
  the flag) — this allows "test the flag" workflows where the flag's treatment
  variant is the one being A/B tested
- But the flag and experiment are separate entities with separate lifecycles
- The SDK gets `get_flag(user_id, flag_key)` — a separate API path from
  `get_variant(user_id, experiment_id)`

## Consequences

**Positive:**
- Clean separation: flags don't expire, experiments do
- Kill switch is a single boolean — instant, no traffic recalculation
- Flags can exist without experiments (pure operational toggles)
- Existing experiment code is not modified — zero regression risk
- SDK gets a clean new method (`get_flag`) without touching `get_variant`
- Segment targeting on flags is independent of experiment targeting

**Negative:**
- Some code duplication (bucketing logic is shared but assignment service
  has two entry points) — mitigated by reusing `bucketing.py` functions
  directly
- Two API paths for the SDK (`/assignments` for experiments, `/flags/evaluate`
  for flags) — acceptable, they serve different use cases

## Alternatives Considered

### Extend `experiments` table with a `type` column (EXPERIMENT vs FLAG)
- Pros: Single table, single API, less code
- Cons: Experiments have lifecycle (start/stop/complete) that flags don't
  want; flags need kill switch that experiments don't; mixing statistical
  experiments with operational toggles is confusing; would need to
 ALTER experiments table significantly; risk of breaking existing SDK
  and API
- Rejected: semantic mismatch, lifecycle conflict, regression risk

### Use a third-party feature flag service (LaunchDarkly, Unleash)
- Pros: Battle-tested, edge evaluation, streaming updates
- Cons: External dependency (violates self-hosted), cost, data leaves
  infrastructure, another service to integrate
- Rejected: violates self-hosted principle

### Flags as a "special" experiment type with no variants (just ON/OFF)
- Pros: Minimal schema change (add `is_flag` boolean to experiments)
- Cons: Still has lifecycle mismatch (experiments have end dates), no
  clean kill switch, confusing UX (flags shown in experiment list),
  SDK must handle "flag experiments" differently
- Rejected: confusing UX, lifecycle mismatch, unclean SDK semantics
