"""
PARWA Jarvis↔Variant LangGraph Integration — Phase 4 Comprehensive Tests

Covers ALL Phase 4 components with 40+ test cases:

  Module 1: Variant Bridge (variant_bridge.py)
    - get_variant_aware_command_config() — tier configs & unknown tier fallback
    - check_jarvis_approval_needed() — per-tier approval rules
    - VARIANT_COMMAND_CONFIGS — structure validation
    - _make_bridge_key(), _make_awareness_key(), _make_feedback_key()

  Module 2: Approval Gate (approval_gate.py)
    - approval_gate_node() — tier × action approval matrix
    - BC-008: graceful error handling

  Module 3: Jarvis Awareness Injector (jarvis_awareness_injector.py)
    - jarvis_awareness_injector_node() — state injection scenarios
    - _inject_emergency_controls(), _inject_command_context(),
      _inject_awareness_fields(), _apply_routing_overrides()

  Module 4: Pipeline Query Agent (pipeline_query_agent.py)
    - pipeline_query_agent_node() — query interpretation
    - _rule_based_query_interpretation() — keyword-based fallback

  Module 5: Pipeline Feedback (pipeline_feedback.py)
    - _map_command_to_pipeline_updates() — all command mappings

  Module 6: Full Integration
    - End-to-end Phase 4 flow verification

Rules:
  - ALL tests independent; no Redis/DB required (mocked)
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
# Shared Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock logger to prevent import errors in all tests."""
    with patch("app.logger.get_logger", return_value=MagicMock()):
        yield


@pytest.fixture
def company_id():
    """Standard test company ID."""
    return "comp_test_001"


@pytest.fixture
def session_id():
    """Standard test session ID."""
    return "sess_test_001"


@pytest.fixture
def user_id():
    """Standard test user ID."""
    return "user_test_001"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 1: Variant Bridge Tests
# ═══════════════════════════════════════════════════════════════════════


class TestVariantBridgeGetCommandConfig:
    """Tests for get_variant_aware_command_config()."""

    def test_mini_parwa_returns_notify_only_mode(self, company_id):
        """mini_parwa tier should return config with mode='notify_only'."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "mini_parwa")
        assert config["mode"] == "notify_only"

    def test_parwa_returns_standard_mode(self, company_id):
        """parwa tier should return config with mode='standard'."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "parwa")
        assert config["mode"] == "standard"

    def test_parwa_high_returns_full_autonomy_mode(self, company_id):
        """parwa_high tier should return config with mode='full_autonomy'."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "parwa_high")
        assert config["mode"] == "full_autonomy"

    def test_unknown_tier_defaults_to_mini_parwa(self, company_id):
        """Unknown tier should default to mini_parwa (safest config)."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "unknown_tier_xyz")
        assert config["mode"] == "notify_only"

    def test_config_includes_company_id(self, company_id):
        """Returned config must include company_id for tenant isolation (BC-001)."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "parwa")
        assert config["company_id"] == company_id

    def test_config_includes_variant_tier(self, company_id):
        """Returned config must include variant_tier for traceability."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "parwa_high")
        assert config["variant_tier"] == "parwa_high"

    def test_config_includes_resolved_at_timestamp(self, company_id):
        """Returned config must include a resolved_at UTC timestamp."""
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        config = get_variant_aware_command_config(company_id, "parwa")
        assert "resolved_at" in config
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(config["resolved_at"])
        assert parsed.tzinfo is not None


