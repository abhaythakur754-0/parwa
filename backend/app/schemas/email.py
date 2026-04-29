"""
PARWA Email Auth Schemas (F-012, F-014)

Pydantic models for email verification and password reset.
"""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


class ResendVerificationRequest(BaseModel):
    """Request to resend verification email.

    F-012: Rate limited to 3 per email per hour.
    """

    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset.

    F-014: Generic response to prevent account enumeration.
    Rate limited to 3 per email per hour.
    """

    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token.

    F-014: Token is single-use, 15-min expiry.
    New password must meet Day 7 strength requirements.
    """

    token: str = Field(min_length=32, max_length=64)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Same strength rules as Day 7 registration."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one " "uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one " "lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one " "special character")
        return v

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ResetPasswordRequest":
        """Confirm password must match."""
        if self.new_password != self.confirm_password:
            raise ValueError("Password and confirm_password do not match")
        return self
