"""
Jarvis Pipeline Graph — 3-Node: SENSE → EVALUATE → NOTIFY

Wave 1: Wired end-to-end with jarvis_db, command_parser, jarvis_auth.
Now supports:
  - Poll mode (monitoring, notifications)
  - Admin chat mode (natural language commands with auth)
  - Quality score write-back
  - System flag read/write
  - Full audit trail
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.graph import StateGraph, END

from app.core.jarvis_pipeline.state import create_jarvis_state, JarvisState
from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate
from app.core.jarvis_pipeline.nodes.jarvis_3_notify import jarvis_notify
from app.core.jarvis_pipeline.jarvis_db import get_db

logger = logging.getLogger("jarvis.pipeline")


def build_jarvis_pipeline():
    """Build the 3-node Jarvis pipeline graph."""
    graph = StateGraph(JarvisState)

    # Add nodes
    graph.add_node("sense", jarvis_sense)
    graph.add_node("evaluate", jarvis_evaluate)
    graph.add_node("notify", jarvis_notify)

    # Linear flow: SENSE → EVALUATE → NOTIFY → END
    graph.add_edge("sense", "evaluate")
    graph.add_edge("evaluate", "notify")
    graph.add_edge("notify", END)

    # Entry point
    graph.set_entry_point("sense")

    return graph


async def run_jarvis(
    tenant_id: str,
    trigger: str = "poll",
    parwa_state: Dict[str, Any] = None,
    admin_question: str = "",
    user_context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Run the full Jarvis pipeline.

    Args:
        tenant_id: The tenant to monitor
        trigger: "poll", "stuck_ticket", "admin_chat", "policy_change"
        parwa_state: PARWA pipeline state (for monitoring)
        admin_question: Admin chat question (for admin_chat trigger)
        user_context: User auth context with 'email' and 'role' (for admin_chat)

    Returns:
        Full Jarvis pipeline result dict.
    """
    state = create_jarvis_state(
        tenant_id=tenant_id,
        trigger=trigger,
        parwa_state=parwa_state,
        admin_question=admin_question,
    )

    # Wire user context for auth
    if user_context:
        state["user_context"] = user_context

    graph = build_jarvis_pipeline()
    compiled = graph.compile()
    result = await compiled.ainvoke(state)
    return result


async def run_jarvis_chat(
    tenant_id: str,
    question: str,
    user_email: str = "admin@parwa.ai",
    user_role: str = "admin",
    parwa_state: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Convenience: Run Jarvis in admin chat mode.

    Full pipeline: chat → parse → auth → execute → DB → response.

    Args:
        tenant_id: The tenant
        question: Natural language command/query
        user_email: Authenticated user's email
        user_role: User's role (owner/admin/supervisor/team_member/viewer)
        parwa_state: Current PARWA state for context

    Returns:
        Dict with chat_response, intent_result, auth_result, notifications
    """
    user_context = {
        "email": user_email,
        "role": user_role,
        "auth_method": "chat",
    }

    return await run_jarvis(
        tenant_id=tenant_id,
        trigger="admin_chat",
        admin_question=question,
        user_context=user_context,
        parwa_state=parwa_state or {},
    )


async def run_jarvis_monitor(parwa_state: Dict[str, Any]):
    """Convenience: Run Jarvis in monitor mode after a PARWA pipeline run.

    Detects stuck tickets, monitors quota, and creates notifications.
    """
    return await run_jarvis(
        tenant_id=parwa_state.get("tenant_id", ""),
        trigger="stuck_ticket" if parwa_state.get("status") in ("escalated", "error") else "poll",
        parwa_state=parwa_state,
    )