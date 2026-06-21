# ADR-002: State Management Strategy

## Status
Accepted

## Context

The current frontend has no state management library. State is passed via props
from `App.jsx`, auth tokens live in `localStorage`, and each page component
manages its own `useState`. This does not scale to 15+ pages with:
- Shared auth/role state across the app
- Server state (experiments, flags, results) that must be cached, invalidated, and refetched
- UI state (sidebar open/closed, theme, locale) that is global but ephemeral
- Real-time SSE updates that must update cached server state

React 19 has no built-in solution for server state caching or global client state.

## Decision

**Split state into two layers:**

### Server State — TanStack Query v5 (`@tanstack/react-query` ^5.x)

All data fetched from the backend is managed by TanStack Query:
- Query keys follow the pattern `['experiments', { status, page }]`, `['flags', flagId]`, etc.
- Mutations (`useMutation`) handle create/update/delete with automatic cache invalidation
- `staleTime`: 60s for list queries, 30s for detail queries, `Infinity` for immutable config (roles, segments)
- `refetchOnWindowFocus`: false (prevents noise during development)
- `retry`: 1 for mutations, 2 for queries
- SSE updates trigger `queryClient.setQueryData()` for optimistic cache updates

### Client UI State — Zustand v5 (`zustand` ^5.x)

Global UI state that is NOT server data:
- `authStore`: `{ user, token, roles, login(), logout() }` — persisted to `localStorage` via `zustand/middleware/persist`
- `uiStore`: `{ sidebarOpen, theme, locale, setTheme(), setLocale() }` — persisted to `localStorage`
- No server data in Zustand — if it comes from the API, it goes in TanStack Query

### Per-component state
- `useState` / `useReducer` for form inputs, modal open/closed, local UI flags
- No change from current pattern

## Consequences

**Positive:**
- Clear separation: server data = TanStack Query, UI state = Zustand, local = useState
- Automatic cache invalidation, background refetch, stale-while-revalidate
- DevTools (`@tanstack/react-query-devtools`) for debugging cache
- SSE updates integrate naturally with `queryClient.setQueryData`
- Zustand is ~1KB gzipped — negligible bundle impact
- Both libraries work with plain JSX (no TypeScript required, though types are available)

**Negative:**
- Two mental models: "is this in Query or Zustand?" — mitigated by the rule
  "if it has an endpoint, it's in Query"
- TanStack Query v5 API changes from v4 (the agent must use v5 syntax:
  `useQuery({ queryKey, queryFn })`, not `useQuery(queryKey, queryFn)`)

## Alternatives Considered

### Redux Toolkit (RTK) + RTK Query
- Pros: Battle-tested, RTK Query for server state, single store
- Cons: Boilerplate (slices, reducers, selectors), steeper learning curve,
  ~12KB gzipped, overkill for this project size, RTK Query is tightly
  coupled to Redux store
- Rejected: too much boilerplate for a 15-page SPA

### Jotai v2 (atomic state)
- Pros: Bottom-up approach, no boilerplate, excellent for fine-grained state
- Cons: No built-in server state solution (would still need TanStack Query),
  mental model is "atoms" — harder to onboard, debugging is less intuitive
- Rejected: no server state story, adds a second library anyway

### React Context only
- Pros: No dependencies, built into React
- Cons: Context re-renders all consumers on any change — performance issues
  with frequent updates (SSE events), no caching, no invalidation, no
  background refetch
- Rejected: no server state capabilities, re-render performance issues

### SWR (Vercel) for server state
- Pros: Simpler than TanStack Query, smaller bundle
- Cons: Fewer features (no `useMutation`, no optimistic updates, no
  devtools, less control over cache invalidation), worse TypeScript support
- Rejected: lacks mutation support and cache control needed for this app
