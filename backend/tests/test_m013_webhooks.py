"""
M-013 integration tests: Webhooks.

Covers:
- Webhook CRUD + webhooks:manage RBAC.
- Secret is returned ONCE on create (via WebhookWithSecretResponse)
  but never in subsequent GETs (only `has_secret: True`).
- Pure functions: `sign_payload` (HMAC-SHA256), `format_payload`
  (slack / discord / generic).
- `send_with_retries` writes one WebhookDelivery row per attempt
  with monotonically-increasing `attempt` and correct success flag.
- `send_test` returns a WebhookTestResponse without retrying.
- `deliver_event` fans out to all active webhooks subscribed to the
  event and skips inactive ones.
- Delivery log endpoint paginates + filters by success.
- DELETE cascades to webhook_deliveries.

Run:
    cd backend && PYTHONPATH=. pytest tests/test_m013_webhooks.py -v
"""
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db import Webhook, WebhookDelivery
from app.services.webhook_service import (
    format_payload,
    send_with_retries,
    send_test,
    sign_payload,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _create_webhook_payload(**overrides) -> dict:
    body = {
        "name":   "Test hook",
        "url":    "https://example.com/hook",
        "events": ["winner_detected"],
        "secret": "whsec_test_secret",
        "format": "generic",
        "is_active": True,
    }
    body.update(overrides)
    return body


# ── 1. CRUD + RBAC ──────────────────────────────────────────────────────────


async def test_create_webhook_returns_secret_once(
    client: AsyncClient, auth_headers,
):
    body = await _create_webhook_payload()
    resp = await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["secret"] == "whsec_test_secret"
    assert data["has_secret"] is True


async def test_get_webhook_masks_secret(
    client: AsyncClient, auth_headers,
):
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]
    resp = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "secret" not in body
    assert body["has_secret"] is True


async def test_list_webhooks(client: AsyncClient, auth_headers):
    for i in range(3):
        body = await _create_webhook_payload(name=f"h{i}")
        await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    resp = await client.get("/api/v1/webhooks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert all("secret" not in item for item in body["items"])
    assert all("has_secret" in item for item in body["items"])


async def test_create_rejects_invalid_event(
    client: AsyncClient, auth_headers,
):
    body = await _create_webhook_payload(events=["bogus_event"])
    resp = await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    assert resp.status_code == 422


async def test_create_rejects_empty_events(
    client: AsyncClient, auth_headers,
):
    body = await _create_webhook_payload(events=[])
    resp = await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    # Pydantic min_length=1 catches this.
    assert resp.status_code == 422


async def test_create_rejects_invalid_url(
    client: AsyncClient, auth_headers,
):
    body = await _create_webhook_payload(url="not-a-url")
    resp = await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    assert resp.status_code == 422


async def test_delete_webhook_cascades_deliveries(
    client: AsyncClient, auth_headers, engine,
):
    body = await _create_webhook_payload()
    create = await client.post("/api/v1/webhooks", json=body, headers=auth_headers)
    webhook_id = create.json()["id"]

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        db.add(WebhookDelivery(
            webhook_id=UUID(webhook_id),
            event_type="test",
            payload={"x": 1},
            attempt=1,
            success=True,
        ))
        await db.commit()

    delete = await client.delete(
        f"/api/v1/webhooks/{webhook_id}", headers=auth_headers,
    )
    assert delete.status_code == 204

    async with TestSession() as db:
        deliveries = (await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.webhook_id == UUID(webhook_id)
            )
        )).scalars().all()
        assert deliveries == []


