"""
Ticket Message Pydantic Schemas

Schemas for ticket messages and attachments.
- MessageCreate: Create a new ticket message
- MessageUpdate: Update an existing message
- MessageResponse: Full message response with computed properties
- AttachmentUpload: Validate attachment uploads
- AttachmentResponse: Attachment response schema
- MessageWithAttachmentsCreate: Create message with attachments
- MessageWithAttachmentsResponse: Message with attachments response
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Message Schemas ─────────────────────────────────────────────────────


class MessageCreate(BaseModel):
    """Schema for creating a new ticket message.

    Fields:
        content: Message text content (required, non-empty)
        role: Who sent the message - customer/agent/system/ai
        channel: Communication channel (email, chat, sms, etc.)
        is_internal: Whether this is an internal note (default False)
        metadata_json: Additional metadata as dict (default {})
    """

    content: str = Field(..., min_length=1, description="Message content")
    role: Literal["customer", "agent", "system", "ai"] = Field(
        ..., description="Message sender role"
    )
    channel: str = Field(..., min_length=1, description="Communication channel")
    is_internal: bool = Field(default=False, description="Whether message is internal")
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v: str) -> str:
        """Validate that content is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError("Content must not be empty")
        return v.strip()


class MessageUpdate(BaseModel):
    """Schema for updating an existing ticket message.

    All fields are optional for partial updates.
    """

    content: Optional[str] = Field(default=None, min_length=1)
    is_internal: Optional[bool] = Field(default=None)

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that content is not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError("Content must not be empty")
        return v.strip() if v else None


class MessageResponse(BaseModel):
    """Full message response schema with computed properties.

    Includes all fields from TicketMessage model plus computed
    properties for role checks.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    company_id: str
    role: str
    content: str
    channel: str
    metadata_json: str
    is_internal: bool
    is_redacted: bool
    ai_confidence: Optional[Decimal] = None
    variant_version: Optional[str] = None
    classification: Optional[str] = None
    created_at: Optional[datetime] = None

    @property
    def is_from_customer(self) -> bool:
        """Check if message was sent by customer."""
        return self.role == "customer"

    @property
    def is_from_agent(self) -> bool:
        """Check if message was sent by agent."""
        return self.role == "agent"

    @property
    def is_from_ai(self) -> bool:
        """Check if message was sent by AI."""
        return self.role == "ai"


# ── Attachment Schemas ──────────────────────────────────────────────────


class AttachmentUpload(BaseModel):
    """Schema for validating attachment uploads.

    Fields:
        filename: Name of the file being uploaded
        file_size: Size of the file in bytes (must be positive)
        mime_type: MIME type of the file
        file_url: URL where the file is stored
    """

    filename: str = Field(..., min_length=1, max_length=255, description="File name")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., min_length=1, max_length=100, description="MIME type")
    file_url: str = Field(..., min_length=1, description="File storage URL")

    @field_validator("file_size")
    @classmethod
    def file_size_must_be_positive(cls, v: int) -> int:
        """Validate that file size is positive."""
        if v <= 0:
            raise ValueError("File size must be positive")
        return v


class AttachmentResponse(BaseModel):
    """Attachment response schema with all model fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    company_id: str
    filename: str
    file_url: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


# ── Composite Schemas ───────────────────────────────────────────────────


class MessageWithAttachmentsCreate(BaseModel):
    """Schema for creating a message with optional attachments.

    Combines message creation with attachment uploads in a single request.
    """

    message: MessageCreate = Field(..., description="Message to create")
    attachments: Optional[list[AttachmentUpload]] = Field(
        default=None, description="Optional list of attachments"
    )


class MessageWithAttachmentsResponse(BaseModel):
    """Response schema for message with attachments.

    Returns the created message along with all associated attachments.
    """

    message: MessageResponse = Field(..., description="Created message")
    attachments: list[AttachmentResponse] = Field(
        default_factory=list, description="List of attachments"
    )
