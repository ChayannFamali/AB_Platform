"""
RBAC service (M-003, ADR-006).

Provides:
- ROLE_PERMISSIONS matrix — single source of truth for the permission → roles
  mapping. Used to build the FastAPI `require_permission` dependency and to seed
  the role_permissions table on first migration.
- `require_permission(permission)` — FastAPI dependency factory. Returns a
  callable that resolves the current user (eager-loaded with roles+permissions)
  and 403s if the user lacks the requested permission.
- `get_user_permissions(user)` — collects all permissions across the user's
  roles (set union). Cheap O(R*P) in Python, no extra DB roundtrip.
- `assign_role`, `revoke_role`, `list_users_with_roles` — admin-only helpers
  used by the roles router.

NOTE: scope checks for SDK API keys live in `auth_service.verify_api_key` and
`dependencies.get_sdk_auth`, NOT here. RBAC governs UI (JWT) endpoints.
"""
from typing import Iterable

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import Role, RolePermission, User, UserRole


# ── Permission matrix (single source of truth) ──────────────────────────────
#
# Keys are stable identifiers (string-snake-case, `:` namespace separator).
# Any new permission MUST be added here AND seeded into role_permissions
# via migration (or runtime admin endpoint).

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "experiments:read", "experiments:create", "experiments:update",
        "experiments:delete", "experiments:analyze",
        "flags:read", "flags:write",
        "segments:read", "segments:write",
        "metrics:read", "metrics:write",
        "guardrails:read", "guardrails:write",
        "holdouts:read", "holdouts:write",
        "results:read", "decisions:write",
        "webhooks:manage",
        "users:manage", "roles:manage",
        "audit:read", "settings:manage",
    }),
    "editor": frozenset({
        "experiments:read", "experiments:create", "experiments:update",
        "experiments:analyze",
        "flags:read", "flags:write",
        "segments:read", "segments:write",
        "metrics:read", "metrics:write",
        "guardrails:read", "guardrails:write",
        "holdouts:read", "holdouts:write",
        "results:read", "decisions:write",
        "webhooks:manage", "audit:read",
    }),
    "analyst": frozenset({
        "experiments:read", "experiments:analyze",
        "flags:read", "segments:read",
        "metrics:read", "guardrails:read",
        "holdouts:read", "results:read", "audit:read",
    }),
    "viewer": frozenset({
        "experiments:read", "flags:read", "segments:read",
        "metrics:read", "guardrails:read",
        "holdouts:read", "results:read",
    }),
}


def get_role_permissions(role_key: str) -> frozenset[str]:
    """Lookup helper; empty frozenset for unknown roles (safe default)."""
    return ROLE_PERMISSIONS.get(role_key, frozenset())


# ── User → permissions ──────────────────────────────────────────────────────

def get_user_permissions(user: User) -> set[str]:
    """
    Aggregate permissions from all roles assigned to the user.

    Requires `user.roles[*].permissions` to be eager-loaded
    (handled in `dependencies.get_current_user`).
    """
    perms: set[str] = set()
    for role in getattr(user, "roles", []) or []:
        for perm in getattr(role, "permissions", []) or []:
            perms.add(perm.permission)
    return perms


# ── FastAPI dependency ──────────────────────────────────────────────────────

def require_permission(permission: str):
    """
    Returns a FastAPI dependency that resolves the current user and verifies
    they hold `permission`. Raises 403 if not.

    Usage:
        @router.post("/experiments", dependencies=[Depends(require_permission("experiments:create"))])
    """
    async def _checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if permission not in get_user_permissions(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Отсутствует право: {permission}",
            )
        return current_user
    return _checker


# ── Role / user-role mutations (admin only) ─────────────────────────────────

async def get_role_by_key(db: AsyncSession, key: str) -> Role | None:
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.key == key)
    )
    return result.scalar_one_or_none()


async def _load_user_with_roles(db: AsyncSession, user_id) -> User | None:
    """
    Single-user lookup with eager-loaded roles → permissions.

    Used by `dependencies.get_current_user` and by auth routes that need to
    serialize roles/permissions into the response. The eager-load ensures
    no lazy queries when `get_user_permissions` runs in `require_permission`.
    """
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
        )
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_role_by_id(db: AsyncSession, role_id) -> Role | None:
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    return result.scalar_one_or_none()


async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.key)
    )
    return list(result.scalars().all())


async def create_role(
    db: AsyncSession,
    key: str,
    name: str,
    description: str | None,
    permissions: Iterable[str],
) -> Role:
    role = Role(key=key, name=name, description=description)
    role.permissions = [RolePermission(permission=p) for p in permissions]
    db.add(role)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Роль с ключом «{key}» уже существует",
        )
    await db.refresh(role)
    return role


async def update_role(
    db: AsyncSession,
    role: Role,
    name: str | None,
    description: str | None,
    permissions: Iterable[str] | None,
) -> Role:
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if permissions is not None:
        # Replace permission set wholesale (simpler than diff).
        # Removing all and re-adding inside the same flush keeps the cascade
        # delete-orphan behavior on Role.permissions clean.
        role.permissions = [RolePermission(permission=p) for p in permissions]
    await db.flush()
    await db.refresh(role)
    return role


async def assign_role(
    db: AsyncSession, user_id, role_id
) -> UserRole:
    """Assign role to user; idempotent (returns existing assignment if any)."""
    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        return row

    assignment = UserRole(user_id=user_id, role_id=role_id)
    db.add(assignment)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Роль уже назначена пользователю",
        )
    await db.refresh(assignment)
    return assignment


async def revoke_role(
    db: AsyncSession, user_id, role_id
) -> bool:
    result = await db.execute(
        delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role_id,
        )
    )
    return result.rowcount > 0


async def list_users_with_roles(
    db: AsyncSession, limit: int, offset: int, role_key: str | None = None
) -> tuple[list[User], int]:
    from sqlalchemy import func

    stmt = select(User).options(
        selectinload(User.roles).selectinload(Role.permissions),
        selectinload(User.api_keys),
    )
    count_stmt = select(func.count(User.id))

    if role_key:
        stmt = stmt.join(UserRole, UserRole.user_id == User.id).join(
            Role, Role.id == UserRole.role_id,
        ).where(Role.key == role_key)
        count_stmt = count_stmt.join(UserRole, UserRole.user_id == User.id).join(
            Role, Role.id == UserRole.role_id,
        ).where(Role.key == role_key)

    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
    users = list((await db.execute(stmt)).scalars().unique().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return users, total


async def set_user_active(
    db: AsyncSession, user_id, is_active: bool
) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.is_active = is_active
    await db.flush()
    await db.refresh(user)
    return user