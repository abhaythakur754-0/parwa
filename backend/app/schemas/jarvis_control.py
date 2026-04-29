"""
PARWA Jarvis Control Schemas (Week 14 Day 1 — Jarvis Command Center)

Pydantic models for the Jarvis Command Center API validation.

Covers:
- Command parsing requests/responses (F-087)
- System status requests/responses (F-088)
- GSD terminal requests/responses (F-089)

Building Codes: BC-001 (tenant isolation), BC-011 (auth), BC-012 (error handling)
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════════════
# F-087: Jarvis Command Parser Schemas
# ══════════════════════════════════════════════════════════════════

VALID_COMMAND_TYPES = {
    "show_status",
    "system_status",
    "list_errors",
    "show_errors",
    "restart_agent",
    "escalate_ticket",
    "train_from_error",
    "list_tickets",
    "show_tickets",
    "get_ticket",
    "assign_ticket",
    "close_ticket",
    "reopen_ticket",
    "list_agents",
    "show_agents",
    "analytics",
    "show_analytics",
    "query_analytics",
    "health_check",
    "ping",
    "uptime",
    "list_integrations",
    "show_integrations",
    "check_integration",
    "enable_integration",
    "disable_integration",
    "list_queues",
    "show_queues",
    "purge_queue",
    "list_incidents",
    "show_incidents",
    "resolve_incident",
    "show_config",
    "get_config",
    "set_config",
    "show_logs",
    "get_logs",
    "export_logs",
    "show_usage",
    "usage_summary",
    "cost_report",
    "train_model",
    "retrain",
    "evaluate_model",
    "restart_service",
    "deploy",
    "rollback",
    "help",
    "commands",
    "list_commands",
    "unknown",
}


class JarvisCommandRequest(BaseModel):
    """Request body for parsing a natural language command.

    The operator sends a free-text command like "show status" or
    "restart agent X" and the parser returns a structured action.
    """

    command: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural language command from the operator",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context (e.g., current view, selected ticket)",
    )
    auto_execute: bool = Field(
        default=False,
        description="Whether to auto-execute if confidence >= threshold",
    )


class CommandParam(BaseModel):
    """A single extracted parameter from a parsed command."""

    name: str = Field(description="Parameter name (e.g., 'ticket_id', 'agent_id')")
    value: str = Field(description="Extracted parameter value")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence that this extraction is correct",
    )


class JarvisCommandResponse(BaseModel):
    """Parsed command result with structured action."""

    command_type: str = Field(description="Resolved command type")
    original_command: str = Field(description="Original input text")
    params: List[CommandParam] = Field(
        default_factory=list,
        description="Extracted parameters",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the parse result (0.0-1.0)",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether this command needs operator confirmation",
    )
    execution_summary: str = Field(
        default="",
        description="Human-readable summary of what will happen",
    )
    aliases_matched: List[str] = Field(
        default_factory=list,
        description="Any command aliases that matched",
    )


class AvailableCommandInfo(BaseModel):
    """Description of an available Jarvis command."""

    command_type: str = Field(description="Command type identifier")
    description: str = Field(description="What the command does")
    category: str = Field(description="Command category")
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternative ways to invoke this command",
    )
    params: List[str] = Field(
        default_factory=list,
        description="Expected parameter names",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether confirmation is required",
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Example invocations",
    )


class AvailableCommandsResponse(BaseModel):
    """List of all available Jarvis commands."""

    commands: List[AvailableCommandInfo]
    total: int = 0


# ══════════════════════════════════════════════════════════════════
# F-088: System Status Service Schemas
# ══════════════════════════════════════════════════════════════════

VALID_SUBSYSTEM_STATUSES = ("healthy", "degraded", "unhealthy", "unknown")


class SubsystemStatusInfo(BaseModel):
    """Health status of a single subsystem."""

    name: str = Field(description="Subsystem identifier")
    status: str = Field(description="Health status")
    latency_ms: float = Field(default=0.0)
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = Field(default=None)
    is_critical: bool = Field(default=True)
    checked_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of the check",
    )


class SystemStatusResponse(BaseModel):
    """Aggregated system health status (F-088)."""

    overall_status: str = Field(description="Aggregate health status")
    subsystems: Dict[str, SubsystemStatusInfo] = Field(
        default_factory=dict,
        description="Per-subsystem health data",
    )
    checked_at: str = Field(description="ISO 8601 timestamp")
    cached: bool = Field(default=False, description="Whether result was cached")
    checks_total: int = 0
    checks_healthy: int = 0
    checks_degraded: int = 0
    checks_unhealthy: int = 0


class StatusHistoryPoint(BaseModel):
    """A single data point in the status history timeline."""

    timestamp: str = Field(description="ISO 8601 timestamp")
    overall_status: str = Field(description="Aggregate status at this time")
    subsystems_summary: Dict[str, str] = Field(
        default_factory=dict,
        description="Summary of subsystem statuses",
    )


class StatusHistoryResponse(BaseModel):
    """Historical system status data for charting."""

    company_id: str
    points: List[StatusHistoryPoint] = Field(default_factory=list)
    total_points: int = 0
    from_timestamp: Optional[str] = None
    to_timestamp: Optional[str] = None


class SystemIncident(BaseModel):
    """A system incident (state transition from healthy→degraded→down)."""

    incident_id: str
    subsystem: str = Field(description="Affected subsystem name")
    previous_status: str = Field(description="Status before incident")
    current_status: str = Field(description="Status during incident")
    severity: str = Field(default="medium", description="Incident severity")
    description: Optional[str] = None
    detected_at: str = Field(description="ISO 8601 timestamp")
    resolved_at: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActiveIncidentsResponse(BaseModel):
    """Active (unresolved) system incidents."""

    incidents: List[SystemIncident] = Field(default_factory=list)
    total: int = 0


# ══════════════════════════════════════════════════════════════════
# F-089: GSD Debug Terminal Service Schemas
# ══════════════════════════════════════════════════════════════════


class GSDStateInfo(BaseModel):
    """Current GSD state for a ticket."""

    ticket_id: str
    company_id: str
    current_state: str = Field(description="Current GSD state (e.g., 'diagnosis')")
    variant: str = Field(default="parwa", description="PARWA variant type")
    entered_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when this state was entered",
    )
    duration_seconds: float = Field(
        default=0.0,
        description="Time spent in current state",
    )
    transition_count: int = Field(
        default=0,
        description="Total transitions for this ticket",
    )
    signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current conversation signals (sentiment, intent, etc.)",
    )
    source: str = Field(
        default="unknown",
        description="Where the state was read from (redis, db)",
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent transition history",
    )


class GSDSessionInfo(BaseModel):
    """An active GSD session."""

    ticket_id: str
    company_id: str
    current_state: str
    agent_id: Optional[str] = Field(default=None)
    duration_seconds: float = 0.0
    is_stuck: bool = Field(default=False, description="Whether session is stuck")
    stuck_reason: Optional[str] = Field(default=None)
    transition_count: int = 0
    last_transition_at: Optional[str] = None


class GSDSessionsResponse(BaseModel):
    """List of active GSD sessions."""

    sessions: List[GSDSessionInfo] = Field(default_factory=list)
    total: int = 0
    stuck_count: int = 0


class ForceTransitionRequest(BaseModel):
    """Request to force-transition a stuck GSD session (admin only)."""

    ticket_id: str = Field(description="Ticket ID to force-transition")
    target_state: str = Field(description="Target GSD state")
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Reason for the force transition (audit log)",
    )


class ForceTransitionResponse(BaseModel):
    """Result of a force transition."""

    ticket_id: str
    previous_state: str
    new_state: str
    transitioned_at: str = Field(description="ISO 8601 timestamp")
    audit_log_id: Optional[str] = Field(default=None)


class StuckSessionInfo(BaseModel):
    """Information about a stuck GSD session."""

    ticket_id: str
    company_id: str
    current_state: str
    stuck_duration_seconds: float
    stuck_threshold_seconds: float
    last_transition_at: Optional[str] = None
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# F-090: Quick Command Buttons Schemas
# ══════════════════════════════════════════════════════════════════


class QuickCommand(BaseModel):
    """A single quick command definition."""

    id: str = Field(description="Unique command identifier")
    label: str = Field(description="Display label")
    icon: str = Field(default="zap", description="Icon name")
    category: str = Field(description="Command category")
    command_text: str = Field(description="Underlying jarvis command text")
    confirmation_required: bool = Field(default=False)
    risk_level: str = Field(
        default="low", description="Risk level: low/medium/high/critical"
    )
    requires_admin: bool = Field(default=False)
    description: Optional[str] = Field(default=None)
    display_label: Optional[str] = Field(
        default=None, description="Tenant-overridden label"
    )
    tenant_enabled: bool = Field(default=True)
    custom_params: Optional[Dict[str, Any]] = Field(default=None)


class QuickCommandExecuteResponse(BaseModel):
    """Result of executing a quick command."""

    command_id: str
    command_text: str
    parsed: Dict[str, Any] = Field(default_factory=dict)
    executed: bool = Field(default=False)
    requires_confirmation: bool = Field(default=False)
    risk_level: str = Field(default="low")


class QuickCommandConfigSchema(BaseModel):
    """Per-tenant quick command configuration."""

    id: str
    company_id: str
    command_id: str
    enabled: bool = Field(default=True)
    custom_label: Optional[str] = None
    custom_params: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class QuickCommandConfigUpdate(BaseModel):
    """Request to update a quick command configuration."""

    enabled: Optional[bool] = Field(default=None)
    custom_label: Optional[str] = Field(default=None, max_length=200)
    custom_params: Optional[Dict[str, Any]] = Field(default=None)


class QuickCommandsResponse(BaseModel):
    """List of available quick commands."""

    commands: List[QuickCommand] = Field(default_factory=list)
    total: int = 0
    categories: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# F-091: Error Panel Schemas
# ══════════════════════════════════════════════════════════════════


class ErrorEntry(BaseModel):
    """A single error entry in the Error Panel."""

    id: str
    error_type: str
    message: str
    severity: str = Field(default="error")
    subsystem: Optional[str] = None
    affected_ticket_id: Optional[str] = None
    affected_agent_id: Optional[str] = None
    created_at: Optional[str] = None
    message_hash: Optional[str] = None


class ErrorGroup(BaseModel):
    """A group of identical errors with count badge."""

    group_key: str
    error_type: str
    message_hash: str
    message_preview: str
    severity: str
    subsystem: Optional[str] = None
    count: int = 1
    latest_error_id: Optional[str] = None
    latest_created_at: Optional[str] = None


class ErrorDetail(BaseModel):
    """Full detail for a single error."""

    id: str
    company_id: str
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    severity: str
    subsystem: Optional[str] = None
    affected_ticket_id: Optional[str] = None
    affected_agent_id: Optional[str] = None
    dismissed: bool = False
    dismissed_by: Optional[str] = None
    created_at: Optional[str] = None


class ErrorStormAlert(BaseModel):
    """Error storm detection alert."""

    active: bool = True
    error_count: int
    window_seconds: int = 10
    threshold: int = 100
    detected_at: str
    severity: str = Field(default="high")


class ErrorStats(BaseModel):
    """Aggregated error statistics."""

    total_errors: int = 0
    dismissed_count: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_subsystem: List[Dict[str, Any]] = Field(default_factory=list)
    by_type: List[Dict[str, Any]] = Field(default_factory=list)
    storm_alert: Optional[ErrorStormAlert] = None
    period_hours: int = 24
    since: Optional[str] = None


class DismissResponse(BaseModel):
    """Result of dismissing an error."""

    message: str = "Error dismissed successfully"
    error_id: str
    dismissed: bool = True
    dismissed_by: Optional[str] = None
    dismissed_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# F-092: Train from Error Schemas
# ══════════════════════════════════════════════════════════════════


VALID_TRAINING_ACTIONS = ("approved", "rejected", "needs_revision")
VALID_TRAINING_SOURCES = ("error_auto", "error_manual", "feedback", "correction")
VALID_TRAINING_STATUSES_FILTER = (
    "queued_for_review",
    "approved",
    "rejected",
    "in_dataset",
    "archived",
)


class TrainingPointCreate(BaseModel):
    """Request to create a training point from an error."""

    error_id: str = Field(description="Error log UUID to convert")
    ticket_id: Optional[str] = Field(default=None)
    correction_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Operator notes about what went wrong",
    )
    expected_response: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="What the correct AI response should have been",
    )
    source: str = Field(
        default="error_manual",
        description="Source of the training data",
    )


class TrainingPoint(BaseModel):
    """A training data point in the pipeline."""

    id: str
    company_id: str
    error_id: Optional[str] = None
    ticket_id: Optional[str] = None
    intent_label: Optional[str] = None
    source: str = Field(default="error_auto")
    status: str = Field(default="queued_for_review")
    created_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    has_correction: bool = False
    has_expected_response: bool = False


class TrainingPointReview(BaseModel):
    """Request to review a training point."""

    action: str = Field(
        description="Review action: approved, rejected, needs_revision",
    )
    review_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Reviewer notes",
    )


class TrainingPointReviewResponse(BaseModel):
    """Result of reviewing a training point."""

    id: str
    training_point_id: str
    previous_status: str
    new_status: str
    action: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


class TrainingStats(BaseModel):
    """Aggregated training pipeline statistics."""

    total: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_intent: List[Dict[str, Any]] = Field(default_factory=list)
    recent_reviews_24h: int = 0
    ready_for_dataset: int = 0
    review_backlog: int = 0


# ══════════════════════════════════════════════════════════════════
# F-093: Self-Healing Orchestrator Schemas
# ══════════════════════════════════════════════════════════════════

VALID_RISK_LEVELS = ("low", "medium", "high", "critical")
VALID_HEALING_OUTCOMES = (
    "success",
    "failed",
    "skipped",
    "requires_confirmation",
    "cooldown_active",
)


class HealingActionInfo(BaseModel):
    """Definition of a registered healing action."""

    name: str = Field(description="Unique action identifier")
    description: str = Field(description="What the healing action does")
    risk_level: str = Field(
        default="low",
        description="Risk level: low/medium/high/critical",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether admin confirmation is required",
    )
    cooldown_seconds: int = Field(
        default=300,
        description="Minimum seconds between auto-triggers",
    )
    enabled: bool = Field(default=True)


class HealingStatusResponse(BaseModel):
    """Current status of the self-healing orchestrator."""

    company_id: str
    is_monitoring: bool = False
    last_check_at: Optional[str] = None
    actions_registered: int = 0
    active_healings: int = 0
    total_healings_24h: int = 0
    healings_by_outcome: Dict[str, int] = Field(default_factory=dict)
    healings_by_action: Dict[str, int] = Field(default_factory=dict)


class HealingHistoryEntry(BaseModel):
    """A single healing event in the audit log."""

    event_id: str
    company_id: str
    action_name: str
    trigger_reason: str
    risk_level: str = "low"
    outcome: str = "success"
    triggered_at: Optional[str] = None
    completed_at: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = "auto"


class HealingHistoryResponse(BaseModel):
    """Healing event history response."""

    company_id: str
    events: List[HealingHistoryEntry] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class HealingTriggerRequest(BaseModel):
    """Request to manually trigger a healing action."""

    action_name: str = Field(
        description="Name of the healing action to trigger",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context for the healing action",
    )


class HealingActionsListResponse(BaseModel):
    """List of all registered healing actions."""

    actions: List[HealingActionInfo] = Field(default_factory=list)
    total: int = 0


class HealingMonitorResult(BaseModel):
    """Result of a monitor_and_heal cycle."""

    company_id: str
    checked_at: Optional[str] = None
    actions_checked: int = 0
    actions_triggered: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# F-094: Trust Preservation Protocol Schemas
# ══════════════════════════════════════════════════════════════════

VALID_PROTOCOL_MODES = ("green", "amber", "red")


class ProtocolModeInfo(BaseModel):
    """Current trust protocol mode and details."""

    company_id: str
    current_mode: str = Field(
        description="Current protocol mode: green/amber/red",
    )
    manual_override: bool = False
    checked_at: Optional[str] = None
    last_evaluation: Optional[str] = None
    subsystem_summary: Dict[str, str] = Field(default_factory=dict)
    critical_degraded: List[str] = Field(default_factory=list)
    critical_down: List[str] = Field(default_factory=list)
    total_degraded_subsystems: int = 0
    features: Dict[str, Any] = Field(default_factory=dict)


class ProtocolSetModeRequest(BaseModel):
    """Request to manually set the protocol mode (admin only)."""

    mode: str = Field(
        description="Target protocol mode: green/amber/red",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional reason for the manual change",
    )


class ProtocolSetModeResponse(BaseModel):
    """Result of setting protocol mode."""

    company_id: str
    previous_mode: str
    new_mode: str
    manual_override: bool = True
    set_by: Optional[str] = None
    set_at: Optional[str] = None
    reason: Optional[str] = None


class ProtocolEvaluateResponse(BaseModel):
    """Result of protocol auto-evaluation."""

    company_id: str
    previous_mode: str = "green"
    current_mode: str = "green"
    transitioned: bool = False
    transition_reason: Optional[str] = None
    manual_override: bool = False
    subsystem_summary: Dict[str, str] = Field(default_factory=dict)
    critical_degraded: List[str] = Field(default_factory=list)
    critical_down: List[str] = Field(default_factory=list)
    total_degraded_subsystems: int = 0
    healthy_duration_seconds: float = 0.0
    evaluated_at: Optional[str] = None


class ProtocolTransition(BaseModel):
    """A single protocol mode transition event."""

    transition_id: str
    company_id: str
    previous_mode: str
    new_mode: str
    reason: str = ""
    triggered_by: str = "auto"
    transitioned_at: Optional[str] = None


class ProtocolHistoryResponse(BaseModel):
    """Protocol transition history response."""

    company_id: str
    transitions: List[ProtocolTransition] = Field(default_factory=list)
    total: int = 0
    limit: int = 50


class RecoveryEstimate(BaseModel):
    """Estimated time to protocol recovery."""

    company_id: str
    current_mode: str = "green"
    estimate_seconds: int = 0
    estimate_message: str = ""
    critical_issues: List[Dict[str, Any]] = Field(default_factory=list)
    degraded_count: int = 0
    subsystem_summary: Dict[str, Any] = Field(default_factory=dict)
    next_mode: Optional[str] = None
    healthy_duration_seconds: float = 0.0
    required_stable_seconds: int = 0
    recovery_progress_pct: float = 0.0


class ResponseWrapper(BaseModel):
    """Response modification wrapper based on protocol mode."""

    response: str
    mode: str = "green"
    modified: bool = False
    modification_type: Optional[str] = None
    auto_execute_enabled: bool = True
    ai_paused: bool = False
    original_response: Optional[str] = None
    original_response_length: Optional[int] = None
    modified_response_length: Optional[int] = None
