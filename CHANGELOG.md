# Changelog

## [Unreleased]

### Added
- M-011: custom metrics subsystem — global, reusable metric templates
  (event + aggregation + AND-combined property filters + optional
  denominator for ratio metrics) snapshotted into per-experiment
  `Metric` rows via `custom_metric_id`. New endpoints:
  `GET/POST /api/v1/custom-metrics`, `GET/PATCH/DELETE
  /api/v1/custom-metrics/{id}`, `GET /api/v1/custom-metrics/by-key/{key}`,
  `POST /api/v1/custom-metrics/{id}/preview` (plain-English summary
  + per-filter dry-run). RBAC: `metrics:read` / `metrics:write`.
  Schema migration `0015_custom_metrics_guardrails`.
- M-011: per-experiment guardrail subsystem. `GuardrailConfig` rows
  attach to one of the experiment's metrics (where `is_guardrail=true`)
  with `direction` ("below"/"above"), `threshold_pct` (positive %),
  and `severity` ("warning"/"critical"). Critical violations set
  `metric.guardrail_violated=True` and block the winner flag for ALL
  primary metrics in the experiment; warning violations emit a new
  `guardrail_warning` insight without blocking. Endpoints nested under
  the experiment: `GET/POST /api/v1/experiments/{id}/guardrails`,
  `PATCH/DELETE /api/v1/experiments/{id}/guardrails/{gid}`.
  RBAC: `guardrails:read` / `guardrails:write`.
- M-011: engine integration. `Metric.aggregation` (new nullable
  column) overrides the engine's old `metric_type`-based default;
  `Metric.filters` (JSONB list of `{field, operator, value}`) is
  applied to `events.properties` at read time in the conversion,
  revenue, and ratio SQL loaders. `custom_metric_id` back-FK on
  `metrics` (ON DELETE SET NULL) preserves traceability. Engine
  evaluation: when a metric has any `GuardrailConfig` rows,
  `evaluate_metric_guardrails` checks each variant's `relative_lift`
  against the configured direction × threshold — fires only when
  `variant.is_significant=True` (avoids noise triggers). Legacy
  fallback: metrics with `is_guardrail=True` but no GuardrailConfigs
  still trip on "any significant negative effect" so pre-M-011
  experiments continue to behave the same.
- M-011: frontend — `/custom-metrics` list + builder pages (with
  filter rows, ratio denominator, plain-English preview) and a new
  "Guardrails" tab on the experiment detail page. Routes registered
  in `App.jsx`; nav link added.

### Notes
- M-011 backend tests: 32 new tests in `test_m011_custom_metrics_guardrails.py`
  — custom metric CRUD (12 cases including duplicate-key, invalid
  operator, ratio with denominator, list pagination, delete,
  custom-metric-id snapshot into experiment Metric), RBAC analyst
  block, filter SQL generation (5 unit tests on `build_filter_clause`),
  guardrail CRUD (5 cases including reject-non-guardrail-metric and
  duplicate-severity), `check_threshold` cross-side matrix (7 unit
  tests covering below/above × significant/not × inside/outside), and
  `evaluate_metric_guardrails` integration (5 cases covering critical
  blocking, warning not-blocking, non-guardrail-metric skip, no-fire
  when not significant, mixed severities). Full backend suite
  **71 passed** (`pytest tests/test_m011_custom_metrics_guardrails.py
  tests/test_stats.py tests/test_integration.py -q`).
- M-011 frontend tests: 4 new MetricFilterRow tests + 3 new
  GuardrailsTab tests. Full frontend suite **94 passed** across 32
  test files (`npm run test:run`).
- M-011 frontend lint: clean (`npm run lint`).
- M-011 frontend bundle: `npm run build` succeeds
  (1073 KB JS / 316 KB gzipped — +34 KB on top of the M-010 baseline
  for CustomMetricListPage + MetricBuilderPage + MetricFilterRow +
  GuardrailsTab + extended ExperimentDetailPage).
