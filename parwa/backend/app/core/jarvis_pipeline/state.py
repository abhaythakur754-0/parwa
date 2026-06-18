"""Jarvis Pipeline — State Definition

Jarvis is the awareness engine: SENSE → EVALUATE → NOTIFY
It monitors PARWA pipeline, evaluates signals, and notifies admins.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class JarvisState(TypedDict, total=False):
    """State that flows through the 3-node Jarvis pipeline.

    Every field is optional (total=False) so nodes can be built incrementally.
    Graph entry point must populate the required input fields.
    """

    # Input
    tenant_id: str
    trigger: str  # "poll", "stuck_ticket", "admin_chat", "policy_change"
    timestamp: str
    parwa_state: Dict[str, Any]
    admin_question: str
    notification_key: str
    stuck_ticket_data: Dict[str, Any]

    # Auth (Wave 1)
    user_context: Dict[str, Any]  # {email, role, auth_method}

    # SENSE output
    signals: Dict[str, Any]
    sense_log: List[Dict[str, Any]]

    # Wave 2: New signal sub-objects (populated by real collectors)
    # These are inside signals dict, but listed here for type clarity:
    # signals.drift_status: {drift_detected, drift_severity, trend_direction, ...}
    # signals.llm_costs: {persisted: {...}, live_session: {...}, total_cost_usd}
    # signals.load_status: {variants: [...], vip_overflow_risk}
    # signals.integration_health: {services: {...}, degraded_count, healthy_count}
    # signals.ticket_flow: {summary: {...}, current_ticket: {...}}

    # EVALUATE output
    evaluations: List[Dict[str, Any]]
    clara_result: str
    reflexion_result: str
    priority_scores: Dict[str, Any]
    evaluation_log: List[Dict[str, Any]]

    # NOTIFY output
    notifications: List[Dict[str, Any]]
    notification_keys: List[str]
    chat_response: str
    quota_feedback: Dict[str, Any]
    wiki_updates: List[Dict[str, Any]]
    notify_log: List[Dict[str, Any]]

    # Pipeline tracking
    total_token_usage: int
    technique_log: List[Dict[str, Any]]
    errors: List[Any]

    # Pipeline output metadata (Wave 1)
    intent_result: Optional[Dict[str, Any]]
    auth_result: Optional[Dict[str, Any]]

    # Wave 3: Command execution result
    command_execution_result: Optional[Dict[str, Any]]

    # Wave 5: Intelligence Layer
    confidence_result: Optional[Dict[str, Any]]       # {confidence, routing, factors, reason}
    sentiment_result: Optional[Dict[str, Any]]         # {score, label, route, escalate}
    approval_gate_result: Optional[Dict[str, Any]]     # {required, reason, gate_type}
    variant_recommendation: Optional[Dict[str, Any]]   # {upgrade_needed, recommended_variant}


def create_jarvis_state(
    tenant_id: str,
    trigger: str = "poll",
    parwa_state: Optional[Dict[str, Any]] = None,
    admin_question: str = "",
    notification_key: str = "",
    stuck_ticket_data: Optional[Dict] = None,
) -> JarvisState:
    """Create initial Jarvis pipeline state."""
    return {
        "tenant_id": tenant_id,
        "trigger": trigger,
        "timestamp": "",

        # Input signals
        "parwa_state": parwa_state or {},
        "admin_question": admin_question,
        "notification_key": notification_key,
        "stuck_ticket_data": stuck_ticket_data or {},

        # SENSE output
        "signals": {
            "stuck_tickets": [],
            "quota_status": {},
            "integration_health": {"services": {}, "degraded_count": 0, "healthy_count": 0},
            "policy_version": {},
            "accuracy_trend": "",
            "ticket_flow": {"summary": {}, "current_ticket": {}},
            # Wave 2 new
            "drift_status": {"drift_detected": False, "drift_severity": "none",
                              "trend_direction": "stable", "trigger_reason": "no_data",
                              "total_scores": 0},
            "llm_costs": {"persisted": {}, "live_session": {}, "total_cost_usd": 0,
                          "total_calls_combined": 0, "total_tokens_combined": 0},
            "load_status": {"variants": [], "total_concurrent": 0, "vip_overflow_risk": False},
        },
        "sense_log": [],

        # EVALUATE output
        "evaluations": [],
        "priority_scores": {},
        "evaluation_log": [],

        # NOTIFY output
        "notifications": [],
        "chat_response": "",
        "quota_feedback": {},
        "wiki_updates": [],
        "notify_log": [],

        # Pipeline tracking
        "total_token_usage": 0,
        "technique_log": [],
        "errors": [],
    }