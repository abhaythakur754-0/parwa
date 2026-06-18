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
            "integration_health": {},
            "policy_version": {},
            "accuracy_trend": "",
            "ticket_flow": {},
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