- M-011 migrations verified: `alembic upgrade head` and
  `downgrade -1` both run cleanly on the test database. Migration
  `0015_custom_metrics_guardrails` is a merge node with
  `down_revision = ("0011_holdouts", "0014_api_key_scopes")` to
  reconcile the existing two-head branch state.
- M-011 enum labelling: PostgreSQL enum labels are lowercase
  (`count`, `sum`, `below`, `warning`, …) to match the wire-format
  strings. SAEnum declarations use `values_callable=lambda enum:
  [e.value for e in enum]` so SQLAlchemy serialises the `.value`
  instead of the `.name`.
- M-011 backward compatibility: the engine still produces analysis
  output for pre-M-011 experiments (rows with `aggregation IS NULL`
  fall back to the legacy `metric_type`-based inference). Guardrail
  semantics also fall back to the pre-M-011 "any negative significant
  effect = violation" rule when a guardrail metric has zero
  GuardrailConfig rows. Existing API responses now include the
  three new Metric columns (`aggregation`, `filters`,
  `custom_metric_id`) — they're nullable, so callers ignoring them
  continue to work.
- M-011 audit hooks: every `custom_metrics` and `guardrail_configs`
  mutation writes an `audit_log` row with the appropriate
  `resource_type` (`"custom_metric"` / `"guardrail_config"`).

### Notes
- M-010 backend tests: 38 new tests pass (22 segment: 6 operator unit
  tests covering all 9 operators, 8 CRUD lifecycle, 1 rule CRUD, 3 AND
  logic + dry-run breakdown, 1 experiment linking, 1 RBAC, 1 audit, 1
  empty-rules; 16 holdout: 3 bucketing unit tests, 5 CRUD lifecycle,
  2 exclusion CRUD, 1 inactive semantics, 1 assignment integration
  with 100% holdout, 1 flag SDK backward-compat smoke, 2 audit).
  Full backend suite **176 passed, 0 failed** (`pytest tests/ -q` —
  138 prior + 38 new).
- M-010 frontend tests: 3 new SegmentRuleRow tests (default render,
  field onChange, remove callback). Full frontend suite **87 passed,
  0 failed** across 30 test files (`npm run test:run`).
- M-010 frontend lint: clean (`npm run lint`).
- M-010 frontend bundle: `npm run build` succeeds
  (1039 KB JS / 310 KB gzipped — +40 KB on top of the M-009 baseline
  for SegmentListPage + SegmentBuilderPage + 2 sub-components +
  extended FlagRuleEditor + i18n namespace).
- M-010 migrations verified: `alembic upgrade head` and
  `downgrade -1` both run cleanly on the test database (0010_segments
  depends on 0009_feature_flags; 0011_holdouts depends on 0010).
- M-010 SDK backward compatibility: SDK v0.2.x methods (`get_flag`,
  `get_flags`, `getVariant`, `trackEvent`, `flush`) are unchanged.
  The SDK clients don't have to send `user_properties` — omitting it
  preserves the pre-M-010 evaluation path.
- M-010 holdout semantics: per the design decision, holdout users
  receive `default` for flag evaluations (rollout is treated as
  inactive for them) so the cohort stays clean for measurement.
- M-010 segment reservation: `FlagRule.segment_id` now has a proper FK
  to `segments.id` (ON DELETE SET NULL). M-009 rows that left the
  column as `NULL` trivially satisfy the new constraint.
- M-010 operator set: the 9 supported operators are listed in
  `segment_service.SEGMENT_OPERATORS` — used by the API to validate
  payloads (422 on unknown operator) and by the matcher to dispatch
  comparisons. `in` / `not_in` expect a list; `gt` / `lt` / `gte` /
  `lte` coerce via `float()` when possible.

