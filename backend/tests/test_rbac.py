"""
RBAC tests (M-003, ADR-006).

Verifies the permission matrix end-to-end:
  - admin   : everything works (200/201/204)
  - editor  : create/update allowed; delete blocked
  - analyst : read + analyze only; create blocked
  - viewer  : read only; mutations blocked
  - SDK key without `events:write` → 403 on POST /events
  - SDK key without `assignments:read` → 403 on POST /assignments

Run:
    cd backend && PYTHONPATH=. pytest tests/test_rbac.py -v
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db import ApiKey
from app.services.auth_service import create_api_key


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _register_login(
    client: AsyncClient, email: str, username: str
) -> dict:
    """Register + login; return Authorization header dict."""
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
    """Bypass the public API to assign an arbitrary role to a user.
    Used to set up editor/analyst/viewer without going through admin flows.
    """
    from sqlalchemy import select
    from app.models.db import Role, User, UserRole

    user_result = await db.execute(select(User).where(User.email == user_email))
    user = user_result.scalar_one()
    role_result = await db.execute(select(Role).where(Role.key == role_key))
    role = role_result.scalar_one()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()


def _create_experiment_payload(name: str = "Test exp") -> dict:
    """Plain dict — NOT async, so callers must NOT await it."""
    return {
        "name": name,
        "variants": [
            {"name": "control",   "traffic_split": 50},
            {"name": "treatment", "traffic_split": 50},
        ],
        "metrics": [{
            "name":        "Click Rate",
            "event_name":  "button_click",
            "metric_type": "conversion",
            "is_primary":  True,
        }],
    }


# ── Auth & /me shape ───────────────────────────────────────────────────────

async def test_first_registered_user_has_admin_role(
    client: AsyncClient,
):
    headers = await _register_login(client, "admin@example.com", "admin")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_admin"] is True
    role_keys = [r["key"] for r in data["roles"]]
    assert "admin" in role_keys
    assert "users:manage" in data["permissions"]
    assert "experiments:delete" in data["permissions"]


async def test_second_user_has_viewer_role_by_default(
    client: AsyncClient,
):
    # Register first user (admin)
    await _register_login(client, "first@example.com", "first")
    # Register second user (should be viewer)
    headers = await _register_login(client, "second@example.com", "second")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    data = resp.json()
    assert data["is_admin"] is False
    role_keys = [r["key"] for r in data["roles"]]
    assert "viewer" in role_keys
    assert "users:manage" not in data["permissions"]
    assert "experiments:read" in data["permissions"]


# ── Admin: full access ─────────────────────────────────────────────────────

async def test_admin_can_list_roles(client: AsyncClient):
    headers = await _register_login(client, "admin2@example.com", "admin2")
    resp = await client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 200
    keys = {r["key"] for r in resp.json()["items"]}
    assert keys == {"admin", "editor", "analyst", "viewer"}


async def test_admin_can_create_and_delete_experiment(client: AsyncClient):
    headers = await _register_login(client, "admin3@example.com", "admin3")
    payload = _create_experiment_payload()
    resp = await client.post("/api/v1/experiments", json=payload, headers=headers)
    assert resp.status_code == 201
    exp_id = resp.json()["id"]

    # Admin has experiments:delete
    resp = await client.delete(f"/api/v1/experiments/{exp_id}", headers=headers)
    assert resp.status_code == 204


# ── Editor: create+update, NOT delete ──────────────────────────────────────

async def test_editor_can_create_experiment(
    client: AsyncClient, engine
):
    # Set up: first user is admin (registers itself), then we grant editor
    await _register_login(client, "owner@example.com", "owner")
    headers = await _register_login(client, "editor@example.com", "editor")

    # Grant editor role to second user
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role_via_db(db, "editor@example.com", "editor")

    payload = _create_experiment_payload("Editor exp")
    resp = await client.post("/api/v1/experiments", json=payload, headers=headers)
    assert resp.status_code == 201
    exp_id = resp.json()["id"]

    # Editor can update status (running)
    resp = await client.patch(
        f"/api/v1/experiments/{exp_id}/status",
        json={"status": "running"},
        headers=headers,
    )
    assert resp.status_code == 200


async def test_editor_cannot_delete_experiment(
    client: AsyncClient, engine
):
    await _register_login(client, "owner2@example.com", "owner2")
    headers = await _register_login(client, "editor2@example.com", "editor2")
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role_via_db(db, "editor2@example.com", "editor")

    # Create experiment as editor
    resp = await client.post(
        "/api/v1/experiments",
        json=_create_experiment_payload("To delete"),
        headers=headers,
    )
    assert resp.status_code == 201
    exp_id = resp.json()["id"]

    # Editor cannot delete
    resp = await client.delete(f"/api/v1/experiments/{exp_id}", headers=headers)
    assert resp.status_code == 403
    assert "experiments:delete" in resp.json()["detail"]


# ── Analyst: read + analyze, NOT create ────────────────────────────────────

async def test_analyst_can_read_but_not_create(
    client: AsyncClient, engine
):
    await _register_login(client, "owner3@example.com", "owner3")
    headers = await _register_login(client, "analyst@example.com", "analyst")
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role_via_db(db, "analyst@example.com", "analyst")

    # Read: 200
    resp = await client.get("/api/v1/experiments", headers=headers)
    assert resp.status_code == 200

    # Create: 403
    resp = await client.post(
        "/api/v1/experiments",
        json=_create_experiment_payload("Analyst tries"),
        headers=headers,
    )
    assert resp.status_code == 403
    assert "experiments:create" in resp.json()["detail"]


async def test_analyst_can_run_analysis(
    client: AsyncClient, engine, conversion_experiment
):
    headers = await _register_login(client, "analyst2@example.com", "analyst2")
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role_via_db(db, "analyst2@example.com", "analyst")

    exp_id = conversion_experiment["id"]
    resp = await client.post(
        f"/api/v1/experiments/{exp_id}/analyze", headers=headers,
    )
    assert resp.status_code == 200


# ── Viewer: read-only ───────────────────────────────────────────────────────

async def test_viewer_cannot_modify(client: AsyncClient):
    # Second user gets viewer role by default.
    await _register_login(client, "owner4@example.com", "owner4")
    headers = await _register_login(client, "viewer@example.com", "viewer")

    # Read: OK
    resp = await client.get("/api/v1/experiments", headers=headers)
    assert resp.status_code == 200

    # Create: blocked
    resp = await client.post(
        "/api/v1/experiments",
        json=_create_experiment_payload("Viewer attempt"),
        headers=headers,
    )
    assert resp.status_code == 403


async def test_viewer_cannot_manage_users(client: AsyncClient):
    await _register_login(client, "owner5@example.com", "owner5")
    headers = await _register_login(client, "viewer2@example.com", "viewer2")

    resp = await client.get("/api/v1/roles", headers=headers)
    assert resp.status_code == 403
    assert "users:manage" in resp.json()["detail"]


# ── API key scopes ─────────────────────────────────────────────────────────

async def test_api_key_default_scopes_grant_events_write(
    client: AsyncClient,
):
    """Default scopes (assignments:read + events:write) should let SDK work."""
    headers = await _register_login(client, "scope1@example.com", "scope1")
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "sdk"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert sorted(resp.json()["scopes"]) == ["assignments:read", "events:write"]

    key = resp.json()["key"]
    # POST /events should work with default scope
    resp = await client.post(
        "/api/v1/events",
        json={"user_id": "u1", "event_name": "page_view"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 201


async def test_api_key_without_events_write_scope_rejected(client: AsyncClient):
    """A key created with only `assignments:read` must get 403 on POST /events."""
    headers = await _register_login(client, "scope2@example.com", "scope2")
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "readonly", "scopes": ["assignments:read"]},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["scopes"] == ["assignments:read"]

    key = resp.json()["key"]
    resp = await client.post(
        "/api/v1/events",
        json={"user_id": "u1", "event_name": "page_view"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403
    assert "events:write" in resp.json()["detail"]


async def test_api_key_without_assignments_read_scope_rejected(client: AsyncClient):
    headers = await _register_login(client, "scope3@example.com", "scope3")
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "eventsonly", "scopes": ["events:write"]},
        headers=headers,
    )
    assert resp.status_code == 201
    key = resp.json()["key"]

    # Need a running experiment to call /assignments. For now we just check
    # the 403 path is hit before any DB lookup that requires experiment.
    resp = await client.post(
        "/api/v1/assignments",
        json={"user_id": "u1", "experiment_id": "00000000-0000-0000-0000-000000000000"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403
    assert "assignments:read" in resp.json()["detail"]


async def test_api_key_with_wildcard_scope_grants_all(client: AsyncClient):
    headers = await _register_login(client, "scope4@example.com", "scope4")
    resp = await client.post(
        "/api/v1/api-keys",
        json={"name": "admin-key", "scopes": ["*"]},
        headers=headers,
    )
    assert resp.status_code == 201
    key = resp.json()["key"]

    # Wildcard should let events through
    resp = await client.post(
        "/api/v1/events",
        json={"user_id": "u1", "event_name": "page_view"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 201


# ── Roles CRUD (admin-only) ────────────────────────────────────────────────

async def test_admin_can_create_custom_role(client: AsyncClient):
    headers = await _register_login(client, "adminr@example.com", "adminr")
    resp = await client.post(
        "/api/v1/roles",
        json={
            "key":         "custom_reviewer",
            "name":        "Custom Reviewer",
            "description": "Read-only with audit access",
            "permissions": ["experiments:read", "audit:read"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["key"] == "custom_reviewer"
    assert sorted(resp.json()["permissions"]) == ["audit:read", "experiments:read"]


async def test_admin_cannot_create_duplicate_role_key(client: AsyncClient):
    headers = await _register_login(client, "admindup@example.com", "admindup")
    payload = {"key": "dup", "name": "Dup", "permissions": []}
    resp = await client.post("/api/v1/roles", json=payload, headers=headers)
    assert resp.status_code == 201
    # Second time → 409
    resp = await client.post("/api/v1/roles", json=payload, headers=headers)
    assert resp.status_code == 409


async def test_admin_can_assign_and_revoke_role(client: AsyncClient, engine):
    # Owner is admin, target is the second user (currently viewer).
    owner_headers = await _register_login(client, "own@example.com", "own")
    target_headers = await _register_login(client, "tgt@example.com", "tgt")

    # Find target user id from /auth/me
    resp = await client.get("/api/v1/auth/me", headers=target_headers)
    target_id = resp.json()["id"]

    # Find editor role id
    resp = await client.get("/api/v1/roles", headers=owner_headers)
    editor_id = next(r["id"] for r in resp.json()["items"] if r["key"] == "editor")

    # Assign editor
    resp = await client.post(
        f"/api/v1/users/{target_id}/roles",
        json={"role_id": editor_id},
        headers=owner_headers,
    )
    assert resp.status_code == 201

    # Target user should now have editor → experiments:create
    resp = await client.post(
        "/api/v1/experiments",
        json=_create_experiment_payload("After promotion"),
        headers=target_headers,
    )
    assert resp.status_code == 201, resp.text

    # Revoke editor
    resp = await client.delete(
        f"/api/v1/users/{target_id}/roles/{editor_id}",
        headers=owner_headers,
    )
    assert resp.status_code == 204

    # Target now reverts to viewer — create blocked
    resp = await client.post(
        "/api/v1/experiments",
        json=_create_experiment_payload("After demotion"),
        headers=target_headers,
    )
    assert resp.status_code == 403


async def test_non_admin_cannot_list_users(client: AsyncClient):
    await _register_login(client, "nonadmin@example.com", "nonadmin")
    headers = await _register_login(client, "viewer3@example.com", "viewer3")
    resp = await client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 403