"""
Email Channel Schemas: Pydantic models for email channel operations.

Week 13 Day 1 (F-121: Email Inbound).

Schemas for inbound email processing, loop detection,
auto-reply detection, and email thread management.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Inbound Email Schemas ──────────────────────────────────────

class InboundEmailCreate(BaseModel):
    """Schema for creating an inbound email record from webhook data."""

    sender_email: str = Field(..., max_length=254,
                              description="Sender email address")
    sender_name: Optional[str] = Field(
        None, max_length=200, description="Sender display name")
    recipient_email: str = Field(...,
                                 max_length=254,
                                 description="Recipient email address")
    subject: Optional[str] = Field(
        None, max_length=500, description="Email subject line")
    body_html: Optional[str] = Field(None, description="HTML body content")
    body_text: Optional[str] = Field(
        None, description="Plain text body content")
    message_id: Optional[str] = Field(
        None, max_length=255, description="RFC 2822 Message-ID header")
    in_reply_to: Optional[str] = Field(
        None, max_length=255, description="In-Reply-To header")
    references: Optional[str] = Field(
        None, description="References header (Message-ID chain)")
    attachments: Optional[List[dict]] = Field(
        default_factory=list, description="Attachment metadata list")
    headers_json: Optional[str] = Field(
        "{}", description="All email headers as JSON string")


class InboundEmailResponse(BaseModel):
    """Schema for API responses containing inbound email data."""

    id: str
    company_id: str
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    sender_email: str
    sender_name: Optional[str] = None
    recipient_email: str
    subject: Optional[str] = None
    is_auto_reply: bool = False
    is_loop: bool = False
    is_processed: bool = False
    ticket_id: Optional[str] = None
    processing_error: Optional[str] = None
    raw_size_bytes: int = 0
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InboundEmailListResponse(BaseModel):
    """Paginated list of inbound emails."""

    items: List[InboundEmailResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Email Thread Schemas ───────────────────────────────────────

class EmailThreadResponse(BaseModel):
    """Schema for email thread data."""

    id: str
    company_id: str
    ticket_id: str
    thread_message_id: str
    latest_message_id: Optional[str] = None
    message_count: int = 1
    participants: str = "[]"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Detection Result Schemas ───────────────────────────────────

class EmailLoopDetection(BaseModel):
    """Result of email loop detection check."""

    is_loop: bool = False
    reason: Optional[str] = None
    loop_type: Optional[str] = Field(
        None,
        description="Type of loop detected: self_sent, x_loop_header, "
                    "already_processed, depth_exceeded"
    )


class AutoReplyDetection(BaseModel):
    """Result of auto-reply / OOO detection check."""

    is_auto_reply: bool = False
    reason: Optional[str] = None
    detection_source: Optional[str] = Field(
        None,
        description="Where the auto-reply was detected: header or body"
    )


class EmailProcessResult(BaseModel):
    """Result of processing an inbound email."""

    status: str = Field(
        ...,
        description="Result status: created_ticket, added_to_thread, "
                    "skipped_auto_reply, skipped_loop, skipped_duplicate, "
                    "rate_limited, validation_error, error"
    )
    ticket_id: Optional[str] = None
    thread_id: Optional[str] = None
    inbound_email_id: str
    error: Optional[str] = None
    loop_detection: Optional[EmailLoopDetection] = None
    auto_reply_detection: Optional[AutoReplyDetection] = None
