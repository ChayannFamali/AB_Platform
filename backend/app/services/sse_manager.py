"""
SSE (Server-Sent Events) manager (M-008).

Implements Redis pub/sub fan-out for real-time experiment updates:

- **Publishers** (`publish_experiment_event`): called from the analysis
  pipeline after `run_and_save` (worker.py / analysis_service.run_and_save).
- **Subscribers** (`subscribe_experiment`): used by the SSE endpoint to
  consume the channel and yield SSE-formatted frames.

Channel naming:
    `results:{experiment_id}`  — per-experiment scope (matches ADR-003).

The module is pure pub/sub glue: no DB, no domain logic. Higher layers
(`routers/sse.py`, `analysis_service.py`) decide *what* gets published.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncIterator

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# ── Channel helpers ──────────────────────────────────────────────────────────


def channel_for(experiment_id: uuid.UUID | str) -> str:
    """Return the Redis pub/sub channel name for an experiment."""
    return f"results:{experiment_id}"


# ── Publishing ───────────────────────────────────────────────────────────────


async def publish_experiment_event(
    redis: Redis,
    experiment_id: uuid.UUID | str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """
    Publish an SSE event to the experiment's channel.

    Returns the number of subscribers that received the message (0 is
    fine — means no UI is currently subscribed to that experiment).
    Silently logs and returns 0 on Redis errors so that a flaky broker
    never breaks the analysis pipeline.
    """
    body = {"type": event_type, "data": payload or {}}
    try:
        return await redis.publish(channel_for(experiment_id), json.dumps(body))
    except Exception as e:
        logger.warning(
            "sse_publish_failed experiment=%s type=%s error=%s",
            str(experiment_id), event_type, str(e),
        )
        return 0


# ── Subscribing ──────────────────────────────────────────────────────────────


async def subscribe_experiment(
    redis: Redis,
    experiment_id: uuid.UUID | str,
) -> AsyncIterator[dict[str, Any]]:
    """
    Async generator yielding decoded event payloads from the experiment
    channel.

    Caller is responsible for closing the underlying pub/sub object — the
    recommended way is to wrap the consumer in `try/finally` and call
    `await pubsub.unsubscribe(); await pubsub.aclose()`.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_for(experiment_id))
    try:
        async for message in pubsub.listen():
            # `message["type"]` is `"message"` for real deliveries, `"subscribe"`
            # for the initial ack — ignore the latter.
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if raw is None:
                continue
            # redis.asyncio can deliver bytes when decode_responses=False on
            # the connection pool — normalize to str before JSON parsing.
            if isinstance(raw, bytes):
                try:
                    raw = raw.decode("utf-8")
                except UnicodeDecodeError as e:
                    logger.warning(
                        "sse_subscribe_decode_failed experiment=%s error=%s",
                        str(experiment_id), str(e),
                    )
                    continue
            try:
                yield json.loads(raw)
            except (TypeError, json.JSONDecodeError) as e:
                logger.warning(
                    "sse_subscribe_decode_failed experiment=%s error=%s raw=%r",
                    str(experiment_id), str(e), raw,
                )
                continue
    finally:
        try:
            await pubsub.unsubscribe(channel_for(experiment_id))
        except Exception:
            pass
        try:
            await pubsub.aclose()
        except Exception:
            pass


# ── SSE wire format ──────────────────────────────────────────────────────────


def format_sse(event_type: str, data: dict[str, Any] | str) -> str:
    """
    Render a single SSE frame.

    Format:
        event: <type>\\n
        data: <json>\\n
        \\n

    Browser EventSource dispatches based on the `event:` line, so the
    frontend uses `addEventListener('result_updated', handler)` rather
    than the default `onmessage` (which only fires for unnamed events).
    """
    body = json.dumps(data, default=str) if not isinstance(data, str) else data
    return f"event: {event_type}\ndata: {body}\n\n"


def format_heartbeat() -> str:
    """
    SSE comment line — keeps the connection alive through corporate
    proxies and nginx without triggering onmessage on the client.

    Format: `: ping\\n\\n`
    """
    return ": ping\n\n"


def format_retry(interval_ms: int = 3000) -> str:
    """
    SSE `retry:` directive — tells the browser how long to wait before
    reconnecting after a disconnect. EventSource honors this automatically.
    """
    return f"retry: {interval_ms}\n\n"