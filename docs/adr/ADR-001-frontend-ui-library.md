# ADR-001: Frontend UI Component Library

## Status
Accepted

## Context

The AB Platform frontend is a production product positioned as a self-hosted
alternative to Optimizely. The current frontend uses plain JSX with hand-written
CSS (~200 lines in App.css). There is no component library, no design system,
no dark mode, and no accessibility infrastructure.

The product needs:
- A consistent design system across 15+ pages
- Dark/light theme support
- Keyboard navigation and screen reader support (a11y)
- Data tables, dialogs, forms, dropdowns, tabs, tooltips
- i18n-friendly text rendering
- A look-and-feel that signals "enterprise platform", not "hackathon prototype"

The frontend is built with React 19 + Vite. It currently uses plain JavaScript
(JSX), not TypeScript.

## Decision

**Adopt shadcn/ui** (latest, via `npx shadcn@latest init`) built on:
- **Radix UI primitives** (`@radix-ui/react-*` ^1.x) — headless, fully accessible components
- **Tailwind CSS** ^3.4.x — utility-first styling, theme tokens via CSS variables
- **class-variance-authority** ^0.7.x — variant composition
- **lucide-react** ^0.4xx.x — icon set

shadcn/ui is not a traditional npm package — it copies component source into
`src/components/ui/` and gives full ownership. This means:
- Components can be customized without upstream constraints
- No runtime dependency on a "library version" — each component is vendored
- The agent-implementation can read and modify every component

### Additional packages
- `react-i18next` ^15.x + `i18next` ^24.x — for ru/en localization
- `@tanstack/react-query` ^5.x — server state (see ADR-002)
- `zustand` ^5.x — client UI state (see ADR-002)

## Consequences

**Positive:**
- Full a11y via Radix primitives (ARIA, keyboard nav, focus trapping)
- Dark/light theme via Tailwind `class` strategy (one `<html class="dark">` toggle)
- Design tokens (colors, spacing, typography) in `tailwind.config.js` — single source of truth
- Components are code-owned — agent can modify any component
- shadcn/ui has excellent documentation for AI agents (well-known patterns)

**Negative:**
- Migration effort: existing App.css must be replaced with Tailwind classes
- Vite needs `@tailwindcss/vite` or PostCSS plugin configuration
- Bundle size increases (~50KB gzipped for Radix primitives used)
- Learning curve: shadcn/ui requires understanding Tailwind utility classes

## Alternatives Considered

### Mantine v7
- Pros: All-in-one, 100+ components, excellent DX, built-in hooks
- Cons: Runtime dependency (must track Mantine version), opinionated theming
  (harder to customize than shadcn), heavier bundle (~120KB gzip), a11y
  quality varies across components
- Rejected: adds a runtime dependency and reduces customization control

### Chakra UI v3
- Pros: Composable, good a11y, well-documented
- Cons: v3 is a major rewrite with breaking changes, requires Emotion
  (runtime CSS-in-JS), bundle size ~80KB gzip, theme customization is
  verbose
- Rejected: CSS-in-JS runtime overhead and version transition risk

### Ant Design v5
- Pros: 60+ components, enterprise look
- Cons: Opinionated design (looks "Ant", not "AB Platform"), bundle ~150KB
  gzip, a11y gaps, customization is painful (less variables)
- Rejected: too opinionated, not a good fit for a product that wants its
  own visual identity

### Building from scratch with Radix UI directly
- Pros: Maximum control, no vendored code
- Cons: Significant implementation effort for dialogs, tables, dropdowns,
  tabs — every component built manually
- Rejected: shadcn/ui already wraps Radix with sensible defaults and
  full ownership — no benefit to going raw
