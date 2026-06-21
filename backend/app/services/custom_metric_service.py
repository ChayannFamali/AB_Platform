"""
Custom metric service (M-011).

Responsibilities:
- CRUD on `CustomMetric`.
- `validate_definition` — operator whitelist + cross-field checks.
- `build_query(metric, *, numerator=True)` — render a parameterised SQL
  fragment that applies filters to `events.properties` AND aggregates
  by `aggregation`. The engine uses this to extend its existing
  conversion / revenue / ratio SQL with metric filters.
- `evaluate_preview(custom_metric, user_properties)` — dry-run the
  filter list against a hypothetical payload, used by the metric
  builder's side-panel preview.
- `copy_to_metric(template)` — produce a dict suitable for inserting
  into a per-experiment `Metric` row at experiment-creation time.
  This is the snapshot mechanism that makes templates reusable without
  coupling analysis to template mutations.

Filter operators
----------------
The same nine operators as `segment_service.SEGMENT_OPERATORS`. Reused
verbatim to keep the targeting vocabulary consistent across segments,
custom metrics, and any future filterable feature.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import CustomMetric, Metric, MetricAggregation, User
from app.schemas.custom_metric import (
    CustomMetricCreate,
    CustomMetricPreviewResponse,
    CustomMetricUpdate,
    VALID_METRIC_OPERATORS,
    _validate_filter_operators,
)

logger = logging.getLogger(__name__)


# Re-export so callers can `from app.services.custom_metric_service import VALID_OPERATORS`.
VALID_OPERATORS = VALID_METRIC_OPERATORS


# ── Loaders ────────────────────────────────────────────────────────────────


async def _load_metric(
    db: AsyncSession, metric_id: UUID
) -> CustomMetric | None:
    return (
        await db.execute(select(CustomMetric).where(CustomMetric.id == metric_id))
    ).scalar_one_or_none()


async def get_custom_metric_by_id(
    db: AsyncSession, metric_id: UUID
) -> CustomMetric | None:
    return await _load_metric(db, metric_id)


async def get_custom_metric_by_key(
    db: AsyncSession, key: str
) -> CustomMetric | None:
    return (
        await db.execute(select(CustomMetric).where(CustomMetric.key == key))
    ).scalar_one_or_none()


async def list_custom_metrics(
    db: AsyncSession, limit: int, offset: int
) -> tuple[list[CustomMetric], int]:
    """Return (items, total). `used_by_count` is filled in by the router."""
    items_q = (
        select(CustomMetric)
        .order_by(CustomMetric.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(items_q)).scalars().all())
    total = (
        await db.execute(select(func.count(CustomMetric.id)))
    ).scalar_one()
    return items, total


async def count_used_by(db: AsyncSession, custom_metric_ids: list[UUID]) -> dict[UUID, int]:
    """
    Per-id count of per-experiment Metric rows currently snapshotting
    this template. Single GROUP BY query — no N+1.
    """
    if not custom_metric_ids:
        return {}
    rows = (
        await db.execute(
            select(Metric.custom_metric_id, func.count(Metric.id))
            .where(Metric.custom_metric_id.in_(custom_metric_ids))
            .group_by(Metric.custom_metric_id)
        )
    ).all()
    return {r[0]: int(r[1]) for r in rows}


# ── Validation ─────────────────────────────────────────────────────────────


def validate_definition(
    *,
    event_name: str,
    aggregation: MetricAggregation,
    metric_type: str,
    filters: list[dict[str, Any]] | None,
    denominator_event_name: str | None,
    denominator_aggregation: MetricAggregation | None,
    denominator_filters: list[dict[str, Any]] | None,
) -> None:
    """
    Cross-field checks beyond Pydantic. Raises HTTPException(422) on
    failure so the router can pass it through unchanged.
    """
    _validate_filter_operators(filters)
    _validate_filter_operators(denominator_filters)

    if metric_type == "conversion" and denominator_event_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="denominator_event_name не применим к conversion метрикам.",
        )
    if denominator_event_name and denominator_event_name == event_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="denominator_event_name не может совпадать с event_name.",
        )
    if denominator_event_name and not denominator_aggregation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="denominator_aggregation обязателен, когда задан denominator_event_name.",
        )

    # unique_count only makes sense as a numerator aggregation — the
    # engine cannot interpret "distinct denominator" in a meaningful way.
    if denominator_aggregation == MetricAggregation.UNIQUE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="denominator_aggregation=unique_count не поддерживается.",
        )


# ── CRUD ───────────────────────────────────────────────────────────────────


def _filters_to_dict(
    filters: list[Any] | None,
) -> list[dict[str, Any]] | None:
    """Pydantic model instances → plain dicts for JSONB persistence."""
    if filters is None:
        return None
    return [
        {
            "field":    f.field,
            "operator": f.operator,
            "value":    f.value,
            "priority": f.priority,
            "enabled":  f.enabled,
        }
        for f in filters
    ]


async def create_custom_metric(
    db: AsyncSession,
    body: CustomMetricCreate,
    actor: User,
) -> CustomMetric:
    if await get_custom_metric_by_key(db, body.key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Кастомная метрика с ключом «{body.key}» уже существует",
        )
    validate_definition(
        event_name=body.event_name,
        aggregation=body.aggregation,
        metric_type=body.metric_type.value,
        filters=_filters_to_dict(body.filters),
        denominator_event_name=body.denominator_event_name,
        denominator_aggregation=body.denominator_aggregation,
        denominator_filters=_filters_to_dict(body.denominator_filters),
    )
    metric = CustomMetric(
        key=body.key,
        name=body.name,
        description=body.description,
        event_name=body.event_name,
        aggregation=body.aggregation,
        metric_type=body.metric_type,
        filters=_filters_to_dict(body.filters),
        denominator_event_name=body.denominator_event_name,
        denominator_aggregation=body.denominator_aggregation,
        denominator_filters=_filters_to_dict(body.denominator_filters),
        is_guardrail=body.is_guardrail,
        created_by=actor.id,
    )
    db.add(metric)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Кастомная метрика с ключом «{body.key}» уже существует",
        )
    await db.refresh(metric)
    return metric


async def update_custom_metric(
    db: AsyncSession,
    metric: CustomMetric,
    body: CustomMetricUpdate,
) -> CustomMetric:
    if body.name is not None:
        metric.name = body.name
    if body.description is not None:
        metric.description = body.description
    if body.filters is not None:
        validate_definition(
            event_name=metric.event_name,
            aggregation=metric.aggregation,
            metric_type=metric.metric_type.value,
            filters=_filters_to_dict(body.filters),
            denominator_event_name=metric.denominator_event_name,
            denominator_aggregation=metric.denominator_aggregation,
            denominator_filters=_filters_to_dict(metric.denominator_filters),
        )
        metric.filters = _filters_to_dict(body.filters)
    if body.denominator_event_name is not None:
        metric.denominator_event_name = body.denominator_event_name
    if body.denominator_aggregation is not None:
        metric.denominator_aggregation = body.denominator_aggregation
    if body.denominator_filters is not None:
        validate_definition(
            event_name=metric.event_name,
            aggregation=metric.aggregation,
            metric_type=metric.metric_type.value,
            filters=_filters_to_dict(metric.filters),
            denominator_event_name=metric.denominator_event_name,
            denominator_aggregation=body.denominator_aggregation or metric.denominator_aggregation,
            denominator_filters=_filters_to_dict(body.denominator_filters),
        )
        metric.denominator_filters = _filters_to_dict(body.denominator_filters)
    if body.is_guardrail is not None:
        metric.is_guardrail = body.is_guardrail
    await db.flush()
    await db.refresh(metric)
    return metric


async def delete_custom_metric(db: AsyncSession, metric: CustomMetric) -> None:
    await db.delete(metric)
    await db.flush()


# ── Snapshot ───────────────────────────────────────────────────────────────


def copy_to_metric(template: CustomMetric) -> dict[str, Any]:
    """
    Produce kwargs for constructing a per-experiment `Metric` row from
    this template. The metric row stores its own (snapshotted) copy of
    event_name / aggregation / filters / denominator — the template can
    be edited or deleted without breaking the experiment.

    Caller is responsible for setting `experiment_id`, `name`,
    `is_primary`, `is_guardrail` — those depend on the specific
    experiment's wiring and aren't part of the template.
    """
    return {
        "event_name":               template.event_name,
        "aggregation":              template.aggregation,
        "metric_type":              template.metric_type,
        "filters":                  template.filters,
        "denominator_event_name":   template.denominator_event_name,
        # `denominator_aggregation` and `denominator_filters` are
        # intentionally NOT carried into the per-experiment Metric row:
        # the engine infers denominator behaviour from
        # `denominator_event_name` and uses the same aggregation/filters
        # for both events. Carrying them would require extra columns we
        # don't need today.
        "custom_metric_id":         template.id,
    }


# ── SQL generation (used by the analysis engine) ──────────────────────────


def build_filter_clause(
    filters: list[dict[str, Any]] | None,
    *,
    alias: str = "e",
    params: dict[str, Any],
    prefix: str = "flt",
) -> tuple[str, int]:
    """
    Return (sql_fragment, n_fragments). The fragment is empty when
    there are no enabled filters.

    `params` is mutated in place — the caller passes it to `db.execute`
    alongside the rest of the analysis SQL.

    `prefix` disambiguates parameter names when multiple clauses are
    concatenated (e.g. numerator + denominator).

    Example with one filter [{"field":"country","operator":"eq","value":"DE"}]:
        " AND (e.properties->>'country' = :flt_0)"
    """
    if not filters:
        return "", 0
    enabled = [f for f in filters if f.get("enabled", True)]
    if not enabled:
        return "", 0
    parts: list[str] = []
    for i, f in enumerate(enabled):
        key = f"{prefix}_{i}"
        op = f["operator"]
        field = f["field"]
        value = f["value"]
        if op == "eq":
            params[key] = value
            parts.append(f"({alias}.properties->>'{field}') = :{key}")
        elif op == "neq":
            params[key] = value
            parts.append(f"({alias}.properties->>'{field}')::text <> :{key}")
        elif op in ("in", "not_in"):
            if not isinstance(value, list):
                continue
            params[key] = [str(x) for x in value]
            cmp = "= ANY(:{})".format(key) if op == "in" else "<> ALL(:{})".format(key)
            parts.append(f"({alias}.properties->>'{field}') {cmp}")
        elif op in ("gt", "lt", "gte", "lte"):
            try:
                params[key] = float(value)
            except (TypeError, ValueError):
                continue
            sql_op = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<="}[op]
            parts.append(f"({alias}.properties->>'{field}')::float {sql_op} :{key}")
        elif op == "contains":
            params[key] = f"%{value}%"
            parts.append(f"({alias}.properties->>'{field}') ILIKE :{key}")
        # Unknown operators silently skip — validate_definition guards
        # against this on the write path.
    if not parts:
        return "", 0
    return " AND " + " AND ".join(parts), len(parts)


def build_aggregation_sql(
    aggregation: str | None,
    metric_type: str,
    *,
    has_denominator: bool,
) -> str:
    """
    Return the inner aggregation expression used by the engine when
    constructing per-user scalars from events.

    The engine historically inferred this from `metric_type`:
      CONVERSION → COUNT, REVENUE → SUM, DURATION → AVG.

    With M-011, an explicit `aggregation` overrides the inference. The
    caller passes `has_denominator=True` so we know the query is the
    delta-method ratio path (numerator only — the engine runs two
    parallel queries and joins).

    Falls back to the legacy inference when `aggregation` is None so
    rows from earlier milestones keep working unchanged.
    """
    if aggregation:
        if aggregation == "count":
            return "COUNT(e.value)"
        if aggregation == "sum":
            return "COALESCE(SUM(e.value), 0)"
        if aggregation == "avg":
            return "COALESCE(AVG(e.value), 0)"
        if aggregation == "unique_count":
            return "COUNT(DISTINCT e.value)"
    # Legacy inference (preserves pre-M-011 behaviour).
    if metric_type == "conversion":
        return "COUNT(*)"
    if metric_type in ("revenue", "duration"):
        return "COALESCE(SUM(e.value), 0)"
    return "COUNT(*)"


# ── Preview ────────────────────────────────────────────────────────────────


def _coerce_number(value: Any) -> float | None:
    """Mirrors segment_service._coerce_number — kept independent to avoid
    a coupling from the metrics package into the segments package."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _match_filter(rule: dict[str, Any], props: dict[str, Any]) -> bool:
    actual = props.get(rule["field"])
    if actual is None:
        return False
    op = rule["operator"]
    expected = rule["value"]
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op in ("in", "not_in"):
        if not isinstance(expected, list):
            return False
        in_list = actual in expected
        return (op == "in") == in_list
    if op in ("gt", "lt", "gte", "lte"):
        a, b = _coerce_number(actual), _coerce_number(expected)
        if a is None or b is None:
            return False
        return {"gt": a > b, "lt": a < b, "gte": a >= b, "lte": a <= b}[op]
    if op == "contains":
        if not isinstance(expected, str):
            return False
        return expected in str(actual)
    return False


