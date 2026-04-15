"""
PARWA Agent Dashboard Schemas (F-097)

Pydantic models for the Agent Dashboard API — card-based views of all
AI agents with real-time status, performance metrics, sparkline data,
quick-action affordances, and Socket.io event payloads.

Building Codes: BC-001 (multi-tenant), BC-005 (real-time),
               BC-007 (AI model), BC-012 (error handling)
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

DASHBOARD_AGENT_STATUSES = (
    "active", "training", "paused", "error", "cold_start",
)

QUICK_ACTION_TYPES = ("pause", "resume", "retrain", "view_metrics")


# ══════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════


class AgentCardMetrics(BaseModel):
    """Key performance metrics for an agent card.

    These are the headline numbers shown on each agent card in the
    dashboard grid view.
    """
    resolution_rate: Optional[float] = Field(
        default=None,
        description="Percentage of tickets resolved by this agent (0-100)",
    )
    csat_avg: Optional[float] = Field(
        default=None,
        description="Average customer satisfaction score (0-5)",
    )
    avg_confidence: Optional[float] = Field(
        default=None,
        description="Average AI confidence score (0-100)",
    )
    escalation_rate: Optional[float] = Field(
        default=None,
        description="Percentage of tickets escalated (0-100)",
    )
    avg_handling_time: Optional[float] = Field(
        default=None,
        description="Average handling time in minutes",
    )
    tickets_handled_24h: int = Field(
        default=0,
        description="Number of tickets handled in the last 24 hours",
    )


class AgentRealtimeMetrics(AgentCardMetrics):
    """Real-time metrics payload for Socket.io push.

    Extends the card metrics with a timestamp and agent identifier
    for use in agent:metrics_updated events.
    """
    agent_id: str
    company_id: str
    timestamp: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# QUICK ACTIONS
# ══════════════════════════════════════════════════════════════════


class AgentQuickAction(BaseModel):
    """A quick-action button on an agent card.

    Each action has a type, whether it's currently allowed, and an
    optional reason if disallowed.
    """
    action: str = Field(
        description="Action type: pause, resume, retrain, view_metrics",
    )
    allowed: bool = Field(
        default=True,
        description="Whether this action is currently available",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason if action is not allowed",
    )


# ══════════════════════════════════════════════════════════════════
# AGENT CARD
# ══════════════════════════════════════════════════════════════════


class AgentCardResponse(BaseModel):
    """Single agent card for the dashboard grid.

    Contains everything the frontend needs to render one agent card:
    identity, status, specialty, headline metrics, sparkline data,
    and quick-action affordances.
    """
    id: str
    name: str
    status: str = Field(
        description="Current agent status: active/training/paused/error/cold_start",
    )
    specialty: str
    description: Optional[str] = None
    base_model: Optional[str] = None
    model_checkpoint_id: Optional[str] = None
    metrics: AgentCardMetrics = Field(
        default_factory=AgentCardMetrics,
    )
    sparkline_data: List[float] = Field(
        default_factory=list,
        description="Resolution rate sparkline (14 data points, daily)",
    )
    quick_actions: List[AgentQuickAction] = Field(
        default_factory=list,
        description="Available quick-action buttons for this agent",
    )
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    activated_at: Optional[str] = None


class AgentCardDetailResponse(AgentCardResponse):
    """Detailed agent card with additional information.

    Extends the base card with channels, permissions, setup status,
    and active instruction set info for the detail view.
    """
    channels: Dict[str, Any] = Field(default_factory=dict)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    setup_status: Optional[Dict[str, Any]] = None
    active_instruction_set: Optional[Dict[str, Any]] = None


# ══════════════════════════════════════════════════════════════════
# STATUS COUNTS
# ══════════════════════════════════════════════════════════════════


class AgentStatusCounts(BaseModel):
    """Counts of agents grouped by status.

    Used for status filter chips on the dashboard.
    """
    active: int = 0
    training: int = 0
    paused: int = 0
    error: int = 0
    cold_start: int = 0
    total: int = 0


# ══════════════════════════════════════════════════════════════════
# LIST / AGGREGATE RESPONSES
# ══════════════════════════════════════════════════════════════════


class AgentCardListResponse(BaseModel):
    """Dashboard endpoint response with all agent cards + status counts."""
    cards: List[AgentCardResponse] = Field(default_factory=list)
    status_counts: AgentStatusCounts = Field(
        default_factory=AgentStatusCounts,
    )


class AgentPauseResumeResponse(BaseModel):
    """Response after pausing or resuming an agent."""
    agent_id: str
    previous_status: str
    new_status: str
    message: str


# ══════════════════════════════════════════════════════════════════
# SOCKET.IO EVENT PAYLOADS
# ══════════════════════════════════════════════════════════════════


class AgentStatusChangedEvent(BaseModel):
    """Payload for the agent:status_changed Socket.io event."""
    agent_id: str
    company_id: str
    previous_status: str
    new_status: str
    changed_by: Optional[str] = None
    timestamp: Optional[str] = None


class AgentMetricsUpdatedEvent(BaseModel):
    """Payload for the agent:metrics_updated Socket.io event."""
    agent_id: str
    company_id: str
    metrics: AgentCardMetrics
    timestamp: Optional[str] = None
