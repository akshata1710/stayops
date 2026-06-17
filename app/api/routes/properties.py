import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_host
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.property import Property
from app.models.user import User
from app.schemas.property import PropertyCreate, PropertyList, PropertyPublic, PropertyUpdate
from app.services.property_service import (
    get_properties_cached,
    get_property_cached,
    invalidate_property_cache,
)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("/", response_model=PropertyPublic, status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(require_host),
):
    prop = Property(**data.model_dump(), host_id=current_user.id)
    db.add(prop)
    await db.flush()
    await db.refresh(prop)
    await invalidate_property_cache(redis)
    return prop


@router.get("/", response_model=list[PropertyList])
async def list_properties(
    city: str | None = Query(None),
    country: str | None = Query(None),
    max_price: float | None = Query(None, gt=0),
    min_guests: int | None = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await get_properties_cached(
        db, redis, city, country, max_price, min_guests, skip, limit
    )


@router.get("/{property_id}", response_model=PropertyPublic)
async def get_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    prop = await get_property_cached(db, redis, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


@router.patch("/{property_id}", response_model=PropertyPublic)
async def update_property(
    property_id: uuid.UUID,
    data: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(require_host),
):
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    if prop.host_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your property")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)
    await db.flush()
    await db.refresh(prop)
    await invalidate_property_cache(redis, property_id=property_id)
    return prop
