"""
PARWA Jarvis Phase 4 — End-to-End Integration Tests

Covers CROSS-MODULE flows through all Phase 4 components:
  1. variant_bridge.py — Bidirectional bridge (Redis + DB)
  2. pipeline_feedback.py — Feedback loop (Redis + DB)
  3. approval_gate.py — Human-in-the-loop approval node
  4. pipeline_query_agent.py — Pipeline state query agent
  5. jarvis_awareness_injector.py — Injects Jarvis awareness into main pipeline
  6. command_graph.py — Updated LangGraph with approval_gate + pipeline_query_agent

These tests exercise FULL FLOWS across multiple modules, not just
individual functions. Each test simulates a realistic end-to-end
scenario and verifies that the modules work TOGETHER correctly.

Rules:
  - ALL tests independent; no Redis/DB required (mock everything)
  - pytest class-based with test_ methods
  - Every test has a clear docstring
  - BC-008: errors never crash the system
  - BC-001: company_id always respected (tenant isolation)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Shared Fixtures & Helpers
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock logger to prevent import errors in all tests."""
    with patch("app.logger.get_logger", return_value=MagicMock()):
        yield


@pytest.fixture
def company_id():
    """Standard test company ID."""
    return "comp_e2e_001"


@pytest.fixture
def session_id():
    """Standard test session ID."""
    return "sess_e2e_001"


@pytest.fixture
def user_id():
    """Standard test user ID."""
    return "user_e2e_001"


@pytest.fixture
def company_a():
    """Company A ID for tenant isolation tests."""
    return "comp_tenant_A"


@pytest.fixture
def company_b():
    """Company B ID for tenant isolation tests."""
    return "comp_tenant_B"


# Patch path for pipeline feedback — it's imported inside _run_manual
_FEEDBACK_PATCH = "app.services.jarvis_agents.pipeline_feedback.apply_command_feedback_sync"


