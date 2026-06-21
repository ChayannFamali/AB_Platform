"""
Pydantic schemas for holdout groups (M-010).

Holdout groups are long-term measurement baselines: a deterministic
fraction of users (e.g. 10%) are excluded from all experiments linked
to the holdout, so analysts can compare outcomes against a never-exposed
cohort.

Manual `HoldoutExclusion` rows let admins opt specific users OUT of the
holdout — VIPs, internal staff, canary accounts — even when they would
otherwise fall into the bucketed cohort.

Bucket math (see `holdout_service.get_holdout_bucket`):
    bucket = sha256(f"holdout:{group_key}:{user_id}")[:4] % 100
    is_in_holdout = bucket < group.size_pct

The `holdout:` namespace is distinct from `flag:` and `traffic:` so
holdout membership is statistically independent of flag rollouts and
experiment traffic allocation.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── HoldoutGroup schemas ───────────────────────────────────────────────────


class HoldoutGroupCreate(BaseModel):
    key: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    size_pct: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description=(
            "Share of the user population excluded from linked experiments "
            "(0..100 inclusive). Bucket is deterministic per (user_id, group_key)."
        ),
    )
    is_active: bool = True


class HoldoutGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    size_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    is_active: bool | None = None


class HoldoutGroupResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    size_pct: float
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    exclusions_count: int = 0
    experiments_count: int = 0

    model_config = {"from_attributes": True}


class HoldoutGroupListItem(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    size_pct: float
    is_active: bool
    exclusions_count: int = 0
    experiments_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedHoldouts(BaseModel):
    items:    list[HoldoutGroupListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Exclusion schemas ──────────────────────────────────────────────────────


class HoldoutExclusionCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=500)


class HoldoutExclusionResponse(BaseModel):
    holdout_group_id: UUID
    user_id:          str
    reason:           str | None
    excluded_by:      UUID | None
    excluded_at:      datetime

    model_config = {"from_attributes": True}


class PaginatedExclusions(BaseModel):
    items:    list[HoldoutExclusionResponse]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool
