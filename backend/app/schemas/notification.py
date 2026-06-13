"""
PARWA Notification Schemas

Pydantic models for notification templates, preferences, and sending.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class NotificationChannel(str, Enum):
    """Available notification channels."""

    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"


# ── Notification Template Schemas ────────────────────────────────────────────


class NotificationTemplateCreate(BaseModel):
    """Schema for creating a notification template."""

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type that triggers this template (e.g., 'ticket.created')",
    )
    channel: NotificationChannel = Field(
        ...,
        description="Channel for this notification template",
    )
    subject_template: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Subject line template (supports Jinja2 variables)",
    )
    body_template: str = Field(
        ...,
        min_length=1,
        description="Body content template (supports Jinja2 variables)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the template is active",
    )

    @field_validator("event_type")
    @classmethod
    def event_type_format(cls, v: str) -> str:
        v = v.strip().lower()
        if "." not in v:
            raise ValueError(
                "event_type should be in format 'entity.action' (e.g., 'ticket.created')"
            )
        return v


class NotificationTemplateUpdate(BaseModel):
    """Schema for updating a notification template."""

    event_type: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Event type that triggers this template",
    )
    channel: Optional[NotificationChannel] = Field(
        default=None,
        description="Channel for this notification",
    )
    subject_template: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Subject line template",
    )
    body_template: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Body content template",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the template is active",
    )

    @field_validator("event_type")
    @classmethod
    def event_type_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if "." not in v:
                raise ValueError(
                    "event_type should be in format 'entity.action'"
                )
        return v


class NotificationTemplateResponse(BaseModel):
    """Schema for notification template response."""

    id: str
    event_type: str
    channel: NotificationChannel
    subject_template: str
    body_template: str
    is_active: bool
    company_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Notification Preference Schemas ──────────────────────────────────────────


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating user notification preferences."""

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type to configure",
    )
    channel: NotificationChannel = Field(
        ...,
        description="Channel to configure",
    )
    enabled: bool = Field(
        ...,
        description="Whether notifications are enabled for this event/channel",
    )


# ── Notification Send Request Schemas ────────────────────────────────────────


class NotificationSendRequest(BaseModel):
    """Schema for manually sending a notification."""

    ticket_id: Optional[str] = Field(
        default=None,
        description="Related ticket ID (if applicable)",
    )
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type determining which template to use",
    )
    recipient_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of user IDs to receive the notification",
    )
    template_vars: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables to substitute in template",
    )

    @field_validator("recipient_ids")
    @classmethod
    def recipients_must_not_have_duplicates(cls, v: List[str]) -> List[str]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate recipient IDs are not allowed")
        return v


class NotificationSendResponse(BaseModel):
    """Schema for notification send result."""

    success: bool
    notification_id: Optional[str] = None
    message: Optional[str] = None
    failed_recipients: Optional[List[str]] = None


# ── Notification API Response Schemas ──────────────────────────────────────────


class NotificationListItem(BaseModel):
    """Single notification item in list response."""

    id: str
    event_type: str
    title: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    ticket_id: Optional[str] = None
    read_at: Optional[str] = None
    created_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    notifications: List[NotificationListItem]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread notification count."""

    unread_count: int


class MarkReadResponse(BaseModel):
    """Response after marking notifications as read."""

    marked_count: int
    marked_all: Optional[bool] = None
    marked_ids: Optional[List[str]] = None


class TemplateListItem(BaseModel):
    """Single template item in list response."""

    id: str
    event_type: str
    channel: str
    name: Optional[str] = None
    description: Optional[str] = None
    subject_template: str
    body_template: str
    is_active: bool
    version: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TemplateListResponse(BaseModel):
    """Paginated list of notification templates."""

    templates: List[TemplateListItem]
    total: int


class TemplateCreateResponse(BaseModel):
    """Response after creating a template."""

    id: str
    event_type: str
    channel: str
    name: Optional[str] = None
    is_active: bool
    version: Optional[int] = None


class TemplateGetResponse(BaseModel):
    """Response for getting a single template."""

    id: str
    event_type: str
    channel: str
    name: Optional[str] = None
    description: Optional[str] = None
    subject_template: str
    body_template: str
    is_active: bool
    version: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TemplateUpdateResponse(BaseModel):
    """Response after updating a template."""

    id: str
    name: Optional[str] = None
    is_active: bool
    updated_at: Optional[str] = None


class TemplateDeleteResponse(BaseModel):
    """Response after deleting a template."""

    success: bool


class TemplateVariablesResponse(BaseModel):
    """Response for template variables."""

    event_type: str
    variables: Dict[str, Any]


class PreferenceUpdateResponse(BaseModel):
    """Response after updating a notification preference."""

    event_type: str
    enabled: Optional[bool] = None
    channels: Optional[List[str]] = None
    priority_threshold: Optional[str] = None


class ResetPreferencesResponse(BaseModel):
    """Response after resetting preferences."""

    reset_count: int


class DisableAllResponse(BaseModel):
    """Response after disabling all notifications."""

    disabled_count: int


class EnableAllResponse(BaseModel):
    """Response after enabling all notifications."""

    enabled_count: int