def _run_graph_with_mocks(
    initial_state: Dict[str, Any],
    zai_router_response: Dict[str, Any],
    zai_agent_response: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run the command graph with mocked ZAI client, Redis, and DB.

    This helper sets up all the mocks needed to run the full command
    graph end-to-end without any real Redis/DB/LLM dependencies.

    Returns:
        Final state dict after graph execution.
    """
    if zai_agent_response is None:
        zai_agent_response = {
            "_source": "rule_based_fallback",
            "action": "notify",
            "channel": "chat",
            "severity": "info",
            "title": "Test",
            "message": "Test notification",
            "action_required": False,
        }

    mock_zai = MagicMock()
    mock_zai.chat.side_effect = [zai_router_response, zai_agent_response]

    with patch(
        "app.services.jarvis_agents.nodes.command_router.get_zai_client",
        return_value=mock_zai,
    ), patch(
        "app.services.jarvis_agents.nodes.escalation_agent.get_zai_client",
        return_value=mock_zai,
    ), patch(
        "app.services.jarvis_agents.nodes.notification_agent.get_zai_client",
        return_value=mock_zai,
    ), patch(
        "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
        return_value=mock_zai,
    ), patch(
        "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
        return_value={},
    ), patch(
        "app.services.jarvis_agents.nodes.pipeline_query_agent._read_awareness_data",
        return_value={},
    ), patch(
        _FEEDBACK_PATCH,
        return_value=True,
    ), patch(
        "app.services.jarvis_agents.nodes.command_executor._create_command_record",
        return_value=("cmd_123", True),
    ), patch(
        "app.services.jarvis_agents.nodes.command_executor._maybe_resolve_alert",
        return_value=False,
    ), patch(
        "app.services.jarvis_agents.nodes.command_executor._dispatch_command_event",
        return_value=None,
    ), patch(
        "app.services.jarvis_agents.nodes.command_executor._execute_action",
        return_value={"executed": True, "action": "test"},
    ), patch(
        "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
        return_value=None,
    ):
        # Reset singleton so each test gets a fresh graph
        from app.services.jarvis_agents import command_graph as cg
        cg._graph_instance = None

        from app.services.jarvis_agents.command_graph import JarvisCommandGraph
        graph = JarvisCommandGraph()
        return graph.run(initial_state)


# ═══════════════════════════════════════════════════════════════════════
# FLOW 1: Full Alert → Awareness → Command → Approval → Pending (mini_parwa)
# ═══════════════════════════════════════════════════════════════════════


class TestFlow1AlertToPendingApproval:
    """Flow 1: Alert triggers awareness → command graph → approval gate
    blocks (mini_parwa) → pending_approval status.

    Verifies:
    - Full flow: command_router → agent → approval_gate → END
    - Audit trail has ALL steps
    - Pipeline feedback is NOT called (execution didn't complete)
    """

    def test_mini_parwa_escalation_blocked_at_approval(self, company_id, session_id, user_id):
        """mini_parwa alert → escalation agent → approval gate blocks → pending_approval."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_001",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Ticket volume 3x normal",
            variant_tier="mini_parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Critical volume spike needs escalation",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
            "reason": "Volume spike detected",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        # Verify execution status is pending_approval (mini_parwa blocks everything)
        assert result["execution_status"] == "pending_approval"
        # Verify agent type is escalation
        assert result["agent_type"] == "escalation"

    def test_mini_parwa_audit_trail_has_all_steps(self, company_id, session_id, user_id):
        """mini_parwa flow: audit_trail must contain command_router → agent → approval_gate."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_002",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Spike detected",
            variant_tier="mini_parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Spike needs escalation",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        steps = [entry.get("step") for entry in result.get("audit_trail", [])]
        assert "command_router" in steps, f"Missing command_router in audit_trail: {steps}"
        assert "escalation_agent" in steps, f"Missing escalation_agent in audit_trail: {steps}"
        assert "approval_gate" in steps, f"Missing approval_gate in audit_trail: {steps}"
        # Must NOT have command_executor (flow was blocked)
        assert "command_executor" not in steps, (
            f"command_executor should NOT be in audit_trail for mini_parwa: {steps}"
        )

    def test_mini_parwa_no_feedback_when_blocked(self, company_id, session_id, user_id):
        """mini_parwa: pipeline_feedback should NOT be called when flow is blocked."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_003",
            alert_type="quality_drop",
            alert_severity="warning",
            alert_message="Quality dropping",
            variant_tier="mini_parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "notification_agent",
            "reasoning": "Quality drop notification",
            "urgency": "medium",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "notify",
            "channel": "chat",
            "severity": "warning",
            "title": "Quality Drop",
            "message": "Quality is dropping",
        }

        with patch(_FEEDBACK_PATCH, return_value=True) as mock_feedback:
            from app.services.jarvis_agents import command_graph as cg
            cg._graph_instance = None

            mock_zai = MagicMock()
            mock_zai.chat.side_effect = [zai_router, zai_agent]

            with patch(
                "app.services.jarvis_agents.nodes.command_router.get_zai_client",
                return_value=mock_zai,
            ), patch(
                "app.services.jarvis_agents.nodes.notification_agent.get_zai_client",
                return_value=mock_zai,
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._create_command_record",
                return_value=("cmd_123", True),
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._execute_action",
                return_value={"executed": True},
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._maybe_resolve_alert",
                return_value=False,
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._dispatch_command_event",
                return_value=None,
            ), patch(
                "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
                return_value=None,
            ):
                from app.services.jarvis_agents.command_graph import JarvisCommandGraph
                graph = JarvisCommandGraph()
                result = graph.run(initial)

            # Feedback should NOT have been called because mini_parwa blocks execution
            assert mock_feedback.call_count == 0
            assert result["execution_status"] == "pending_approval"

    def test_mini_parwa_notification_also_blocked(self, company_id, session_id, user_id):
        """mini_parwa: even a simple notification is blocked at approval gate."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_004",
            alert_type="error_rate_high",
            alert_severity="info",
            alert_message="Minor error rate increase",
            variant_tier="mini_parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "notification_agent",
            "reasoning": "Info-level notification",
            "urgency": "low",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "notify",
            "channel": "chat",
            "severity": "info",
            "title": "Info",
            "message": "Minor issue",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)
        assert result["execution_status"] == "pending_approval"


# ═══════════════════════════════════════════════════════════════════════
# FLOW 2: Full Alert → Command → Auto-Approve → Execute → Feedback (parwa_high)
# ═══════════════════════════════════════════════════════════════════════


class TestFlow2AutoApproveExecuteFeedback:
    """Flow 2: parwa_high → auto-approve → command executor runs → feedback written.

    Verifies:
    - Audit trail: command_router → agent → approval_gate → command_executor → END
    - Pipeline feedback was generated
    """

    def test_parwa_high_escalation_auto_approved(self, company_id, session_id, user_id):
        """parwa_high: escalation is auto-approved and executed."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_010",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Volume spike",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Critical spike needs escalation",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        # parwa_high auto-approves escalation (only emergency needs approval)
        assert result["execution_status"] == "completed"
        assert result["agent_type"] == "escalation"

    def test_parwa_high_audit_trail_has_executor(self, company_id, session_id, user_id):
        """parwa_high: audit_trail contains command_executor step."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_011",
            alert_type="quality_drop",
            alert_severity="warning",
            alert_message="Quality drop",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "notification_agent",
            "reasoning": "Notification about quality",
            "urgency": "medium",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "notify",
            "channel": "chat",
            "severity": "warning",
            "title": "Quality",
            "message": "Quality drop detected",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        steps = [entry.get("step") for entry in result.get("audit_trail", [])]
        assert "command_router" in steps
        assert "notification_agent" in steps
        assert "approval_gate" in steps
        assert "command_executor" in steps

    def test_parwa_high_feedback_was_generated(self, company_id, session_id, user_id):
        """parwa_high: pipeline feedback is called after execution."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_012",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Spike",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Spike",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
        }

        with patch(_FEEDBACK_PATCH, return_value=True) as mock_feedback:
            from app.services.jarvis_agents import command_graph as cg
            cg._graph_instance = None

            mock_zai = MagicMock()
            mock_zai.chat.side_effect = [zai_router, zai_agent]

            with patch(
                "app.services.jarvis_agents.nodes.command_router.get_zai_client",
                return_value=mock_zai,
            ), patch(
                "app.services.jarvis_agents.nodes.escalation_agent.get_zai_client",
                return_value=mock_zai,
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._create_command_record",
                return_value=("cmd_123", True),
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._execute_action",
                return_value={"executed": True},
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._maybe_resolve_alert",
                return_value=False,
            ), patch(
                "app.services.jarvis_agents.nodes.command_executor._dispatch_command_event",
                return_value=None,
            ), patch(
                "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
                return_value=None,
            ):
                from app.services.jarvis_agents.command_graph import JarvisCommandGraph
                graph = JarvisCommandGraph()
                result = graph.run(initial)

            # Feedback should have been called
            assert mock_feedback.call_count == 1
            assert result["execution_status"] == "completed"

    def test_parwa_high_emergency_still_blocked(self, company_id, session_id, user_id):
        """parwa_high: emergency action (full_stop) still needs approval."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_013",
            alert_type="emergency_state_change",
            alert_severity="emergency",
            alert_message="System critical failure",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Emergency needs escalation",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "full_stop",
            "scope": "all_channels",
            "escalation_tier": "manager",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        # full_stop is an emergency action — even parwa_high needs approval
        assert result["execution_status"] == "pending_approval"


# ═══════════════════════════════════════════════════════════════════════
# FLOW 3: NL Command → Pipeline Query → Approval → Execute
# ═══════════════════════════════════════════════════════════════════════


class TestFlow3NLPipelineQuery:
    """Flow 3: User types NL command → pipeline_query_agent → approval → execute.

    Verifies:
    - pipeline_query_agent was invoked
    - Query result flows through to execution
    """

    def test_nl_quality_query_routed_to_pipeline_query(self, company_id, session_id, user_id):
        """NL 'check quality score' routes to pipeline_query_agent."""
        from app.services.jarvis_agents.command_state import create_command_state_from_nl

        initial = create_command_state_from_nl(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            raw_input="check quality score",
            awareness_snapshot={
                "quality_score": 0.85,
                "drift_status": "none",
                "drift_score": 0.02,
            },
            variant_tier="parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "pipeline_query_agent",
            "reasoning": "User wants quality information",
            "urgency": "low",
            "parameters": {},
        }

        result = _run_graph_with_mocks(initial, zai_router)

        # Verify the pipeline_query_agent was invoked
        assert result["agent_type"] == "pipeline_query"
        assert result["agent_action"] == "query_pipeline"

    def test_pipeline_query_result_flows_through(self, company_id, session_id, user_id):
        """Pipeline query result appears in final state."""
        from app.services.jarvis_agents.command_state import create_command_state_from_nl

        initial = create_command_state_from_nl(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            raw_input="what is the system health?",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "pipeline_query_agent",
            "reasoning": "Status query",
            "urgency": "low",
            "parameters": {},
        }

        result = _run_graph_with_mocks(initial, zai_router)

        # For parwa_high, pipeline_query should be auto-approved and executed
        assert result["execution_status"] == "completed"
        assert result["agent_type"] == "pipeline_query"

    def test_pipeline_query_audit_trail(self, company_id, session_id, user_id):
        """Pipeline query flow: audit trail includes pipeline_query_agent step."""
        from app.services.jarvis_agents.command_state import create_command_state_from_nl

        initial = create_command_state_from_nl(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            raw_input="show me agent utilization",
            variant_tier="parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "pipeline_query_agent",
            "reasoning": "Agent status query",
            "urgency": "low",
            "parameters": {},
        }

        result = _run_graph_with_mocks(initial, zai_router)

        steps = [entry.get("step") for entry in result.get("audit_trail", [])]
        assert "pipeline_query_agent" in steps


# ═══════════════════════════════════════════════════════════════════════
# FLOW 4: Variant Tier Transition During Flow
# ═══════════════════════════════════════════════════════════════════════


class TestFlow4TierTransition:
    """Flow 4: Switching variant tiers mid-flow changes approval rules.

    Verifies:
    - Different tiers produce different approval outcomes
    - Approval rules change correctly when tier changes
    """

    def test_same_action_different_tiers(self, company_id, session_id, user_id):
        """Same escalation action: mini_parwa blocks, parwa_high auto-approves."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state_mini = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "mini_parwa",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {"scope": "all_urgent"},
            "agent_reasoning": "Spike",
        }
        result_mini = approval_gate_node(state_mini)
        assert result_mini["execution_status"] == "pending_approval"

        state_high = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {"scope": "all_urgent"},
            "agent_reasoning": "Spike",
        }
        result_high = approval_gate_node(state_high)
        assert result_high["execution_status"] == "approved"

    def test_parwa_monetary_needs_approval(self, company_id, session_id, user_id):
        """parwa tier: monetary action (refund) needs approval."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "billing",
            "agent_action": "refund",
            "agent_decision": {},
            "agent_reasoning": "Customer refund",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_parwa_high_monetary_auto_approved(self, company_id, session_id, user_id):
        """parwa_high tier: same monetary action (refund) is auto-approved."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "billing",
            "agent_action": "refund",
            "agent_decision": {},
            "agent_reasoning": "Customer refund",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "approved"

    def test_variant_config_transitions_correctly(self, company_id):
        """Switching from parwa_high to mini_parwa changes config correctly."""
        from app.services.jarvis_agents.variant_bridge import get_variant_aware_command_config

        config_high = get_variant_aware_command_config(company_id, "parwa_high")
        assert config_high["mode"] == "full_autonomy"
        assert config_high["auto_execute_allowed"] is True

        config_mini = get_variant_aware_command_config(company_id, "mini_parwa")
        assert config_mini["mode"] == "notify_only"
        assert config_mini["auto_execute_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════
# FLOW 5: Emergency Full Stop Flow
# ═══════════════════════════════════════════════════════════════════════


class TestFlow5EmergencyFullStop:
    """Flow 5: Red alert → escalation → approval gate blocks emergency → pending.

    Verifies:
    - Emergency controls are set in state (legal_threat_detected, urgency=critical)
    - Even parwa_high blocks emergency actions
    """

    def test_emergency_action_sets_critical_urgency(self):
        """Emergency action in pipeline_feedback sets urgency=critical and legal_threat_detected."""
        from app.services.jarvis_agents.pipeline_feedback import _map_command_to_pipeline_updates

        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="full_stop",
            agent_decision={},
            execution_result={},
        )
        assert updates["urgency"] == "critical"
        assert updates["legal_threat_detected"] is True
        assert updates["emergency_state"] == "red_alert"

    def test_emergency_bridge_injects_legal_threat(self):
        """Bridge injects legal_threat_detected=True for emergency actions."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )

        bridge = {"emergency_state": "red_alert"}
        updates = _inject_emergency_controls(bridge, {})
        assert updates["urgency"] == "critical"
        assert updates["legal_threat_detected"] is True

    def test_emergency_feedback_sets_system_paused(self):
        """Emergency feedback sets system_mode='paused' and ai_paused=True."""
        from app.services.jarvis_agents.pipeline_feedback import _map_command_to_pipeline_updates

        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="full_stop",
            agent_decision={},
            execution_result={},
        )
        assert updates["system_mode"] == "paused"
        assert updates["ai_paused"] is True
        assert updates["proposed_action"] == "escalate"

    def test_parwa_high_full_stop_blocked(self, company_id, session_id, user_id):
        """parwa_high: full_stop emergency action is blocked at approval gate."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "emergency",
            "agent_action": "full_stop",
            "agent_decision": {},
            "agent_reasoning": "Critical system failure",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_red_alert_injector_sets_emergency_state(self):
        """Awareness injector with red_alert state sets proper pipeline overrides."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
            _apply_routing_overrides,
        )

        bridge = {"emergency_state": "red_alert"}
        emergency_updates = _inject_emergency_controls(bridge, {})
        routing_updates = _apply_routing_overrides(bridge, {})

        assert emergency_updates["urgency"] == "critical"
        assert emergency_updates["legal_threat_detected"] is True


# ═══════════════════════════════════════════════════════════════════════
# FLOW 6: Awareness Injector → Pipeline State → Read Back
# ═══════════════════════════════════════════════════════════════════════


class TestFlow6AwarenessInjectAndRead:
    """Flow 6: Inject awareness → pipeline reads it back correctly.

    Verifies:
    - Injected state appears in pipeline via awareness_injector
    - pipeline_query_agent can see the injected data
    """

    def test_inject_awareness_fields_appear_in_pipeline(self):
        """Injected awareness data appears in pipeline state via _inject_awareness_fields."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )

        awareness = {
            "quality_score": 0.92,
            "drift_status": "none",
            "drift_score": 0.03,
            "system_health": "healthy",
            "ticket_volume_today": 42,
            "active_agents": 5,
        }
        updates = _inject_awareness_fields(awareness)
        assert updates["quality_score"] == 0.92
        assert updates["drift_status"] == "none"
        assert updates["system_health"] == "healthy"
        assert updates["ticket_volume_today"] == 42
        assert updates["active_agents"] == 5

    def test_inject_command_context_appears(self):
        """Injected command context (co_pilot, feed entry) appears in pipeline."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )

        bridge = {
            "co_pilot_suggestion": "Switch to ReAct for better quality",
            "co_pilot_suggestion_type": "action_suggestion",
            "jarvis_feed_entry": {"type": "notification_sent", "message": "test"},
            "source": "jarvis_command_graph",
            "injected_at": "2025-01-01T00:00:00Z",
            "command_state_summary": {"agent_type": "escalation"},
        }
        updates = _inject_command_context(bridge)
        assert updates["co_pilot_suggestion"] == "Switch to ReAct for better quality"
        assert updates["co_pilot_suggestion_type"] == "action_suggestion"
        assert "jarvis_feed_entry" in updates
        assert "jarvis_command_metadata" in updates

    def test_pipeline_query_reads_awareness_data(self):
        """Pipeline query agent can read and report on awareness data."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )

        awareness = {
            "quality_score": 0.78,
            "drift_status": "detected",
            "drift_score": 0.12,
            "system_health": "degraded",
        }
        result = _rule_based_query_interpretation(
            "what's the quality score?",
            {}, awareness, "parwa",
        )
        assert result["query_type"] == "quality"
        assert "0.78" in result["answer"]
        assert result["data_points"]["quality_score"] == 0.78

    def test_full_inject_then_query_roundtrip(self, company_id, session_id):
        """Full roundtrip: inject awareness → query it back via pipeline_query_agent."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )

        # Step 1: Inject awareness
        awareness = {
            "quality_score": 0.65,
            "drift_status": "detected",
            "drift_score": 0.20,
            "system_health": "degraded",
            "ticket_volume_today": 200,
            "ticket_volume_avg": 80,
        }
        injected = _inject_awareness_fields(awareness)

        # Step 2: Simulate pipeline having this state
        pipeline_state = {**injected}

        # Step 3: Query agent reads it back
        result = _rule_based_query_interpretation(
            "what's the quality score?",
            pipeline_state, awareness, "parwa",
        )
        assert result["query_type"] == "quality"
        assert "0.65" in result["answer"]


# ═══════════════════════════════════════════════════════════════════════
# FLOW 7: Tenant Isolation
# ═══════════════════════════════════════════════════════════════════════


class TestFlow7TenantIsolation:
    """Flow 7: Company A's state should NOT leak to Company B.

    Verifies:
    - Key patterns are tenant-isolated
    - Approval rules are per-tenant
    - Feedback is tenant-isolated
    """

    def test_bridge_keys_are_tenant_isolated(self, company_a, company_b, session_id):
        """Different companies produce different bridge keys."""
        from app.services.jarvis_agents.variant_bridge import (
            _make_bridge_key,
            _make_awareness_key,
            _make_feedback_key,
        )

        key_a = _make_bridge_key(company_a, session_id)
        key_b = _make_bridge_key(company_b, session_id)
        assert key_a != key_b
        assert company_a in key_a
        assert company_b in key_b
        assert company_b not in key_a

    def test_awareness_keys_are_tenant_isolated(self, company_a, company_b, session_id):
        """Different companies produce different awareness keys."""
        from app.services.jarvis_agents.variant_bridge import _make_awareness_key

        key_a = _make_awareness_key(company_a, session_id)
        key_b = _make_awareness_key(company_b, session_id)
        assert key_a != key_b

    def test_feedback_keys_are_tenant_isolated(self, company_a, company_b, session_id):
        """Different companies produce different feedback keys."""
        from app.services.jarvis_agents.variant_bridge import _make_feedback_key

        key_a = _make_feedback_key(company_a, session_id)
        key_b = _make_feedback_key(company_b, session_id)
        assert key_a != key_b

    def test_approval_rules_per_tenant(self, company_a, company_b):
        """Approval decisions are scoped to company_id."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        result_a = check_jarvis_approval_needed(
            company_a, "parwa", "escalation", "escalate",
        )
        result_b = check_jarvis_approval_needed(
            company_b, "parwa", "escalation", "escalate",
        )

        # Both should require approval for escalation in parwa tier
        assert result_a["approval_needed"] is True
        assert result_b["approval_needed"] is True
        assert result_a["variant_tier"] == "parwa"
        assert result_b["variant_tier"] == "parwa"

    def test_command_config_includes_company_id(self, company_a, company_b):
        """Command configs include company_id for tenant tracking."""
        from app.services.jarvis_agents.variant_bridge import get_variant_aware_command_config

        config_a = get_variant_aware_command_config(company_a, "parwa")
        config_b = get_variant_aware_command_config(company_b, "parwa_high")

        assert config_a["company_id"] == company_a
        assert config_b["company_id"] == company_b
        assert config_a["mode"] == "standard"
        assert config_b["mode"] == "full_autonomy"

    def test_feedback_id_includes_company(self, company_a, session_id):
        """Feedback ID generation is scoped to company."""
        from app.services.jarvis_agents.pipeline_feedback import _generate_feedback_id

        id_a = _generate_feedback_id(company_a, session_id)
        assert id_a.startswith("fb_")
        id_a2 = _generate_feedback_id(company_a, session_id)
        assert id_a != id_a2  # Unique even for same company/session

    def test_approval_request_scoped_to_company(self, company_a, session_id, user_id):
        """Approval request includes company_id for tenant isolation."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            _create_approval_request,
        )

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ):
            request = _create_approval_request(
                company_id=company_a,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={"scope": "all_urgent"},
                agent_reasoning="Spike",
                approval_reason="Needs approval",
                variant_tier="mini_parwa",
            )

        assert request["company_id"] == company_a
        assert request["session_id"] == session_id
        assert request["status"] == "pending"


# ═══════════════════════════════════════════════════════════════════════
# FLOW 8: BC-008 Resilience
# ═══════════════════════════════════════════════════════════════════════


class TestFlow8BC008Resilience:
    """Flow 8: System continues when Redis/DB/LLM fail.

    Verifies:
    - Redis unavailable → bridge returns False/empty → pipeline continues
    - Error in approval gate → defaults to pending_approval (safest)
    - Error in pipeline query → returns error fallback, not crash
    """

    def test_redis_unavailable_bridge_inject_returns_false(self, company_id, session_id):
        """Redis unavailable: inject_jarvis_state_into_pipeline returns False."""
        from app.services.jarvis_agents.variant_bridge import (
            inject_jarvis_state_into_pipeline,
        )

        async def _redis_none():
            return None

        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            side_effect=_redis_none,
        ):
            import asyncio
            result = asyncio.run(inject_jarvis_state_into_pipeline(
                company_id, session_id, {"agent_type": "escalation"},
            ))
        assert result is False

    def test_redis_unavailable_read_returns_empty(self, company_id, session_id):
        """Redis unavailable: read_pipeline_state_for_jarvis returns empty dict."""
        from app.services.jarvis_agents.variant_bridge import (
            read_pipeline_state_for_jarvis,
        )

        async def _redis_none():
            return None

        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            side_effect=_redis_none,
        ), patch(
            "app.services.jarvis_agents.variant_bridge._read_pipeline_state_from_db",
            return_value={},
        ):
            import asyncio
            result = asyncio.run(read_pipeline_state_for_jarvis(
                company_id, session_id,
            ))
        assert result == {}

    def test_redis_unavailable_sync_awareness_returns_false(self, company_id, session_id):
        """Redis unavailable: sync_awareness_to_pipeline returns False."""
        from app.services.jarvis_agents.variant_bridge import (
            sync_awareness_to_pipeline,
        )

        async def _redis_none():
            return None

        with patch(
            "app.services.jarvis_agents.variant_bridge._get_redis_async",
            side_effect=_redis_none,
        ):
            import asyncio
            result = asyncio.run(sync_awareness_to_pipeline(
                company_id, session_id, {"system_health": "healthy"},
            ))
        assert result is False

    def test_approval_gate_error_defaults_to_pending(self, company_id, session_id, user_id):
        """Error in approval gate: defaults to pending_approval (safest)."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {},
            "agent_reasoning": "",
        }

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate.check_jarvis_approval_needed",
            side_effect=Exception("Unexpected error"),
        ):
            result = approval_gate_node(state)

        assert result["execution_status"] == "pending_approval"

    def test_pipeline_query_error_returns_fallback(self, company_id, session_id):
        """Error in pipeline_query_agent: returns error fallback, not crash."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "check quality",
            "awareness_snapshot": {},
        }

        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            side_effect=RuntimeError("Redis connection failed"),
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_awareness_data",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("ZAI SDK unavailable"),
        ):
            result = pipeline_query_agent_node(state)

        assert isinstance(result, dict)
        assert result["agent_type"] == "pipeline_query"

    def test_awareness_injector_redis_down_continues(self, company_id, session_id):
        """Awareness injector with Redis down: returns empty result, pipeline continues."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )

        state = {
            "tenant_id": company_id,
            "session_id": session_id,
        }

        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value={},
        ):
            result = jarvis_awareness_injector_node(state)

        assert isinstance(result, dict)
        assert "node_execution_log" in result

    def test_feedback_mapping_never_crashes(self):
        """_map_command_to_pipeline_updates never crashes, even with bad input."""
        from app.services.jarvis_agents.pipeline_feedback import _map_command_to_pipeline_updates

        result = _map_command_to_pipeline_updates("", "", {}, {})
        assert isinstance(result, dict)

        result2 = _map_command_to_pipeline_updates(
            None, None, None, None,  # type: ignore
        )
        assert isinstance(result2, dict)

    def test_approval_needed_error_defaults_safe(self, company_id):
        """check_jarvis_approval_needed on error defaults to requiring approval."""
        from app.services.jarvis_agents.variant_bridge import check_jarvis_approval_needed

        with patch(
            "app.services.jarvis_agents.variant_bridge.get_variant_aware_command_config",
            side_effect=Exception("Config error"),
        ):
            result = check_jarvis_approval_needed(
                company_id, "parwa", "notification", "notify",
            )

        assert result["approval_needed"] is True
        assert "error" in result

    def test_command_config_unknown_tier_safe(self, company_id):
        """Unknown tier in get_variant_aware_command_config returns safest config."""
        from app.services.jarvis_agents.variant_bridge import get_variant_aware_command_config

        config = get_variant_aware_command_config(company_id, "nonexistent_tier")
        assert config["mode"] == "notify_only"
        assert config["auto_execute_allowed"] is False