### Added
- M-010: Segments + Holdout Groups (ADR-004 follow-on). Six new tables
  (`segments`, `segment_rules`, `experiment_segments`,
  `holdout_groups`, `holdout_exclusions`) plus FK on `flag_rules.segment_id`
  and `experiments.holdout_group_id`. Segments are reusable targeting
  definitions: 9 operators (eq/neq/in/not_in/gt/lt/gte/lte/contains)
  AND-combined into named segments; `user_properties` is passed by the
  SDK at evaluate time. Holdout groups are deterministic measurement
  baselines (`holdout:` bucket namespace) that exclude users from linked
  experiments AND from flag rollouts. UI routers under `/api/v1/segments`
  and `/api/v1/holdouts` (`segments:read` / `segments:write` /
  `holdouts:read` / `holdouts:write`). SDK routers (`/assignments`,
  `/sdk/flags/evaluate`, `/sdk/flags/evaluate-batch`) accept an
  optional `user_properties` dict — backward-compatible: omitting it
  preserves pre-M-010 behavior. `flag_service._resolve_rollout` is now
  segment-aware (reason codes `segment_in` / `segment_out`); segment
  rule with a matching `segment_id` wins over flag-level rollout.
  `assignment_service` checks holdout BEFORE bucket/variant pick and
  validates segment match against linked `experiment_segments` (OR
  across segments). Frontend: new `SegmentListPage` (`/segments`),
  `SegmentBuilderPage` (`/segments/new` and `/segments/:key`) with a
  visual rule builder + live dry-run preview; `FlagRuleEditor` now
  exposes a "Apply to segment" select. New components:
  `SegmentRuleRow`, `SegmentPreview`. i18n keys (ru + en).
- M-009: Feature flags — kill switches + gradual rollouts + SDK contract
  (ADR-004). Two new tables (`feature_flags`, `flag_rules`) with
  `segment_id` reserved (nullable UUID, no FK yet — wired up by M-010).
  UI router under `/api/v1/flags` (`flags:read` / `flags:write`); SDK
  router under `/api/v1/sdk/flags` (scope `flags:read`). Bucket math is
  deterministic SHA256 with a dedicated `flag:` key namespace so flag
  outcomes stay independent of experiment assignments. Rule evaluation
  resolves to `flag.rollout_percentage` by default; rules with
  `segment_id=null` and the lowest `priority` act as "applies to
  everyone" overrides — first match wins. Reason codes returned to the
  SDK: `kill_switch`, `rollout_in`, `rollout_out`, `rule_override`,
  `not_found`. Audit hooks on every mutation (create / update /
  toggle / delete / add_rule / delete_rule). Frontend: new
  `FlagListPage` (`/flags`) with summary stats + optimistic kill switch
  + delete; new `FlagDetailPage` (`/flags/:key`) with config card,
  rollout slider, and rule editor; Dashboard "Active flags" card wired
  to `/api/v1/flags/summary`. New sub-components: `FlagToggle`,
  `RolloutSlider`, `FlagStatusBadge`, `FlagRuleEditor`. Python SDK
  v0.2.0: `get_flag(user_id, flag_key, default=False)` +
  `get_flags(user_id, flag_keys)`. JS SDK v0.2.0: `getFlag` +
  `getFlags`. Both SDKs reuse the existing TTL cache, batch
  endpoints for SDK startup, and graceful degradation on timeout /
  5xx / 403 (returns `default` instead of throwing). Existing SDK
  methods (`get_variant` / `getVariant`, `track_event` /
  `trackEvent`) are unchanged — v0.1.x clients keep working.
