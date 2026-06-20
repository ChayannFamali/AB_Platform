"""
Audit log service (M-004).

Provides:
- `log_action(db, *, actor, action, resource_type, resource_id, details, request)`
  — append a row. Called manually from mutation endpoints after the change
  is flushed (so resource_id is available).
- `list_audit_entries(db, *, limit, offset, resource_type, user_id, action)`
  — paginated, filterable read for the admin UI.

The audit log is append-only — there is no `update` or `delete` endpoint
on purpose. A separate retention/cleanup job (future work) can prune old
rows.
"""
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import AuditLog, User


# ── Public API ──────────────────────────────────────────────────────────────

async def log_action(
    db: AsyncSession,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: UUID | str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """
    Append an audit log row. Caller is responsible for committing the
    surrounding transaction (we just `add()` and `flush()` so the row is
    inserted before the endpoint returns, then commit happens via
    `get_db` dependency teardown).
    """
    ip_address, user_agent = _extract_request_meta(request)

    entry = AuditLog(
        user_id       = actor.id if actor else None,
        action        = action,
        resource_type = resource_type,
        resource_id   = resource_id,
        details       = details,
        ip_address    = ip_address,
        user_agent    = user_agent,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_audit_entries(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    resource_type: str | None = None,
    user_id: UUID | None = None,
    action: str | None = None,
) -> tuple[list[AuditLog], int]:
    """
    Return (items, total) for the audit log, with optional filters.

    Eager-loads `entry.user` so the response can include `user_username`
    without N+1 queries.
    """
    base = select(AuditLog).options(selectinload(AuditLog.user))

    conditions = []
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)

    items_stmt = base
    count_stmt = select(func.count(AuditLog.id))
    if conditions:
        items_stmt = items_stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    items_stmt = (
        items_stmt
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(items_stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_request_meta(request: Request | None) -> tuple[str | None, str | None]:
    """Pull IP (X-Forwarded-For aware) and User-Agent from a FastAPI Request."""
    if request is None:
        return None, None
    # X-Forwarded-For is comma-separated; first entry is the original client.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua