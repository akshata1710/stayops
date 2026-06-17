import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from jose import jwt, JWTError
from services.booking.db import get_db
from services.booking.models import Booking, BookingStatus
from services.booking.schemas import BookingCreate, BookingPublic

router = APIRouter(prefix="/bookings", tags=["bookings"])
USER_SERVICE = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
PROPERTY_SERVICE = os.getenv("PROPERTY_SERVICE_URL", "http://localhost:8002")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

async def get_current_user(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{USER_SERVICE}/api/v1/auth/validate/{user_id}")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="User not found")
    return resp.json()

@router.post("/", response_model=BookingPublic, status_code=201)
async def create_booking(
    data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Fetch property from property-service
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{PROPERTY_SERVICE}/api/v1/properties/{data.property_id}")
    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="Property not found")
    property_ = resp.json()

    if data.num_guests > property_["max_guests"]:
        raise HTTPException(status_code=422, detail=f"Max capacity is {property_['max_guests']}")

    # Check availability
    conflict = await db.execute(
        select(Booking).where(and_(
            Booking.property_id == data.property_id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
            Booking.check_in < data.check_out,
            Booking.check_out > data.check_in,
        ))
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Property not available for selected dates")

    nights = (data.check_out - data.check_in).days
    total_price = float(property_["price_per_night"]) * nights

    booking = Booking(
        property_id=data.property_id,
        guest_id=uuid.UUID(current_user["id"]),
        check_in=data.check_in,
        check_out=data.check_out,
        num_guests=data.num_guests,
        guest_notes=data.guest_notes,
        total_price=total_price,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking

@router.get("/me", response_model=list[BookingPublic])
async def my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Booking)
        .where(Booking.guest_id == uuid.UUID(current_user["id"]))
        .order_by(Booking.created_at.desc())
    )
    return list(result.scalars().all())

@router.post("/{booking_id}/cancel", response_model=BookingPublic)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.guest_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking.status not in (BookingStatus.pending, BookingStatus.confirmed):
        raise HTTPException(status_code=422, detail="Cannot cancel this booking")
    booking.status = BookingStatus.cancelled
    await db.flush()
    await db.refresh(booking)
    return booking

@router.get("/{booking_id}", response_model=BookingPublic)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.guest_id) != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your booking")
    return booking
