"""
Pydantic schemas for the segments system (M-010).

Segments are reusable targeting definitions: a named, ordered set of
matchers applied to a user's `properties` dict (sent by the SDK at
evaluate time). Rules inside a segment are AND-combined — a user matches
the segment only when every enabled rule matches.

Operators
---------
The 9 supported operators are validated server-side via the
`SEGMENT_OPERATORS` constant in `segment_service.py`. Values are typed
as `Any` here because the wire format is heterogeneous:

  - eq / neq  — scalar comparison (string/number/bool).
  - in / not_in — list membership (`value` is a JSONB array on the row).
  - gt / lt / gte / lte — numeric comparison. The matcher coerces both
    sides to float when possible; otherwise the rule does not match.
  - contains — substring match against a string field. Numbers and booleans
    are coerced via `str()`.

A rule that references a missing `field` in the user properties does
NOT match (returns False). This is intentional — segments should be
explicit about who is included, not silently include everyone.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── SegmentRule schemas ────────────────────────────────────────────────────


class SegmentRuleCreate(BaseModel):
    field:    str  = Field(..., min_length=1, max_length=100)
    operator: str  = Field(..., min_length=1, max_length=20)
    value:    Any
    priority: int  = 0
    enabled:  bool = True


class SegmentRuleResponse(BaseModel):
    id:         UUID
    segment_id: UUID
    field:      str
    operator:   str
    value:      Any
    priority:   int
    enabled:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Segment schemas ────────────────────────────────────────────────────────


class SegmentCreate(BaseModel):
    key: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Stable identifier (lowercase, digits, hyphens, underscores).",
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    rules: list[SegmentRuleCreate] = Field(default_factory=list)


class SegmentUpdate(BaseModel):
    """Partial update — every field is optional. Pass `rules` to replace."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    rules: list[SegmentRuleCreate] | None = None


class SegmentResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    rules: list[SegmentRuleResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SegmentListItem(BaseModel):
    """Lightweight payload for the list view — no rules."""
    id: UUID
    key: str
    name: str
    description: str | None
    rules_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSegments(BaseModel):
    items:    list[SegmentListItem]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool


# ── Evaluation schemas ─────────────────────────────────────────────────────


class SegmentEvaluateRequest(BaseModel):
    """Dry-run a segment against a hypothetical user properties payload."""
    user_properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Same dict the SDK would send with a flag evaluation.",
    )


class SegmentEvaluateResponse(BaseModel):
    matches:         bool
    matched_rules:   int = Field(description="How many rules matched (out of total enabled).")
    total_rules:     int
    per_rule:        list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Per-rule breakdown: [{rule_id, field, operator, matched, reason}, ...]."
            "Useful for debugging why a segment does or doesn't match."
        ),
    )


# ── Experiment linking schemas ─────────────────────────────────────────────


class SegmentExperimentLink(BaseModel):
    """Returned when an experiment is linked or unlinked to a segment."""
    experiment_id: UUID
    segment_id:    UUID


class SegmentLinkRequest(BaseModel):
    """Attach a segment to one or more experiments (bulk)."""
    experiment_ids: list[UUID] = Field(..., min_length=1, max_length=100)

    @field_validator("experiment_ids")
    @classmethod
    def _dedupe(cls, v: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        out: list[UUID] = []
        for x in v:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
