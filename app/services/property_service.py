import hashlib
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_delete, cache_delete_pattern, cache_get, cache_set
from app.models.property import Property
from app.schemas.property import PropertyList, PropertyPublic

CACHE_TTL = 300


def _list_cache_key(city, country, max_price, min_guests, skip, limit) -> str:
    raw = f"{city}:{country}:{max_price}:{min_guests}:{skip}:{limit}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"properties:list:{digest}"


def _detail_cache_key(property_id: uuid.UUID) -> str:
    return f"properties:detail:{property_id}"


async def get_properties_cached(
    db: AsyncSession,
    redis: aioredis.Redis,
    city=None, country=None, max_price=None,
    min_guests=None, skip=0, limit=20,
) -> list[dict]:
    cache_key = _list_cache_key(city, country, max_price, min_guests, skip, limit)

    cached = await cache_get(redis, cache_key)
    if cached is not None:
        print(f"[CACHE HIT] {cache_key}")
        return cached

    print(f"[CACHE MISS] {cache_key} — querying Postgres")
    query = select(Property).where(Property.is_active == True)

    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
    if country:
        query = query.where(Property.country.ilike(f"%{country}%"))
    if max_price:
        query = query.where(Property.price_per_night <= max_price)
    if min_guests:
        query = query.where(Property.max_guests >= min_guests)

    query = query.offset(skip).limit(limit).order_by(Property.created_at.desc())
    result = await db.execute(query)
    properties = list(result.scalars().all())

    serialised = [
        PropertyList.model_validate(p).model_dump(mode="json") for p in properties
    ]

    await cache_set(redis, cache_key, serialised, ttl=CACHE_TTL)
    return serialised


async def get_property_cached(
    db: AsyncSession, redis: aioredis.Redis, property_id: uuid.UUID
) -> dict | None:
    cache_key = _detail_cache_key(property_id)

    cached = await cache_get(redis, cache_key)
    if cached is not None:
        print(f"[CACHE HIT] {cache_key}")
        return cached

    print(f"[CACHE MISS] {cache_key} — querying Postgres")
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        return None

    serialised = PropertyPublic.model_validate(prop).model_dump(mode="json")
    await cache_set(redis, cache_key, serialised, ttl=CACHE_TTL)
    return serialised


async def invalidate_property_cache(
    redis: aioredis.Redis, property_id: uuid.UUID | None = None
) -> None:
    deleted = await cache_delete_pattern(redis, "properties:list:*")
    print(f"[CACHE INVALIDATE] Cleared {deleted} list cache keys")
    if property_id:
        await cache_delete(redis, _detail_cache_key(property_id))
        print(f"[CACHE INVALIDATE] Cleared detail cache for {property_id}")
