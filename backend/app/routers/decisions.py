"""
Decision log router (M-012).

Append-only decision history per experiment. Nested under the
experiment so the URL carries the experiment id naturally and matches
the M-005 DecisionLogTab shell.

  GET  /api/v1/experiments/{experiment_id}/decisions
         — paginated list (results:read)
  POST /api/v1/experiments/{experiment_id}/decisions
         — append a new decision (decisions:write)

There is intentionally NO PATCH or DELETE endpoint. The decision log
is immutable by design — corrections are made by appending a new
decision (e.g. "iterate" then later "ship"), not editing history.

All POSTs append an `audit_log` row with `resource_type="decision"`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Decision, Experiment, User
from app.schemas.decision import (
    DecisionCreate,
    DecisionResponse,
    PaginatedDecisions,
)
from app.services import audit_service, decision_service, rbac_service

# Nested under /experiments — note: NO prefix on the router itself.
# The full path /api/v1/experiments/{experiment_id}/decisions is
# constructed here so it sits next to the other nested resources
# (guardrails, results, etc.).
router = APIRouter(
    prefix="/api/v1/experiments",
    tags=["decisions"],
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


def _response(decision: Decision) -> DecisionResponse:
    return DecisionResponse(
        id                  = decision.id,
        experiment_id       = decision.experiment_id,
        status              = decision.status,
        comment             = decision.comment,
        decided_by          = decision.decided_by,
        decided_by_username = (
            decision.decided_by_user.username
            if decision.decided_by_user else None
        ),
        decided_at          = decision.decided_at,
    )


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get(
    "/{experiment_id}/decisions",
    response_model=PaginatedDecisions,
)
async def list_decisions(
    experiment_id: UUID,
    limit:  int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(rbac_service.require_permission("results:read")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    items, total = await decision_service.list_decisions_for_experiment(
        db, experiment_id, limit=limit, offset=offset,
    )
    return PaginatedDecisions(
        items=[_response(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post(
    "/{experiment_id}/decisions",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_decision(
    experiment_id: UUID,
    body: DecisionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("decisions:write")),
):
    experiment = await _load_experiment(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Эксперимент не найден")
    decision = await decision_service.create_decision(db, experiment, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="decision",
        resource_id=decision.id,
        details={
            **decision_service.decision_audit_details(decision),
            "status":       decision.status,
            "experiment_id": str(experiment_id),
        },
        request=request,
    )
    return _response(decision)