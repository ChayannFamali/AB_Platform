import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import Assignment, Experiment, ExperimentStatus
from app.services.bucketing import get_bucket, is_in_traffic, pick_variant
from app.services.redis_client import (
    get_assignment_cache,
    get_experiment_cache,
    set_assignment_cache,
    set_experiment_cache,
)

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
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.variants))
        .where(Experiment.id == experiment_id)
    )
    return result.scalar_one_or_none()


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
) -> dict | None:
    """
    Возвращает вариант для пользователя.
    None = пользователь не участвует в эксперименте.

    Порядок:
    1. Redis кэш назначения → быстрый путь
    2. Конфиг эксперимента (Redis или БД)
    3. Проверки (статус, трафик, mutex)
    4. Существующее назначение в БД (cache miss)
    5. Новое назначение (hash → вариант)
    6. Кэш в Redis + sync write в БД
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
        await set_experiment_cache(redis, exp_id_str, exp_data)

    if exp_data["status"] != ExperimentStatus.RUNNING.value:
        return None

    if not is_in_traffic(user_id, exp_id_str, exp_data["traffic_percentage"]):
        return None

    if exp_data["mutex_group_id"]:
        conflict = await _check_mutex_conflict(
            db, redis, user_id, exp_data["mutex_group_id"], exp_id_str
        )
        if conflict:
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
