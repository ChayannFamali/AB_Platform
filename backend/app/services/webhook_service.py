"""
Webhook service (M-013).

Outbound webhook delivery with HMAC-SHA256 signing, format
adapters (Slack / Discord / generic), and 3-attempt exponential
backoff retry.

Public surface
--------------
- CRUD: `create_webhook`, `list_webhooks`, `get_webhook_by_id`,
        `update_webhook`, `delete_webhook`, `list_deliveries`.
- Fan-out (called by analysis_service via the worker task):
        `deliver_event` — looks up all active webhooks subscribed to
        the event and calls `send_with_retries` for each.
- Synchronous test send: `send_test` — single attempt, no retries,
        returns the result to the caller.

Pure helpers (no I/O)
---------------------
- `sign_payload(secret, body)` — HMAC-SHA256 hex digest.
- `format_payload(event_type, payload, format)` — Slack / Discord
        / generic adapter.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import User, Webhook, WebhookDelivery
from app.schemas.webhook import (
    WebhookCreate,
    WebhookTestResponse,
    WebhookUpdate,
)

logger = logging.getLogger(__name__)


# ── Constants ───────────────────────────────────────────────────────────────

MAX_RESPONSE_BODY_LEN = 4096   # truncate stored response bodies
REQUEST_TIMEOUT_SEC    = 10.0   # per-attempt HTTP timeout
MAX_ATTEMPTS           = 3      # initial + 2 retries
RETRY_BACKOFF_SEC      = [0, 2, 4]  # attempt 1 immediate, then 2s, then 4s


# ── Pure helpers ────────────────────────────────────────────────────────────


def sign_payload(secret: str, body: bytes) -> str:
    """
    HMAC-SHA256 hex digest of the request body, keyed by `secret`.

    Returns `sha256=<hex>` — the GitHub-style header value most webhook
    providers expect. The `sha256=` prefix is also the convention used
    by Stripe / Slack-compatible receivers.
    """
    digest = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def format_payload(
    event_type: str,
    payload: dict[str, Any],
    fmt: str,
) -> dict[str, Any]:
    """
    Adapt a generic `payload` into the target format's wire shape.

    - "generic" — pass through (event_type + payload as-is).
    - "slack"   — Slack incoming-webhook JSON with `text` + `attachments`.
    - "discord" — Discord webhook JSON with `content` + `embeds`.

    Each adapter picks the most-prominent scalar from the payload
    (lift / p_value / srm p-value / etc.) and surfaces it as the
    headline of the message. The full payload stays available under
    the `payload` key for tools that want to render structured data.
    """
    if fmt == "slack":
        return _format_slack(event_type, payload)
    if fmt == "discord":
        return _format_discord(event_type, payload)
    # "generic" / fallback
    return {"event_type": event_type, "payload": payload}


def _format_slack(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Slack incoming-webhook shape: top-level `text` + rich attachments."""
    headline = _slack_headline(event_type, payload)
    fields: list[dict[str, Any]] = []
    for k, v in payload.items():
        if k in ("experiment_id", "variant_id", "metric_id"):
            continue
        if isinstance(v, float):
            v = round(v, 4)
        fields.append({"title": k, "value": str(v), "short": True})
    return {
        "text": headline,
        "attachments": [
            {
                "fallback": headline,
                "color": _slack_color(event_type),
                "fields": fields,
            }
        ],
    }


def _slack_color(event_type: str) -> str:
    return {
        "winner_detected":            "good",
        "srm_alert":                  "danger",
        "guardrail_violated":         "danger",
        "sequential_boundary_crossed": "good",
    }.get(event_type, "#999999")


def _slack_headline(event_type: str, payload: dict[str, Any]) -> str:
    titles = {
        "winner_detected":             ":tada: Winner detected",
        "srm_alert":                   ":warning: Sample Ratio Mismatch",
        "guardrail_violated":          ":no_entry: Guardrail violated",
        "sequential_boundary_crossed":  ":zap: Sequential boundary crossed",
    }
    title = titles.get(event_type, event_type)
    lift = payload.get("lift") or payload.get("relative_lift")
    p = payload.get("p_value")
    if isinstance(lift, (int, float)) and isinstance(p, (int, float)):
        return f"{title} (lift={lift:.4f}, p={p:.4g})"
    return title


