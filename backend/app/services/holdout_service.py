"""
Holdout service (M-010).

Responsibilities:
- CRUD on `HoldoutGroup` and `HoldoutExclusion` rows.
- `get_holdout_bucket(user_id, group_key)` — deterministic SHA256 bucketing
  with a dedicated `holdout:` namespace prefix (independent of flag/traffic).
- `is_in_holdout(db, user_id, group)` — combines bucketing with manual
  exclusions and the `is_active` kill switch.
- `is_user_in_any_linked_holdout(db, user_id, experiment)` — single point
  called from `assignment_service` before bucket / variant pick.

Bucket math
-----------
    bucket = sha256(f"holdout:{group_key}:{user_id}")[:4] % 100
    in_holdout = (not manual_excluded) and (not is_active == False)
                 and bucket < group.size_pct

The `holdout:` namespace is distinct from `flag:` (M-009) and `traffic:`
(M-001) so holdout membership is statistically independent of every
other bucketing decision in the system. Same `user_id` in the same
experiment can be:

  - in `traffic` for the experiment
  - NOT in any `holdout` linked to that experiment
  - rolled IN for a particular feature flag

— without correlation between the three outcomes.

Manual exclusions always win: a user explicitly excluded from a holdout
group is never considered "in holdout" regardless of bucket position.
This lets admins carve out VIPs, internal staff, canary accounts, etc.

Audit hooks:
    Every mutation appends an `audit_log` row with `resource_type =
    "holdout_group"` (or `"holdout_exclusion"` for per-user operations).
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

from app.models.db import (
    Experiment,
    HoldoutExclusion,
    HoldoutGroup,
    User,
)
from app.schemas.holdout import (
    HoldoutExclusionCreate,
    HoldoutGroupCreate,
    HoldoutGroupUpdate,
)

logger = logging.getLogger(__name__)


# ── Bucketing ──────────────────────────────────────────────────────────────


def get_holdout_bucket(user_id: str, group_key: str) -> int:
    """
    Deterministic bucket 0..99 for `(user_id, group_key)`.

    Uses a dedicated `holdout:` namespace so holdout membership is
    statistically independent of flag rollouts (`flag:`) and experiment
    traffic allocation (`traffic:`).
    """
    key = f"holdout:{group_key}:{user_id}"
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big") % 100


# ── Loaders ────────────────────────────────────────────────────────────────


async def _load_group(
    db: AsyncSession, group_id: UUID, *, with_exclusions: bool = False
) -> HoldoutGroup | None:
    stmt = select(HoldoutGroup).where(HoldoutGroup.id == group_id)
    if with_exclusions:
        stmt = stmt.options(
            selectinload(HoldoutGroup.exclusions),
            selectinload(HoldoutGroup.experiments),
        )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _load_group_by_key(
    db: AsyncSession, key: str
) -> HoldoutGroup | None:
    return (
        await db.execute(select(HoldoutGroup).where(HoldoutGroup.key == key))
    ).scalar_one_or_none()


async def get_holdout_by_id(db: AsyncSession, group_id: UUID) -> HoldoutGroup | None:
    """Load a holdout group with exclusions + experiments eager-loaded.

    Used after mutations and for direct GETs so the router can compute
    `exclusions_count` / `experiments_count` without lazy IO.
    """
    return await _load_group(db, group_id, with_exclusions=True)


async def get_holdout_by_key(db: AsyncSession, key: str) -> HoldoutGroup | None:
    return await _load_group_by_key(db, key)


# ── CRUD ───────────────────────────────────────────────────────────────────


async def list_holdouts(
    db: AsyncSession, limit: int, offset: int
) -> tuple[list[HoldoutGroup], int]:
    stmt = (
        select(HoldoutGroup)
        .options(
            selectinload(HoldoutGroup.exclusions),
            selectinload(HoldoutGroup.experiments),
        )
        .order_by(HoldoutGroup.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().unique().all())
    total = (
        await db.execute(select(func.count(HoldoutGroup.id)))
    ).scalar_one()
    return items, total


async def create_holdout(
    db: AsyncSession,
    body: HoldoutGroupCreate,
    actor: User,
) -> HoldoutGroup:
    if await _load_group_by_key(db, body.key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Группа с ключом «{body.key}» уже существует",
        )
    group = HoldoutGroup(
        key=body.key,
        name=body.name,
        description=body.description,
        size_pct=body.size_pct,
        is_active=body.is_active,
        created_by=actor.id,
    )
    db.add(group)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Группа с ключом «{body.key}» уже существует",
        )
    # Re-fetch with exclusions + experiments eager-loaded so the
    # response model's `exclusions_count` / `experiments_count` can be
    # computed without triggering lazy IO inside the async context.
    return await get_holdout_by_id(db, group.id)


async def update_holdout(
    db: AsyncSession,
    group: HoldoutGroup,
    body: HoldoutGroupUpdate,
) -> HoldoutGroup:
    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    if body.size_pct is not None:
        group.size_pct = body.size_pct
    if body.is_active is not None:
        group.is_active = body.is_active
    await db.flush()
    # Re-fetch the same way create_holdout does — see comment above.
    return await get_holdout_by_id(db, group.id)


async def delete_holdout(db: AsyncSession, group: HoldoutGroup) -> None:
    await db.delete(group)
    await db.flush()


# ── Exclusion CRUD ─────────────────────────────────────────────────────────


async def list_exclusions(
    db: AsyncSession,
    group: HoldoutGroup,
    limit: int,
    offset: int,
) -> tuple[list[HoldoutExclusion], int]:
    base = select(HoldoutExclusion).where(
        HoldoutExclusion.holdout_group_id == group.id
    )
    count = select(func.count(HoldoutExclusion.user_id)).where(
        HoldoutExclusion.holdout_group_id == group.id
    )
    items = list(
        (
            await db.execute(
                base.order_by(HoldoutExclusion.excluded_at.desc())
                    .limit(limit).offset(offset)
            )
        ).scalars().all()
    )
    total = (await db.execute(count)).scalar_one()
    return items, total


async def add_exclusion(
    db: AsyncSession,
    group: HoldoutGroup,
    body: HoldoutExclusionCreate,
    actor: User,
) -> HoldoutExclusion:
    """Add (or no-op if existing) a manual per-user exclusion."""
    existing = (
        await db.execute(
            select(HoldoutExclusion).where(
                HoldoutExclusion.holdout_group_id == group.id,
                HoldoutExclusion.user_id == body.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    exclusion = HoldoutExclusion(
        holdout_group_id=group.id,
        user_id=body.user_id,
        reason=body.reason,
        excluded_by=actor.id,
    )
    db.add(exclusion)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Исключение уже существует",
        )
    await db.refresh(exclusion)
    return exclusion


async def remove_exclusion(
    db: AsyncSession,
    group: HoldoutGroup,
    user_id: str,
) -> bool:
    result = await db.execute(
        select(HoldoutExclusion).where(
            HoldoutExclusion.holdout_group_id == group.id,
            HoldoutExclusion.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True


# ── Membership checks ──────────────────────────────────────────────────────


async def is_in_holdout(
    db: AsyncSession,
    user_id: str,
    group: HoldoutGroup,
) -> bool:
    """
    Returns True if the user should be treated as in-holdout for this group.

    Order of checks (any True short-circuits to False):
      1. `is_active == False` → nobody is in holdout (group disabled).
      2. user_id in `holdout_exclusions` → explicitly opted out, never in.
      3. bucket < size_pct → in holdout.

    Bucketing reuses `get_holdout_bucket`; the result is reproducible
    across server restarts, replicas, and DB migrations because it's
    a pure SHA256 of the inputs.
    """
    if not group.is_active:
        return False

    excluded = (
        await db.execute(
            select(HoldoutExclusion).where(
                HoldoutExclusion.holdout_group_id == group.id,
                HoldoutExclusion.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if excluded is not None:
        return False

    bucket = get_holdout_bucket(user_id, group.key)
    return bucket < group.size_pct


async def is_user_in_any_linked_holdout(
    db: AsyncSession,
    user_id: str,
    experiment: Experiment,
) -> bool:
    """
    Returns True if `experiment` is linked to a holdout group AND the user
    falls inside that group. Called by `assignment_service` before any
    bucket / variant pick so holdout users never receive a variant.

    No linked holdout → False (no exclusion).
    """
    group = experiment.holdout_group
    if group is None:
        return False
    return await is_in_holdout(db, user_id, group)


# ── Audit helpers ──────────────────────────────────────────────────────────


def holdout_audit_details(group: HoldoutGroup) -> dict[str, Any]:
    return {
        "key":       group.key,
        "name":      group.name,
        "size_pct":  group.size_pct,
        "is_active": group.is_active,
    }


def exclusion_audit_details(exclusion: HoldoutExclusion) -> dict[str, Any]:
    return {
        "user_id": exclusion.user_id,
        "reason":  exclusion.reason,
    }