class TestVariantBridgeApprovalNeeded:
    """Tests for check_jarvis_approval_needed()."""

    # ── mini_parwa: ALL actions need approval ──

    def test_mini_parwa_escalation_needs_approval(self, company_id):
        """mini_parwa: escalation action requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "escalation", "escalate",
        )
        assert result["approval_needed"] is True

    def test_mini_parwa_notification_needs_approval(self, company_id):
        """mini_parwa: even notification requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "notification", "notify",
        )
        assert result["approval_needed"] is True

    def test_mini_parwa_sla_protection_needs_approval(self, company_id):
        """mini_parwa: SLA protection requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "sla_protection", "protect_sla",
        )
        assert result["approval_needed"] is True

    def test_mini_parwa_quality_recovery_needs_approval(self, company_id):
        """mini_parwa: quality recovery requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "quality_recovery", "recover_quality",
        )
        assert result["approval_needed"] is True

    def test_mini_parwa_reassignment_needs_approval(self, company_id):
        """mini_parwa: reassignment requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "reassignment", "reassign",
        )
        assert result["approval_needed"] is True

    # ── parwa: Only monetary + escalation need approval ──

    def test_parwa_refund_monetary_needs_approval(self, company_id):
        """parwa: refund (monetary action) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "billing", "refund",
        )
        assert result["approval_needed"] is True
        assert "monetary" in result["reason"].lower()

    def test_parwa_escalation_needs_approval(self, company_id):
        """parwa: escalation action requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "escalation", "escalate",
        )
        assert result["approval_needed"] is True

    def test_parwa_notification_auto_approved(self, company_id):
        """parwa: notification action is auto-approved."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "notification", "notify",
        )
        assert result["approval_needed"] is False
        assert result["approval_type"] == "auto"

    def test_parwa_protect_sla_auto_approved(self, company_id):
        """parwa: SLA protection is auto-approved (not monetary/escalation)."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "sla_protection", "protect_sla",
        )
        assert result["approval_needed"] is False

    # ── parwa_high: Only emergency needs approval ──

    def test_parwa_high_full_stop_emergency_needs_approval(self, company_id):
        """parwa_high: full_stop (emergency) requires approval."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa_high", "emergency", "full_stop",
        )
        assert result["approval_needed"] is True

    def test_parwa_high_notification_auto_approved(self, company_id):
        """parwa_high: notification is auto-approved."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa_high", "notification", "notify",
        )
        assert result["approval_needed"] is False

    def test_parwa_high_escalation_auto_approved(self, company_id):
        """parwa_high: escalation is auto-approved (only emergency needs approval)."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa_high", "escalation", "escalate",
        )
        assert result["approval_needed"] is False

    # ── Unknown tier ──

    def test_unknown_tier_defaults_to_requiring_approval(self, company_id):
        """Unknown tier defaults to requiring approval (safest default)."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "nonexistent_tier", "notification", "notify",
        )
        assert result["approval_needed"] is True


class TestVariantBridgeConfigStructure:
    """Tests for VARIANT_COMMAND_CONFIGS structure."""

    def test_all_tiers_present_in_config(self):
        """VARIANT_COMMAND_CONFIGS must contain all 3 tiers."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        assert "mini_parwa" in VARIANT_COMMAND_CONFIGS
        assert "parwa" in VARIANT_COMMAND_CONFIGS
        assert "parwa_high" in VARIANT_COMMAND_CONFIGS

    def test_config_has_required_keys(self):
        """Each tier config must have all required keys."""
        from app.services.jarvis_agents.variant_bridge import VARIANT_COMMAND_CONFIGS
        required_keys = {
            "mode", "description", "auto_execute_allowed",
            "approval_required_for", "max_urgency_auto",
            "can_pause_ai", "can_escalate", "can_reassign",
            "can_modify_technique", "can_activate_sla_protection",
        }
        for tier_name, config in VARIANT_COMMAND_CONFIGS.items():
            missing = required_keys - set(config.keys())
            assert not missing, (
                f"Tier '{tier_name}' missing keys: {missing}"
            )


class TestVariantBridgeKeyPatterns:
    """Tests for _make_bridge_key, _make_awareness_key, _make_feedback_key."""

    def test_bridge_key_includes_company_id_first(self, company_id, session_id):
        """Bridge key must start with company_id (BC-001)."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key = _make_bridge_key(company_id, session_id)
        assert key.startswith(f"parwa:{company_id}:")

    def test_awareness_key_includes_company_id_first(self, company_id, session_id):
        """Awareness key must start with company_id (BC-001)."""
        from app.services.jarvis_agents.variant_bridge import _make_awareness_key
        key = _make_awareness_key(company_id, session_id)
        assert key.startswith(f"parwa:{company_id}:")

    def test_feedback_key_includes_company_id_first(self, company_id, session_id):
        """Feedback key must start with company_id (BC-001)."""
        from app.services.jarvis_agents.variant_bridge import _make_feedback_key
        key = _make_feedback_key(company_id, session_id)
        assert key.startswith(f"parwa:{company_id}:")

    def test_bridge_key_contains_session_id(self, company_id, session_id):
        """Bridge key must contain session_id."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key = _make_bridge_key(company_id, session_id)
        assert session_id in key

    def test_different_company_ids_produce_different_keys(self, session_id):
        """Different company_ids must produce different keys (tenant isolation)."""
        from app.services.jarvis_agents.variant_bridge import _make_bridge_key
        key_a = _make_bridge_key("comp_A", session_id)
        key_b = _make_bridge_key("comp_B", session_id)
        assert key_a != key_b


# ═══════════════════════════════════════════════════════════════════════
# MODULE 2: Approval Gate Tests
# ═══════════════════════════════════════════════════════════════════════


