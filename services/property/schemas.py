import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from services.property.models import PropertyType

class PropertyCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str | None = None
    property_type: PropertyType = PropertyType.apartment
    address: str = Field(..., min_length=5)
    city: str
    country: str
    max_guests: int = Field(..., ge=1)
    bedrooms: int = Field(..., ge=0)
    bathrooms: int = Field(..., ge=1)
    price_per_night: Decimal = Field(..., gt=0)

class PropertyPublic(PropertyCreate):
    id: uuid.UUID
    host_id: uuid.UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class PropertyList(BaseModel):
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
