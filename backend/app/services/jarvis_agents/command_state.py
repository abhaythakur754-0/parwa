"""
PARWA Jarvis Command State — LangGraph State for the Multi-Agent Command Layer

This defines the state that flows through the Jarvis Command Graph.
It's separate from ParwaGraphState because the command graph runs
independently from the main customer care pipeline.

The state carries:
  - The triggering alert (if any)
  - The parsed NL command (if user-initiated)
  - Router decision (which agent to invoke)
  - Agent decision (what action to take)
  - Execution result (what actually happened)

Flow:
  Alert/User Input → CommandRouter → [AgentNode] → CommandExecutor → Result
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing import TypedDict


def _merge_dicts(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer: merge new dict into existing (new keys override)."""
    return {**existing, **new}


def _merge_lists(existing: List[Any], new: List[Any]) -> List[Any]:
    """Reducer: append new items to existing list."""
    return existing + new


class JarvisCommandState(TypedDict, total=False):
    """State flowing through the Jarvis Command Graph.

    Unlike ParwaGraphState (which handles customer messages), this state
    handles Jarvis's own operational decisions. When Jarvis notices something
    via the Awareness Engine, or when a user gives a command, this state
    tracks the decision-making process from detection to action.

    Groups:
      1. TRIGGER     — What initiated this command (alert or user input)
      2. CONTEXT     — Current awareness snapshot + session data
      3. ROUTER      — Router agent's decision on which agent to invoke
      4. AGENT       — The specialist agent's decision on what to do
      5. EXECUTION   — What actually happened when the action was executed
      6. AUDIT       — Full audit trail for compliance
    """

    # ──────────────────────────────────────────────────────────────
    # GROUP 1: TRIGGER — What started this command
    # ──────────────────────────────────────────────────────────────

    trigger_type: str
    """What triggered this command: 'alert' (from awareness engine), 
    'user_nl' (natural language from user), 'user_quick' (quick command),
    'proactive' (Jarvis's own initiative), 'scheduled' (periodic task)."""

    alert_id: str
    """If trigger_type='alert', the ID of the JarvisProactiveAlert."""

    alert_type: str
    """Alert type: ticket_volume_spike, quality_drop, drift_detected, etc."""

    alert_severity: str
    """Alert severity: info, warning, critical, emergency."""

    alert_message: str
    """Human-readable alert message."""

    alert_details: Dict[str, Any]
    """Structured alert details from details_json."""

    raw_input: str
    """If trigger_type='user_nl', the raw natural language input."""

    session_id: str
    """The CC session this command is associated with."""

    company_id: str
    """BC-001: Company ID for tenant isolation."""

    user_id: str
    """User ID for audit and security scoping."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 2: CONTEXT — Current awareness state
    # ──────────────────────────────────────────────────────────────

    awareness_snapshot: Dict[str, Any]
    """Latest awareness snapshot data (7 domains)."""

    active_alerts_summary: List[Dict[str, Any]]
    """Summary of all currently active alerts for context."""

    session_context: Dict[str, Any]
    """Current CC session context (variant tier, pipeline status, etc.)."""

    variant_tier: str
    """Current variant tier: mini_parwa, parwa, parwa_high."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 3: ROUTER — Command Router Agent's decision
    # ──────────────────────────────────────────────────────────────

    router_decision: str
    """Which agent the router selected: escalation, sla_protection, 
    quality_recovery, reassignment, notification, no_action."""

    router_reasoning: str
    """Why the router selected this agent."""

    router_urgency: str
    """Router's assessed urgency: low, medium, high, critical."""

    router_parameters: Dict[str, Any]
    """Router's suggested parameters for the agent."""

    router_source: str
    """How the router made its decision: 'zai_llm' or 'rule_based_fallback'."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 4: AGENT — Specialist agent's decision
    # ──────────────────────────────────────────────────────────────

    agent_type: str
    """Which agent was invoked (same as router_decision)."""

    agent_action: str
    """The action the agent decided to take."""

    agent_decision: Dict[str, Any]
    """Full structured decision from the agent (action, scope, parameters, etc.)."""

    agent_reasoning: str
    """Agent's reasoning for its decision."""

    agent_source: str
    """How the agent decided: 'zai_llm' or 'rule_based_fallback'."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 5: EXECUTION — What actually happened
    # ──────────────────────────────────────────────────────────────

    execution_status: str
    """Execution status: pending, executing, completed, failed, skipped."""

    execution_result: Dict[str, Any]
    """Structured result from executing the agent's decision."""

    execution_error: str
    """Error message if execution failed."""

    execution_time_ms: float
    """Total execution time in milliseconds."""

    command_id: str
    """ID of the JarvisCommand DB record for this execution."""

    db_command_created: bool
    """Whether a JarvisCommand DB record was successfully created."""

    alert_resolved: bool
    """Whether the triggering alert was resolved as a result of this action."""

    # ──────────────────────────────────────────────────────────────
    # GROUP 6: AUDIT — Full trail
    # ──────────────────────────────────────────────────────────────

    node_outputs: Annotated[Dict[str, Any], _merge_dicts]
    """Accumulated outputs from each node: {node_name: output_dict}."""

    audit_trail: Annotated[List[Dict[str, Any]], _merge_lists]
    """Step-by-step audit entries: [{step, timestamp, agent, action, result}]."""

    errors: Annotated[List[str], _merge_lists]
    """Accumulated error messages (BC-008 graceful degradation)."""


