# Changelog

## [Unreleased]

### Added
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
- M-003 tests: 72 passed, 0 failed (`pytest tests/ -v`).
- M-003 migration verified: `alembic upgrade head` and `downgrade -1` both run
  cleanly on the test database.
- The legacy `users.is_admin` column is retained as a deprecated read-only field
  for one release cycle; it will be removed by migration `0015` (future task).