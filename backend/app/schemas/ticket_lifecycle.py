"""
PARWA Ticket Lifecycle Schemas

Pydantic v2 models for ticket lifecycle, incident, and spam endpoint responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Ticket Lifecycle Response Schemas ─────────────────────────────────────


class TicketEscalateResponse(BaseModel):
    """Response after escalating a ticket."""

    success: bool = Field(description="Whether the escalation was successful")
    ticket_id: str = Field(description="ID of the escalated ticket")
    new_status: str = Field(description="New ticket status after escalation")
    escalated: bool = Field(default=True, description="Whether the ticket was escalated")


class TicketReopenResponse(BaseModel):
    """Response after reopening a ticket."""

    success: bool = Field(description="Whether the reopen was successful")
    ticket_id: str = Field(description="ID of the reopened ticket")
    new_status: str = Field(description="New ticket status after reopen")
    reopen_count: int = Field(description="Total number of times this ticket has been reopened")


class TicketFreezeResponse(BaseModel):
    """Response after freezing a ticket."""

    success: bool = Field(description="Whether the freeze was successful")
    ticket_id: str = Field(description="ID of the frozen ticket")
    status: str = Field(description="Current ticket status")


class TicketThawResponse(BaseModel):
    """Response after thawing a ticket."""

    success: bool = Field(description="Whether the thaw was successful")
    ticket_id: str = Field(description="ID of the thawed ticket")
    status: str = Field(description="Current ticket status")


class TicketSpamMarkResponse(BaseModel):
    """Response after marking a ticket as spam."""

    success: bool = Field(description="Whether the operation was successful")
    ticket_id: str = Field(description="ID of the ticket")
    is_spam: bool = Field(description="Current spam status")
    status: str = Field(description="Current ticket status")


class TicketSpamUnmarkResponse(BaseModel):
    """Response after removing spam marking from a ticket."""

    success: bool = Field(description="Whether the operation was successful")
    ticket_id: str = Field(description="ID of the ticket")
    is_spam: bool = Field(description="Current spam status")
    status: str = Field(description="Current ticket status")


class TicketTransitionsResponse(BaseModel):
    """Response for valid ticket status transitions."""

    ticket_id: str = Field(description="ID of the ticket")
    current_status: str = Field(description="Current ticket status")
    valid_transitions: List[str] = Field(
        default_factory=list,
        description="List of valid status transitions",
    )


class StaleTicketsResponse(BaseModel):
    """Response for stale tickets listing."""

    tickets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of stale tickets",
    )
    total: int = Field(description="Total number of stale tickets")
    statistics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Stale ticket statistics",
    )


# ── Incident Response Schemas ─────────────────────────────────────────────


class IncidentResponse(BaseModel):
    """Response for incident operations."""

    id: Optional[str] = Field(default=None, description="Incident ID")
    title: Optional[str] = Field(default=None, description="Incident title")
    description: Optional[str] = Field(default=None, description="Incident description")
    severity: Optional[str] = Field(default=None, description="Severity level")
    status: Optional[str] = Field(default=None, description="Incident status")
    affected_services: Optional[List[str]] = Field(default=None, description="Affected services")
    master_ticket_id: Optional[str] = Field(default=None, description="Master ticket ID")
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    resolution_summary: Optional[str] = Field(default=None, description="Resolution summary")
    created_at: Optional[Any] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[Any] = Field(default=None, description="Last update timestamp")

    model_config = {"from_attributes": True, "extra": "allow"}


class IncidentDetailResponse(BaseModel):
    """Response for incident detail with linked tickets."""

    id: Optional[str] = Field(default=None, description="Incident ID")
    title: Optional[str] = Field(default=None, description="Incident title")
    description: Optional[str] = Field(default=None, description="Incident description")
    severity: Optional[str] = Field(default=None, description="Severity level")
    status: Optional[str] = Field(default=None, description="Incident status")
    affected_services: Optional[List[str]] = Field(default=None, description="Affected services")
    master_ticket_id: Optional[str] = Field(default=None, description="Master ticket ID")
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    resolution_summary: Optional[str] = Field(default=None, description="Resolution summary")
    created_at: Optional[Any] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[Any] = Field(default=None, description="Last update timestamp")
    linked_tickets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of linked tickets",
    )

    model_config = {"from_attributes": True, "extra": "allow"}


class IncidentListResponse(BaseModel):
    """Response for listing incidents."""

    incidents: List[Any] = Field(default_factory=list, description="List of incidents")
    banner: Optional[Dict[str, Any]] = Field(default=None, description="Incident banner info")
    statistics: Optional[Dict[str, Any]] = Field(default=None, description="Incident statistics")


class IncidentNotifyResponse(BaseModel):
    """Response after notifying incident customers."""

    notified_count: Optional[int] = Field(default=None, description="Number of customers notified")
    message: Optional[str] = Field(default=None, description="Notification result message")

    model_config = {"extra": "allow"}


# ── Spam Queue Response Schemas ───────────────────────────────────────────


class SpamQueueItem(BaseModel):
    """Single spam queue item."""

    id: str = Field(description="Ticket ID")
    subject: Optional[str] = Field(default=None, description="Ticket subject")
    spam_score: Optional[float] = Field(default=None, description="Spam score")
    is_spam: bool = Field(description="Whether marked as spam")
    status: Optional[str] = Field(default=None, description="Ticket status")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")


class SpamQueueResponse(BaseModel):
    """Response for spam queue listing."""

    tickets: List[SpamQueueItem] = Field(default_factory=list, description="List of spam tickets")
    total: int = Field(description="Total number of spam tickets")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Spam statistics")


class SpamAnalyzeResponse(BaseModel):
    """Response for spam analysis of content."""

    is_spam: Optional[bool] = Field(default=None, description="Whether content is spam")
    spam_score: Optional[float] = Field(default=None, description="Spam confidence score")
    reasons: Optional[List[str]] = Field(default=None, description="Reasons for spam classification")

    model_config = {"extra": "allow"}
