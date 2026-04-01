"""
PARWA Auth Schemas (F-010, F-011, F-013)

Pydantic models for authentication request/response validation.
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Shared Validators ──────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def _validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


# ── Request Schemas ────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Registration request — creates company + owner user."""

    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    industry: str = Field(min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """BC-011: Minimum 8 chars with complexity check."""
        if not re.search(r"[A-Z]", v):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )
        if not re.search(r"[a-z]", v):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )
        if not re.search(r"\d", v):
            raise ValueError(
                "Password must contain at least one digit"
            )
        return v


class LoginRequest(BaseModel):
    """Login request — email + password."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    """Google OAuth sign-in request."""

    id_token: str = Field(min_length=1)


# ── Response Schemas ───────────────────────────────────────────────


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    company_id: str
    company_name: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Combined login/register response: user + tokens."""

    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
