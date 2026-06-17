import hashlib
import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from services.property.db import get_db, get_redis
from services.property.models import Property
from services.property.schemas import PropertyCreate, PropertyList, PropertyPublic, PropertyCreate as PropertyUpdate

router = APIRouter(prefix="/properties", tags=["properties"])
USER_SERVICE = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
CACHE_TTL = 300

async def get_current_user(authorization: str = Header(...)):
    """Decode JWT and validate user via user-service."""
    import os
    from jose import jwt, JWTError
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY", "change-me-in-production"), algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{USER_SERVICE}/api/v1/auth/validate/{user_id}")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="User not found")
    return resp.json()

def _cache_key(city, country, max_price, min_guests, skip, limit):
    raw = f"{city}:{country}:{max_price}:{min_guests}:{skip}:{limit}"
    return f"properties:list:{hashlib.md5(raw.encode()).hexdigest()[:12]}"

@router.post("/", response_model=PropertyPublic, status_code=201)
async def create_property(
    data: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("host", "admin"):
        raise HTTPException(status_code=403, detail="Host role required")
    prop = Property(**data.model_dump(), host_id=uuid.UUID(current_user["id"]))
    db.add(prop)
    await db.flush()
    await db.refresh(prop)
    redis = await get_redis()
    keys = await redis.keys("properties:list:*")
    if keys:
        await redis.delete(*keys)
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
):
    cache_key = _cache_key(city, country, max_price, min_guests, skip, limit)
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        print(f"[CACHE HIT] {cache_key}")
        return json.loads(cached)
    print(f"[CACHE MISS] {cache_key}")
    query = select(Property).where(Property.is_active == True)
    if city: query = query.where(Property.city.ilike(f"%{city}%"))
    if country: query = query.where(Property.country.ilike(f"%{country}%"))
    if max_price: query = query.where(Property.price_per_night <= max_price)
    if min_guests: query = query.where(Property.max_guests >= min_guests)
    query = query.offset(skip).limit(limit).order_by(Property.created_at.desc())
    result = await db.execute(query)
    props = list(result.scalars().all())
    serialised = [PropertyList.model_validate(p).model_dump(mode="json") for p in props]
    await redis.set(cache_key, json.dumps(serialised, default=str), ex=CACHE_TTL)
    return serialised

@router.get("/{property_id}", response_model=PropertyPublic)
async def get_property(property_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop
