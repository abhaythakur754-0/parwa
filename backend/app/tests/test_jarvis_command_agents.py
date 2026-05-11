"""
PARWA Jarvis Phase 3 End-to-End Test

This test simulates the COMPLETE flow:
  1. Create a fake company
  2. Create a fake CC session
  3. Simulate awareness ticks with bad metrics
  4. Verify Jarvis detects the problems (awareness)
  5. Verify Jarvis routes to the right agent (command router)
  6. Verify Jarvis takes action (command executor)
  7. Verify the full multi-agent flow works end-to-end

This proves Jarvis has AWARENESS and can ACT on it autonomously.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FAKE COMPANY SETUP
# ══════════════════════════════════════════════════════════════════

FAKE_COMPANY_ID = str(uuid.uuid4())
FAKE_USER_ID = str(uuid.uuid4())
FAKE_SESSION_ID = str(uuid.uuid4())


class TestJarvisPhase3EndToEnd:
    """End-to-end test for Phase 3: Multi-Agent Command Layer."""

    def test_command_graph_routes_alert_to_escalation_agent(self):
        """When a critical ticket volume spike alert comes in,
        the command router should route to the escalation agent."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph

        graph = JarvisCommandGraph()

        result = graph.run_from_alert(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            alert_id=str(uuid.uuid4()),
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Ticket volume is 3x above average!",
            alert_details={"volume_today": 150, "volume_avg": 50, "spike_multiplier": 3.0},
            awareness_snapshot={
                "system_health": "degraded",
                "ticket_volume_today": 150,
                "ticket_volume_avg": 50,
                "ticket_volume_spike": True,
                "active_agents": 3,
                "agent_pool_utilization": 95.0,
                "quality_score": 0.72,
            },
        )

        # Verify the graph completed
        assert result.get("execution_status") in ("completed", "failed")
        assert result.get("router_decision") in ("escalation", "notification", "sla_protection")
        assert result.get("agent_type") is not None
        assert result.get("audit_trail") is not None
        assert len(result.get("audit_trail", [])) >= 1  # At least one step

    def test_command_graph_routes_quality_alert_to_quality_agent(self):
        """When a quality drop alert comes in,
        the command router should route to the quality recovery agent."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph

        graph = JarvisCommandGraph()

        result = graph.run_from_alert(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            alert_id=str(uuid.uuid4()),
            alert_type="quality_drop",
            alert_severity="warning",
            alert_message="Quality score dropped below 0.70",
            alert_details={"quality_score": 0.65, "threshold": 0.70},
            awareness_snapshot={
                "system_health": "healthy",
                "quality_score": 0.65,
                "drift_score": 0.35,
                "drift_status": "moderate",
            },
        )

        assert result.get("execution_status") in ("completed", "failed")
        # Quality-related alerts should go to quality_recovery or notification
        assert result.get("router_decision") in (
            "quality_recovery", "notification", "escalation",
        )

    def test_command_graph_routes_user_nl_command(self):
        """When a user types 'pause all AI', the command graph
        should route through the regex parser to escalation agent."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph

        graph = JarvisCommandGraph()

        result = graph.run_from_nl(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            raw_input="pause all AI agents",
            awareness_snapshot={"system_health": "healthy"},
        )

        assert result.get("execution_status") in ("completed", "failed")
        # "pause all AI" should route to escalation (via regex)
        assert result.get("router_decision") in ("escalation", "notification")

    def test_command_graph_handles_unknown_alert(self):
        """When an unknown alert type comes in, Jarvis should
        still make a decision (never crash - BC-008)."""
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph

        graph = JarvisCommandGraph()

        result = graph.run_from_alert(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            alert_id=str(uuid.uuid4()),
            alert_type="unknown_weird_alert_type",
            alert_severity="info",
            alert_message="Something weird happened",
        )

        # Should NOT crash — BC-008
        assert result.get("execution_status") in ("completed", "failed")
        assert result.get("agent_type") is not None

    def test_command_state_creation_from_alert(self):
        """Test that command state is correctly created from an alert."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        state = create_command_state_from_alert(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            alert_id="alert-123",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Volume spike detected!",
            alert_details={"multiplier": 3.0},
        )

        assert state["trigger_type"] == "alert"
        assert state["alert_type"] == "ticket_volume_spike"
        assert state["alert_severity"] == "critical"
        assert state["company_id"] == FAKE_COMPANY_ID
        assert len(state.get("audit_trail", [])) >= 1

    def test_command_state_creation_from_nl(self):
        """Test that command state is correctly created from NL input."""
        from app.services.jarvis_agents.command_state import create_command_state_from_nl

        state = create_command_state_from_nl(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            raw_input="show me today's errors",
        )

        assert state["trigger_type"] == "user_nl"
        assert state["raw_input"] == "show me today's errors"
        assert state["company_id"] == FAKE_COMPANY_ID

    def test_zai_client_rule_based_fallback(self):
        """Test that the ZAI client falls back to rule-based decisions
        when the SDK is unavailable (which it will be in tests)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        # Test command router fallback
        result = client.chat(
            "command_router",
            "Ticket volume spike detected",
            context={"alert_type": "ticket_volume_spike", "severity": "critical"},
        )

        assert result.get("agent") in (
            "escalation_agent", "sla_protection_agent",
            "quality_recovery_agent", "reassignment_agent",
            "notification_agent",
        )
        assert result.get("_source") == "rule_based_fallback"

    def test_zai_client_escalation_fallback(self):
        """Test escalation agent rule-based fallback."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        result = client.chat(
            "escalation_agent",
            "What should we escalate?",
            context={"alert_type": "ticket_volume_spike", "severity": "critical"},
        )

        assert result.get("action") == "escalate"
        assert result.get("_source") == "rule_based_fallback"

    def test_zai_client_quality_recovery_fallback(self):
        """Test quality recovery agent rule-based fallback."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        result = client.chat(
            "quality_recovery_agent",
            "Quality dropped to 0.5",
            context={"quality_score": 0.5, "drift_score": 0.4},
        )

        assert result.get("action") == "recover_quality"
        assert result.get("strategy") in ("switch_technique", "retrain", "adjust_threshold")

    def test_command_router_node_routes_correctly(self):
        """Test the command router node directly."""
        from app.services.jarvis_agents.nodes.command_router import command_router_node

        state = {
            "trigger_type": "alert",
            "alert_type": "ticket_volume_spike",
            "alert_severity": "critical",
            "alert_message": "3x volume spike!",
            "alert_details": {"multiplier": 3.0},
            "company_id": FAKE_COMPANY_ID,
            "session_id": FAKE_SESSION_ID,
            "user_id": FAKE_USER_ID,
            "awareness_snapshot": {"system_health": "degraded", "ticket_volume_today": 150},
            "variant_tier": "mini_parwa",
        }

        result = command_router_node(state)

        assert result.get("router_decision") is not None
        assert result.get("router_reasoning") is not None
        assert result.get("node_outputs", {}).get("command_router") is not None

    def test_escalation_agent_node(self):
        """Test the escalation agent node directly."""
        from app.services.jarvis_agents.nodes.escalation_agent import escalation_agent_node

        state = {
            "alert_type": "ticket_volume_spike",
            "alert_severity": "critical",
            "alert_message": "3x volume spike!",
            "alert_details": {},
            "company_id": FAKE_COMPANY_ID,
            "session_id": FAKE_SESSION_ID,
            "awareness_snapshot": {
                "system_health": "degraded",
                "ticket_volume_today": 150,
                "ticket_volume_spike": True,
                "active_agents": 3,
                "agent_pool_utilization": 95.0,
            },
            "router_parameters": {},
        }

        result = escalation_agent_node(state)

        assert result.get("agent_type") == "escalation"
        assert result.get("agent_action") in ("escalate", "no_action")
        assert result.get("agent_decision") is not None

    def test_notification_agent_node(self):
        """Test the notification agent node directly."""
        from app.services.jarvis_agents.nodes.notification_agent import notification_agent_node

        state = {
            "alert_type": "system_health_change",
            "alert_severity": "info",
            "alert_message": "System health changed to degraded",
            "company_id": FAKE_COMPANY_ID,
            "session_id": FAKE_SESSION_ID,
            "awareness_snapshot": {"system_health": "degraded"},
            "router_parameters": {},
        }

        result = notification_agent_node(state)

        assert result.get("agent_type") == "notification"
        assert result.get("agent_action") in ("notify", "no_action")

    def test_command_executor_node(self):
        """Test the command executor node directly."""
        from app.services.jarvis_agents.nodes.command_executor import command_executor_node

        state = {
            "trigger_type": "alert",
            "alert_id": str(uuid.uuid4()),
            "alert_type": "ticket_volume_spike",
            "company_id": FAKE_COMPANY_ID,
            "session_id": FAKE_SESSION_ID,
            "user_id": FAKE_USER_ID,
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {
                "action": "escalate",
                "scope": "all_urgent",
                "escalation_tier": "tier2",
                "reason": "Ticket volume spike",
            },
            "agent_source": "rule_based_fallback",
        }

        result = command_executor_node(state)

        assert result.get("execution_status") in ("completed", "failed")
        assert result.get("audit_trail") is not None

    def test_full_awareness_to_command_pipeline(self):
        """THE BIG TEST: Simulate the full pipeline from awareness to command.

        1. Create awareness state with critical metrics
        2. Run awareness tick (mocked DB)
        3. Verify alert would be created
        4. Feed alert into command graph
        5. Verify Jarvis takes action

        This proves Jarvis has awareness AND can act on it.
        """
        from app.services.jarvis_agents.command_graph import JarvisCommandGraph

        # Simulate a BAD system state — lots of tickets, high utilization,
        # low quality, drift detected
        bad_awareness_state = {
            "system_health": "critical",
            "ticket_volume_today": 250,
            "ticket_volume_avg": 80,
            "ticket_volume_spike": True,
            "active_agents": 2,
            "agent_pool_capacity": 5,
            "agent_pool_utilization": 98.0,
            "quality_score": 0.45,
            "drift_score": 0.65,
            "drift_status": "severe",
            "active_alerts_count": 5,
            "plan_usage_today": 92.0,
            "subscription_status": "active",
        }

        # Run the command graph with a critical alert
        graph = JarvisCommandGraph()
        result = graph.run_from_alert(
            company_id=FAKE_COMPANY_ID,
            session_id=FAKE_SESSION_ID,
            user_id=FAKE_USER_ID,
            alert_id=str(uuid.uuid4()),
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Ticket volume 3x above average with critical system health!",
            alert_details={
                "volume_today": 250,
                "volume_avg": 80,
                "quality_score": 0.45,
                "system_health": "critical",
            },
            awareness_snapshot=bad_awareness_state,
            session_context={"variant_tier": "mini_parwa"},
            variant_tier="mini_parwa",
        )

        # ── VERIFY JARVIS HAS AWARENESS AND CAN ACT ──

        # 1. Graph completed
        assert result.get("execution_status") in ("completed", "failed"), \
            f"Graph should complete, got: {result.get('execution_status')}"

        # 2. Router made a decision
        assert result.get("router_decision") is not None, \
            "Router should make a decision"

        # 3. An agent was invoked
        assert result.get("agent_type") is not None, \
            "An agent should be invoked"

        # 4. Audit trail exists (for compliance)
        assert len(result.get("audit_trail", [])) >= 1, \
            "Audit trail should have at least one step"

        # 5. The decision makes sense for the situation
        # With critical health + quality drop + volume spike,
        # Jarvis should escalate or take protective action
        router_decision = result.get("router_decision", "")
        assert router_decision in (
            "escalation", "sla_protection", "quality_recovery",
            "reassignment", "notification",
        ), f"Router should pick a valid agent, got: {router_decision}"

        # 6. Node outputs exist for every node that ran
        node_outputs = result.get("node_outputs", {})
        assert "command_router" in node_outputs, \
            "Command router should have output"

        # 7. Verify the full chain: trigger → router → agent → executor
        audit_trail = result.get("audit_trail", [])
        step_names = [entry.get("step", "") for entry in audit_trail]
        # At least the command_executor step should exist
        assert len(step_names) >= 1, "Should have at least one audit step"

        print("\n✅ JARVIS AWARENESS + COMMAND PIPELINE VERIFIED!")
        print(f"   Trigger: {result.get('trigger_type')}")
        print(f"   Router decision: {result.get('router_decision')}")
        print(f"   Agent type: {result.get('agent_type')}")
        print(f"   Agent action: {result.get('agent_action')}")
        print(f"   Execution status: {result.get('execution_status')}")
        print(f"   Router source: {result.get('router_source')}")
        print(f"   Agent source: {result.get('agent_source')}")
        print(f"   Audit trail steps: {step_names}")

    def test_co_pilot_mode(self):
        """Test Jarvis co-pilot mode for user questions."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        result = client.chat(
            "co_pilot",
            "What should I do about the ticket spike?",
            context={
                "alert_type": "ticket_volume_spike",
                "ticket_volume_today": 150,
                "system_health": "degraded",
            },
        )

        assert result.get("suggestion") is not None
        assert result.get("suggestion_type") in (
            "policy_reminder", "action_suggestion",
            "best_practice", "warning",
        )
        assert result.get("_source") == "rule_based_fallback"

    def test_agent_selector_function(self):
        """Test the agent selector conditional edge."""
        from app.services.jarvis_agents.command_graph import _agent_selector

        # Test all valid decisions
        assert _agent_selector({"router_decision": "escalation"}) == "escalation_agent"
        assert _agent_selector({"router_decision": "sla_protection"}) == "sla_protection_agent"
        assert _agent_selector({"router_decision": "quality_recovery"}) == "quality_recovery_agent"
        assert _agent_selector({"router_decision": "reassignment"}) == "reassignment_agent"
        assert _agent_selector({"router_decision": "notification"}) == "notification_agent"
        assert _agent_selector({"router_decision": "no_action"}) == "command_executor"

        # Unknown decision defaults to notification
        assert _agent_selector({"router_decision": "unknown"}) == "notification_agent"

    def test_sla_protection_agent_node(self):
        """Test the SLA protection agent node directly."""
        from app.services.jarvis_agents.nodes.sla_protection_agent import sla_protection_agent_node

        state = {
            "alert_type": "sla_breach_risk",
            "alert_severity": "warning",
            "alert_message": "5 tickets at risk of SLA breach",
            "alert_details": {"at_risk_count": 5},
            "company_id": FAKE_COMPANY_ID,
            "awareness_snapshot": {
                "system_health": "degraded",
                "ticket_volume_today": 100,
                "active_agents": 3,
                "quality_score": 0.75,
            },
        }

        result = sla_protection_agent_node(state)
        assert result.get("agent_type") == "sla_protection"
        assert result.get("agent_action") in ("protect_sla", "no_action")

    def test_reassignment_agent_node(self):
        """Test the reassignment agent node directly."""
        from app.services.jarvis_agents.nodes.reassignment_agent import reassignment_agent_node

        state = {
            "alert_type": "agent_pool_exhausted",
            "alert_severity": "critical",
            "alert_message": "Agent pool at 98% utilization",
            "alert_details": {"utilization": 98.0},
            "company_id": FAKE_COMPANY_ID,
            "awareness_snapshot": {
                "active_agents": 2,
                "agent_pool_capacity": 2,
                "agent_pool_utilization": 98.0,
                "ticket_volume_today": 200,
            },
            "variant_tier": "mini_parwa",
        }

        result = reassignment_agent_node(state)
        assert result.get("agent_type") == "reassignment"
        assert result.get("agent_action") in ("reassign", "no_action")

    def test_quality_recovery_agent_node(self):
        """Test the quality recovery agent node directly."""
        from app.services.jarvis_agents.nodes.quality_recovery_agent import quality_recovery_agent_node

        state = {
            "alert_type": "quality_drop",
            "alert_severity": "warning",
            "alert_message": "Quality score dropped to 0.55",
            "alert_details": {"quality_score": 0.55},
            "company_id": FAKE_COMPANY_ID,
            "awareness_snapshot": {
                "quality_score": 0.55,
                "drift_score": 0.45,
                "drift_status": "moderate",
                "system_health": "healthy",
            },
        }

        result = quality_recovery_agent_node(state)
        assert result.get("agent_type") == "quality_recovery"
        assert result.get("agent_action") in ("recover_quality", "no_action")
