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

### Changed
- All existing pages refactored: `useState`+`useEffect` for server data replaced
  with `useQuery`/`useMutation`; hardcoded Russian strings replaced with `t()`
  keys; hand-written CSS classes replaced with Tailwind utilities.
- `App.jsx`: auth state now sourced from `useAuthStore` (Zustand + persist);
  `ProtectedRoute` reads from store.
- `main.jsx`: wraps the app with `ErrorBoundary`, `QueryClientProvider`,
  `I18nProvider`, and `ThemeProvider`.
- `index.css`: replaced Vite template with Tailwind directives and shadcn
  light/dark CSS variables.

### Removed
- `App.css` — no longer used (all styles via Tailwind + shadcn).

### Notes
- Bundle: 28 KB CSS / 907 KB JS (277 KB gzipped). Chunked warning is expected
  for the initial bootstrap; future tasks may add code-splitting.
- No backend changes in this task; existing endpoints and SDK contracts are
  untouched.