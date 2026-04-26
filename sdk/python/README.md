# AB Platform — Python SDK

## Installation

```bash
pip install abplatform
# или локально:
pip install -e sdk/python/
```

## Quick Start

```python
from abplatform import ABPlatformClient

client = ABPlatformClient("http://your-ab-platform:8000")

# Получить вариант
variant = client.get_variant(
    user_id="user_123",
    experiment_id="your-experiment-uuid",
    default="control",   # fallback если сервер недоступен
)

if variant == "treatment":
    show_new_button()
else:
    show_old_button()

# Трекать событие
client.track_event("user_123", "button_click")
client.track_event("user_123", "purchase", value=49.99)
client.track_event("user_123", "page_view", properties={"page": "/home"})

# Flush при shutdown (опционально — фоновый поток флушит автоматически)
client.flush()
```

## Context Manager

```python
with ABPlatformClient("http://localhost:8000") as client:
    variant = client.get_variant("user_123", "exp-uuid")
    # при выходе из блока — автоматический flush
```

## Конфигурация

```python
client = ABPlatformClient(
    api_url="http://localhost:8000",
    timeout=1.0,         # таймаут запроса к API (секунды)
    cache_ttl=300,       # кэш варианта (секунды)
    batch_size=50,       # flush при N событиях в буфере
    flush_interval=10.0, # flush каждые N секунд
)
```

## Graceful Degradation

SDK никогда не бросает исключение.
Если сервер недоступен — `get_variant` возвращает `default`.
