"""
Pydantic schemas for the custom-metrics system (M-011).

A `CustomMetric` is a reusable, global template for what to measure.
Templates are snapshotted into per-experiment `Metric` rows at
experiment-creation time via `custom_metric_id`; editing a template
does NOT mutate existing experiment metrics (they are immutable
snapshots — this keeps analysis reproducible).

Shape
-----
- `event_name` — the numerator event.
- `aggregation` — count / sum / avg / unique_count over `events.value`.
- `filters`     — AND-combined list of property matchers (same operators
                  as segment_rules: eq/neq/in/not_in/gt/lt/gte/lte/contains).
- `denominator_*` — when set, metric is treated as a ratio (numerator per
                  denominator); the engine's delta-method branch detects
                  this from `denominator_event_name`.
- `metric_type` — conversion / revenue / duration. CONVERSION forbids a
                  denominator (ratios only make sense for revenue/duration).

Validation lives both at the schema layer (shape + cross-field checks
below) AND in `custom_metric_service.validate_definition` (operator
whitelist, denominator-aggregation compatibility).
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.db import MetricAggregation, MetricType


# ── Shared filter rule shape ───────────────────────────────────────────────


class MetricFilterCreate(BaseModel):
    """
    One filter rule applied to `events.properties` JSONB at read time.

    `value` is `Any` because the wire format is heterogeneous:
    scalars for eq/neq/gt/lt/gte/lte/contains and lists for in/not_in.
    """
    field:    str  = Field(..., min_length=1, max_length=100)
    operator: str  = Field(..., min_length=1, max_length=20)
    value:    Any
    priority: int  = 0
    enabled:  bool = True

    @field_validator("operator")
    @classmethod
    def _validate_operator(cls, v: str) -> str:
        if v not in VALID_METRIC_OPERATORS:
            raise ValueError(f"Неизвестный оператор фильтра: «{v}»")
        return v


# ── CustomMetric CRUD ──────────────────────────────────────────────────────


class CustomMetricCreate(BaseModel):
    key: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Stable identifier (lowercase, digits, hyphens, underscores).",
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    event_name: str = Field(..., min_length=1, max_length=255)
    aggregation: MetricAggregation
    metric_type: MetricType
    filters: list[MetricFilterCreate] | None = Field(default=None)
    denominator_event_name: str | None = Field(default=None, max_length=255)
    denominator_aggregation: MetricAggregation | None = Field(default=None)
    denominator_filters: list[MetricFilterCreate] | None = Field(default=None)
    is_guardrail: bool = Field(
        default=False,
        description="UX hint shown in the metric builder; enforcement is via GuardrailConfig.",
    )

    @model_validator(mode="after")
    def _check_denominator(self) -> "CustomMetricCreate":
        if self.denominator_event_name and self.metric_type == MetricType.CONVERSION:
            raise ValueError(
                "denominator_event_name не применим к conversion метрикам. "
                "Используйте metric_type=revenue или duration."
            )
        if (
            self.denominator_event_name
            and self.denominator_event_name == self.event_name
        ):
            raise ValueError(
                "denominator_event_name не может совпадать с event_name."
            )
        if self.denominator_event_name and not self.denominator_aggregation:
            raise ValueError(
                "denominator_aggregation обязателен, когда задан denominator_event_name."
            )
        return self


class CustomMetricUpdate(BaseModel):
    """Partial update — every field is optional."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    filters: list[MetricFilterCreate] | None = None
    denominator_event_name: str | None = Field(default=None, max_length=255)
    denominator_aggregation: MetricAggregation | None = None
    denominator_filters: list[MetricFilterCreate] | None = None
    is_guardrail: bool | None = None


class CustomMetricResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    event_name: str
    aggregation: MetricAggregation
    metric_type: MetricType
    filters: list[dict[str, Any]] | None
    denominator_event_name: str | None
    denominator_aggregation: MetricAggregation | None
    denominator_filters: list[dict[str, Any]] | None
    is_guardrail: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    used_by_count: int = Field(
        default=0,
        description="How many per-experiment Metric rows currently snapshot this template.",
    )

    model_config = {"from_attributes": True}


class CustomMetricListItem(BaseModel):
    """Lightweight payload for the list view — no filters/description body."""
    id: UUID
    key: str
    name: str
    description: str | None
    event_name: str
    aggregation: MetricAggregation
    metric_type: MetricType
    is_guardrail: bool
    used_by_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedCustomMetrics(BaseModel):
    items:    list[CustomMetricListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Dry-run / preview schemas ──────────────────────────────────────────────


class CustomMetricPreviewRequest(BaseModel):
    """Dry-run a custom metric against a hypothetical events payload."""
    user_properties: dict[str, Any] = Field(default_factory=dict)


class CustomMetricPreviewResponse(BaseModel):
    """Plain-English preview shown in the metric builder side panel."""
    summary:            str = Field(description="Human-readable definition of the metric.")
    matches:            bool
    matched_filters:    int
    total_filters:      int
    per_filter:         list[dict[str, Any]] = Field(default_factory=list)


# ── Snapshot schema (used by experiments.py when adding a metric) ──────────


class CustomMetricSnapshot(BaseModel):
    """
    Used inside `MetricCreate.custom_metric_id` when creating an
    experiment. When present, the experiment_service calls
    `custom_metric_service.copy_to_metric(template)` to snapshot
    event_name, aggregation, filters, denominator into the new Metric
    row. The CustomMetric itself is NOT mutated.
    """

    pass  # The presence of this model + `custom_metric_id: UUID | None`
          # on MetricCreate is enough — Pydantic just needs a type.


# ── Field validator that the engine also reuses ────────────────────────────

VALID_METRIC_OPERATORS: tuple[str, ...] = (
    "eq", "neq", "in", "not_in",
    "gt", "lt", "gte", "lte",
    "contains",
)


def _validate_filter_operators(filters: list[dict[str, Any]] | None) -> None:
    """
    Raise ValueError when any filter uses an operator outside the
    supported catalogue. Reused by the service so request bodies and
    dry-run previews share validation.
    """
    if not filters:
        return
    for f in filters:
        op = f.get("operator") if isinstance(f, dict) else None
        if op not in VALID_METRIC_OPERATORS:
            raise ValueError(f"Неизвестный оператор фильтра: «{op}»")
