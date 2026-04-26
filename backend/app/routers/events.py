import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_sdk_auth
from app.models.db import User
from app.schemas.event import BatchResponse, EventBatch, EventCreate, EventResponse
from app.services import event_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def track_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_sdk_auth),
):
    """Принимает одно событие от SDK. Требует X-API-Key или Bearer токен."""
    return await event_service.save_event(db, data)


@router.post("/events/batch", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def track_events_batch(
    data: EventBatch,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_sdk_auth),
):
    """
    Принимает батч событий — предпочтительный способ для SDK.
    Требует X-API-Key или Bearer токен.
    """
    inserted = await event_service.save_events_batch(db, data.events)
    return BatchResponse(received=len(data.events), inserted=inserted)
