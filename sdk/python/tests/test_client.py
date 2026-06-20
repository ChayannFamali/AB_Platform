"""
Тесты SDK без реального сервера.
responses — библиотека для мокирования HTTP.
"""
import json
import time

import pytest
import responses as resp

from abplatform import ABPlatformClient


# get_variant ──────────────────────────────────────────────────────────────

@resp.activate
def test_get_variant_assigned():
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/assignments",
        json={"assigned": True, "variant": "treatment", "experiment_id": "exp-1"},
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_variant("user_1", "exp-1") == "treatment"


@resp.activate
def test_get_variant_not_in_experiment():
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/assignments",
        json={"assigned": False, "variant": None, "experiment_id": "exp-1"},
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_variant("user_1", "exp-1", default="control") == "control"


def test_get_variant_server_down():
    """Сервер недоступен → возвращает default, не бросает исключение."""
    client = ABPlatformClient("http://nonexistent:9999", timeout=0.1)
    result = client.get_variant("user_1", "exp-1", default="control")
    assert result == "control"


@resp.activate
def test_get_variant_server_error():
    """500 от сервера → graceful degradation."""
    resp.add(resp.POST, "http://localhost:8000/api/v1/assignments", status=500)
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_variant("user_1", "exp-1", default="control") == "control"


# Caching ──────────────────────────────────────────────────────────────────

@resp.activate
def test_caching_second_call_no_request():
    """Второй вызов — из кэша, без HTTP запроса."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/assignments",
        json={"assigned": True, "variant": "treatment", "experiment_id": "exp-1"},
    )
    client = ABPlatformClient("http://localhost:8000", cache_ttl=60)
    client.get_variant("user_1", "exp-1")
    client.get_variant("user_1", "exp-1")
    client.get_variant("user_1", "exp-1")

    assert len(resp.calls) == 1  # только один HTTP запрос


def test_cache_ttl_expiry():
    """Кэш истекает через TTL."""
    from abplatform.cache import TTLCache
    cache = TTLCache(ttl=1)
    cache.set("key", "value")
    assert cache.get("key") == "value"
    time.sleep(1.1)
    assert cache.get("key") is None


# track_event ─────────────────────────────────────────────────────────────

def test_track_event_buffered():
    """События буферизуются — не отправляются сразу."""
    client = ABPlatformClient("http://localhost:8000", batch_size=100)
    client.track_event("user_1", "click")
    client.track_event("user_1", "purchase", value=49.99)

    with client._lock:
        assert len(client._event_buffer) == 2


@resp.activate
def test_flush_sends_batch():
    """flush() отправляет все события одним запросом."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/events/batch",
        json={"received": 2, "inserted": 2},
        status=201,
    )
    client = ABPlatformClient("http://localhost:8000")
    client.track_event("user_1", "click")
    client.track_event("user_2", "purchase", value=100.0)
    client.flush()

    assert len(resp.calls) == 1
    body = json.loads(resp.calls[0].request.body)
    assert len(body["events"]) == 2
    assert body["events"][1]["value"] == 100.0


@resp.activate
def test_auto_flush_on_batch_size():
    """При достижении batch_size — автоматический flush."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/events/batch",
        json={"received": 3, "inserted": 3},
        status=201,
    )
    client = ABPlatformClient("http://localhost:8000", batch_size=3)
    client.track_event("u1", "e1")
    client.track_event("u2", "e2")
    client.track_event("u3", "e3")  # ← при этом вызове должен flush

    time.sleep(0.1)
    assert len(resp.calls) == 1


def test_flush_server_down_no_exception():
    """flush() при недоступном сервере не бросает исключение."""
    client = ABPlatformClient("http://nonexistent:9999", timeout=0.1)
    client.track_event("user_1", "click")
    client.flush()  # не должно падать


# Context Manager ─────────────────────────────────────────────────────────

@resp.activate
def test_context_manager_flushes_on_exit():
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/events/batch",
        json={"received": 1, "inserted": 1},
        status=201,
    )
    with ABPlatformClient("http://localhost:8000") as client:
        client.track_event("user_1", "click")
    # при выходе из with — flush

    assert len(resp.calls) == 1


# ── Feature flags (M-009) ──────────────────────────────────────────────────


@resp.activate
def test_get_flag_returns_true_when_enabled():
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "new_checkout", "value": True, "reason": "rollout_in"},
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_flag("user_1", "new_checkout") is True


@resp.activate
def test_get_flag_returns_false_when_disabled():
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "new_checkout", "value": False, "reason": "kill_switch"},
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_flag("user_1", "new_checkout") is False


@resp.activate
def test_get_flag_returns_default_on_server_error():
    """5xx → client returns default, never raises."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        status=500,
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_flag("user_1", "any_flag", default=True) is True


