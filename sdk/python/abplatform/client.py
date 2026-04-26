import logging
import threading
import time
from typing import Optional

import requests

from .cache import TTLCache

logger = logging.getLogger(__name__)


class ABPlatformClient:
    """
    Python SDK для AB Platform.

    Использование без авторизации (старый способ, deprecated):
        client = ABPlatformClient("http://localhost:8000")

    С API ключом (рекомендуется):
        client = ABPlatformClient(
            api_url="http://localhost:8000",
            api_key="abp_ваш_ключ",
        )
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,  
        timeout: float = 1.0,
        cache_ttl: int = 300,
        batch_size: int = 50,
        flush_interval: float = 10.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._cache = TTLCache(ttl=cache_ttl)
        self._event_buffer: list[dict] = []
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._lock = threading.Lock()
        self._closed = False

        # Заголовки для всех запросов
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-API-Key"] = api_key

        self._flush_thread = threading.Thread(
            target=self._auto_flush_loop,
            daemon=True,
            name="abplatform-flush",
        )
        self._flush_thread.start()

    # Public API ───────────────────────────────────────────────────────────

    def get_variant(
        self,
        user_id: str,
        experiment_id: str,
        default: str = "control",
    ) -> str:
        """
        Возвращает вариант эксперимента для пользователя.
        Никогда не бросает исключение — при любой ошибке возвращает default.
        """
        cache_key = f"{user_id}:{experiment_id}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = requests.post(
                f"{self.api_url}/api/v1/assignments",
                json={"user_id": user_id, "experiment_id": experiment_id},
                headers=self._headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("assigned") and data.get("variant"):
                    variant = data["variant"]
                    self._cache.set(cache_key, variant)
                    return variant
        except requests.exceptions.Timeout:
            logger.warning("ABPlatform: get_variant timeout — returning default")
        except requests.exceptions.ConnectionError:
            logger.warning("ABPlatform: server unavailable — returning default")
        except Exception as e:
            logger.warning(f"ABPlatform: get_variant error: {e}")

        return default

    def track_event(
        self,
        user_id: str,
        event_name: str,
        value: Optional[float] = None,
        properties: Optional[dict] = None,
    ) -> None:
        """Буферизует событие для батч отправки. Никогда не бросает исключение."""
        event = {
            "user_id": user_id,
            "event_name": event_name,
            "value": value,
            "properties": properties,
        }
        flush_now = False
        with self._lock:
            self._event_buffer.append(event)
            if len(self._event_buffer) >= self._batch_size:
                flush_now = True

        if flush_now:
            self._flush()

    def flush(self) -> None:
        """Принудительно отправляет все буферизованные события."""
        self._flush()

    def close(self) -> None:
        """Flush и завершение. Вызывай при shutdown приложения."""
        self._closed = True
        self._flush()

    # Internal ─────────────────────────────────────────────────────────────

    def _flush(self) -> None:
        with self._lock:
            if not self._event_buffer:
                return
            events = self._event_buffer.copy()
            self._event_buffer.clear()

        try:
            response = requests.post(
                f"{self.api_url}/api/v1/events/batch",
                json={"events": events},
                headers=self._headers,
                timeout=self.timeout * 5,
            )
            if response.status_code == 201:
                logger.debug(f"ABPlatform: flushed {len(events)} events")
            else:
                logger.warning(f"ABPlatform: flush failed {response.status_code}")
        except Exception as e:
            logger.warning(f"ABPlatform: flush error: {e}")

    def _auto_flush_loop(self) -> None:
        while not self._closed:
            time.sleep(self._flush_interval)
            self._flush()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self) -> str:
        has_key = "X-API-Key" in self._headers
        return f"ABPlatformClient(api_url={self.api_url!r}, authenticated={has_key})"
