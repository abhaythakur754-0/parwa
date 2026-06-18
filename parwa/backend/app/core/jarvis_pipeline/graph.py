"""
Jarvis Pipeline Graph — 3-Node: SENSE → EVALUATE → NOTIFY

Jarvis is the awareness engine. It does NOT auto-heal or take
autonomous actions. It watches, evaluates, notifies, and answers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.graph import StateGraph, END

from app.core.jarvis_pipeline.state import create_jarvis_state, JarvisState
from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate
from app.core.jarvis_pipeline.nodes.jarvis_3_notify import jarvis_notify

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
) -> Dict[str, Any]:
    """Run the full Jarvis pipeline.

    Args:
        tenant_id: The tenant to monitor
        trigger: "poll", "stuck_ticket", "admin_chat", "policy_change"
        parwa_state: PARWA pipeline state (for monitoring)
        admin_question: Admin chat question (for admin_chat trigger)

    Returns:
        Full Jarvis pipeline result dict.
    """
    state = create_jarvis_state(
        tenant_id=tenant_id,
        trigger=trigger,
        parwa_state=parwa_state,
        admin_question=admin_question,
    )

    graph = build_jarvis_pipeline()
    compiled = graph.compile()
    result = await compiled.ainvoke(state)
    return result


async def run_jarvis_monitor(parwa_state: Dict[str, Any]):
    """Convenience: Run Jarvis in monitor mode after a PARWA pipeline run.

    Detects stuck tickets, monitors quota, and creates notifications.
    """
    return await run_jarvis(
        tenant_id=parwa_state.get("tenant_id", ""),
        trigger="stuck_ticket" if parwa_state.get("status") in ("escalated", "error") else "poll",
        parwa_state=parwa_state,
    )