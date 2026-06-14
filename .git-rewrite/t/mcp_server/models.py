"""
PARWA MCP Server — Pydantic Schemas

All request/response models for the MCP protocol and sub-servers.
MCP (Model Context Protocol) defines a standardized interface for
external AI tool integrations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# MCP Protocol Core Models
# ═══════════════════════════════════════════════════════════════════


class ToolCategory(str, Enum):
    """Categories of MCP tools."""
    KNOWLEDGE = "knowledge"
    INTEGRATION = "integration"
    TOOL = "tool"


class ToolStatus(str, Enum):
    """Operational status of a tool."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"


class ToolDefinition(BaseModel):
    """Schema for a single MCP tool definition."""
    name: str = Field(..., description="Unique tool identifier (e.g. 'faq_search')")
    description: str = Field(..., description="Human-readable description of what the tool does")
    category: ToolCategory = Field(..., description="Tool category")
    server: str = Field(..., description="Name of the sub-server that owns this tool")
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing the tool's input parameters",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing the tool's output",
    )
    status: ToolStatus = Field(default=ToolStatus.ACTIVE)
    version: str = Field(default="1.0.0")
    tags: list[str] = Field(default_factory=list, description="Searchable tags for discovery")


class ServerInfo(BaseModel):
    """Schema for a registered MCP sub-server."""
    name: str = Field(..., description="Unique server identifier")
    description: str = Field(..., description="Human-readable server description")
    category: ToolCategory = Field(..., description="Server category")
    tool_count: int = Field(default=0, description="Number of registered tools")
    status: ToolStatus = Field(default=ToolStatus.ACTIVE)
    version: str = Field(default="1.0.0")


class ToolInvokeRequest(BaseModel):
    """Schema for invoking an MCP tool."""
    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters matching the tool's input_schema",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional invocation context (tenant, user, etc.)",
    )


class ToolInvokeResponse(BaseModel):
    """Schema for a tool invocation response."""
    success: bool = Field(..., description="Whether the invocation succeeded")
    tool_name: str = Field(..., description="Name of the invoked tool")
    data: Any = Field(default=None, description="Tool output data")
    error: str | None = Field(default=None, description="Error message if invocation failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Invocation metadata (latency, tokens, etc.)",
    )


class ToolsListResponse(BaseModel):
    """Schema for listing all available tools."""
    tools: list[ToolDefinition] = Field(default_factory=list)
    total: int = Field(default=0)
    categories: list[str] = Field(default_factory=list)


class ServersListResponse(BaseModel):
    """Schema for listing all registered sub-servers."""
    servers: list[ServerInfo] = Field(default_factory=list)
    total: int = Field(default=0)


# ═══════════════════════════════════════════════════════════════════
# Health & System Models
# ═══════════════════════════════════════════════════════════════════


class HealthResponse(BaseModel):
    """Schema for health check responses."""
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    service: str = "parwa-mcp"
    version: str = "1.0.0"
    environment: str = "development"
    uptime_seconds: float = 0.0
    registered_servers: int = 0
    registered_tools: int = 0
    backend_reachable: bool | None = None


# ═══════════════════════════════════════════════════════════════════
# Knowledge Sub-server Models
# ═══════════════════════════════════════════════════════════════════


class FAQSearchRequest(BaseModel):
    """Request to search FAQs."""
    query: str = Field(..., min_length=1, description="Search query")
    category: str | None = Field(default=None, description="Filter by FAQ category")
    limit: int = Field(default=5, ge=1, le=50, description="Max results to return")
    language: str = Field(default="en", description="Response language")


class FAQSearchResult(BaseModel):
    """A single FAQ search result."""
    id: str = ""
    question: str = ""
    answer: str = ""
    category: str = ""
    confidence: float = 0.0
    source: str = "faq"


class RAGQueryRequest(BaseModel):
    """Request to query the RAG pipeline."""
    query: str = Field(..., min_length=1, description="Natural language query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")
    knowledge_base_id: str | None = Field(default=None, description="Specific KB to query")
    filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters")


class RAGQueryResult(BaseModel):
    """A single RAG retrieval result."""
    content: str = ""
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class KBQueryRequest(BaseModel):
    """Request to query a knowledge base."""
    query: str = Field(..., min_length=1, description="Search query")
    knowledge_base_ids: list[str] = Field(
        default_factory=list,
        description="Specific KB IDs to search (empty = all)",
    )
    search_type: Literal["semantic", "keyword", "hybrid"] = Field(
        default="hybrid",
        description="Search strategy",
    )
    limit: int = Field(default=10, ge=1, le=100)


class KBDocument(BaseModel):
    """A knowledge base document."""
    id: str = ""
    title: str = ""
    content: str = ""
    knowledge_base_id: str = ""
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Integration Sub-server Models
# ═══════════════════════════════════════════════════════════════════


class EmailSendRequest(BaseModel):
    """Request to send an email."""
    to: list[str] = Field(..., min_length=1, description="Recipient addresses")
    subject: str = Field(..., min_length=1, description="Email subject")
    body: str = Field(..., min_length=1, description="Email body (HTML or plain)")
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    reply_to: str | None = Field(default=None)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    template_id: str | None = Field(default=None, description="Email template to use")
    template_data: dict[str, Any] = Field(default_factory=dict)


class EmailSendResponse(BaseModel):
    """Response from sending an email."""
    message_id: str = ""
    status: str = "sent"
    recipients: list[str] = Field(default_factory=list)


