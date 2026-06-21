"""
Pydantic schemas for the feature flag system (M-009, ADR-004).

The flag system is boolean-only for now: each flag has a kill switch
(`enabled`) and a rollout percentage (0..100). SDK clients call
`POST /flags/evaluate` with a `user_id` and receive a `{value: bool}`
response.

Rules are stored as overrides and evaluated when segments land in
M-010. Until then, rules with `segment_id=null` act as "default for
everyone" overrides (first by priority wins).
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── FlagRule schemas ────────────────────────────────────────────────────────


class FlagRuleCreate(BaseModel):
    """
    Create payload for a flag rule.

    `segment_id` is reserved for M-010 (Segments). Until that migration
    lands, callers should leave it null — flags with `segment_id=null`
    are treated as "applies to everyone", ordered by priority.
    """
    segment_id: UUID | None = None
    rollout_percentage: float = Field(..., ge=0.0, le=100.0)
    priority: int = 0
    enabled: bool = True


class FlagRuleResponse(BaseModel):
    id: UUID
    flag_id: UUID
    segment_id: UUID | None
    rollout_percentage: float
    priority: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── FeatureFlag schemas ────────────────────────────────────────────────────


class FeatureFlagCreate(BaseModel):
    key: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description=(
            "Stable identifier used by SDK clients "
            "(e.g. \"new_checkout_flow\"). Lowercase, "
            "letters / digits / hyphens / underscores."
        ),
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    rollout_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    rules: list[FlagRuleCreate] = Field(default_factory=list)


class FeatureFlagUpdate(BaseModel):
    """Partial update — every field is optional."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    rollout_percentage: float | None = Field(default=None, ge=0.0, le=100.0)


class FeatureFlagToggle(BaseModel):
    """Minimal payload for the quick enable/disable switch."""
    enabled: bool


class FeatureFlagResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    enabled: bool
    rollout_percentage: float
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    rules: list[FlagRuleResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FeatureFlagListItem(BaseModel):
    """Lightweight payload for the list view — no rules."""
    id: UUID
    key: str
    name: str
    description: str | None
    enabled: bool
    rollout_percentage: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedFlags(BaseModel):
    items: list[FeatureFlagListItem]
    total: int
    limit: int
    offset: int
    has_next: bool
    has_prev: bool
    summary: "FlagsSummary"


class FlagsSummary(BaseModel):
    """
    Aggregate counts for the dashboard "Active flags" card.

    `enabled_total` = flags with `enabled=True` (live regardless of rollout).
    `enabled_with_rollout` = enabled AND rollout_percentage > 0 (actually
    serving some traffic).
    """
    total: int
    enabled_total: int
    enabled_with_rollout: int
    disabled_total: int


# ── Evaluation schemas (SDK-facing) ────────────────────────────────────────


class FlagEvaluateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    flag_key: str = Field(..., min_length=3, max_length=100)
    # M-010: optional user properties used for segment-rule evaluation.
    # Backward-compatible — absent or empty means segment rules can't match.
    user_properties: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Free-form properties about the calling user (country, device_type, "
            "plan, etc.) used by segment-targeted flag rules. Absent or empty "
            "means the user matches no segment, so rules with a segment_id "
            "are skipped and only flag-level/default rules apply."
        ),
    )


class FlagEvaluateResponse(BaseModel):
    key: str
    value: bool
    reason: str = Field(
        ...,
        description=(
            "Why this value was returned: "
            "'kill_switch', 'rollout_in', 'rollout_out', 'segment_in', "
            "'segment_out', 'rule_override', 'flag_rollout', 'not_found'."
        ),
    )


class FlagEvaluateBatchRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    flag_keys: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Flag keys to evaluate for the given user (max 100).",
    )
    user_properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Same shape as FlagEvaluateRequest.user_properties.",
    )

    @field_validator("flag_keys")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        # Preserve order but drop duplicates — SDK may call the same key
        # multiple times in a session.
        seen: set[str] = set()
        out: list[str] = []
        for key in v:
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out


class FlagEvaluateBatchResponse(BaseModel):
    values: dict[str, bool]
    details: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Per-flag evaluation breakdown: {key: {value, reason}}."
        ),
    )


PaginatedFlags.model_rebuild()