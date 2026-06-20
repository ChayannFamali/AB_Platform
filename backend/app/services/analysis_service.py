import csv
import io
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


# ── CSV export (M-005) ────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "metric_name",
    "variant",
    "sample_size",
    "mean",
    "std_dev",
    "p_value",
    "ci_low",
    "ci_high",
    "relative_lift",
    "is_significant",
    "is_winner",
    "test_used",
    "achieved_mde",
    "srm_detected",
    "srm_p_value",
]


async def export_results_csv(db: AsyncSession, experiment_id: UUID) -> str:
    """
    Build an RFC 4180 CSV string of all saved results for the experiment.

    One row per (metric, variant). `metric`/`variant` columns carry
    human-readable names; numeric nullable fields are emitted as empty
    strings when null so the file is friendlier to spreadsheet tools.

    Raises ValueError if the experiment has no results yet.
    """
    rows = (
        await db.execute(
            select(Result)
            .options(selectinload(Result.metric), selectinload(Result.variant))
            .where(Result.experiment_id == experiment_id)
        )
    ).scalars().all()

    if not rows:
        raise ValueError(
            f"No results for experiment={experiment_id}. "
            "Run POST /experiments/{id}/analyze first."
        )

    # SRM is per-metric, not per-variant; carry it through by metric_id.
    srm_by_metric: dict[UUID, tuple[bool, float | None]] = {
        r.metric_id: (r.srm_detected, r.srm_p_value) for r in rows
    }

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=CSV_COLUMNS,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",  # RFC 4180
    )
    writer.writeheader()

    for r in rows:
        srm_detected, srm_p_value = srm_by_metric.get(r.metric_id, (False, None))
        writer.writerow({
            "metric_name":    r.metric.name if r.metric else "",
            "variant":        r.variant.name if r.variant else "",
            "sample_size":    r.sample_size,
            "mean":           _fmt_float(r.mean),
            "std_dev":        _fmt_float(r.std_dev),
            "p_value":        _fmt_float(r.p_value),
            "ci_low":         _fmt_float(r.confidence_interval_low),
            "ci_high":        _fmt_float(r.confidence_interval_high),
            "relative_lift":  _fmt_float(r.relative_lift),
            "is_significant": "" if r.is_significant is None else bool(r.is_significant),
            "is_winner":      bool(r.is_winner),
            "test_used":      r.test_used or "",
            "achieved_mde":   _fmt_float(r.achieved_mde),
            "srm_detected":   bool(srm_detected),
            "srm_p_value":    _fmt_float(srm_p_value),
        })

    return buffer.getvalue()


def _fmt_float(value: float | None) -> str:
    """Empty string for None so spreadsheet tools see blank cells, not 'None'."""
    if value is None:
        return ""
    # Full precision — analysis numbers are already small floats.
    return f"{value:.6f}"
