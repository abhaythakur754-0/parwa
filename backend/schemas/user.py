from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from backend.models.user import RoleEnum


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="The user's email address")
    role: RoleEnum = Field(..., description="The role of the user")
    is_active: bool = Field(default=True, description="Whether the user account is active")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="The user's password (must be at least 8 characters)")
    company_id: uuid.UUID = Field(..., description="The ID of the company this user belongs to")


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
