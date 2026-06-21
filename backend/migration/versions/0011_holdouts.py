"""Holdout groups (M-010).

Adds long-term measurement holdout cohorts:

  - `holdout_groups`       — named buckets of users excluded from linked
                             experiments (e.g. 10% baseline that never
                             sees any variant).
  - `holdout_exclusions`   — manual per-user opt-out: a user who would
                             otherwise fall into the bucketed cohort can
                             be explicitly excluded (VIPs, internal staff).

Also ALTERs `experiments` with a nullable `holdout_group_id` FK pointing
to `holdout_groups.id` (ON DELETE SET NULL). Experiments linked to a
holdout will skip users who are inside that holdout bucket (see
`assignment_service` and `flag_service._resolve_rollout`).

Why holdout affects flag rollouts too:
  Per the M-010 design decision (holdout → default), users in a holdout
  cohort are considered "untouched" — flag rollouts evaluate to false
  for them, so the cohort stays clean for measurement purposes. The
  flag-service check reuses `holdout_service.is_in_holdout` to honor
  manual exclusions as well.

No data backfill needed: existing experiments simply have
`holdout_group_id = NULL` and continue working as before.

Revision ID: 0011_holdouts
Revises: 0010_segments
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0011_holdouts"
down_revision = "0010_segments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holdout_groups",
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
            "size_pct",
            sa.Float(),
            nullable=False,
            server_default=sa.text("10"),
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
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("key", name="uq_holdout_groups_key"),
    )
    op.create_index(
        "ix_holdout_groups_key",
        "holdout_groups",
        ["key"],
        unique=True,
    )

    op.create_table(
        "holdout_exclusions",
        sa.Column(
            "holdout_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("holdout_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(length=255), primary_key=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "excluded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "excluded_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_holdout_exclusions_user_id",
        "holdout_exclusions",
        ["user_id"],
    )

    # ALTER experiments with the holdout_group_id FK.
    op.add_column(
        "experiments",
        sa.Column(
            "holdout_group_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_experiments_holdout_group_id",
        "experiments",
        "holdout_groups",
        ["holdout_group_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_experiments_holdout_group_id",
        "experiments",
        type_="foreignkey",
    )
    op.drop_column("experiments", "holdout_group_id")
    op.drop_index("ix_holdout_exclusions_user_id", table_name="holdout_exclusions")
    op.drop_table("holdout_exclusions")
    op.drop_index("ix_holdout_groups_key", table_name="holdout_groups")
    op.drop_table("holdout_groups")
