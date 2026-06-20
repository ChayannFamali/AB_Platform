"""
Audit log router (M-004).

GET /api/v1/audit — paginated, filterable audit log.

Requires the `audit:read` permission (admin / editor / analyst per
ADR-006 matrix). The audit log is read-only — there is intentionally
no POST / PATCH / DELETE endpoint.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import User
from app.schemas.audit import AuditLogEntry, PaginatedAudit
from app.services import audit_service, rbac_service

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["audit"],
    dependencies=[Depends(rbac_service.require_permission("audit:read"))],
)


@router.get("", response_model=PaginatedAudit)
async def list_audit(
    limit:  int = Query(default=20, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0,  ge=0,        description="Pagination offset"),
    resource_type: str | None = Query(default=None, description="Filter by resource type"),
    user_id:       UUID | None = Query(default=None, description="Filter by actor user id"),
    action:        str | None = Query(default=None, description="Filter by action verb"),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_service.list_audit_entries(
        db,
        limit=limit,
        offset=offset,
        resource_type=resource_type,
        user_id=user_id,
        action=action,
    )
    return PaginatedAudit(
        items=[_entry_response(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


def _entry_response(entry) -> AuditLogEntry:
    return AuditLogEntry(
        id            = entry.id,
        user_id       = entry.user_id,
        user_username = entry.user.username if entry.user else None,
        action        = entry.action,
        resource_type = entry.resource_type,
        resource_id   = entry.resource_id,
        details       = entry.details,
        ip_address    = entry.ip_address,
        user_agent    = entry.user_agent,
        created_at    = entry.created_at,
    )