"""
PARWA Admin Panel Schemas (F06)

Pydantic models for admin panel, company settings, team management,
and API provider CRUD request/response validation.

BC-002: Money fields use Numeric, never float.
BC-011: Password validators (L02) enforced.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


# ── Enums ──────────────────────────────────────────────────────────


class OOOStatus(str, Enum):
    inactive = "inactive"
    active = "active"
    scheduled = "scheduled"


class TeamRole(str, Enum):
    owner = "owner"
    admin = "admin"
    agent = "agent"
    viewer = "viewer"


# ── Company Profile ────────────────────────────────────────────────


class CompanyProfileResponse(BaseModel):
    id: str
    name: str
    industry: str
    subscription_tier: str
    subscription_status: str
    mode: str
    paddle_customer_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanyProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, min_length=1, max_length=50)
    mode: Optional[str] = Field(None, min_length=1, max_length=50)


# ── Company Settings ───────────────────────────────────────────────


class CompanySettingsResponse(BaseModel):
    id: str
    company_id: str
    ooo_status: str
    ooo_message: Optional[str] = None
    ooo_until: Optional[str] = None
    brand_voice: Optional[str] = None
    tone_guidelines: Optional[str] = None
    prohibited_phrases: List[str] = []
    pii_patterns: List[str] = []
    custom_regex: List[str] = []
    top_k: int = 5
    similarity_threshold: float = 0.70
    rerank_model: Optional[str] = None
    confidence_thresholds: Dict[str, Any] = {}
    intent_labels: List[str] = []
    custom_rules: List[str] = []
    assignment_rules: List[str] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanySettingsUpdate(BaseModel):
    ooo_status: Optional[OOOStatus] = None
    ooo_message: Optional[str] = Field(None, max_length=5000)
    ooo_until: Optional[datetime] = None
    brand_voice: Optional[str] = Field(None, max_length=10000)
    tone_guidelines: Optional[str] = Field(None, max_length=10000)
    prohibited_phrases: Optional[List[str]] = Field(None, max_length=100)
    pii_patterns: Optional[List[str]] = Field(None, max_length=100)
    custom_regex: Optional[List[str]] = Field(None, max_length=100)
    top_k: Optional[int] = Field(None, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(None, ge=0, le=1)
    rerank_model: Optional[str] = Field(None, max_length=255)
    confidence_thresholds: Optional[Dict[str, Any]] = None
    intent_labels: Optional[List[str]] = Field(None, max_length=200)
    custom_rules: Optional[List[str]] = Field(None, max_length=200)
    assignment_rules: Optional[List[str]] = Field(None, max_length=200)


# ── Team Member ────────────────────────────────────────────────────


class TeamMemberResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamMemberUpdate(BaseModel):
    role: Optional[TeamRole] = None
    is_active: Optional[bool] = None


# ── Password Change ────────────────────────────────────────────────


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """L02: uppercase, lowercase, digit, special char."""
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


# ── API Provider ───────────────────────────────────────────────────


class APIProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    description: Optional[str] = None
    required_fields: List[str] = []
    optional_fields: List[str] = []
    default_endpoint: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class APIProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: str = Field(min_length=1, max_length=50)
    description: Optional[str] = None
    required_fields: Optional[List[str]] = None
    optional_fields: Optional[List[str]] = None
    default_endpoint: Optional[str] = None


class APIProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_type: Optional[str] = Field(
        None, min_length=1, max_length=50,
    )
    description: Optional[str] = None
    required_fields: Optional[List[str]] = None
    optional_fields: Optional[List[str]] = None
    default_endpoint: Optional[str] = None
    is_active: Optional[bool] = None


# ── Admin Client ───────────────────────────────────────────────────


class AdminClientResponse(BaseModel):
    id: str
    name: str
    industry: str
    subscription_tier: str
    subscription_status: str
    mode: str
    paddle_customer_id: Optional[str] = None
    paddle_subscription_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    user_count: int = 0

    model_config = {"from_attributes": True}


class SubscriptionTier(str, Enum):
    starter = "starter"
    growth = "growth"
    high_volume = "high_volume"
    enterprise = "enterprise"


class SubscriptionStatus(str, Enum):
    active = "active"
    paused = "paused"
    cancelled = "cancelled"
    past_due = "past_due"
    trial = "trial"


class AdminClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    industry: Optional[str] = Field(None, min_length=1, max_length=50)
    subscription_tier: Optional[SubscriptionTier] = None
    subscription_status: Optional[SubscriptionStatus] = None
    mode: Optional[str] = Field(None, min_length=1, max_length=50)


# ── Pagination ─────────────────────────────────────────────────────


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int


# ── Message ────────────────────────────────────────────────────────


class SubscriptionUpdateRequest(BaseModel):
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None


class MessageResponse(BaseModel):
    message: str
