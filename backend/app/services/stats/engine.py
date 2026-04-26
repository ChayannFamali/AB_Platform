import logging
from dataclasses import dataclass, field
from uuid import UUID
import math

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import Assignment, Experiment, ExperimentStatus, Metric, MetricType, Variant
from app.services.stats.corrections import benjamini_hochberg
from app.services.stats.hypothesis_tests import (
    TestResult,
    check_normality,
    delta_method_test,
    mann_whitney_test,
    welch_t_test,
    z_test_proportions,
)
from app.services.stats.sample_size import (
    calculate_achieved_mde_conversion,
    calculate_achieved_mde_revenue,
)
from app.services.stats.srm import SRMResult, check_srm

logger = logging.getLogger(__name__)


# Data structures 

@dataclass
class VariantAnalysis:
    variant_id: UUID
    variant_name: str
    sample_size: int
    mean: float
    std_dev: float | None = None
    p_value: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    effect_size: float | None = None
    relative_lift: float | None = None
    is_significant: bool | None = None
    is_winner: bool = False
    ai_interpretation: str | None = None
    is_normal: bool | None = None
    normality_p_value: float | None = None
    test_used: str | None = None
    achieved_mde: float | None = None
    numerator_mean: float | None = None           # среднее числителя на юзера
    denominator_mean: float | None = None         # среднее знаменателя на юзера
    numerator_relative_lift: float | None = None  # относительный lift числителя %
    denominator_relative_lift: float | None = None # относительный lift знаменателя %


@dataclass
class MetricAnalysis:
    metric_id: UUID
    metric_name: str
    metric_type: str
    is_primary: bool
    is_guardrail: bool
    srm: SRMResult
    variants: list[VariantAnalysis] = field(default_factory=list)
    guardrail_violated: bool = False


# DB queries 

async def _get_variant_counts(
    db: AsyncSession, experiment_id: UUID
) -> dict[str, dict]:
    result = await db.execute(
        select(
            Variant.id,
            Variant.name,
            Variant.traffic_split,
            func.count(Assignment.id).label("count"),
        )
        .outerjoin(Assignment, Assignment.variant_id == Variant.id)
        .where(Variant.experiment_id == experiment_id)
        .group_by(Variant.id, Variant.name, Variant.traffic_split)
    )
    return {
        row.name: {
            "id": row.id,
            "count": row.count or 0,
            "traffic_split": row.traffic_split,
        }
        for row in result
    }


async def _get_conversion_data(
    db: AsyncSession, experiment_id: UUID, event_name: str
) -> dict[str, tuple[int, int]]:
    """Возвращает {variant_name: (total_users, converted_users)}."""
    rows = await db.execute(
        text("""
            SELECT
                a.variant_name,
                COUNT(DISTINCT a.user_id)                                      AS total_users,
                COUNT(DISTINCT CASE WHEN e.user_id IS NOT NULL
                                    THEN a.user_id END)                        AS converted_users
            FROM assignments a
            LEFT JOIN events e
                   ON e.user_id     = a.user_id
                  AND e.event_name  = :event_name
                  AND e.occurred_at >= a.assigned_at
            WHERE a.experiment_id = :experiment_id
            GROUP BY a.variant_name
        """),
        {"experiment_id": str(experiment_id), "event_name": event_name},
    )
    return {r.variant_name: (r.total_users, r.converted_users) for r in rows}


async def _get_revenue_data(
    db: AsyncSession, experiment_id: UUID, event_name: str
) -> dict[str, list[float]]:
    """Возвращает {variant_name: [value_per_user, ...]}."""
    rows = await db.execute(
        text("""
            SELECT
                a.variant_name,
                a.user_id,
                COALESCE(SUM(e.value), 0) AS total_value
            FROM assignments a
            LEFT JOIN events e
                   ON e.user_id     = a.user_id
                  AND e.event_name  = :event_name
                  AND e.occurred_at >= a.assigned_at
                  AND e.value IS NOT NULL
            WHERE a.experiment_id = :experiment_id
            GROUP BY a.variant_name, a.user_id
        """),
        {"experiment_id": str(experiment_id), "event_name": event_name},
    )
    data: dict[str, list[float]] = {}
    for row in rows:
        data.setdefault(row.variant_name, []).append(float(row.total_value))
    return data


