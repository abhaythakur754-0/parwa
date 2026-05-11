"""
PARWA Ticket Schemas (MF01-MF06, F-049-F-052, F-070)

Pydantic v2 models for ticket CRUD request/response validation.

Day 24 (Week 4 Day 1): Full ticket system schema support.
  - MF01: TicketPriority enum (critical/high/medium/low)
  - MF02: TicketCategory enum (tech_support/billing/feature_request/bug_report/general/complaint)
  - MF04: Status change tracking
  - MF06: SLA policy support
  - F-049: AI classification and confidence
  - F-050: Assignment rules
  - F-051: Bulk operations
  - F-052: Channel configuration
  - F-070: Identity matching
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Enums (re-exported from models for convenience) ─────────────────────────


class TicketStatus:
    """Ticket status constants for schema validation."""

    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    AWAITING_CLIENT = "awaiting_client"
    AWAITING_HUMAN = "awaiting_human"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    CLOSED = "closed"
    FROZEN = "frozen"
    QUEUED = "queued"
    STALE = "stale"

    VALID_STATUSES = [
        OPEN, ASSIGNED, IN_PROGRESS, AWAITING_CLIENT, AWAITING_HUMAN,
        RESOLVED, REOPENED, CLOSED, FROZEN, QUEUED, STALE,
    ]

    OPEN_STATUSES = [OPEN, ASSIGNED, IN_PROGRESS, AWAITING_CLIENT,
                     AWAITING_HUMAN, REOPENED, QUEUED]
    RESOLVED_STATUSES = [RESOLVED]
    CLOSED_STATUSES = [CLOSED, FROZEN]


class TicketPriority:
    """Ticket priority constants."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    VALID_PRIORITIES = [CRITICAL, HIGH, MEDIUM, LOW]


class TicketCategory:
    """Ticket category constants."""

    TECH_SUPPORT = "tech_support"
    BILLING = "billing"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    GENERAL = "general"
    COMPLAINT = "complaint"

    VALID_CATEGORIES = [
        TECH_SUPPORT, BILLING, FEATURE_REQUEST, BUG_REPORT, GENERAL, COMPLAINT,
    ]


class AssigneeType:
    """Assignee type constants."""

    AI = "ai"
    HUMAN = "human"
    SYSTEM = "system"

    VALID_TYPES = [AI, HUMAN, SYSTEM]


# ── Base Schema ────────────────────────────────────────────────────────────


class TicketBase(BaseModel):
    """Base schema with shared configuration."""

    model_config = ConfigDict(from_attributes=True)


# ── TicketCreate Schema ─────────────────────────────────────────────────────


class TicketCreate(BaseModel):
    """Request to create a new ticket.

    Fields:
        subject: Optional subject line for the ticket.
        customer_id: ID of the customer creating the ticket.
        channel: Communication channel (email, chat, sms, voice, social).
        priority: Priority level (default: medium).
        category: Classification category (optional).
        tags: List of tags for categorization (default: []).
        metadata_json: Additional metadata as JSON (default: {}).
    """

    subject: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Subject line for the ticket",
    )
    customer_id: str = Field(
        min_length=1,
        max_length=36,
        description="ID of the customer creating the ticket",
    )
    channel: str = Field(
        min_length=1,
        max_length=50,
        description="Communication channel (email, chat, sms, voice, social)",
    )
    priority: str = Field(
        default=TicketPriority.MEDIUM,
        description="Priority level (critical, high, medium, low)",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Classification category",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags for categorization",
    )
    metadata_json: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata as JSON",
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority is one of the allowed values."""
        if v not in TicketPriority.VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority. Must be one of: {TicketPriority.VALID_PRIORITIES}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Validate category is one of the allowed values if provided."""
        if v is not None and v not in TicketCategory.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category. Must be one of: {TicketCategory.VALID_CATEGORIES}"
            )
        return v


# ── TicketUpdate Schema ─────────────────────────────────────────────────────


class TicketUpdate(BaseModel):
    """Request to update ticket fields.

    All fields are optional for partial updates.

    Fields:
        priority: New priority level.
        category: New classification category.
        tags: New list of tags.
        status: New status.
        assigned_to: ID of the new assignee.
        subject: New subject line.
    """

    priority: Optional[str] = Field(
        default=None,
        description="New priority level",
    )
    category: Optional[str] = Field(
        default=None,
        description="New classification category",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New list of tags",
    )
    status: Optional[str] = Field(
        default=None,
        description="New status",
    )
    assigned_to: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the new assignee",
    )
    subject: Optional[str] = Field(
        default=None,
        max_length=255,
        description="New subject line",
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        """Validate priority is one of the allowed values if provided."""
        if v is not None and v not in TicketPriority.VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority. Must be one of: {TicketPriority.VALID_PRIORITIES}"
            )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Validate category is one of the allowed values if provided."""
        if v is not None and v not in TicketCategory.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category. Must be one of: {TicketCategory.VALID_CATEGORIES}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status is one of the allowed values if provided."""
        if v is not None and v not in TicketStatus.VALID_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {TicketStatus.VALID_STATUSES}"
            )
        return v


