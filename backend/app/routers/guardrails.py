"""
Guardrail router (M-011).

UI endpoints (JWT + RBAC `guardrails:read` / `guardrails:write`):

  GET    /api/v1/experiments/{experiment_id}/guardrails
              — paginated list of guardrails for the experiment (guardrails:read)
  POST   /api/v1/experiments/{experiment_id}/guardrails
              — create guardrail (guardrails:write)
  PATCH  /api/v1/experiments/{experiment_id}/guardrails/{guardrail_id}
              — partial update (guardrails:write)
  DELETE /api/v1/experiments/{experiment_id}/guardrails/{guardrail_id}
              — delete (guardrails:write)

Guardrails are scoped to a specific experiment and a specific metric
row belonging to that experiment. The service layer enforces that
`metric.is_guardrail=True` is set before a config can be attached —
this catches the common wiring mistake of attaching a guardrail to a
non-guardrail metric.

All mutations append an `audit_log` row with
`resource_type="guardrail_config"`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Experiment, GuardrailConfig, User
from app.schemas.guardrail import (
    GuardrailCreate,
    GuardrailListItem,
    GuardrailResponse,
    GuardrailUpdate,
    PaginatedGuardrails,
)
from app.services import audit_service, guardrail_service, rbac_service

# Nested under /experiments — note: NO prefix on the router itself.
# The path /api/v1/experiments/{experiment_id}/guardrails is constructed
# here so the experiment id sits in the URL naturally and matches how
# the M-005 tab fetches its data.
router = APIRouter(
    prefix="/api/v1/experiments",
    tags=["guardrails"],
)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _load_experiment(
    db: AsyncSession, experiment_id: UUID
) -> Experiment | None:
    return (
        await db.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
    ).scalar_one_or_none()


def _response(config: GuardrailConfig) -> GuardrailResponse:
    return GuardrailResponse.model_validate(config)


def _list_item(config: GuardrailConfig) -> GuardrailListItem:
    return GuardrailListItem.model_validate(config)


# Lazy import — keeps the import graph clean and avoids cycles when
# `app.database` is mid-import.
from sqlalchemy import select  # noqa: E402


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get(
    "/{experiment_id}/guardrails",
    response_model=PaginatedGuardrails,
)
async def list_guardrails(
    experiment_id: UUID,
    limit:  int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("guardrails:read")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    items, total = await guardrail_service.list_guardrails_for_experiment(
        db, experiment_id, limit=limit, offset=offset,
    )
    return PaginatedGuardrails(
        items=[_list_item(g) for g in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post(
    "/{experiment_id}/guardrails",
    response_model=GuardrailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_guardrail(
    experiment_id: UUID,
    body: GuardrailCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("guardrails:write")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    config = await guardrail_service.create_guardrail(db, experiment, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="guardrail_config",
        resource_id=config.id,
        details={
            **guardrail_service.guardrail_audit_details(config),
            "experiment_id": str(experiment_id),
        },
        request=request,
    )
    return _response(config)


@router.patch(
    "/{experiment_id}/guardrails/{guardrail_id}",
    response_model=GuardrailResponse,
)
async def update_guardrail(
    experiment_id: UUID,
    guardrail_id: UUID,
    body: GuardrailUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("guardrails:write")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    config = await guardrail_service.get_guardrail_by_id(db, guardrail_id)
    if not config or config.experiment_id != experiment_id:
        raise HTTPException(status_code=404, detail="Guardrail не найден")
    config = await guardrail_service.update_guardrail(db, config, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="guardrail_config",
        resource_id=config.id,
        details={
            **guardrail_service.guardrail_audit_details(config),
            "experiment_id": str(experiment_id),
            "fields_changed": [
                f for f in ("threshold_pct", "severity", "is_enabled")
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _response(config)


@router.delete(
    "/{experiment_id}/guardrails/{guardrail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_guardrail(
    experiment_id: UUID,
    guardrail_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("guardrails:write")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    config = await guardrail_service.get_guardrail_by_id(db, guardrail_id)
    if not config or config.experiment_id != experiment_id:
        raise HTTPException(status_code=404, detail="Guardrail не найден")
    details = {
        **guardrail_service.guardrail_audit_details(config),
        "experiment_id": str(experiment_id),
    }
    await guardrail_service.delete_guardrail(db, config)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="guardrail_config",
        resource_id=guardrail_id,
        details=details,
        request=request,
    )