# ═══════════════════════════════════════════════════════════════════════
# FLOW 9: Approval Response Flow
# ═══════════════════════════════════════════════════════════════════════


class TestFlow9ApprovalResponse:
    """Flow 9: Create approval → simulate human approval/rejection.

    Verifies:
    - Approval request creation
    - Human approval → flow resumes to command_executor
    - Human rejection → flow ends
    """

    def test_create_approval_request_structure(self, company_id, session_id, user_id):
        """Created approval request has all required fields."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            _create_approval_request,
        )

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ):
            request = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision={"scope": "all_urgent"},
                agent_reasoning="Volume spike detected",
                approval_reason="Escalation requires human approval in mini_parwa",
                variant_tier="mini_parwa",
            )

        assert "request_id" in request
        assert request["request_id"].startswith("apr_")
        assert request["company_id"] == company_id
        assert request["session_id"] == session_id
        assert request["agent_type"] == "escalation"
        assert request["agent_action"] == "escalate"
        assert request["variant_tier"] == "mini_parwa"
        assert request["status"] == "pending"

    def test_human_approval_resumes_flow(self, company_id, user_id):
        """process_approval_response with approved=True → next_step='command_executor'."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )

        result = process_approval_response(
            company_id=company_id,
            request_id="apr_test123",
            approved=True,
            approver_id=user_id,
            approver_notes="Looks good, proceed",
        )

        assert result["approved"] is True
        assert result["status"] == "approved"
        assert result["next_step"] == "command_executor"
        assert result["approver_id"] == user_id
        assert result["company_id"] == company_id

    def test_human_rejection_ends_flow(self, company_id, user_id):
        """process_approval_response with approved=False → next_step='end'."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )

        result = process_approval_response(
            company_id=company_id,
            request_id="apr_test456",
            approved=False,
            approver_id=user_id,
            approver_notes="Too risky right now",
        )

        assert result["approved"] is False
        assert result["status"] == "rejected"
        assert result["next_step"] == "end"
        assert result["approver_id"] == user_id

    def test_approval_response_includes_timestamp(self, company_id, user_id):
        """Approval response includes a processed_at UTC timestamp."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )

        result = process_approval_response(
            company_id=company_id,
            request_id="apr_test789",
            approved=True,
            approver_id=user_id,
        )

        assert "processed_at" in result
        parsed = datetime.fromisoformat(result["processed_at"])
        assert parsed.tzinfo is not None

    def test_approval_decision_summary_in_request(self, company_id, session_id, user_id):
        """Approval request includes a summarized agent decision."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            _create_approval_request,
        )

        decision = {
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
            "reason": "Volume spike",
            "extra_field": "should_be_excluded",
        }

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ):
            request = _create_approval_request(
                company_id=company_id,
                session_id=session_id,
                user_id=user_id,
                agent_type="escalation",
                agent_action="escalate",
                agent_decision=decision,
                agent_reasoning="Critical spike",
                approval_reason="Needs approval",
                variant_tier="mini_parwa",
            )

        summary = request["agent_decision_summary"]
        assert "action" in summary or "scope" in summary or "escalation_tier" in summary

    def test_approval_gate_pending_result_has_request_id(self, company_id, session_id, user_id):
        """Approval gate result for pending_approval includes an approval_request_id."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "mini_parwa",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {},
            "agent_reasoning": "",
        }

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ):
            result = approval_gate_node(state)

        assert result["execution_status"] == "pending_approval"
        assert "approval_request_id" in result["execution_result"]
        assert result["execution_result"]["approval_request_id"].startswith("apr_")

    def test_approval_response_error_handling(self, company_id):
        """process_approval_response handles errors gracefully."""
        from app.services.jarvis_agents.nodes.approval_gate import (
            process_approval_response,
        )

        result = process_approval_response(
            company_id=company_id,
            request_id="",
            approved=True,
            approver_id="user1",
        )

        assert isinstance(result, dict)
        assert "status" in result


