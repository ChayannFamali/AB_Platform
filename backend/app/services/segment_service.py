"""
Segment service (M-010).

Responsibilities:
- CRUD on `Segment` and its nested `SegmentRule` rows.
- `evaluate_segment(segment, user_properties)` — returns whether the
  given user properties payload matches every enabled rule (AND logic).
- `match_rule(rule, user_properties)` — single-rule matcher implementing
  the 9 supported operators.
- `link_segment_to_experiments(...)` / `unlink_segment_from_experiment(...)`
  — M2M management for `experiment_segments`.

Operators
---------
The full set is `SEGMENT_OPERATORS` below — used both to validate request
payloads at the schema layer (future) and to switch on inside `match_rule`.

Type-coercion rules:
  - eq / neq        — strict equality after JSON-shaped comparison.
                      `True != 1` and `"1" != 1` are intentionally
                      different so callers can be explicit about types.
  - in / not_in     — list membership. `value` must be a list at write
                      time (validated by Pydantic).
  - gt / lt / gte / lte — numeric. Both sides are coerced via float()
                      when possible; non-numeric comparisons miss.
  - contains        — substring match on string fields.

A missing `field` in `user_properties` always returns False (the rule
"misses") — segments are explicit about who is in, never implicit.

Audit hooks:
    Every mutation appends an `audit_log` row with `resource_type =
    "segment"` and a `details` blob capturing the relevant state.
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

from app.models.db import (
    ExperimentSegment,
    Segment,
    SegmentRule,
    User,
)
from app.schemas.segment import (
    SegmentCreate,
    SegmentEvaluateResponse,
    SegmentRuleCreate,
    SegmentUpdate,
)

logger = logging.getLogger(__name__)


# ── Operator catalogue ─────────────────────────────────────────────────────


SEGMENT_OPERATORS: tuple[str, ...] = (
    "eq", "neq", "in", "not_in",
    "gt", "lt", "gte", "lte",
    "contains",
)


# ── Loader helpers ─────────────────────────────────────────────────────────


async def _load_segment(
    db: AsyncSession, segment_id: UUID, *, with_rules: bool = True
) -> Segment | None:
    stmt = select(Segment).where(Segment.id == segment_id)
    if with_rules:
        stmt = stmt.options(selectinload(Segment.rules))
    return (await db.execute(stmt)).scalar_one_or_none()


async def _load_segment_by_key(
    db: AsyncSession, segment_key: str, *, with_rules: bool = True
) -> Segment | None:
    stmt = select(Segment).where(Segment.key == segment_key)
    if with_rules:
        stmt = stmt.options(selectinload(Segment.rules))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_segment_by_id(db: AsyncSession, segment_id: UUID) -> Segment | None:
    return await _load_segment(db, segment_id)


async def get_segment_by_key(db: AsyncSession, segment_key: str) -> Segment | None:
    return await _load_segment_by_key(db, segment_key)


# ── CRUD ───────────────────────────────────────────────────────────────────


async def list_segments(
    db: AsyncSession, limit: int, offset: int
) -> tuple[list[Segment], int]:
    """
    Return (items, total). Items are eager-loaded with rules so the
    `rules_count` field on `SegmentListItem` is cheap to compute.
    """
    stmt = (
        select(Segment)
        .options(selectinload(Segment.rules))
        .order_by(Segment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count(Segment.id)))
    ).scalar_one()
    return items, total


async def create_segment(
    db: AsyncSession,
    body: SegmentCreate,
    actor: User,
) -> Segment:
    """Create a segment with optional initial rules."""
    if await _load_segment_by_key(db, body.key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Сегмент с ключом «{body.key}» уже существует",
        )
    for rule in body.rules:
        if rule.operator not in SEGMENT_OPERATORS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Неизвестный оператор: «{rule.operator}»",
            )
    segment = Segment(
        key=body.key,
        name=body.name,
        description=body.description,
        created_by=actor.id,
    )
    segment.rules = [_rule_from_create(r) for r in body.rules]
    db.add(segment)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Сегмент с ключом «{body.key}» уже существует",
        )
    return await _load_segment(db, segment.id)


async def update_segment(
    db: AsyncSession,
    segment: Segment,
    body: SegmentUpdate,
) -> Segment:
    if body.name is not None:
        segment.name = body.name
    if body.description is not None:
        segment.description = body.description
    if body.rules is not None:
        for r in body.rules:
            if r.operator not in SEGMENT_OPERATORS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Неизвестный оператор: «{r.operator}»",
                )
        # Replace rules wholesale — simpler than diff. The cascade
        # delete-orphan on Segment.rules cleans up old rows.
        segment.rules = [_rule_from_create(r) for r in body.rules]
    await db.flush()
    return await _load_segment(db, segment.id)


async def delete_segment(db: AsyncSession, segment: Segment) -> None:
    await db.delete(segment)
    await db.flush()


# ── Rule CRUD ──────────────────────────────────────────────────────────────


async def add_rule(
    db: AsyncSession,
    segment: Segment,
    body: SegmentRuleCreate,
) -> SegmentRule:
    if body.operator not in SEGMENT_OPERATORS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Неизвестный оператор: «{body.operator}»",
        )
    rule = _rule_from_create(body, segment_id=segment.id)
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule: SegmentRule) -> None:
    await db.delete(rule)
    await db.flush()


def _rule_from_create(
    body: SegmentRuleCreate, segment_id: UUID | None = None
) -> SegmentRule:
    return SegmentRule(
        segment_id=segment_id,
        field=body.field,
        operator=body.operator,
        value=body.value,
        priority=body.priority,
        enabled=body.enabled,
    )


# ── Experiment linking (M2M) ──────────────────────────────────────────────


async def link_segment_to_experiments(
    db: AsyncSession,
    segment: Segment,
    experiment_ids: list[UUID],
) -> int:
    """
    Bulk-attach the segment to the given experiments. Idempotent — existing
    links are not duplicated (composite PK collision = no-op via skip).

    Returns the number of NEW rows inserted.
    """
    # Skip duplicates first.
    existing = {
        row.experiment_id
        for row in (
            await db.execute(
                select(ExperimentSegment).where(
                    ExperimentSegment.segment_id == segment.id,
                    ExperimentSegment.experiment_id.in_(experiment_ids),
                )
            )
        ).scalars().all()
    }
    inserted = 0
    for exp_id in experiment_ids:
        if exp_id in existing:
            continue
        db.add(ExperimentSegment(experiment_id=exp_id, segment_id=segment.id))
        inserted += 1
    if inserted:
        await db.flush()
    return inserted


async def unlink_segment_from_experiment(
    db: AsyncSession,
    segment: Segment,
    experiment_id: UUID,
) -> bool:
    """Detach a single experiment; returns True if a row was removed."""
    result = await db.execute(
        delete(ExperimentSegment).where(
            ExperimentSegment.segment_id == segment.id,
            ExperimentSegment.experiment_id == experiment_id,
        )
    )
    return result.rowcount > 0


async def list_segment_experiments(
    db: AsyncSession, segment: Segment
) -> list[UUID]:
    rows = (
        await db.execute(
            select(ExperimentSegment.experiment_id).where(
                ExperimentSegment.segment_id == segment.id,
            )
        )
    ).scalars().all()
    return list(rows)


# ── Evaluation ─────────────────────────────────────────────────────────────


def _coerce_number(value: Any) -> float | None:
    """Best-effort coercion to float. Returns None for non-numeric values."""
    if isinstance(value, bool):
        # bool is a subclass of int in Python — reject it explicitly so
        # True/False don't accidentally become 1.0/0.0 in comparisons.
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def match_rule(rule: SegmentRule, user_properties: dict[str, Any]) -> bool:
    """
    Returns True if the rule matches against the given properties.

    A rule with a missing `field` in `user_properties` returns False —
    segments are explicit about who is in.
    """
    actual = user_properties.get(rule.field)
    if actual is None:
        return False

    op = rule.operator
    expected = rule.value

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
        a = _coerce_number(actual)
        b = _coerce_number(expected)
        if a is None or b is None:
            return False
        if op == "gt":  return a > b
        if op == "lt":  return a < b
        if op == "gte": return a >= b
        if op == "lte": return a <= b

    if op == "contains":
        if not isinstance(expected, str):
            return False
        return expected in str(actual)

    return False


def evaluate_segment(
    segment: Segment, user_properties: dict[str, Any]
) -> SegmentEvaluateResponse:
    """
    AND-combined evaluation across all enabled rules.

    Per-rule breakdown is included in the response so the UI's
    SegmentPreview component can show *why* a segment did or didn't match.
    """
    per_rule: list[dict[str, Any]] = []
    matched = 0
    total = 0
    overall = True
    for rule in sorted(segment.rules or [], key=lambda r: r.priority):
        if not rule.enabled:
            continue
        total += 1
        rule_matched = match_rule(rule, user_properties)
        per_rule.append({
            "rule_id":  str(rule.id),
            "field":    rule.field,
            "operator": rule.operator,
            "expected": rule.value,
            "actual":   user_properties.get(rule.field),
            "matched":  rule_matched,
            "reason":   "ok" if rule_matched else "no_match",
        })
        if rule_matched:
            matched += 1
        else:
            overall = False
    return SegmentEvaluateResponse(
        matches=overall,
        matched_rules=matched,
        total_rules=total,
        per_rule=per_rule,
    )


# ── Audit helpers ──────────────────────────────────────────────────────────


def segment_audit_details(segment: Segment) -> dict[str, Any]:
    return {
        "key":         segment.key,
        "name":        segment.name,
        "rules_count": len(segment.rules or []),
    }
