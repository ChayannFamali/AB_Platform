"""Sequential testing (mSPRT) results — M-007.

Adds:
  - `experiments.is_sequential`     — opt-in flag for always-valid p-values
  - `results.sequential_fpr`        — always-valid p-value at current sample
  - `results.sequential_boundary_crossed` — whether the mSPRT boundary is crossed
  - `results_daily.sequential_fpr`   — historical always-valid p-value for the
    SequentialPValueChart on the experiment detail page

Non-sequential experiments get NULL on the new `*_sequential_*` columns
(their fixed-horizon p-value is stored in the existing `p_value` column).

Revision ID: 0008_sequential_results
Revises: 0007_audit_log
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op


revision = "0008_sequential_results"
down_revision = "0007_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # experiments: opt-in flag for sequential testing
    op.add_column(
        "experiments",
        sa.Column(
            "is_sequential",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # results: always-valid p-value at current sample size
    op.add_column(
        "results",
        sa.Column("sequential_fpr", sa.Float(), nullable=True),
    )
    op.add_column(
        "results",
        sa.Column(
            "sequential_boundary_crossed",
            sa.Boolean(),
            nullable=True,
        ),
    )

    # results_daily: history of always-valid p-value for the chart
    op.add_column(
        "results_daily",
        sa.Column("sequential_fpr", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("results_daily", "sequential_fpr")
    op.drop_column("results", "sequential_boundary_crossed")
    op.drop_column("results", "sequential_fpr")
    op.drop_column("experiments", "is_sequential")