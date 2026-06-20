from datetime import datetime
from uuid import UUID
from sqlalchemy import func 

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import Experiment, ExperimentStatus, Metric, MutexGroup, Variant
from app.schemas.experiment import ExperimentCreate, MutexGroupCreate



ALLOWED_TRANSITIONS: dict[ExperimentStatus, list[ExperimentStatus]] = {
    ExperimentStatus.DRAFT:     [ExperimentStatus.RUNNING],
    ExperimentStatus.RUNNING:   [ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED],
    ExperimentStatus.PAUSED:    [ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED],
    ExperimentStatus.COMPLETED: [],
}


# Experiments 

async def get_experiments(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    status: ExperimentStatus | None = None,
) -> tuple[list[Experiment], int]:
    """Возвращает (эксперименты, total_count) с поддержкой пагинации и фильтра."""
    conditions = []
    if status:
        conditions.append(Experiment.status == status)

    # Считаем total отдельным запросом
    count_q = select(func.count(Experiment.id))
    if conditions:
        count_q = count_q.where(*conditions)
    total = (await db.execute(count_q)).scalar() or 0

    # Основной запрос с пагинацией
    items_q = select(Experiment).order_by(Experiment.created_at.desc())
    if conditions:
        items_q = items_q.where(*conditions)
    items_q = items_q.offset(offset).limit(limit)

    result = await db.execute(items_q)
    return list(result.scalars().all()), total


async def get_experiment_by_id(db: AsyncSession, experiment_id: UUID) -> Experiment | None:
    result = await db.execute(
        select(Experiment)
        .options(
            selectinload(Experiment.variants),
            selectinload(Experiment.metrics),
        )
        .where(Experiment.id == experiment_id)
    )
    return result.scalar_one_or_none()


async def create_experiment(db: AsyncSession, data: ExperimentCreate) -> Experiment:
    experiment = Experiment(
        name=data.name,
        description=data.description,
        traffic_percentage=data.traffic_percentage,
        mutex_group_id=data.mutex_group_id,
        is_sequential=data.is_sequential,
    )
    db.add(experiment)
    await db.flush()  # получаем ID до создания вариантов

    for v in data.variants:
        db.add(Variant(
            experiment_id=experiment.id,
            name=v.name,
            description=v.description,
            traffic_split=v.traffic_split,
        ))

    for m in data.metrics:
        db.add(Metric(
            experiment_id=experiment.id,
            name=m.name,
            event_name=m.event_name,
            metric_type=m.metric_type,
            is_primary=m.is_primary,
            is_guardrail=m.is_guardrail,
        ))

    await db.flush()
    await db.refresh(experiment, ["variants", "metrics"])
    return experiment


async def update_experiment_status(
    db: AsyncSession,
    experiment: Experiment,
    new_status: ExperimentStatus,
) -> Experiment:
    allowed = ALLOWED_TRANSITIONS.get(experiment.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Нельзя перейти из '{experiment.status}' в '{new_status}'. "
            f"Допустимые переходы: {[s.value for s in allowed]}"
        )

    experiment.status = new_status

    if new_status == ExperimentStatus.RUNNING and experiment.started_at is None:
        experiment.started_at = datetime.utcnow()

    if new_status == ExperimentStatus.COMPLETED:
        experiment.ended_at = datetime.utcnow()

    await db.flush()
    return experiment


async def delete_experiment(db: AsyncSession, experiment: Experiment) -> None:
    if experiment.status != ExperimentStatus.DRAFT:
        raise ValueError("Удалять можно только эксперименты в статусе DRAFT")
    await db.delete(experiment)


# MutexGroups 

async def get_mutex_groups(db: AsyncSession) -> list[MutexGroup]:
    result = await db.execute(select(MutexGroup).order_by(MutexGroup.created_at.desc()))
    return list(result.scalars().all())


async def create_mutex_group(db: AsyncSession, data: MutexGroupCreate) -> MutexGroup:
    group = MutexGroup(name=data.name, description=data.description)
    db.add(group)
    await db.flush()
    return group
