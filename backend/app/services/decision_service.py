"""
Decision log service (M-012).

Append-only decision history per experiment. Each decision is a single
record capturing who decided, when, what (one of ship / stop / iterate
/ inconclusive), and an optional rationale comment.

The service keeps `experiments.decision_status` in sync with the latest
decision's status — it's the only place that mutates that column, so
read paths can rely on it without re-aggregating from the log.

There is intentionally no `update` or `delete` operation. The audit
log captures the `create` action; revision history lives in the
append-only row stream itself.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import Decision, Experiment, User
from app.schemas.decision import DecisionCreate


# ── Loaders ────────────────────────────────────────────────────────────────


async def list_decisions_for_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Decision], int]:
    """
    Return (items, total) for one experiment, ordered most-recent first
    (UI shows newest at top, like a chat history).

    Eager-loads `decided_by_user` so the response can include
    `decided_by_username` without N+1.
    """
    base = (
        select(Decision)
        .options(selectinload(Decision.decided_by_user))
        .where(Decision.experiment_id == experiment_id)
    )
    items_stmt = (
        base
        .order_by(Decision.decided_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_stmt = (
        select(func.count(Decision.id))
        .where(Decision.experiment_id == experiment_id)
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def get_decision_by_id(
    db: AsyncSession, decision_id: UUID
) -> Decision | None:
    return (
        await db.execute(
            select(Decision)
            .options(selectinload(Decision.decided_by_user))
            .where(Decision.id == decision_id)
        )
    ).scalar_one_or_none()


# ── Mutations ──────────────────────────────────────────────────────────────


async def create_decision(
    db: AsyncSession,
    experiment: Experiment,
    body: DecisionCreate,
    actor: User,
) -> Decision:
    """
    Append a decision row + mirror its status onto the experiment.

    Both writes happen in the same transaction — the caller (router)
    commits via `get_db` dependency teardown. If either step fails the
    whole operation rolls back, leaving the experiment's
    `decision_status` consistent with the log.
    """
    decision = Decision(
        experiment_id = experiment.id,
        status        = body.status,
        comment       = body.comment,
        decided_by    = actor.id,
    )
    db.add(decision)
    await db.flush()

    # Denormalised mirror — the latest decision's status. Decided
    # chronologically (decided_at DESC), so the just-inserted row is
    # always the "latest" we just appended. Storing the string (not the
    # Python Enum literal) keeps the column wire-format-stable for
    # Pydantic / API clients.
    experiment.decision_status = body.status
    await db.flush()

    # Refresh to populate `decided_at` (server default) and ensure the
    # `decided_by_user` relationship is eager-loaded for the response.
    await db.refresh(decision, attribute_names=["decided_by_user"])
    return decision


# ── Audit helpers ──────────────────────────────────────────────────────────


def decision_audit_details(decision: Decision) -> dict[str, Any]:
    """
    Stable details dict for the audit_log entry. Same shape for both
    create and (future) update operations so the audit trail is
    grep-friendly.
    """
    return {
        "decision_id":   str(decision.id),
        "experiment_id": str(decision.experiment_id),
        "status":        decision.status,
        "has_comment":   bool(decision.comment),
    }