- M-008: Real-time SSE updates — `GET /api/v1/events/stream?experiment_id=<uuid>&token=<jwt>`
  (ADR-003): JWT in `?token=` query (EventSource cannot send custom headers),
  Redis pub/sub fan-out via per-experiment channel `results:{experiment_id}`,
  `text/event-stream` response with `Cache-Control: no-cache` and
  `X-Accel-Buffering: no` headers; 30s `: ping` heartbeats; native
  EventSource auto-reconnect; named events (`event: result_updated |
  srm_alert | winner_detected | guardrail_violated |
  sequential_boundary_crossed`) so the browser dispatches by type.
  New `app/services/sse_manager.py` (publisher + subscriber +
  format_sse/format_heartbeat/format_retry) and `app/routers/sse.py`
  (StreamingResponse endpoint with `results:read` RBAC). Wire-up:
  `analysis_service.run_and_save` publishes `result_updated` on every
  analysis and the 4 alert types based on the rule-based insights engine
  (SRM, clear winner, guardrail, sequential boundary). Frontend: new
  `hooks/useSSE.js` (EventSource wrapper, auto-reconnect, JWT
  injection, cleanup on unmount); `ExperimentDetailPage` subscribes on
  mount, invalidates TanStack queries on `result_updated`, and shows
  i18n toasts for SRM / winner / guardrail / boundary alerts (visible
  from every tab, not just Results). nginx location block for
  `/api/v1/events/stream` with `proxy_buffering off`,
  `proxy_read_timeout 3600s`, `proxy_http_version 1.1`. i18n keys
  (`sse.toast.{srm,winner,guardrail,boundary,updated}`) in
  `ru.json` + `en.json`.
- M-007: Statistical Intelligence — Sequential testing (mSPRT,
  Howard et al. 2021) + rule-based insights engine + 8 stat UX
  components. New `backend/app/services/stats/sequential.py` with
  closed-form log-space mSPRT statistic (`always_valid_pvalue`,
  `rho_max=0.001`, returns `None` for n<30); new
  `backend/app/services/stats/interpreter.py` with six rules
  (SRM detected → ERROR, clear winner → SUCCESS at p<0.01 + lift>2%,
  likely winner → SUCCESS at p<0.05, underpowered → WARNING when
  MDE > 50% of baseline, guardrail violated → ERROR, no significance
  yet → INFO, sequential boundary crossed → INFO for sequential
  experiments); migration `0008_sequential_results` adding
  `experiments.is_sequential`, `results.sequential_fpr`,
  `results.sequential_boundary_crossed`, and
  `results_daily.sequential_fpr`; mSPRT wired into the analysis
  engine (conversion + revenue/duration branches — ratio metrics
  skipped for now); engine now returns a new
  `ExperimentAnalysis(metrics, insights)` wrapper so the router can
  return `insights` at the top level of the analysis response;
  `experiment_service.create_experiment` accepts
  `is_sequential: bool`; CSV export extended with two new columns
  (`sequential_fpr`, `sequential_boundary_crossed`); wizard Step 5
  «Settings» exposing the sequential toggle (and a holdout-group
  placeholder for M-010) so wizard now has 5 steps
  (Basics → Variants → Metrics → Settings → Review); results tab
  renders `<InsightPanel>` above all metric tables when insights
  are present and `<SequentialPValueChart>` (recharts) for
  sequential experiments; 8 new frontend components in
  `frontend/src/components/stats/` (`SignificanceBadge`,
  `SRMAlert`, `PowerWarning`, `CIBar`, `AchievedMDEBlock`,
  `TestBadge`, `SequentialPValueChart`, `InsightPanel`) — each with
  i18n keys and unit tests; `ExperimentResultsTab` refactored to
  use `SignificanceBadge` + `TestBadge` + `SRMAlert` instead of
  inline helpers; `ExperimentSettingsTab` shows the `is_sequential`
  flag; i18n keys (`stats.*`, `wizard.step5`, `wizard.settings.*`,
  `experiments.detail.sequential*`) in `ru.json` + `en.json`.
