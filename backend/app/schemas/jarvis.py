"""
PARWA Jarvis Schemas (Week 6 — Day 2 Phase 2)

Pydantic models for Jarvis onboarding chat API validation.

Covers:
- Session management (create, get, update context)
- Message send/receive with rich message types
- OTP verification (business email)
- Demo pack purchase ($1 pack)
- Payment (Paddle checkout)
- Demo call (voice AI call)
- Handoff (onboarding → customer care)
- Action tickets (CRUD + status)
- Call summary (post-call data)
- Entry context (URL param routing)
- Paginated history

Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Validators ─────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

_VALID_SESSION_TYPES = ("onboarding", "customer_care")
_VALID_PACK_TYPES = ("free", "demo")
_VALID_PAYMENT_STATUSES = ("none", "pending", "completed", "failed")
_VALID_ROLES = ("user", "jarvis", "system")
_VALID_MESSAGE_TYPES = (
    "text", "bill_summary", "payment_card", "otp_card",
    "handoff_card", "demo_call_card", "action_ticket",
    "call_summary", "recharge_cta",
    "limit_reached", "pack_expired", "error",
)
_VALID_STAGES = (
    "welcome", "discovery", "demo", "pricing",
    "bill_review", "verification", "payment", "handoff",
)
_VALID_TICKET_TYPES = (
    "otp_verification", "otp_verified",
    "payment_demo_pack", "payment_variant", "payment_variant_completed",
    "demo_call", "demo_call_completed",
    "roi_import", "handoff",
)
_VALID_TICKET_STATUSES = ("pending", "in_progress", "completed", "failed")
_VALID_ENTRY_SOURCES = (
    "direct", "pricing", "roi", "demo", "features",
    "referral", "ad", "organic", "email_campaign", "other",
)


def _validate_email(email: str) -> str:
    """Validate email format."""
    if not email or not _EMAIL_REGEX.match(email):
        raise ValueError("Invalid email format")
    return email.strip().lower()


def _validate_phone(phone: str) -> str:
    """Validate phone number — digits, spaces, +, -, parens. Min 7 digits."""
    cleaned = re.sub(r"[^\d+]", "", phone)
    digit_count = len(re.sub(r"\D", "", phone))
    if digit_count < 7:
        raise ValueError("Phone number must have at least 7 digits")
    if digit_count > 15:
        raise ValueError("Phone number too long (max 15 digits)")
    return phone.strip()


# ── Session Schemas ────────────────────────────────────────────────


class JarvisSessionCreate(BaseModel):
    """Request to create or resume a Jarvis session.

    Called on page load (/onboarding). If an active session exists
    for this user, it is resumed. Otherwise a new one is created.
    """

    entry_source: str = Field(
        default="direct",
        description="Where the user came from (pricing, roi, demo, etc.)",
    )
    entry_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional URL params (variant_id, industry, etc.)",
    )

    @field_validator("entry_source")
    @classmethod
    def entry_source_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_ENTRY_SOURCES:
            raise ValueError(
                f"Invalid entry_source. "
                f"Must be one of: {', '.join(_VALID_ENTRY_SOURCES)}"
            )
        return v


class JarvisContextUpdate(BaseModel):
    """Partial update to session context_json.

    Only provided fields are merged into existing context.
    """

    industry: Optional[str] = Field(default=None, max_length=50)
    selected_variants: Optional[List[Dict[str, Any]]] = None
    roi_result: Optional[Dict[str, Any]] = None
    demo_topics: Optional[List[str]] = None
    concerns_raised: Optional[List[str]] = None
    business_email: Optional[str] = Field(default=None, max_length=255)
    email_verified: Optional[bool] = None
    referral_source: Optional[str] = Field(default=None, max_length=100)
    pages_visited: Optional[List[str]] = None
    detected_stage: Optional[str] = None

    @field_validator("business_email")
    @classmethod
    def validate_business_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validate_email(v)

    @field_validator("detected_stage")
    @classmethod
    def validate_stage(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in _VALID_STAGES:
            raise ValueError(
                f"Invalid stage. Must be one of: {', '.join(_VALID_STAGES)}"
            )
        return v


class JarvisEntryContextRequest(BaseModel):
    """Set entry context from URL params."""

    entry_source: str = Field(
        description="Where the user came from",
    )
    entry_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="URL params (variant_id, industry, etc.)",
    )

    @field_validator("entry_source")
    @classmethod
    def entry_source_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_ENTRY_SOURCES:
            raise ValueError(
                f"Invalid entry_source. "
                f"Must be one of: {', '.join(_VALID_ENTRY_SOURCES)}"
            )
        return v


class JarvisSessionResponse(BaseModel):
    """Session details with context and limits."""

    id: str
    type: str
    context: Dict[str, Any] = Field(default_factory=dict)
    message_count_today: int = 0
    total_message_count: int = 0
    remaining_today: int = 20
    pack_type: str = "free"
    pack_expiry: Optional[str] = None
    demo_call_used: bool = False
    is_active: bool = True
    payment_status: str = "none"
    handoff_completed: bool = False
    detected_stage: str = "welcome"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Message Schemas ────────────────────────────────────────────────


class JarvisMessageSend(BaseModel):
    """User sends a message to Jarvis."""

    content: str = Field(
        min_length=1,
        max_length=4000,
        description="User message text",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (optional, uses active session if omitted)",
    )


class JarvisMessageResponse(BaseModel):
    """AI response message with metadata."""

    id: str
    session_id: str
    role: str
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    knowledge_used: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Knowledge base files used for this response",
    )

    model_config = {"from_attributes": True}


class JarvisHistoryResponse(BaseModel):
    """Paginated chat history."""

    messages: List[JarvisMessageResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


# ── OTP Schemas ────────────────────────────────────────────────────


class JarvisOtpRequest(BaseModel):
    """Send OTP to business email."""

    email: str = Field(
        min_length=5,
        max_length=255,
        description="Business email address",
    )

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        return _validate_email(v)


class JarvisOtpVerify(BaseModel):
    """Verify OTP code."""

    code: str = Field(
        min_length=4,
        max_length=6,
        description="OTP code",
    )
    email: Optional[str] = Field(
        default=None,
        description="Email that received the OTP",
    )


class JarvisOtpResponse(BaseModel):
    """OTP send/verify response."""

    message: str
    status: str
    attempts_remaining: Optional[int] = None
    expires_at: Optional[str] = None


# ── Demo Pack Schemas ──────────────────────────────────────────────


class JarvisDemoPackPurchase(BaseModel):
    """Purchase $1 demo pack request."""

    pass  # No fields needed — uses session context


class JarvisDemoPackStatusResponse(BaseModel):
    """Demo pack status response."""

    pack_type: str
    remaining_today: int
    total_allowed: int
    pack_expiry: Optional[str] = None
    demo_call_remaining: bool = True


# ── Payment Schemas ────────────────────────────────────────────────


class JarvisPaymentCreate(BaseModel):
    """Create Paddle checkout session."""

    variants: List[Dict[str, Any]] = Field(
        ...,
        description="List of {id, quantity} variant selections",
        min_length=1,
    )
    industry: str = Field(
        ...,
        description="Industry identifier",
    )

    @field_validator("variants")
    @classmethod
    def validate_variants(
            cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in v:
            if "id" not in item:
                raise ValueError("Each variant must have an 'id'")
            if "quantity" not in item:
                raise ValueError("Each variant must have a 'quantity'")
            qty = item["quantity"]
            if not isinstance(qty, int) or qty < 1:
                raise ValueError("Quantity must be a positive integer")
            if qty > 10:
                raise ValueError("Max 10 per variant")
        return v


class JarvisPaymentStatusResponse(BaseModel):
    """Payment status response."""

    status: str
    paddle_transaction_id: Optional[str] = None
    amount: Optional[str] = None
    currency: str = "USD"
    paid_at: Optional[str] = None


class JarvisPaymentWebhookPayload(BaseModel):
    """Paddle webhook payload (internal parsing)."""

    event_type: str
    event_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    signature: Optional[str] = None


# ── Demo Call Schemas ──────────────────────────────────────────────


class JarvisDemoCallRequest(BaseModel):
    """Initiate demo voice call."""

    phone: str = Field(
        min_length=7,
        max_length=20,
        description="Phone number to call",
    )

    @field_validator("phone")
    @classmethod
    def phone_must_be_valid(cls, v: str) -> str:
        return _validate_phone(v)


class JarvisDemoCallVerifyOtp(BaseModel):
    """Verify phone OTP for demo call."""

    code: str = Field(
        min_length=4,
        max_length=6,
        description="Phone OTP code",
    )


class JarvisDemoCallSummaryResponse(BaseModel):
    """Post-call summary response."""

    call_id: Optional[str] = None
    status: str = "completed"
    duration_seconds: int = 0
    topics_discussed: List[str] = Field(default_factory=list)
    key_moments: List[Dict[str, Any]] = Field(default_factory=list)
    user_impressions: Optional[str] = None
    roi_mapping: Optional[Dict[str, Any]] = None
    transcript_summary: Optional[str] = None
    created_at: Optional[str] = None


# ── Handoff Schemas ────────────────────────────────────────────────


class JarvisHandoffRequest(BaseModel):
    """Execute handoff to customer care."""

    pass  # Uses session context — no extra fields


class JarvisHandoffStatusResponse(BaseModel):
    """Handoff status response."""

    handoff_completed: bool
    new_session_id: Optional[str] = None
    handoff_at: Optional[str] = None


# ── Action Ticket Schemas ──────────────────────────────────────────


class JarvisActionTicketCreate(BaseModel):
    """Create an action ticket."""

    ticket_type: str = Field(
        description="Type of action ticket",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional ticket metadata",
    )

    @field_validator("ticket_type")
    @classmethod
    def ticket_type_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_TICKET_TYPES:
            raise ValueError(
                f"Invalid ticket_type. "
                f"Must be one of: {', '.join(_VALID_TICKET_TYPES)}"
            )
        return v


class JarvisActionTicketUpdateStatus(BaseModel):
    """Update ticket status."""

    status: str = Field(description="New status")

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_TICKET_STATUSES:
            raise ValueError(
                f"Invalid status. "
                f"Must be one of: {', '.join(_VALID_TICKET_STATUSES)}"
            )
        return v


class JarvisActionTicketResponse(BaseModel):
    """Action ticket with result and metadata."""

    id: str
    session_id: str
    ticket_type: str
    status: str = "pending"
    result: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class JarvisActionTicketListResponse(BaseModel):
    """List of action tickets for a session."""

    tickets: List[JarvisActionTicketResponse]
    total: int = 0


# ── Error Schema ───────────────────────────────────────────────────


class JarvisErrorResponse(BaseModel):
    """Standard Jarvis error response.

    Matches PARWA error format:
    {"error": {"code": "...", "message": "...", "details": ...}}
    """

    error: Dict[str, Any] = Field(
        default_factory=lambda: {
            "code": "INTERNAL_ERROR",
            "message": "An error occurred",
            "details": None,
        }
    )
