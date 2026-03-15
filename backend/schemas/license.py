"""
Pydantic V2 schemas for License.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

class LicenseBase(BaseModel):
    """Base fields for License."""
    license_key: str
    tier: Literal["mini", "parwa", "parwa_high"]
    status: Literal["active", "suspended", "expired"]
    max_seats: int = 1

class LicenseCreate(LicenseBase):
    """Schema for creating a License."""
    company_id: UUID

class LicenseUpdate(BaseModel):
    """Schema for updating a License."""
    tier: Optional[Literal["mini", "parwa", "parwa_high"]] = None
    status: Optional[Literal["active", "suspended", "expired"]] = None
    max_seats: Optional[int] = None

class LicenseResponse(LicenseBase):
    """Schema for returning a License in API responses."""
    id: UUID
    company_id: UUID
    issued_at: datetime
    expires_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
