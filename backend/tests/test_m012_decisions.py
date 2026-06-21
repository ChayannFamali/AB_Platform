"""
M-012 integration tests: Decision Log.

Covers the append-only decision history per experiment:
  - POST  /api/v1/experiments/{id}/decisions   (decisions:write)
  - GET   /api/v1/experiments/{id}/decisions   (results:read)
  - experiments.decision_status mirrors the latest decision
  - Invalid status → 422
  - Permission gate (analyst → 403 on POST; viewer → 403 on POST)
  - Append-only: no PATCH/DELETE endpoints exist
  - Decision log + status update happen in the same transaction
  - Audit log row created on POST
  - Decisions cascade-delete with experiment

Run:
    cd backend && PYTHONPATH=. pytest tests/test_m012_decisions.py -v
"""
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.db import AuditLog, Decision, Experiment, Role, User, UserRole


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _register_login(client: AsyncClient, email: str, username: str) -> dict:
    """Register + login a non-admin user, return auth headers."""
    await client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "password": "password123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _grant_role(db: AsyncSession, email: str, role_key: str) -> None:
    """Attach a role to a user bypassing the public API (admin-only)."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    role = (await db.execute(select(Role).where(Role.key == role_key))).scalar_one()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()


# ── 1. Happy path: create + list ────────────────────────────────────────────

async def test_create_decision_happy_path(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    resp = await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship", "comment": "Treatment +3.2% (p=0.012)."},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "ship"
    assert body["comment"] == "Treatment +3.2% (p=0.012)."
    assert body["experiment_id"] == exp_id
    assert body["decided_by_username"] == "testuser"
    assert body["decided_by"] is not None
    assert body["decided_at"] is not None


async def test_create_decision_without_comment_is_allowed(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    resp = await client.post(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        json={"status": "iterate"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["comment"] is None


@pytest.mark.parametrize("status", ["ship", "stop", "iterate", "inconclusive"])
async def test_create_decision_accepts_all_four_statuses(
    client: AsyncClient, conversion_experiment, auth_headers, status,
):
    resp = await client.post(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        json={"status": status},
        headers=auth_headers,
    )
    assert resp.status_code == 201, f"{status}: {resp.text}"
    assert resp.json()["status"] == status


async def test_create_decision_rejects_unknown_status(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    resp = await client.post(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        json={"status": "maybe-later"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_create_decision_404_for_unknown_experiment(
    client: AsyncClient, auth_headers,
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(
        f"/api/v1/experiments/{fake_id}/decisions",
        json={"status": "ship"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── 2. experiment.decision_status mirror ────────────────────────────────────

async def test_decision_status_mirrors_latest_decision(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    # Initially null.
    detail = await client.get(f"/api/v1/experiments/{exp_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["decision_status"] is None

    # First decision → "iterate".
    await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "iterate", "comment": "Need more data"},
        headers=auth_headers,
    )
    detail = await client.get(f"/api/v1/experiments/{exp_id}", headers=auth_headers)
    assert detail.json()["decision_status"] == "iterate"

    # Second decision → "ship". decision_status should track the latest.
    await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship", "comment": "Confirmed"},
        headers=auth_headers,
    )
    detail = await client.get(f"/api/v1/experiments/{exp_id}", headers=auth_headers)
    assert detail.json()["decision_status"] == "ship"


# ── 3. List ─────────────────────────────────────────────────────────────────

async def test_list_decisions_empty(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    resp = await client.get(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["has_next"] is False


async def test_list_decisions_returns_most_recent_first(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    for status in ("iterate", "inconclusive", "ship"):
        resp = await client.post(
            f"/api/v1/experiments/{exp_id}/decisions",
            json={"status": status},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/decisions",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert [d["status"] for d in body["items"]] == ["ship", "inconclusive", "iterate"]


async def test_list_decisions_pagination(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    for i in range(5):
        await client.post(
            f"/api/v1/experiments/{exp_id}/decisions",
            json={"status": "iterate"},
            headers=auth_headers,
        )
    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/decisions?limit=2&offset=2",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["has_next"] is True
    assert body["has_prev"] is True


async def test_list_decisions_is_scoped_to_experiment(
    client: AsyncClient, auth_headers,
):
    # Two experiments → decisions in one must not leak to the other.
    a = (await client.post("/api/v1/experiments", json={
        "name": "A",
        "variants": [
            {"name": "c", "traffic_split": 50},
            {"name": "t", "traffic_split": 50},
        ],
        "metrics": [{
            "name": "M", "event_name": "e",
            "metric_type": "conversion", "is_primary": True,
        }],
    }, headers=auth_headers)).json()
    b = (await client.post("/api/v1/experiments", json={
        "name": "B",
        "variants": [
            {"name": "c", "traffic_split": 50},
            {"name": "t", "traffic_split": 50},
        ],
        "metrics": [{
            "name": "M", "event_name": "e",
            "metric_type": "conversion", "is_primary": True,
        }],
    }, headers=auth_headers)).json()

    await client.post(f"/api/v1/experiments/{a['id']}/decisions",
                      json={"status": "ship"}, headers=auth_headers)
    await client.post(f"/api/v1/experiments/{b['id']}/decisions",
                      json={"status": "stop"}, headers=auth_headers)
    await client.post(f"/api/v1/experiments/{b['id']}/decisions",
                      json={"status": "iterate"}, headers=auth_headers)

    ra = await client.get(f"/api/v1/experiments/{a['id']}/decisions",
                          headers=auth_headers)
    rb = await client.get(f"/api/v1/experiments/{b['id']}/decisions",
                          headers=auth_headers)
    assert ra.json()["total"] == 1
    assert rb.json()["total"] == 2
    assert [d["status"] for d in rb.json()["items"]] == ["iterate", "stop"]


# ── 4. Append-only: no PATCH / DELETE ───────────────────────────────────────

async def test_decision_log_has_no_patch_endpoint(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    create = await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship"},
        headers=auth_headers,
    )
    decision_id = create.json()["id"]
    # PATCH must not exist — FastAPI returns 404 (no matching route) or
    # 405 (method not allowed) when an endpoint is missing. Either is
    # acceptable; both prove the absence of a mutation surface.
    resp = await client.patch(
        f"/api/v1/experiments/{exp_id}/decisions/{decision_id}",
        json={"comment": "tampered"},
        headers=auth_headers,
    )
    assert resp.status_code in (404, 405)


async def test_decision_log_has_no_delete_endpoint(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    exp_id = conversion_experiment["id"]
    create = await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship"},
        headers=auth_headers,
    )
    decision_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/experiments/{exp_id}/decisions/{decision_id}",
        headers=auth_headers,
    )
    assert resp.status_code in (404, 405)


# ── 5. RBAC ─────────────────────────────────────────────────────────────────

async def test_analyst_cannot_create_decision(
    client: AsyncClient, conversion_experiment, engine,
):
    headers = await _register_login(client, "analyst@example.com", "analyst")
    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role(db, "analyst@example.com", "analyst")

    resp = await client.post(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        json={"status": "ship"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_analyst_can_list_decisions(
    client: AsyncClient, conversion_experiment, engine, auth_headers,
):
    exp_id = conversion_experiment["id"]
    await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship"},
        headers=auth_headers,
    )
    headers = await _register_login(client, "analyst@example.com", "analyst")
    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        await _grant_role(db, "analyst@example.com", "analyst")

    resp = await client.get(
        f"/api/v1/experiments/{exp_id}/decisions",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_viewer_cannot_create_decision(
    client: AsyncClient, conversion_experiment,
):
    headers = await _register_login(client, "viewer@example.com", "viewer")
    resp = await client.post(
        f"/api/v1/experiments/{conversion_experiment['id']}/decisions",
        json={"status": "ship"},
        headers=headers,
    )
    # viewers register with the "viewer" role by default → no decisions:write.
    assert resp.status_code == 403


# ── 6. Audit + cascade ──────────────────────────────────────────────────────

async def test_create_decision_writes_audit_entry(
    client: AsyncClient, conversion_experiment, auth_headers, engine,
):
    exp_id = conversion_experiment["id"]
    create = await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship", "comment": "OK"},
        headers=auth_headers,
    )
    decision_id = create.json()["id"]

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.resource_type == "decision")
            .where(AuditLog.resource_id == UUID(decision_id))
        )
        row = result.scalar_one_or_none()

    assert row is not None
    assert row.action == "create"
    assert row.details["status"] == "ship"
    assert row.details["experiment_id"] == exp_id
    assert row.details["has_comment"] is True


async def test_decision_status_rollback_on_failure(
    client: AsyncClient, conversion_experiment, auth_headers,
):
    """
    If the second decision POST fails (invalid status), the
    experiment's decision_status must NOT advance. We test this by
    sending an invalid payload that gets rejected at Pydantic (422),
    leaving the experiment's status at whatever it was before.
    """
    exp_id = conversion_experiment["id"]
    await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "iterate"},
        headers=auth_headers,
    )
    # Invalid status — FastAPI rejects before reaching the DB.
    bad = await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "wat"},
        headers=auth_headers,
    )
    assert bad.status_code == 422

    detail = await client.get(f"/api/v1/experiments/{exp_id}", headers=auth_headers)
    # Status is still "iterate" — the failed POST did not mutate state.
    assert detail.json()["decision_status"] == "iterate"


async def test_decisions_cascade_with_experiment(
    client: AsyncClient, conversion_experiment, auth_headers, engine,
):
    exp_id = conversion_experiment["id"]
    await client.post(
        f"/api/v1/experiments/{exp_id}/decisions",
        json={"status": "ship"},
        headers=auth_headers,
    )

    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as db:
        before = (await db.execute(
            select(Decision).where(Decision.experiment_id == UUID(exp_id))
        )).scalars().all()
        assert len(before) == 1

    # The experiment is in DRAFT so DELETE is allowed (router-enforced).
    delete = await client.delete(
        f"/api/v1/experiments/{exp_id}", headers=auth_headers,
    )
    assert delete.status_code == 204

    async with TestSession() as db:
        after = (await db.execute(
            select(Decision).where(Decision.experiment_id == UUID(exp_id))
        )).scalars().all()
        assert after == []  # cascade-delete via FK ON DELETE CASCADE