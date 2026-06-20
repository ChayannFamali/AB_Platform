"""
Pydantic schemas for the audit log (M-004).

Wire-format shapes for GET /api/v1/audit.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """
    One audit row. `details` carries action-specific context
    (e.g. role_key, is_active) — opaque to the schema.
    """
    id:            UUID
    user_id:       UUID | None
    user_username: str | None = None
    action:        str
    resource_type: str
    resource_id:   UUID | None
    details:       dict[str, Any] | None = None
    ip_address:    str | None
    user_agent:    str | None
    created_at:    datetime

    model_config = {"from_attributes": True}


class PaginatedAudit(BaseModel):
    items:    list[AuditLogEntry]
    total:    int
    limit:    int
    offset:   int
    has_next: bool
    has_prev: bool