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
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
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
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(String(36), ForeignKey("integrations.id"), nullable=False)
    base_url = Column(String(500), nullable=False)
    auth_type = Column(String(50), nullable=False)  # bearer, basic, api_key, oauth2
    auth_config = Column(Text)  # encrypted
    headers = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class WebhookIntegration(Base):
    __tablename__ = "webhook_integrations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(String(36), ForeignKey("integrations.id"), nullable=False)
    webhook_url = Column(String(500), nullable=False)
    secret = Column(String(255))
    events = Column(Text, default="[]")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class MCPConnection(Base):
    __tablename__ = "mcp_connections"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
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
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    db_type = Column(String(50), nullable=False)  # postgresql, mysql, mongodb
    connection_string = Column(Text)  # encrypted
    is_readonly = Column(Boolean, default=True)
    status = Column(String(50), default="disconnected")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class EventBuffer(Base):
    __tablename__ = "event_buffer"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"))
    event_type = Column(String(100), nullable=False)
    event_data = Column(Text)
    ttl_seconds = Column(Integer, default=86400)  # 24h default (BC-005)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
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
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36))
    actor_type = Column(String(50), nullable=False)  # user, system, api_key
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
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
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
