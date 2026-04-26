from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    event_name: str = Field(..., min_length=1, max_length=255)
    value: float | None = None                # для revenue метрик
    properties: dict | None = None            # любые доп. данные
    occurred_at: datetime | None = None       # если None → server time


class EventBatch(BaseModel):
    events: list[EventCreate] = Field(..., min_length=1, max_length=1000)


class EventResponse(BaseModel):
    id: UUID
    user_id: str
    event_name: str
    value: float | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


class BatchResponse(BaseModel):
    received: int
    inserted: int
