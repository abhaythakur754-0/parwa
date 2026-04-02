"""
PARWA Phone OTP Schemas (C5)

Pydantic models for phone OTP request/response validation.
"""

from typing import Optional

from pydantic import BaseModel, Field


class SendOTPRequest(BaseModel):
    """Request to send an OTP to a phone number."""

    phone: str = Field(
        min_length=8, max_length=20,
        pattern=r'^\+\d{8,15}$',
    )
    company_id: str = Field(
        min_length=1, max_length=36,
    )


class VerifyOTPRequest(BaseModel):
    """Request to verify a phone OTP code."""

    phone: str = Field(
        min_length=8, max_length=20,
        pattern=r'^\+\d{8,15}$',
    )
    code: str = Field(min_length=6, max_length=6)
    company_id: str = Field(
        min_length=1, max_length=36,
    )


class SendOTPResponse(BaseModel):
    """Response after sending OTP."""

    message: str
    expires_in: int


class VerifyOTPResponse(BaseModel):
    """Response after verifying OTP."""

    status: str
    message: str
    attempts_remaining: Optional[int] = None