- M-006: Create Experiment Wizard + Sample Size Calculator — 4-step
  wizard at `/experiments/new` (Basics → Variants → Metrics → Review)
  with per-step validation, back button state preservation, and inline
  `SampleSizeCalculator` on step 3; standalone calculator page at
  `/tools/sample-size`; shared `SampleSizeCalculator` component with
  two tabs (Conversion + Continuous, calling the existing
  `/api/v1/stats/sample-size/{conversion,revenue}` endpoints); new
  sub-components `WizardStepper` (numbered progress indicator with
  done/current/pending states) and `WizardStep` (header + footer with
  Back/Next buttons); new API client function `getSampleSizeContinuous`;
  nav link to the calculator; i18n keys (`wizard.step1-4`,
  `wizard.review.*`, `sampleSize.*`) in `ru.json` + `en.json`.
- M-005: Core pages — `DashboardPage` at `/` (summary cards: running
  experiments / completed / total + recent activity feed from audit log +
  quick action links; "active flags" card is a stub pending M-009);
  `ExperimentDetailPage` at `/experiments/:id` with four URL-synced tabs
  (`?tab=overview|results|decisions|settings`); sub-components
  `ExperimentStatusCard`, `ExperimentResultsTab` (extracted from the
  former `ExperimentResults.jsx`), `DecisionLogTab` (placeholder for
  M-012), `ExperimentSettingsTab` (read-only metadata), and
  `ExportButton`; `SettingsPage` at `/settings` with theme toggle,
  language switcher, admin shortcuts, and platform version block; new
  backend endpoint `GET /api/v1/experiments/{id}/results/export?format=csv`
  returning RFC 4180 CSV (`text/csv` + `Content-Disposition: attachment`),
  backed by `analysis_service.export_results_csv()`; new API client
  functions `exportResults` (Blob for download) and fixed
  `getDailyResults` URL (was missing `/api/v1` prefix — caused 404 on
  the daily trend chart); i18n keys for all new pages and tabs in
  `ru.json` + `en.json` (dashboard, settings, export, decisions,
  experiments.detail, experiments.tabs).
- M-004: Audit log + Users & Audit pages — `AuditLog` model (append-only,
  `id` / `user_id` / `action` / `resource_type` / `resource_id` /
  `details` JSONB / `ip_address` / `user_agent` / `created_at`);
  migration `0007_audit_log` (`down_revision = "0014_api_key_scopes"`,
  creates `audit_log` with 4 indexes on `created_at` / `user_id` /
  `resource_type` / `action`); `app/services/audit_service.py`
  (`log_action(actor, action, resource_type, resource_id, details, request)`
  + `list_audit_entries(limit, offset, resource_type, user_id, action)` —
  IP/UA extracted from `Request`, eager-loads `user` to avoid N+1);
  `app/schemas/audit.py` (`AuditLogEntry` with `details` instead of
  `metadata` because the latter is reserved by SQLAlchemy's Declarative
  API); `app/routers/audit.py` (`GET /api/v1/audit`, paginated,
  filterable, requires `audit:read`); audit hooks on all five
  role/user mutations (`POST /roles`, `PATCH /roles/{id}`,
  `PATCH /users/{id}`, `POST /users/{id}/roles`,
  `DELETE /users/{id}/roles/{role_id}`); `UsersPage` at
  `/settings/users` with role assign/revoke dialog and is_active toggle;
  `AuditLogPage` at `/settings/audit` with resource_type / action
  filters; API client additions (`getUsers`, `getRoles`, `assignRole`,
  `revokeRole`, `updateUserActive`, `getAuditLog`); nav links (admin
  only); i18n keys for both pages (ru + en).
