"""Segments (M-010, ADR-004).

Adds the targeting subsystem used by feature flags and experiments:

  - `segments`           — named, reusable user-property definitions.
  - `segment_rules`      — AND-combined matchers inside a segment
                           (9 operators: eq/neq/in/not_in/gt/lt/gte/lte/contains).
  - `experiment_segments`— M2M link from experiments to segments
                           (experiments only assign users in linked segments).

Also retrofits `flag_rules.segment_id` with an FK to the new `segments`
table. M-009 created the column as a bare nullable UUID with no FK; this
migration completes the contract so M-010's flag evaluation can rely on
referential integrity. Existing rows have segment_id=NULL (M-009 default),
so the constraint adds with no validation work.

No backfill is needed: every `flag_rules.segment_id` left behind by M-009
is NULL, which trivially satisfies the new FK constraint.

Revision ID: 0010_segments
Revises: 0009_feature_flags
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0010_segments"
down_revision = "0009_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the new segments-related tables.
    op.create_table(
        "segments",
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
        sa.UniqueConstraint("key", name="uq_segments_key"),
    )
    op.create_index("ix_segments_key", "segments", ["key"], unique=True)

    op.create_table(
        "segment_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        "ix_segment_rules_segment_priority",
        "segment_rules",
        ["segment_id", "priority"],
    )

    op.create_table(
        "experiment_segments",
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "added_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_experiment_segments_segment_id",
        "experiment_segments",
        ["segment_id"],
    )

    # 2. Retrofit flag_rules.segment_id with an FK to the new table.
    # Existing rows from M-009 all have segment_id=NULL (default), which
    # trivially satisfies the constraint — no data migration needed.
    op.create_foreign_key(
        "fk_flag_rules_segment_id",
        "flag_rules",
        "segments",
        ["segment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop FK first so the table can stand on its own.
    op.drop_constraint("fk_flag_rules_segment_id", "flag_rules", type_="foreignkey")
    op.drop_index("ix_experiment_segments_segment_id", table_name="experiment_segments")
    op.drop_table("experiment_segments")
    op.drop_index("ix_segment_rules_segment_priority", table_name="segment_rules")
    op.drop_table("segment_rules")
    op.drop_index("ix_segments_key", table_name="segments")
    op.drop_table("segments")
