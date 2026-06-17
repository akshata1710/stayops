import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator
from services.booking.models import BookingStatus

class BookingCreate(BaseModel):
    property_id: uuid.UUID
    check_in: date
    check_out: date
    num_guests: int = Field(..., ge=1)
    guest_notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self

class BookingPublic(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    guest_id: uuid.UUID
    check_in: date
    check_out: date
    total_price: Decimal
    num_guests: int
    status: BookingStatus
    created_at: datetime
    model_config = {"from_attributes": True}
