"""
PARWA Integration Schemas

Pydantic v2 models for request/response validation across all 9 integration
domain models: Integration, RESTConnector, WebhookIntegration, MCPConnection,
DBConnection, EventBuffer, ErrorLog, AuditTrail, and OutgoingWebhook.

Security rules:
- Encrypted fields (credentials_encrypted, auth_config_encrypted,
  auth_token_encrypted, connection_string_encrypted) are NEVER exposed
  in Create, Update, or Response schemas.
- Secret fields (WebhookIntegration.secret, OutgoingWebhook.secret) are
  accepted in Create/Update but masked in Response schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Integration ───────────────────────────────────────────────────────────────


class IntegrationCreate(BaseModel):
    """Schema for creating a new integration."""

    integration_type: str = Field(
        ...,
        max_length=100,
        description="Type of integration (e.g. slack, salesforce, hubspot)",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-readable integration name",
    )
    status: Optional[str] = Field(
        default="disconnected",
        max_length=50,
        description="Connection status (connected, disconnected, error)",
    )
    settings: Optional[str] = Field(
        default="{}",
        description="JSON-encoded integration settings",
    )
    last_sync: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of last successful sync",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Last error message if status is error",
    )


class IntegrationUpdate(BaseModel):
    """Schema for partially updating an integration."""

    integration_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Type of integration",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-readable integration name",
    )
    status: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Connection status",
    )
    settings: Optional[str] = Field(
        default=None,
        description="JSON-encoded integration settings",
    )
    last_sync: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of last successful sync",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Last error message if status is error",
    )


class IntegrationResponse(BaseModel):
    """Schema for integration API responses.

    credentials_encrypted is intentionally excluded for security.
    """

    id: str
    company_id: str
    integration_type: str
    name: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[str] = None
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── RESTConnector ─────────────────────────────────────────────────────────────


class RESTConnectorCreate(BaseModel):
    """Schema for creating a REST API connector."""

    integration_id: str = Field(
        ...,
        description="Parent integration ID",
    )
    base_url: str = Field(
        ...,
        max_length=500,
        description="Base URL for the REST API",
    )
    auth_type: str = Field(
        ...,
        max_length=50,
        description="Authentication method (bearer, basic, api_key, oauth2)",
    )
    headers: Optional[str] = Field(
        default="{}",
        description="JSON-encoded default headers",
    )
    is_active: Optional[bool] = Field(
        default=True,
        description="Whether the connector is active",
    )


class RESTConnectorUpdate(BaseModel):
    """Schema for partially updating a REST connector."""

    integration_id: Optional[str] = Field(
        default=None,
        description="Parent integration ID",
    )
    base_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Base URL for the REST API",
    )
    auth_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Authentication method",
    )
    headers: Optional[str] = Field(
        default=None,
        description="JSON-encoded default headers",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the connector is active",
    )


class RESTConnectorResponse(BaseModel):
    """Schema for REST connector API responses.

    auth_config_encrypted is intentionally excluded for security.
    """

    id: str
    company_id: str
    integration_id: str
    base_url: str
    auth_type: str
    headers: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── WebhookIntegration ────────────────────────────────────────────────────────


class WebhookIntegrationCreate(BaseModel):
    """Schema for creating an incoming webhook integration."""

    integration_id: str = Field(
        ...,
        description="Parent integration ID",
    )
    webhook_url: str = Field(
        ...,
        max_length=500,
        description="URL that will receive webhook payloads",
    )
    secret: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Signing secret for payload verification",
    )
    events: Optional[str] = Field(
        default="[]",
        description="JSON-encoded list of subscribed event types",
    )
    is_active: Optional[bool] = Field(
        default=True,
        description="Whether the webhook is active",
    )


class WebhookIntegrationUpdate(BaseModel):
    """Schema for partially updating a webhook integration."""

    integration_id: Optional[str] = Field(
        default=None,
        description="Parent integration ID",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL that will receive webhook payloads",
    )
    secret: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Signing secret for payload verification",
    )
    events: Optional[str] = Field(
        default=None,
        description="JSON-encoded list of subscribed event types",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the webhook is active",
    )


class WebhookIntegrationResponse(BaseModel):
    """Schema for webhook integration API responses.

    secret is masked to prevent exposure in API responses.
    """

    id: str
    company_id: str
    integration_id: str
    webhook_url: str
    secret_masked: Optional[str] = Field(
        default=None,
        description="Masked signing secret (never exposed in full)",
    )
    events: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── MCPConnection ─────────────────────────────────────────────────────────────


class MCPConnectionCreate(BaseModel):
    """Schema for creating an MCP (Model Context Protocol) connection."""

    name: str = Field(
        ...,
        max_length=255,
        description="Human-readable MCP connection name",
    )
    server_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="MCP server endpoint URL",
    )
    status: Optional[str] = Field(
        default="disconnected",
        max_length=50,
        description="Connection status (connected, disconnected, error)",
    )
    capabilities: Optional[str] = Field(
        default="[]",
        description="JSON-encoded list of MCP capabilities",
    )


class MCPConnectionUpdate(BaseModel):
    """Schema for partially updating an MCP connection."""

    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-readable MCP connection name",
    )
    server_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="MCP server endpoint URL",
    )
    status: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Connection status",
    )
    capabilities: Optional[str] = Field(
        default=None,
        description="JSON-encoded list of MCP capabilities",
    )


class MCPConnectionResponse(BaseModel):
    """Schema for MCP connection API responses.

    auth_token_encrypted is intentionally excluded for security.
    """

    id: str
    company_id: str
    name: str
    server_url: Optional[str] = None
    status: Optional[str] = None
    capabilities: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── DBConnection ──────────────────────────────────────────────────────────────


class DBConnectionCreate(BaseModel):
    """Schema for creating a database connection."""

    name: str = Field(
        ...,
        max_length=255,
        description="Human-readable database connection name",
    )
    db_type: str = Field(
        ...,
        max_length=50,
        description="Database engine type (postgresql, mysql, mongodb)",
    )
    is_readonly: Optional[bool] = Field(
        default=True,
        description="Whether the connection is read-only",
    )
    status: Optional[str] = Field(
        default="disconnected",
        max_length=50,
        description="Connection status (connected, disconnected, error)",
    )


class DBConnectionUpdate(BaseModel):
    """Schema for partially updating a database connection."""

    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-readable database connection name",
    )
    db_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Database engine type",
    )
    is_readonly: Optional[bool] = Field(
        default=None,
        description="Whether the connection is read-only",
    )
    status: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Connection status",
    )


class DBConnectionResponse(BaseModel):
    """Schema for database connection API responses.

    connection_string_encrypted is intentionally excluded for security.
    """

    id: str
    company_id: str
    name: str
    db_type: str
    is_readonly: Optional[bool] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── EventBuffer ───────────────────────────────────────────────────────────────


class EventBufferCreate(BaseModel):
    """Schema for creating an event buffer entry."""

    session_id: Optional[str] = Field(
        default=None,
        description="Associated ticket/session ID",
    )
    event_type: str = Field(
        ...,
        max_length=100,
        description="Type of event (e.g. message.created, ticket.assigned)",
    )
    event_data: Optional[str] = Field(
        default=None,
        description="JSON-encoded event payload",
    )
    ttl_seconds: Optional[int] = Field(
        default=86400,
        ge=1,
        description="Time-to-live in seconds (default 24h, BC-005)",
    )


class EventBufferUpdate(BaseModel):
    """Schema for partially updating an event buffer entry."""

    session_id: Optional[str] = Field(
        default=None,
        description="Associated ticket/session ID",
    )
    event_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Type of event",
    )
    event_data: Optional[str] = Field(
        default=None,
        description="JSON-encoded event payload",
    )
    ttl_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Time-to-live in seconds",
    )


class EventBufferResponse(BaseModel):
    """Schema for event buffer API responses."""

    id: str
    company_id: str
    session_id: Optional[str] = None
    event_type: str
    event_data: Optional[str] = None
    ttl_seconds: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── ErrorLog ──────────────────────────────────────────────────────────────────


class ErrorLogCreate(BaseModel):
    """Schema for creating an error log entry."""

    error_type: str = Field(
        ...,
        max_length=100,
        description="Error category (e.g. ValidationError, ExternalAPIError)",
    )
    error_message: str = Field(
        ...,
        description="Human-readable error description",
    )
    stack_trace: Optional[str] = Field(
        default=None,
        description="Full stack trace for debugging",
    )
    path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Request path where the error occurred",
    )
    method: Optional[str] = Field(
        default=None,
        max_length=10,
        description="HTTP method (GET, POST, etc.)",
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP status code associated with the error",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Correlation ID for tracing across services",
    )
    resolved: Optional[bool] = Field(
        default=False,
        description="Whether the error has been resolved",
    )


class ErrorLogUpdate(BaseModel):
    """Schema for partially updating an error log entry."""

    error_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Error category",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Human-readable error description",
    )
    stack_trace: Optional[str] = Field(
        default=None,
        description="Full stack trace for debugging",
    )
    path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Request path where the error occurred",
    )
    method: Optional[str] = Field(
        default=None,
        max_length=10,
        description="HTTP method",
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP status code",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="Correlation ID",
    )
    resolved: Optional[bool] = Field(
        default=None,
        description="Whether the error has been resolved",
    )


class ErrorLogResponse(BaseModel):
    """Schema for error log API responses."""

    id: str
    company_id: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    correlation_id: Optional[str] = None
    resolved: Optional[bool] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── AuditTrail ────────────────────────────────────────────────────────────────


class AuditTrailCreate(BaseModel):
    """Schema for creating an audit trail entry."""

    actor_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the user or system that performed the action",
    )
    actor_type: str = Field(
        ...,
        max_length=50,
        description="Type of actor (user, system, api_key)",
    )
    action: str = Field(
        ...,
        max_length=100,
        description="Action performed (e.g. ticket.created, user.updated)",
    )
    resource_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Type of resource affected (e.g. ticket, user, company)",
    )
    resource_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the affected resource",
    )
    old_value: Optional[str] = Field(
        default=None,
        description="JSON-encoded previous value of the changed field",
    )
    new_value: Optional[str] = Field(
        default=None,
        description="JSON-encoded new value of the changed field",
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        description="IP address of the actor",
    )
    user_agent: Optional[str] = Field(
        default=None,
        max_length=500,
        description="User-Agent header of the actor",
    )


class AuditTrailUpdate(BaseModel):
    """Schema for partially updating an audit trail entry.

    Note: audit entries are typically immutable; this schema exists
    for completeness but should be used with caution.
    """

    actor_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the actor",
    )
    actor_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Type of actor",
    )
    action: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Action performed",
    )
    resource_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Type of resource affected",
    )
    resource_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="ID of the affected resource",
    )
    old_value: Optional[str] = Field(
        default=None,
        description="JSON-encoded previous value",
    )
    new_value: Optional[str] = Field(
        default=None,
        description="JSON-encoded new value",
    )
    ip_address: Optional[str] = Field(
        default=None,
        max_length=45,
        description="IP address of the actor",
    )
    user_agent: Optional[str] = Field(
        default=None,
        max_length=500,
        description="User-Agent header",
    )


class AuditTrailResponse(BaseModel):
    """Schema for audit trail API responses."""

    id: str
    company_id: str
    actor_id: Optional[str] = None
    actor_type: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── OutgoingWebhook ───────────────────────────────────────────────────────────


class OutgoingWebhookCreate(BaseModel):
    """Schema for creating an outgoing webhook."""

    name: str = Field(
        ...,
        max_length=255,
        description="Human-readable webhook name",
    )
    url: str = Field(
        ...,
        max_length=500,
        description="Destination URL for outgoing webhook payloads",
    )
    secret: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Signing secret for payload signature verification",
    )
    events: Optional[str] = Field(
        default="[]",
        description="JSON-encoded list of event types that trigger delivery",
    )
    is_active: Optional[bool] = Field(
        default=True,
        description="Whether the webhook is active",
    )


class OutgoingWebhookUpdate(BaseModel):
    """Schema for partially updating an outgoing webhook."""

    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Human-readable webhook name",
    )
    url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Destination URL",
    )
    secret: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Signing secret for payload signature verification",
    )
    events: Optional[str] = Field(
        default=None,
        description="JSON-encoded list of event types",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether the webhook is active",
    )


class OutgoingWebhookResponse(BaseModel):
    """Schema for outgoing webhook API responses.

    secret is masked to prevent exposure in API responses.
    """

    id: str
    company_id: str
    name: str
    url: str
    secret_masked: Optional[str] = Field(
        default=None,
        description="Masked signing secret (never exposed in full)",
    )
    events: Optional[str] = None
    is_active: Optional[bool] = None
    last_delivery_at: Optional[datetime] = None
    last_status: Optional[str] = None
    failure_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
