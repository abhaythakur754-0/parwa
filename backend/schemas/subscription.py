"""
Pydantic V2 schemas for Subscription.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

class SubscriptionBase(BaseModel):
    """Base fields for Subscription."""
    plan_tier: Literal["mini", "parwa", "parwa_high"]
    status: Literal["active", "past_due", "canceled", "trialing"]
    amount_cents: int = Field(gt=0, description="Amount must be positive.")
    currency: str = "usd"

class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a Subscription."""
    company_id: UUID
    current_period_start: datetime
    current_period_end: datetime

class SubscriptionUpdate(BaseModel):
    """Schema for updating a Subscription."""
    status: Optional[Literal["active", "past_due", "canceled", "trialing"]] = None
    current_period_end: Optional[datetime] = None

class SubscriptionResponse(SubscriptionBase):
    """Schema for returning a Subscription in API responses."""
    id: UUID
    company_id: UUID
    stripe_subscription_id: Optional[str] = None
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
