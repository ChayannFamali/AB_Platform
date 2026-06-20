# Changelog

## [Unreleased]

### Added
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

### Notes
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
- M-003 migration verified: `alembic upgrade head` and `downgrade -1` both run
  cleanly on the test database.
- The legacy `users.is_admin` column is retained as a deprecated read-only field
  for one release cycle; it will be removed by migration `0015` (future task).