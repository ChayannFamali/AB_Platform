from collections import defaultdict
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import Result, ResultDaily, User
from app.schemas.result import (
    AnalysisResponse,
    DailyResultsResponse,
    DailySnapshotItem,
    MetricResultResponse,
    VariantResultResponse,
)
from app.services.analysis_service import run_and_save

router = APIRouter()


# Helpers 

def _build_variant_response(va) -> VariantResultResponse:
    return VariantResultResponse(
        variant_id=va.variant_id,
        variant_name=va.variant_name,
        sample_size=va.sample_size,
        mean=va.mean,
        std_dev=va.std_dev,
        p_value=va.p_value,
        ci_low=va.ci_low,
        ci_high=va.ci_high,
        effect_size=va.effect_size,
        relative_lift=va.relative_lift,
        is_significant=va.is_significant,
        is_winner=va.is_winner,
        ai_interpretation=va.ai_interpretation,
        is_normal=va.is_normal,
        normality_p_value=va.normality_p_value,
        test_used=va.test_used,
        achieved_mde=va.achieved_mde,
        numerator_mean=va.numerator_mean,
        denominator_mean=va.denominator_mean,
        numerator_relative_lift=va.numerator_relative_lift,
        denominator_relative_lift=va.denominator_relative_lift,
    )


def _build_variant_response_from_db(r: Result) -> VariantResultResponse:
    return VariantResultResponse(
        variant_id=r.variant_id,
        variant_name=r.variant.name if r.variant else "",
        sample_size=r.sample_size,
        mean=r.mean,
        std_dev=r.std_dev,
        p_value=r.p_value,
        ci_low=r.confidence_interval_low,
        ci_high=r.confidence_interval_high,
        effect_size=r.effect_size,
        relative_lift=r.relative_lift,
        is_significant=r.is_significant,
        is_winner=r.is_winner or False,
        ai_interpretation=r.ai_interpretation,
        is_normal=r.is_normal,
        normality_p_value=r.normality_p_value,
        test_used=r.test_used,
        achieved_mde=r.achieved_mde,
        numerator_mean=r.numerator_mean,
        denominator_mean=r.denominator_mean,
        numerator_relative_lift=r.numerator_relative_lift,
        denominator_relative_lift=r.denominator_relative_lift,
    )


def _compute_guardrail_violated(metric_results: list[Result]) -> bool:
    metric = metric_results[0].metric if metric_results else None
    if not metric or not metric.is_guardrail:
        return False
    for r in metric_results:
        variant_name = r.variant.name if r.variant else ""
        if (
            variant_name != "control"
            and r.is_significant
            and r.effect_size is not None
            and r.effect_size < 0
        ):
            return True
    return False


# Endpoints 

@router.post("/experiments/{experiment_id}/analyze", response_model=AnalysisResponse)
async def trigger_analysis(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Ручной запуск анализа. Результаты сохраняются в БД."""
    try:
        metric_results = await run_and_save(db, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AnalysisResponse(
        experiment_id=experiment_id,
        metrics=[
            MetricResultResponse(
                metric_id=m.metric_id,
                metric_name=m.metric_name,
                metric_type=m.metric_type,
                is_primary=m.is_primary,
                is_guardrail=m.is_guardrail,
                srm_detected=m.srm.srm_detected,
                srm_p_value=m.srm.p_value,
                guardrail_violated=m.guardrail_violated,
                variants=[_build_variant_response(va) for va in m.variants],
            )
            for m in metric_results
        ],
    )


@router.get("/experiments/{experiment_id}/results", response_model=AnalysisResponse)
async def get_results(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Возвращает последние сохранённые результаты из БД."""
    rows = await db.execute(
        select(Result)
        .options(selectinload(Result.metric), selectinload(Result.variant))
        .where(Result.experiment_id == experiment_id)
    )
    results = rows.scalars().all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="Результатов нет — запустите анализ: POST /experiments/{id}/analyze",
        )

    by_metric: dict[UUID, list[Result]] = defaultdict(list)
    for r in results:
        by_metric[r.metric_id].append(r)

    metrics = []
    for metric_id, metric_results in by_metric.items():
        first = metric_results[0]
        metric_obj = first.metric
        metrics.append(
            MetricResultResponse(
                metric_id=metric_id,
                metric_name=metric_obj.name if metric_obj else "",
                metric_type=metric_obj.metric_type.value if metric_obj else "",
                is_primary=metric_obj.is_primary if metric_obj else False,
                is_guardrail=metric_obj.is_guardrail if metric_obj else False,
                srm_detected=first.srm_detected,
                srm_p_value=first.srm_p_value,
                guardrail_violated=_compute_guardrail_violated(metric_results),
                variants=[_build_variant_response_from_db(r) for r in metric_results],
            )
        )

    return AnalysisResponse(experiment_id=experiment_id, metrics=metrics)


@router.get("/experiments/{experiment_id}/results/daily", response_model=DailyResultsResponse)
async def get_daily_results(
    experiment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Возвращает daily снапшоты результатов для trend-анализа.

    Данные появляются после первого запуска snapshot_daily_results (01:00 UTC).
    Frontend группирует по (metric_id, variant_id) для построения time series
    p-value и effect_size в динамике.
    """
    rows = await db.execute(
        select(ResultDaily)
        .options(
            selectinload(ResultDaily.variant),
            selectinload(ResultDaily.metric),
        )
        .where(ResultDaily.experiment_id == experiment_id)
        .order_by(ResultDaily.snapshot_date)
    )
    snapshots = rows.scalars().all()

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=(
                "Нет daily снапшотов. "
                "Данные появятся после 01:00 UTC следующего дня."
            ),
        )

    return DailyResultsResponse(
        experiment_id=experiment_id,
        snapshots=[
            DailySnapshotItem(
                snapshot_date=s.snapshot_date,
                metric_id=s.metric_id,
                metric_name=s.metric.name if s.metric else "",
                variant_id=s.variant_id,
                variant_name=s.variant.name if s.variant else "",
                sample_size=s.sample_size,
                mean=s.mean,
                p_value=s.p_value,
                effect_size=s.effect_size,
                relative_lift=s.relative_lift,
                ci_low=s.ci_low,
                ci_high=s.ci_high,
                is_significant=s.is_significant,
                test_used=s.test_used,
            )
            for s in snapshots
        ],
    )
