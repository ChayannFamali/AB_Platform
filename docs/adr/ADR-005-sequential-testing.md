# ADR-005: Sequential Testing — mSPRT vs Alpha-Spending

## Status
Accepted

## Context

The platform's current statistical approach is fixed-horizon: the user
creates an experiment, waits for the hourly cron to analyze, and must not
"peek" at results before the sample size is reached (otherwise the false
positive rate inflates).

This is a known problem in A/B testing. Commercial platforms (Optimizely,
Statsig, GrowthBook) offer sequential testing to allow "peeking" — checking
results at any time without inflating the false positive rate (FPR).

Two approaches are mature:
1. **mSPRT (Always-Valid Sequential Testing)** — used by Optimizely (post-2015)
2. **Alpha-spending (O'Brien-Fleming / Pocock)** — used in clinical trials
   and some A/B platforms

The existing stats engine uses scipy + numpy. The sequential method must
integrate with the existing `hypothesis_tests.py` module and the `Result`
data model.

## Decision

**Use mSPRT (mixtures of Sequential Probability Ratio Tests)** for sequential
experiments.

### Rationale
mSPRT produces an **always-valid p-value** — a single number that can be
checked at any time, with FPR controlled at α regardless of how many times
you look. This is ideal for a platform with hourly cron analysis and a
real-time SSE results page.

### Implementation outline
- `app/services/stats/sequential.py`
- `always_valid_pvalue(group_a, group_b, alpha=0.05, max_n=10_000_000)`
- Uses a mixture of Gaussian prior with variance parameter `rho_max` (default
  0.001, as per Howard et al. 2016, "Uniformly Valid Sequential Tests")
- The mSPRT statistic at time t:
  ```
  Λ_t = ∫ N(m, 1) prior * likelihood_ratio dm
  p_t = 1 / (1 + Λ_t)     (always-valid p-value)
  ```
- Reject H0 when `p_t < α`
- The "boundary" is not a fixed line but a decreasing p-value threshold —
  we store `sequential_fpr` (the always-valid p-value) in the `results` table
- `sequential_boundary_crossed = true` when `sequential_fpr < alpha`

### When sequential is used
- `experiments.is_sequential = true` → the analysis service calls
  `always_valid_pvalue` in addition to the fixed-horizon test
- The fixed-horizon test still runs (for the final decision) — sequential
  is an overlay for "peeking", not a replacement
- `results.sequential_fpr` is the always-valid p-value at current sample size
- `results.sequential_boundary_crossed` is true if the boundary was crossed

### Why not alpha-spending
- Alpha-spending requires pre-specifying the number of looks (interim
  analyses) — inflexible for hourly cron (you'd need to know how many
  hourly crons will run before the experiment ends)
- Alpha-spending produces different thresholds at each look — the user must
  understand "look 3 has α=0.022, look 5 has α=0.018" — confusing
- mSPRT has a single, constant interpretation: "the always-valid p-value
  is 0.03, which is < α=0.05" — simple, no "which look are we on?"
- mSPRT allows any stopping time with no FPR inflation — alpha-spending
  does too, but with pre-planned looks; mSPRT needs no such plan

### Why mSPRT over group sequential (Pocock/O'Brien-Fleming)
- Group sequential methods are designed for equally-spaced looks — our
  hourly cron produces uneven spacing (experiments may be paused, or
  traffic varies by day)
- mSPRT is continuous — works at any sample size, any time

## Consequences

**Positive:**
- Users can peek at results anytime — the #1 UX complaint about A/B
  testing platforms is "don't look until sample size is reached"
- The hourly cron naturally serves as the "look" schedule — no change
  to worker
- Always-valid p-value is a single number — simple to explain in the UI:
  "Sequential p-value: 0.032 (< 0.05 threshold, safe to stop)"
- Integrates with SSE: when sequential boundary is crossed, push a
  `sequential_boundary_crossed` event to the frontend

**Negative:**
- mSPRT is slightly more conservative than fixed-horizon at the same
  sample size — experiments need ~10-15% more samples to reach the same
  power. This is inherent to any sequential method.
- Implementation requires careful numerical work (Gaussian mixture
  integral, log-space for numerical stability) — the agent must test
  with golden numbers (see TESTING_STRATEGY.md)
- "mSPRT" is less familiar to statisticians than "alpha-spending" —
  but the UI abstraction ("sequential p-value") hides the method name
  from users

### Phase 2 consideration
- CUPED variance reduction (pre-experiment covariate adjustment) is
  complementary to mSPRT — both reduce required sample size. CUPED is
  in the backlog (TASKS.md) but not in this ADR's scope.

## Alternatives Considered

### Alpha-spending (O'Brien-Fleming boundaries)
- Pros: Well-known in clinical trials, implemented in statsmodels
  (`Sequentialdesign`), conservative early looks
- Cons: Requires pre-specified number of looks; produces different α
  thresholds per look (confusing UI); designed for equal-spacing looks;
  statsmodels implementation is for biomedical use cases, not A/B testing
- Rejected: inflexible for hourly cron, confusing per-look thresholds

### Bonferroni correction (divide α by number of looks)
- Pros: Trivially simple, no new code
- Cons: Extremely conservative — with 720 looks (30 days hourly), α/720
  = 0.0000694 — you'd need an enormous effect to detect anything;
  not a real sequential method, just a crude correction
- Rejected: too conservative, effectively useless

### Do nothing (keep fixed-horizon only, warn users not to peek)
- Pros: Zero implementation effort
- Cons: Users WILL peek (everyone does) — the platform should protect
  them from inflated FPR rather than telling them "don't look"
- Rejected: does not solve the core problem; not competitive with
  commercial platforms