def create_command_state_from_alert(
    company_id: str,
    session_id: str,
    user_id: str,
    alert_id: str = "",
    alert_type: str = "",
    alert_severity: str = "info",
    alert_message: str = "",
    alert_details: Optional[Dict[str, Any]] = None,
    awareness_snapshot: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    variant_tier: str = "mini_parwa",
) -> Dict[str, Any]:
    """Create initial command state from an awareness alert.

    This is how Jarvis goes from "I noticed something" to "I'm going to do
    something about it." The alert triggers the command graph.
    """
    from datetime import datetime, timezone

    return {
        # TRIGGER
        "trigger_type": "alert",
        "alert_id": alert_id,
        "alert_type": alert_type,
        "alert_severity": alert_severity,
        "alert_message": alert_message,
        "alert_details": alert_details or {},
        "raw_input": "",
        "session_id": session_id,
        "company_id": company_id,
        "user_id": user_id,

        # CONTEXT
        "awareness_snapshot": awareness_snapshot or {},
        "active_alerts_summary": [],
        "session_context": session_context or {},
        "variant_tier": variant_tier,

        # ROUTER
        "router_decision": "",
        "router_reasoning": "",
        "router_urgency": "medium",
        "router_parameters": {},
        "router_source": "",

        # AGENT
        "agent_type": "",
        "agent_action": "",
        "agent_decision": {},
        "agent_reasoning": "",
        "agent_source": "",

        # EXECUTION
        "execution_status": "pending",
        "execution_result": {},
        "execution_error": "",
        "execution_time_ms": 0.0,
        "command_id": "",
        "db_command_created": False,
        "alert_resolved": False,

        # AUDIT
        "node_outputs": {},
        "audit_trail": [{
            "step": "init",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": "alert",
            "alert_type": alert_type,
            "severity": alert_severity,
        }],
        "errors": [],
    }


def create_command_state_from_nl(
    company_id: str,
    session_id: str,
    user_id: str,
    raw_input: str,
    awareness_snapshot: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    variant_tier: str = "mini_parwa",
) -> Dict[str, Any]:
    """Create initial command state from a user's natural language input.

    This is how a user's command like "pause all AI" enters the graph.
    """
    from datetime import datetime, timezone

    return {
        # TRIGGER
        "trigger_type": "user_nl",
        "alert_id": "",
        "alert_type": "",
        "alert_severity": "",
        "alert_message": "",
        "alert_details": {},
        "raw_input": raw_input,
        "session_id": session_id,
        "company_id": company_id,
        "user_id": user_id,

        # CONTEXT
        "awareness_snapshot": awareness_snapshot or {},
        "active_alerts_summary": [],
        "session_context": session_context or {},
        "variant_tier": variant_tier,

        # ROUTER
        "router_decision": "",
        "router_reasoning": "",
        "router_urgency": "medium",
        "router_parameters": {},
        "router_source": "",

        # AGENT
        "agent_type": "",
        "agent_action": "",
        "agent_decision": {},
        "agent_reasoning": "",
        "agent_source": "",

        # EXECUTION
        "execution_status": "pending",
        "execution_result": {},
        "execution_error": "",
        "execution_time_ms": 0.0,
        "command_id": "",
        "db_command_created": False,
        "alert_resolved": False,

        # AUDIT
        "node_outputs": {},
        "audit_trail": [{
            "step": "init",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": "user_nl",
            "raw_input": raw_input[:100],
        }],
        "errors": [],
    }
