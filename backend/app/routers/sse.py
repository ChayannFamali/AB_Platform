"""
SSE router (M-008).

Exposes `GET /api/v1/events/stream?experiment_id=<uuid>&token=<jwt>` as a
`text/event-stream` `StreamingResponse`. The browser's EventSource API does
not allow custom request headers, so the JWT rides in the `token` query
parameter instead of `Authorization` (ADR-003).

Wire format:
    event: <type>\n
    data: <json>\n
    \n

The first event after connect is `connected` (so the client knows the
stream is live even if no analysis has happened yet). Heartbeats
(`: ping\n\n`) are emitted every 30s to keep corporate proxies from
closing the connection.

Permission: `results:read` — every standard role (admin / editor /
analyst / viewer) carries it, so this is effectively "any logged-in
user" while still going through RBAC.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db import Role, RolePermission, User
from app.services import sse_manager
from app.services.auth_service import _decode_token, get_user_by_id
from app.services.redis_client import get_redis
from app.services.rbac_service import get_user_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["sse"])

_HEARTBEAT_INTERVAL = 30.0  # seconds


async def _authenticate_token(token: str | None, db: AsyncSession) -> User:
    """
    JWT auth via query parameter. Decodes the token (same secret/algorithm
    as `auth_service.create_access_token`) and loads the user with
    roles+permissions eager so RBAC can run without lazy queries.

    Raises HTTP 401 for missing / invalid / inactive tokens.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется токен (?token=<jwt>)",
        )
    try:
        payload = _decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
        )

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или деактивирован",
        )
    # Re-fetch with roles+permissions eager-loaded.
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    return result.scalar_one()


@router.get("/stream")
async def stream_experiment_events(
    request: Request,
    experiment_id: uuid.UUID = Query(..., description="Experiment to subscribe to"),
    token: str | None = Query(default=None, description="JWT access token"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # ── Auth ─────────────────────────────────────────────────────────────
    user = await _authenticate_token(token, db)

    # ── Permission check ─────────────────────────────────────────────────
    if "results:read" not in get_user_permissions(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Отсутствует право: results:read",
        )

    # ── Stream ───────────────────────────────────────────────────────────
    async def event_generator() -> AsyncIterator[str]:
        # Initial frame so clients can confirm the connection is live even
        # before any analysis runs.
        yield sse_manager.format_sse(
            "connected",
            {"experiment_id": str(experiment_id)},
        )
        yield sse_manager.format_retry()

        # Two concurrent loops: Redis pub/sub messages and heartbeats.
        # We use an asyncio queue to merge them.
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def pump_redis() -> None:
            try:
                async for message in sse_manager.subscribe_experiment(
                    redis, experiment_id
                ):
                    event_type = message.get("type", "message")
                    payload = message.get("data") or {}
                    await queue.put(sse_manager.format_sse(event_type, payload))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(
                    "sse_subscribe_failed",
                    experiment_id=str(experiment_id),
                    error=str(e),
                )
                await queue.put(
                    sse_manager.format_sse("error", {"detail": "stream interrupted"})
                )
            finally:
                # Sentinel so the heartbeat loop also shuts down.
                await queue.put(None)

        async def pump_heartbeat() -> None:
            try:
                while True:
                    await asyncio.sleep(_HEARTBEAT_INTERVAL)
                    await queue.put(sse_manager.format_heartbeat())
            except asyncio.CancelledError:
                raise

        pump_redis_task   = asyncio.create_task(pump_redis())
        pump_heartbeat_task = asyncio.create_task(pump_heartbeat())

        try:
            while True:
                # Bail out if the client disconnected (e.g. closed tab).
                if await request.is_disconnected():
                    break
                frame = await queue.get()
                if frame is None:
                    # pump_redis finished → no more frames coming.
                    break
                yield frame
        finally:
            pump_redis_task.cancel()
            pump_heartbeat_task.cancel()
            # Drain cancellation so we don't leak warnings.
            for task in (pump_redis_task, pump_heartbeat_task):
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return _sse_response(event_generator())


def _sse_response(generator: AsyncIterator[str]):
    """
    Build a StreamingResponse with the SSE-specific headers.

    `Cache-Control: no-cache` and `X-Accel-Buffering: no` are required so
    nginx doesn't buffer frames (proxy_buffering off) and so clients see
    updates immediately rather than after the cache TTL.
    """
    from fastapi.responses import StreamingResponse

    headers = {
        "Cache-Control":     "no-cache",
        "X-Accel-Buffering": "no",
        "Connection":        "keep-alive",
    }
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=headers,
    )