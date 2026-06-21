"""
Guardrail service (M-011).

Responsibilities:
- CRUD on `GuardrailConfig` (per-experiment, per-metric).
- `evaluate_metric_guardrails(metric_analysis, configs_by_metric)` —
  cross-side threshold check used by the analysis engine after each
  variant's hypothesis test. Returns a per-variant check list and
  updates `metric_analysis.guardrail_violated` when any *critical*
  guardrail fires.

Threshold semantics
-------------------
A guardrail config has `direction` ("below"/"above") and a positive
`threshold_pct`. The check fires when:
  - direction="below" and `relative_lift < -threshold_pct`
  - direction="above" and `relative_lift > +threshold_pct`

It ONLY fires when `variant.is_significant == True` — this prevents
noise-triggered alerts on tiny samples where the lift estimate is
unstable. See ADR follow-on design decision.

Severity
--------
  - "warning"  — emits an insight via `app.services.stats.interpreter`.
                 Does NOT mutate `metric_analysis.guardrail_violated`.
  - "critical" — sets `metric_analysis.guardrail_violated=True`. The
                 engine then blocks ALL primary-metric winners in the
                 experiment (existing winner-blocking logic in
                 `engine.run_analysis` keys off this flag).

A guardrail metric with NO GuardrailConfig rows falls back to the
pre-M-011 behaviour ("any significant negative effect = violation").
This keeps experiments migrated from earlier milestones working
unchanged.
"""
from __future__ import annotations

import logging
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    Experiment,
    GuardrailConfig,
    GuardrailDirection,
    GuardrailSeverity,
    Metric,
    User,
)
from app.schemas.guardrail import (
    GuardrailCheck,
    GuardrailCreate,
    GuardrailUpdate,
)

logger = logging.getLogger(__name__)


# ── Loaders ────────────────────────────────────────────────────────────────


async def get_guardrail_by_id(
    db: AsyncSession, guardrail_id: UUID
) -> GuardrailConfig | None:
    return (
        await db.execute(
            select(GuardrailConfig).where(GuardrailConfig.id == guardrail_id)
        )
    ).scalar_one_or_none()


async def list_guardrails_for_experiment(
    db: AsyncSession,
    experiment_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[GuardrailConfig], int]:
    """All guardrails attached to an experiment, ordered by created_at desc."""
    items_q = (
        select(GuardrailConfig)
        .where(GuardrailConfig.experiment_id == experiment_id)
        .order_by(GuardrailConfig.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    total_q = (
        select(func.count(GuardrailConfig.id))
        .where(GuardrailConfig.experiment_id == experiment_id)
    )
    items = list((await db.execute(items_q)).scalars().all())
    total = (await db.execute(total_q)).scalar_one()
    return items, total


async def load_guardrails_grouped_by_metric(
    db: AsyncSession, experiment_id: UUID
) -> dict[UUID, list[GuardrailConfig]]:
    """
    Bulk-load all enabled guardrails for an experiment, grouped by metric.
    Single SELECT — avoids N+1 in the analysis engine.
    """
    rows = (
        await db.execute(
            select(GuardrailConfig)
            .where(
                GuardrailConfig.experiment_id == experiment_id,
                GuardrailConfig.is_enabled.is_(True),
            )
        )
    ).scalars().all()
    grouped: dict[UUID, list[GuardrailConfig]] = {}
    for g in rows:
        grouped.setdefault(g.metric_id, []).append(g)
    return grouped


# ── CRUD ───────────────────────────────────────────────────────────────────


async def _validate_metric_for_guardrail(
    db: AsyncSession, experiment_id: UUID, metric_id: UUID
) -> Metric:
    """
    Ensure `metric_id` belongs to `experiment_id`. The router relies on
    the FK to do most of the work, but we also require the metric to be
    marked `is_guardrail=True` — attaching a guardrail to a non-guardrail
    metric is a wiring mistake the API should reject explicitly.
    """
    metric = (
        await db.execute(
            select(Metric).where(
                Metric.id == metric_id,
                Metric.experiment_id == experiment_id,
            )
        )
    ).scalar_one_or_none()
    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Метрика {metric_id} не принадлежит эксперименту {experiment_id}",
        )
    if not metric.is_guardrail:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Метрика {metric_id} не помечена как guardrail "
                "(is_guardrail=False). Установите флаг is_guardrail перед "
                "прикреплением guardrail-конфигурации."
            ),
        )
    return metric


async def create_guardrail(
    db: AsyncSession,
    experiment: Experiment,
    body: GuardrailCreate,
    actor: User,
) -> GuardrailConfig:
    await _validate_metric_for_guardrail(db, experiment.id, body.metric_id)
    config = GuardrailConfig(
        experiment_id=experiment.id,
        metric_id=body.metric_id,
        direction=body.direction,
        threshold_pct=body.threshold_pct,
        severity=body.severity,
        is_enabled=body.is_enabled,
        created_by=actor.id,
    )
    db.add(config)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Guardrail с direction={body.direction.value}, "
                f"severity={body.severity.value} уже существует для "
                f"метрики {body.metric_id}"
            ),
        )
    await db.refresh(config)
    return config