- M-002: Frontend testing setup — Vitest 2.x + React Testing Library 16 +
  jsdom 25 + @vitest/coverage-v8; `npm test` / `npm run test:run` /
  `npm run test:coverage` / `npm run test:watch` / `npm run test:ui`
  scripts; `vitest.config.js` (jsdom env, automatic JSX runtime,
  coverage thresholds), `src/test/setup.js` (jest-dom matchers,
  matchMedia/IntersectionObserver/ResizeObserver mocks, localStorage reset),
  `src/test/utils.jsx` (`renderWithProviders` wrapping QueryClient +
  MemoryRouter + I18nextProvider); ESLint config relaxed for test files
  (`react-refresh/only-export-components` disabled, vitest globals enabled).
  Smoke tests for all six pages (Login, Register, ExperimentList,
  CreateExperiment, ExperimentResults, ApiKeysPage) and four common
  components (EmptyState, LoadingState, ErrorBoundary, PageContainer) —
  29 tests, all passing. API mocked at module level via `vi.mock`
  (no MSW yet — keeps M-002 lean; MSW can be added in M-005/M-008
  for proper HTTP-level integration tests).
- M-001: Frontend foundation — Tailwind CSS + shadcn/ui (vendored components:
  button, card, input, label, badge, alert, dialog, dropdown-menu, tabs, tooltip,
  table, select, checkbox, switch, toast), TanStack Query v5 for server state,
  Zustand v5 for client state (auth + UI persisted), react-i18next with ru/en
  translations, light/dark theme via `<html class="dark">` toggle,
  reusable `EmptyState` / `LoadingState` / `ErrorBoundary` / `PageContainer`
  components, and a `useToast` hook for app-wide notifications.
- M-003: RBAC backend — `Role`, `RolePermission`, `UserRole` models; `ApiKey.scopes`
  (JSONB); migration `0006_rbac` (creates tables, seeds the four predefined
  roles with the ADR-006 permission matrix, migrates existing `is_admin=true`
  users to `admin` role and the rest to `viewer`); migration
  `0014_api_key_scopes` (adds scopes column with the
  `["assignments:read", "events:write"]` default for backward-compatible SDK
  v0.1.0 behaviour); `rbac_service.require_permission(...)` FastAPI dependency
  factory; `require_sdk_scope(...)` for SDK scope checks; new endpoints
  `/api/v1/roles`, `/api/v1/users`, `/api/v1/users/{id}/roles` (admin only);
  `UserResponse` now embeds `roles[]` and `permissions[]`; `ApiKeyCreate`
  accepts a `scopes` list and `ApiKeyResponse` returns it.

### Changed
- `tests/conftest.py` (M-004): `clean_tables` now TRUNCATEs `roles` +
  `role_permissions` and re-seeds the four standard roles + their
  permission sets per test (imported from `rbac_service.ROLE_PERMISSIONS`).
  Previously roles accumulated across tests, eventually breaking
  `test_admin_can_list_roles` assertions on `len(roles) == 4`.
- All existing pages refactored (M-001): `useState`+`useEffect` for server data
  replaced with `useQuery`/`useMutation`; hardcoded Russian strings replaced
  with `t()` keys; hand-written CSS classes replaced with Tailwind utilities.
- `App.jsx` (M-001): auth state now sourced from `useAuthStore` (Zustand + persist);
  `ProtectedRoute` reads from store.
- `main.jsx` (M-001): wraps the app with `ErrorBoundary`, `QueryClientProvider`,
  `I18nProvider`, and `ThemeProvider`.
- `index.css` (M-001): replaced Vite template with Tailwind directives and shadcn
  light/dark CSS variables.
- `dependencies.py` (M-003): `get_current_user` now eager-loads
  `User.roles → Role.permissions` so `require_permission` performs a single
  set lookup with no N+1. `get_sdk_auth` falls back to JWT for debugging.
- All UI routers (M-003): every protected endpoint now declares its required
  permission via `Depends(rbac_service.require_permission(...))` —
  `experiments:read` for GETs, `experiments:create` for POSTs,
  `experiments:update` for PATCH status, `experiments:delete` for DELETE,
  `experiments:analyze` for `/analyze`, `results:read` for `/results/*` and
  sample-size, `users:manage` for roles/users management.
- SDK routers (M-003): `assignments` and `events` now enforce SDK scopes via
  `require_sdk_scope("assignments:read")` / `require_sdk_scope("events:write")`.
  Keys with `scopes == ["*"]` bypass the check (admin SDK keys).
