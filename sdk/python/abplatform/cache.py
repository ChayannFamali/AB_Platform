import time


class TTLCache:
    """
    Простой in-memory кэш с TTL.
    Хранит вариант пользователя — не нужно дёргать API при каждом вызове.
    """

    def __init__(self, ttl: int = 300):
        self._ttl = ttl
        self._store: dict[str, tuple[str, float]] = {} 

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
