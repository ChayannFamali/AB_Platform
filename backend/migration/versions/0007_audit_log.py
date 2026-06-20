"""Audit log (M-004)

Creates the `audit_log` table that records administrative mutations.
In M-004 the hooks cover role/user changes; later tasks add hooks on
experiment, flag, segment, etc. mutations.

Revision ID: 0007_audit_log
Revises: 0014_api_key_scopes
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_audit_log"
down_revision = "0014_api_key_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action",        sa.String(50),  nullable=False),
        sa.Column("resource_type", sa.String(50),  nullable=False),
        sa.Column("resource_id",   postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details",       postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address",    sa.String(64), nullable=True),
        sa.Column("user_agent",    sa.Text(),     nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_created_at",    "audit_log", ["created_at"])
    op.create_index("ix_audit_log_user_id",       "audit_log", ["user_id"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])
    op.create_index("ix_audit_log_action",        "audit_log", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_action",        table_name="audit_log")
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id",       table_name="audit_log")
    op.drop_index("ix_audit_log_created_at",    table_name="audit_log")
    op.drop_table("audit_log")