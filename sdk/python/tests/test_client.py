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