async def _get_ratio_data(
    db: AsyncSession,
    experiment_id: UUID,
    numerator_event: str,
    denominator_event: str,
) -> dict[str, tuple[list[float], list[float]]]:
    """
    Для ratio метрик: возвращает {variant_name: (numerator_per_user[], denominator_per_user[])}.

    numerator_event:   event_name числителя (например "purchase", value = сумма покупки)
    denominator_event: event_name знаменателя (например "session_start"):
        - value != NULL → используем value
        - value == NULL → считаем каждое событие как 1 (count semantics)

    Каждый assigned пользователь присутствует в результате (LEFT JOIN).
    Пользователи без событий получают (0, 0).
    """
    rows = await db.execute(
        text("""
            SELECT
                a.variant_name,
                a.user_id,
                COALESCE(SUM(
                    CASE WHEN e.event_name = :num_event
                         THEN COALESCE(e.value, 0) ELSE 0 END
                ), 0) AS numerator,
                COALESCE(SUM(
                    CASE WHEN e.event_name = :den_event
                         THEN COALESCE(e.value, 1) ELSE 0 END
                ), 0) AS denominator
            FROM assignments a
            LEFT JOIN events e
                   ON e.user_id     = a.user_id
                  AND (e.event_name = :num_event OR e.event_name = :den_event)
                  AND e.occurred_at >= a.assigned_at
            WHERE a.experiment_id = :experiment_id
            GROUP BY a.variant_name, a.user_id
        """),
        {
            "experiment_id": str(experiment_id),
            "num_event":     numerator_event,
            "den_event":     denominator_event,
        },
    )
    data: dict[str, tuple[list[float], list[float]]] = {}
    for row in rows:
        vn = row.variant_name
        if vn not in data:
            data[vn] = ([], [])
        data[vn][0].append(float(row.numerator))
        data[vn][1].append(float(row.denominator))
    return data


# Core analysis helpers 

def _find_control(variant_counts: dict[str, dict]) -> str:
    if "control" in variant_counts:
        return "control"
    return sorted(variant_counts.keys())[0]


def _apply_test_result(analysis: VariantAnalysis, test: TestResult) -> None:
    analysis.p_value = test.p_value
    analysis.ci_low = test.ci_low
    analysis.ci_high = test.ci_high
    analysis.effect_size = test.effect_size
    analysis.relative_lift = test.relative_lift
    analysis.is_significant = test.is_significant
    analysis.test_used = test.test_used


def _compute_achieved_mde(
    metric_type: MetricType,
    variant_analysis: VariantAnalysis,
    control_analysis: VariantAnalysis,
) -> float | None:
    """
    MDE при текущей выборке (post-experiment).

    Для ratio метрик: control_analysis.std_dev содержит std линеаризованных
    значений Z (установлено в run_analysis после delta_method_test).
    Это корректно — дисперсия ratio estimator отражена в std(Z).
    """
    n = min(variant_analysis.sample_size, control_analysis.sample_size)
    try:
        if metric_type == MetricType.CONVERSION:
            if 0.0 < control_analysis.mean < 1.0:
                mde = calculate_achieved_mde_conversion(n, control_analysis.mean)
                return None if math.isinf(mde) else mde

        elif metric_type in (MetricType.REVENUE, MetricType.DURATION):
            std = control_analysis.std_dev or variant_analysis.std_dev
            if std and std > 0:
                mde = calculate_achieved_mde_revenue(n, std)
                return None if math.isinf(mde) else mde

    except Exception as e:
        logger.warning(f"MDE расчёт не удался: {e}")

    return None


# Main analysis 

