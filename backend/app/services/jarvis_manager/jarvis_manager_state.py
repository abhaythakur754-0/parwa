"""
Jarvis Manager State — The state object for the Jarvis Manager graph.

Jarvis is NOT a chatbot. Jarvis is a MANAGER/MONITOR that:
  - Watches variant pipelines running
  - Detects errors, quality drops, anomalies
  - Takes corrective actions autonomously
  - Talks directly to clients (like OpenClaw)
  - Escalates to humans when needed
  - Self-heals when it detects its own issues

This is inspired by OpenClaw's action-first, multi-channel architecture
where the AI doesn't just respond — it ACTS.

BC-008: Never crash.
BC-001: company_id first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class JarvisManagerState(TypedDict, total=False):
    """State object for the Jarvis Manager graph.

    This flows through the Jarvis Manager pipeline, which is SEPARATE
    from the variant pipeline. Jarvis watches the variant pipeline
    and intervenes when needed.
    """

    # ── INCOMING ────────────────────────────────────────────────────
    company_id: str
    """Tenant identifier (BC-001)."""

    session_id: str
    """Current CC session ID."""

    user_id: str
    """User ID for audit."""

    trigger_type: str
    """What triggered Jarvis: 'variant_error' | 'quality_drop' | 'anomaly' |
    'client_message' | 'scheduled_check' | 'escalation' | 'alert'"""

    trigger_details: Dict[str, Any]
    """Details about what triggered this Jarvis run."""

    variant_tier: str
    """Which variant tier is being monitored."""

    # ── MONITORING ──────────────────────────────────────────────────

    variant_pipeline_state: Dict[str, Any]
    """Snapshot of the variant pipeline's current state.
    Jarvis reads this to understand what's happening."""

    awareness_snapshot: Dict[str, Any]
    """Current awareness engine snapshot (7 domains)."""

    quality_metrics: Dict[str, Any]
    """Current quality metrics from the variant pipeline:
    {
        'recent_quality_scores': List[float],
        'average_quality': float,
        'quality_trend': str,  # 'improving' | 'stable' | 'declining'
        'failed_tickets': int,
        'total_tickets': int,
    }"""

    anomaly_indicators: Dict[str, Any]
    """Anomaly indicators from monitoring:
    {
        'ticket_volume_spike': bool,
        'error_rate_spike': bool,
        'latency_spike': bool,
        'sentiment_drop': bool,
        'escalation_spike': bool,
    }"""

    # ── DIAGNOSIS ───────────────────────────────────────────────────

    diagnosis: Dict[str, Any]
    """Jarvis's diagnosis of the situation:
    {
        'issue_type': str,     # 'quality_degradation' | 'error_spike' | etc.
        'severity': str,       # 'low' | 'medium' | 'high' | 'critical'
        'root_cause': str,     # What Jarvis thinks is wrong
        'affected_area': str,  # What part of the system is affected
        'confidence': float,   # How confident Jarvis is in this diagnosis
    }"""

    # ── ACTION ──────────────────────────────────────────────────────

    action_plan: Dict[str, Any]
    """Jarvis's action plan:
    {
        'actions': List[Dict],  # [{action_type, target, parameters}]
        'priority': str,
        'estimated_impact': str,
        'requires_human_approval': bool,
    }"""

    actions_executed: Annotated[List[Dict[str, Any]], operator.add]
    """Actions that have been executed by Jarvis.
    Uses operator.add reducer so actions can be appended."""

    # ── CLIENT COMMUNICATION ────────────────────────────────────────

    client_message: str
    """Message to send directly to the client/customer.
    Jarvis talks to clients directly — like OpenClaw."""

    client_message_type: str
    """Type of client message: 'info' | 'apology' | 'update' |
    'resolution' | 'escalation_notice'"""

    # ── SELF-HEALING ────────────────────────────────────────────────

    self_healing_applied: bool
    """Whether Jarvis applied self-healing actions."""

    self_healing_details: Dict[str, Any]
    """Details of self-healing actions applied:
    {
        'provider_switched': bool,
        'threshold_adjusted': bool,
        'circuit_breaker_triggered': bool,
        'fallback_activated': bool,
    }"""

    # ── OUTPUT ──────────────────────────────────────────────────────

    execution_status: str
    """Final status: 'acted' | 'escalated' | 'monitored' | 'self_healed' |
    'no_action_needed' | 'failed'"""

    execution_time_ms: float
    """Total execution time in milliseconds."""

    audit_trail: Annotated[List[Dict[str, Any]], operator.add]
    """Audit trail entries.
    Uses operator.add reducer so entries can be appended."""

    errors: Annotated[List[str], operator.add]
    """Errors encountered.
    Uses operator.add reducer."""


def create_jarvis_manager_state(
    company_id: str,
    session_id: str,
    user_id: str,
    trigger_type: str = "scheduled_check",
    trigger_details: Optional[Dict[str, Any]] = None,
    variant_tier: str = "mini_parwa",
    variant_pipeline_state: Optional[Dict[str, Any]] = None,
    awareness_snapshot: Optional[Dict[str, Any]] = None,
) -> JarvisManagerState:
    """Create initial Jarvis Manager state.

    Args:
        company_id: Company ID (BC-001).
        session_id: CC session ID.
        user_id: User ID for audit.
        trigger_type: What triggered this Jarvis run.
        trigger_details: Details about the trigger.
        variant_tier: Which variant tier is being monitored.
        variant_pipeline_state: Snapshot of variant pipeline state.
        awareness_snapshot: Current awareness snapshot.

    Returns:
        Initialized JarvisManagerState.
    """
    return JarvisManagerState(
        company_id=company_id,
        session_id=session_id,
        user_id=user_id,
        trigger_type=trigger_type,
        trigger_details=trigger_details or {},
        variant_tier=variant_tier,
        variant_pipeline_state=variant_pipeline_state or {},
        awareness_snapshot=awareness_snapshot or {},
        quality_metrics={},
        anomaly_indicators={},
        diagnosis={},
        action_plan={},
        actions_executed=[],
        client_message="",
        client_message_type="info",
        self_healing_applied=False,
        self_healing_details={},
        execution_status="pending",
        execution_time_ms=0.0,
        audit_trail=[],
        errors=[],
    )
