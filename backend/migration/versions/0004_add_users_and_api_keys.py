"""Add users and api_keys tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",              postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username",        sa.String(100),  nullable=False),
        sa.Column("email",           sa.String(255),  nullable=False),
        sa.Column("hashed_password", sa.String(255),  nullable=False),
        sa.Column("is_active",       sa.Boolean(),    nullable=False, server_default=sa.text("true")),
        sa.Column("is_admin",        sa.Boolean(),    nullable=False, server_default=sa.text("false")),
        sa.Column("created_at",      sa.DateTime(),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email",    name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "api_keys",
        sa.Column("id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id",      postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("key",          sa.String(100), nullable=False),
        sa.Column("is_active",    sa.Boolean(),   nullable=False, server_default=sa.text("true")),
        sa.Column("created_at",   sa.DateTime(),  nullable=False),
        sa.Column("last_used_at", sa.DateTime(),  nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_api_keys_key"),
    )
    op.create_index("ix_api_keys_key",  "api_keys", ["key"])
    op.create_index("ix_api_keys_user", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_user", table_name="api_keys")
    op.drop_index("ix_api_keys_key",  table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
