import logging
from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Event
from app.schemas.event import EventCreate

logger = logging.getLogger(__name__)


async def save_event(db: AsyncSession, data: EventCreate) -> Event:
    """Сохраняет одно событие."""
    event = Event(
        user_id=data.user_id,
        event_name=data.event_name,
        value=data.value,
        properties=data.properties,
        occurred_at=data.occurred_at or datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def save_events_batch(db: AsyncSession, events: list[EventCreate]) -> int:
    """
    Bulk insert — один SQL запрос на весь батч.

    INSERT INTO events (...) VALUES (...), (...), (...) 
    
    Намного быстрее чем N отдельных INSERT.
    Критично при высоком трафике SDK.
    """
    if not events:
        return 0

    now = datetime.utcnow()
    rows = [
        {
            "user_id": e.user_id,
            "event_name": e.event_name,
            "value": e.value,
            "properties": e.properties,
            "occurred_at": e.occurred_at or now,
        }
        for e in events
    ]

    await db.execute(insert(Event), rows)
    await db.flush()

    logger.info(f"Batch insert: {len(rows)} events")
    return len(rows)
