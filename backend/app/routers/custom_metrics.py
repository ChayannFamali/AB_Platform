"""
Custom metric router (M-011).

UI endpoints (JWT + RBAC `metrics:read` / `metrics:write`):

  GET    /api/v1/custom-metrics                 — paginated list (metrics:read)
  POST   /api/v1/custom-metrics                 — create template (metrics:write)
  GET    /api/v1/custom-metrics/{id}            — get by id (metrics:read)
  GET    /api/v1/custom-metrics/by-key/{key}    — get by stable key (metrics:read)
  PATCH  /api/v1/custom-metrics/{id}            — partial update (metrics:write)
  DELETE /api/v1/custom-metrics/{id}            — delete template (metrics:write)
  POST   /api/v1/custom-metrics/{id}/preview    — dry-run filters against
                                                   a hypothetical user_properties
                                                   payload (metrics:read).

All mutations append an `audit_log` row with `resource_type =
"custom_metric"`. Deletion does NOT cascade to per-experiment Metric
rows (custom_metric_id FK is ON DELETE SET NULL).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import CustomMetric, User
from app.schemas.custom_metric import (
    CustomMetricCreate,
    CustomMetricListItem,
    CustomMetricPreviewRequest,
    CustomMetricPreviewResponse,
    CustomMetricResponse,
    CustomMetricUpdate,
    PaginatedCustomMetrics,
)
from app.services import audit_service, custom_metric_service, rbac_service

router = APIRouter(
    prefix="/api/v1/custom-metrics",
    tags=["custom-metrics"],
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _response(
    metric: CustomMetric, *, used_by_count: int = 0
) -> CustomMetricResponse:
    return CustomMetricResponse(
        id=metric.id,
        key=metric.key,
        name=metric.name,
        description=metric.description,
        event_name=metric.event_name,
        aggregation=metric.aggregation,
        metric_type=metric.metric_type,
        filters=metric.filters,
        denominator_event_name=metric.denominator_event_name,
        denominator_aggregation=metric.denominator_aggregation,
        denominator_filters=metric.denominator_filters,
        is_guardrail=metric.is_guardrail,
        created_by=metric.created_by,
        created_at=metric.created_at,
        updated_at=metric.updated_at,
        used_by_count=used_by_count,
    )


def _list_item(
    metric: CustomMetric, *, used_by_count: int = 0
) -> CustomMetricListItem:
    return CustomMetricListItem(
        id=metric.id,
        key=metric.key,
        name=metric.name,
        description=metric.description,
        event_name=metric.event_name,
        aggregation=metric.aggregation,
        metric_type=metric.metric_type,
        is_guardrail=metric.is_guardrail,
        used_by_count=used_by_count,
        created_at=metric.created_at,
        updated_at=metric.updated_at,
    )


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedCustomMetrics)
async def list_custom_metrics(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("metrics:read")),
):
    items, total = await custom_metric_service.list_custom_metrics(db, limit, offset)
    used_by = await custom_metric_service.count_used_by(
        db, [m.id for m in items]
    )
    return PaginatedCustomMetrics(
        items=[_list_item(m, used_by_count=used_by.get(m.id, 0)) for m in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post("", response_model=CustomMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_metric(
    body: CustomMetricCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("metrics:write")),
):
    metric = await custom_metric_service.create_custom_metric(db, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="custom_metric",
        resource_id=metric.id,
        details=custom_metric_service.custom_metric_audit_details(metric),
        request=request,
    )
    return _response(metric)


@router.get("/by-key/{metric_key}", response_model=CustomMetricResponse)
async def get_custom_metric_by_key(
    metric_key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("metrics:read")),
):
    metric = await custom_metric_service.get_custom_metric_by_key(db, metric_key)
    if not metric:
        raise HTTPException(status_code=404, detail="Кастомная метрика не найдена")
    used_by = await custom_metric_service.count_used_by(db, [metric.id])
    return _response(metric, used_by_count=used_by.get(metric.id, 0))


@router.get("/{metric_id}", response_model=CustomMetricResponse)
async def get_custom_metric(
    metric_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("metrics:read")),
):
    metric = await custom_metric_service.get_custom_metric_by_id(db, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Кастомная метрика не найдена")
    used_by = await custom_metric_service.count_used_by(db, [metric.id])
    return _response(metric, used_by_count=used_by.get(metric.id, 0))


@router.patch("/{metric_id}", response_model=CustomMetricResponse)
async def update_custom_metric(
    metric_id: UUID,
    body: CustomMetricUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("metrics:write")),
):
    metric = await custom_metric_service.get_custom_metric_by_id(db, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Кастомная метрика не найдена")
    metric = await custom_metric_service.update_custom_metric(db, metric, body)
    used_by = await custom_metric_service.count_used_by(db, [metric.id])
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="custom_metric",
        resource_id=metric.id,
        details={
            **custom_metric_service.custom_metric_audit_details(
                metric, used_by_count=used_by.get(metric.id, 0),
            ),
            "fields_changed": [
                f for f in (
                    "name", "description", "filters",
                    "denominator_event_name", "denominator_aggregation",
                    "denominator_filters", "is_guardrail",
                )
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _response(metric, used_by_count=used_by.get(metric.id, 0))


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_metric(
    metric_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("metrics:write")),
):
    metric = await custom_metric_service.get_custom_metric_by_id(db, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Кастомная метрика не найдена")
    used_by = await custom_metric_service.count_used_by(db, [metric.id])
    used_by_count = used_by.get(metric.id, 0)
    details = custom_metric_service.custom_metric_audit_details(
        metric, used_by_count=used_by_count,
    )
    await custom_metric_service.delete_custom_metric(db, metric)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="custom_metric",
        resource_id=metric_id,
        details={
            **details,
            "warning": (
                "Per-experiment Metric rows keep their snapshotted copy; "
                "custom_metric_id FK is set to NULL."
            ) if used_by_count else None,
        },
        request=request,
    )


# ── Dry-run preview ────────────────────────────────────────────────────────


@router.post(
    "/{metric_id}/preview",
    response_model=CustomMetricPreviewResponse,
)
async def preview_custom_metric(
    metric_id: UUID,
    body: CustomMetricPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("metrics:read")),
):
    """
    Debug endpoint: render a plain-English summary of the metric
    definition and dry-run its filter list against a hypothetical
    `user_properties` payload. Powers the side-panel preview in the
    metric builder.
    """
    metric = await custom_metric_service.get_custom_metric_by_id(db, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Кастомная метрика не найдена")
    return custom_metric_service.evaluate_preview(metric, body.user_properties)
