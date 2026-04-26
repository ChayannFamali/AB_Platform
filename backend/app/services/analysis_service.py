import logging
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Result
from app.services.ai.prompts import MetricContext, build_result_prompt
from app.services.ai.providers import get_ai_provider
from app.services.stats.engine import MetricAnalysis, VariantAnalysis, run_analysis

logger = logging.getLogger(__name__)


def _find_control(variants: list[VariantAnalysis]) -> VariantAnalysis | None:
    for v in variants:
        if v.variant_name == "control":
            return v
    return sorted(variants, key=lambda v: v.variant_name)[0] if variants else None


async def _get_ai_interpretation(
    experiment_name: str,
    metric: MetricAnalysis,
    control: VariantAnalysis,
    treatment: VariantAnalysis,
) -> str | None:
    provider = get_ai_provider()
    ctx = MetricContext(
        experiment_name=experiment_name,
        metric_name=metric.metric_name,
        metric_type=metric.metric_type,
        control_mean=control.mean,
        treatment_mean=treatment.mean,
        control_size=control.sample_size,
        treatment_size=treatment.sample_size,
        effect_size=treatment.effect_size or 0.0,
        relative_lift=treatment.relative_lift,
        p_value=treatment.p_value,
        ci_low=treatment.ci_low,
        ci_high=treatment.ci_high,
        is_significant=treatment.is_significant,
        is_winner=treatment.is_winner,
        srm_detected=metric.srm.srm_detected,
        guardrail_violated=metric.guardrail_violated,
    )
    prompt = build_result_prompt(ctx)
    return await provider.generate(prompt)


async def run_and_save(db: AsyncSession, experiment_id: UUID) -> list[MetricAnalysis]:
    from sqlalchemy import select
    from app.models.db import Experiment

    exp = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = exp.scalar_one_or_none()
    exp_name = experiment.name if experiment else str(experiment_id)

    results = await run_analysis(db, experiment_id)

    rows = []
    for metric_result in results:
        control_va = _find_control(metric_result.variants)

        for va in metric_result.variants:
            if va.variant_name != "control" and control_va:
                va.ai_interpretation = await _get_ai_interpretation(
                    exp_name, metric_result, control_va, va
                )

        for va in metric_result.variants:
            rows.append({
                "experiment_id":             experiment_id,
                "variant_id":                va.variant_id,
                "metric_id":                 metric_result.metric_id,
                "sample_size":               va.sample_size,
                "mean":                      va.mean,
                "std_dev":                   va.std_dev,
                "p_value":                   va.p_value,
                "confidence_interval_low":   va.ci_low,
                "confidence_interval_high":  va.ci_high,
                "effect_size":               va.effect_size,
                "relative_lift":             va.relative_lift,
                "is_significant":            va.is_significant,
                "is_winner":                 va.is_winner,
                "srm_detected":              metric_result.srm.srm_detected,
                "srm_p_value":               metric_result.srm.p_value,
                "is_normal":                 va.is_normal,
                "normality_p_value":         va.normality_p_value,
                "test_used":                 va.test_used,
                "achieved_mde":              va.achieved_mde,
                "numerator_mean":            va.numerator_mean,
                "denominator_mean":          va.denominator_mean,
                "numerator_relative_lift":   va.numerator_relative_lift,
                "denominator_relative_lift": va.denominator_relative_lift,
                "ai_interpretation":         va.ai_interpretation,
            })

    if rows:
        stmt = insert(Result).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_result_exp_variant_metric",
            set_={
                "sample_size":               stmt.excluded.sample_size,
                "mean":                      stmt.excluded.mean,
                "std_dev":                   stmt.excluded.std_dev,
                "p_value":                   stmt.excluded.p_value,
                "confidence_interval_low":   stmt.excluded.confidence_interval_low,
                "confidence_interval_high":  stmt.excluded.confidence_interval_high,
                "effect_size":               stmt.excluded.effect_size,
                "relative_lift":             stmt.excluded.relative_lift,
                "is_significant":            stmt.excluded.is_significant,
                "is_winner":                 stmt.excluded.is_winner,
                "srm_detected":              stmt.excluded.srm_detected,
                "srm_p_value":               stmt.excluded.srm_p_value,
                "is_normal":                 stmt.excluded.is_normal,
                "normality_p_value":         stmt.excluded.normality_p_value,
                "test_used":                 stmt.excluded.test_used,
                "achieved_mde":              stmt.excluded.achieved_mde,
                "numerator_mean":            stmt.excluded.numerator_mean,
                "denominator_mean":          stmt.excluded.denominator_mean,
                "numerator_relative_lift":   stmt.excluded.numerator_relative_lift,
                "denominator_relative_lift": stmt.excluded.denominator_relative_lift,
                "ai_interpretation":         stmt.excluded.ai_interpretation,
            },
        )
        await db.execute(stmt)
        await db.flush()

    logger.info(f"Анализ сохранён: experiment={experiment_id}, строк={len(rows)}")
    return results
