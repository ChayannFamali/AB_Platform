"""Feature flags (M-009, ADR-004).

Adds:
  - `feature_flags` — top-level flag config (key, kill switch, rollout %)
  - `flag_rules`    — per-flag overrides. `segment_id` is a nullable UUID
                      without an FK — M-010 (Segments + Holdouts) will add
                      the FK and segment-matching logic. Until then, rules
                      with a NULL `segment_id` act as "default for everyone"
                      overrides (first by priority wins).

Design notes:
- `feature_flags.key` is the stable identifier used by the SDK
  (`client.get_flag(user_id, "my_flag")`). Unique, indexed.
- `rollout_percentage` is 0..100 inclusive; values outside that range are
  rejected at the schema layer (see `flag.py` schemas).
- Rules inherit CASCADE delete from their parent flag — deleting a flag
  removes all of its rules in one transaction.
- No `variants` column — M-009 is boolean-only per design decision.
  Multi-variant flags can be added later without breaking this schema.

Revision ID: 0009_feature_flags
Revises: 0008_sequential_results
Create Date: 2026-06-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0009_feature_flags"
down_revision = "0008_sequential_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "rollout_percentage",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
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
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("key", name="uq_feature_flags_key"),
    )
    op.create_index(
        "ix_feature_flags_key",
        "feature_flags",
        ["key"],
        unique=True,
    )

    op.create_table(
        "flag_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "flag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_flags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable UUID WITHOUT FK — M-010 (Segments) will add the FK
        # to the new `segments` table. Until then this column is just
        # metadata stored alongside each rule.
        sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rollout_percentage", sa.Float(), nullable=False),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_flag_rules_flag_priority",
        "flag_rules",
        ["flag_id", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_flag_rules_flag_priority", table_name="flag_rules")
    op.drop_table("flag_rules")
    op.drop_index("ix_feature_flags_key", table_name="feature_flags")
    op.drop_table("feature_flags")