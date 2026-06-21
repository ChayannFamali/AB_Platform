"""Custom Metrics + Guardrails (M-011)

Adds the reusable metric template and per-experiment guardrail threshold
subsystems:

  - `custom_metrics`    — global, reusable metric definitions
                          (event_name, aggregation, filters, denominator).
                          Snapshotted into `metrics` at experiment creation.
  - `guardrail_configs` — per-experiment threshold + direction + severity
                          attached to a specific `metrics` row.

Also retrofits the existing `metrics` table with three nullable columns:
  - `aggregation`       — explicit aggregation enum (was inferred from
                          `metric_type` by the engine before M-011).
  - `filters`           — JSONB list of {field, operator, value} AND-rules
                          applied to `events.properties` at read time.
  - `custom_metric_id`  — back-reference to the source custom metric.
                          ON DELETE SET NULL — deleting the template
                          does not invalidate the experiment.

All new columns on `metrics` are nullable so existing rows from earlier
milestones remain valid; the engine infers `aggregation` from
`metric_type` when NULL.

Revision ID: 0015_custom_metrics_guardrails
Revises: 0014_api_key_scopes
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0015_custom_metrics_guardrails"
# Two-branch merge node: M-013 added 0014_api_key_scopes as a sibling
# branch off 0006_rbac, while the line 0006 → 0014 → 0007 → 0008 → 0009 →
# 0010 → 0011_holdouts carries all earlier feature work. Both heads need
# to be applied before this migration; alembic walks the DAG in order.
down_revision = ("0011_holdouts", "0014_api_key_scopes")
branch_labels = None
depends_on = None


# Reused enum names so the SAEnum() declarations on the ORM model bind
# cleanly. PostgreSQL will create the enum types as needed.
_METRIC_AGGREGATION = "metricaggregation"
_GUARDRAIL_DIRECTION = "guardraildirection"
_GUARDRAIL_SEVERITY = "guardrailseverity"


def upgrade() -> None:
    # 1. Custom metrics — global templates.
    op.create_table(
        "custom_metrics",
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
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column(
            "aggregation",
            postgresql.ENUM(
                "count", "sum", "avg", "unique_count",
                name=_METRIC_AGGREGATION,
                create_type=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "metric_type",
            postgresql.ENUM(
                "conversion", "revenue", "duration",
                name="metrictype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("denominator_event_name", sa.String(length=255), nullable=True),
        sa.Column(
            "denominator_aggregation",
            postgresql.ENUM(
                "count", "sum", "avg", "unique_count",
                name=_METRIC_AGGREGATION,
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("denominator_filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "is_guardrail",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.UniqueConstraint("key", name="uq_custom_metrics_key"),
    )
    op.create_index("ix_custom_metrics_key", "custom_metrics", ["key"], unique=True)

    # 2. Retrofit `metrics` with nullable M-011 columns.
    op.add_column(
        "metrics",
        sa.Column(
            "aggregation",
            postgresql.ENUM(
                "count", "sum", "avg", "unique_count",
                name=_METRIC_AGGREGATION,
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "metrics",
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "metrics",
        sa.Column(
            "custom_metric_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_metrics_custom_metric_id",
        "metrics",
        "custom_metrics",
        ["custom_metric_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_metrics_custom_metric_id",
        "metrics",
        ["custom_metric_id"],
    )

    # 3. Guardrail configs — per-experiment thresholds.
    op.create_table(
        "guardrail_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metrics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "direction",
            postgresql.ENUM(
                "below", "above",
                name=_GUARDRAIL_DIRECTION,
                create_type=True,
            ),
            nullable=False,
        ),
        sa.Column("threshold_pct", sa.Float(), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "warning", "critical",
                name=_GUARDRAIL_SEVERITY,
                create_type=True,
            ),
            nullable=False,
            server_default=sa.text("'warning'"),
        ),
        sa.Column(
            "is_enabled",
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
        sa.UniqueConstraint(
            "experiment_id", "metric_id", "direction", "severity",
            name="uq_guardrail_exp_metric_dir_severity",
        ),
    )
    op.create_index(
        "ix_guardrail_configs_experiment",
        "guardrail_configs",
        ["experiment_id"],
    )
    op.create_index(
        "ix_guardrail_configs_metric",
        "guardrail_configs",
        ["metric_id"],
    )


def downgrade() -> None:
    # Reverse order: guardrails → metrics retrofit → custom_metrics.
    op.drop_index("ix_guardrail_configs_metric", table_name="guardrail_configs")
    op.drop_index("ix_guardrail_configs_experiment", table_name="guardrail_configs")
    op.drop_table("guardrail_configs")
    op.drop_index("ix_metrics_custom_metric_id", table_name="metrics")
    op.drop_constraint("fk_metrics_custom_metric_id", "metrics", type_="foreignkey")
    op.drop_column("metrics", "custom_metric_id")
    op.drop_column("metrics", "filters")
    op.drop_column("metrics", "aggregation")
    op.drop_index("ix_custom_metrics_key", table_name="custom_metrics")
    op.drop_table("custom_metrics")

    # Drop enum types we created so a downgrade → upgrade cycle is clean.
    # IF EXISTS makes the downgrade safe to re-run after a partial failure.
    op.execute("DROP TYPE IF EXISTS metricaggregation")
    op.execute("DROP TYPE IF EXISTS guardraildirection")
    op.execute("DROP TYPE IF EXISTS guardrailseverity")
