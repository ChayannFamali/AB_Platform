"""Webhooks (M-013)

Adds the `webhooks` and `webhook_deliveries` tables.

  - `webhooks`             — per-tenant webhook configuration (URL,
                              subscribed event list, optional HMAC
                              secret, payload format: slack/discord/
                              generic, is_active flag).
  - `webhook_deliveries`   — append-only audit trail of every
                              delivery attempt: HTTP status, response
                              body, attempt number, success flag,
                              duration in ms.

Revision ID: 0017_webhooks
Revises: 0016_decisions
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0017_webhooks"
down_revision = "0016_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. webhooks — top-level config
    op.create_table(
        "webhooks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name",      sa.String(length=255), nullable=False),
        sa.Column("url",       sa.Text(),              nullable=False),
        # JSONB list of event types the webhook subscribes to
        # (e.g. ["winner_detected", "srm_alert"]).
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Optional HMAC-SHA256 secret. NULL → no signature header.
        # Never returned in GET responses (see `schemas.webhook.WebhookResponse`).
        sa.Column("secret", sa.String(length=255), nullable=True),
        # Payload format: "generic" (raw JSON), "slack", "discord".
        sa.Column(
            "format",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'generic'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_webhooks_is_active", "webhooks", ["is_active"],
    )

    # 2. webhook_deliveries — append-only audit trail of every delivery
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "webhook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status_code",   sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(),     nullable=True),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_webhook_id",
        "webhook_deliveries", ["webhook_id"],
    )
    op.create_index(
        "ix_webhook_deliveries_created_at",
        "webhook_deliveries", ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_created_at",
        table_name="webhook_deliveries",
    )
    op.drop_index(
        "ix_webhook_deliveries_webhook_id",
        table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhooks_is_active", table_name="webhooks")
    op.drop_table("webhooks")