class VoiceCallRequest(BaseModel):
    """Request to initiate a voice call."""
    to: str = Field(..., description="Phone number to call")
    from_number: str | None = Field(default=None, description="Caller ID number")
    message: str = Field(default="", description="Initial TTS message")
    language: str = Field(default="en-US")
    webhook_url: str | None = Field(default=None, description="Status callback URL")


class VoiceCallResponse(BaseModel):
    """Response from initiating a voice call."""
    call_sid: str = ""
    status: str = "initiated"
    to: str = ""


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    conversation_id: str | None = Field(default=None, description="Existing conversation")
    message: str = Field(..., min_length=1, description="Message text")
    channel: str = Field(default="chat_widget", description="Chat channel source")
    customer_id: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    """Response from sending a chat message."""
    conversation_id: str = ""
    message_id: str = ""
    reply: str = ""
    is_ai_generated: bool = False
    confidence: float = 0.0


class TicketCreateRequest(BaseModel):
    """Request to create a support ticket."""
    subject: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    priority: Literal["low", "medium", "high", "urgent"] = Field(default="medium")
    category: str | None = Field(default=None)
    customer_id: str | None = Field(default=None)
    channel: str = Field(default="api")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketResponse(BaseModel):
    """Response for a ticket operation."""
    ticket_id: str = ""
    status: str = ""
    subject: str = ""
    priority: str = ""
    message: str = ""


class EcommerceOrderRequest(BaseModel):
    """Request to look up an e-commerce order."""
    order_id: str = Field(..., description="Platform order ID")
    platform: Literal["shopify", "woocommerce", "magento", "bigcommerce"] = Field(
        default="shopify",
    )
    include_items: bool = Field(default=True)
    include_customer: bool = Field(default=False)


class EcommerceOrderResponse(BaseModel):
    """Response with order details."""
    order_id: str = ""
    platform: str = ""
    status: str = ""
    total: float = 0.0
    currency: str = "USD"
    items: list[dict[str, Any]] = Field(default_factory=list)
    customer: dict[str, Any] | None = None


class CRMContactRequest(BaseModel):
    """Request to look up a CRM contact."""
    contact_id: str | None = Field(default=None, description="CRM contact ID")
    email: str | None = Field(default=None, description="Contact email")
    phone: str | None = Field(default=None, description="Contact phone")
    platform: Literal["hubspot", "salesforce", "pipedrive"] = Field(default="hubspot")


class CRMContactResponse(BaseModel):
    """Response with CRM contact details."""
    contact_id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    notes: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Tool Sub-server Models
# ═══════════════════════════════════════════════════════════════════


class AnalyticsQueryRequest(BaseModel):
    """Request for analytics data."""
    metric: str = Field(..., description="Metric name (e.g. 'csat', 'resolution_time')")
    period: Literal["1h", "6h", "24h", "7d", "30d", "90d"] = Field(default="24h")
    granularity: Literal["minute", "hour", "day"] = Field(default="hour")
    filters: dict[str, Any] = Field(default_factory=dict)


class AnalyticsQueryResponse(BaseModel):
    """Response with analytics data."""
    metric: str = ""
    period: str = ""
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class MonitoringStatusRequest(BaseModel):
    """Request for system monitoring status."""
    component: str | None = Field(default=None, description="Specific component to check")
    include_metrics: bool = Field(default=True)


class MonitoringStatusResponse(BaseModel):
    """Response with monitoring status."""
    components: list[dict[str, Any]] = Field(default_factory=list)
    overall_status: str = "healthy"
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class NotificationSendRequest(BaseModel):
    """Request to send a notification."""
    recipient_type: Literal["agent", "customer", "admin", "channel"] = Field(...)
    recipient_id: str = Field(..., description="Recipient identifier")
    title: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    channel: Literal["in_app", "email", "sms", "push", "webhook"] = Field(
        default="in_app",
    )
    priority: Literal["low", "normal", "high", "urgent"] = Field(default="normal")
    data: dict[str, Any] = Field(default_factory=dict)


class NotificationSendResponse(BaseModel):
    """Response from sending a notification."""
    notification_id: str = ""
    status: str = "sent"
    channel: str = ""


class ComplianceCheckRequest(BaseModel):
    """Request to run a compliance check."""
    check_type: Literal["gdpr", "pii_scan", "data_retention", "audit_log", "consent"] = Field(
        ...,
        description="Type of compliance check to run",
    )
    target_id: str | None = Field(default=None, description="Specific resource to check")
    scope: Literal["single", "company", "global"] = Field(default="single")


class ComplianceCheckResponse(BaseModel):
    """Response from a compliance check."""
    check_type: str = ""
    status: Literal["pass", "fail", "warning"] = "pass"
    findings: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str = ""


class SLACheckRequest(BaseModel):
    """Request to check SLA status."""
    ticket_id: str | None = Field(default=None, description="Specific ticket to check")
    policy_id: str | None = Field(default=None, description="Specific SLA policy")
    include_breached: bool = Field(default=False, description="Include breached tickets")


class SLACheckResponse(BaseModel):
    """Response with SLA status."""
    policy_name: str = ""
    current_breaches: int = 0
    at_risk_count: int = 0
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Shared Response Envelope
# ═══════════════════════════════════════════════════════════════════


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    error: dict[str, Any] = Field(..., description="Error details")
