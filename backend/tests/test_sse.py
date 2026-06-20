"""
Tests for the SSE (Server-Sent Events) layer (M-008).

Scopes:
1. **Pure unit tests** for `sse_manager.format_*` helpers and publisher
   error handling — no live I/O.
2. **HTTP integration tests** against the real FastAPI app, using the
   real Redis at `localhost:6379` (Docker `ab-platform-redis-1`).

The SSE endpoint requires actual Redis pub/sub semantics (the conftest's
`AsyncMock` does not fan-out messages between publishers and subscribers),
so we override `get_redis` for these tests to point at the real Redis
pool.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.main import app
from app.services import sse_manager
from app.services.redis_client import get_redis, pool as redis_pool


# ── Unit tests: wire format ──────────────────────────────────────────────────

def test_format_sse_named_event():
    frame = sse_manager.format_sse("result_updated", {"experiment_id": "abc"})
    # EventSource uses `event:` to dispatch by name; `data:` carries the JSON.
    assert frame.startswith("event: result_updated\n")
    assert 'data: {"experiment_id": "abc"}' in frame
    assert frame.endswith("\n\n")


def test_format_sse_with_string_data():
    """String data is passed through unchanged (no double-encoding)."""
    frame = sse_manager.format_sse("ping", "hello")
    assert frame == "event: ping\ndata: hello\n\n"


def test_format_heartbeat_is_comment():
    """Heartbeat uses SSE comment syntax so it doesn't fire onmessage."""
    hb = sse_manager.format_heartbeat()
    assert hb == ": ping\n\n"
    # Comments MUST start with a colon and not include `data:` or `event:`.
    assert not hb.lstrip().startswith("data:")
    assert not hb.lstrip().startswith("event:")


def test_format_retry_directive():
    """`retry:` tells the browser how long to wait before reconnecting."""
    r = sse_manager.format_retry(5000)
    assert r == "retry: 5000\n\n"


def test_channel_for():
    assert sse_manager.channel_for(uuid.UUID("11111111-1111-1111-1111-111111111111")) == \
        "results:11111111-1111-1111-1111-111111111111"
    assert sse_manager.channel_for("any-string") == "results:any-string"


# ── Unit tests: publisher error handling ─────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_experiment_event_returns_subscriber_count():
    """publish_experiment_event returns the number of subscribers reached."""
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(return_value=2)

    count = await sse_manager.publish_experiment_event(
        fake_redis,
        uuid.uuid4(),
        "result_updated",
        {"foo": "bar"},
    )

    assert count == 2
    fake_redis.publish.assert_awaited_once()
    channel_arg, payload_arg = fake_redis.publish.call_args.args
    assert channel_arg.startswith("results:")
    body = json.loads(payload_arg)
    assert body["type"] == "result_updated"
    assert body["data"] == {"foo": "bar"}


@pytest.mark.asyncio
async def test_publish_swallows_redis_errors():
    """A flaky Redis MUST NOT break analysis — publisher logs and returns 0."""
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(side_effect=ConnectionError("redis down"))

    count = await sse_manager.publish_experiment_event(
        fake_redis, uuid.uuid4(), "result_updated",
    )

    assert count == 0  # swallowed, not propagated


# ── Integration tests: real Redis pub/sub round-trip ─────────────────────────


@pytest.fixture
async def real_redis_client():
    """Override the conftest's mock Redis with the real Redis pool."""
    async def _override():
        async with Redis(connection_pool=redis_pool) as r:
            yield r

    app.dependency_overrides[get_redis] = _override
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_subscribe_yields_decoded_messages(real_redis_client):
    """
    subscribe_experiment parses JSON and skips subscribe acks. Uses real
    Redis so the channel actually carries published messages.

    IMPORTANT: subscribe FIRST, publish in a background task. If you
    publish before subscribing, the messages are dropped by Redis
    pub/sub (it only delivers to current subscribers).

    Note on event loops: pytest-asyncio creates a fresh loop per test,
    so the module-level `redis_pool` may have connections bound to a
    previous loop. We build a fresh pool here to be safe.
    """
    from redis.asyncio import ConnectionPool

    fresh_pool = ConnectionPool.from_url(
        "redis://localhost:6379", decode_responses=True,
    )
    try:
        async with Redis(connection_pool=fresh_pool) as redis:
            received: list[dict] = []

            async def collect():
                async for msg in sse_manager.subscribe_experiment(redis, "test-sub"):
                    received.append(msg)
                    if len(received) >= 2:
                        return

            collect_task = asyncio.create_task(collect())
            # Give the subscriber a moment to subscribe before publishing.
            await asyncio.sleep(0.1)

            await redis.publish("results:test-sub", json.dumps({"type": "result_updated", "data": {"x": 1}}))
            await redis.publish("results:test-sub", json.dumps({"type": "srm_alert", "data": {"p_value": 0.01}}))
            await redis.publish("results:test-sub", "garbage-not-json")

            try:
                await asyncio.wait_for(collect_task, timeout=3.0)
            except asyncio.TimeoutError:
                collect_task.cancel()

        types = [m.get("type") for m in received]
        assert "result_updated" in types
        assert "srm_alert" in types
    finally:
        await fresh_pool.aclose()


# ── HTTP integration: SSE endpoint ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_endpoint_requires_token(
    client: AsyncClient, auth_headers: dict
):
    """No token → 401."""
    exp_resp = await client.post("/api/v1/experiments", json={
        "name": "Test",
        "variants": [
            {"name": "control",   "traffic_split": 50},
            {"name": "treatment", "traffic_split": 50},
        ],
        "metrics": [{
            "name": "m", "event_name": "e", "metric_type": "conversion",
            "is_primary": True,
        }],
    }, headers=auth_headers)
    assert exp_resp.status_code == 201, exp_resp.text
    exp_id = exp_resp.json()["id"]

    resp = await client.get(f"/api/v1/events/stream?experiment_id={exp_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sse_endpoint_rejects_bad_token(
    client: AsyncClient, auth_headers: dict
):
    """Invalid token → 401."""
    exp_resp = await client.post("/api/v1/experiments", json={
        "name": "Test",
        "variants": [
            {"name": "control",   "traffic_split": 50},
            {"name": "treatment", "traffic_split": 50},
        ],
        "metrics": [{
            "name": "m", "event_name": "e", "metric_type": "conversion",
            "is_primary": True,
        }],
    }, headers=auth_headers)
    assert exp_resp.status_code == 201, exp_resp.text
    exp_id = exp_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/events/stream?experiment_id={exp_id}&token=not-a-jwt",
    )
    assert resp.status_code == 401


# Auth (no token, bad token) above are sufficient — the permission check
# is covered by the standard RBAC matrix in `test_rbac.py`. The streaming
# flow itself is covered by `test_subscribe_yields_decoded_messages` which
# drives the same `subscribe_experiment` generator that the SSE endpoint
# uses internally. End-to-end HTTP tests of the SSE endpoint are
# unreliable: httpx 0.28's ASGITransport buffers streaming response bodies
# until completion, and the SSE endpoint never completes by design.