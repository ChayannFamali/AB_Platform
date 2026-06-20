"""
Roles & user-role management (M-003).

All endpoints require the `users:manage` permission — admin-only.

Mutating endpoints also append an audit log row via `audit_service`
(M-004): every create / update / assign / revoke / toggle_active lands
in `audit_log` with the actor, target resource, and (where relevant) a
small details blob.

Endpoints:
  GET    /api/v1/roles             — list all roles with permissions
  POST   /api/v1/roles             — create a new role        [+ audit]
  PATCH  /api/v1/roles/{id}        — rename / description / permissions  [+ audit]
  GET    /api/v1/users             — list users with their roles + permissions
  PATCH  /api/v1/users/{id}        — toggle is_active         [+ audit]
  POST   /api/v1/users/{id}/roles  — assign role              [+ audit]
  DELETE /api/v1/users/{id}/roles/{role_id} — revoke role      [+ audit]
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Role, User
from app.schemas.rbac import (
    AssignRoleRequest,
    PaginatedRoles,
    PaginatedUsers,
    RoleCreate,
    RoleResponse,
    RoleSummary,
    RoleUpdate,
    UserRoleAssignmentResponse,
    UserUpdateRequest,
    UserWithRolesResponse,
)
from app.services import audit_service, rbac_service

router = APIRouter(
    prefix="/api/v1",
    tags=["roles"],
    dependencies=[Depends(rbac_service.require_permission("users:manage"))],
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        key=role.key,
        name=role.name,
        description=role.description,
        permissions=sorted(p.permission for p in role.permissions),
        created_at=role.created_at,
    )


def _user_response(user: User) -> UserWithRolesResponse:
    roles = [RoleSummary.model_validate(r) for r in (user.roles or [])]
    perms: set[str] = set()
    for r in (user.roles or []):
        for p in (r.permissions or []):
            perms.add(p.permission)
    return UserWithRolesResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        roles=roles,
        permissions=sorted(perms),
    )


# ── Roles CRUD ──────────────────────────────────────────────────────────────

@router.get("/roles", response_model=PaginatedRoles)
async def list_roles(db: AsyncSession = Depends(get_db)):
    roles = await rbac_service.list_roles(db)
    return PaginatedRoles(items=[_role_response(r) for r in roles], total=len(roles))


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("users:manage")),
):
    role = await rbac_service.create_role(
        db, body.key, body.name, body.description, body.permissions,
    )
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="role",
        resource_id=role.id,
        details={"key": role.key, "name": role.name, "permissions": sorted(body.permissions)},
        request=request,
    )
    return _role_response(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    body: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("users:manage")),
):
    role = await rbac_service.get_role_by_id(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    role = await rbac_service.update_role(
        db, role, body.name, body.description, body.permissions,
    )
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="role",
        resource_id=role.id,
        details={
            "key": role.key,
            "fields_changed": [
                f for f in ("name", "description", "permissions")
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _role_response(role)


# ── Users listing / update ──────────────────────────────────────────────────

@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    role:   str | None = Query(default=None, description="Фильтр по ключу роли"),
    db: AsyncSession = Depends(get_db),
):
    users, total = await rbac_service.list_users_with_roles(db, limit, offset, role)
    return PaginatedUsers(
        items=[_user_response(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.patch("/users/{user_id}", response_model=UserWithRolesResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("users:manage")),
):
    if body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не указано ни одного поля для обновления",
        )
    previous_active = (
        await db.execute(
            select(User.is_active).where(User.id == user_id)
        )
    ).scalar_one_or_none()
    user = await rbac_service.set_user_active(db, user_id, body.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    await audit_service.log_action(
        db,
        actor=actor,
        action="toggle_active",
        resource_type="user",
        resource_id=user.id,
        details={
            "username":      user.username,
            "is_active":     user.is_active,
            "previous_state": previous_active,
        },
        request=request,
    )
    return _user_response(user)


# ── User ↔ Role assignment ──────────────────────────────────────────────────

@router.post(
    "/users/{user_id}/roles",
    response_model=UserRoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("users:manage")),
):
    role = await rbac_service.get_role_by_id(db, body.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    assignment = await rbac_service.assign_role(db, user_id, body.role_id)
    await audit_service.log_action(
        db,
        actor=actor,
        action="assign",
        resource_type="user_role",
        resource_id=assignment.user_id,
        details={
            "user_id":    str(user.id),
            "username":   user.username,
            "role_id":    str(role.id),
            "role_key":   role.key,
        },
        request=request,
    )
    return UserRoleAssignmentResponse(
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_key=role.key,
        assigned_at=assignment.assigned_at,
    )


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_role(
    user_id: UUID,
    role_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("users:manage")),
):
    # Look up role/user for audit details before deletion
    role = await rbac_service.get_role_by_id(db, role_id)
    user = await rbac_service._load_user_with_roles(db, user_id)

    revoked = await rbac_service.revoke_role(db, user_id, role_id)
    if not revoked:
        raise HTTPException(
            status_code=404,
            detail="Связь пользователь↔роль не найдена",
        )
    await audit_service.log_action(
        db,
        actor=actor,
        action="revoke",
        resource_type="user_role",
        resource_id=user_id,
        details={
            "user_id":  str(user_id),
            "username": user.username if user else None,
            "role_id":  str(role_id),
            "role_key": role.key if role else None,
        },
        request=request,
    )