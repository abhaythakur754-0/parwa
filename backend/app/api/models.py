"""
Jarvis API — Pydantic Request / Response Models

Every endpoint has a typed model.  Validation lives here so the route
handlers stay clean and delegate-only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# Generic / Shared
# ═══════════════════════════════════════════════════════════════

class TenantQuery(BaseModel):
    """Most endpoints accept at least a tenant_id."""
    tenant_id: str = Field(default="default_tenant", description="Tenant identifier")


class OkResponse(BaseModel):
    ok: bool = True
    message: str = ""


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str = ""
    detail: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Chat & Commands
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    question: str
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


class MetricsQuery(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    days: int = Field(default=7, ge=1, le=365)


# ═══════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════

class NotificationsQuery(TenantQuery):
    include_resolved: bool = False


class BatchActionRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    batch_key: str


class BatchRejectRequest(BatchActionRequest):
    """Alias for semantic clarity — same shape."""
    pass


# ═══════════════════════════════════════════════════════════════
# Flags
# ═══════════════════════════════════════════════════════════════

class SetFlagRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    flag_type: str
    flag_value: str
    scope: str = "global"
    target_id: Optional[str] = None
    reason: str = ""
    expires_at: Optional[str] = None


class RevokeFlagRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")


# ═══════════════════════════════════════════════════════════════
# Control Commands
# ═══════════════════════════════════════════════════════════════

class PauseRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    target: str = Field(default="all")
    scope: str = "global"
    duration: Optional[str] = Field(default=None, description="e.g. '2h', '30m', 'today'")
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


class ResumeRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    target: str = Field(default="all")
    scope: str = "global"
    duration: Optional[str] = None
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


class RedirectRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    target: str = Field(description="Channel name, e.g. 'instagram', 'email', 'all'")
    handler: str = Field(default="ai", description="'ai' or 'human'")
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


class ModeRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    mode: str = Field(description="'shadow', 'supervised', or 'graduated'")
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


# ═══════════════════════════════════════════════════════════════
# Quality & Reports
# ═══════════════════════════════════════════════════════════════

class QualityScoresQuery(TenantQuery):
    days: int = Field(default=7, ge=1, le=365)


class ResolveAlertRequest(BaseModel):
    pass  # alert_id in path


class FeedbackRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    ticket_id: Optional[str] = None
    ticket_type: str = ""
    query: str = ""
    ai_response: str = ""
    correct_response: str = ""
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    signal_type: str = Field(default="approved", description="'approved' or 'rejected'")
    metadata: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════
# SLA
# ═══════════════════════════════════════════════════════════════

class SLAQuery(TenantQuery):
    days: int = Field(default=30, ge=1, le=365)


# ═══════════════════════════════════════════════════════════════
# Approvals
# ═══════════════════════════════════════════════════════════════

class ApprovalsPendingQuery(TenantQuery):
    pass


class ApprovalBatchRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    action: str = Field(description="'approve' or 'reject'")
    batch_key: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Emergency
# ═══════════════════════════════════════════════════════════════

class EmergencyShutdownRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="owner")


class PauseAllRefundsRequest(BaseModel):
    tenant_id: str = Field(default="default_tenant")
    user_email: str = Field(default="admin@parwa.ai")
    user_role: str = Field(default="admin")


# ═══════════════════════════════════════════════════════════════
# Audit
# ═══════════════════════════════════════════════════════════════

class AuditQuery(TenantQuery):
    limit: int = Field(default=50, ge=1, le=500)
    action: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# SSE Stream
# ═══════════════════════════════════════════════════════════════

class SSEEvent(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Ticket Submission (PARWA Pipeline)
# ═══════════════════════════════════════════════════════════════

class TicketSubmitRequest(BaseModel):
    """Submit a ticket to the PARWA pipeline.

    The pipeline runs inside the server process, so quality scores,
    notifications, and audit entries are written to the shared DB.
    """
    tenant_id: str = Field(default="default_tenant")
    query: str = Field(description="Customer query / ticket text")
    channel_type: str = Field(default="email", description="'email', 'chat', 'phone', etc.")
    variant_tier: str = Field(default="high", description="'mini', 'parwa', 'high'")
    customer_context: Dict[str, Any] = Field(default_factory=dict)
    sender: str = Field(default="", description="Customer email or identifier")


# ═══════════════════════════════════════════════════════════════
# Phase 9 — Onboarding
# ═══════════════════════════════════════════════════════════════

class AccountSetupRequest(BaseModel):
    """Step 1: Create a new tenant account."""
    company_name: str = Field(description="Legal company name")
    admin_email: str = Field(description="Admin user email (unique)")
    password: str = Field(min_length=8, description="Admin password (min 8 chars)")
    industry: str = Field(default="general", description="Industry vertical")
    company_size: str = Field(default="1-10", description="Company size bracket, e.g. '1-10', '11-50', '51-200'")


class SelectTierRequest(BaseModel):
    """Step 2: Choose pricing tier and billing cycle."""
    tenant_id: str = Field(description="Tenant ID from account setup")
    tier: str = Field(description="'mini', 'parwa', or 'high'")
    billing_cycle: str = Field(description="'monthly' or 'annual'")


class ConnectIntegrationRequest(BaseModel):
    """Step 3: Connect a third-party integration."""
    tenant_id: str = Field(description="Tenant ID")
    integration_type: str = Field(description="Integration name, e.g. 'shopify', 'zendesk', 'gorgias'")
    credentials: Dict[str, Any] = Field(default_factory=dict, description="Integration credentials / tokens")


class UploadKBRequest(BaseModel):
    """Step 4: Upload a knowledge base entry."""
    tenant_id: str = Field(description="Tenant ID")
    title: str = Field(description="Article / document title")
    category: str = Field(default="general", description="KB category, e.g. 'refund_policy', 'product_info'")
    content: str = Field(min_length=10, description="Full text content of the KB entry")


class SetPolicyRequest(BaseModel):
    """Step 5: Configure business policies."""
    tenant_id: str = Field(description="Tenant ID")
    policies: Dict[str, Any] = Field(
        description="Policy key-value pairs: refund_rules, escalation_triggers, "
                    "response_tone, business_hours, restricted_actions",
    )


class GenerateKeyRequest(BaseModel):
    """Step 6: Generate an additional API key."""
    tenant_id: str = Field(description="Tenant ID")
    key_type: str = Field(default="live", description="'live' or 'test'")
    name: str = Field(default="Onboarding Key", description="Human-readable key name")


class TestTicketRequest(BaseModel):
    """Step 6: Submit a test ticket through the pipeline."""
    tenant_id: str = Field(description="Tenant ID")
    query: str = Field(description="Test query / ticket text")


class LoginRequest(BaseModel):
    """Authenticate with email and password."""
    email: str = Field(description="Registered admin email")
    password: str = Field(description="Admin password")


class RegisterKeyRequest(BaseModel):
    """Generate a new API key (authenticated)."""
    tenant_id: str = Field(description="Tenant ID")
    key_type: str = Field(default="live", description="'live' or 'test'")
    name: str = Field(default="API Key", description="Human-readable key name")


class RevokeKeyRequest(BaseModel):
    """Revoke an API key (authenticated)."""
    tenant_id: str = Field(description="Tenant ID")
    key_id: str = Field(description="The key ID to revoke")
