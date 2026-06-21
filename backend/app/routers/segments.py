"""
Segment router (M-010).

UI endpoints (JWT + RBAC `segments:read` / `segments:write`):

  GET    /api/v1/segments                    — paginated list (segments:read)
  POST   /api/v1/segments                    — create with rules (segments:write)
  GET    /api/v1/segments/{id}               — get by id (segments:read)
  GET    /api/v1/segments/by-key/{key}       — get by stable key (segments:read)
  PATCH  /api/v1/segments/{id}               — partial update (segments:write)
  DELETE /api/v1/segments/{id}               — delete segment + rules (segments:write)
  POST   /api/v1/segments/{id}/rules         — add single rule (segments:write)
  DELETE /api/v1/segments/{id}/rules/{rule_id} — delete rule (segments:write)
  POST   /api/v1/segments/{id}/evaluate      — dry-run against user_properties (segments:read)
  POST   /api/v1/segments/{id}/experiments   — link to experiments (segments:write)
  DELETE /api/v1/segments/{id}/experiments/{experiment_id} — unlink (segments:write)

All mutations write an `audit_log` row with `resource_type="segment"`
or `"segment_rule"`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Segment, SegmentRule, User
from app.schemas.segment import (
    PaginatedSegments,
    SegmentCreate,
    SegmentEvaluateRequest,
    SegmentEvaluateResponse,
    SegmentExperimentLink,
    SegmentLinkRequest,
    SegmentListItem,
    SegmentResponse,
    SegmentRuleCreate,
    SegmentRuleResponse,
    SegmentUpdate,
)
from app.services import audit_service, rbac_service, segment_service

router = APIRouter(
    prefix="/api/v1/segments",
    tags=["segments"],
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _segment_response(segment: Segment) -> SegmentResponse:
    return SegmentResponse.model_validate(segment)


def _segment_list_item(segment: Segment) -> SegmentListItem:
    return SegmentListItem(
        id=segment.id,
        key=segment.key,
        name=segment.name,
        description=segment.description,
        rules_count=len(segment.rules or []),
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


def _rule_response(rule: SegmentRule) -> SegmentRuleResponse:
    return SegmentRuleResponse.model_validate(rule)


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedSegments)
async def list_segments(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("segments:read")),
):
    items, total = await segment_service.list_segments(db, limit, offset)
    return PaginatedSegments(
        items=[_segment_list_item(s) for s in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    body: SegmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.create_segment(db, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="segment",
        resource_id=segment.id,
        details=segment_service.segment_audit_details(segment),
        request=request,
    )
    return _segment_response(segment)


@router.get("/by-key/{segment_key}", response_model=SegmentResponse)
async def get_segment_by_key(
    segment_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("segments:read")),
):
    segment = await segment_service.get_segment_by_key(db, segment_key)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    return _segment_response(segment)


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("segments:read")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    return _segment_response(segment)


@router.patch("/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: UUID,
    body: SegmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    segment = await segment_service.update_segment(db, segment, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="segment",
        resource_id=segment.id,
        details={
            **segment_service.segment_audit_details(segment),
            "fields_changed": [
                f for f in ("name", "description", "rules")
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _segment_response(segment)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    details = segment_service.segment_audit_details(segment)
    await segment_service.delete_segment(db, segment)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="segment",
        resource_id=segment_id,
        details=details,
        request=request,
    )


# ── Rule CRUD ──────────────────────────────────────────────────────────────


@router.post(
    "/{segment_id}/rules",
    response_model=SegmentRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_rule(
    segment_id: UUID,
    body: SegmentRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    rule = await segment_service.add_rule(db, segment, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="add_rule",
        resource_type="segment",
        resource_id=segment.id,
        details={
            "segment_key": segment.key,
            "rule_id":     str(rule.id),
            "field":       rule.field,
            "operator":    rule.operator,
            "priority":    rule.priority,
        },
        request=request,
    )
    return _rule_response(rule)


@router.delete(
    "/{segment_id}/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    segment_id: UUID,
    rule_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    rule = next((r for r in (segment.rules or []) if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    details = {
        "segment_key": segment.key,
        "rule_id":     str(rule.id),
        "field":       rule.field,
        "operator":    rule.operator,
    }
    await segment_service.delete_rule(db, rule)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete_rule",
        resource_type="segment",
        resource_id=segment.id,
        details=details,
        request=request,
    )


# ── Dry-run evaluation ─────────────────────────────────────────────────────


@router.post(
    "/{segment_id}/evaluate",
    response_model=SegmentEvaluateResponse,
)
async def evaluate_segment(
    segment_id: UUID,
    body: SegmentEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("segments:read")),
):
    """
    Debug endpoint: dry-run a segment against a hypothetical user
    properties payload. Returns per-rule breakdown for the UI's
    SegmentPreview component.
    """
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    return segment_service.evaluate_segment(segment, body.user_properties)


# ── Experiment linking (M2M) ──────────────────────────────────────────────


@router.post(
    "/{segment_id}/experiments",
    response_model=list[SegmentExperimentLink],
    status_code=status.HTTP_201_CREATED,
)
async def link_experiments(
    segment_id: UUID,
    body: SegmentLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    inserted = await segment_service.link_segment_to_experiments(
        db, segment, body.experiment_ids,
    )
    if inserted > 0:
        await audit_service.log_action(
            db,
            actor=actor,
            action="link_experiments",
            resource_type="segment",
            resource_id=segment.id,
            details={
                "segment_key":     segment.key,
                "experiment_ids":  [str(eid) for eid in body.experiment_ids],
                "rows_inserted":   inserted,
            },
            request=request,
        )
    return [
        SegmentExperimentLink(experiment_id=eid, segment_id=segment.id)
        for eid in body.experiment_ids
    ]


@router.delete(
    "/{segment_id}/experiments/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_experiment(
    segment_id: UUID,
    experiment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("segments:write")),
):
    segment = await segment_service.get_segment_by_id(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Сегмент не найден")
    removed = await segment_service.unlink_segment_from_experiment(
        db, segment, experiment_id,
    )
    if removed:
        await audit_service.log_action(
            db,
            actor=actor,
            action="unlink_experiment",
            resource_type="segment",
            resource_id=segment.id,
            details={
                "segment_key":   segment.key,
                "experiment_id": str(experiment_id),
            },
            request=request,
        )
