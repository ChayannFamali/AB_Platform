"""
Pydantic schemas for the decision log (M-012).

Wire-format shapes for:

  POST /api/v1/experiments/{experiment_id}/decisions
  GET  /api/v1/experiments/{experiment_id}/decisions
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# The four decision verbs. `Literal` gives us a 422 from FastAPI when a
# caller sends anything else — no separate validator needed.
DecisionStatus = Literal["ship", "stop", "iterate", "inconclusive"]


class DecisionCreate(BaseModel):
    """Body for POST /experiments/{id}/decisions."""
    status:  DecisionStatus = Field(
        ...,
        description=(
            "Decision verb: 'ship', 'stop', 'iterate', or 'inconclusive'."
        ),
    )
    comment: str | None = Field(
        default=None,
        max_length=10_000,
        description="Optional free-form rationale / context.",
    )


class DecisionResponse(BaseModel):
    """
    One decision entry. Includes `decided_by_username` (denormalised
    from `users.username`) so the frontend can render the actor
    without a second request.
    """
    id:                  UUID
    experiment_id:       UUID
    status:              DecisionStatus
    comment:             str | None
    decided_by:          UUID | None
    decided_by_username: str | None = None
    decided_at:          datetime

    model_config = {"from_attributes": True}


class PaginatedDecisions(BaseModel):
    items:    list[DecisionResponse]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool