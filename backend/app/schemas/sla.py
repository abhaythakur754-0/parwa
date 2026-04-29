"""
PARWA SLA Schemas

Pydantic models for SLA (Service Level Agreement) management.
- SLA Policy CRUD operations
- SLA Timer tracking for tickets
- SLA Breach notifications
- SLA Statistics
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, computed_field, model_validator

# ── Enums ────────────────────────────────────────────────────────────


class Priority(str, Enum):
    """Ticket priority levels for SLA."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class PlanTier(str, Enum):
    """Subscription plan tiers for SLA."""

    starter = "mini_parwa"
    growth = "parwa"
    high = "high"


class BreachType(str, Enum):
    """Types of SLA breaches."""

    first_response = "first_response"
    resolution = "resolution"


# ── SLA Policy Schemas ───────────────────────────────────────────────


class SLAPolicyBase(BaseModel):
    """Base schema for SLA policy with shared fields."""

    plan_tier: PlanTier = Field(..., description="Subscription plan tier")
    priority: Priority = Field(..., description="Ticket priority level")
    first_response_minutes: int = Field(
        ..., gt=0, description="Maximum minutes for first response"
    )
    resolution_minutes: int = Field(
        ..., gt=0, description="Maximum minutes for resolution"
    )
    update_frequency_minutes: int = Field(
        ..., gt=0, description="Required update frequency in minutes"
    )

    @field_validator(
        "first_response_minutes", "resolution_minutes", "update_frequency_minutes"
    )
    @classmethod
    def minutes_must_be_positive(cls, v: int) -> int:
        """Validate that minutes fields are positive integers."""
        if v <= 0:
            raise ValueError("Minutes must be a positive integer")
        return v


class SLAPolicyCreate(SLAPolicyBase):
    """Schema for creating a new SLA policy."""

    is_active: bool = Field(default=True, description="Whether the policy is active")


class SLAPolicyUpdate(BaseModel):
    """Schema for updating an existing SLA policy."""

    plan_tier: Optional[PlanTier] = Field(None, description="Subscription plan tier")
    priority: Optional[Priority] = Field(None, description="Ticket priority level")
    first_response_minutes: Optional[int] = Field(
        None, gt=0, description="Maximum minutes for first response"
    )
    resolution_minutes: Optional[int] = Field(
        None, gt=0, description="Maximum minutes for resolution"
    )
    update_frequency_minutes: Optional[int] = Field(
        None, gt=0, description="Required update frequency in minutes"
    )
    is_active: Optional[bool] = Field(None, description="Whether the policy is active")

    @field_validator(
        "first_response_minutes", "resolution_minutes", "update_frequency_minutes"
    )
    @classmethod
    def minutes_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        """Validate that minutes fields are positive integers if provided."""
        if v is not None and v <= 0:
            raise ValueError("Minutes must be a positive integer")
        return v


class SLAPolicyResponse(SLAPolicyBase):
    """Full SLA policy response schema."""

    id: str = Field(..., description="Unique policy identifier")
    company_id: str = Field(..., description="Company identifier")
    is_active: bool = Field(..., description="Whether the policy is active")
    created_at: datetime = Field(..., description="Policy creation timestamp")
    updated_at: datetime = Field(..., description="Policy last update timestamp")

    model_config = {"from_attributes": True}


# ── SLA Timer Schemas ────────────────────────────────────────────────


class SLATimerResponse(BaseModel):
    """SLA timer tracking for a specific ticket."""

    id: str = Field(..., description="Unique timer identifier")
    ticket_id: str = Field(..., description="Associated ticket identifier")
    policy_id: str = Field(..., description="Associated SLA policy identifier")
    first_response_at: Optional[datetime] = Field(
        None, description="Timestamp of first response"
    )
    resolved_at: Optional[datetime] = Field(None, description="Timestamp of resolution")
    breached_at: Optional[datetime] = Field(
        None, description="Timestamp when SLA was breached"
    )
    is_breached: bool = Field(
        default=False, description="Whether SLA has been breached"
    )
    created_at: datetime = Field(..., description="Timer creation timestamp")
    updated_at: datetime = Field(..., description="Timer last update timestamp")
    resolution_target: Optional[datetime] = Field(
        None, description="Target datetime for resolution"
    )

    @model_validator(mode="after")
    def _ensure_utc_aware(self) -> "SLATimerResponse":
        """Normalize any naive datetimes to UTC-aware to avoid subtraction errors."""

        def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        self.created_at = _to_utc(self.created_at)
        self.updated_at = _to_utc(self.updated_at)
        self.resolution_target = _to_utc(self.resolution_target)
        self.first_response_at = _to_utc(self.first_response_at)
        self.resolved_at = _to_utc(self.resolved_at)
        self.breached_at = _to_utc(self.breached_at)
        return self

    @computed_field
    @property
    def time_remaining_seconds(self) -> Optional[int]:
        """Calculate remaining time in seconds until resolution deadline."""
        if self.resolution_target is None:
            return None
        if self.resolved_at is not None:
            return 0
        now = datetime.now(timezone.utc)
        remaining = (self.resolution_target - now).total_seconds()
        return max(0, int(remaining))

    @computed_field
    @property
    def is_approaching(self) -> bool:
        """Check if SLA is approaching breach (75% threshold)."""
        if self.resolution_target is None or self.resolved_at is not None:
            return False
        if self.created_at is None:
            return False
        now = datetime.now(timezone.utc)
        if now >= self.resolution_target:
            return False

        total_seconds = (self.resolution_target - self.created_at).total_seconds()
        elapsed_seconds = (now - self.created_at).total_seconds()

        if total_seconds <= 0:
            return False

        elapsed_percentage = elapsed_seconds / total_seconds
        return elapsed_percentage >= 0.75

    model_config = {"from_attributes": True}


# ── SLA Breach Alert Schema ───────────────────────────────────────────


class SLABreachAlert(BaseModel):
    """SLA breach notification schema."""

    ticket_id: str = Field(..., description="Associated ticket identifier")
    policy_id: str = Field(..., description="Associated SLA policy identifier")
    breach_type: BreachType = Field(
        ..., description="Type of SLA breach (first_response or resolution)"
    )
    time_elapsed_minutes: int = Field(
        ..., ge=0, description="Minutes elapsed before breach"
    )
    threshold_minutes: int = Field(..., gt=0, description="SLA threshold in minutes")

    model_config = {"from_attributes": True}


# ── SLA Statistics Schema ─────────────────────────────────────────────


class SLAStats(BaseModel):
    """SLA performance statistics."""

    total_tickets: int = Field(
        default=0, ge=0, description="Total number of tickets tracked"
    )
    breached_count: int = Field(
        default=0, ge=0, description="Number of breached SLA tickets"
    )
    approaching_count: int = Field(
        default=0, ge=0, description="Number of tickets approaching SLA breach"
    )
    compliant_count: int = Field(
        default=0, ge=0, description="Number of SLA-compliant tickets"
    )
    avg_first_response_minutes: Optional[float] = Field(
        None, ge=0, description="Average first response time in minutes"
    )
    avg_resolution_minutes: Optional[float] = Field(
        None, ge=0, description="Average resolution time in minutes"
    )

    model_config = {"from_attributes": True}