def test_get_flag_returns_default_when_server_down():
    """Connection refused → client returns default, never raises."""
    client = ABPlatformClient("http://nonexistent:9999", timeout=0.1)
    assert client.get_flag("user_1", "any_flag", default=False) is False


@resp.activate
def test_get_flag_returns_false_for_missing_flag():
    """Server returns `value=False, reason=not_found` → SDK returns False."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "missing", "value": False, "reason": "not_found"},
    )
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_flag("user_1", "missing") is False


@resp.activate
def test_get_flag_cached():
    """Second call uses the cache — no second HTTP request."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "cached", "value": True, "reason": "rollout_in"},
    )
    client = ABPlatformClient("http://localhost:8000", cache_ttl=60)
    assert client.get_flag("user_1", "cached") is True
    assert client.get_flag("user_1", "cached") is True
    assert client.get_flag("user_1", "cached") is True
    assert len(resp.calls) == 1


@resp.activate
def test_get_flag_distinct_users_distinct_buckets():
    """The cache key includes user_id — different users don't share cache."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "per_user", "value": True, "reason": "rollout_in"},
    )
    client = ABPlatformClient("http://localhost:8000")
    client.get_flag("user_A", "per_user")
    client.get_flag("user_B", "per_user")
    assert len(resp.calls) == 2  # one per user


@resp.activate
def test_get_flags_batch():
    """Batch evaluation fetches all missing keys in one HTTP request."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate-batch",
        json={
            "values": {"a": True, "b": False, "c": True},
            "details": {},
        },
    )
    client = ABPlatformClient("http://localhost:8000")
    result = client.get_flags("user_1", ["a", "b", "c"])
    assert result == {"a": True, "b": False, "c": True}
    assert len(resp.calls) == 1


@resp.activate
def test_get_flags_uses_cache_for_already_resolved_keys():
    """Keys already cached skip the batch endpoint."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate",
        json={"key": "cached_flag", "value": True, "reason": "rollout_in"},
    )
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate-batch",
        json={"values": {"fresh_flag": False}, "details": {}},
    )
    client = ABPlatformClient("http://localhost:8000", cache_ttl=60)
    client.get_flag("user_1", "cached_flag")           # single fetch
    result = client.get_flags("user_1", ["cached_flag", "fresh_flag"])
    # Only the batch endpoint is hit — the single-fetch path is not
    # re-used for keys the cache already has.
    assert result == {"cached_flag": True, "fresh_flag": False}
    assert len([c for c in resp.calls if "/flags/evaluate-batch" in c.request.url]) == 1


def test_get_flags_empty_list_returns_empty_dict():
    client = ABPlatformClient("http://localhost:8000")
    assert client.get_flags("user_1", []) == {}


def test_get_flags_server_down_returns_all_defaults():
    client = ABPlatformClient("http://nonexistent:9999", timeout=0.1)
    result = client.get_flags("user_1", ["a", "b", "c"])
    assert result == {"a": False, "b": False, "c": False}


@resp.activate
def test_get_flags_403_missing_scope_graceful():
    """API key without `flags:read` returns 403 → SDK returns defaults."""
    resp.add(
        resp.POST,
        "http://localhost:8000/api/v1/sdk/flags/evaluate-batch",
        status=403,
    )
    client = ABPlatformClient("http://localhost:8000")
    result = client.get_flags("user_1", ["x"])
    assert result == {"x": False}
