"""P1: delta method fields, decomposition, results_daily

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-27

Изменения:
    metrics:       + denominator_event_name (ratio метрики)
    results:       + numerator_mean, denominator_mean,
                     numerator_relative_lift, denominator_relative_lift
    results_daily: новая таблица для cumulative dynamics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Ratio поле в metrics ───────────────────────────────────────────────
    op.add_column(
        "metrics",
        sa.Column("denominator_event_name", sa.String(255), nullable=True),
    )

    # ── 2. Декомпозиция в results ─────────────────────────────────────────────
    op.add_column("results", sa.Column("numerator_mean",            sa.Float(), nullable=True))
    op.add_column("results", sa.Column("denominator_mean",          sa.Float(), nullable=True))
    op.add_column("results", sa.Column("numerator_relative_lift",   sa.Float(), nullable=True))
    op.add_column("results", sa.Column("denominator_relative_lift", sa.Float(), nullable=True))

    # ── 3. Таблица results_daily ──────────────────────────────────────────────
    op.create_table(
        "results_daily",
        sa.Column("id",            postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id",     postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(),    nullable=False),
        sa.Column("sample_size",   sa.Integer(), nullable=False),
        sa.Column("mean",          sa.Float(),   nullable=False),
        sa.Column("p_value",       sa.Float(),   nullable=True),
        sa.Column("effect_size",   sa.Float(),   nullable=True),
        sa.Column("relative_lift", sa.Float(),   nullable=True),
        sa.Column("ci_low",        sa.Float(),   nullable=True),
        sa.Column("ci_high",       sa.Float(),   nullable=True),
        sa.Column("is_significant", sa.Boolean(), nullable=True),
        sa.Column("test_used",     sa.String(50), nullable=True),
        sa.Column("created_at",    sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["variant_id"],    ["variants.id"]),
        sa.ForeignKeyConstraint(["metric_id"],     ["metrics.id"]),
        sa.UniqueConstraint(
            "experiment_id", "variant_id", "metric_id", "snapshot_date",
            name="uq_result_daily_exp_variant_metric_date",
        ),
    )
    op.create_index(
        "ix_results_daily_exp_date",
        "results_daily",
        ["experiment_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_results_daily_exp_date", table_name="results_daily")
    op.drop_table("results_daily")

    op.drop_column("results", "denominator_relative_lift")
    op.drop_column("results", "numerator_relative_lift")
    op.drop_column("results", "denominator_mean")
    op.drop_column("results", "numerator_mean")

    op.drop_column("metrics", "denominator_event_name")