def evaluate_preview(
    template: CustomMetric,
    user_properties: dict[str, Any],
) -> CustomMetricPreviewResponse:
    """Plain-English preview for the metric builder side panel."""
    filters = template.filters or []
    matched, total = 0, 0
    per_filter: list[dict[str, Any]] = []
    for rule in sorted(filters, key=lambda r: r.get("priority", 0)):
        if not rule.get("enabled", True):
            continue
        total += 1
        ok = _match_filter(rule, user_properties)
        per_filter.append({
            "field":    rule["field"],
            "operator": rule["operator"],
            "expected": rule["value"],
            "actual":   user_properties.get(rule["field"]),
            "matched":  ok,
        })
        if ok:
            matched += 1

    summary = _describe_metric(template, matched == total and total > 0)
    return CustomMetricPreviewResponse(
        summary=summary,
        matches=(matched == total and total > 0),
        matched_filters=matched,
        total_filters=total,
        per_filter=per_filter,
    )


def _describe_metric(template: CustomMetric, matches: bool) -> str:
    """Human-readable summary used in the metric builder preview."""
    agg_verb = {
        "count":        "count",
        "sum":          "sum",
        "avg":          "average",
        "unique_count": "count distinct",
    }.get(template.aggregation.value, template.aggregation.value)

    noun = template.event_name
    if template.denominator_event_name:
        return (
            f"{agg_verb.capitalize()} of «{noun}» events per "
            f"{template.denominator_event_name} events"
        )
    if template.filters:
        return (
            f"{agg_verb.capitalize()} of «{noun}» events "
            f"matching {len(template.filters)} filter(s)"
        )
    return f"{agg_verb.capitalize()} of «{noun}» events"


# ── Audit helpers ──────────────────────────────────────────────────────────


def custom_metric_audit_details(metric: CustomMetric, *, used_by_count: int = 0) -> dict[str, Any]:
    return {
        "key":             metric.key,
        "name":            metric.name,
        "event_name":      metric.event_name,
        "aggregation":     metric.aggregation.value if metric.aggregation else None,
        "metric_type":     metric.metric_type.value if metric.metric_type else None,
        "is_guardrail":    metric.is_guardrail,
        "used_by_count":   used_by_count,
    }