# ── TicketResponse Schema ──────────────────────────────────────────────────


class TicketResponse(BaseModel):
    """Full ticket response with computed fields.

    Includes all fields from the Ticket model plus computed properties:
        - is_open: Whether the ticket is in an open state
        - is_resolved: Whether the ticket is resolved
        - is_closed: Whether the ticket is closed/frozen
        - time_since_created: Human-readable time since creation
        - time_since_updated: Human-readable time since last update
    """

    model_config = ConfigDict(from_attributes=True)

    # Core fields
    id: str = Field(description="Unique ticket identifier")
    company_id: str = Field(description="Company ID for tenant isolation")
    customer_id: Optional[str] = Field(
        default=None,
        description="ID of the customer",
    )
    channel: str = Field(description="Communication channel")
    status: str = Field(description="Current ticket status")
    subject: Optional[str] = Field(default=None, description="Subject line")
    priority: str = Field(description="Priority level")
    category: Optional[str] = Field(default=None, description="Classification category")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    # Assignment fields
    agent_id: Optional[str] = Field(default=None, description="AI agent ID if assigned")
    assigned_to: Optional[str] = Field(
        default=None,
        description="Human agent ID if assigned",
    )

    # Classification fields
    classification_intent: Optional[str] = Field(
        default=None,
        description="AI-detected intent",
    )
    classification_type: Optional[str] = Field(
        default=None,
        description="Type of classification",
    )

    # Metadata
    metadata_json: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    # State tracking
    reopen_count: int = Field(default=0, description="Number of times reopened")
    frozen: bool = Field(default=False, description="Whether ticket is frozen")
    parent_ticket_id: Optional[str] = Field(
        default=None,
        description="Parent ticket ID for merged tickets",
    )
    duplicate_of_id: Optional[str] = Field(
        default=None,
        description="Original ticket ID if this is a duplicate",
    )
    is_spam: bool = Field(default=False, description="Spam flag")
    awaiting_human: bool = Field(
        default=False,
        description="Flag for AI-to-human handoff",
    )
    awaiting_client: bool = Field(
        default=False,
        description="Waiting for client response",
    )
    escalation_level: int = Field(
        default=1,
        description="Escalation level (L1=1, L2=2, L3=3)",
    )
    sla_breached: bool = Field(default=False, description="SLA breach flag")

    # SLA tracking
    first_response_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of first response",
    )
    resolution_target_at: Optional[datetime] = Field(
        default=None,
        description="SLA resolution target timestamp",
    )
    client_timezone: Optional[str] = Field(
        default=None,
        description="Client timezone for SLA calculations",
    )

    # Plan and variant tracking
    plan_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Plan tier snapshot at creation",
    )
    variant_version: Optional[str] = Field(
        default=None,
        description="AI variant that handled this ticket",
    )

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp",
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        description="Closure timestamp",
    )

    # Computed properties
    is_open: bool = Field(default=False, description="Whether ticket is open")
    is_resolved: bool = Field(default=False, description="Whether ticket is resolved")
    is_closed: bool = Field(default=False, description="Whether ticket is closed")
    time_since_created: Optional[str] = Field(
        default=None,
        description="Human-readable time since creation",
    )
    time_since_updated: Optional[str] = Field(
        default=None,
        description="Human-readable time since last update",
    )

    @model_validator(mode="after")
    def compute_fields(self) -> "TicketResponse":
        """Compute derived fields based on status and timestamps."""
        # Compute status-based fields
        self.is_open = self.status in TicketStatus.OPEN_STATUSES
        self.is_resolved = self.status in TicketStatus.RESOLVED_STATUSES
        self.is_closed = self.status in TicketStatus.CLOSED_STATUSES

        # Compute time deltas
        now = datetime.now(timezone.utc)

        if self.created_at:
            self.time_since_created = self._format_timedelta(now - self.created_at)

        if self.updated_at:
            self.time_since_updated = self._format_timedelta(now - self.updated_at)

        return self

    @staticmethod
    def _format_timedelta(delta: timedelta) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h"
        elif total_seconds < 604800:
            days = total_seconds // 86400
            return f"{days}d"
        elif total_seconds < 2592000:
            weeks = total_seconds // 604800
            return f"{weeks}w"
        else:
            months = total_seconds // 2592000
            return f"{months}mo"


