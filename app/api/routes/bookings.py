import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingPublic, BookingWithDetails
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", response_model=BookingPublic, status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a booking. Automatically:
    - Validates property capacity against num_guests
    - Checks date-range availability (prevents double-booking)
    - Calculates total price = price_per_night × nights
    """
    booking = await booking_service.create_booking(db, data, guest_id=current_user.id)
    return booking


@router.get("/me", response_model=list[BookingPublic])
async def my_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all bookings for the authenticated user."""
    return await booking_service.get_bookings_for_guest(db, current_user.id, skip, limit)


@router.get("/{booking_id}", response_model=BookingWithDetails)
async def get_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = await booking_service.get_booking_by_id(db, booking_id, with_details=True)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.guest_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingPublic)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a pending or confirmed booking. Only the guest can cancel their own booking."""
    booking = await booking_service.get_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return await booking_service.cancel_booking(db, booking, requesting_user_id=current_user.id)