async def run_analysis(
    db: AsyncSession,
    experiment_id: UUID,
) -> list[MetricAnalysis]:
    """
    Полный анализ эксперимента.

    Для каждой метрики:
    - Conversion:        Z-тест для пропорций
    - Revenue/Duration:  Shapiro-Wilk → Welch t-test (нормальное) или
                         Mann-Whitney (ненормальное, n < 5000)
    - Ratio (с denominator_event_name):
                         Delta method (линеаризация Тейлора) +
                         декомпозиция числитель/знаменатель
    - Все treatment:     MDE post-experiment
    - Primary метрики:   BH коррекция на множественные сравнения
    """
    exp_result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.variants), selectinload(Experiment.metrics))
        .where(Experiment.id == experiment_id)
    )
    experiment = exp_result.scalar_one_or_none()
    if not experiment:
        raise ValueError(f"Эксперимент {experiment_id} не найден")

    variant_counts = await _get_variant_counts(db, experiment_id)
    if not variant_counts:
        raise ValueError("Нет назначений — анализ невозможен")

    control_name = _find_control(variant_counts)

    srm = check_srm(
        observed_counts={name: data["count"] for name, data in variant_counts.items()},
        expected_splits={name: data["traffic_split"] for name, data in variant_counts.items()},
    )
    if srm.srm_detected:
        logger.warning(f"SRM обнаружен в эксперименте {experiment_id}: p={srm.p_value:.4f}")

    metric_results: list[MetricAnalysis] = []
    all_primary_p_values: list[float] = []
    primary_analyses: list[tuple[MetricAnalysis, VariantAnalysis]] = []

    for metric in experiment.metrics:
        metric_analysis = MetricAnalysis(
            metric_id=metric.id,
            metric_name=metric.name,
            metric_type=metric.metric_type.value,
            is_primary=metric.is_primary,
            is_guardrail=metric.is_guardrail,
            srm=srm,
        )

        #  Conversion 
        if metric.metric_type == MetricType.CONVERSION:
            conv_data = await _get_conversion_data(db, experiment_id, metric.event_name)

            for variant_name, v_data in variant_counts.items():
                total, converted = conv_data.get(variant_name, (0, 0))
                va = VariantAnalysis(
                    variant_id=v_data["id"],
                    variant_name=variant_name,
                    sample_size=total,
                    mean=converted / total if total > 0 else 0.0,
                    test_used="z_test" if variant_name != control_name else None,
                )

                if variant_name != control_name and variant_name in conv_data:
                    c_total, c_conv = conv_data.get(control_name, (0, 0))
                    test = z_test_proportions(c_conv, c_total, converted, total)
                    if test:
                        _apply_test_result(va, test)

                metric_analysis.variants.append(va)

        #  Revenue / Duration 
        elif metric.metric_type in (MetricType.REVENUE, MetricType.DURATION):

            #  Ratio метрика: Delta method 
            if metric.denominator_event_name:
                ratio_data = await _get_ratio_data(
                    db, experiment_id, metric.event_name, metric.denominator_event_name
                )

                ctrl_num_list, ctrl_den_list = ratio_data.get(control_name, ([], []))
                ctrl_num = np.array(ctrl_num_list, dtype=float)
                ctrl_den = np.array(ctrl_den_list, dtype=float)

                sum_ctrl_den = float(np.sum(ctrl_den))
                theta_c = float(np.sum(ctrl_num)) / sum_ctrl_den if sum_ctrl_den > 0 else 0.0
                z_ctrl = ctrl_num - theta_c * ctrl_den
                ctrl_std_linearized = float(np.std(z_ctrl, ddof=1)) if len(z_ctrl) > 1 else None
                ctrl_num_mean = float(np.mean(ctrl_num)) if len(ctrl_num) > 0 else 0.0
                ctrl_den_mean = float(np.mean(ctrl_den)) if len(ctrl_den) > 0 else 0.0

                for variant_name, v_data in variant_counts.items():
                    trt_num_list, trt_den_list = ratio_data.get(variant_name, ([], []))
                    trt_num = np.array(trt_num_list, dtype=float)
                    trt_den = np.array(trt_den_list, dtype=float)

                    sum_trt_den = float(np.sum(trt_den))
                    theta_t = float(np.sum(trt_num)) / sum_trt_den if sum_trt_den > 0 else 0.0

                    va = VariantAnalysis(
                        variant_id=v_data["id"],
                        variant_name=variant_name,
                        sample_size=len(trt_num_list),
                        mean=theta_c if variant_name == control_name else theta_t,
                        std_dev=ctrl_std_linearized if variant_name == control_name else None,
                        numerator_mean=ctrl_num_mean if variant_name == control_name
                                       else (float(np.mean(trt_num)) if len(trt_num) > 0 else 0.0),
                        denominator_mean=ctrl_den_mean if variant_name == control_name
                                         else (float(np.mean(trt_den)) if len(trt_den) > 0 else 0.0),
                    )

                    if variant_name != control_name:
                        test = delta_method_test(
                            ctrl_num_list, ctrl_den_list,
                            trt_num_list, trt_den_list,
                        )
                        if test:
                            _apply_test_result(va, test)
                            # std линеаризованных значений для MDE
                            va.std_dev = test.std_dev_treatment

                        # Декомпозиция: относительный lift числителя и знаменателя
                        trt_num_mean = float(np.mean(trt_num)) if len(trt_num) > 0 else 0.0
                        trt_den_mean = float(np.mean(trt_den)) if len(trt_den) > 0 else 0.0
                        va.numerator_relative_lift = (
                            (trt_num_mean - ctrl_num_mean) / ctrl_num_mean * 100
                            if ctrl_num_mean != 0 else None
                        )
                        va.denominator_relative_lift = (
                            (trt_den_mean - ctrl_den_mean) / ctrl_den_mean * 100
                            if ctrl_den_mean != 0 else None
                        )
                        logger.info(
                            f"Delta method: {variant_name}/{metric.name}: "
                            f"θ_ctrl={theta_c:.4f}, θ_trt={theta_t:.4f}, "
                            f"num_lift={va.numerator_relative_lift:.1f}%, "
                            f"den_lift={va.denominator_relative_lift:.1f}%"
                            if va.numerator_relative_lift and va.denominator_relative_lift else
                            f"Delta method: {variant_name}/{metric.name}: "
                            f"θ_ctrl={theta_c:.4f}, θ_trt={theta_t:.4f}"
                        )

                    metric_analysis.variants.append(va)

            #  Обычная revenue/duration: Welch / Mann-Whitney 
            else:
                rev_data = await _get_revenue_data(db, experiment_id, metric.event_name)
                ctrl_values = rev_data.get(control_name, [])

                for variant_name, v_data in variant_counts.items():
                    values = rev_data.get(variant_name, [])
                    va = VariantAnalysis(
                        variant_id=v_data["id"],
                        variant_name=variant_name,
                        sample_size=len(values),
                        mean=float(np.mean(values)) if values else 0.0,
                        std_dev=float(np.std(values, ddof=1)) if len(values) > 1 else None,
                    )

                    if variant_name != control_name and variant_name in rev_data:
                        is_normal_ctrl, _ = check_normality(ctrl_values)
                        is_normal_trt, norm_p_trt = check_normality(values)
                        both_normal = is_normal_ctrl and is_normal_trt

                        va.is_normal = both_normal
                        va.normality_p_value = norm_p_trt

                        if not both_normal and len(values) < 5000:
                            test = mann_whitney_test(ctrl_values, values)
                            logger.info(
                                f"Mann-Whitney выбран для {variant_name}/{metric.name}: "
                                f"is_normal_ctrl={is_normal_ctrl}, is_normal_trt={is_normal_trt}"
                            )
                        else:
                            test = welch_t_test(ctrl_values, values)

                        if test:
                            _apply_test_result(va, test)

                    metric_analysis.variants.append(va)

        #  MDE post-experiment 
        control_va = next(
            (va for va in metric_analysis.variants if va.variant_name == control_name),
            None,
        )
        if control_va and control_va.sample_size >= 30:
            for va in metric_analysis.variants:
                if va.variant_name == control_name:
                    continue
                va.achieved_mde = _compute_achieved_mde(metric.metric_type, va, control_va)
                if va.achieved_mde is not None:
                    logger.debug(
                        f"MDE post-exp {metric.name}/{va.variant_name}: {va.achieved_mde:.4f}"
                    )

        #  Собираем p-values для BH коррекции 
        if metric.is_primary:
            for va in metric_analysis.variants:
                if va.variant_name != control_name and va.p_value is not None:
                    all_primary_p_values.append(va.p_value)
                    primary_analyses.append((metric_analysis, va))

        metric_results.append(metric_analysis)

    #  BH коррекция по всем primary метрикам 
    if all_primary_p_values:
        corrected = benjamini_hochberg(all_primary_p_values)
        for (_, va), is_sig in zip(primary_analyses, corrected):
            va.is_significant = is_sig

    #  Победители и guardrail нарушения 
    for metric_analysis in metric_results:
        for va in metric_analysis.variants:
            if va.variant_name == control_name:
                continue

            if metric_analysis.is_guardrail:
                if va.is_significant and va.effect_size is not None and va.effect_size < 0:
                    metric_analysis.guardrail_violated = True
                    logger.warning(
                        f"Guardrail нарушен: метрика={metric_analysis.metric_name}, "
                        f"вариант={va.variant_name}, effect={va.effect_size:.4f}"
                    )

            if metric_analysis.is_primary:
                guardrail_ok = not any(
                    m.guardrail_violated for m in metric_results if m.is_guardrail
                )
                if (
                    va.is_significant
                    and va.effect_size is not None
                    and va.effect_size > 0
                    and guardrail_ok
                ):
                    va.is_winner = True

    return metric_results
