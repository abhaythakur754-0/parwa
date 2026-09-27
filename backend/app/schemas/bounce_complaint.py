"""
Bounce & Complaint Schemas — Week 13 Day 3 (F-124)

Pydantic models for bounce/complaint API endpoints and service responses.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Bounce Listing Schemas ──────────────────────────────────────

class BounceListItem(BaseModel):
    """Single bounce event in list response."""

    id: str
    email: str
    type: str = Field(..., description="soft/hard/complaint/unsubscribe")
    reason: Optional[str] = None
    provider: Optional[str] = None
    event_date: Optional[str] = None
    status: Optional[str] = None
    whitelisted: bool = False
    ticket_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class BounceListResponse(BaseModel):
    """Response for GET /api/email/bounces."""

    bounces: List[BounceListItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


# ── Whitelist Schema ────────────────────────────────────────────

class WhitelistRequest(BaseModel):
    """Request to whitelist a bounced email."""

    justification: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Reason for whitelisting this email",
    )


class WhitelistResponse(BaseModel):
    """Response for POST /api/email/bounces/{id}/whitelist."""

    status: str = "whitelisted"
    bounce_id: str
    email: str


# ── Stats Schemas ───────────────────────────────────────────────

class BounceStatsResponse(BaseModel):
    """Response for GET /api/email/bounces/stats."""

    total_bounces: int = 0
    hard_bounces: int = 0
    soft_bounces: int = 0
    complaints: int = 0
    bounce_rate: float = 0.0
    complaint_rate: float = 0.0
    trend: str = Field("stable", description="improving/stable/worsening")
    range_days: int = 7
    suppressed_count: int = 0


# ── Digest Schema ───────────────────────────────────────────────

class DeliverabilityAlertItem(BaseModel):
    """Single deliverability alert."""

    id: str
    alert_type: str
    severity: str
    message: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    created_at: Optional[str] = None
    acknowledged: bool = False


class BounceDigestResponse(BaseModel):
    """Response for GET /api/email/bounces/digest."""

    since_last_digest: Optional[str] = None
    critical_alerts: List[DeliverabilityAlertItem] = []
    summary: dict = Field(default_factory=dict)


# ── Email Status Check Schema ───────────────────────────────────

class EmailStatusCheckResponse(BaseModel):
    """Response for checking if an email can receive messages."""

    email: str
    is_valid: bool = True
    is_complained: bool = False
    can_send: bool = True
    email_status: Optional[str] = None
    hard_bounces: int = 0
    soft_bounces: int = 0
    complaints: int = 0
    delivered: int = 0
    whitelisted: bool = False
