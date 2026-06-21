"""
Holdout router (M-010).

UI endpoints (JWT + RBAC `holdouts:read` / `holdouts:write`):

  GET    /api/v1/holdouts                       — paginated list (holdouts:read)
  POST   /api/v1/holdouts                       — create group (holdouts:write)
  GET    /api/v1/holdouts/{id}                  — get by id (holdouts:read)
  GET    /api/v1/holdouts/by-key/{key}          — get by stable key (holdouts:read)
  PATCH  /api/v1/holdouts/{id}                  — partial update (holdouts:write)
  DELETE /api/v1/holdouts/{id}                  — delete group + exclusions (holdouts:write)
  GET    /api/v1/holdouts/{id}/exclusions       — list manual exclusions (holdouts:read)
  POST   /api/v1/holdouts/{id}/exclusions       — add manual exclusion (holdouts:write)
  DELETE /api/v1/holdouts/{id}/exclusions/{user_id} — remove exclusion (holdouts:write)

Mutations audit-log under `resource_type="holdout_group"` for group
operations and `resource_type="holdout_exclusion"` for per-user actions.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import HoldoutExclusion, HoldoutGroup, User
from app.schemas.holdout import (
    HoldoutExclusionCreate,
    HoldoutExclusionResponse,
    HoldoutGroupCreate,
    HoldoutGroupListItem,
    HoldoutGroupResponse,
    HoldoutGroupUpdate,
    PaginatedExclusions,
    PaginatedHoldouts,
)
from app.services import audit_service, holdout_service, rbac_service

router = APIRouter(
    prefix="/api/v1/holdouts",
    tags=["holdouts"],
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _group_response(group: HoldoutGroup) -> HoldoutGroupResponse:
    return HoldoutGroupResponse(
        id=group.id,
        key=group.key,
        name=group.name,
        description=group.description,
        size_pct=group.size_pct,
        is_active=group.is_active,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at,
        exclusions_count=len(group.exclusions or []),
        experiments_count=len(group.experiments or []),
    )


def _group_list_item(group: HoldoutGroup) -> HoldoutGroupListItem:
    return HoldoutGroupListItem(
        id=group.id,
        key=group.key,
        name=group.name,
        description=group.description,
        size_pct=group.size_pct,
        is_active=group.is_active,
        exclusions_count=len(group.exclusions or []),
        experiments_count=len(group.experiments or []),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _exclusion_response(e: HoldoutExclusion) -> HoldoutExclusionResponse:
    return HoldoutExclusionResponse.model_validate(e)


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedHoldouts)
async def list_holdouts(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("holdouts:read")),
):
    items, total = await holdout_service.list_holdouts(db, limit, offset)
    return PaginatedHoldouts(
        items=[_group_list_item(g) for g in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post("", response_model=HoldoutGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_holdout(
    body: HoldoutGroupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("holdouts:write")),
):
    group = await holdout_service.create_holdout(db, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="holdout_group",
        resource_id=group.id,
        details=holdout_service.holdout_audit_details(group),
        request=request,
    )
    return _group_response(group)


@router.get("/by-key/{group_key}", response_model=HoldoutGroupResponse)
async def get_holdout_by_key(
    group_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("holdouts:read")),
):
    group = await holdout_service.get_holdout_by_key(db, group_key)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return _group_response(group)


@router.get("/{group_id}", response_model=HoldoutGroupResponse)
async def get_holdout(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("holdouts:read")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return _group_response(group)


@router.patch("/{group_id}", response_model=HoldoutGroupResponse)
async def update_holdout(
    group_id: UUID,
    body: HoldoutGroupUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("holdouts:write")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    previous_size = group.size_pct
    previous_active = group.is_active
    group = await holdout_service.update_holdout(db, group, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="holdout_group",
        resource_id=group.id,
        details={
            **holdout_service.holdout_audit_details(group),
            "fields_changed": [
                f for f in ("name", "description", "size_pct", "is_active")
                if getattr(body, f) is not None
            ],
            "previous_size_pct":  previous_size,
            "previous_is_active": previous_active,
        },
        request=request,
    )
    return _group_response(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holdout(
    group_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("holdouts:write")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    details = holdout_service.holdout_audit_details(group)
    await holdout_service.delete_holdout(db, group)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="holdout_group",
        resource_id=group_id,
        details=details,
        request=request,
    )


# ── Exclusions ─────────────────────────────────────────────────────────────


@router.get(
    "/{group_id}/exclusions",
    response_model=PaginatedExclusions,
)
async def list_exclusions(
    group_id: UUID,
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("holdouts:read")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    items, total = await holdout_service.list_exclusions(
        db, group, limit, offset,
    )
    return PaginatedExclusions(
        items=[_exclusion_response(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post(
    "/{group_id}/exclusions",
    response_model=HoldoutExclusionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_exclusion(
    group_id: UUID,
    body: HoldoutExclusionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("holdouts:write")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    exclusion = await holdout_service.add_exclusion(db, group, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="holdout_exclusion",
        # resource_id is a UUID column — use the group id and put the
        # user_id in details (see HoldoutExclusionAdd audit contract).
        resource_id=group.id,
        details={
            "group_key": group.key,
            "user_id":   exclusion.user_id,
            "reason":    exclusion.reason,
        },
        request=request,
    )
    return _exclusion_response(exclusion)


@router.delete(
    "/{group_id}/exclusions/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_exclusion(
    group_id: UUID,
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("holdouts:write")),
):
    group = await holdout_service.get_holdout_by_id(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    removed = await holdout_service.remove_exclusion(db, group, user_id)
    if removed:
        await audit_service.log_action(
            db,
            actor=actor,
            action="delete",
            resource_type="holdout_exclusion",
            resource_id=group.id,
            details={
                "group_key": group.key,
                "user_id":   user_id,
            },
            request=request,
        )