def _format_discord(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Discord webhook shape: `content` (top-level) + `embeds` array."""
    titles = {
        "winner_detected":             "🏆 Winner detected",
        "srm_alert":                   "⚠️ Sample Ratio Mismatch",
        "guardrail_violated":          "⛔ Guardrail violated",
        "sequential_boundary_crossed": "⚡ Sequential boundary crossed",
    }
    fields: list[dict[str, Any]] = []
    for k, v in payload.items():
        if k in ("experiment_id", "variant_id", "metric_id"):
            continue
        if isinstance(v, float):
            v = round(v, 4)
        fields.append({"name": k, "value": str(v), "inline": True})
    return {
        "content": titles.get(event_type, event_type),
        "embeds": [
            {
                "title":  titles.get(event_type, event_type),
                "color":  _discord_color(event_type),
                "fields": fields,
            }
        ],
    }


def _discord_color(event_type: str) -> int:
    return {
        "winner_detected":             0x2ecc71,  # green
        "srm_alert":                   0xe74c3c,  # red
        "guardrail_violated":          0xe74c3c,
        "sequential_boundary_crossed": 0x3498db,  # blue
    }.get(event_type, 0x999999)


# ── Loaders / CRUD ──────────────────────────────────────────────────────────


async def get_webhook_by_id(
    db: AsyncSession, webhook_id: UUID
) -> Webhook | None:
    return (
        await db.execute(
            select(Webhook).where(Webhook.id == webhook_id)
        )
    ).scalar_one_or_none()


async def list_webhooks(
    db: AsyncSession, limit: int, offset: int
) -> tuple[list[Webhook], int]:
    items_q = (
        select(Webhook)
        .order_by(Webhook.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_q = select(func.count(Webhook.id))
    items = list((await db.execute(items_q)).scalars().all())
    total = (await db.execute(count_q)).scalar_one()
    return items, total


async def list_active_webhooks_for_event(
    db: AsyncSession, event_type: str
) -> list[Webhook]:
    """
    All active webhooks subscribed to `event_type`.

    `events` is a JSONB array — match via the `?` containment operator.
    """
    rows = await db.execute(
        select(Webhook).where(
            Webhook.is_active.is_(True),
            Webhook.events.op("?")(event_type),
        )
    )
    return list(rows.scalars().all())


async def create_webhook(
    db: AsyncSession, body: WebhookCreate, actor: User
) -> Webhook:
    webhook = Webhook(
        name       = body.name,
        url        = str(body.url),
        events     = body.events,
        secret     = body.secret,
        format     = body.format,
        is_active  = body.is_active,
        created_by = actor.id,
    )
    db.add(webhook)
    await db.flush()
    await db.refresh(webhook)
    return webhook


async def update_webhook(
    db: AsyncSession, webhook: Webhook, body: WebhookUpdate
) -> Webhook:
    if body.name is not None:
        webhook.name = body.name
    if body.url is not None:
        webhook.url = str(body.url)
    if body.events is not None:
        webhook.events = body.events
    if body.secret is not None:
        # Empty string is treated as "clear the secret".
        webhook.secret = body.secret or None
    if body.format is not None:
        webhook.format = body.format
    if body.is_active is not None:
        webhook.is_active = body.is_active
    await db.flush()
    await db.refresh(webhook)
    return webhook


async def delete_webhook(db: AsyncSession, webhook: Webhook) -> None:
    await db.delete(webhook)
    await db.flush()


async def list_deliveries(
    db: AsyncSession,
    webhook_id: UUID,
    *,
    limit: int,
    offset: int,
    success: bool | None = None,
) -> tuple[list[WebhookDelivery], int]:
    base = select(WebhookDelivery).where(
        WebhookDelivery.webhook_id == webhook_id,
    )
    if success is not None:
        base = base.where(WebhookDelivery.success.is_(success))
    items_q = (
        base.order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_q = select(func.count(WebhookDelivery.id)).where(
        WebhookDelivery.webhook_id == webhook_id,
    )
    if success is not None:
        count_q = count_q.where(WebhookDelivery.success.is_(success))
    items = list((await db.execute(items_q)).scalars().all())
    total = (await db.execute(count_q)).scalar_one()
    return items, total


# ── HTTP delivery (pure I/O, used by retry loop + test) ─────────────────────


async def _send_one(
    url: str,
    body: bytes,
    headers: dict[str, str],
) -> tuple[int, str, int]:
    """
    Single HTTP POST attempt. Returns (status_code, response_body,
    duration_ms). On transport errors (timeout, connection refused,
    etc.) returns (0, "<error message>", duration_ms).
    """
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
            resp = await client.post(url, content=body, headers=headers)
            elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
            text = resp.text or ""
            if len(text) > MAX_RESPONSE_BODY_LEN:
                text = text[:MAX_RESPONSE_BODY_LEN] + "...<truncated>"
            return (resp.status_code, text, elapsed_ms)
    except Exception as e:
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        return (0, f"{type(e).__name__}: {e}", elapsed_ms)


def _build_headers(
    webhook: Webhook, body: bytes
) -> dict[str, str]:
    """
    Build the outbound headers — Content-Type + (when applicable)
    X-Hub-Signature-256 / X-Signature-SHA256.
    """
    headers = {
        "Content-Type":  "application/json",
        "User-Agent":    "AB-Platform-Webhooks/1.0",
        "X-Webhook-Event": webhook.events[0] if webhook.events else "",
    }
    if webhook.secret:
        headers["X-Signature-SHA256"] = sign_payload(webhook.secret, body)
    return headers


async def send_with_retries(
    db: AsyncSession,
    webhook: Webhook,
    event_type: str,
    payload: dict[str, Any],
) -> WebhookDelivery:
    """
    Try up to MAX_ATTEMPTS times, with exponential backoff between
    attempts. Persists a WebhookDelivery row on every attempt (so the
    log shows the full retry history, not just the last one).
    """
    body_obj = format_payload(event_type, payload, webhook.format)
    body_bytes = json.dumps(body_obj, default=str).encode("utf-8")
    headers = _build_headers(webhook, body_bytes)

    last_status: int = 0
    last_body: str = ""
    last_duration = 0
    last_success = False

    for attempt_num in range(1, MAX_ATTEMPTS + 1):
        status, response_body, duration_ms = await _send_one(
            webhook.url, body_bytes, headers,
        )
        success = 200 <= status < 300

        # Persist this attempt BEFORE the next sleep so the log
        # reflects all attempts even if the worker is killed mid-retry.
        delivery = WebhookDelivery(
            webhook_id    = webhook.id,
            event_type    = event_type,
            payload       = body_obj,
            status_code   = status if status > 0 else None,
            response_body = response_body,
            attempt       = attempt_num,
            success       = success,
            duration_ms   = duration_ms,
        )
        db.add(delivery)
        await db.flush()

        last_status, last_body, last_duration = status, response_body, duration_ms
        last_success = success

        if success:
            break

        # Don't sleep after the final attempt.
        if attempt_num < MAX_ATTEMPTS:
            backoff = RETRY_BACKOFF_SEC[attempt_num]
            logger.info(
                f"webhook_retry webhook={webhook.id} attempt={attempt_num} "
                f"status={status} backoff={backoff}s",
            )
            await asyncio.sleep(backoff)

    # Final flush — db.flush() inside the loop already persisted each
    # attempt; the final commit happens at request teardown via
    # `get_db` dependency.
    return WebhookDelivery(
        webhook_id    = webhook.id,
        event_type    = event_type,
        payload       = body_obj,
        status_code   = last_status if last_status > 0 else None,
        response_body = last_body,
        attempt       = MAX_ATTEMPTS,
        success       = last_success,
        duration_ms   = last_duration,
    )


async def send_test(webhook: Webhook) -> WebhookTestResponse:
    """
    Synchronous test send. Single attempt, no retries. Used by the
    "Test" button on the WebhookSettingsPage to surface immediate
    feedback without polluting the retry-log with a forced-success.
    """
    body_obj = format_payload(
        "test",
        {"hello": "world", "ts": asyncio.get_event_loop().time()},
        webhook.format,
    )
    body_bytes = json.dumps(body_obj, default=str).encode("utf-8")
    headers = _build_headers(webhook, body_bytes)
    status, response_body, duration_ms = await _send_one(
        webhook.url, body_bytes, headers,
    )
    return WebhookTestResponse(
        status_code   = status,
        response_body = response_body or None,
        duration_ms   = duration_ms,
        success       = 200 <= status < 300,
    )


# ── Fan-out (used by the worker task) ───────────────────────────────────────


async def deliver_event(
    db: AsyncSession,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """
    Look up all active webhooks subscribed to `event_type` and deliver
    the payload to each. Returns the number of webhooks fanned out
    (NOT the number of successful deliveries — use the delivery log
    for that).

    A single failing webhook MUST NOT block the others; failures are
    logged inside `send_with_retries` and persisted to the delivery
    log.
    """
    webhooks = await list_active_webhooks_for_event(db, event_type)
    for webhook in webhooks:
        try:
            await send_with_retries(db, webhook, event_type, payload)
        except Exception as e:
            logger.error(
                f"webhook_fanout_failed webhook={webhook.id} "
                f"event={event_type} error={type(e).__name__}: {e}",
            )
    return len(webhooks)


# ── Audit helpers ──────────────────────────────────────────────────────────


def webhook_audit_details(webhook: Webhook) -> dict[str, Any]:
    return {
        "webhook_id": str(webhook.id),
        "name":       webhook.name,
        "url":        webhook.url,
        "events":     list(webhook.events or []),
        "format":     webhook.format,
        "is_active":  webhook.is_active,
        "has_secret": bool(webhook.secret),
    }