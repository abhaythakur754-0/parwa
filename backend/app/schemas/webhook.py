"""
Webhook Pydantic Schemas (BC-003, BC-012)

Schemas for incoming webhook payloads and API responses.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    """Generic incoming webhook payload schema.

    Used as a base for provider-specific payload extraction.
    """
    provider: str = Field(
        ..., description="Webhook provider name",
    )
    event_id: str = Field(
        ..., description="Provider-specific event ID",
    )
    event_type: str = Field(
        ..., description="Event type (e.g. subscription.created)",
    )
    company_id: str = Field(
        ..., description="Tenant company ID (BC-001)",
    )
    payload: Optional[dict[str, Any]] = Field(
        default=None,
        description="Raw webhook payload data",
    )


class WebhookResponse(BaseModel):
    """Response schema for webhook endpoints (BC-012)."""
    status: str = Field(
        ..., description="Processing status",
    )
    message: str = Field(
        ..., description="Human-readable status message",
    )
    event_id: Optional[str] = Field(
        default=None,
        description="Webhook event record ID",
    )
    duplicate: bool = Field(
        default=False,
        description="Whether this was a duplicate event",
    )
