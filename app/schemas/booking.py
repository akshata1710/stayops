import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from app.models.booking import BookingStatus
from app.schemas.property import PropertyList
from app.schemas.user import UserPublic


class BookingBase(BaseModel):
    check_in: date
    check_out: date
    num_guests: int = Field(..., ge=1, le=50)
    guest_notes: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> "BookingBase":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if (self.check_out - self.check_in).days < 1:
            raise ValueError("Minimum stay is 1 night")
        return self


class BookingCreate(BookingBase):
    property_id: uuid.UUID


class BookingUpdate(BaseModel):
    status: BookingStatus | None = None
    guest_notes: str | None = Field(None, max_length=1000)


class BookingPublic(BookingBase):
    id: uuid.UUID
    property_id: uuid.UUID
    guest_id: uuid.UUID
    total_price: Decimal
    status: BookingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingWithDetails(BookingPublic):
    """Extended response that includes nested property and guest info."""
    property: PropertyList
    guest: UserPublic
