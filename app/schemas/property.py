import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.property import PropertyType


class PropertyBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str | None = Field(None, max_length=5000)
    property_type: PropertyType = PropertyType.apartment
    address: str = Field(..., min_length=5, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    max_guests: int = Field(..., ge=1, le=50)
    bedrooms: int = Field(..., ge=0, le=50)
    bathrooms: int = Field(..., ge=1, le=50)
    price_per_night: Decimal = Field(..., gt=0, decimal_places=2)


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    title: str | None = Field(None, min_length=5, max_length=255)
    description: str | None = None
    price_per_night: Decimal | None = Field(None, gt=0, decimal_places=2)
    max_guests: int | None = Field(None, ge=1, le=50)
    is_active: bool | None = None


class PropertyPublic(PropertyBase):
    id: uuid.UUID
    host_id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PropertyList(BaseModel):
    """Lightweight schema for listing views — excludes description."""
    id: uuid.UUID
    title: str
    city: str
    country: str
    property_type: PropertyType
    price_per_night: Decimal
    max_guests: int
    bedrooms: int
    is_active: bool

    model_config = {"from_attributes": True}