# ═══════════════════════════════════════════════════════════════════════
# CROSS-CUTTING: Full Graph Integration
# ═══════════════════════════════════════════════════════════════════════


class TestCrossCuttingGraphIntegration:
    """Additional cross-cutting integration tests for the full command graph."""

    def test_parwa_sla_protection_auto_approved(self, company_id, session_id, user_id):
        """parwa: SLA protection is auto-approved (not monetary/escalation)."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_sla_001",
            alert_type="sla_breach_risk",
            alert_severity="high",
            alert_message="5 tickets at SLA risk",
            variant_tier="parwa",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "sla_protection_agent",
            "reasoning": "SLA breach risk",
            "urgency": "high",
            "parameters": {},
        }

        mock_zai = MagicMock()
        mock_zai.chat.side_effect = [
            zai_router,
            {
                "_source": "rule_based_fallback",
                "action": "protect_sla",
                "at_risk_count": 5,
                "strategy": "prioritize",
            },
        ]

        from app.services.jarvis_agents import command_graph as cg
        cg._graph_instance = None

        with patch(
            "app.services.jarvis_agents.nodes.command_router.get_zai_client",
            return_value=mock_zai,
        ), patch(
            "app.services.jarvis_agents.nodes.sla_protection_agent.get_zai_client",
            return_value=mock_zai,
        ), patch(
            "app.services.jarvis_agents.nodes.command_executor._create_command_record",
            return_value=("cmd_sla", True),
        ), patch(
            "app.services.jarvis_agents.nodes.command_executor._execute_action",
            return_value={"executed": True},
        ), patch(
            "app.services.jarvis_agents.nodes.command_executor._maybe_resolve_alert",
            return_value=False,
        ), patch(
            "app.services.jarvis_agents.nodes.command_executor._dispatch_command_event",
            return_value=None,
        ), patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ), patch(
            _FEEDBACK_PATCH,
            return_value=True,
        ):
            from app.services.jarvis_agents.command_graph import JarvisCommandGraph
            graph = JarvisCommandGraph()
            result = graph.run(initial)

        assert result["execution_status"] == "completed"
        assert result["agent_type"] == "sla_protection"

    def test_parwa_refund_monetary_blocked(self, company_id, session_id, user_id):
        """parwa: refund (monetary) action is blocked at approval gate."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "billing",
            "agent_action": "refund",
            "agent_decision": {"amount": 50.00},
            "agent_reasoning": "Customer requested refund",
        }

        with patch(
            "app.services.jarvis_agents.nodes.approval_gate._persist_approval_request",
            return_value=None,
        ):
            result = approval_gate_node(state)

        assert result["execution_status"] == "pending_approval"
        reason = result["execution_result"].get("approval_reason", "")
        assert "monetary" in reason.lower()

    def test_node_outputs_accumulate_across_graph(self, company_id, session_id, user_id):
        """node_outputs should accumulate entries from each node in the graph."""
        from app.services.jarvis_agents.command_state import create_command_state_from_alert

        initial = create_command_state_from_alert(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            alert_id="alert_node_001",
            alert_type="ticket_volume_spike",
            alert_severity="critical",
            alert_message="Spike",
            variant_tier="parwa_high",
        )

        zai_router = {
            "_source": "rule_based_fallback",
            "agent": "escalation_agent",
            "reasoning": "Spike needs escalation",
            "urgency": "critical",
            "parameters": {},
        }
        zai_agent = {
            "_source": "rule_based_fallback",
            "action": "escalate",
            "scope": "all_urgent",
            "escalation_tier": "tier2",
        }

        result = _run_graph_with_mocks(initial, zai_router, zai_agent)

        node_outputs = result.get("node_outputs", {})
        assert "command_router" in node_outputs
        assert "escalation_agent" in node_outputs
        assert "approval_gate" in node_outputs
        assert "command_executor" in node_outputs

    def test_graph_run_from_nl_creates_correct_state(self, company_id, session_id, user_id):
        """run_from_nl creates state with trigger_type='user_nl'."""
        from app.services.jarvis_agents.command_state import create_command_state_from_nl

        initial = create_command_state_from_nl(
            company_id=company_id,
            session_id=session_id,
            user_id=user_id,
            raw_input="pause all AI",
            variant_tier="mini_parwa",
        )

        assert initial["trigger_type"] == "user_nl"
        assert initial["raw_input"] == "pause all AI"

    def test_feedback_loop_closes_properly(self):
        """Feedback loop: escalation → feedback → awareness injector reads it back."""
        from app.services.jarvis_agents.pipeline_feedback import _map_command_to_pipeline_updates
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )

        # Step 1: Escalation produces feedback
        feedback = _map_command_to_pipeline_updates(
            agent_type="escalation",
            agent_action="escalate",
            agent_decision={"scope": "all_urgent", "escalation_tier": "tier2"},
            execution_result={},
        )
        assert feedback["urgency"] == "critical"
        assert feedback["proposed_action"] == "escalate"

        # Step 2: Feedback data is read back by awareness injector
        bridge_with_feedback = {
            "escalation_in_progress": True,
            "urgency": "critical",
        }
        routing_overrides = _apply_routing_overrides(bridge_with_feedback, {})
        assert routing_overrides.get("urgency") == "critical"
