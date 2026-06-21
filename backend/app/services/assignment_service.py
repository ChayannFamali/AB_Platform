import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import (
    Assignment,
    Experiment,
    ExperimentSegment,
    ExperimentStatus,
    HoldoutGroup,
    Segment,
)
from app.services.bucketing import get_bucket, is_in_traffic, pick_variant
from app.services.holdout_service import is_user_in_any_linked_holdout
from app.services.redis_client import (
    get_assignment_cache,
    get_experiment_cache,
    set_assignment_cache,
    set_experiment_cache,
)
from app.services.segment_service import evaluate_segment

logger = logging.getLogger(__name__)



def _serialize_experiment(experiment: Experiment) -> dict:
    """Сериализуем эксперимент для Redis кэша."""
    return {
        "id": str(experiment.id),
        "status": experiment.status.value,
        "traffic_percentage": experiment.traffic_percentage,
        "mutex_group_id": str(experiment.mutex_group_id) if experiment.mutex_group_id else None,
        "variants": [
            {
                "id": str(v.id),
                "name": v.name,
                "traffic_split": v.traffic_split,
            }
            for v in experiment.variants
        ],
    }


async def _load_experiment(db: AsyncSession, experiment_id: UUID) -> Experiment | None:
    """
    Load an experiment with variants + holdout_group eager-loaded.
    Segments are loaded separately by `_load_segments_for_experiment`
    because `experiment_segments` is a pure association table
    (no ORM relationships on it — see M-003 user_roles pattern).
    """
    result = await db.execute(
        select(Experiment)
        .options(
            selectinload(Experiment.variants),
            selectinload(Experiment.holdout_group).selectinload(
                HoldoutGroup.exclusions
            ),
        )
        .where(Experiment.id == experiment_id)
    )
    return result.scalar_one_or_none()


async def _load_segments_for_experiment(
    db: AsyncSession, experiment_id: UUID
) -> list[Segment]:
    """
    Return the segments linked to an experiment, each with its `rules`
    eager-loaded so `evaluate_segment` can run without lazy IO.
    """
    rows = (
        await db.execute(
            select(Segment)
            .options(selectinload(Segment.rules))
            .join(ExperimentSegment, ExperimentSegment.segment_id == Segment.id)
            .where(ExperimentSegment.experiment_id == experiment_id)
        )
    ).scalars().unique().all()
    return list(rows)


async def _get_db_assignment(
    db: AsyncSession, user_id: str, experiment_id: UUID
) -> Assignment | None:
    result = await db.execute(
        select(Assignment).where(
            Assignment.user_id == user_id,
            Assignment.experiment_id == experiment_id,
        )
    )
    return result.scalar_one_or_none()


