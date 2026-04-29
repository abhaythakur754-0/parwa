"""
PARWA Customer Schemas

Pydantic models for customer management, identity resolution, and channel linking.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Validators ───────────────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# Simple phone regex - allows various international formats
_PHONE_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")


def _validate_email(email: str) -> str:
    """Validate and normalize email format."""
    if not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


def _validate_phone(phone: str) -> str:
    """Validate and normalize phone format."""
    # Remove spaces, dashes, parentheses for validation
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    if not _PHONE_REGEX.match(cleaned):
        raise ValueError("Invalid phone format")
    return cleaned


# ── Customer Channel Type ────────────────────────────────────────────────────


class ChannelType(str, Enum):
    """Available customer channel types."""

    EMAIL = "email"
    PHONE = "phone"
    SLACK = "slack"
    WEBCHAT = "webchat"


# ── Customer CRUD Schemas ────────────────────────────────────────────────────


class CustomerCreate(BaseModel):
    """Schema for creating a customer."""

    email: Optional[str] = Field(
        default=None,
        max_length=254,
        description="Customer email address",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Customer phone number",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Customer display name",
    )
    external_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="External system identifier",
    )
    metadata_json: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional customer metadata",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_email(v)
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_phone(v)
        return None

    @model_validator(mode="after")
    def require_at_least_one_contact(self) -> "CustomerCreate":
        """Require at least one of email or phone."""
        if not self.email and not self.phone:
            raise ValueError("At least one of email or phone is required")
        return self


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""

    email: Optional[str] = Field(
        default=None,
        max_length=254,
        description="Customer email address",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Customer phone number",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Customer display name",
    )
    external_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="External system identifier",
    )
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional customer metadata",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_email(v)
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_phone(v)
        return None


class CustomerResponse(BaseModel):
    """Schema for customer response."""

    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    external_id: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    company_id: str
    is_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Customer Merge Schemas ───────────────────────────────────────────────────


class CustomerMergeRequest(BaseModel):
    """Schema for merging customer records."""

    primary_customer_id: str = Field(
        ...,
        description="ID of the customer that will be the primary (surviving) record",
    )
    merged_customer_ids: List[str] = Field(
        ...,
        min_length=1,
        description="IDs of customers to merge into the primary",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reason for merging customers",
    )

    @field_validator("merged_customer_ids")
    @classmethod
    def merged_must_not_include_primary(cls, v: List[str], info) -> List[str]:
        primary_id = info.data.get("primary_customer_id")
        if primary_id and primary_id in v:
            raise ValueError(
                "Primary customer cannot be in the merged_customer_ids list"
            )
        if len(v) != len(set(v)):
            raise ValueError("Duplicate customer IDs in merged_customer_ids")
        return v


# ── Identity Resolution Schemas ──────────────────────────────────────────────


class IdentityMatchRequest(BaseModel):
    """Schema for resolving customer identity from multiple identifiers."""

    email: Optional[str] = Field(
        default=None,
        description="Email address to match",
    )
    phone: Optional[str] = Field(
        default=None,
        description="Phone number to match",
    )
    social_id: Optional[str] = Field(
        default=None,
        description="Social media identifier",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_email(v)
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return _validate_phone(v)
        return None

    @model_validator(mode="after")
    def require_at_least_one_identifier(self) -> "IdentityMatchRequest":
        """Require at least one identifier to match."""
        if not self.email and not self.phone and not self.social_id:
            raise ValueError("At least one of email, phone, or social_id is required")
        return self


class IdentityMatchResponse(BaseModel):
    """Schema for identity match result."""

    matched_customer_id: Optional[str] = Field(
        default=None,
        description="ID of the matched customer (None if no match)",
    )
    match_method: str = Field(
        ...,
        description="How the match was found: 'email', 'phone', 'social', 'fuzzy', or 'none'",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the match (0-1)",
    )
    action_taken: str = Field(
        ...,
        description="Action taken: 'linked', 'created', 'merged', or 'none'",
    )


# ── Customer Channel Schemas ─────────────────────────────────────────────────


class CustomerChannelCreate(BaseModel):
    """Schema for linking a communication channel to a customer."""

    customer_id: str = Field(
        ...,
        description="Customer to link the channel to",
    )
    channel_type: ChannelType = Field(
        ...,
        description="Type of communication channel",
    )
    external_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="External identifier for this channel (e.g., phone number, email)",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether this channel has been verified",
    )

    @field_validator("external_id")
    @classmethod
    def external_id_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("external_id cannot be blank")
        return v.strip()


class CustomerChannelResponse(BaseModel):
    """Schema for customer channel response."""

    id: str
    customer_id: str
    channel_type: ChannelType
    external_id: str
    is_verified: bool
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
