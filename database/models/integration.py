"""
Integration Models: integrations, rest_connectors, webhook_integrations,
mcp_connections, db_connections, event_buffer, error_log,
audit_trail, outgoing_webhooks.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    integration_type = Column(String(100), nullable=False)
    name = Column(String(255))
    status = Column(String(50), default="disconnected")
    credentials_encrypted = Column(Text)
    settings = Column(Text, default="{}")
    last_sync = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class RESTConnector(Base):
    __tablename__ = "rest_connectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    integration_id = Column(
        String(36), ForeignKey("integrations.id"),
        nullable=False,
    )
    base_url = Column(String(500), nullable=False)
    # bearer, basic, api_key, oauth2
    auth_type = Column(String(50), nullable=False)
    auth_config = Column(Text)  # encrypted
    headers = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class WebhookIntegration(Base):
    __tablename__ = "webhook_integrations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    integration_id = Column(
        String(36), ForeignKey("integrations.id"),
        nullable=False,
    )
    webhook_url = Column(String(500), nullable=False)
    secret = Column(String(255))
    events = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class MCPConnection(Base):
    __tablename__ = "mcp_connections"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    server_url = Column(String(500))
    auth_token = Column(Text)  # encrypted
    status = Column(String(50), default="disconnected")
    capabilities = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class DBConnection(Base):
    __tablename__ = "db_connections"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    # postgresql, mysql, mongodb
    db_type = Column(String(50), nullable=False)
    connection_string = Column(Text)  # encrypted
    is_readonly = Column(Boolean, default=True)
    status = Column(String(50), default="disconnected")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class EventBuffer(Base):
    __tablename__ = "event_buffer"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    event_type = Column(String(100), nullable=False)
    event_data = Column(Text)
    # 24h default (BC-005)
    ttl_seconds = Column(Integer, default=86400)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    path = Column(String(500))
    method = Column(String(10))
    status_code = Column(Integer)
    correlation_id = Column(String(36))
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    actor_id = Column(String(36))
    # user, system, api_key
    actor_type = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(36))
    old_value = Column(Text)
    new_value = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class OutgoingWebhook(Base):
    __tablename__ = "outgoing_webhooks"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(255))
    events = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    last_delivery_at = Column(DateTime)
    last_status = Column(String(50))
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class CustomIntegration(Base):
    """Unified custom integration table for F-031.

    Supports 5 integration types: rest, graphql, webhook_in, webhook_out, database.
    Config is stored as encrypted JSON with type-specific schemas.

    BC-001: Scoped to company_id.
    BC-011: Credentials encrypted at rest (AES-256).
    BC-012: Auto-disable after 3 consecutive errors.
    """

    __tablename__ = "custom_integrations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    # rest, graphql, webhook_in, webhook_out, database
    integration_type = Column(String(50), nullable=False, index=True)
    # draft, active, disabled, error
    status = Column(String(50), nullable=False, default="draft", index=True)
    # Encrypted JSON config — type-specific fields
    config_encrypted = Column(Text, nullable=False, default="{}")
    # Non-encrypted settings (metadata, labels, etc.)
    settings = Column(Text, nullable=False, default="{}")
    # Unique webhook endpoint ID (for webhook_in type only)
    webhook_id = Column(String(36), unique=True, index=True)
    # HMAC signing secret (webhook_in type only)
    webhook_secret = Column(String(255))
    # Error tracking
    consecutive_error_count = Column(Integer, nullable=False, default=0)
    last_error_message = Column(Text)
    last_tested_at = Column(DateTime)
    last_test_result = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class WebhookDeliveryLog(Base):
    """Outgoing webhook delivery log for F-031.

    Tracks every delivery attempt with status, response, and retry info.

    BC-001: Scoped to company_id.
    BC-004: Supports retry with exponential backoff.
    """

    __tablename__ = "webhook_delivery_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    custom_integration_id = Column(
        String(36), ForeignKey("custom_integrations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The event that triggered this delivery
    trigger_event = Column(String(100), nullable=False)
    trigger_event_id = Column(String(36))
    # Delivery attempt number (1, 2, 3)
    attempt = Column(Integer, nullable=False, default=1)
    # pending, success, failed
    status = Column(String(50), nullable=False, default="pending")
    # HTTP status code from target
    response_status_code = Column(Integer)
    response_body = Column(Text)
    error_message = Column(Text)
    # Request payload (for debugging, not encrypted)
    payload_snapshot = Column(Text)
    # Timestamps
    scheduled_at = Column(DateTime, default=lambda: datetime.utcnow())
    delivered_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
