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
    "show_status", "system_status", "list_errors", "show_errors",
    "restart_agent", "escalate_ticket", "train_from_error",
    "list_tickets", "show_tickets", "get_ticket", "assign_ticket",
    "close_ticket", "reopen_ticket", "list_agents", "show_agents",
    "analytics", "show_analytics", "query_analytics",
    "health_check", "ping", "uptime",
    "list_integrations", "show_integrations", "check_integration",
    "enable_integration", "disable_integration",
    "list_queues", "show_queues", "purge_queue",
    "list_incidents", "show_incidents", "resolve_incident",
    "show_config", "get_config", "set_config",
    "show_logs", "get_logs", "export_logs",
    "show_usage", "usage_summary", "cost_report",
    "train_model", "retrain", "evaluate_model",
    "restart_service", "deploy", "rollback",
    "help", "commands", "list_commands",
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
