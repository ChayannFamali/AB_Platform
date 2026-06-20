"""API key scopes (M-003, ADR-006)

Adds a JSONB `scopes` column to api_keys with a server-side default that grants
existing keys full SDK access (`assignments:read` + `events:write`). This keeps
all pre-existing keys working unchanged with the SDK v0.1.0 contract.

Revision ID: 0014_api_key_scopes
Revises: 0006_rbac
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_api_key_scopes"
down_revision = "0006_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                "'[\"assignments:read\", \"events:write\"]'::jsonb"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "scopes")