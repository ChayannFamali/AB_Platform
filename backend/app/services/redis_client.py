import json
from uuid import UUID

from redis.asyncio import ConnectionPool, Redis

from app.config import settings

# Connection pool — создаётся один раз при старте
pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:
    async with Redis(connection_pool=pool) as redis:
        yield redis


# Experiment cache 

async def get_experiment_cache(redis: Redis, experiment_id: str) -> dict | None:
    data = await redis.get(f"exp:{experiment_id}")
    return json.loads(data) if data else None


async def set_experiment_cache(redis: Redis, experiment_id: str, data: dict, ttl: int = 300):
    await redis.setex(f"exp:{experiment_id}", ttl, json.dumps(data))


async def invalidate_experiment_cache(redis: Redis, experiment_id: str):
    await redis.delete(f"exp:{experiment_id}")


# Assignment cache 

async def get_assignment_cache(redis: Redis, experiment_id: str, user_id: str) -> str | None:
    return await redis.get(f"assign:{experiment_id}:{user_id}")


async def set_assignment_cache(
    redis: Redis,
    experiment_id: str,
    user_id: str,
    variant_name: str,
    ttl: int = 3600,
):
    await redis.setex(f"assign:{experiment_id}:{user_id}", ttl, variant_name)
