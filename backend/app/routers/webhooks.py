"""
Webhook router (M-013).

UI endpoints (JWT + RBAC `webhooks:manage`):

  GET    /api/v1/webhooks                       — paginated list
  POST   /api/v1/webhooks                       — create (returns the secret once)
  GET    /api/v1/webhooks/{id}                  — get by id
  PATCH  /api/v1/webhooks/{id}                  — partial update
  DELETE /api/v1/webhooks/{id}                  — delete
  POST   /api/v1/webhooks/{id}/test             — synchronous test send
  GET    /api/v1/webhooks/{id}/deliveries       — paginated delivery log

The create endpoint returns the plain `secret` (via
`WebhookWithSecretResponse`) so the operator can copy it into their
receiver. All subsequent reads use the masked `WebhookResponse`
(`has_secret: bool`, no plain secret).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import User, Webhook, WebhookDelivery
from app.schemas.webhook import (
    PaginatedWebhookDeliveries,
    PaginatedWebhooks,
    WebhookCreate,
    WebhookListItem,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdate,
    WebhookWithSecretResponse,
)
from app.services import audit_service, rbac_service, webhook_service

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(rbac_service.require_permission("webhooks:manage"))],
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _masked_response(webhook: Webhook) -> WebhookResponse:
    return WebhookResponse(
        id         = webhook.id,
        name       = webhook.name,
        url        = webhook.url,
        events     = list(webhook.events or []),
        format     = webhook.format,
        is_active  = webhook.is_active,
        has_secret = bool(webhook.secret),
        created_by = webhook.created_by,
        created_at = webhook.created_at,
        updated_at = webhook.updated_at,
    )


def _list_item(webhook: Webhook) -> WebhookListItem:
    return WebhookListItem(
        id         = webhook.id,
        name       = webhook.name,
        url        = webhook.url,
        events     = list(webhook.events or []),
        format     = webhook.format,
        is_active  = webhook.is_active,
        has_secret = bool(webhook.secret),
        created_at = webhook.created_at,
    )


def _with_secret_response(
    webhook: Webhook, secret: str | None
) -> WebhookWithSecretResponse:
    return WebhookWithSecretResponse(
        id         = webhook.id,
        name       = webhook.name,
        url        = webhook.url,
        events     = list(webhook.events or []),
        format     = webhook.format,
        is_active  = webhook.is_active,
        has_secret = bool(webhook.secret),
        created_by = webhook.created_by,
        created_at = webhook.created_at,
        updated_at = webhook.updated_at,
        secret     = secret,
    )


def _delivery_response(d: WebhookDelivery):
    return {
        "id":            d.id,
        "webhook_id":    d.webhook_id,
        "event_type":    d.event_type,
        "status_code":   d.status_code,
        "response_body": d.response_body,
        "attempt":       d.attempt,
        "success":       d.success,
        "duration_ms":   d.duration_ms,
        "created_at":    d.created_at,
    }


# ── CRUD ───────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedWebhooks)
async def list_webhooks(
    limit:  int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    db: AsyncSession = Depends(get_db),
):
    items, total = await webhook_service.list_webhooks(db, limit, offset)
    return PaginatedWebhooks(
        items=[_list_item(w) for w in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.post(
    "",
    response_model=WebhookWithSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    body: WebhookCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("webhooks:manage")),
):
    webhook = await webhook_service.create_webhook(db, body, actor)
    await audit_service.log_action(
        db,
        actor=actor,
        action="create",
        resource_type="webhook",
        resource_id=webhook.id,
        details=webhook_service.webhook_audit_details(webhook),
        request=request,
    )
    # Return the plain secret ONLY here so the operator can copy it.
    return _with_secret_response(webhook, webhook.secret)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    webhook = await webhook_service.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook не найден")
    return _masked_response(webhook)


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("webhooks:manage")),
):
    webhook = await webhook_service.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook не найден")
    webhook = await webhook_service.update_webhook(db, webhook, body)
    await audit_service.log_action(
        db,
        actor=actor,
        action="update",
        resource_type="webhook",
        resource_id=webhook.id,
        details={
            **webhook_service.webhook_audit_details(webhook),
            "fields_changed": [
                f for f in ("name", "url", "events", "secret",
                            "format", "is_active")
                if getattr(body, f) is not None
            ],
        },
        request=request,
    )
    return _masked_response(webhook)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_webhook(
    webhook_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(rbac_service.require_permission("webhooks:manage")),
):
    webhook = await webhook_service.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook не найден")
    details = webhook_service.webhook_audit_details(webhook)
    await webhook_service.delete_webhook(db, webhook)
    await audit_service.log_action(
        db,
        actor=actor,
        action="delete",
        resource_type="webhook",
        resource_id=webhook_id,
        details=details,
        request=request,
    )


# ── Test send ──────────────────────────────────────────────────────────────


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
)
async def test_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    webhook = await webhook_service.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook не найден")
    return await webhook_service.send_test(webhook)


# ── Deliveries ─────────────────────────────────────────────────────────────


@router.get(
    "/{webhook_id}/deliveries",
    response_model=PaginatedWebhookDeliveries,
)
async def list_webhook_deliveries(
    webhook_id: UUID,
    limit:  int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0,  ge=0),
    success: bool | None = Query(
        default=None,
        description="Filter by success flag",
    ),
    db: AsyncSession = Depends(get_db),
):
    webhook = await webhook_service.get_webhook_by_id(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook не найден")
    items, total = await webhook_service.list_deliveries(
        db, webhook_id, limit=limit, offset=offset, success=success,
    )
    return PaginatedWebhookDeliveries(
        items=[_delivery_response(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )