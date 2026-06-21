"""
Pydantic schemas for the guardrail system (M-011).

A `GuardrailConfig` attaches a configurable threshold + direction to a
specific per-experiment `Metric` row. The analysis engine checks the
metric's `relative_lift` against the threshold and fires a violation
when the cross-side condition is met (direction="below" + significant
negative lift > threshold_pct, or direction="above" + significant
positive lift > threshold_pct).

Severity:
  - "warning"  — emits a `guardrail_warning` insight (M-007 InsightPanel).
                 Does NOT block winner designation.
  - "critical" — sets `metric.guardrail_violated=True`. Blocks winner
                 designation across ALL primary metrics in the experiment
                 (see `app/services/stats/engine.py`).

A guardrail only fires when the variant's hypothesis test is
statistically significant (avoids noise triggers on tiny experiments).
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.db import GuardrailDirection, GuardrailSeverity


class GuardrailCreate(BaseModel):
    metric_id:     UUID
    direction:     GuardrailDirection
    threshold_pct: float = Field(
        ...,
        gt=0,
        le=100,
        description=(
            "Positive percentage. direction='below' fires when "
            "relative_lift < -threshold_pct. direction='above' fires "
            "when relative_lift > +threshold_pct."
        ),
    )
    severity:      GuardrailSeverity = GuardrailSeverity.WARNING
    is_enabled:    bool = True


class GuardrailUpdate(BaseModel):
    """Partial update — every field is optional."""
    threshold_pct: float | None = Field(default=None, gt=0, le=100)
    severity:      GuardrailSeverity | None = None
    is_enabled:    bool | None = None


class GuardrailResponse(BaseModel):
    id:             UUID
    experiment_id:  UUID
    metric_id:      UUID
    direction:      GuardrailDirection
    threshold_pct:  float
    severity:       GuardrailSeverity
    is_enabled:     bool
    created_by:     UUID | None
    created_at:     datetime
    updated_at:     datetime

    model_config = {"from_attributes": True}


class GuardrailListItem(BaseModel):
    """Lightweight payload — same fields, no future-proofing extras."""
    id:             UUID
    experiment_id:  UUID
    metric_id:      UUID
    direction:      GuardrailDirection
    threshold_pct:  float
    severity:       GuardrailSeverity
    is_enabled:     bool

    model_config = {"from_attributes": True}


class PaginatedGuardrails(BaseModel):
    items:    list[GuardrailListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Evaluation output (used by the engine) ────────────────────────────────


class GuardrailCheck(BaseModel):
    """Per-variant, per-config result of a guardrail check."""
    guardrail_id:   UUID
    metric_id:      UUID
    variant_id:     UUID
    direction:      GuardrailDirection
    threshold_pct:  float
    severity:       GuardrailSeverity
    is_violated:    bool
    relative_lift:  float | None
    is_significant: bool | None
    reason:         str

    @model_validator(mode="after")
    def _check_consistency(self) -> "GuardrailCheck":
        if self.is_violated and not self.is_significant:
            # Should never happen — engine guards this. Safety net.
            raise ValueError("Violation requires statistical significance.")
        return self