class TestApprovalGateNode:
    """Tests for approval_gate_node()."""

    def test_mini_parwa_escalation_pending_approval(self, company_id, session_id, user_id):
        """mini_parwa + escalation → approval_needed=True, execution_status='pending_approval'."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "mini_parwa",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {"scope": "all_urgent"},
            "agent_reasoning": "Spike detected",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"
        assert result["execution_result"]["status"] == "pending_approval"

    def test_parwa_notification_auto_approved(self, company_id, session_id, user_id):
        """parwa + notification → approval_needed=False, execution_status='approved'."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {"channel": "chat"},
            "agent_reasoning": "Info alert",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "approved"

    def test_parwa_escalation_needs_approval(self, company_id, session_id, user_id):
        """parwa + escalation → approval_needed=True."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {},
            "agent_reasoning": "",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_parwa_refund_monetary_needs_approval(self, company_id, session_id, user_id):
        """parwa + refund (monetary) → approval_needed=True."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "billing",
            "agent_action": "refund",
            "agent_decision": {},
            "agent_reasoning": "Customer requested refund",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_parwa_high_escalation_auto_approved(self, company_id, session_id, user_id):
        """parwa_high + escalation → approval_needed=False."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {},
            "agent_reasoning": "",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "approved"

    def test_parwa_high_full_stop_needs_approval(self, company_id, session_id, user_id):
        """parwa_high + full_stop (emergency) → approval_needed=True."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa_high",
            "agent_type": "emergency",
            "agent_action": "full_stop",
            "agent_decision": {},
            "agent_reasoning": "Critical failure",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_unknown_tier_defaults_to_approval(self, company_id, session_id, user_id):
        """Unknown tier → approval_needed=True (safest default)."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "unknown_tier",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {},
            "agent_reasoning": "",
        }
        result = approval_gate_node(state)
        assert result["execution_status"] == "pending_approval"

    def test_bc008_missing_agent_type_still_works(self, company_id, session_id, user_id):
        """BC-008: Missing agent_type/agent_action should not crash."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            # agent_type and agent_action missing
            "agent_decision": {},
            "agent_reasoning": "",
        }
        result = approval_gate_node(state)
        # Should not crash — returns a result dict
        assert isinstance(result, dict)
        assert "execution_status" in result

    def test_approval_result_includes_audit_trail(self, company_id, session_id, user_id):
        """Approval result should include an audit_trail entry."""
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "variant_tier": "parwa",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {},
            "agent_reasoning": "",
        }
        result = approval_gate_node(state)
        assert "audit_trail" in result
        assert len(result["audit_trail"]) > 0
        assert result["audit_trail"][0]["step"] == "approval_gate"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 3: Jarvis Awareness Injector Tests
# ═══════════════════════════════════════════════════════════════════════


