# Changelog

## [Unreleased]

### Added
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