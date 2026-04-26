import hashlib


def get_bucket(user_id: str, experiment_id: str) -> int:
    """
    Детерминированный бакет 0-99 для пары user+experiment.
    Один и тот же user_id всегда даёт одинаковый бакет.
    Перезапуск сервера, смена БД — результат не меняется.
    """
    key = f"{user_id}:{experiment_id}"
    hash_bytes = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(hash_bytes[:4], byteorder="big") % 100


def is_in_traffic(user_id: str, experiment_id: str, traffic_percentage: float) -> bool:
    """
    Проверяет попадает ли пользователь в % трафика эксперимента.
    Отдельный хэш от bucketing — независимые решения.
    
    Пример: traffic_percentage=50 → половина пользователей
    вообще не участвует в эксперименте.
    """
    key = f"traffic:{user_id}:{experiment_id}"
    hash_bytes = hashlib.sha256(key.encode()).digest()
    bucket = int.from_bytes(hash_bytes[:4], byteorder="big") % 100
    return bucket < traffic_percentage


def pick_variant(bucket: int, variants: list[dict]) -> dict | None:
    """
    Выбирает вариант по бакету и traffic_split.
    Варианты сортируются по имени — детерминированный порядок.
    
    Пример: control=50%, treatment=50%
    bucket 0-49  → control
    bucket 50-99 → treatment
    """
    sorted_variants = sorted(variants, key=lambda v: v["name"])
    cumulative = 0.0
    for variant in sorted_variants:
        cumulative += variant["traffic_split"]
        if bucket < cumulative:
            return variant
    return None
