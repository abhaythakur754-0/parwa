"""
PARWA Auth Schemas (F-010, F-011, F-013)

Pydantic models for authentication request/response validation.
- L01: confirm_password field
- L02: special character requirement
- L03: password strength meter
- L08: is_new_user flag in response
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Shared Validators ──────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def _validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


# ── Password Strength Scoring (L03) ──────────────────────────────


def get_password_strength(password: str) -> str:
    """Score password strength: weak, fair, strong, very strong.

    F-010 spec: password strength meter.
    """
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password):
        score += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1
    if len(password) >= 16:
        score += 1

    if score <= 2:
        return "weak"
    elif score <= 5:
        return "fair"
    elif score == 6:
        return "strong"
    return "very strong"


# ── Request Schemas ────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Registration request — creates company + owner user.

    L01: confirm_password must match password.
    L02: Password must include special character.
    """

    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
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
        """BC-011: Min 8 chars + uppercase + lowercase + digit
        + special char (L02)."""
        if not re.search(r"[A-Z]", v):
            raise ValueError(
                "Password must contain at least one "
                "uppercase letter"
            )
        if not re.search(r"[a-z]", v):
            raise ValueError(
                "Password must contain at least one "
                "lowercase letter"
            )
        if not re.search(r"\d", v):
            raise ValueError(
                "Password must contain at least one digit"
            )
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError(
                "Password must contain at least one "
                "special character"
            )
        return v

    @model_validator(mode="after")
    def passwords_must_match(self) -> "RegisterRequest":
        """L01: confirm_password must match password."""
        if self.password != self.confirm_password:
            raise ValueError(
                "Password and confirm_password do not match"
            )
        return self


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
    """Combined login/register response: user + tokens.

    L08: is_new_user flag for Google OAuth flow.
    """

    user: UserResponse
    tokens: TokenResponse
    is_new_user: bool = False


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class EmailCheckResponse(BaseModel):
    """L04: Email availability check response."""

    email: str
    available: bool