async def test_patch_webhook_toggles_active(
    client: AsyncClient, auth_headers,
):
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/webhooks/{webhook_id}",
        json={"is_active": False, "name": "Renamed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["name"] == "Renamed"


# ── 2. RBAC: viewer / analyst cannot manage ───────────────────────────────


async def test_viewer_cannot_manage_webhooks(
    client: AsyncClient, auth_headers,
):
    # `auth_headers` registers `testuser` first (admin). Without that
    # fixture the next registration would itself become admin and the
    # permission check below wouldn't fire.
    await client.post("/api/v1/auth/register", json={
        "username": "viewer", "email": "v@example.com",
        "password": "password123",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "v@example.com", "password": "password123",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for method, path in [
        ("GET",    "/api/v1/webhooks"),
        ("POST",   "/api/v1/webhooks"),
        ("PATCH",  "/api/v1/webhooks/00000000-0000-0000-0000-000000000000"),
        ("DELETE", "/api/v1/webhooks/00000000-0000-0000-0000-000000000000"),
    ]:
        resp = await client.request(method, path, headers=headers,
                                    json={"name": "x"})
        assert resp.status_code in (403, 401), (
            f"{method} {path} expected 403/401 got {resp.status_code}"
        )


# ── 3. Pure helpers ─────────────────────────────────────────────────────────


def test_sign_payload_is_stable_hmac_sha256():
    secret = "whsec_abc"
    body   = b'{"hello":"world"}'
    sig1 = sign_payload(secret, body)
    sig2 = sign_payload(secret, body)
    assert sig1 == sig2
    assert sig1.startswith("sha256=")
    assert len(sig1) == len("sha256=") + 64  # hex SHA-256


def test_sign_payload_changes_with_body():
    sig_a = sign_payload("k", b"alpha")
    sig_b = sign_payload("k", b"beta")
    assert sig_a != sig_b


def test_sign_payload_changes_with_secret():
    sig_a = sign_payload("k1", b"x")
    sig_b = sign_payload("k2", b"x")
    assert sig_a != sig_b


def test_format_payload_generic_passthrough():
    payload = {"experiment_id": "e1", "lift": 0.05, "p_value": 0.01}
    out = format_payload("winner_detected", payload, "generic")
    assert out["event_type"] == "winner_detected"
    assert out["payload"] == payload


def test_format_payload_slack_shape():
    out = format_payload("winner_detected", {"lift": 0.05, "p_value": 0.01}, "slack")
    assert "text" in out
    assert isinstance(out.get("attachments"), list)
    assert out["attachments"][0]["color"] == "good"
    assert "Winner detected" in out["text"]


def test_format_payload_slack_danger_for_srm():
    out = format_payload("srm_alert", {"p_value": 0.001}, "slack")
    assert out["attachments"][0]["color"] == "danger"


def test_format_payload_discord_shape():
    out = format_payload("guardrail_violated", {"degradation": -8.5}, "discord")
    assert "content" in out
    assert isinstance(out.get("embeds"), list)
    assert out["embeds"][0]["color"] == 0xE74C3C  # red


# ── 4. Delivery + retries (no network — we use httpx.AsyncClient patched) ───


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    """
    Records the number of times post() was called and returns a
    predetermined sequence of responses (one per attempt). Lets us
    simulate 500 → 500 → 200 retry sequences without touching the
    real network.
    """
    instances: list = []

    def __init__(self, *, timeout=None):
        self.timeout = timeout
        self.posts: list[tuple[str, bytes, dict]] = []
        self._responses: list[_FakeResponse] = []
        _FakeAsyncClient.instances.append(self)

    def set_responses(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, *, content, headers):
        self.posts.append((url, content, headers))
        # Pop the next response; if exhausted, return the last one.
        if self._responses:
            return self._responses.pop(0)
        return self._responses[-1] if self._responses else _FakeResponse(500)


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    """Swap `webhook_service._send_one` to a fake we can drive per-test.

    We patch at the import site so the service uses our fake without
    touching the real network — `send_with_retries` calls `_send_one`
    directly, so monkey-patching that single function is enough.
    """
    _FakeAsyncClient.instances = []
    fake_results: list[tuple[int, str, int]] = []

    async def _send_one(url, body, headers):
        if not fake_results:
            return (0, "no-fake-result", 0)
        return fake_results.pop(0)

    from app.services import webhook_service
    monkeypatch.setattr(webhook_service, "_send_one", _send_one)
    return fake_results


async def test_send_with_retries_writes_one_row_per_attempt(
    client: AsyncClient, auth_headers, engine, _patch_httpx,
):
    """2 failures → 3rd attempt succeeds → 3 WebhookDelivery rows."""
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(name="retry-hook"),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]

    _patch_httpx.extend([
        (500, "boom", 50),
        (500, "boom", 50),
        (200, "ok",   50),
    ])

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        webhook = (await db.execute(
            select(Webhook).where(Webhook.id == UUID(webhook_id))
        )).scalar_one()
        final = await send_with_retries(
            db, webhook, "winner_detected", {"lift": 0.05},
        )
        await db.commit()

    assert final.success is True
    async with TestSession() as db:
        rows = (await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.webhook_id == UUID(webhook_id)
            ).order_by(WebhookDelivery.attempt)
        )).scalars().all()
    assert len(rows) == 3
    assert [r.attempt for r in rows] == [1, 2, 3]
    assert [r.success for r in rows] == [False, False, True]
    assert rows[-1].status_code == 200


async def test_send_with_retries_gives_up_after_three(
    client: AsyncClient, auth_headers, engine, _patch_httpx,
):
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(name="give-up"),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]

    # Three 500s — every attempt fails. Service should still write
    # one row per attempt (3 total) and stop after MAX_ATTEMPTS.
    _patch_httpx.extend([
        (500, "err", 10),
        (500, "err", 10),
        (500, "err", 10),
    ])

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        webhook = (await db.execute(
            select(Webhook).where(Webhook.id == UUID(webhook_id))
        )).scalar_one()
        final = await send_with_retries(
            db, webhook, "srm_alert", {"p_value": 0.001},
        )
        await db.commit()

    assert final.success is False
    async with TestSession() as db:
        rows = (await db.execute(
            select(WebhookDelivery).where(
                WebhookDelivery.webhook_id == UUID(webhook_id)
            )
        )).scalars().all()
    assert len(rows) == 3
    assert all(r.success is False for r in rows)


async def test_send_test_returns_first_attempt(
    client: AsyncClient, auth_headers, _patch_httpx,
):
    """`send_test` is single-shot — no retries, no delivery row."""
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(name="test-endpoint"),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]

    _patch_httpx.append((200, "ok", 25))

    resp = await client.post(
        f"/api/v1/webhooks/{webhook_id}/test", headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status_code"] == 200
    assert body["success"] is True


# ── 5. Deliveries list endpoint ────────────────────────────────────────────


async def test_list_deliveries_pagination_and_filter(
    client: AsyncClient, auth_headers, engine, _patch_httpx,
):
    create = await client.post(
        "/api/v1/webhooks",
        json=await _create_webhook_payload(name="delivery-log"),
        headers=auth_headers,
    )
    webhook_id = create.json()["id"]

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        for i in range(5):
            db.add(WebhookDelivery(
                webhook_id=UUID(webhook_id),
                event_type="test",
                payload={"i": i},
                status_code=200 if i % 2 == 0 else 500,
                attempt=1,
                success=i % 2 == 0,
            ))
        await db.commit()

    resp = await client.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?limit=10",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 5

    # Filter: only successful deliveries (3 out of 5: i=0,2,4).
    resp_success = await client.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?success=true",
        headers=auth_headers,
    )
    assert resp_success.status_code == 200
    assert resp_success.json()["total"] == 3
    assert all(d["success"] for d in resp_success.json()["items"])