# ── TicketListResponse Schema ──────────────────────────────────────────────


class TicketListResponse(BaseModel):
    """Paginated list of tickets.

    Fields:
        items: List of ticket responses.
        total: Total number of matching records.
        page: Current page number (1-based).
        page_size: Number of items per page.
        pages: Total number of pages.
    """

    items: List[TicketResponse] = Field(
        default_factory=list,
        description="List of ticket responses",
    )
    total: int = Field(default=0, description="Total number of matching records")
    page: int = Field(default=1, ge=1, description="Current page number (1-based)")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    pages: int = Field(default=0, description="Total number of pages")

    @model_validator(mode="after")
    def compute_pages(self) -> "TicketListResponse":
        """Compute total pages based on total and page_size."""
        if self.page_size > 0:
            self.pages = (self.total + self.page_size - 1) // self.page_size
        return self


# ── TicketFilter Schema ─────────────────────────────────────────────────────


class TicketFilter(BaseModel):
    """Filter parameters for listing tickets.

    All fields are optional for flexible filtering.

    Fields:
        status: List of statuses to filter by.
        priority: List of priorities to filter by.
        category: List of categories to filter by.
        assigned_to: Filter by assignee ID.
        channel: Filter by communication channel.
        customer_id: Filter by customer ID.
        date_from: Filter tickets created after this date.
        date_to: Filter tickets created before this date.
        tags: List of tags to filter by (matches any).
        is_spam: Filter by spam status.
        is_frozen: Filter by frozen status.
        search: Full-text search query.
    """

    status: Optional[List[str]] = Field(
        default=None,
        description="List of statuses to filter by",
    )
    priority: Optional[List[str]] = Field(
        default=None,
        description="List of priorities to filter by",
    )
    category: Optional[List[str]] = Field(
        default=None,
        description="List of categories to filter by",
    )
    assigned_to: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Filter by assignee ID",
    )
    channel: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Filter by communication channel",
    )
    customer_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Filter by customer ID",
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Filter tickets created after this date",
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Filter tickets created before this date",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags to filter by (matches any)",
    )
    is_spam: Optional[bool] = Field(
        default=None,
        description="Filter by spam status",
    )
    is_frozen: Optional[bool] = Field(
        default=None,
        description="Filter by frozen status",
    )
    search: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Full-text search query",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate all statuses are valid."""
        if v is not None:
            invalid = [s for s in v if s not in TicketStatus.VALID_STATUSES]
            if invalid:
                raise ValueError(
                    f"Invalid status values: {invalid}. "
                    f"Must be one of: {TicketStatus.VALID_STATUSES}"
                )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate all priorities are valid."""
        if v is not None:
            invalid = [p for p in v if p not in TicketPriority.VALID_PRIORITIES]
            if invalid:
                raise ValueError(
                    f"Invalid priority values: {invalid}. "
                    f"Must be one of: {TicketPriority.VALID_PRIORITIES}"
                )
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate all categories are valid."""
        if v is not None:
            invalid = [c for c in v if c not in TicketCategory.VALID_CATEGORIES]
            if invalid:
                raise ValueError(
                    f"Invalid category values: {invalid}. "
                    f"Must be one of: {TicketCategory.VALID_CATEGORIES}"
                )
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "TicketFilter":
        """Validate date_from is before date_to."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self


# ── TicketStatusUpdate Schema ──────────────────────────────────────────────


class TicketStatusUpdate(BaseModel):
    """Request to change a ticket's status.

    Fields:
        status: New status value.
        reason: Optional reason for the status change.
    """

    status: str = Field(
        min_length=1,
        max_length=50,
        description="New status value",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional reason for the status change",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        if v not in TicketStatus.VALID_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {TicketStatus.VALID_STATUSES}"
            )
        return v


# ── TicketAssign Schema ────────────────────────────────────────────────────


class TicketAssign(BaseModel):
    """Request to assign a ticket.

    Fields:
        assignee_id: ID of the assignee (optional for unassignment).
        assignee_type: Type of assignee (ai, human, system).
        reason: Optional reason for the assignment.
    """

    assignee_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the assignee (optional for unassignment)",
    )
    assignee_type: str = Field(
        default=AssigneeType.HUMAN,
        description="Type of assignee (ai, human, system)",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional reason for the assignment",
    )

    @field_validator("assignee_type")
    @classmethod
    def validate_assignee_type(cls, v: str) -> str:
        """Validate assignee type is one of the allowed values."""
        if v not in AssigneeType.VALID_TYPES:
            raise ValueError(
                f"Invalid assignee_type. Must be one of: {AssigneeType.VALID_TYPES}"
            )
        return v


# ── TicketBulkStatusUpdate Schema ──────────────────────────────────────────


class TicketBulkStatusUpdate(BaseModel):
    """Request to update status for multiple tickets.

    Fields:
        ticket_ids: List of ticket IDs to update.
        status: New status value for all tickets.
        reason: Optional reason for the status change.
    """

    ticket_ids: List[str] = Field(
        min_length=1,
        max_length=100,
        description="List of ticket IDs to update (max 100)",
    )
    status: str = Field(
        min_length=1,
        max_length=50,
        description="New status value for all tickets",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional reason for the status change",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        if v not in TicketStatus.VALID_STATUSES:
            raise ValueError(
                f"Invalid status. Must be one of: {TicketStatus.VALID_STATUSES}"
            )
        return v

    @field_validator("ticket_ids")
    @classmethod
    def validate_ticket_ids(cls, v: List[str]) -> List[str]:
        """Validate ticket IDs are unique and non-empty."""
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for ticket_id in v:
            if not ticket_id or not ticket_id.strip():
                raise ValueError("Ticket IDs cannot be empty strings")
            if ticket_id not in seen:
                seen.add(ticket_id)
                unique_ids.append(ticket_id)
        return unique_ids


# ── TicketBulkAssign Schema ────────────────────────────────────────────────


class TicketBulkAssign(BaseModel):
    """Request to assign multiple tickets.

    Fields:
        ticket_ids: List of ticket IDs to assign.
        assignee_id: ID of the assignee.
        assignee_type: Type of assignee (ai, human, system).
        reason: Optional reason for the assignment.
    """

    ticket_ids: List[str] = Field(
        min_length=1,
        max_length=100,
        description="List of ticket IDs to assign (max 100)",
    )
    assignee_id: str = Field(
        min_length=1,
        max_length=36,
        description="ID of the assignee",
    )
    assignee_type: str = Field(
        default=AssigneeType.HUMAN,
        description="Type of assignee (ai, human, system)",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional reason for the assignment",
    )

    @field_validator("assignee_type")
    @classmethod
    def validate_assignee_type(cls, v: str) -> str:
        """Validate assignee type is one of the allowed values."""
        if v not in AssigneeType.VALID_TYPES:
            raise ValueError(
                f"Invalid assignee_type. Must be one of: {AssigneeType.VALID_TYPES}"
            )
        return v

    @field_validator("ticket_ids")
    @classmethod
    def validate_ticket_ids(cls, v: List[str]) -> List[str]:
        """Validate ticket IDs are unique and non-empty."""
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for ticket_id in v:
            if not ticket_id or not ticket_id.strip():
                raise ValueError("Ticket IDs cannot be empty strings")
            if ticket_id not in seen:
                seen.add(ticket_id)
                unique_ids.append(ticket_id)
        return unique_ids


# ── Additional Response Schemas ────────────────────────────────────────────


class TicketStatusUpdateResponse(BaseModel):
    """Response after a successful status update."""

    ticket_id: str = Field(description="ID of the updated ticket")
    old_status: Optional[str] = Field(
        default=None,
        description="Previous status value",
    )
    new_status: str = Field(description="New status value")
    updated_at: datetime = Field(description="Timestamp of the update")
    message: str = Field(default="Status updated successfully")


class TicketAssignResponse(BaseModel):
    """Response after a successful assignment."""

    ticket_id: str = Field(description="ID of the assigned ticket")
    previous_assignee_id: Optional[str] = Field(
        default=None,
        description="ID of the previous assignee",
    )
    new_assignee_id: Optional[str] = Field(
        default=None,
        description="ID of the new assignee",
    )
    assignee_type: str = Field(description="Type of assignee")
    assigned_at: datetime = Field(description="Timestamp of the assignment")
    message: str = Field(default="Ticket assigned successfully")


class TicketBulkOperationResponse(BaseModel):
    """Response after a bulk operation."""

    success_count: int = Field(description="Number of successful operations")
    failure_count: int = Field(description="Number of failed operations")
    total_requested: int = Field(description="Total number of tickets requested")
    successful_ids: List[str] = Field(
        default_factory=list,
        description="List of successfully processed ticket IDs",
    )
    failed_ids: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of failed operations with reasons",
    )
    undo_token: Optional[str] = Field(
        default=None,
        description="Token for undoing the bulk operation",
    )
    message: str = Field(default="Bulk operation completed")
