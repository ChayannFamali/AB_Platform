from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AssignmentRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    experiment_id: UUID
    anonymous_id: str | None = None
    # M-010: optional user properties used for segment-targeting evaluation.
    # Backward-compatible: clients that don't send it get the pre-M-010
    # behavior (segment rules are skipped because there's nothing to match).
    user_properties: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form properties about the calling user (country, device_type, "
            "plan, etc.) used by segment targeting. Backward-compatible — "
            "absent or empty means the user matches no segment."
        ),
    )


class AssignmentResponse(BaseModel):
    assigned: bool
    variant: str | None = None
    experiment_id: str
