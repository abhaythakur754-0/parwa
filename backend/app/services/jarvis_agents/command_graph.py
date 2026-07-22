"""
PARWA Jarvis Command Graph — LangGraph Multi-Agent Graph (Phase 4)

This is the graph that wires all the agent nodes together into a
coherent decision-making pipeline. It's how Jarvis goes from
"I noticed something" to "I did something about it."

Graph Topology (Phase 4 — with approval_gate):
  START → command_router → [agent_selector] → specialist_agent
        → approval_gate → command_executor → END

  The agent_selector is a conditional edge that routes to the correct
  specialist agent based on the command_router's decision:

    command_router → escalation_agent    (if router_decision == "escalation")
    command_router → sla_protection_agent (if router_decision == "sla_protection")
    command_router → quality_recovery_agent (if router_decision == "quality_recovery")
    command_router → reassignment_agent   (if router_decision == "reassignment")
    command_router → notification_agent   (if router_decision == "notification")
    command_router → approval_gate        (if router_decision == "no_action")
    command_router → pipeline_query_agent (if router_decision == "pipeline_query")

  All specialist agents flow into approval_gate which checks if the
  action needs human approval based on variant_tier:
    - mini_parwa: ALL actions need approval
    - parwa: Only escalation + monetary actions
    - parwa_high: Only emergency actions

  If approved (auto or by human), flows to command_executor.
  If pending_approval, the graph ends and waits for human input.

Phase 4 Changes:
  - Added approval_gate between specialist agents and command_executor
  - Added pipeline_query_agent for querying variant pipeline state
  - Added variant_tier awareness throughout the graph
  - Added feedback loop: command_executor writes back to pipeline via bridge

BC-001: company_id first parameter on all public methods.
BC-008: Every node wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.logger import get_logger
from app.services.jarvis_agents.command_state import (
    JarvisCommandState,
    create_command_state_from_alert,
    create_command_state_from_nl,
)
from app.services.jarvis_agents.nodes.command_router import command_router_node
from app.services.jarvis_agents.nodes.escalation_agent import escalation_agent_node
from app.services.jarvis_agents.nodes.sla_protection_agent import sla_protection_agent_node
from app.services.jarvis_agents.nodes.quality_recovery_agent import quality_recovery_agent_node
from app.services.jarvis_agents.nodes.reassignment_agent import reassignment_agent_node
from app.services.jarvis_agents.nodes.notification_agent import notification_agent_node
from app.services.jarvis_agents.nodes.command_executor import command_executor_node
from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
from app.services.jarvis_agents.nodes.pipeline_query_agent import pipeline_query_agent_node

logger = get_logger("jarvis_command_graph")


# ══════════════════════════════════════════════════════════════════
# AGENT SELECTOR: Conditional edge from router to specialist
# ══════════════════════════════════════════════════════════════════

def _agent_selector(state: Dict[str, Any]) -> str:
    """Route from command_router to the correct specialist agent.

    This is a LangGraph conditional edge function. It reads the
    router_decision from state and returns the name of the next node.

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        Node name string for the next node to execute.
    """
    decision = state.get("router_decision", "notification")

    agent_map = {
        "escalation": "escalation_agent",
        "sla_protection": "sla_protection_agent",
        "quality_recovery": "quality_recovery_agent",
        "reassignment": "reassignment_agent",
        "notification": "notification_agent",
        "pipeline_query": "pipeline_query_agent",
        "no_action": "approval_gate",  # Skip agent, go to approval gate
    }

    next_node = agent_map.get(decision, "notification_agent")

    logger.debug(
        "agent_selector: decision=%s → next_node=%s",
        decision, next_node,
    )

    return next_node


# ══════════════════════════════════════════════════════════════════
# APPROVAL SELECTOR: Conditional edge from approval_gate
# ══════════════════════════════════════════════════════════════════

def _approval_selector(state: Dict[str, Any]) -> str:
    """Route from approval_gate based on approval status.

    If the action was auto-approved, proceed to command_executor.
    If the action is pending human approval, end the graph (wait).

    Args:
        state: Current JarvisCommandState dict.

    Returns:
        "command_executor" if approved, "__end__" if pending approval.
    """
    execution_status = state.get("execution_status", "")

    if execution_status == "approved":
        logger.debug("approval_selector: approved → command_executor")
        return "command_executor"
    elif execution_status == "pending_approval":
        logger.debug("approval_selector: pending_approval → END")
        return "__end__"
    else:
        # Unknown status — proceed to executor (fail-open for safety)
        logger.debug(
            "approval_selector: unknown_status=%s → command_executor",
            execution_status,
        )
        return "command_executor"


# ══════════════════════════════════════════════════════════════════
# STATE MERGE HELPER: Properly merge dict/list fields in manual mode
# ══════════════════════════════════════════════════════════════════

def _merge_state_updates(state: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """Merge node output updates into state, properly handling
    node_outputs (dict merge) and audit_trail/errors (list append)."""
    for key, value in updates.items():
        if key == "node_outputs" and isinstance(value, dict):
            existing = state.get("node_outputs", {})
            if not isinstance(existing, dict):
                existing = {}
            existing.update(value)
            state[key] = existing
        elif key in ("audit_trail", "errors") and isinstance(value, list):
            existing = state.get(key, [])
            if not isinstance(existing, list):
                existing = []
            existing.extend(value)
            state[key] = existing
        else:
            state[key] = value


# ══════════════════════════════════════════════════════════════════
# COMMAND GRAPH CLASS
# ══════════════════════════════════════════════════════════════════


class JarvisCommandGraph:
    """The LangGraph-based multi-agent command graph.

    Usage:
      graph = get_command_graph()
      result = graph.run_from_alert(company_id, session_id, user_id, alert, ...)
      result = graph.run_from_nl(company_id, session_id, user_id, "pause all AI", ...)

    The graph can also be used without LangGraph installed — it falls
    back to a simple sequential execution of nodes (BC-008).
    """

    def __init__(self):
        self._graph = None
        self._use_langgraph = False
        self._try_build_graph()

    def _try_build_graph(self):
        """Try to build a LangGraph StateGraph. Falls back to manual execution."""
        try:
            from langgraph.graph import StateGraph, END

            graph = StateGraph(JarvisCommandState)

            # Add all nodes
            graph.add_node("command_router", command_router_node)
            graph.add_node("escalation_agent", escalation_agent_node)
            graph.add_node("sla_protection_agent", sla_protection_agent_node)
            graph.add_node("quality_recovery_agent", quality_recovery_agent_node)
            graph.add_node("reassignment_agent", reassignment_agent_node)
            graph.add_node("notification_agent", notification_agent_node)
            graph.add_node("pipeline_query_agent", pipeline_query_agent_node)
            graph.add_node("approval_gate", approval_gate_node)
            graph.add_node("command_executor", command_executor_node)

            # Set entry point
            graph.set_entry_point("command_router")

            # Add conditional edge from router to specialist agents
            graph.add_conditional_edges(
                "command_router",
                _agent_selector,
                {
                    "escalation_agent": "escalation_agent",
                    "sla_protection_agent": "sla_protection_agent",
                    "quality_recovery_agent": "quality_recovery_agent",
                    "reassignment_agent": "reassignment_agent",
                    "notification_agent": "notification_agent",
                    "pipeline_query_agent": "pipeline_query_agent",
                    "approval_gate": "approval_gate",
                },
            )

            # All specialist agents flow to approval gate (Phase 4)
            graph.add_edge("escalation_agent", "approval_gate")
            graph.add_edge("sla_protection_agent", "approval_gate")
            graph.add_edge("quality_recovery_agent", "approval_gate")
            graph.add_edge("reassignment_agent", "approval_gate")
            graph.add_edge("notification_agent", "approval_gate")
            graph.add_edge("pipeline_query_agent", "approval_gate")

            # Approval gate routes to executor (if approved) or END (if pending)
            graph.add_conditional_edges(
                "approval_gate",
                _approval_selector,
                {
                    "command_executor": "command_executor",
                    "__end__": END,
                },
            )

            # Executor is the end
            graph.add_edge("command_executor", END)

            self._graph = graph.compile()
            self._use_langgraph = True

            logger.info("command_graph: langgraph_compiled_successfully")

        except ImportError:
            logger.info("command_graph: langgraph_not_available, using_manual_execution")
            self._graph = None
            self._use_langgraph = False
        except Exception as e:
            logger.warning(
                "command_graph: langgraph_build_failed, using_manual: %s",
                str(e)[:200],
            )
            self._graph = None
            self._use_langgraph = False

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the command graph with the given initial state.

        If LangGraph is available, uses the compiled graph.
        Otherwise, manually executes nodes in sequence.

        Args:
            initial_state: Initial JarvisCommandState dict.

        Returns:
            Final state dict after graph execution.
        """
        start_time = time.monotonic()

        try:
            if self._use_langgraph and self._graph:
                result = self._graph.invoke(initial_state)
            else:
                result = self._run_manual(initial_state)

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

            logger.info(
                "command_graph_complete: company=%s, session=%s, "
                "trigger=%s, agent=%s, action=%s, status=%s, ms=%.1f",
                result.get("company_id", ""),
                result.get("session_id", ""),
                result.get("trigger_type", ""),
                result.get("agent_type", ""),
                result.get("agent_action", ""),
                result.get("execution_status", ""),
                elapsed_ms,
            )

            return result

        except Exception as e:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.exception("command_graph_error: ms=%.1f", elapsed_ms)
            return {
                **initial_state,
                "execution_status": "failed",
                "execution_error": str(e)[:200],
                "execution_time_ms": elapsed_ms,
                "errors": [f"command_graph: {str(e)[:200]}"],
            }

    def _run_manual(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Manual sequential execution when LangGraph is not available.

        Executes: router → agent → executor in sequence, passing
        state updates between nodes. Properly merges dict/list fields.
        """
        # Step 1: Command Router
        router_updates = command_router_node(state)
        _merge_state_updates(state, router_updates)

        # Step 2: Select and run specialist agent
        agent_decision = state.get("router_decision", "notification")
        agent_map = {
            "escalation": escalation_agent_node,
            "sla_protection": sla_protection_agent_node,
            "quality_recovery": quality_recovery_agent_node,
            "reassignment": reassignment_agent_node,
            "notification": notification_agent_node,
            "pipeline_query": pipeline_query_agent_node,
        }

        if agent_decision != "no_action":
            agent_fn = agent_map.get(agent_decision, notification_agent_node)
            agent_updates = agent_fn(state)
            _merge_state_updates(state, agent_updates)

        # Step 3: Approval Gate (Phase 4)
        approval_updates = approval_gate_node(state)
        _merge_state_updates(state, approval_updates)

        # Step 3b: If pending approval, stop here (don't execute)
        if state.get("execution_status") == "pending_approval":
            return state

        # Step 4: Command Executor
        executor_updates = command_executor_node(state)
        _merge_state_updates(state, executor_updates)

        # Step 5: Apply command feedback to pipeline (Phase 4)
        try:
            from app.services.jarvis_agents.pipeline_feedback import (
                apply_command_feedback_sync,
            )
            apply_command_feedback_sync(
                company_id=state.get("company_id", ""),
                session_id=state.get("session_id", ""),
                command_result=state,
            )
        except Exception:
            logger.debug("pipeline_feedback_non_fatal", exc_info=True)

        return state

    def run_from_alert(
        self,
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
        """Run the command graph triggered by an awareness alert.

        This is how Jarvis goes from "I noticed something" to "I did something."
        Called by the awareness engine or proactive injector when a critical
        alert needs automated action.

        Args:
            company_id: Company ID for BC-001.
            session_id: CC session ID.
            user_id: User ID for audit.
            alert_id: The triggering alert's ID.
            alert_type: Type of alert (e.g., ticket_volume_spike).
            alert_severity: Alert severity.
            alert_message: Human-readable alert message.
            alert_details: Structured alert details.
            awareness_snapshot: Current awareness state.
            session_context: Current CC session context.
            variant_tier: Current variant tier.

        Returns:
            Final command state dict with execution results.
        """
        initial_state = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id=alert_id,
            alert_type=alert_type,
            alert_severity=alert_severity,
            alert_message=alert_message,
            alert_details=alert_details,
            awareness_snapshot=awareness_snapshot,
            session_context=session_context,
            variant_tier=variant_tier,
        )

        return self.run(initial_state)

    def run_from_nl(
        self,
        company_id: str,
        session_id: str,
        user_id: str,
        raw_input: str,
        awareness_snapshot: Optional[Dict[str, Any]] = None,
        session_context: Optional[Dict[str, Any]] = None,
        variant_tier: str = "mini_parwa",
    ) -> Dict[str, Any]:
        """Run the command graph triggered by a user's natural language command.

        This is how a user's command like "pause all AI" enters the
        multi-agent system and gets processed intelligently.

        Args:
            company_id: Company ID for BC-001.
            session_id: CC session ID.
            user_id: User ID for audit.
            raw_input: The natural language command text.
            awareness_snapshot: Current awareness state.
            session_context: Current CC session context.
            variant_tier: Current variant tier.

        Returns:
            Final command state dict with execution results.
        """
        initial_state = create_command_state_from_nl(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            raw_input=raw_input,
            awareness_snapshot=awareness_snapshot,
            session_context=session_context,
            variant_tier=variant_tier,
        )

        return self.run(initial_state)


# ══════════════════════════════════════════════════════════════════
# SINGLETON + CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

_graph_instance: Optional[JarvisCommandGraph] = None


def get_command_graph() -> JarvisCommandGraph:
    """Get or create the global command graph instance."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = JarvisCommandGraph()
    return _graph_instance


def run_command_from_alert(
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
    """Convenience function: run command graph from an awareness alert."""
    graph = get_command_graph()
    return graph.run_from_alert(
        company_id=company_id,
        session_id=session_id,
        user_id=user_id,
        alert_id=alert_id,
        alert_type=alert_type,
        alert_severity=alert_severity,
        alert_message=alert_message,
        alert_details=alert_details,
        awareness_snapshot=awareness_snapshot,
        session_context=session_context,
        variant_tier=variant_tier,
    )


def run_command_from_nl(
    company_id: str,
    session_id: str,
    user_id: str,
    raw_input: str,
    awareness_snapshot: Optional[Dict[str, Any]] = None,
    session_context: Optional[Dict[str, Any]] = None,
    variant_tier: str = "mini_parwa",
) -> Dict[str, Any]:
    """Convenience function: run command graph from a user NL command."""
    graph = get_command_graph()
    return graph.run_from_nl(
        company_id=company_id,
        session_id=session_id,
        user_id=user_id,
        raw_input=raw_input,
        awareness_snapshot=awareness_snapshot,
        session_context=session_context,
        variant_tier=variant_tier,
    )
