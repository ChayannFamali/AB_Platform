# ADR-006: RBAC Model — Role-Based vs Attribute-Based Access Control

## Status
Accepted

## Context

The platform currently has a single `is_admin` boolean on the `User` model.
The first registered user becomes admin; all others are non-admin. This is
insufficient for a multi-user platform where:
- Analysts need to view results and create experiments but not manage users
- Editors need to create/modify experiments and flags but not delete them
- Viewers need read-only access (dashboards, results)
- Admins need full control (users, roles, settings, deletion)

The platform needs role-based access control (RBAC) for these personas.
The question is: simple RBAC (role → permissions) or ABAC (attribute-based,
where permissions depend on resource attributes like "experiment owner")?

## Decision

**Use Role-Based Access Control (RBAC)** with a fixed set of roles and a
permission matrix. No ABAC.

### Roles
| Role | Key | Description |
|------|-----|-------------|
| Admin | `admin` | Full control. Can manage users, roles, system settings, delete anything. |
| Editor | `editor` | Can create/modify experiments, flags, segments, metrics, webhooks. Cannot delete experiments or manage users. |
| Analyst | `analyst` | Can view everything, run analysis, create sample size calculations. Cannot create/modify experiments or flags. Read-only + analysis. |
| Viewer | `viewer` | Read-only. Can view dashboards, results, flags. No mutations. |

### Permission matrix
| Permission | admin | editor | analyst | viewer |
|------------|:------|:-------|:--------|:------|
| `experiments:read` | ✓ | ✓ | ✓ | ✓ |
| `experiments:create` | ✓ | ✓ | | |
| `experiments:update` | ✓ | ✓ | | |
| `experiments:delete` | ✓ | | | |
| `experiments:analyze` | ✓ | ✓ | ✓ | |
| `flags:read` | ✓ | ✓ | ✓ | ✓ |
| `flags:write` | ✓ | ✓ | | |
| `segments:read` | ✓ | ✓ | ✓ | ✓ |
| `segments:write` | ✓ | ✓ | | |
| `metrics:read` | ✓ | ✓ | ✓ | ✓ |
| `metrics:write` | ✓ | ✓ | | |
| `guardrails:read` | ✓ | ✓ | ✓ | ✓ |
| `guardrails:write` | ✓ | ✓ | | |
| `holdouts:read` | ✓ | ✓ | ✓ | ✓ |
| `holdouts:write` | ✓ | ✓ | | |
| `results:read` | ✓ | ✓ | ✓ | ✓ |
| `decisions:write` | ✓ | ✓ | | |
| `webhooks:manage` | ✓ | ✓ | | |
| `users:manage` | ✓ | | | |
| `roles:manage` | ✓ | | | |
| `audit:read` | ✓ | ✓ | ✓ | |
| `settings:manage` | ✓ | | | |

### Data model
```sql
roles (id UUID PK, key TEXT UNIQUE, name TEXT, description TEXT)
role_permissions (role_id UUID FK, permission TEXT)  -- composite PK
user_roles (user_id UUID FK, role_id UUID FK)          -- composite PK
```

### Implementation
- `app/services/rbac_service.py`: `require_permission(permission)` FastAPI
  dependency — checks the current user's roles → permissions map
- `app/dependencies.py`: `get_current_user` extended to eagerly load
  roles + permissions
- Each router endpoint declares its required permission via
  `Depends(require_permission("experiments:create"))`
- The first registered user (currently `is_admin=true`) is migrated to
  the `admin` role in migration `0006`
- The `is_admin` boolean on `users` is retained but deprecated (read-only
  fallback in auth logic for one release cycle, then dropped in `0015`)

### API Key scopes
API keys (SDK) get a `scopes` JSONB field: `["assignments:read", "events:write"]`.
The SDK endpoints check scopes instead of RBAC permissions. Default scopes
on existing keys: `["assignments:read", "events:write"]` (preserves
backward compatibility — existing keys continue to work).

## Consequences

**Positive:**
- Simple to understand: user has role(s) → role has permissions → permission
  check is a set lookup
- Simple to implement: one decorator/dependency per endpoint
- Four roles cover all personas without combinatorial explosion
- Permission matrix is explicit and auditable
- API key scopes separate SDK auth from UI auth cleanly

**Negative:**
- No resource-level permissions (e.g., "editor can only edit their own
  experiments") — if needed later, ABAC must be added
- Granularity is at the action level, not the instance level — any editor
  can edit any experiment
- Adding a new permission requires a migration (add to `role_permissions`
  seed) — but this is intentional (explicit over implicit)

### Phase 2 consideration
If resource-level ownership becomes needed (e.g., "experiment owner can
edit their own experiment even if not editor"), we extend with a
`experiment.owner_id` column and a custom check — but this is NOT ABAC,
it's a simple ownership check layered on top of RBAC.

## Alternatives Considered

### ABAC (Attribute-Based Access Control)
- Pros: Resource-level granularity ("user can edit experiment if
  experiment.owner_id == user.id OR user.role == admin")
- Cons: Significantly more complex (policy engine, attribute evaluation,
  combinatorial rules), harder to audit ("why could this user do X?"),
  overkill for a platform with 4 personas and no multi-tenancy
- Rejected: complexity not justified by current requirements; RBAC +
  optional ownership check is sufficient

### Simple boolean flags (extend `is_admin` pattern)
- Pros: Zero new tables, one column per flag
- Cons: Combinatorial explosion (is_admin, is_editor, is_analyst, can_delete,
  can_create...), no permission matrix, hard to audit, inflexible
- Rejected: does not scale, no clear permission model

### CASL (npm package for JS-side authorization)
- Pros: Declarative, well-designed, isomorphic (can run frontend + backend)
- Cons: This is frontend-only; we need backend authorization. Backend is
  Python. CASL is JS-only. Would need a parallel Python implementation.
- Rejected: wrong ecosystem for backend auth; RBAC with explicit permission
  strings is simpler and language-agnostic
