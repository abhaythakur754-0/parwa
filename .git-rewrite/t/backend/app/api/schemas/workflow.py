"""
PARWA Workflow API Schemas (Week 10 Day 4)

Pydantic v2 request/response models for the Workflow API router.
These schemas provide type-safe serialization and validation for
all workflow-related endpoints.

Endpoints covered:
  - POST /execute              — Execute a workflow pipeline
  - GET  /state/{conv_id}       — Get current workflow state
  - POST /state/{conv_id}/transition — Force GSD state transition
  - GET  /context/health/{conv_id}  — Context health meter status
  - POST /context/compress     — Trigger context compression
  - GET  /metrics              — Technique execution metrics
  - GET  /metrics/leaderboard  — Technique leaderboard
  - GET  /metrics/variants     — Variant summaries
  - GET  /capacity/{company_id} — Capacity status
  - POST /capacity/{company_id}/configure — Capacity config
  - GET  /config/{company_id}  — Tenant config
  - PUT  /config/{company_id}/{category} — Update tenant config
  - GET  /gsd/{company_id}/{ticket_id}/transitions — GSD history
  - GET  /gsd/{company_id}/{ticket_id}/analytics  — GSD analytics
  - POST /migrate              — State migration
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class GSDStateValue(str, Enum):
    """Valid GSD state values for transitions."""
    NEW = "new"
    GREETING = "greeting"
    DIAGNOSIS = "diagnosis"
    RESOLUTION = "resolution"
    FOLLOW_UP = "follow_up"
    ESCALATE = "escalate"
    HUMAN_HANDOFF = "human_handoff"
    CLOSED = "closed"


class CompressionStrategy(str, Enum):
    """Compression strategy options."""
    EXTRACTIVE = "extractive"
    ABSTRACTIVE = "abstractive"
    HYBRID = "hybrid"
    SLIDING_WINDOW = "sliding_window"
    PRIORITY_BASED = "priority_based"


class HealthStatus(str, Enum):
    """Context health status levels."""
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


# ══════════════════════════════════════════════════════════════════
# WORKFLOW EXECUTION
# ══════════════════════════════════════════════════════════════════


class WorkflowExecuteRequest(BaseModel):
    """Request body for POST /execute.

    Executes a full workflow pipeline: GSD determination → technique
    routing → response generation.
    """

    conversation_id: str = Field(
        ...,
        description="Unique conversation identifier",
    )
    ticket_id: str = Field(
        ...,
        description="Associated ticket ID",
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Customer query text",
    )
    customer_tier: str = Field(
        default="free",
        description="Customer tier for escalation priority",
    )
    channel: str = Field(
        default="chat",
        description="Communication channel (chat, phone, email)",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (RAG results, signals, etc.)",
    )


class WorkflowExecuteResponse(BaseModel):
    """Response body for POST /execute."""

    status: str = Field(description="Execution status (ok, error)")
    conversation_id: str = Field(description="Conversation ID")
    ticket_id: str = Field(description="Ticket ID")
    gsd_state: str = Field(description="Current GSD state after execution")
    technique_used: Optional[str] = Field(
        None, description="Technique that was executed"
    )
    response: Optional[str] = Field(
        None, description="Generated response text"
    )
    token_usage: int = Field(default=0, description="Tokens consumed")
    execution_time_ms: float = Field(
        default=0.0, description="Total execution time in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata",
    )


# ══════════════════════════════════════════════════════════════════
# WORKFLOW STATE
# ══════════════════════════════════════════════════════════════════


class WorkflowStateResponse(BaseModel):
    """Response body for GET /state/{conversation_id}."""

    status: str = Field(description="Response status")
    conversation_id: str = Field(description="Conversation ID")
    ticket_id: Optional[str] = Field(
        None, description="Associated ticket ID"
    )
    company_id: Optional[str] = Field(
        None, description="Tenant company ID"
    )
    gsd_state: str = Field(description="Current GSD state")
    gsd_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="GSD state transition history",
    )
    technique_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Results from executed techniques",
    )
    token_usage: int = Field(default=0, description="Total tokens used")
    is_terminal: bool = Field(
        default=False,
        description="Whether the conversation is in a terminal state",
    )
    available_transitions: List[str] = Field(
        default_factory=list,
        description="Valid next GSD states from current state",
    )


class StateTransitionRequest(BaseModel):
    """Request body for POST /state/{conversation_id}/transition.

    Forces a GSD state transition, bypassing normal AI-driven
    determination. Useful for admin overrides and testing.
    """

    target_state: GSDStateValue = Field(
        ...,
        description="Target GSD state to transition to",
    )
    trigger_reason: str = Field(
        default="manual_override",
        description="Human-readable reason for the forced transition",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional transition metadata",
    )


class StateTransitionResponse(BaseModel):
    """Response body for POST /state/{conversation_id}/transition."""

    status: str = Field(description="Transition status")
    previous_state: str = Field(description="State before transition")
    current_state: str = Field(description="State after transition")
    trigger_reason: str = Field(description="Why the transition occurred")
    is_terminal: bool = Field(
        default=False,
        description="Whether the new state is terminal",
    )


# ══════════════════════════════════════════════════════════════════
# CONTEXT HEALTH
# ══════════════════════════════════════════════════════════════════


class HealthMetricsSchema(BaseModel):
    """Individual health metric measurements."""

    token_usage_ratio: float = Field(
        default=0.0, description="Token budget usage ratio"
    )
    compression_ratio: float = Field(
        default=1.0, description="Context compression ratio"
    )
    relevance_score: float = Field(
        default=1.0, description="Context relevance score"
    )
    freshness_score: float = Field(
        default=1.0, description="Context freshness score"
    )
    signal_preservation: float = Field(
        default=1.0, description="Signal preservation score"
    )
    context_coherence: float = Field(
        default=1.0, description="Context coherence score"
    )


class HealthAlertSchema(BaseModel):
    """A single context health alert."""

    alert_type: str = Field(description="Alert type identifier")
    severity: HealthStatus = Field(description="Alert severity level")
    message: str = Field(description="Human-readable alert message")
    metric_name: str = Field(description="Metric that triggered the alert")
    metric_value: float = Field(description="Current metric value")
    threshold: float = Field(description="Threshold that was crossed")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")


class ContextHealthResponse(BaseModel):
    """Response body for GET /context/health/{conversation_id}."""

    status: str = Field(description="Response status")
    conversation_id: str = Field(description="Conversation ID")
    company_id: str = Field(description="Tenant company ID")
    overall_score: float = Field(description="Weighted health score")
    health_status: HealthStatus = Field(description="Overall health status")
    metrics: HealthMetricsSchema = Field(
        description="Individual metric measurements"
    )
    alerts: List[HealthAlertSchema] = Field(
        default_factory=list, description="Active alerts"
    )
    turn_number: int = Field(default=0, description="Conversation turn number")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    recommendations: List[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


# ══════════════════════════════════════════════════════════════════
# CONTEXT COMPRESSION
# ══════════════════════════════════════════════════════════════════


class ContextCompressRequest(BaseModel):
    """Request body for POST /context/compress.

    Triggers context compression for a conversation to reduce
    token usage while preserving important information.
    """

    conversation_id: str = Field(
        ...,
        description="Conversation to compress",
    )
    content: List[str] = Field(
        ...,
        min_length=1,
        description="Content chunks to compress",
    )
    token_counts: Optional[List[int]] = Field(
        None,
        description="Token counts per chunk (auto-estimated if missing)",
    )
    priorities: Optional[List[float]] = Field(
        None,
        description="Priority weights per chunk (default 0.5)",
    )
    strategy: CompressionStrategy = Field(
        default=CompressionStrategy.HYBRID,
        description="Compression algorithm to use",
    )
    max_tokens: int = Field(
        default=2000,
        gt=0,
        description="Maximum tokens in compressed output",
    )


class ContextCompressResponse(BaseModel):
    """Response body for POST /context/compress."""

    status: str = Field(description="Compression status")
    conversation_id: str = Field(description="Conversation ID")
    original_token_count: int = Field(
        default=0, description="Tokens before compression"
    )
    compressed_token_count: int = Field(
        default=0, description="Tokens after compression"
    )
    compression_ratio: float = Field(
        default=1.0, description="Compressed/original ratio"
    )
    strategy_used: str = Field(description="Strategy that was applied")
    chunks_removed: int = Field(
        default=0, description="Number of chunks removed"
    )
    chunks_retained: int = Field(
        default=0, description="Number of chunks retained"
    )
    processing_time_ms: float = Field(
        default=0.0, description="Processing time in milliseconds"
    )


# ══════════════════════════════════════════════════════════════════
# TECHNIQUE METRICS
# ══════════════════════════════════════════════════════════════════


class TechniqueStatsSchema(BaseModel):
    """Aggregated statistics for a single technique."""

    technique_id: str = Field(description="Technique identifier")
    total_executions: int = Field(default=0)
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    timeout_count: int = Field(default=0)
    error_count: int = Field(default=0)
    total_tokens: int = Field(default=0)
    avg_exec_time_ms: float = Field(default=0.0)
    min_exec_time_ms: float = Field(default=0.0)
    max_exec_time_ms: float = Field(default=0.0)
    success_rate: float = Field(
        default=0.0, description="Success rate percentage"
    )


class MetricsResponse(BaseModel):
    """Response body for GET /metrics."""

    status: str = Field(description="Response status")
    techniques: List[TechniqueStatsSchema] = Field(
        default_factory=list,
        description="Per-technique aggregated stats",
    )
    total_executions: int = Field(default=0)
    total_tokens: int = Field(default=0)
    window: Optional[str] = Field(
        None, description="Time window applied (e.g. 5min, 1hr)"
    )
    percentiles: Dict[str, float] = Field(
        default_factory=lambda: {
            "p50": 0.0, "p95": 0.0, "p99": 0.0,
        },
        description="Execution time percentiles",
    )


class LeaderboardEntrySchema(BaseModel):
    """Single entry in a technique leaderboard."""

    rank: int = Field(description="Rank position (1-based)")
    technique_id: str = Field(description="Technique identifier")
    value: float = Field(description="Metric value")
    label: str = Field(description="Metric label (e.g. total_executions)")


class LeaderboardResponse(BaseModel):
    """Response body for GET /metrics/leaderboard."""

    status: str = Field(description="Response status")
    sort_by: str = Field(description="Metric used for sorting")
    entries: List[LeaderboardEntrySchema] = Field(
        default_factory=list, description="Ranked technique entries"
    )
    total_techniques: int = Field(default=0)


class VariantSummarySchema(BaseModel):
    """Aggregated summary for a single variant."""

    variant: str = Field(description="Variant name")
    total_executions: int = Field(default=0)
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    total_tokens: int = Field(default=0)
    total_exec_time_ms: float = Field(default=0.0)
    success_rate: float = Field(default=0.0)
    technique_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Per-technique execution counts",
    )


class VariantMetricsResponse(BaseModel):
    """Response body for GET /metrics/variants."""

    status: str = Field(description="Response status")
    variants: List[VariantSummarySchema] = Field(
        default_factory=list, description="Per-variant summaries"
    )


# ══════════════════════════════════════════════════════════════════
# CAPACITY
# ══════════════════════════════════════════════════════════════════


class CapacityVariantStatus(BaseModel):
    """Capacity status for a single variant."""

    variant: str = Field(description="Variant name")
    used: int = Field(description="Currently active slots")
    total: int = Field(description="Maximum concurrent slots")
    available: int = Field(description="Available slots")
    percentage: float = Field(description="Utilization percentage")
    queue_size: int = Field(
        default=0, description="Items waiting in queue"
    )


class CapacityStatusResponse(BaseModel):
    """Response body for GET /capacity/{company_id}."""

    status: str = Field(description="Response status")
    company_id: str = Field(description="Tenant company ID")
    variants: List[CapacityVariantStatus] = Field(
        default_factory=list, description="Per-variant capacity"
    )
    has_overflow: bool = Field(
        default=False, description="Whether any variant is overflowing"
    )
    total_queued: int = Field(default=0, description="Total queued items")
    alerts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Active capacity alerts"
    )
    scaling_suggestion: Optional[Dict[str, Any]] = Field(
        None, description="Auto-scaling recommendation if overflow"
    )


class CapacityConfigureRequest(BaseModel):
    """Request body for POST /capacity/{company_id}/configure.

    Sets custom capacity limits for one or more variants.
    """

    variant: str = Field(
        ...,
        description="Variant to configure",
    )
    max_concurrent: int = Field(
        ...,
        gt=0,
        description="Maximum concurrent executions",
    )


class CapacityConfigureResponse(BaseModel):
    """Response body for POST /capacity/{company_id}/configure."""

    status: str = Field(description="Configuration status")
    company_id: str = Field(description="Tenant company ID")
    variant: str = Field(description="Configured variant")
    max_concurrent: int = Field(description="New max concurrent limit")


# ══════════════════════════════════════════════════════════════════
# TENANT CONFIG
# ══════════════════════════════════════════════════════════════════


class TenantConfigResponse(BaseModel):
    """Response body for GET /config/{company_id}.

    Returns the full merged tenant configuration including
    variant defaults and per-company overrides.
    """

    status: str = Field(description="Response status")
    company_id: str = Field(description="Tenant company ID")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full merged configuration by category",
    )
    version: int = Field(default=0, description="Config version number")
    variant_type: str = Field(
        default="parwa", description="Active variant type"
    )


class TenantConfigUpdateRequest(BaseModel):
    """Request body for PUT /config/{company_id}/{category}.

    Updates configuration within a specific category.
    Only provided fields will be updated; others remain unchanged.
    """

    config: Dict[str, Any] = Field(
        ...,
        description="Partial or full config dict for the category",
    )


class TenantConfigUpdateResponse(BaseModel):
    """Response body for PUT /config/{company_id}/{category}."""

    status: str = Field(description="Update status")
    company_id: str = Field(description="Tenant company ID")
    category: str = Field(description="Updated category")
    version: int = Field(description="New config version")
    updated_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Updated configuration for this category",
    )


# ══════════════════════════════════════════════════════════════════
# GSD TRANSITIONS & ANALYTICS
# ══════════════════════════════════════════════════════════════════


class GSDTransitionEntry(BaseModel):
    """A single GSD transition record."""

    state: str = Field(description="State after transition")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")
    trigger: str = Field(description="Reason for the transition")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class GSDTransitionsResponse(BaseModel):
    """Response body for GET /gsd/{company_id}/{ticket_id}/transitions."""

    status: str = Field(description="Response status")
    company_id: str = Field(description="Tenant company ID")
    ticket_id: str = Field(description="Ticket ID")
    transitions: List[GSDTransitionEntry] = Field(
        default_factory=list, description="Ordered transition history"
    )
    total_transitions: int = Field(
        default=0, description="Total number of transitions"
    )


class GSDAnalyticsResponse(BaseModel):
    """Response body for GET /gsd/{company_id}/{ticket_id}/analytics.

    Provides transition reasoning, signal snapshots, and
    conversation-level analytics.
    """

    status: str = Field(description="Response status")
    company_id: str = Field(description="Tenant company ID")
    ticket_id: str = Field(description="Ticket ID")
    current_state: str = Field(description="Current GSD state")
    recommended_next_state: str = Field(
        description="AI-recommended next state"
    )
    variant: str = Field(description="Active variant type")
    reasoning_chain: List[Dict[str, Any]] = Field(
        default_factory=list, description="Step-by-step reasoning"
    )
    signals_snapshot: Dict[str, Any] = Field(
        default_factory=dict, description="Current signal values"
    )
    escalation_conditions_met: bool = Field(
        default=False, description="Whether escalation is warranted"
    )
    diagnosis_loop_count: int = Field(
        default=0, description="Number of diagnosis loop entries"
    )
    time_in_current_state_seconds: float = Field(
        default=0.0, description="Time spent in current state"
    )
    estimated_resolution_time_minutes: int = Field(
        default=0, description="Estimated time to resolution"
    )
    state_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of visits per state",
    )


# ══════════════════════════════════════════════════════════════════
# STATE MIGRATION
# ══════════════════════════════════════════════════════════════════


class StateMigrateRequest(BaseModel):
    """Request body for POST /migrate.

    Migrates a conversation state to the latest schema version.
    Supports dry-run mode for preview.
    """

    state: Dict[str, Any] = Field(
        ...,
        description="The state dictionary to migrate",
    )
    target_version: Optional[int] = Field(
        None,
        description="Target schema version (defaults to latest)",
    )
    dry_run: bool = Field(
        default=False,
        description="Preview changes without applying",
    )


class StateMigrateResponse(BaseModel):
    """Response body for POST /migrate."""

    status: str = Field(description="Migration status")
    success: bool = Field(description="Whether migration succeeded")
    from_version: int = Field(description="Source schema version")
    to_version: int = Field(description="Target schema version")
    changes_made: List[str] = Field(
        default_factory=list, description="List of changes applied"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Migration warnings"
    )
    state_after: Dict[str, Any] = Field(
        default_factory=dict,
        description="The state after migration (or preview)",
    )


# ══════════════════════════════════════════════════════════════════
# LANGGRAPH MULTI-AGENT PROCESSING
# ══════════════════════════════════════════════════════════════════


class LangGraphProcessRequest(BaseModel):
    """Request body for POST /langgraph/process.

    Processes a customer message through the multi-agent LangGraph
    system with variant_tier-driven routing, MAKER validation,
    and tier-aware approval workflows.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Raw incoming message from customer",
    )
    channel: str = Field(
        default="email",
        description="Origin channel: email, sms, voice, chat, api",
    )
    customer_id: str = Field(
        ...,
        description="Customer identifier",
    )
    variant_tier: str = Field(
        default="mini",
        description="Variant tier: mini, pro, high",
    )
    customer_tier: str = Field(
        default="free",
        description="Customer segment: free, pro, enterprise, vip",
    )
    industry: str = Field(
        default="general",
        description="Industry vertical",
    )
    language: str = Field(
        default="en",
        description="Language code (en, hi, es, etc.)",
    )
    conversation_id: str = Field(
        default="",
        description="Conversation ID (empty = new conversation)",
    )
    ticket_id: str = Field(
        default="",
        description="Ticket ID (empty = new ticket)",
    )
    session_id: str = Field(
        default="",
        description="Session ID (empty = new session)",
    )