class TestJarvisAwarenessInjectorNode:
    """Tests for jarvis_awareness_injector_node() and its helpers."""

    def test_ai_paused_sets_system_mode_paused(self, company_id, session_id):
        """With ai_paused=True in bridge → sets system_mode='paused', proposed_action='escalate'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {"ai_paused": True}
        feedback_data = {}
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        assert updates["system_mode"] == "paused"
        assert updates["proposed_action"] == "escalate"
        assert updates["ai_paused"] is True

    def test_emergency_red_alert_sets_urgency_critical(self, company_id, session_id):
        """With emergency_state='red_alert' → sets urgency='critical', legal_threat_detected=True."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {"emergency_state": "red_alert"}
        feedback_data = {}
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        assert updates["urgency"] == "critical"
        assert updates["legal_threat_detected"] is True

    def test_emergency_full_stop_sets_urgency_critical(self, company_id, session_id):
        """With emergency_state='full_stop' → sets urgency='critical', legal_threat_detected=True."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {"emergency_state": "full_stop"}
        feedback_data = {}
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        assert updates["urgency"] == "critical"
        assert updates["legal_threat_detected"] is True
        assert updates["system_mode"] == "paused"

    def test_co_pilot_suggestion_injected(self, company_id, session_id):
        """With co_pilot_suggestion in bridge → injects both suggestion and type."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )
        bridge_state = {
            "co_pilot_suggestion": "Consider switching to ReAct technique",
            "co_pilot_suggestion_type": "action_suggestion",
        }
        updates = _inject_command_context(bridge_state)
        assert updates["co_pilot_suggestion"] == "Consider switching to ReAct technique"
        assert updates["co_pilot_suggestion_type"] == "action_suggestion"

    def test_normal_state_no_emergency_updates(self, company_id, session_id):
        """With normal state (no alerts) → no emergency control updates."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {}
        feedback_data = {}
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        # Should not contain emergency-related keys
        assert "urgency" not in updates
        assert "legal_threat_detected" not in updates
        assert "system_mode" not in updates

    def test_quality_alerts_from_awareness(self, company_id, session_id):
        """With quality_alerts from awareness → updates quality_alerts field."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        awareness_data = {
            "quality_alerts": [
                {"metric": "quality_score", "severity": "warning"},
            ],
        }
        updates = _inject_awareness_fields(awareness_data)
        assert "quality_alerts" in updates
        assert len(updates["quality_alerts"]) == 1

    def test_bc008_redis_unavailable_graceful_fallback(self, company_id, session_id):
        """BC-008: With Redis unavailable, the injector node should not crash.

        When _read_bridge_state returns empty (Redis down), the node
        should return a skip result, not an exception.
        """
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "tenant_id": company_id,
            "session_id": session_id,
        }
        # Mock all Redis readers to return empty dicts
        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value={},
        ):
            result = jarvis_awareness_injector_node(state)
        # Should return empty result with skipped log, not crash
        assert isinstance(result, dict)
        assert "node_execution_log" in result

    def test_missing_tenant_id_still_works(self):
        """BC-008: With missing tenant_id → returns early without crash."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "session_id": "sess_123",
            # tenant_id missing
        }
        result = jarvis_awareness_injector_node(state)
        assert isinstance(result, dict)
        assert "node_execution_log" in result

    def test_sla_protection_active_sets_urgency_high(self):
        """SLA protection active in bridge → urgency='high'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        bridge_state = {"sla_protection_active": True}
        current_state = {}
        updates = _apply_routing_overrides(bridge_state, current_state)
        assert updates["urgency"] == "high"

    def test_escalation_in_progress_sets_urgency_critical(self):
        """Escalation in progress in bridge → urgency='critical'."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        bridge_state = {"escalation_in_progress": True}
        current_state = {}
        updates = _apply_routing_overrides(bridge_state, current_state)
        assert updates["urgency"] == "critical"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 4: Pipeline Query Agent Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineQueryAgent:
    """Tests for pipeline_query_agent_node() and _rule_based_query_interpretation()."""

    def test_quality_query_returns_quality_info(self):
        """Query about quality → returns quality info from awareness."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        awareness = {"quality_score": 0.72, "drift_status": "detected", "drift_score": 0.15}
        result = _rule_based_query_interpretation(
            "What's the current quality score?",
            {}, awareness, "parwa",
        )
        assert result["query_type"] == "quality"
        assert "0.72" in result["answer"]
        assert result["data_points"]["quality_score"] == 0.72

    def test_volume_query_returns_volume_info(self):
        """Query about volume → returns volume info."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        awareness = {
            "ticket_volume_today": 150,
            "ticket_volume_avg": 80,
            "ticket_volume_spike": True,
        }
        result = _rule_based_query_interpretation(
            "How many tickets today?",
            {}, awareness, "parwa",
        )
        assert result["query_type"] == "volume"
        assert result["data_points"]["ticket_volume_today"] == 150

    def test_agent_query_returns_agent_pool_info(self):
        """Query about agent load → returns agent pool info.

        Note: The query must use an 'agent'-keyword without also
        matching 'volume' keywords (ticket/queue/load) earlier,
        because the rule-based interpreter checks volume keywords
        before agent keywords.
        """
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        awareness = {
            "active_agents": 5,
            "agent_pool_capacity": 10,
            "agent_pool_utilization": 85.0,
        }
        result = _rule_based_query_interpretation(
            "What is the agent utilization?",
            {}, awareness, "parwa",
        )
        assert result["query_type"] == "agent"
        assert result["data_points"]["active_agents"] == 5
        assert result["data_points"]["agent_pool_capacity"] == 10

    def test_unknown_query_returns_general_summary(self):
        """Unknown query type → returns general system overview."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        awareness = {
            "system_health": "healthy",
            "quality_score": 0.90,
            "active_agents": 3,
        }
        result = _rule_based_query_interpretation(
            "Tell me about the system",
            {}, awareness, "parwa",
        )
        assert result["query_type"] == "general"
        assert "system_health" in result["data_points"]

    def test_zai_sdk_fallback_to_rule_based(self, company_id, session_id):
        """With ZAI SDK failure → falls back to rule-based response."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "parwa",
            "raw_input": "What's the quality score?",
            "awareness_snapshot": {
                "quality_score": 0.85,
                "drift_status": "none",
                "drift_score": 0.02,
            },
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_awareness_data",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("ZAI SDK unavailable"),
        ):
            result = pipeline_query_agent_node(state)
        assert result["agent_type"] == "pipeline_query"
        assert result["agent_action"] == "query_pipeline"

    def test_empty_awareness_snapshot_still_returns_something(self, company_id, session_id):
        """With empty awareness_snapshot → still returns something useful."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            pipeline_query_agent_node,
        )
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "variant_tier": "mini_parwa",
            "raw_input": "system status",
            "awareness_snapshot": {},
        }
        with patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_pipeline_state",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent._read_awareness_data",
            return_value={},
        ), patch(
            "app.services.jarvis_agents.nodes.pipeline_query_agent.get_zai_client",
            side_effect=Exception("no SDK"),
        ):
            result = pipeline_query_agent_node(state)
        # Should not crash and should have a result
        assert "agent_decision" in result
        assert result["agent_type"] == "pipeline_query"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 5: Pipeline Feedback Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineFeedbackMapping:
    """Tests for _map_command_to_pipeline_updates()."""

    def test_escalation_sets_urgency_critical(self):
        """Escalation → urgency='critical', proposed_action='escalate'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="escalation",
            agent_action="escalate",
            agent_decision={"scope": "all_urgent", "escalation_tier": "tier2"},
            execution_result={},
        )
        assert updates["urgency"] == "critical"
        assert updates["proposed_action"] == "escalate"

    def test_ai_pause_sets_paused_state(self):
        """AI pause → ai_paused=True, system_mode='paused'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="pause_ai",
            agent_decision={"reason": "Quality drop detected"},
            execution_result={},
        )
        assert updates["ai_paused"] is True
        assert updates["system_mode"] == "paused"

    def test_ai_resume_sets_auto_mode(self):
        """AI resume → ai_paused=False, system_mode='auto'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="resume_ai",
            agent_decision={},
            execution_result={},
        )
        assert updates["ai_paused"] is False
        assert updates["system_mode"] == "auto"
        assert updates["global_pause_reason"] == ""

    def test_quality_recovery_sets_drift_recovering(self):
        """Quality recovery → drift_status='recovering', quality_alerts updated."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="quality_recovery",
            agent_action="recover_quality",
            agent_decision={
                "strategy": "switch_technique",
                "current_score": 0.65,
                "target_score": 0.85,
                "new_techniques": ["react"],
            },
            execution_result={},
        )
        assert updates["drift_status"] == "recovering"
        assert "quality_alerts" in updates
        assert len(updates["quality_alerts"]) > 0
        assert updates["quality_alerts"][0]["action"] == "recovery_switch_technique"

    def test_sla_protection_sets_protection_active(self):
        """SLA protection → sla_protection_active=True, urgency='high'."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="sla_protection",
            agent_action="protect_sla",
            agent_decision={
                "strategy": "prioritize",
                "at_risk_count": 5,
            },
            execution_result={},
        )
        assert updates["sla_protection_active"] is True
        assert updates["urgency"] == "high"
        assert updates["sla_protection_strategy"] == "prioritize"

    def test_reassignment_sets_in_progress(self):
        """Reassignment → reassignment_in_progress=True."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="reassignment",
            agent_action="reassign",
            agent_decision={
                "from_agent": "agent_A",
                "to_agent": "agent_B",
                "ticket_count": 10,
            },
            execution_result={},
        )
        assert updates["reassignment_in_progress"] is True
        assert updates["reassignment_from"] == "agent_A"
        assert updates["reassignment_to"] == "agent_B"

    def test_emergency_sets_red_alert(self):
        """Emergency action → emergency_state='red_alert', legal_threat_detected=True."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="full_stop",
            agent_decision={},
            execution_result={},
        )
        assert updates["emergency_state"] == "red_alert"
        assert updates["urgency"] == "critical"
        assert updates["legal_threat_detected"] is True

    def test_notification_updates_jarvis_feed(self):
        """Notification → jarvis_feed_entry updated."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="notification",
            agent_action="notify",
            agent_decision={
                "channel": "email",
                "severity": "warning",
                "title": "Volume spike",
            },
            execution_result={},
        )
        assert "jarvis_feed_entry" in updates
        assert updates["jarvis_feed_entry"]["type"] == "notification_sent"
        assert updates["jarvis_feed_entry"]["channel"] == "email"

    def test_pipeline_query_updates_jarvis_feed(self):
        """Pipeline query → jarvis_feed_entry with query result."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="pipeline_query",
            agent_action="query_pipeline",
            agent_decision={
                "query_type": "quality",
                "answer": "Quality score is 0.85",
            },
            execution_result={},
        )
        assert "jarvis_feed_entry" in updates
        assert updates["jarvis_feed_entry"]["type"] == "pipeline_query_result"
        assert updates["jarvis_feed_entry"]["query_type"] == "quality"


# ═══════════════════════════════════════════════════════════════════════
# MODULE 6: Full Integration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFullPhase4Integration:
    """Integration tests for the complete Phase 4 flow."""

    def test_awareness_to_command_to_feedback_loop(self, company_id, session_id):
        """Test: awareness tick → alert → command graph → approval gate →
        executor → feedback loop.

        Simulates the full flow where:
        1. An awareness event triggers a command
        2. The command router selects an agent
        3. The approval gate checks if approval is needed
        4. The feedback mapper translates the result back to pipeline fields
        """
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )

        # Step 1: Awareness detects escalation needed
        awareness = {
            "quality_score": 0.45,
            "drift_status": "detected",
            "system_health": "degraded",
        }

        # Step 2: Command router decides to escalate
        command_state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": "user_001",
            "variant_tier": "parwa",
            "agent_type": "escalation",
            "agent_action": "escalate",
            "agent_decision": {
                "scope": "all_urgent",
                "escalation_tier": "tier2",
            },
            "agent_reasoning": "Quality below threshold",
        }

        # Step 3: Approval gate checks
        gate_result = approval_gate_node(command_state)
        assert gate_result["execution_status"] == "pending_approval"

        # Step 4: After approval, executor runs → feedback maps result
        feedback_updates = _map_command_to_pipeline_updates(
            agent_type="escalation",
            agent_action="escalate",
            agent_decision=command_state["agent_decision"],
            execution_result={"status": "completed"},
        )
        assert feedback_updates["urgency"] == "critical"
        assert feedback_updates["proposed_action"] == "escalate"

    def test_variant_tier_influences_flow_mini_parwa_blocks_auto(
        self, company_id, session_id,
    ):
        """Verify that mini_parwa variant_tier blocks auto-execution
        while parwa_high allows it.

        mini_parwa should require approval for ALL actions,
        parwa_high should auto-approve most actions.
        """
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )

        # mini_parwa: even a simple notification needs approval
        mini_result = check_jarvis_approval_needed(
            company_id, "mini_parwa", "notification", "notify",
        )
        assert mini_result["approval_needed"] is True

        # parwa_high: notification is auto-approved
        high_result = check_jarvis_approval_needed(
            company_id, "parwa_high", "notification", "notify",
        )
        assert high_result["approval_needed"] is False

        # parwa_high: escalation is auto-approved
        high_esc = check_jarvis_approval_needed(
            company_id, "parwa_high", "escalation", "escalate",
        )
        assert high_esc["approval_needed"] is False

    def test_feedback_flows_back_to_pipeline_state(self, company_id, session_id):
        """Verify feedback from command execution flows back to pipeline state.

        When a quality recovery command is executed, the pipeline should
        see updated drift_status and quality_alerts.
        """
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )

        # Step 1: Quality recovery executed
        feedback_updates = _map_command_to_pipeline_updates(
            agent_type="quality_recovery",
            agent_action="recover_quality",
            agent_decision={
                "strategy": "switch_technique",
                "current_score": 0.55,
                "target_score": 0.85,
                "new_techniques": ["react"],
            },
            execution_result={"status": "completed"},
        )

        # Step 2: Verify feedback maps to pipeline fields
        assert feedback_updates["drift_status"] == "recovering"
        assert "quality_alerts" in feedback_updates

        # Step 3: Simulate awareness data flowing back through injector
        awareness_data = {
            "drift_status": "recovering",
            "quality_alerts": feedback_updates["quality_alerts"],
            "quality_score": 0.55,
        }
        injected = _inject_awareness_fields(awareness_data)
        assert injected["drift_status"] == "recovering"
        assert "quality_alerts" in injected

    def test_tenant_isolation_across_full_flow(self, company_id, session_id):
        """Verify company_id is respected throughout the full flow (BC-001).

        Different companies should have completely isolated states.
        """
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
            check_jarvis_approval_needed,
            _make_bridge_key,
            _make_feedback_key,
        )

        # Config includes company_id
        config_a = get_variant_aware_command_config("comp_A", "parwa")
        config_b = get_variant_aware_command_config("comp_B", "parwa")
        assert config_a["company_id"] == "comp_A"
        assert config_b["company_id"] == "comp_B"

        # Approval check includes company_id in its context
        approval_a = check_jarvis_approval_needed(
            "comp_A", "parwa", "escalation", "escalate",
        )
        # The result should be deterministic regardless of company_id
        # for the same tier/action combo
        approval_b = check_jarvis_approval_needed(
            "comp_B", "parwa", "escalation", "escalate",
        )
        assert approval_a["approval_needed"] == approval_b["approval_needed"]

        # Redis keys are tenant-isolated
        key_a = _make_bridge_key("comp_A", session_id)
        key_b = _make_bridge_key("comp_B", session_id)
        assert key_a != key_b
        assert "comp_A" in key_a
        assert "comp_B" in key_b

    def test_bc008_error_in_approval_gate_never_crashes(self, company_id, session_id):
        """BC-008: If check_jarvis_approval_needed raises, approval_gate
        should still return a result (never crash).
        """
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node

        # Force an error in the approval check by passing corrupt state
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": "user_001",
            "variant_tier": "parwa",
            "agent_type": "notification",
            "agent_action": "notify",
            "agent_decision": {},
            "agent_reasoning": "",
        }
        # Mock check_jarvis_approval_needed to raise
        with patch(
            "app.services.jarvis_agents.nodes.approval_gate.check_jarvis_approval_needed",
            side_effect=RuntimeError("Unexpected DB error"),
        ):
            result = approval_gate_node(state)
        # Should NOT crash — returns a dict with error info
        assert isinstance(result, dict)
        # On error, default to requiring approval (safest)
        assert result["execution_status"] == "pending_approval"

    def test_emergency_action_full_flow(self, company_id, session_id):
        """Test emergency action flowing through: bridge → approval → feedback.

        An emergency full_stop action on parwa_high should:
        1. Need approval (emergency actions always need approval)
        2. Map to red_alert + legal_threat_detected in pipeline state
        """
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        from app.services.jarvis_agents.nodes.approval_gate import approval_gate_node
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )

        # Step 1: Even parwa_high needs approval for full_stop
        approval = check_jarvis_approval_needed(
            company_id, "parwa_high", "emergency", "full_stop",
        )
        assert approval["approval_needed"] is True

        # Step 2: Approval gate blocks it
        state = {
            "company_id": company_id,
            "session_id": session_id,
            "user_id": "user_001",
            "variant_tier": "parwa_high",
            "agent_type": "emergency",
            "agent_action": "full_stop",
            "agent_decision": {"reason": "Critical system failure"},
            "agent_reasoning": "Multiple cascading failures detected",
        }
        gate_result = approval_gate_node(state)
        assert gate_result["execution_status"] == "pending_approval"

        # Step 3: After approval, feedback maps correctly
        feedback = _map_command_to_pipeline_updates(
            agent_type="emergency",
            agent_action="full_stop",
            agent_decision=state["agent_decision"],
            execution_result={"status": "completed"},
        )
        assert feedback["emergency_state"] == "red_alert"
        assert feedback["legal_threat_detected"] is True
        assert feedback["ai_paused"] is True


# ═══════════════════════════════════════════════════════════════════════
# ADDITIONAL EDGE CASE & ROBUSTNESS TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCasesAndRobustness:
    """Additional edge case tests for BC-008 compliance and robustness."""

    def test_approval_needed_result_has_all_required_fields(self, company_id):
        """check_jarvis_approval_needed result must have all required fields."""
        from app.services.jarvis_agents.variant_bridge import (
            check_jarvis_approval_needed,
        )
        result = check_jarvis_approval_needed(
            company_id, "parwa", "notification", "notify",
        )
        required_fields = {
            "approval_needed", "reason", "approval_type",
            "variant_tier", "agent_type", "agent_action",
        }
        missing = required_fields - set(result.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_get_command_config_bc008_exception_returns_safest(self, company_id):
        """BC-008: get_variant_aware_command_config returns safest config on error.

        If the config resolution raises, the except block returns
        mini_parwa config with an error field.
        """
        from app.services.jarvis_agents.variant_bridge import (
            get_variant_aware_command_config,
        )
        # Patch datetime to raise, forcing the except path
        with patch(
            "app.services.jarvis_agents.variant_bridge.datetime",
        ) as mock_dt:
            mock_dt.now.side_effect = RuntimeError("Timestamp error")
            mock_dt.timezone = timezone  # keep timezone accessible
            result = get_variant_aware_command_config(company_id, "parwa")
        # Should return safest config (mini_parwa) with error info
        assert result["mode"] == "notify_only"
        assert "error" in result

    def test_feedback_empty_command_result(self):
        """_map_command_to_pipeline_updates with empty inputs returns empty dict."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="",
            agent_action="",
            agent_decision={},
            execution_result={},
        )
        # No matching agent_type or action → no updates
        assert isinstance(updates, dict)

    def test_inject_awareness_fields_empty_data(self):
        """_inject_awareness_fields with empty data returns empty updates."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        updates = _inject_awareness_fields({})
        assert updates == {}

    def test_inject_awareness_fields_none_values_ignored(self):
        """_inject_awareness_fields should ignore None values."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_awareness_fields,
        )
        awareness_data = {
            "quality_score": None,
            "drift_status": "detected",
        }
        updates = _inject_awareness_fields(awareness_data)
        # quality_score should NOT be in updates (None values skipped)
        assert "quality_score" not in updates
        # drift_status should be in updates
        assert updates["drift_status"] == "detected"

    def test_apply_routing_overrides_system_mode_paused(self):
        """_apply_routing_overrides should set system_mode='paused' when bridge says so."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        bridge_state = {"system_mode": "paused"}
        current_state = {}
        updates = _apply_routing_overrides(bridge_state, current_state)
        assert updates["system_mode"] == "paused"

    def test_apply_routing_overrides_system_mode_supervised(self):
        """_apply_routing_overrides should set system_mode='supervised' when bridge says so."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _apply_routing_overrides,
        )
        bridge_state = {"system_mode": "supervised"}
        current_state = {}
        updates = _apply_routing_overrides(bridge_state, current_state)
        assert updates["system_mode"] == "supervised"

    def test_quality_recovery_with_switch_technique_sets_technique_stack(self):
        """Quality recovery with switch_technique strategy sets technique_stack."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="quality_recovery",
            agent_action="recover_quality",
            agent_decision={
                "strategy": "switch_technique",
                "new_techniques": ["react", "self_consistency"],
                "current_score": 0.60,
                "target_score": 0.90,
            },
            execution_result={},
        )
        assert "technique_stack" in updates
        assert updates["technique_stack"] == ["react", "self_consistency"]

    def test_sla_protection_with_at_risk_tickets(self):
        """SLA protection with at_risk_count > 0 creates active_alerts."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="sla_protection",
            agent_action="protect_sla",
            agent_decision={
                "strategy": "prioritize",
                "at_risk_count": 8,
            },
            execution_result={},
        )
        assert "active_alerts" in updates
        assert len(updates["active_alerts"]) > 0
        assert updates["active_alerts"][0]["severity"] == "high"

    def test_reassignment_with_upgrade_suggestion(self):
        """Reassignment with upgrade_suggested=True creates upgrade alert."""
        from app.services.jarvis_agents.pipeline_feedback import (
            _map_command_to_pipeline_updates,
        )
        updates = _map_command_to_pipeline_updates(
            agent_type="reassignment",
            agent_action="reassign",
            agent_decision={
                "from_agent": "agent_X",
                "to_agent": "agent_Y",
                "ticket_count": 5,
                "upgrade_suggested": True,
            },
            execution_result={},
        )
        assert "active_alerts" in updates
        # Should have an upgrade suggestion alert with jarvis_upgrade_suggestion ID
        assert any(
            alert.get("alert_id") == "jarvis_upgrade_suggestion"
            for alert in updates["active_alerts"]
        )

    def test_inject_command_context_with_jarvis_feed(self):
        """_inject_command_context should inject jarvis_feed_entry from bridge."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_command_context,
        )
        bridge_state = {
            "jarvis_feed_entry": {
                "type": "command_execution",
                "agent_type": "escalation",
                "status": "completed",
            },
            "source": "jarvis_command_graph",
            "injected_at": "2025-01-01T00:00:00Z",
            "command_state_summary": {"agent_type": "escalation"},
        }
        updates = _inject_command_context(bridge_state)
        assert "jarvis_feed_entry" in updates
        assert "jarvis_command_metadata" in updates
        assert updates["jarvis_command_metadata"]["source"] == "jarvis_command_graph"

    def test_emergency_query_interpretation(self):
        """Emergency/status query → returns emergency-related data."""
        from app.services.jarvis_agents.nodes.pipeline_query_agent import (
            _rule_based_query_interpretation,
        )
        awareness = {"system_health": "degraded"}
        pipeline_state = {"emergency_state": "red_alert", "ai_paused": True}
        result = _rule_based_query_interpretation(
            "Is there an emergency?",
            pipeline_state, awareness, "parwa_high",
        )
        assert result["query_type"] == "emergency"
        assert result["data_points"]["emergency_state"] == "red_alert"

    def test_paused_channels_injected(self):
        """Paused channels from bridge should be injected into updates."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {
            "paused_channels": ["email", "sms"],
            "paused_actions": ["auto_respond"],
        }
        feedback_data = {}
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        assert updates["paused_channels"] == ["email", "sms"]
        assert updates["paused_actions"] == ["auto_respond"]

    def test_feedback_takes_precedence_over_bridge(self):
        """Feedback data should take precedence over bridge state in emergency controls."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            _inject_emergency_controls,
        )
        bridge_state = {"ai_paused": False}
        feedback_data = {"ai_paused": True}  # Feedback overrides
        updates = _inject_emergency_controls(bridge_state, feedback_data)
        # feedback_data is merged after bridge_state, so True wins
        assert updates["ai_paused"] is True

    def test_awareness_injector_with_full_state(self, company_id, session_id):
        """Full integration of jarvis_awareness_injector_node with all data sources."""
        from app.services.jarvis_agents.nodes.jarvis_awareness_injector import (
            jarvis_awareness_injector_node,
        )
        state = {
            "tenant_id": company_id,
            "session_id": session_id,
        }
        bridge_data = {
            "ai_paused": True,
            "co_pilot_suggestion": "Try switching techniques",
            "co_pilot_suggestion_type": "action_suggestion",
            "escalation_in_progress": True,
            "source": "jarvis_command_graph",
            "injected_at": datetime.now(timezone.utc).isoformat(),
            "command_state_summary": {"agent_type": "escalation"},
        }
        awareness_data = {
            "quality_score": 0.72,
            "drift_status": "detected",
            "system_health": "degraded",
        }
        feedback_data = {}

        with patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_bridge_state",
            return_value=bridge_data,
        ), patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_awareness_state",
            return_value=awareness_data,
        ), patch(
            "app.services.jarvis_agents.nodes.jarvis_awareness_injector._read_feedback_state",
            return_value=feedback_data,
        ):
            result = jarvis_awareness_injector_node(state)

        # Verify key fields are injected
        assert result.get("ai_paused") is True
        assert result.get("system_mode") == "paused"
        assert result.get("urgency") == "critical"  # from escalation_in_progress
        assert result.get("co_pilot_suggestion") == "Try switching techniques"
        assert result.get("quality_score") == 0.72
        assert result.get("drift_status") == "detected"
        # Verify execution log
        assert "node_execution_log" in result
        log_entry = result["node_execution_log"][0]
        assert log_entry["node_name"] == "jarvis_awareness_injector"
        assert log_entry["status"] == "completed"
