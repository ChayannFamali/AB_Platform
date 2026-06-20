from datetime import date
from uuid import UUID

from pydantic import BaseModel


class VariantResultResponse(BaseModel):
    variant_id: UUID
    variant_name: str
    sample_size: int
    mean: float
    std_dev: float | None
    p_value: float | None
    ci_low: float | None
    ci_high: float | None
    effect_size: float | None
    relative_lift: float | None
    is_significant: bool | None
    is_winner: bool
    ai_interpretation: str | None = None
    is_normal: bool | None = None
    normality_p_value: float | None = None
    test_used: str | None = None
    achieved_mde: float | None = None
    numerator_mean: float | None = None
    denominator_mean: float | None = None
    numerator_relative_lift: float | None = None
    denominator_relative_lift: float | None = None
    sequential_fpr: float | None = None
    sequential_boundary_crossed: bool | None = None

    model_config = {"from_attributes": True}


class MetricResultResponse(BaseModel):
    metric_id: UUID
    metric_name: str
    metric_type: str
    is_primary: bool
    is_guardrail: bool
    srm_detected: bool
    srm_p_value: float | None
    guardrail_violated: bool
    variants: list[VariantResultResponse]


class InsightResponse(BaseModel):
    """Rule-based finding (M-007). `title` and `description` are i18n keys;
    `params` provides interpolation values for the frontend translator."""
    type: str
    severity: str  # "success" | "warning" | "error" | "info"
    title: str
    description: str
    metric_id: str | None = None
    variant_id: str | None = None
    params: dict = {}


class AnalysisResponse(BaseModel):
    experiment_id: UUID
    metrics: list[MetricResultResponse]
    insights: list[InsightResponse] = []


# Cumulative dynamics

class DailySnapshotItem(BaseModel):
    """
    Один снапшот результата: один вариант, одна метрика, одна дата.
    Frontend группирует по (metric_id, variant_id) для построения time series.
    """
    snapshot_date: date
    metric_id: UUID
    metric_name: str
    variant_id: UUID
    variant_name: str
    sample_size: int
    mean: float
    p_value: float | None
    effect_size: float | None
    relative_lift: float | None
    ci_low: float | None
    ci_high: float | None
    is_significant: bool | None
    test_used: str | None
    sequential_fpr: float | None = None


class DailyResultsResponse(BaseModel):
    """
    Все daily снапшоты эксперимента, отсортированные по дате.

    Пример использования (frontend):
        series = {}
        for snap in response.snapshots:
            key = f"{snap.metric_id}_{snap.variant_id}"
            series[key] = series.get(key, []) + [
                {"date": snap.snapshot_date, "p_value": snap.p_value, ...}
            ]
    """
    experiment_id: UUID
    snapshots: list[DailySnapshotItem]
