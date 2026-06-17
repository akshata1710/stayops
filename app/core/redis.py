import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def cache_get(redis: aioredis.Redis, key: str) -> Any | None:
    value = await redis.get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(redis: aioredis.Redis, key: str, value: Any, ttl: int = 300) -> None:
    await redis.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(redis: aioredis.Redis, key: str) -> None:
    await redis.delete(key)


async def cache_delete_pattern(redis: aioredis.Redis, pattern: str) -> int:
    keys = await redis.keys(pattern)
    if keys:
        return await redis.delete(*keys)
    return 0
