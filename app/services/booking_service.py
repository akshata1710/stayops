import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from app.models.property import Property
from app.schemas.booking import BookingCreate, BookingUpdate


async def check_availability(
    db: AsyncSession,
    property_id: uuid.UUID,
    check_in: date,
    check_out: date,
    exclude_booking_id: uuid.UUID | None = None,
) -> bool:
    """
    Returns True if the property is available for the given date range.

    Uses the overlap formula: existing.check_in < new.check_out AND
    existing.check_out > new.check_in — catches all overlap cases.
    """
    query = select(Booking).where(
        and_(
            Booking.property_id == property_id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        )
    )
    if exclude_booking_id:
        query = query.where(Booking.id != exclude_booking_id)

    result = await db.execute(query)
    conflicting = result.scalar_one_or_none()
    return conflicting is None


async def create_booking(
    db: AsyncSession, data: BookingCreate, guest_id: uuid.UUID
) -> Booking:
    # Fetch the property — validate it exists and is active
    result = await db.execute(
        select(Property).where(
            Property.id == data.property_id, Property.is_active == True
        )
    )
    property_ = result.scalar_one_or_none()
    if not property_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or unavailable",
        )

    # Capacity check
    if data.num_guests > property_.max_guests:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Property max capacity is {property_.max_guests} guests",
        )

    # Availability check — prevents double-booking
    available = await check_availability(
        db, data.property_id, data.check_in, data.check_out
    )
    if not available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Property is not available for the selected dates",
        )

    # Calculate total price
    nights = (data.check_out - data.check_in).days
    total_price = float(property_.price_per_night) * nights

    booking = Booking(
        property_id=data.property_id,
        guest_id=guest_id,
        check_in=data.check_in,
        check_out=data.check_out,
        num_guests=data.num_guests,
        guest_notes=data.guest_notes,
        total_price=total_price,
        status=BookingStatus.pending,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


async def get_booking_by_id(
    db: AsyncSession, booking_id: uuid.UUID, with_details: bool = False
) -> Booking | None:
    query = select(Booking).where(Booking.id == booking_id)
    if with_details:
        query = query.options(
            selectinload(Booking.property), selectinload(Booking.guest)
        )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_bookings_for_guest(
    db: AsyncSession, guest_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> list[Booking]:
    result = await db.execute(
        select(Booking)
        .where(Booking.guest_id == guest_id)
        .offset(skip)
        .limit(limit)
        .order_by(Booking.created_at.desc())
    )
    return list(result.scalars().all())


async def cancel_booking(
    db: AsyncSession, booking: Booking, requesting_user_id: uuid.UUID
) -> Booking:
    if booking.guest_id != requesting_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own bookings",
        )
    if booking.status not in (BookingStatus.pending, BookingStatus.confirmed):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot cancel a booking with status '{booking.status}'",
        )
    booking.status = BookingStatus.cancelled
    await db.flush()
    await db.refresh(booking)
    return booking
