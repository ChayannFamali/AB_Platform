"""
Pydantic schemas for webhooks (M-013).

Wire-format shapes for:

  GET   /api/v1/webhooks
  POST  /api/v1/webhooks
  GET   /api/v1/webhooks/{id}
  PATCH /api/v1/webhooks/{id}
  POST  /api/v1/webhooks/{id}/test
  GET   /api/v1/webhooks/{id}/deliveries
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


# The four supported event types. Pydantic enforces this in the
# `events` list and on the per-event delivery path. Adding a new event
# type requires updating both this Literal AND the analysis_service
# publisher (and CHANGELOG.md).
WebhookEvent = Literal[
    "winner_detected",
    "srm_alert",
    "guardrail_violated",
    "sequential_boundary_crossed",
]

WebhookFormat = Literal["generic", "slack", "discord"]


# ── CRUD ────────────────────────────────────────────────────────────────────


class WebhookCreate(BaseModel):
    """Body for POST /webhooks."""
    name:   str          = Field(..., min_length=1, max_length=255)
    url:    HttpUrl      = Field(...)
    events: list[WebhookEvent] = Field(..., min_length=1)
    secret: str | None   = Field(default=None, max_length=255)
    format: WebhookFormat = "generic"
    is_active: bool      = True

    @field_validator("events")
    @classmethod
    def _events_unique(cls, v: list[str]) -> list[str]:
        # De-dupe to keep the JSONB clean; the analysis_service uses
        # an IN-clause so duplicates are harmless but bloat the column.
        seen: set[str] = set()
        out: list[str] = []
        for ev in v:
            if ev not in seen:
                seen.add(ev)
                out.append(ev)
        return out


class WebhookUpdate(BaseModel):
    """Body for PATCH /webhooks/{id}. All fields optional."""
    name:      str | None = Field(default=None, min_length=1, max_length=255)
    url:       HttpUrl | None = None
    events:    list[WebhookEvent] | None = None
    secret:    str | None = Field(default=None, max_length=255)
    format:    WebhookFormat | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    """
    One webhook row. `secret` is INTENTIONALLY OMITTED — it is only
    ever returned at create time and never echoed back in subsequent
    GETs. Set it to "***" in the response so the UI can render a
    masked placeholder.
    """
    id:        UUID
    name:      str
    url:       str
    events:    list[str]
    format:    WebhookFormat
    is_active: bool
    has_secret: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookListItem(BaseModel):
    """Compact webhook row for the list view (no events expansion)."""
    id:         UUID
    name:       str
    url:        str
    events:     list[str]
    format:     WebhookFormat
    is_active:  bool
    has_secret: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedWebhooks(BaseModel):
    items:    list[WebhookListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Deliveries ──────────────────────────────────────────────────────────────


class WebhookDeliveryResponse(BaseModel):
    """One row from the webhook delivery log."""
    id:            UUID
    webhook_id:    UUID
    event_type:    str
    status_code:   int | None
    response_body: str | None
    attempt:       int
    success:       bool
    duration_ms:   int | None
    created_at:    datetime

    model_config = {"from_attributes": True}


class PaginatedWebhookDeliveries(BaseModel):
    items:    list[WebhookDeliveryResponse]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Test send ───────────────────────────────────────────────────────────────


class WebhookTestResponse(BaseModel):
    """
    Result of POST /webhooks/{id}/test. The test endpoint sends a
    synchronous payload and waits for the response, returning the
    status code, response body (truncated), and duration.
    """
    status_code:   int
    response_body: str | None
    duration_ms:   int
    success:       bool


class WebhookWithSecretResponse(WebhookResponse):
    """
    WebhookCreate returns this one-time variant that INCLUDES the
    secret so the user can copy it. Subsequent reads use the regular
    WebhookResponse (without `secret`, with `has_secret`).
    """
    secret: str | None = None

    model_config = {"from_attributes": True}