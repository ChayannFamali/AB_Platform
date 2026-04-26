"""Add stats fields to results table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "a265706a403c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("relative_lift",     sa.Float(),       nullable=True))
    op.add_column("results", sa.Column("is_normal",         sa.Boolean(),     nullable=True))
    op.add_column("results", sa.Column("normality_p_value", sa.Float(),       nullable=True))
    op.add_column("results", sa.Column("test_used",         sa.String(50),    nullable=True))
    op.add_column("results", sa.Column("achieved_mde",      sa.Float(),       nullable=True))


def downgrade() -> None:
    op.drop_column("results", "achieved_mde")
    op.drop_column("results", "test_used")
    op.drop_column("results", "normality_p_value")
    op.drop_column("results", "is_normal")
    op.drop_column("results", "relative_lift")