class LangGraphProcessResponse(BaseModel):
    """Response body for POST /langgraph/process.

    Returns the final state after the LangGraph multi-agent
    system has processed the message through all nodes (24 groups, ~155 fields).
    """

    status: str = Field(description="Processing status (ok, error)")
    conversation_id: str = Field(description="Conversation ID")
    ticket_id: str = Field(description="Ticket ID")
    variant_tier: str = Field(description="Variant tier used")
    intent: str = Field(default="general", description="Classified intent")
    target_agent: str = Field(default="faq", description="Domain agent selected")
    agent_response: str = Field(default="", description="Generated response")
    delivery_status: str = Field(
        default="pending", description="Delivery status",
    )
    delivery_channel: str = Field(
        default="", description="Actual delivery channel",
    )
    maker_mode: str = Field(
        default="", description="MAKER mode used (efficiency/balanced/conservative)",
    )
    approval_decision: str = Field(
        default="", description="Control system approval decision",
    )
    sentiment_score: float = Field(
        default=0.5, description="Sentiment score 0.0-1.0",
    )
    tokens_consumed: int = Field(default=0, description="Total tokens consumed")
    error: str = Field(default="", description="Error message, if any")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional processing metadata",
    )
    # New fields from 24-group ParwaGraphState
    gsd_state: str = Field(
        default="new", description="Current GSD state after processing",
    )
    urgency: str = Field(
        default="low", description="Urgency classification",
    )
    agent_confidence: float = Field(
        default=0.0, description="Agent confidence score 0.0-1.0",
    )
    red_flag: bool = Field(
        default=False, description="Whether MAKER detected a red flag",
    )
    guardrails_passed: bool = Field(
        default=False, description="Whether guardrails checks passed",
    )
    system_mode: str = Field(
        default="auto", description="System mode: auto, supervised, shadow, paused",
    )
    k_value_used: int = Field(
        default=0, description="K value used by MAKER validator",
    )
    trust_score: float = Field(
        default=1.0, description="Trust score for the interaction 0.0-1.0",
    )
    tcpa_consent_verified: bool = Field(
        default=False, description="Whether TCPA consent was verified for SMS",
    )
    call_id: str = Field(
        default="", description="Voice call identifier (if voice channel)",
    )
