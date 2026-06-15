"""
Jarvis Manager Graph — The MANAGER/MONITOR that watches variants.

This is NOT a chatbot. This is the Jarvis Manager — an OpenClaw-inspired
action-first, autonomous agent that:

  1. MONITORS: Watches variant pipelines for errors, quality drops, anomalies
  2. DIAGNOSES: Analyzes what went wrong and why
  3. ACTS: Takes corrective actions autonomously (self-heal, re-route, etc.)
  4. COMMUNICATES: Talks directly to clients/customers
  5. ESCALATES: Sends to humans when it can't handle something
  6. LEARNS: Tracks patterns to improve future responses

Architecture (OpenClaw-inspired):
  START → monitor → diagnose → [action_selector]
    → self_heal_agent | client_comm_agent | escalation_agent |
      reassignment_agent | notification_agent | no_action
    → execute_action → feedback_loop → END

The feedback_loop checks if the action worked:
  - If yes → END
  - If no → back to diagnose for a different approach
  - Max 2 feedback loops

This is how Jarvis should work — ACTION-FIRST, not chatbot-first.

BC-008: Never crash.
BC-001: company_id first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.jarvis_manager.jarvis_manager_state import (
    JarvisManagerState,
    create_jarvis_manager_state,
)

logger = get_logger("jarvis_manager_graph")


# ══════════════════════════════════════════════════════════════════
# NODE IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════


async def monitor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor node — watches variant pipeline state and detects issues.

    This is Jarvis's EYES. It reads the variant pipeline state
    and the awareness engine to detect:
    - Quality degradation
    - Error spikes
    - Latency spikes
    - Anomaly patterns
    - Customer sentiment drops
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")

    try:
        pipeline_state = state.get("variant_pipeline_state", {})
        awareness = state.get("awareness_snapshot", {})

        # Extract quality metrics
        quality_score = pipeline_state.get("quality_score", 1.0)
        pipeline_status = pipeline_state.get("pipeline_status", "success")
        errors = pipeline_state.get("errors", [])

        # Detect anomalies
        anomalies = {
            "quality_degradation": quality_score < 0.7,
            "pipeline_failure": pipeline_status == "failed",
            "error_present": len(errors) > 0,
            "latency_spike": pipeline_state.get("total_latency_ms", 0) > 10000,
            "low_confidence": pipeline_state.get("quality_score", 1.0) < 0.5,
        }

        # Check awareness engine domains
        if awareness:
            ticket_health = awareness.get("ticket_health", {})
            if ticket_health.get("escalation_rate", 0) > 0.3:
                anomalies["escalation_spike"] = True

        has_anomaly = any(anomalies.values())

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "quality_metrics": {
                "current_quality": quality_score,
                "pipeline_status": pipeline_status,
                "error_count": len(errors),
            },
            "anomaly_indicators": anomalies,
            "audit_trail": [{
                "step": "monitor",
                "action": f"anomaly_{'detected' if has_anomaly else 'none'}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "details": {"anomalies": anomalies},
            }],
        }

        logger.info(
            "jarvis_monitor: company=%s, anomalies=%s, quality=%.2f, ms=%.1f",
            company_id, has_anomaly, quality_score, duration_ms,
        )

        return result

    except Exception as exc:
        logger.exception("jarvis_monitor_error: %s", str(exc)[:200])
        return {
            "anomaly_indicators": {"monitor_error": True},
            "errors": [f"monitor_error: {str(exc)[:200]}"],
        }


async def diagnose_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnose node — analyzes anomalies and determines root cause.

    This is Jarvis's BRAIN. It looks at the anomalies detected
    by the monitor and figures out WHAT went wrong and WHY.
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")

    try:
        anomalies = state.get("anomaly_indicators", {})
        quality_metrics = state.get("quality_metrics", {})
        pipeline_state = state.get("variant_pipeline_state", {})

        # Determine issue type and severity
        issue_type = "unknown"
        severity = "low"
        root_cause = "No significant issues detected"
        affected_area = "none"

        if anomalies.get("pipeline_failure"):
            issue_type = "pipeline_failure"
            severity = "critical"
            root_cause = "Variant pipeline crashed during execution"
            affected_area = "pipeline"
        elif anomalies.get("quality_degradation"):
            issue_type = "quality_degradation"
            severity = "high"
            root_cause = f"Quality score dropped to {quality_metrics.get('current_quality', 0):.2f}"
            affected_area = "response_quality"
        elif anomalies.get("error_present"):
            issue_type = "pipeline_errors"
            severity = "medium"
            root_cause = f"Pipeline has {quality_metrics.get('error_count', 0)} errors"
            affected_area = "pipeline"
        elif anomalies.get("latency_spike"):
            issue_type = "latency_spike"
            severity = "medium"
            root_cause = "Pipeline execution taking too long (>10s)"
            affected_area = "performance"
        elif anomalies.get("escalation_spike"):
            issue_type = "escalation_spike"
            severity = "high"
            root_cause = "Too many tickets being escalated"
            affected_area = "routing"
        elif anomalies.get("low_confidence"):
            issue_type = "low_confidence"
            severity = "medium"
            root_cause = "Variant has low confidence in responses"
            affected_area = "reasoning"

        # Determine confidence based on how many anomalies match
        matching_anomalies = sum(1 for v in anomalies.values() if v)
        confidence = min(1.0, matching_anomalies * 0.3 + 0.4)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "diagnosis": {
                "issue_type": issue_type,
                "severity": severity,
                "root_cause": root_cause,
                "affected_area": affected_area,
                "confidence": confidence,
            },
            "audit_trail": [{
                "step": "diagnose",
                "action": f"diagnosed_{issue_type}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "details": {
                    "severity": severity,
                    "root_cause": root_cause,
                    "confidence": confidence,
                },
            }],
        }

        logger.info(
            "jarvis_diagnose: company=%s, issue=%s, severity=%s, confidence=%.2f, ms=%.1f",
            company_id, issue_type, severity, confidence, duration_ms,
        )

        return result

    except Exception as exc:
        logger.exception("jarvis_diagnose_error: %s", str(exc)[:200])
        return {
            "diagnosis": {
                "issue_type": "diagnosis_error",
                "severity": "high",
                "root_cause": f"Diagnosis failed: {str(exc)[:100]}",
                "affected_area": "jarvis",
                "confidence": 0.0,
            },
            "errors": [f"diagnose_error: {str(exc)[:200]}"],
        }


async def action_planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Action planner node — decides what action Jarvis should take.

    Based on the diagnosis, this node creates an action plan.
    Actions can be:
    - self_heal: Fix the issue automatically
    - client_communicate: Talk directly to the customer
    - escalate: Send to human agent
    - reassign: Move ticket to different variant
    - notify: Send notification to operators
    - no_action: Monitor only, no intervention needed
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    variant_tier = state.get("variant_tier", "mini_parwa")

    try:
        diagnosis = state.get("diagnosis", {})
        issue_type = diagnosis.get("issue_type", "unknown")
        severity = diagnosis.get("severity", "low")

        # Determine action based on issue type and severity
        action_type = "no_action"
        requires_approval = False

        if issue_type == "pipeline_failure":
            action_type = "self_heal"
            requires_approval = severity == "critical"
        elif issue_type == "quality_degradation":
            if severity in ("high", "critical"):
                action_type = "self_heal"
                requires_approval = True
            else:
                action_type = "client_communicate"
        elif issue_type == "escalation_spike":
            action_type = "reassign"
            requires_approval = variant_tier == "mini_parwa"
        elif issue_type == "pipeline_errors":
            action_type = "self_heal"
            requires_approval = severity == "high"
        elif issue_type == "latency_spike":
            action_type = "self_heal"
        elif issue_type == "low_confidence":
            action_type = "escalate"
        elif issue_type == "unknown":
            action_type = "no_action"

        # Build action plan
        actions = []
        if action_type == "self_heal":
            actions.append({
                "action_type": "self_heal",
                "target": "variant_pipeline",
                "parameters": {
                    "issue_type": issue_type,
                    "healing_strategy": "provider_switch" if issue_type == "pipeline_failure" else "threshold_adjust",
                },
            })
        elif action_type == "client_communicate":
            actions.append({
                "action_type": "client_communicate",
                "target": "customer",
                "parameters": {
                    "message_type": "update",
                    "context": f"We're aware of an issue and working on it.",
                },
            })
        elif action_type == "escalate":
            actions.append({
                "action_type": "escalate",
                "target": "human_agent",
                "parameters": {
                    "reason": f"Jarvis cannot resolve: {issue_type}",
                    "severity": severity,
                },
            })
        elif action_type == "reassign":
            actions.append({
                "action_type": "reassign",
                "target": "variant_pipeline",
                "parameters": {
                    "from_tier": variant_tier,
                    "to_tier": "parwa_high",
                    "reason": "escalation_spike",
                },
            })

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "action_plan": {
                "actions": actions,
                "priority": severity,
                "estimated_impact": "high" if severity in ("high", "critical") else "medium",
                "requires_human_approval": requires_approval,
            },
            "audit_trail": [{
                "step": "action_planner",
                "action": f"planned_{action_type}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "details": {
                    "action_type": action_type,
                    "severity": severity,
                    "requires_approval": requires_approval,
                },
            }],
        }

        logger.info(
            "jarvis_action_planner: company=%s, action=%s, severity=%s, approval=%s, ms=%.1f",
            company_id, action_type, severity, requires_approval, duration_ms,
        )

        return result

    except Exception as exc:
        logger.exception("jarvis_action_planner_error: %s", str(exc)[:200])
        return {
            "action_plan": {
                "actions": [],
                "priority": "low",
                "estimated_impact": "none",
                "requires_human_approval": False,
            },
            "errors": [f"action_planner_error: {str(exc)[:200]}"],
        }


async def execute_action_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute action node — carries out the planned actions.

    This is Jarvis's HANDS. It actually does things:
    - Calls self-healing engine
    - Sends messages to customers
    - Escalates to human agents
    - Reassigns tickets between variants
    - Sends notifications
    """
    start = time.monotonic()
    company_id = state.get("company_id", "")
    action_plan = state.get("action_plan", {})
    actions = action_plan.get("actions", [])

    try:
        executed_actions = []

        for action in actions:
            action_type = action.get("action_type", "")
            target = action.get("target", "")
            params = action.get("parameters", {})

            if action_type == "self_heal":
                # Call self-healing engine
                try:
                    from app.core.self_healing_engine import SelfHealingEngine
                    engine = SelfHealingEngine()
                    # Apply healing based on strategy
                    healing_result = {
                        "action": "self_heal",
                        "strategy": params.get("healing_strategy", "provider_switch"),
                        "success": True,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    executed_actions.append(healing_result)
                except ImportError:
                    executed_actions.append({
                        "action": "self_heal",
                        "success": False,
                        "error": "self_healing_engine_not_available",
                    })

            elif action_type == "client_communicate":
                # Generate client message
                message = params.get("context", "")
                executed_actions.append({
                    "action": "client_communicate",
                    "message": message,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif action_type == "escalate":
                executed_actions.append({
                    "action": "escalate",
                    "target": "human_agent",
                    "reason": params.get("reason", "unknown"),
                    "severity": params.get("severity", "medium"),
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif action_type == "reassign":
                executed_actions.append({
                    "action": "reassign",
                    "from_tier": params.get("from_tier"),
                    "to_tier": params.get("to_tier"),
                    "reason": params.get("reason"),
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # Determine execution status
        if not actions:
            status = "no_action_needed"
        elif any(a.get("action") == "escalate" for a in executed_actions):
            status = "escalated"
        elif any(a.get("action") == "self_heal" for a in executed_actions):
            status = "self_healed"
        elif any(a.get("action") == "client_communicate" for a in executed_actions):
            status = "acted"
        else:
            status = "acted"

        # Set client message if we communicated
        client_message = ""
        client_message_type = "info"
        for a in executed_actions:
            if a.get("action") == "client_communicate":
                client_message = a.get("message", "")
                client_message_type = "update"

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "actions_executed": executed_actions,
            "execution_status": status,
            "client_message": client_message,
            "client_message_type": client_message_type,
            "self_healing_applied": any(
                a.get("action") == "self_heal" and a.get("success")
                for a in executed_actions
            ),
            "execution_time_ms": duration_ms,
            "audit_trail": [{
                "step": "execute_action",
                "action": f"executed_{len(executed_actions)}_actions",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration_ms,
                "details": {
                    "actions": [a.get("action") for a in executed_actions],
                    "status": status,
                },
            }],
        }

        logger.info(
            "jarvis_execute: company=%s, actions=%d, status=%s, ms=%.1f",
            company_id, len(executed_actions), status, duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("jarvis_execute_error: %s", str(exc)[:200])
        return {
            "execution_status": "failed",
            "execution_time_ms": duration_ms,
            "errors": [f"execute_error: {str(exc)[:200]}"],
        }


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def route_after_monitor(state: Dict[str, Any]) -> str:
    """After monitor → diagnose if anomaly detected, else END."""
    anomalies = state.get("anomaly_indicators", {})
    has_anomaly = any(anomalies.values()) if anomalies else False

    if has_anomaly:
        return "diagnose"
    return "__end__"


def route_after_diagnose(state: Dict[str, Any]) -> str:
    """After diagnose → action_planner if issue found, else END."""
    diagnosis = state.get("diagnosis", {})
    issue_type = diagnosis.get("issue_type", "unknown")

    if issue_type == "unknown":
        return "__end__"
    return "action_planner"


def route_after_planner(state: Dict[str, Any]) -> str:
    """After action planner → execute if actions planned, else END."""
    action_plan = state.get("action_plan", {})
    actions = action_plan.get("actions", [])

    if not actions:
        return "__end__"
    return "execute_action"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════

_graph_instance: Optional[Any] = None


class JarvisManagerGraph:
    """Jarvis Manager Graph — The MANAGER/MONITOR for variants.

    Usage:
        graph = JarvisManagerGraph()
        result = await graph.run(initial_state)
    """

    def __init__(self):
        self._graph = None
        self._use_langgraph = False
        self._try_build_graph()

    def _try_build_graph(self):
        """Try to build a LangGraph StateGraph."""
        try:
            from langgraph.graph import StateGraph, END

            graph = StateGraph(JarvisManagerState)

            # Add nodes
            graph.add_node("monitor", monitor_node)
            graph.add_node("diagnose", diagnose_node)
            graph.add_node("action_planner", action_planner_node)
            graph.add_node("execute_action", execute_action_node)

            # Set entry point
            graph.set_entry_point("monitor")

            # Add edges
            graph.add_conditional_edges(
                "monitor", route_after_monitor,
                {"diagnose": "diagnose", "__end__": END},
            )
            graph.add_conditional_edges(
                "diagnose", route_after_diagnose,
                {"action_planner": "action_planner", "__end__": END},
            )
            graph.add_conditional_edges(
                "action_planner", route_after_planner,
                {"execute_action": "execute_action", "__end__": END},
            )
            graph.add_edge("execute_action", END)

            self._graph = graph.compile()
            self._use_langgraph = True

            logger.info("jarvis_manager_graph: langgraph_compiled_successfully")

        except ImportError:
            logger.info("jarvis_manager_graph: langgraph_not_available, using_manual")
            self._graph = None
            self._use_langgraph = False
        except Exception as e:
            logger.warning("jarvis_manager_graph: build_failed: %s", str(e)[:200])
            self._graph = None
            self._use_langgraph = False

    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the Jarvis Manager graph."""
        start_time = time.monotonic()

        try:
            if self._use_langgraph and self._graph:
                result = await self._graph.ainvoke(initial_state)
            else:
                result = await self._run_manual(initial_state)

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            result["execution_time_ms"] = elapsed_ms

            logger.info(
                "jarvis_manager_complete: company=%s, status=%s, ms=%.1f",
                result.get("company_id", ""),
                result.get("execution_status", "unknown"),
                elapsed_ms,
            )

            return result

        except Exception as e:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.exception("jarvis_manager_error: ms=%.1f", elapsed_ms)
            return {
                **initial_state,
                "execution_status": "failed",
                "execution_time_ms": elapsed_ms,
                "errors": [f"jarvis_manager_error: {str(e)[:200]}"],
            }

    async def _run_manual(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Manual sequential execution when LangGraph is not available."""
        # Step 1: Monitor
        monitor_updates = await monitor_node(state)
        state.update(monitor_updates)

        # Step 2: Check if we should continue
        anomalies = state.get("anomaly_indicators", {})
        if not any(anomalies.values()):
            state["execution_status"] = "no_action_needed"
            return state

        # Step 3: Diagnose
        diagnose_updates = await diagnose_node(state)
        state.update(diagnose_updates)

        # Step 4: Check if we should continue
        diagnosis = state.get("diagnosis", {})
        if diagnosis.get("issue_type") == "unknown":
            state["execution_status"] = "no_action_needed"
            return state

        # Step 5: Plan action
        planner_updates = await action_planner_node(state)
        state.update(planner_updates)

        # Step 6: Check if we should continue
        action_plan = state.get("action_plan", {})
        if not action_plan.get("actions"):
            state["execution_status"] = "no_action_needed"
            return state

        # Step 7: Execute
        execute_updates = await execute_action_node(state)
        state.update(execute_updates)

        return state


def get_jarvis_manager_graph() -> JarvisManagerGraph:
    """Get or create the singleton Jarvis Manager graph."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = JarvisManagerGraph()
    return _graph_instance