async def update_guardrail(
    db: AsyncSession,
    config: GuardrailConfig,
    body: GuardrailUpdate,
) -> GuardrailConfig:
    if body.threshold_pct is not None:
        config.threshold_pct = body.threshold_pct
    if body.severity is not None:
        config.severity = body.severity
    if body.is_enabled is not None:
        config.is_enabled = body.is_enabled
    await db.flush()
    await db.refresh(config)
    return config


async def delete_guardrail(db: AsyncSession, config: GuardrailConfig) -> None:
    await db.delete(config)
    await db.flush()


# ── Evaluation (used by the stats engine) ──────────────────────────────────


def _direction_matches(
    direction: GuardrailDirection,
    relative_lift: float,
    threshold_pct: float,
) -> bool:
    """
    direction="below": fires when relative_lift is more negative than -threshold_pct.
    direction="above": fires when relative_lift is more positive than +threshold_pct.

    `threshold_pct` is a positive number; the service applies the sign.
    """
    if direction == GuardrailDirection.BELOW:
        return relative_lift < -threshold_pct
    # ABOVE
    return relative_lift > threshold_pct


def check_threshold(
    config: GuardrailConfig,
    *,
    relative_lift: float | None,
    is_significant: bool | None,
) -> GuardrailCheck:
    """
    Pure function — no DB access. Engine uses this to decide whether a
    single config fires for a single variant.

    Returns a `GuardrailCheck` so the interpreter can build an insight
    payload. `is_violated=False` for any condition that doesn't match
    (missing lift, not significant, threshold not crossed).
    """
    if relative_lift is None:
        reason = "no_lift_estimate"
    elif is_significant is None:
        reason = "no_significance_test"
    elif not is_significant:
        reason = "not_significant"
    elif _direction_matches(config.direction, relative_lift, config.threshold_pct):
        return GuardrailCheck(
            guardrail_id=config.id,
            metric_id=config.metric_id,
            variant_id=UUID("00000000-0000-0000-0000-000000000000"),
            direction=config.direction,
            threshold_pct=config.threshold_pct,
            severity=config.severity,
            is_violated=True,
            relative_lift=relative_lift,
            is_significant=True,
            reason="threshold_crossed",
        )
    else:
        reason = "below_threshold"
    return GuardrailCheck(
        guardrail_id=config.id,
        metric_id=config.metric_id,
        variant_id=UUID("00000000-0000-0000-0000-000000000000"),
        direction=config.direction,
        threshold_pct=config.threshold_pct,
        severity=config.severity,
        is_violated=False,
        relative_lift=relative_lift,
        is_significant=is_significant,
        reason=reason,
    )


def evaluate_metric_guardrails(
    metric_analysis,  # app.services.stats.engine.MetricAnalysis (avoid import cycle)
    configs: Iterable[GuardrailConfig],
    *,
    variant_filter=None,
) -> list[GuardrailCheck]:
    """
    Apply every enabled guardrail config to every non-control variant
    on `metric_analysis`. Returns a flat list of `GuardrailCheck`
    results. Mutates `metric_analysis.guardrail_violated=True` if any
    critical config fires.

    `variant_filter` (optional callable) lets callers restrict the
    evaluation to specific variants (used by tests). Defaults to
    "all non-control variants".
    """
    checks: list[GuardrailCheck] = []
    # Non-guardrail metrics never participate in guardrail evaluation —
    # the engine's call site filters by `is_guardrail` too, but the
    # service is defensive in case it's called directly (e.g. from tests).
    if not metric_analysis.is_guardrail:
        return checks

    fired_critical = False
    warning_count = 0

    def _iter_variants():
        for va in metric_analysis.variants:
            if va.variant_name == "control":
                continue
            if variant_filter and not variant_filter(va):
                continue
            yield va

    for va in _iter_variants():
        for config in configs:
            check = check_threshold(
                config,
                relative_lift=va.relative_lift,
                is_significant=va.is_significant,
            )
            # Replace the placeholder variant_id with the actual one.
            check.variant_id = va.variant_id
            checks.append(check)
            if check.is_violated and check.severity == GuardrailSeverity.CRITICAL:
                fired_critical = True
            elif check.is_violated and check.severity == GuardrailSeverity.WARNING:
                warning_count += 1

    if fired_critical and not metric_analysis.guardrail_violated:
        metric_analysis.guardrail_violated = True
        logger.warning(
            f"guardrail_critical_violation metric={metric_analysis.metric_name} "
            f"id={metric_analysis.metric_id}"
        )
    if warning_count:
        metric_analysis.guardrail_warning_count = (
            (metric_analysis.guardrail_warning_count or 0) + warning_count
        )
    return checks


# ── Audit helpers ──────────────────────────────────────────────────────────


def guardrail_audit_details(config: GuardrailConfig) -> dict:
    return {
        "metric_id":     str(config.metric_id),
        "direction":     config.direction.value,
        "threshold_pct": config.threshold_pct,
        "severity":      config.severity.value,
        "is_enabled":    config.is_enabled,
    }
