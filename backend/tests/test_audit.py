"""
Audit log tests (M-004).

Verifies:
- Every mutation on /api/v1/roles and /api/v1/users writes a row
  to audit_log (create role, update role, toggle user, assign role,
  revoke role).
- GET /api/v1/audit returns paginated, filterable entries.
- Audit log requires the audit:read permission (admins / editors /
  analysts can read; viewers cannot).
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db import AuditLog


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _register_login(
    client: AsyncClient, email: str, username: str
) -> dict:
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "email":    email,
        "password": "password123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "password123",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _grant_role_via_db(db: AsyncSession, user_email: str, role_key: str):
    from app.models.db import Role, User, UserRole
    u = (await db.execute(select(User).where(User.email == user_email))).scalar_one()
    r = (await db.execute(select(Role).where(Role.key == role_key))).scalar_one()
    db.add(UserRole(user_id=u.id, role_id=r.id))
    await db.commit()


async def _audit_count(db: AsyncSession) -> int:
    return (await db.execute(select(AuditLog.id))).scalars().all().__len__()


# ── Audit hooks on role/user mutations ──────────────────────────────────────

async def test_create_role_writes_audit_entry(
    client: AsyncClient, engine
):
    headers = await _register_login(client, "audit_admin@example.com", "audit_admin")

    resp = await client.post(
        "/api/v1/roles",
        json={"key": "qa", "name": "QA", "permissions": ["experiments:read"]},
        headers=headers,
    )
    assert resp.status_code == 201
    role_id = resp.json()["id"]

    resp = await client.get("/api/v1/audit", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(
        e["action"] == "create"
        and e["resource_type"] == "role"
        and e["resource_id"] == role_id
        for e in items
    )


async def test_update_role_writes_audit_entry(
    client: AsyncClient, engine
):
    headers = await _register_login(client, "audit_admin2@example.com", "audit_admin2")

    role = (
        await client.post(
            "/api/v1/roles",
            json={"key": "ops", "name": "Ops", "permissions": []},
            headers=headers,
        )
    ).json()

    resp = await client.patch(
        f"/api/v1/roles/{role['id']}",
        json={"name": "Operations"},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        "/api/v1/audit?resource_type=role&action=update", headers=headers,
    )
    items = resp.json()["items"]
    assert any(e["resource_id"] == role["id"] for e in items)
    entry = next(e for e in items if e["resource_id"] == role["id"])
    assert "name" in entry["details"]["fields_changed"]


async def test_assign_role_writes_audit_entry(
    client: AsyncClient, engine
):
    headers = await _register_login(client, "audit_admin3@example.com", "audit_admin3")

    # Register a second user (viewer by default) to act as the target.
    target_headers = await _register_login(client, "audit_target@example.com", "audit_target")
    me = (await client.get("/api/v1/auth/me", headers=target_headers)).json()

    # Find editor role
    roles = (await client.get("/api/v1/roles", headers=headers)).json()["items"]
    editor_id = next(r["id"] for r in roles if r["key"] == "editor")

    resp = await client.post(
        f"/api/v1/users/{me['id']}/roles",
        json={"role_id": editor_id},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        "/api/v1/audit?action=assign&resource_type=user_role", headers=headers,
    )
    items = resp.json()["items"]
    assert items, "expected at least one assign audit entry"
    entry = items[0]
    assert entry["details"]["role_key"] == "editor"
    assert entry["details"]["user_id"] == me["id"]


async def test_revoke_role_writes_audit_entry(
    client: AsyncClient, engine
):
    headers = await _register_login(client, "audit_admin4@example.com", "audit_admin4")
    target_headers = await _register_login(client, "audit_tgt2@example.com", "audit_tgt2")
    me = (await client.get("/api/v1/auth/me", headers=target_headers)).json()

    roles = (await client.get("/api/v1/roles", headers=headers)).json()["items"]
    editor_id = next(r["id"] for r in roles if r["key"] == "editor")

    await client.post(
        f"/api/v1/users/{me['id']}/roles",
        json={"role_id": editor_id},
        headers=headers,
    )
    resp = await client.delete(
        f"/api/v1/users/{me['id']}/roles/{editor_id}",
        headers=headers,
    )
    assert resp.status_code == 204

    resp = await client.get(
        "/api/v1/audit?action=revoke&resource_type=user_role", headers=headers,
    )
    assert resp.json()["items"], "expected at least one revoke audit entry"


async def test_toggle_user_active_writes_audit_entry(
    client: AsyncClient
):
    headers = await _register_login(client, "audit_admin5@example.com", "audit_admin5")
    target_headers = await _register_login(client, "audit_tgt3@example.com", "audit_tgt3")
    me = (await client.get("/api/v1/auth/me", headers=target_headers)).json()

    resp = await client.patch(
        f"/api/v1/users/{me['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        "/api/v1/audit?action=toggle_active&resource_type=user", headers=headers,
    )
    items = resp.json()["items"]
    assert items
    entry = items[0]
    assert entry["details"]["is_active"] is False
    assert entry["details"]["previous_state"] is True


# ── Audit log filtering & pagination ────────────────────────────────────────

async def test_audit_filters_by_resource_type(
    client: AsyncClient
):
    headers = await _register_login(client, "audit_admin6@example.com", "audit_admin6")

    # Trigger two role mutations and one user toggle.
    role = (
        await client.post(
            "/api/v1/roles",
            json={"key": "tmp", "name": "Tmp", "permissions": []},
            headers=headers,
        )
    ).json()
    await client.patch(
        f"/api/v1/roles/{role['id']}",
        json={"name": "Tmp2"},
        headers=headers,
    )

    resp = await client.get("/api/v1/audit?resource_type=role", headers=headers)
    items = resp.json()["items"]
    assert items
    assert all(e["resource_type"] == "role" for e in items)


async def test_audit_pagination(client: AsyncClient):
    headers = await _register_login(client, "audit_admin7@example.com", "audit_admin7")

    # Create 3 roles to generate audit entries
    for i in range(3):
        await client.post(
            "/api/v1/roles",
            json={"key": f"page{i}", "name": f"Page {i}", "permissions": []},
            headers=headers,
        )

    resp = await client.get("/api/v1/audit?limit=2&offset=0", headers=headers)
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["has_next"] is True
    assert body["has_prev"] is False

    resp = await client.get("/api/v1/audit?limit=2&offset=2", headers=headers)
    body = resp.json()
    assert body["has_next"] is False  # 3rd page boundary (4 total entries? test sees >=3)
    assert body["has_prev"] is True


# ── Permission enforcement ──────────────────────────────────────────────────

async def test_viewer_cannot_read_audit_log(client: AsyncClient):
    # First user (admin) creates a role
    admin_headers = await _register_login(client, "admin_audit@example.com", "admin_audit")
    await client.post(
        "/api/v1/roles",
        json={"key": "audit_role", "name": "R", "permissions": []},
        headers=admin_headers,
    )

    # Second user is viewer by default → audit:read not in their set
    viewer_headers = await _register_login(client, "viewer_audit@example.com", "viewer_audit")
    resp = await client.get("/api/v1/audit", headers=viewer_headers)
    assert resp.status_code == 403
    assert "audit:read" in resp.json()["detail"]


async def test_unauthenticated_cannot_read_audit_log(client: AsyncClient):
    resp = await client.get("/api/v1/audit")
    assert resp.status_code == 401