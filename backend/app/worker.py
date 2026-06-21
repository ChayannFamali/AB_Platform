import logging
import uuid as uuid_module
from datetime import datetime

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db import Experiment, ExperimentStatus, Result, ResultDaily
from app.services.analysis_service import run_and_save
from app.services.partition_manager import ensure_partitions

logger = logging.getLogger(__name__)


# Jobs

async def deliver_webhooks(
    ctx: dict,
    event_type: str,
    payload: dict,
) -> dict:
    """
    M-013: fan out one event-type/payload pair to every active webhook
    subscribed to `event_type`. Runs as a background arq task so the
    analysis pipeline doesn't block on HTTP timeouts.

    Args:
        event_type: "winner_detected" | "srm_alert" |
                    "guardrail_violated" | "sequential_boundary_crossed"
        payload:    JSON-serialisable dict. The webhook_service
                    formatter decides what to surface as headline vs.
                    structured fields based on `format`.
    """
    from app.services.webhook_service import deliver_event
    async with AsyncSessionLocal() as db:
        count = await deliver_event(db, event_type, payload)
    return {"event_type": event_type, "fanned_out": count}


async def analyze_running_experiments(ctx: dict) -> dict:
    """
    Анализирует все RUNNING эксперименты.
    Запускается каждый час в :00.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Experiment).where(Experiment.status == ExperimentStatus.RUNNING)
        )
        experiments = result.scalars().all()

        success, failed = 0, 0
        for exp in experiments:
            try:
                await run_and_save(db, exp.id)
                success += 1
            except Exception as e:
                logger.error(f"Анализ упал для {exp.id}: {e}")
                failed += 1

    logger.info(f"Hourly analysis: success={success}, failed={failed}")
    return {"analyzed": success, "failed": failed}


async def analyze_single_experiment(ctx: dict, experiment_id: str) -> str:
    """Ручной запуск анализа для одного эксперимента."""
    from uuid import UUID
    async with AsyncSessionLocal() as db:
        await run_and_save(db, UUID(experiment_id))
    return f"Анализ завершён: {experiment_id}"


async def snapshot_daily_results(ctx: dict) -> dict:
    """
    Ежедневный снапшот результатов → results_daily для trend-анализа.

    Запускается в 01:00 UTC — после hourly analysis в 00:00.
    Читает текущие результаты из таблицы results для всех RUNNING экспериментов
    и upsert-ит их в results_daily с snapshot_date=сегодня.

    Idempotent: повторный запуск в тот же день перезаписывает снапшот
    (актуально если эксперимент анализировался несколько раз за день).
    """
    from datetime import date
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    today = date.today()

    async with AsyncSessionLocal() as db:
        running_ids_result = await db.execute(
            select(Experiment.id).where(Experiment.status == ExperimentStatus.RUNNING)
        )
        running_ids = [row[0] for row in running_ids_result]

        if not running_ids:
            logger.info("Нет running экспериментов для daily снапшота")
            return {"snapshots": 0, "date": str(today)}

        results_result = await db.execute(
            select(Result).where(Result.experiment_id.in_(running_ids))
        )
        results = results_result.scalars().all()

        if not results:
            logger.info("Running эксперименты есть, но результатов пока нет")
            return {"snapshots": 0, "date": str(today)}

        snapshot_rows = [
            {
                "id":             uuid_module.uuid4(),
                "experiment_id":  r.experiment_id,
                "variant_id":     r.variant_id,
                "metric_id":      r.metric_id,
                "snapshot_date":  today,
                "sample_size":    r.sample_size,
                "mean":           r.mean,
                "p_value":        r.p_value,
                "effect_size":    r.effect_size,
                "relative_lift":  r.relative_lift,
                "ci_low":         r.confidence_interval_low,
                "ci_high":        r.confidence_interval_high,
                "is_significant": r.is_significant,
                "test_used":      r.test_used,
                "sequential_fpr": r.sequential_fpr,
                "created_at":     datetime.utcnow(),
            }
            for r in results
        ]

        stmt = pg_insert(ResultDaily).values(snapshot_rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_result_daily_exp_variant_metric_date",
            set_={
                "sample_size":    stmt.excluded.sample_size,
                "mean":           stmt.excluded.mean,
                "p_value":        stmt.excluded.p_value,
                "effect_size":    stmt.excluded.effect_size,
                "relative_lift":  stmt.excluded.relative_lift,
                "ci_low":         stmt.excluded.ci_low,
                "ci_high":        stmt.excluded.ci_high,
                "is_significant": stmt.excluded.is_significant,
                "test_used":      stmt.excluded.test_used,
                "sequential_fpr": stmt.excluded.sequential_fpr,
            },
        )
        await db.execute(stmt)
        await db.commit()

    logger.info(f"Daily snapshot: {len(snapshot_rows)} строк за {today}")
    return {"snapshots": len(snapshot_rows), "date": str(today)}


async def create_monthly_partitions(ctx: dict) -> dict:
    """
    Создаёт партиции events на 3 месяца вперёд.
    Запускается ежедневно в 03:00 UTC.
    """
    async with AsyncSessionLocal() as db:
        created = await ensure_partitions(db, months_ahead=3)
        if created:
            await db.commit()
            logger.info(f"Новые партиции: {created}")
        else:
            logger.debug("Все партиции актуальны, ничего не создано")

    return {"created": created, "count": len(created)}


# Worker settings 

class WorkerSettings:
    functions = [
        analyze_running_experiments,
        analyze_single_experiment,
        snapshot_daily_results,
        create_monthly_partitions,
        deliver_webhooks,
    ]

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    cron_jobs = [
        # Анализ каждый час в :00
        cron(analyze_running_experiments, minute=0),
        # Daily снапшот в 01:00 UTC (через час после полуночного анализа)
        cron(snapshot_daily_results, hour=1, minute=0),
        # Создание партиций в 03:00 UTC
        cron(create_monthly_partitions, hour=3, minute=0),
    ]

    on_startup = None
    on_shutdown = None
