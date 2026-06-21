"""
Feature flag router (M-009, ADR-004).

UI endpoints (JWT, RBAC):
  GET    /api/v1/flags           — paginated list (flags:read)
  POST   /api/v1/flags           — create flag (flags:write)
  GET    /api/v1/flags/{id}      — get by id (flags:read)
  GET    /api/v1/flags/by-key/{key} — get by stable key (flags:read)
  PATCH  /api/v1/flags/{id}      — partial update (flags:write)
  PATCH  /api/v1/flags/{id}/toggle — kill switch (flags:write)
  DELETE /api/v1/flags/{id}      — delete flag + rules (flags:write)
  POST   /api/v1/flags/{id}/rules — add rule (flags:write)
  DELETE /api/v1/flags/{id}/rules/{rule_id} — delete rule (flags:write)
  GET    /api/v1/flags/summary  — counts for dashboard (flags:read)

SDK endpoints (X-API-Key, scope):
  POST /api/v1/sdk/flags/evaluate        — single (flags:read)
  POST /api/v1/sdk/flags/evaluate-batch  — batch  (flags:read)

Audit hooks: every mutation appends an `audit_log` row with
`resource_type="feature_flag"`. Rule operations are logged under the
parent flag with the rule's id in `details`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_sdk_scope
from app.models.db import FeatureFlag, FlagRule, User
from app.schemas.flag import (
    FeatureFlagCreate,
    FeatureFlagListItem,
    FeatureFlagResponse,
    FeatureFlagToggle,
    FeatureFlagUpdate,
    FlagEvaluateBatchRequest,
    FlagEvaluateBatchResponse,
    FlagEvaluateRequest,
    FlagEvaluateResponse,
    FlagRuleCreate,
    FlagRuleResponse,
    FlagsSummary,
    PaginatedFlags,
)
from app.services import audit_service, flag_service, rbac_service

# UI router — JWT + RBAC.
router = APIRouter(
    prefix="/api/v1/flags",
    tags=["flags"],
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _flag_response(flag: FeatureFlag) -> FeatureFlagResponse:
    return FeatureFlagResponse.model_validate(flag)


def _flag_list_item(flag: FeatureFlag) -> FeatureFlagListItem:
    return FeatureFlagListItem.model_validate(flag)


def _rule_response(rule: FlagRule) -> FlagRuleResponse:
    return FlagRuleResponse.model_validate(rule)


# ── CRUD ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedFlags)
async def list_flags(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    enabled: bool | None = Query(default=None, description="Filter by enabled state"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("flags:read")),
):
    items, total = await flag_service.list_flags(db, limit, offset, enabled)
    summary = await flag_service.list_flags_summary(db)
    return PaginatedFlags(
        items=[_flag_list_item(f) for f in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
        summary=summary,
    )


@router.get("/summary", response_model=FlagsSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("flags:read")),
):
    """
    Aggregate counts for the dashboard "Active flags" card.

    Kept separate from the list endpoint so the dashboard doesn't have to
    page through the whole table to read the counts.
    """
    return await flag_service.list_flags_summary(db)


@router.post("", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(
    body: FeatureFlagCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    flag = await flag_service.create_flag(db, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="feature_flag",
        resource_id=flag.id,
        details=flag_service.flag_audit_details(flag),
        request=request,
    )
    return _flag_response(flag)


@router.get("/by-key/{flag_key}", response_model=FeatureFlagResponse)
async def get_flag_by_key(
    flag_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("flags:read")),
):
    flag = await flag_service.get_flag_by_key(db, flag_key)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    return _flag_response(flag)


@router.get("/{flag_id}", response_model=FeatureFlagResponse)
async def get_flag(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("flags:read")),
):
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    return _flag_response(flag)


@router.patch("/{flag_id}", response_model=FeatureFlagResponse)
async def update_flag(
    flag_id: UUID,
    body: FeatureFlagUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    flag = await flag_service.update_flag(db, flag, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="feature_flag",
        resource_id=flag.id,
        details={
            **flag_service.flag_audit_details(flag),
            "fields_changed": [
                f for f in ("name", "description", "enabled", "rollout_percentage")
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _flag_response(flag)


@router.patch("/{flag_id}/toggle", response_model=FeatureFlagResponse)
async def toggle_flag(
    flag_id: UUID,
    body: FeatureFlagToggle,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    """Quick kill switch — separate from PATCH so the UI can optimistic-toggle."""
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    previous = flag.enabled
    flag = await flag_service.toggle_flag(db, flag, body.enabled)
    await audit_service.log_action(
        db,
        actor=actor,
        action="toggle_enabled",
        resource_type="feature_flag",
        resource_id=flag.id,
        details={
            "key": flag.key,
            "enabled": flag.enabled,
            "previous_state": previous,
        },
        request=request,
    )
    return _flag_response(flag)


@router.delete("/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flag(
    flag_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    details = flag_service.flag_audit_details(flag)
    await flag_service.delete_flag(db, flag)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="feature_flag",
        resource_id=flag_id,
        details=details,
        request=request,
    )


# ── Rule CRUD (segment support reserved for M-010) ─────────────────────────


@router.post(
    "/{flag_id}/rules",
    response_model=FlagRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_rule(
    flag_id: UUID,
    body: FlagRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    rule = await flag_service.add_rule(db, flag, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="add_rule",
        resource_type="feature_flag",
        resource_id=flag.id,
        details={
            "flag_key": flag.key,
            "rule_id": str(rule.id),
            "priority": rule.priority,
            "rollout_percentage": rule.rollout_percentage,
            "segment_id": str(rule.segment_id) if rule.segment_id else None,
        },
        request=request,
    )
    return _rule_response(rule)


@router.delete(
    "/{flag_id}/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    flag_id: UUID,
    rule_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("flags:write")),
):
    flag = await flag_service.get_flag_by_id(db, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Флаг не найден")
    # Find rule via relationship to avoid a stray query.
    rule = next((r for r in (flag.rules or []) if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    details = {
        "flag_key": flag.key,
        "rule_id": str(rule.id),
        "priority": rule.priority,
        "rollout_percentage": rule.rollout_percentage,
    }
    await flag_service.delete_rule(db, rule)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete_rule",
        resource_type="feature_flag",
        resource_id=flag.id,
        details=details,
        request=request,
    )


# ── SDK endpoints (separate router so they live under /sdk) ─────────────────


sdk_router = APIRouter(
    prefix="/api/v1/sdk/flags",
    tags=["sdk"],
)


@sdk_router.post(
    "/evaluate",
    response_model=FlagEvaluateResponse,
)
async def sdk_evaluate_flag(
    data: FlagEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_sdk_scope("flags:read")),
):
    """Single-flag evaluation. Returns the boolean result + reason.

    M-010: forwards optional `user_properties` to segment-aware evaluation.
    """
    value, reason, _ = await flag_service.evaluate_flag(
        db, data.user_id, data.flag_key, data.user_properties or None,
    )
    return FlagEvaluateResponse(key=data.flag_key, value=value, reason=reason)


@sdk_router.post(
    "/evaluate-batch",
    response_model=FlagEvaluateBatchResponse,
)
async def sdk_evaluate_flags_batch(
    data: FlagEvaluateBatchRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_sdk_scope("flags:read")),
):
    """Batch evaluation — preferred for SDK startup.

    M-010: forwards optional `user_properties` so segment targeting is
    evaluated uniformly across all keys in the batch.
    """
    results = await flag_service.evaluate_flags(
        db, data.user_id, data.flag_keys, data.user_properties or None,
    )
    values: dict[str, bool] = {}
    details: dict[str, dict[str, str]] = {}
    for key, (value, reason, _) in results.items():
        values[key] = value
        details[key] = {"value": "true" if value else "false", "reason": reason}
    return FlagEvaluateBatchResponse(values=values, details=details)