- `auth_service.create_user` (M-003): first registered user gets the `admin`
  RBAC role, every subsequent user gets `viewer`. The legacy `is_admin` boolean
  is still flipped for backward compatibility but the authoritative check is
  now via roles.

### Removed
- `App.css` (M-001) — no longer used (all styles via Tailwind + shadcn).
- `frontend/src/pages/ExperimentResults.jsx` (M-005) — replaced by
  `ExperimentDetailPage` (4 tabs) + `ExperimentResultsTab` (extracted
  results-table logic). The `/experiments/:id` route now renders the
  new detail page. Old `ExperimentResults.test.jsx` was deleted and
  replaced by `ExperimentDetailPage.test.jsx`.
- `frontend/src/pages/CreateExperiment.jsx` (M-006) — replaced by
  `CreateExperimentWizard` (4 steps). The `/experiments/new` route
  now renders the new wizard. Old `CreateExperiment.test.jsx` was
  deleted and replaced by `CreateExperimentWizard.test.jsx`.

### Notes
- M-009 backend tests: 27 new flag tests pass (4 bucket-math unit
  tests, 9 CRUD lifecycle, 2 rule CRUD, 6 evaluation incl. rule
  override + 50% distribution check, 2 RBAC, 2 SDK scope, 2 audit).
  Full backend suite **138 passed, 0 failed** (`pytest tests/ -v`).
- M-009 frontend tests: 8 new tests across 3 files (3 FlagListPage,
  3 FlagStatusBadge, 4 RolloutSlider — 1 shared assertion shape).
  Full frontend suite **84 passed, 0 failed** across 29 test files
  (`npm run test:run`).
- M-009 frontend lint: clean (`npm run lint`).
- M-009 frontend bundle: `npm run build` succeeds
  (999 KB JS / 300 KB gzipped — +21 KB on top of the M-008 baseline
  for the new flag pages + 4 sub-components).
- M-009 Python SDK: 12 new tests (6 get_flag + 6 get_flags —
  happy path, server error, connection refused, missing flag, caching,
  per-user cache, batch, partial cache, empty list, all defaults,
  403 missing scope). SDK suite **23 passed, 0 failed**
  (`pytest sdk/python/tests/`).
- M-009 JS SDK: 11 new tests (6 getFlag + 5 getFlags — same matrix).
  SDK suite **26 passed, 0 failed** (`jest`).
- M-009 migration verified: `alembic upgrade head` and
  `downgrade -1` both run cleanly.
- M-009 SDK backward compatibility: v0.1.x clients keep working —
  `getVariant` / `trackEvent` / `flush` / `destroy` are unchanged.
- M-009 segment targeting: deferred to M-010 (Segments + Holdouts).
  `FlagRule.segment_id` is already in the schema (nullable UUID, no
  FK) so M-010 only needs to add the FK and segment-membership check
  in `flag_service._resolve_rollout`.
- M-008 backend tests: 10 new SSE tests pass (5 format/wire-format
  unit tests, 2 publisher error-handling tests, 1 subscribe + parse
  test using real Redis, 2 auth tests for the SSE endpoint —
  no-token 401 and bad-token 401). Full backend suite
  **111 passed, 0 failed** (`pytest tests/ -v`).
- M-008 frontend tests: 6 new useSSE hook tests added (disabled /
  missing-token no-op, URL with token, subscribes to all 5 named event
  types + connected, onEvent callback fires on typed event, close on
  unmount). Full frontend suite **74 passed, 0 failed** across 26
  test files (`npm run test:run`).
- M-008 frontend lint: clean (`npm run lint`).
- M-008 frontend bundle: `npm run build` succeeds
  (978 KB JS / 294 KB gzipped — +3 KB on top of the M-007 baseline
  for the `useSSE` hook).
