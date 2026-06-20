"""
Feature flag service (M-009, ADR-004).

Responsibilities:
- CRUD on `FeatureFlag` and its nested `FlagRule` rows.
- `evaluate_flag(user_id, flag_key)` — single-flag evaluation with
  deterministic SHA256 bucketing. Returns `(value, reason)` so the
  SDK can show *why* a flag was on or off.
- `evaluate_flags(user_id, flag_keys)` — batch version, used by SDK
  startup and warm-path rendering.
- `list_flags_summary(db)` — aggregate counts for the Dashboard
  "Active flags" card.

Bucketing:
    bucket = sha256(f"flag:{key}:{user_id}")[:4] % 100
    value  = bucket < rollout_percentage

The namespace ("flag:") is distinct from the experiment / traffic
buckets used elsewhere, so the same `user_id` produces independent
outcomes across flag rollouts and experiment assignments.

Audit hooks:
    Every mutation appends an `audit_log` row with `resource_type =
    "feature_flag"` and a `details` blob capturing the relevant state.
    Rules are not audited individually — the parent flag's `rules`
    field is included in the audit details.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import FeatureFlag, FlagRule, User
from app.schemas.flag import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FlagRuleCreate,
    FlagsSummary,
)

logger = logging.getLogger(__name__)


# ── Bucketing ───────────────────────────────────────────────────────────────


def get_flag_bucket(user_id: str, flag_key: str) -> int:
    """
    Deterministic bucket 0..99 for `(user_id, flag_key)`.

    Uses a separate key namespace from experiment / traffic bucketing so
    that the same user gets independent results across flags and
    experiments. SHA256 → first 4 bytes → integer mod 100.
    """
    key = f"flag:{flag_key}:{user_id}"
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big") % 100


# ── CRUD ────────────────────────────────────────────────────────────────────


async def _load_flag(
    db: AsyncSession, flag_id: UUID, *, with_rules: bool = True
) -> FeatureFlag | None:
    stmt = select(FeatureFlag).where(FeatureFlag.id == flag_id)
    if with_rules:
        stmt = stmt.options(selectinload(FeatureFlag.rules))
    return (await db.execute(stmt)).scalar_one_or_none()


async def _load_flag_by_key(
    db: AsyncSession, flag_key: str, *, with_rules: bool = True
) -> FeatureFlag | None:
    stmt = select(FeatureFlag).where(FeatureFlag.key == flag_key)
    if with_rules:
        stmt = stmt.options(selectinload(FeatureFlag.rules))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_flag_by_id(db: AsyncSession, flag_id: UUID) -> FeatureFlag | None:
    return await _load_flag(db, flag_id)


async def get_flag_by_key(db: AsyncSession, flag_key: str) -> FeatureFlag | None:
    return await _load_flag_by_key(db, flag_key)


async def list_flags(
    db: AsyncSession,
    limit: int,
    offset: int,
    enabled: bool | None = None,
) -> tuple[list[FeatureFlag], int]:
    """
    Return (items, total). `items` are lightweight — no rules eager-loaded.
    `summary` is computed via a separate aggregate query.
    """
    base = select(FeatureFlag)
    count = select(func.count(FeatureFlag.id))
    if enabled is not None:
        base = base.where(FeatureFlag.enabled == enabled)
        count = count.where(FeatureFlag.enabled == enabled)

    base = base.order_by(FeatureFlag.created_at.desc()).limit(limit).offset(offset)
    items = list((await db.execute(base)).scalars().all())
    total = (await db.execute(count)).scalar_one()
    return items, total


async def create_flag(
    db: AsyncSession,
    body: FeatureFlagCreate,
    actor: User,
) -> FeatureFlag:
    """Create a flag with optional initial rules."""
    if await _load_flag_by_key(db, body.key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Флаг с ключом «{body.key}» уже существует",
        )
    flag = FeatureFlag(
        key=body.key,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        rollout_percentage=body.rollout_percentage,
        created_by=actor.id,
    )
    flag.rules = [_rule_from_create(r) for r in body.rules]
    db.add(flag)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Флаг с ключом «{body.key}» уже существует",
        )
    # Re-fetch with rules eager-loaded — refresh() drops the relationship cache
    # and we need rules available for the response model without lazy IO.
    return await _load_flag(db, flag.id)


async def update_flag(
    db: AsyncSession,
    flag: FeatureFlag,
    body: FeatureFlagUpdate,
) -> FeatureFlag:
    if body.name is not None:
        flag.name = body.name
    if body.description is not None:
        flag.description = body.description
    if body.enabled is not None:
        flag.enabled = body.enabled
    if body.rollout_percentage is not None:
        flag.rollout_percentage = body.rollout_percentage
    await db.flush()
    return await _load_flag(db, flag.id)


async def toggle_flag(
    db: AsyncSession,
    flag: FeatureFlag,
    enabled: bool,
) -> FeatureFlag:
    """Set the kill switch in one shot (used by the UI quick-toggle)."""
    flag.enabled = enabled
    await db.flush()
    return await _load_flag(db, flag.id)


async def delete_flag(db: AsyncSession, flag: FeatureFlag) -> None:
    await db.delete(flag)
    await db.flush()


# ── Rule CRUD (M-009 + M-010 stub) ──────────────────────────────────────────


async def add_rule(
    db: AsyncSession,
    flag: FeatureFlag,
    body: FlagRuleCreate,
) -> FlagRule:
    rule = _rule_from_create(body, flag_id=flag.id)
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule: FlagRule) -> None:
    await db.delete(rule)
    await db.flush()


def _rule_from_create(body: FlagRuleCreate, flag_id: UUID | None = None) -> FlagRule:
    return FlagRule(
        flag_id=flag_id,
        segment_id=body.segment_id,
        rollout_percentage=body.rollout_percentage,
        priority=body.priority,
        enabled=body.enabled,
    )


# ── Summary (dashboard) ─────────────────────────────────────────────────────


async def list_flags_summary(db: AsyncSession) -> FlagsSummary:
    """Aggregate counts for the dashboard."""
    total = (await db.execute(select(func.count(FeatureFlag.id)))).scalar_one()
    enabled_total = (
        await db.execute(
            select(func.count(FeatureFlag.id)).where(FeatureFlag.enabled == True)
        )
    ).scalar_one()
    enabled_with_rollout = (
        await db.execute(
            select(func.count(FeatureFlag.id)).where(
                FeatureFlag.enabled == True,
                FeatureFlag.rollout_percentage > 0,
            )
        )
    ).scalar_one()
    return FlagsSummary(
        total=total,
        enabled_total=enabled_total,
        enabled_with_rollout=enabled_with_rollout,
        disabled_total=total - enabled_total,
    )


# ── Evaluation ──────────────────────────────────────────────────────────────


def _resolve_rollout(flag: FeatureFlag) -> tuple[float, str]:
    """
    Pick which rollout percentage to apply. Returns (rollout, reason).

    Priority:
    1. flag.enabled == False → 0, "kill_switch"
       (handled by callers, not here — this helper assumes enabled=True)
    2. enabled rule with no segment_id, lowest priority → rule.rollout_percentage
    3. otherwise → flag.rollout_percentage

    `reason` is a human-readable label for the SDK / audit log.
    """
    default_rule = next(
        (
            r for r in (flag.rules or [])
            if r.enabled and r.segment_id is None
        ),
        None,
    )
    if default_rule is not None:
        return float(default_rule.rollout_percentage), "rule_override"
    return float(flag.rollout_percentage), "flag_rollout"


async def evaluate_flag(
    db: AsyncSession,
    user_id: str,
    flag_key: str,
) -> tuple[bool, str, bool]:
    """
    Evaluate a single flag for a given user.

    Returns `(value, reason, found)`:
      - `value`  — the boolean result (defaults to False on miss/error)
      - `reason` — one of "kill_switch", "rollout_in", "rollout_out",
                   "rule_override", "not_found"
      - `found`  — False if no flag with that key exists
    """
    flag = await _load_flag_by_key(db, flag_key)
    if flag is None:
        return False, "not_found", False
    if not flag.enabled:
        return False, "kill_switch", True
    rollout, _ = _resolve_rollout(flag)
    bucket = get_flag_bucket(user_id, flag_key)
    return bucket < rollout, ("rollout_in" if bucket < rollout else "rollout_out"), True


async def evaluate_flags(
    db: AsyncSession,
    user_id: str,
    flag_keys: list[str],
) -> dict[str, tuple[bool, str, bool]]:
    """Batch evaluation. Missing keys return `found=False`."""
    if not flag_keys:
        return {}
    stmt = (
        select(FeatureFlag)
        .options(selectinload(FeatureFlag.rules))
        .where(FeatureFlag.key.in_(flag_keys))
    )
    flags = {f.key: f for f in (await db.execute(stmt)).scalars().all()}
    out: dict[str, tuple[bool, str, bool]] = {}
    for key in flag_keys:
        flag = flags.get(key)
        if flag is None:
            out[key] = (False, "not_found", False)
            continue
        if not flag.enabled:
            out[key] = (False, "kill_switch", True)
            continue
        rollout, _ = _resolve_rollout(flag)
        bucket = get_flag_bucket(user_id, key)
        out[key] = bucket < rollout, ("rollout_in" if bucket < rollout else "rollout_out"), True
    return out


# ── Audit helpers ───────────────────────────────────────────────────────────


def flag_audit_details(flag: FeatureFlag) -> dict[str, Any]:
    """Compact dict used by callers when writing audit rows."""
    return {
        "key":                flag.key,
        "name":               flag.name,
        "enabled":            flag.enabled,
        "rollout_percentage": flag.rollout_percentage,
        "rules_count":        len(flag.rules or []),
    }