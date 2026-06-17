import uuid, enum
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from services.booking.db import Base

class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"

class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_property_dates", "property_id", "check_in", "check_out"),
        CheckConstraint("check_out > check_in", name="ck_bookings_dates"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    num_guests: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), nullable=False, default=BookingStatus.pending)
    guest_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
