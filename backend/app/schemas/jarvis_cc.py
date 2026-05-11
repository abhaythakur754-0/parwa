"""
PARWA Jarvis Customer Care Schemas

Pydantic models for Jarvis Customer Care API validation.
Separate from onboarding schemas (jarvis.py) because CC mode
has fundamentally different request/response shapes.

Covers:
- CC Session creation and response
- CC Message send (with ticket_id + channel context)
- CC Message response (with pipeline metadata)
- CC Context get/update
- CC Session health
- CC History (paginated)
- Awareness Engine tick/snapshot/alert schemas (Phase 2.1)

Based on: jarvis_cc_service.py Phase 1.2, jarvis_awareness_engine.py Phase 2.1
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Validators ─────────────────────────────────────────────────────

_VALID_CC_CHANNELS = ("chat", "email", "sms", "voice", "whatsapp", "social")
_VALID_CC_MESSAGE_TYPES = (
    "text", "variant_pipeline", "ai_generated", "direct_ai",
    "error", "proactive_alert", "command_response",
)


# ── CC Session Schemas ─────────────────────────────────────────────


class JarvisCCSessionCreate(BaseModel):
    """Request to create or resume a customer care session.

    After onboarding handoff, the client creates a CC session.
    If an active CC session exists for this user+company, it is resumed.
    """

    existing_session_id: Optional[str] = Field(
        default=None,
        description="Resume a specific session by ID (optional)",
    )


class JarvisCCSessionResponse(BaseModel):
    """Customer care session details with context and limits."""

    id: str
    type: str = "customer_care"
    context: Dict[str, Any] = Field(default_factory=dict)
    message_count_today: int = 0
    total_message_count: int = 0
    remaining_today: int = 5000
    is_active: bool = True
    variant_tier: str = "mini_parwa"
    industry: str = "general"
    awareness_enabled: bool = False
    pipeline_status: str = "unknown"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ── CC Message Schemas ─────────────────────────────────────────────


class JarvisCCMessageSend(BaseModel):
    """User sends a message to Jarvis in customer care mode.

    Extends the onboarding message with ticket_id and channel
    context — critical for CC mode where messages may be tied
    to specific support tickets and channels.
    """

    content: str = Field(
        min_length=1,
        max_length=10000,
        description="User message text",
    )
    session_id: str = Field(
        description="Customer care session ID (required for CC mode)",
    )
    ticket_id: Optional[str] = Field(
        default=None,
        description="Ticket ID if message is within a ticket context",
    )
    channel: str = Field(
        default="chat",
        description="Communication channel",
    )

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_CC_CHANNELS:
            raise ValueError(
                f"Invalid channel. "
                f"Must be one of: {', '.join(_VALID_CC_CHANNELS)}"
            )
        return v


class JarvisCCMessageResponse(BaseModel):
    """AI response message with pipeline metadata.

    Unlike onboarding responses, CC responses include rich
    pipeline metadata (quality score, technique, latency, etc.)
    so the dashboard can display operational metrics.
    """

    id: str
    session_id: str
    role: str
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pipeline_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline execution metadata (quality, latency, technique)",
    )
    timestamp: Optional[str] = None

    model_config = {"from_attributes": True}


class JarvisCCHistoryResponse(BaseModel):
    """Paginated chat history for a customer care session."""

    messages: List[JarvisCCMessageResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


# ── CC Context Schemas ─────────────────────────────────────────────


class JarvisCCContextResponse(BaseModel):
    """Customer care session context with runtime enrichment.

    Includes both stored context (variant_tier, industry, etc.)
    and runtime-enriched data (instance status, ticket counts,
    emergency state).
    """

    session_id: str
    variant_tier: str = "mini_parwa"
    variant_instance_id: str = ""
    industry: str = "general"
    mode: str = "customer_care"
    awareness_enabled: bool = False
    pipeline_status: str = "unknown"
    last_pipeline_metadata: Dict[str, Any] = Field(default_factory=dict)
    proactive_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    runtime: Dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime-enriched data (instance status, tickets, emergency)",
    )
    full_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete raw context JSON",
    )


class JarvisCCContextUpdate(BaseModel):
    """Partial update to customer care session context.

    Only provided fields are merged into existing context.
    Protected keys (variant_tier, variant_instance_id, industry)
    cannot be set to None — they require explicit non-null values.
    """

    awareness_enabled: Optional[bool] = None
    proactive_alerts: Optional[List[Dict[str, Any]]] = None
    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom key-value pairs to merge into context",
    )

    @field_validator("custom_fields")
    @classmethod
    def custom_fields_must_be_dict(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is not None and len(v) > 50:
            raise ValueError("Custom fields cannot exceed 50 keys")
        return v


# ── CC Health Schemas ──────────────────────────────────────────────


class JarvisCCInstanceHealth(BaseModel):
    """Variant instance health within CC session."""

    status: str = "unknown"
    active_tickets: int = 0
    total_handled: int = 0
    last_activity: Optional[str] = None


class JarvisCCSessionHealthResponse(BaseModel):
    """Health status of a customer care session.

    Used by the dashboard to display operational metrics
    and alert on issues.
    """

    session_id: str
    is_active: bool = True
    session_type: str = "customer_care"
    variant_tier: str = "unknown"
    industry: str = "unknown"
    messages_today: int = 0
    total_messages: int = 0
    daily_limit: int = 5000
    daily_remaining: int = 5000
    last_message_at: Optional[str] = None
    pipeline_status: str = "unknown"
    last_quality_score: Optional[float] = None
    awareness_enabled: bool = False
    ai_paused: bool = False
    instance: Optional[JarvisCCInstanceHealth] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════
# AWARENESS ENGINE SCHEMAS (Phase 2.1)
# ══════════════════════════════════════════════════════════════════


_VALID_TICK_TYPES = ("periodic", "on_change", "manual", "emergency")
_VALID_ALERT_SEVERITIES = ("info", "warning", "critical", "emergency")
_VALID_ALERT_STATUSES = ("active", "acknowledged", "dismissed", "resolved", "expired")
_VALID_ALERT_CATEGORIES = (
    "system_health", "ticket_volume", "agent_pool",
    "quality", "drift", "billing", "security", "integration",
)


class JarvisAwarenessTickRequest(BaseModel):
    """Request to manually trigger an awareness tick.

    Used by the dashboard to force an awareness refresh
    (e.g., when user navigates to the monitoring view)
    or by the system for on_change/emergency ticks.
    """

    session_id: str = Field(
        description="Customer care session ID to tick",
    )
    tick_type: str = Field(
        default="manual",
        description="Type of tick: periodic, on_change, manual, emergency",
    )

    @field_validator("tick_type")
    @classmethod
    def tick_type_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_TICK_TYPES:
            raise ValueError(
                f"Invalid tick_type. Must be one of: {', '.join(_VALID_TICK_TYPES)}"
            )
        return v


class JarvisAwarenessTickResponse(BaseModel):
    """Response from an awareness tick.

    Contains the snapshot ID, tick metadata, and any alerts
    that were generated during this tick.
    """

    snapshot_id: str
    tick_type: str
    tick_number: int
    alerts_created: int = 0
    alert_ids: List[str] = Field(default_factory=list)
    system_health: str = "unknown"
    quality_score: Optional[float] = None
    drift_score: Optional[float] = None
    delta_significant: bool = False
    total_ms: float = 0.0


class JarvisAwarenessSnapshotResponse(BaseModel):
    """Single awareness snapshot from the Awareness Engine.

    Maps the JarvisAwarenessSnapshot ORM model to an API response.
    Includes all 7 monitoring domain fields plus metadata.
    """

    id: str
    session_id: str
    company_id: str
    snapshot_type: str = "periodic"
    tick_number: Optional[int] = None

    # Domain 1: Plan & Subscription
    current_plan: Optional[str] = None
    plan_usage_today: Optional[float] = None
    subscription_status: Optional[str] = None
    days_until_renewal: Optional[int] = None

    # Domain 2: System Health
    system_health: str = "unknown"
    channel_health: Dict[str, str] = Field(default_factory=dict)
    active_alerts_count: int = 0
    active_alerts: List[Dict[str, Any]] = Field(default_factory=list)

    # Domain 3: Ticket Volume
    ticket_volume_today: int = 0
    ticket_volume_avg: Optional[float] = None
    ticket_volume_spike: bool = False

    # Domain 4: Agent Pool
    active_agents: int = 0
    agent_pool_capacity: int = 0
    agent_pool_utilization: Optional[float] = None

    # Domain 5: Training
    training_running: bool = False
    training_mistake_count: int = 0
    training_model_version: Optional[str] = None

    # Domain 6: Drift & Quality
    drift_status: str = "none"
    drift_score: Optional[float] = None
    quality_score: Optional[float] = None
    quality_alerts: List[Dict[str, Any]] = Field(default_factory=list)

    # Domain 7: Errors
    last_5_errors: List[Dict[str, Any]] = Field(default_factory=list)

    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class JarvisAwarenessSnapshotListResponse(BaseModel):
    """Paginated list of awareness snapshots."""

    snapshots: List[JarvisAwarenessSnapshotResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class JarvisProactiveAlertResponse(BaseModel):
    """Proactive alert from the Awareness Engine.

    Unlike JarvisMessage (user-initiated), proactive alerts
    are system-initiated — Jarvis noticed something and is
    proactively telling the user about it.
    """

    id: str
    session_id: str
    company_id: str
    alert_type: str
    severity: str = "info"
    category: str = "system_health"
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    action_required: bool = False
    action_url: Optional[str] = None
    ttl_seconds: int = 0
    related_snapshot_id: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class JarvisProactiveAlertListResponse(BaseModel):
    """Paginated list of proactive alerts."""

    alerts: List[JarvisProactiveAlertResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class JarvisAlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""

    alert_id: str = Field(description="Alert ID to acknowledge")


class JarvisAlertDismissRequest(BaseModel):
    """Request to dismiss an alert."""

    alert_id: str = Field(description="Alert ID to dismiss")


class JarvisAlertResolveRequest(BaseModel):
    """Request to resolve an alert."""

    alert_id: str = Field(description="Alert ID to resolve")


class JarvisAwarenessDeltaResponse(BaseModel):
    """Delta between two awareness states.

    Shows what changed between the previous and current tick,
    including threshold crossings and recovered fields.
    """

    changed_fields: Dict[str, Any] = Field(default_factory=dict)
    has_significant_changes: bool = False
    new_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    recovered: List[Dict[str, Any]] = Field(default_factory=list)
    is_first_tick: bool = False
