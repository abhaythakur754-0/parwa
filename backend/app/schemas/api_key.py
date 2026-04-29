"""
PARWA API Key Schemas (F-019)

Pydantic models for API key CRUD request/response validation.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(min_length=1, max_length=255)
    scopes: List[str] = Field(min_length=1)
    expires_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
    )


class APIKeyResponse(BaseModel):
    """API key info (never includes raw key or hash)."""

    id: str
    name: str
    key_prefix: str
    scopes: List[str] = []
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    revoked: bool = False


class APIKeyCreatedResponse(BaseModel):
    """Response when a new key is created (includes raw key)."""

    key: str
    api_key: APIKeyResponse


class APIKeyRotatedResponse(BaseModel):
    """Response when a key is rotated."""

    key: str
    old_key_id: str
    grace_period_ends: Optional[str] = None
    api_key: APIKeyResponse


class APIKeyRevokedResponse(BaseModel):
    """Response when a key is revoked."""

    status: str
    key_id: str