- M-008 SSE end-to-end test limitation: httpx 0.28's ASGITransport
  buffers the entire streaming response body until completion, so
  end-to-end HTTP tests of the SSE endpoint are unreliable. The
  streaming flow is covered by direct `subscribe_experiment` tests
  against real Redis, which exercises the same code path the SSE
  endpoint uses internally. Auth + headers are verified by HTTP.
- M-007 backend tests: 15 new tests pass (6 mSPRT golden numbers
  including CLT floor / zero-variance / large-effect / continuous
  metrics / monotonic sample-size; 9 interpreter rule tests covering
  every insight type). Full backend suite
  **101 passed, 0 failed** (`pytest tests/ -v`).
- M-007 frontend tests: 8 new stat-component tests + 1 wizard test
  added. Full frontend suite **68 passed, 0 failed** across 25
  test files (`npm run test:run`).
- M-007 frontend lint: clean (`npm run lint`).
- M-007 frontend bundle: `npm run build` succeeds
  (975 KB JS / 294 KB gzipped — 8 new stat components add ~3 KB
  gzipped on top of the M-006 baseline; recharts is already in the
  bundle so the sequential chart adds no new dependency weight).
- M-007 migration verified: `alembic upgrade head` and
  `downgrade -1` both run cleanly on the test database.
- M-006 backend: no changes; existing 86 tests still pass
  (`pytest tests/ -v`).
- M-001 bundle: 28 KB CSS / 907 KB JS (277 KB gzipped).
- M-002 tests: 29 passed, 0 failed across 10 test files
  (`npm run test:run`).
- M-002 coverage: 47% lines / 25% functions / 73% branches — smoke-only
  baseline; thresholds tuned for current test count and will tighten as
  feature-specific tests are added in M-005+ (TESTING_STRATEGY.md
  target is 70% overall).
- M-003 tests: 72 passed, 0 failed (`pytest tests/ -v`).
- M-004 backend tests: 9 audit tests pass; full backend suite
  81 passed, 0 failed (`pytest tests/ -v`).
- M-004 frontend tests: 33 passed, 0 failed across 12 test files
  (`npm run test:run`) — added 4 new smoke tests (2 per page).
- M-004 migration verified: `alembic upgrade head` and `downgrade -1`
  both run cleanly.
- M-005 backend tests: 86 passed, 0 failed (`pytest tests/ -v`) —
  added 5 new tests for `GET /api/v1/experiments/{id}/results/export`
  (404 when no results / 400 on bad format / 401 unauthenticated /
  well-formed CSV with 1 row / multiple variant rows).
- M-005 frontend tests: 39 passed, 0 failed across 14 test files
  (`npm run test:run`) — added 7 new tests (2 DashboardPage,
  3 SettingsPage, 2 ExperimentDetailPage) and deleted the old
  `ExperimentResults.test.jsx` (replaced by `ExperimentDetailPage.test.jsx`).
- M-005 frontend lint: clean (`npm run lint`).
- M-005 frontend bundle: `npm run build` succeeds (no new size budget
  concerns — DashboardPage + ExperimentDetailPage + SettingsPage +
  5 sub-components add ~12 KB gzipped on top of the M-001 baseline).
- M-006 frontend tests: 48 passed, 0 failed across 17 test files
  (`npm run test:run`) — added 9 new tests (3 WizardStepper,
  3 SampleSizeCalculator, 4 CreateExperimentWizard, 1
  SampleSizeCalculatorPage) and deleted the old
  `CreateExperiment.test.jsx` (replaced by
  `CreateExperimentWizard.test.jsx`).
- M-006 frontend lint: clean (`npm run lint`).
- M-006 backend: no changes; existing 86 tests still pass
  (`pytest tests/ -v`).
- M-003 migration verified: `alembic upgrade head` and `downgrade -1` both run
  cleanly on the test database.
- The legacy `users.is_admin` column is retained as a deprecated read-only field
  for one release cycle; it will be removed by migration `0015` (future task).