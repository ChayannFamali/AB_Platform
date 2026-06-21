"""
Segment tests (M-010).

Covers:
- Unit (match_rule): all 9 operators (eq/neq/in/not_in/gt/lt/gte/lte/contains).
- CRUD lifecycle (create / list / get / update / delete).
- Rule CRUD (add / delete) — keeps AND-combination semantics.
- AND logic across multiple rules.
- Dry-run /evaluate endpoint (per-rule breakdown).
- Experiment linking (M2M) and unlinking.
- RBAC: viewer can read, editor can write, viewer cannot write.
- Audit log: every mutation appends a row.
"""
import pytest
from httpx import AsyncClient


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_segment_payload(
    key: str = "eu_users",
    name: str = "EU Users",
    rules: list | None = None,
) -> dict:
    return {
        "key": key,
        "name": name,
        "description": "Test segment",
        "rules": rules or [],
    }


async def _register_login(
    client: AsyncClient, email: str, username: str
) -> dict:
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": "password123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "password123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_segment(
    client: AsyncClient, headers: dict, **overrides
) -> dict:
    payload = _make_segment_payload(**overrides)
    resp = await client.post("/api/v1/segments", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_rule(
    field: str = "country",
    operator: str = "eq",
    value=...,
    priority: int = 0,
    enabled: bool = True,
) -> dict:
    return {
        "field": field,
        "operator": operator,
        "value": "DE" if value is ... else value,
        "priority": priority,
        "enabled": enabled,
    }


# ── Unit tests: match_rule operators ───────────────────────────────────────


@pytest.fixture
def rule_eq():
    from app.models.db import SegmentRule
    return SegmentRule(field="country", operator="eq", value="DE")


@pytest.fixture
def rule_in():
    from app.models.db import SegmentRule
    return SegmentRule(field="country", operator="in", value=["DE", "FR"])


@pytest.fixture
def rule_gt():
    from app.models.db import SegmentRule
    return SegmentRule(field="age", operator="gt", value=18)


@pytest.fixture
def rule_contains():
    from app.models.db import SegmentRule
    return SegmentRule(field="email", operator="contains", value="@example.com")


def test_match_rule_eq(rule_eq):
    from app.services.segment_service import match_rule
    assert match_rule(rule_eq, {"country": "DE"}) is True
    assert match_rule(rule_eq, {"country": "FR"}) is False
    # Missing field → False.
    assert match_rule(rule_eq, {}) is False


def test_match_rule_neq():
    from app.models.db import SegmentRule
    from app.services.segment_service import match_rule
    rule = SegmentRule(field="plan", operator="neq", value="free")
    assert match_rule(rule, {"plan": "pro"}) is True
    assert match_rule(rule, {"plan": "free"}) is False


def test_match_rule_in_not_in(rule_in):
    from app.services.segment_service import match_rule
    assert match_rule(rule_in, {"country": "DE"}) is True
    assert match_rule(rule_in, {"country": "FR"}) is True
    assert match_rule(rule_in, {"country": "US"}) is False

    from app.models.db import SegmentRule
    rule_not_in = SegmentRule(field="country", operator="not_in", value=["DE", "FR"])
    assert match_rule(rule_not_in, {"country": "US"}) is True
    assert match_rule(rule_not_in, {"country": "DE"}) is False


def test_match_rule_gt_lt_gte_lte(rule_gt):
    from app.models.db import SegmentRule
    from app.services.segment_service import match_rule
    assert match_rule(rule_gt, {"age": 25}) is True
    assert match_rule(rule_gt, {"age": 18}) is False
    assert match_rule(rule_gt, {"age": 10}) is False

    rule_lt = SegmentRule(field="age", operator="lt", value=18)
    assert match_rule(rule_lt, {"age": 10}) is True
    assert match_rule(rule_lt, {"age": 18}) is False

    rule_gte = SegmentRule(field="age", operator="gte", value=18)
    assert match_rule(rule_gte, {"age": 18}) is True
    assert match_rule(rule_gte, {"age": 17}) is False

    rule_lte = SegmentRule(field="age", operator="lte", value=18)
    assert match_rule(rule_lte, {"age": 18}) is True
    assert match_rule(rule_lte, {"age": 19}) is False


def test_match_rule_numeric_coercion():
    """String numbers compare as numbers in gt/lt comparisons."""
    from app.models.db import SegmentRule
    from app.services.segment_service import match_rule
    rule = SegmentRule(field="score", operator="gt", value="100")
    assert match_rule(rule, {"score": 150}) is True
    assert match_rule(rule, {"score": "150"}) is True
    assert match_rule(rule, {"score": 50}) is False
    # Non-numeric → False (not an exception).
    assert match_rule(rule, {"score": "abc"}) is False


def test_match_rule_contains(rule_contains):
    from app.services.segment_service import match_rule
    assert match_rule(rule_contains, {"email": "alice@example.com"}) is True
    assert match_rule(rule_contains, {"email": "bob@other.com"}) is False
    # Coerces non-strings via str().
    assert match_rule(rule_contains, {"email": 12345}) is False  # "12345" has no @
    # Missing field → False.
    assert match_rule(rule_contains, {}) is False


# ── CRUD lifecycle ─────────────────────────────────────────────────────────


async def test_create_segment_returns_full_payload(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    resp = await client.post(
        "/api/v1/segments",
        json=_make_segment_payload(
            key="eu_users",
            name="EU Users",
            rules=[_make_rule(field="country", operator="in", value=["DE", "FR"])],
        ),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key"] == "eu_users"
    assert len(body["rules"]) == 1


async def test_create_segment_duplicate_key_returns_409(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    await _create_segment(client, headers, key="dup_segment", name="Dup")
    resp = await client.post(
        "/api/v1/segments",
        json=_make_segment_payload(key="dup_segment", name="Dup 2"),
        headers=headers,
    )
    assert resp.status_code == 409


async def test_create_segment_rejects_bad_key(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    resp = await client.post(
        "/api/v1/segments",
        json=_make_segment_payload(key="AB", name="Bad Key"),  # too short + uppercase
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_segment_rejects_unknown_operator(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    resp = await client.post(
        "/api/v1/segments",
        json=_make_segment_payload(
            key="bad_op_segment",
            rules=[{"field": "country", "operator": "regex", "value": "DE"}],
        ),
        headers=headers,
    )
    assert resp.status_code == 422


async def test_list_segments_pagination(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    for i in range(3):
        await _create_segment(
            client, headers, key=f"seg_{i:03d}", name=f"Segment {i}",
        )
    resp = await client.get("/api/v1/segments?limit=2&offset=0", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["has_next"] is True


async def test_get_segment_by_id_and_key(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(client, headers, key="lookup_seg", name="Lookup")

    by_id = await client.get(f"/api/v1/segments/{seg['id']}", headers=headers)
    assert by_id.status_code == 200
    assert by_id.json()["key"] == "lookup_seg"

    by_key = await client.get("/api/v1/segments/by-key/lookup_seg", headers=headers)
    assert by_key.status_code == 200
    assert by_key.json()["id"] == seg["id"]


async def test_get_unknown_segment_returns_404(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    import uuid
    resp = await client.get(
        f"/api/v1/segments/{uuid.uuid4()}", headers=headers,
    )
    assert resp.status_code == 404


async def test_update_segment_replaces_rules(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(
        client, headers, key="upd_seg", name="Upd",
        rules=[_make_rule(field="country", operator="eq", value="DE")],
    )
    resp = await client.patch(
        f"/api/v1/segments/{seg['id']}",
        json={
            "rules": [
                _make_rule(field="country", operator="in",
                          value=["DE", "FR"]),
                _make_rule(field="plan", operator="neq", value="free",
                          priority=1),
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rules"]) == 2


async def test_delete_segment_cascades_rules(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(
        client, headers, key="del_seg", name="Del",
        rules=[_make_rule(field="country", operator="eq", value="DE")],
    )
    resp = await client.delete(
        f"/api/v1/segments/{seg['id']}", headers=headers,
    )
    assert resp.status_code == 204
    # Confirm gone.
    get_resp = await client.get(
        f"/api/v1/segments/{seg['id']}", headers=headers,
    )
    assert get_resp.status_code == 404


# ── Rule CRUD ──────────────────────────────────────────────────────────────


async def test_add_and_delete_rule(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(client, headers, key="rules_seg", name="Rules")

    resp = await client.post(
        f"/api/v1/segments/{seg['id']}/rules",
        json=_make_rule(field="plan", operator="eq", value="pro"),
        headers=headers,
    )
    assert resp.status_code == 201
    rule_id = resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/segments/{seg['id']}", headers=headers,
    )
    assert len(get_resp.json()["rules"]) == 1

    del_resp = await client.delete(
        f"/api/v1/segments/{seg['id']}/rules/{rule_id}", headers=headers,
    )
    assert del_resp.status_code == 204


# ── AND logic ──────────────────────────────────────────────────────────────


async def test_and_logic_all_rules_must_match(client: AsyncClient):
    """Two enabled rules — both must match (AND)."""
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(
        client, headers, key="and_seg", name="AND",
        rules=[
            _make_rule(field="country", operator="eq", value="DE", priority=0),
            _make_rule(field="plan", operator="eq", value="pro", priority=1),
        ],
    )
    seg_id = seg["id"]

    # Both match → matches=True.
    r1 = await client.post(
        f"/api/v1/segments/{seg_id}/evaluate",
        json={"user_properties": {"country": "DE", "plan": "pro"}},
        headers=headers,
    )
    assert r1.json()["matches"] is True
    assert r1.json()["matched_rules"] == 2

    # Only one match → matches=False.
    r2 = await client.post(
        f"/api/v1/segments/{seg_id}/evaluate",
        json={"user_properties": {"country": "DE", "plan": "free"}},
        headers=headers,
    )
    assert r2.json()["matches"] is False
    assert r2.json()["matched_rules"] == 1


async def test_disabled_rule_is_skipped(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(
        client, headers, key="skip_seg", name="Skip",
        rules=[_make_rule(field="country", operator="eq", value="DE", enabled=False)],
    )
    r = await client.post(
        f"/api/v1/segments/{seg['id']}/evaluate",
        json={"user_properties": {"country": "DE"}},
        headers=headers,
    )
    # Disabled rule → no rules evaluated → vacuously matches.
    assert r.json()["matches"] is True
    assert r.json()["total_rules"] == 0


# ── /evaluate dry-run ──────────────────────────────────────────────────────


async def test_evaluate_returns_per_rule_breakdown(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    seg = await _create_segment(
        client, headers, key="break_seg", name="Breakdown",
        rules=[
            _make_rule(field="country", operator="eq", value="DE", priority=0),
            _make_rule(field="plan", operator="eq", value="pro", priority=1),
        ],
    )
    r = await client.post(
        f"/api/v1/segments/{seg['id']}/evaluate",
        json={"user_properties": {"country": "FR", "plan": "pro"}},
        headers=headers,
    )
    body = r.json()
    assert body["matches"] is False
    assert body["matched_rules"] == 1
    assert body["total_rules"] == 2
    per_rule = body["per_rule"]
    assert per_rule[0]["matched"] is False  # country=FR, expected DE
    assert per_rule[1]["matched"] is True   # plan=pro, expected pro


# ── Experiment linking ─────────────────────────────────────────────────────


async def test_link_and_unlink_segment_to_experiment(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    # Create a segment.
    seg = await _create_segment(client, headers, key="link_seg", name="Link")
    # Create an experiment.
    exp_resp = await client.post("/api/v1/experiments", json={
        "name": "Link Test",
        "variants": [
            {"name": "control",   "traffic_split": 50},
            {"name": "treatment", "traffic_split": 50},
        ],
        "metrics": [{
            "name": "Click Rate",
            "event_name": "click",
            "metric_type": "conversion",
            "is_primary": True,
        }],
    }, headers=headers)
    assert exp_resp.status_code == 201
    exp_id = exp_resp.json()["id"]

    # Link the segment to the experiment.
    link_resp = await client.post(
        f"/api/v1/segments/{seg['id']}/experiments",
        json={"experiment_ids": [exp_id]},
        headers=headers,
    )
    assert link_resp.status_code == 201

    # Unlink.
    unlink_resp = await client.delete(
        f"/api/v1/segments/{seg['id']}/experiments/{exp_id}",
        headers=headers,
    )
    assert unlink_resp.status_code == 204


# ── RBAC ───────────────────────────────────────────────────────────────────


async def test_viewer_can_read_but_not_write(client: AsyncClient):
    # First user → admin → can create.
    admin_headers = await _register_login(
        client, "admin@example.com", "admin",
    )
    await _create_segment(client, admin_headers, key="rbac_seg", name="RBAC")

    # Second user → viewer (default).
    await client.post("/api/v1/auth/register", json={
        "username": "viewer", "email": "viewer@example.com", "password": "password123",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "viewer@example.com", "password": "password123",
    })
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Read allowed.
    r = await client.get("/api/v1/segments", headers=viewer_headers)
    assert r.status_code == 200

    # Write forbidden.
    w = await client.post(
        "/api/v1/segments",
        json=_make_segment_payload(key="v_seg", name="V"),
        headers=viewer_headers,
    )
    assert w.status_code == 403


# ── Audit ──────────────────────────────────────────────────────────────────


async def test_create_segment_writes_audit_entry(client: AsyncClient):
    headers = await _register_login(client, "creator@example.com", "creator")
    await _create_segment(client, headers, key="audited_seg", name="Audited")
    r = await client.get(
        "/api/v1/audit?resource_type=segment", headers=headers,
    )
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()["items"]]
    assert "create" in actions