async def _check_mutex_conflict(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    mutex_group_id: str,
    current_experiment_id: str,
) -> bool:
    """
    Проверяет: есть ли у пользователя assignment в другом эксперименте
    той же mutex группы? Если да — нельзя назначить в текущий.
    """
    result = await db.execute(
        select(Assignment)
        .join(Experiment, Assignment.experiment_id == Experiment.id)
        .where(
            Assignment.user_id == user_id,
            Experiment.mutex_group_id == UUID(mutex_group_id),
            Assignment.experiment_id != UUID(current_experiment_id),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None



async def _write_assignment_sync(
    db: AsyncSession,
    user_id: str,
    experiment_id: UUID,
    variant_id: UUID,
    variant_name: str,
) -> None:
    """
    Синхронная запись в БД в той же транзакции.
    Используется для тестов и когда нужна гарантия записи.
    """
    try:
        # Защита от race condition
        existing = await _get_db_assignment(db, user_id, experiment_id)
        if existing:
            return

        db.add(Assignment(
            user_id=user_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            variant_name=variant_name,
        ))
    except Exception as e:
        logger.error(f"Assignment write failed for user={user_id} exp={experiment_id}: {e}")
        raise


async def get_or_create_assignment(
    db: AsyncSession,
    redis: Redis,
    user_id: str,
    experiment_id: UUID,
    user_properties: dict[str, Any] | None = None,
) -> dict | None:
    """
    Возвращает вариант для пользователя.
    None = пользователь не участвует в эксперименте.

    Порядок:
    1. Redis кэш назначения → быстрый путь
    2. Конфиг эксперимента (Redis или БД)
    3. Проверки (статус, трафик, holdout, сегменты, mutex)
    4. Существующее назначение в БД (cache miss)
    5. Новое назначение (hash → вариант)
    6. Кэш в Redis + sync write в БД

    M-010 additions:
      - Holdout check: if experiment.holdout_group_id is set AND user is
        in that bucket → return None. Manual exclusions carve out VIPs.
      - Segment check: if experiment is linked to one or more segments
        AND user matches NONE of them → return None. If at least one
        segment matches → user is in the experiment.
    """
    exp_id_str = str(experiment_id)

    cached_variant = await get_assignment_cache(redis, exp_id_str, user_id)
    if cached_variant:
        return {"variant": cached_variant, "experiment_id": exp_id_str, "cached": True}

    exp_data = await get_experiment_cache(redis, exp_id_str)
    if not exp_data:
        experiment = await _load_experiment(db, experiment_id)
        if not experiment:
            return None
        exp_data = _serialize_experiment(experiment)
        # M-010: cache the holdout and segment presence so the Redis-only
        # path can decide without a DB roundtrip.
        exp_data["holdout_group_id"] = (
            str(experiment.holdout_group_id) if experiment.holdout_group_id else None
        )
        await set_experiment_cache(redis, exp_id_str, exp_data)

    if exp_data["status"] != ExperimentStatus.RUNNING.value:
        return None

    if not is_in_traffic(user_id, exp_id_str, exp_data["traffic_percentage"]):
        return None

    # M-010: Holdout check — done before segment/mutex because holdout is
    # the strictest gate ("this user is excluded from this whole class of
    # experiments"). Uses the same key namespace as the DB column so we
    # only need one DB lookup when cache misses.
    if exp_data.get("holdout_group_id"):
        experiment = await _load_experiment(db, experiment_id)
        if experiment and await is_user_in_any_linked_holdout(
            db, user_id, experiment,
        ):
            return None

    if exp_data["mutex_group_id"]:
        conflict = await _check_mutex_conflict(
            db, redis, user_id, exp_data["mutex_group_id"], exp_id_str
        )
        if conflict:
            return None

    # M-010: Segment check — if the experiment has any segments linked,
    # the user must match at least one of them (OR across segments). A
    # segment with no rules is always considered a match (vacuous AND).
    # Load fresh with segments since the Redis cache doesn't carry them.
    segments = await _load_segments_for_experiment(db, experiment_id)
    if segments:
        if not _user_matches_any_segment(segments, user_properties or {}):
            return None

    existing = await _get_db_assignment(db, user_id, experiment_id)
    if existing:
        await set_assignment_cache(redis, exp_id_str, user_id, existing.variant_name)
        return {"variant": existing.variant_name, "experiment_id": exp_id_str, "cached": False}

    bucket = get_bucket(user_id, exp_id_str)
    variant = pick_variant(bucket, exp_data["variants"])
    if not variant:
        return None

    await set_assignment_cache(redis, exp_id_str, user_id, variant["name"])

    await _write_assignment_sync(
        db=db,
        user_id=user_id,
        experiment_id=experiment_id,
        variant_id=UUID(variant["id"]),
        variant_name=variant["name"],
    )

    return {"variant": variant["name"], "experiment_id": exp_id_str, "cached": False}


def _user_matches_any_segment(
    segments: list[Segment], user_properties: dict[str, Any]
) -> bool:
    """
    OR across the experiment's linked segments. Each segment evaluates
    with AND logic internally (`segment_service.evaluate_segment`).

    A segment with no rules is treated as matching (vacuously true) —
    this lets admins attach an "empty placeholder" segment without
    excluding everyone.
    """
    for segment in segments or []:
        if not segment.rules:
            return True
        if evaluate_segment(segment, user_properties).matches:
            return True
    return False
