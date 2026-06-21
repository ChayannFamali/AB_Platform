"""Decision Log (M-012)

Append-only decision history per experiment.

Creates the `decisions` table and adds `decision_status` to
`experiments` (the latest decision's status, denormalised for fast
read on the experiment list / detail page).

Revision ID: 0016_decisions
Revises: 0015_custom_metrics_guardrails
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0016_decisions"
down_revision = "0015_custom_metrics_guardrails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. decisions — append-only history of ship/stop/iterate/inconclusive
    #    decisions per experiment. `status` is VARCHAR(20) rather than a
    #    PG ENUM because the four values are unlikely to change and
    #    VARCHAR keeps the downgrade symmetric (no enum type to drop).
    op.create_table(
        "decisions",
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
        # ship / stop / iterate / inconclusive — validated at the Pydantic
        # layer (`schemas.decision.DecisionCreate`).
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_decisions_experiment_id",
        "decisions",
        ["experiment_id"],
    )
    op.create_index(
        "ix_decisions_decided_at",
        "decisions",
        ["decided_at"],
    )

    # 2. experiments.decision_status — denormalised mirror of the latest
    #    decision's status. NULL means "no decision yet". Updated by the
    #    service layer whenever a new decision is appended. Keeping it
    #    on the experiment avoids a JOIN on every experiment-list /
    #    detail read.
    op.add_column(
        "experiments",
        sa.Column("decision_status", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiments", "decision_status")
    op.drop_index("ix_decisions_decided_at",    table_name="decisions")
    op.drop_index("ix_decisions_experiment_id", table_name="decisions")
    op.drop_table("decisions")