from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.db import ExperimentStatus, MetricType


# Variant 

class VariantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    traffic_split: float = Field(..., gt=0, le=100)


class VariantResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    name: str
    description: str | None
    traffic_split: float
    created_at: datetime

    model_config = {"from_attributes": True}


# Metric 

class MetricCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    event_name: str = Field(..., min_length=1, max_length=255)
    denominator_event_name: str | None = Field( 
        default=None,
        max_length=255,
        description=(
            "Event name знаменателя для ratio метрик. "
            "Например: event_name='purchase', denominator_event_name='session_start' "
            "→ metric = sum(purchase.value) / count(session_start). "
            "Если None — стандартная revenue/duration метрика."
        ),
    )
    metric_type: MetricType
    is_primary: bool = False
    is_guardrail: bool = False

    @model_validator(mode="after")
    def validate_denominator(self) -> "MetricCreate":
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
        return self


class MetricResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    name: str
    event_name: str
    denominator_event_name: str | None  
    metric_type: MetricType
    is_primary: bool
    is_guardrail: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Experiment 

class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    traffic_percentage: float = Field(default=100.0, gt=0, le=100)
    mutex_group_id: UUID | None = None
    variants: list[VariantCreate] = Field(..., min_length=2)
    metrics: list[MetricCreate] = Field(..., min_length=1)
    is_sequential: bool = Field(
        default=False,
        description=(
            "Opt-in to always-valid sequential testing (mSPRT). "
            "When true, the engine computes an always-valid p-value alongside "
            "the fixed-horizon test; users may peek at results anytime without "
            "inflating the false-positive rate."
        ),
    )

    @model_validator(mode="after")
    def validate_splits(self) -> "ExperimentCreate":
        total = sum(v.traffic_split for v in self.variants)
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Сумма traffic_split вариантов должна быть 100%, получено {total}%")
        return self

    @model_validator(mode="after")
    def validate_primary_metric(self) -> "ExperimentCreate":
        if not any(m.is_primary for m in self.metrics):
            raise ValueError("Должна быть хотя бы одна primary метрика")
        return self
class ExperimentUpdate(BaseModel):
    """Схема для частичного обновления эксперимента"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    traffic_percentage: float | None = Field(None, gt=0, le=100)
    mutex_group_id: UUID | None = None


class ExperimentStatusUpdate(BaseModel):
    status: ExperimentStatus


class ExperimentResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: ExperimentStatus
    traffic_percentage: float
    mutex_group_id: UUID | None
    started_at: datetime | None
    ended_at: datetime | None
    is_sequential: bool
    created_at: datetime
    updated_at: datetime
    variants: list[VariantResponse]
    metrics: list[MetricResponse]

    model_config = {"from_attributes": True}


class ExperimentListItem(BaseModel):
    id: UUID
    name: str
    status: ExperimentStatus
    traffic_percentage: float
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# MutexGroup 

class MutexGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class MutexGroupResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# Pagination 

class PaginatedExperiments(BaseModel):
    items:    list[ExperimentListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool
