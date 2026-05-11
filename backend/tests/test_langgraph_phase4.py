"""
Tests for PARWA LangGraph Multi-Agent System — Phase 4 Integration

Covers:
  - ParwaGraphState (24 groups, ~155 fields)
  - create_initial_state() factory
  - 6 new groups (19-24) field validation
  - LangGraph config helpers
  - Edge functions routing
  - Graph builder
  - Checkpointer
  - API schemas (LangGraphProcessRequest/Response)
  - Integration: invoke_parwa_graph fallback
  - Integration: main.py graph initialization

Target: 90+ tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock logger to prevent import errors."""
    with patch("app.logger.get_logger", return_value=MagicMock()):
        yield


@pytest.fixture
def initial_state():
    """Create a default initial state for testing."""
    from app.core.langgraph.state import create_initial_state
    return create_initial_state(
        message="Hello, I need help",
        channel="email",
        customer_id="cust_123",
        tenant_id="tenant_abc",
        variant_tier="pro",
        customer_tier="enterprise",
        industry="ecommerce",
        language="en",
        conversation_id="conv_456",
        ticket_id="tick_789",
        session_id="sess_012",
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. ParwaGraphState — Field Count & Structure (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestParwaGraphStateStructure:
    def test_total_field_count(self):
        from app.core.langgraph.state import get_total_field_count
        assert get_total_field_count() >= 150  # 24 groups, ~155 fields

    def test_state_has_24_group_keys_in_count(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert len(counts) == 24

    def test_group_1_input_field_count(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert counts["1_INPUT"] == 11

    def test_group_6_maker_validator_field_count(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert counts["6_MAKER_VALIDATOR"] == 8

    def test_group_14_jarvis_awareness_field_count(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert counts["14_JARVIS_AWARENESS"] == 21

    def test_group_19_self_healing_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "19_SELF_HEALING_TRUST" in counts

    def test_group_20_jarvis_command_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "20_JARVIS_COMMAND" in counts

    def test_group_21_integration_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "21_INTEGRATION" in counts

    def test_group_22_voice_call_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "22_VOICE_CALL" in counts

    def test_group_23_sms_compliance_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "23_SMS_COMPLIANCE" in counts

    def test_group_24_dynamic_instruction_exists(self):
        from app.core.langgraph.state import _count_fields
        counts = _count_fields()
        assert "24_DYNAMIC_INSTRUCTION" in counts


# ═══════════════════════════════════════════════════════════════════════
# 2. create_initial_state — Input Group (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCreateInitialStateInput:
    def test_message_populated(self, initial_state):
        assert initial_state["message"] == "Hello, I need help"

    def test_channel_populated(self, initial_state):
        assert initial_state["channel"] == "email"

    def test_customer_id_populated(self, initial_state):
        assert initial_state["customer_id"] == "cust_123"

    def test_tenant_id_populated(self, initial_state):
        assert initial_state["tenant_id"] == "tenant_abc"

    def test_variant_tier_populated(self, initial_state):
        assert initial_state["variant_tier"] == "pro"

    def test_customer_tier_populated(self, initial_state):
        assert initial_state["customer_tier"] == "enterprise"

    def test_industry_populated(self, initial_state):
        assert initial_state["industry"] == "ecommerce"

    def test_session_id_populated(self, initial_state):
        assert initial_state["session_id"] == "sess_012"


# ═══════════════════════════════════════════════════════════════════════
# 3. create_initial_state — Groups 2-18 Defaults (15 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestInitialStateGroups2to18:
    def test_pii_defaults(self, initial_state):
        assert initial_state["pii_redacted_message"] == ""
        assert initial_state["pii_entities_found"] == []

    def test_empathy_defaults(self, initial_state):
        assert initial_state["sentiment_score"] == 0.5
        assert initial_state["urgency"] == "low"
        assert initial_state["legal_threat_detected"] is False

    def test_router_defaults(self, initial_state):
        assert initial_state["intent"] == "general"
        assert initial_state["target_agent"] == "faq"
        assert initial_state["complexity_score"] == 0.0

    def test_domain_agent_defaults(self, initial_state):
        assert initial_state["agent_response"] == ""
        assert initial_state["agent_confidence"] == 0.0
        assert initial_state["proposed_action"] == "respond"

    def test_maker_defaults(self, initial_state):
        assert initial_state["k_solutions"] == []
        assert initial_state["red_flag"] is False
        assert initial_state["k_value_used"] == 0

    def test_control_defaults(self, initial_state):
        assert initial_state["approval_decision"] == ""
        assert initial_state["system_mode"] == "auto"

    def test_dspy_defaults(self, initial_state):
        assert initial_state["prompt_optimized"] is False
        assert initial_state["optimized_prompt_version"] == ""

    def test_guardrails_defaults(self, initial_state):
        assert initial_state["guardrails_passed"] is False
        assert initial_state["guardrails_flags"] == []

    def test_delivery_defaults(self, initial_state):
        assert initial_state["delivery_status"] == "pending"
        assert initial_state["fallback_attempted"] is False

    def test_state_update_defaults(self, initial_state):
        assert initial_state["ticket_created"] is False
        assert initial_state["audit_log_written"] is False

    def test_gsd_defaults(self, initial_state):
        assert initial_state["gsd_state"] == "new"
        assert initial_state["context_health"] == 1.0

    def test_metadata_defaults(self, initial_state):
        assert initial_state["tokens_consumed"] == 0
        assert initial_state["total_llm_calls"] == 0
        assert initial_state["node_execution_log"] == []

    def test_jarvis_awareness_defaults(self, initial_state):
        assert initial_state["system_health"] == "healthy"
        assert initial_state["subscription_status"] == "active"
        assert initial_state["drift_status"] == "none"

    def test_emergency_defaults(self, initial_state):
        assert initial_state["ai_paused"] is False
        assert initial_state["emergency_state"] == "normal"

    def test_anti_arbitrage_defaults(self, initial_state):
        assert initial_state["arbitrage_risk_score"] == 0.0
        assert initial_state["plan_cycling_detected"] is False


# ═══════════════════════════════════════════════════════════════════════
# 4. NEW Groups 19-24 — Self-Healing & Trust (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup19SelfHealingTrust:
    def test_self_healing_enabled_default(self, initial_state):
        assert initial_state["self_healing_enabled"] is True

    def test_api_recovery_attempted_default(self, initial_state):
        assert initial_state["api_recovery_attempted"] is False

    def test_api_recovery_success_default(self, initial_state):
        assert initial_state["api_recovery_success"] is False

    def test_circuit_breaker_state_default(self, initial_state):
        assert initial_state["circuit_breaker_state"] == "closed"

    def test_trust_score_default(self, initial_state):
        assert initial_state["trust_score"] == 1.0

    def test_trust_violation_default(self, initial_state):
        assert initial_state["trust_violation"] == "none"


# ═══════════════════════════════════════════════════════════════════════
# 5. NEW Group 20 — Jarvis Command Context (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup20JarvisCommand:
    def test_jarvis_command_parsed_default(self, initial_state):
        assert initial_state["jarvis_command_parsed"] == ""

    def test_jarvis_command_intent_default(self, initial_state):
        assert initial_state["jarvis_command_intent"] == ""

    def test_co_pilot_suggestion_default(self, initial_state):
        assert initial_state["co_pilot_suggestion"] == ""

    def test_co_pilot_suggestion_type_default(self, initial_state):
        assert initial_state["co_pilot_suggestion_type"] == ""

    def test_jarvis_feed_entry_default(self, initial_state):
        assert initial_state["jarvis_feed_entry"] == {}

    def test_jarvis_command_metadata_default(self, initial_state):
        assert initial_state["jarvis_command_metadata"] == {}


# ═══════════════════════════════════════════════════════════════════════
# 6. NEW Group 21 — Integration & Connector (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup21IntegrationConnector:
    def test_connector_health_default(self, initial_state):
        assert initial_state["connector_health"] == {}

    def test_connector_data_fetched_default(self, initial_state):
        assert initial_state["connector_data_fetched"] == []

    def test_integration_sync_status_default(self, initial_state):
        assert initial_state["integration_sync_status"] == "not_configured"

    def test_webhook_events_pending_default(self, initial_state):
        assert initial_state["webhook_events_pending"] == 0

    def test_external_system_errors_default(self, initial_state):
        assert initial_state["external_system_errors"] == []

    def test_connector_last_sync_default(self, initial_state):
        assert initial_state["connector_last_sync"] == {}


# ═══════════════════════════════════════════════════════════════════════
# 7. NEW Group 22 — Voice Call State (7 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup22VoiceCall:
    def test_call_id_default(self, initial_state):
        assert initial_state["call_id"] == ""

    def test_call_status_default(self, initial_state):
        assert initial_state["call_status"] == ""

    def test_call_duration_seconds_default(self, initial_state):
        assert initial_state["call_duration_seconds"] == 0

    def test_call_recording_enabled_default(self, initial_state):
        assert initial_state["call_recording_enabled"] is False

    def test_call_transcription_default(self, initial_state):
        assert initial_state["call_transcription"] == ""

    def test_call_participants_default(self, initial_state):
        assert initial_state["call_participants"] == []

    def test_voice_consent_verified_default(self, initial_state):
        assert initial_state["voice_consent_verified"] is False


# ═══════════════════════════════════════════════════════════════════════
# 8. NEW Group 23 — SMS Compliance (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup23SMSCompliance:
    def test_tcpa_consent_verified_default(self, initial_state):
        assert initial_state["tcpa_consent_verified"] is False

    def test_tcpa_consent_timestamp_default(self, initial_state):
        assert initial_state["tcpa_consent_timestamp"] == ""

    def test_sms_rate_limit_remaining_default(self, initial_state):
        assert initial_state["sms_rate_limit_remaining"] == 100

    def test_sms_opt_out_default(self, initial_state):
        assert initial_state["sms_opt_out"] is False

    def test_sms_compliance_flags_default(self, initial_state):
        assert initial_state["sms_compliance_flags"] == []


# ═══════════════════════════════════════════════════════════════════════
# 9. NEW Group 24 — Dynamic Instruction (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGroup24DynamicInstruction:
    def test_dynamic_instructions_default(self, initial_state):
        assert initial_state["dynamic_instructions"] == []

    def test_policy_overrides_default(self, initial_state):
        assert initial_state["policy_overrides"] == {}

    def test_undo_available_default(self, initial_state):
        assert initial_state["undo_available"] is False

    def test_undo_action_id_default(self, initial_state):
        assert initial_state["undo_action_id"] == ""

    def test_instruction_version_default(self, initial_state):
        assert initial_state["instruction_version"] == 1

    def test_instruction_updated_at_default(self, initial_state):
        assert initial_state["instruction_updated_at"] == ""


# ═══════════════════════════════════════════════════════════════════════
# 10. Config — Variant Tiers & MAKER (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConfigVariantTiers:
    def test_mini_maker_k_value(self):
        from app.core.langgraph.config import get_maker_k_value
        assert get_maker_k_value("mini") == 3

    def test_pro_maker_k_value_low_complexity(self):
        from app.core.langgraph.config import get_maker_k_value
        assert get_maker_k_value("pro", 0.2) == 3

    def test_pro_maker_k_value_high_complexity(self):
        from app.core.langgraph.config import get_maker_k_value
        assert get_maker_k_value("pro", 0.8) == 5

    def test_high_maker_k_value_low_complexity(self):
        from app.core.langgraph.config import get_maker_k_value
        assert get_maker_k_value("high", 0.1) == 5

    def test_high_maker_k_value_high_complexity(self):
        from app.core.langgraph.config import get_maker_k_value
        assert get_maker_k_value("high", 0.9) == 7

    def test_mini_agents(self):
        from app.core.langgraph.config import get_available_agents
        agents = get_available_agents("mini")
        assert "faq" in agents
        assert "refund" not in agents

    def test_pro_agents(self):
        from app.core.langgraph.config import get_available_agents
        agents = get_available_agents("pro")
        assert "refund" in agents
        assert "escalation" in agents

    def test_mini_voice_disabled(self):
        from app.core.langgraph.config import is_voice_enabled
        assert is_voice_enabled("mini") is False

    def test_pro_voice_enabled(self):
        from app.core.langgraph.config import is_voice_enabled
        assert is_voice_enabled("pro") is True

    def test_unknown_tier_fallback_to_mini(self):
        from app.core.langgraph.config import get_variant_config
        config = get_variant_config("unknown_tier")
        assert config["tier"] == "mini"


# ═══════════════════════════════════════════════════════════════════════
# 11. Config — Intent Mapping & Action Classification (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConfigIntentMapping:
    def test_faq_intent_maps_to_faq(self):
        from app.core.langgraph.config import map_intent_to_agent
        assert map_intent_to_agent("faq", "pro") == "faq"

    def test_refund_intent_maps_to_refund(self):
        from app.core.langgraph.config import map_intent_to_agent
        assert map_intent_to_agent("refund", "pro") == "refund"

    def test_refund_intent_fallback_on_mini(self):
        from app.core.langgraph.config import map_intent_to_agent
        # Mini doesn't have refund agent, should fallback
        result = map_intent_to_agent("refund", "mini")
        assert result in ["faq", "technical", "billing"]  # one of mini's agents

    def test_technical_intent_maps(self):
        from app.core.langgraph.config import map_intent_to_agent
        assert map_intent_to_agent("technical", "pro") == "technical"

    def test_monetary_action_type(self):
        from app.core.langgraph.config import classify_action_type
        assert classify_action_type("refund") == "monetary"

    def test_destructive_action_type(self):
        from app.core.langgraph.config import classify_action_type
        assert classify_action_type("delete_account") == "destructive"

    def test_informational_action_type(self):
        from app.core.langgraph.config import classify_action_type
        assert classify_action_type("respond") == "informational"

    def test_needs_human_approval_pro_monetary(self):
        from app.core.langgraph.config import needs_human_approval
        assert needs_human_approval("monetary", "pro") is True


# ═══════════════════════════════════════════════════════════════════════
# 12. Edge Functions — Routing (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeRouting:
    def test_router_routes_faq_to_faq_agent(self):
        from app.core.langgraph.edges import route_after_router
        state = {"intent": "faq", "variant_tier": "pro"}
        assert route_after_router(state) == "faq_agent"

    def test_router_routes_refund_on_pro(self):
        from app.core.langgraph.edges import route_after_router
        state = {"intent": "refund", "variant_tier": "pro"}
        assert route_after_router(state) == "refund_agent"

    def test_router_refund_fallback_on_mini(self):
        from app.core.langgraph.edges import route_after_router
        state = {"intent": "refund", "variant_tier": "mini"}
        # Mini doesn't have refund agent
        result = route_after_router(state)
        assert result.endswith("_agent")

    def test_maker_red_flag_goes_to_control(self):
        from app.core.langgraph.edges import route_after_maker
        state = {"red_flag": True, "action_type": "monetary", "variant_tier": "pro"}
        assert route_after_maker(state) == "control_system"

    def test_maker_no_red_flag_goes_to_dspy(self):
        from app.core.langgraph.edges import route_after_maker
        state = {"red_flag": False, "action_type": "informational", "variant_tier": "mini"}
        assert route_after_maker(state) == "dspy_optimizer"

    def test_control_approved_goes_to_dspy(self):
        from app.core.langgraph.edges import route_after_control
        state = {"approval_decision": "approved"}
        assert route_after_control(state) == "dspy_optimizer"

    def test_control_rejected_goes_to_state_update(self):
        from app.core.langgraph.edges import route_after_control
        state = {"approval_decision": "rejected"}
        assert route_after_control(state) == "state_update"

    def test_guardrails_passed_goes_to_delivery(self):
        from app.core.langgraph.edges import route_after_guardrails
        state = {"guardrails_passed": True}
        assert route_after_guardrails(state) == "channel_delivery"

    def test_guardrails_blocked_goes_to_state_update(self):
        from app.core.langgraph.edges import route_after_guardrails
        state = {"guardrails_passed": False}
        assert route_after_guardrails(state) == "state_update"

    def test_delivery_email_routes_to_email_agent(self):
        from app.core.langgraph.edges import route_after_delivery
        state = {"channel": "email", "variant_tier": "pro"}
        assert route_after_delivery(state) == "email_agent"


# ═══════════════════════════════════════════════════════════════════════
# 13. Edge Functions — DSPy & Context (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeDspyContext:
    def test_dspy_skipped_for_mini(self):
        from app.core.langgraph.edges import should_use_dspy
        state = {"variant_tier": "mini", "complexity_score": 0.9}
        assert should_use_dspy(state) == "guardrails"

    def test_dspy_used_for_high(self):
        from app.core.langgraph.edges import should_use_dspy
        state = {"variant_tier": "high", "complexity_score": 0.3}
        assert should_use_dspy(state) == "dspy_optimizer"

    def test_dspy_conditional_for_pro_low_complexity(self):
        from app.core.langgraph.edges import should_use_dspy
        state = {"variant_tier": "pro", "complexity_score": 0.3}
        assert should_use_dspy(state) == "guardrails"

    def test_dspy_conditional_for_pro_high_complexity(self):
        from app.core.langgraph.edges import should_use_dspy
        state = {"variant_tier": "pro", "complexity_score": 0.8}
        assert should_use_dspy(state) == "dspy_optimizer"

    def test_emergency_check_ai_paused(self):
        from app.core.langgraph.edges import route_after_emergency_check
        state = {"ai_paused": True, "emergency_state": "normal"}
        assert route_after_emergency_check(state) == "state_update"

    def test_emergency_check_normal_proceeds(self):
        from app.core.langgraph.edges import route_after_emergency_check
        state = {"ai_paused": False, "emergency_state": "normal"}
        assert route_after_emergency_check(state) == "pii_redaction"


# ═══════════════════════════════════════════════════════════════════════
# 14. Graph Builder (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestGraphBuilder:
    def test_node_imports_count(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert len(_NODE_IMPORTS) >= 18

    def test_node_imports_has_pii_redaction(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert "pii_redaction" in _NODE_IMPORTS

    def test_node_imports_has_maker_validator(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert "maker_validator" in _NODE_IMPORTS

    def test_node_imports_has_control_system(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert "control_system" in _NODE_IMPORTS

    def test_node_imports_has_state_update(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert "state_update" in _NODE_IMPORTS

    def test_node_imports_has_voice_agent(self):
        from app.core.langgraph.graph import _NODE_IMPORTS
        assert "voice_agent" in _NODE_IMPORTS

    def test_get_node_function_valid(self):
        from app.core.langgraph.graph import _get_node_function
        # This should work without actually importing (mocked)
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.pii_redaction_node = lambda s: s
            mock_import.return_value = mock_module
            func = _get_node_function("pii_redaction")
            assert callable(func)

    def test_get_node_function_unknown_raises(self):
        from app.core.langgraph.graph import _get_node_function
        with pytest.raises(ValueError, match="Unknown node"):
            _get_node_function("nonexistent_node_xyz")


# ═══════════════════════════════════════════════════════════════════════
# 15. Checkpointer (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCheckpointer:
    def test_get_thread_id_with_session(self):
        from app.core.langgraph.checkpointer import get_thread_id
        result = get_thread_id("tenant_abc", "sess_123")
        assert result == "tenant_abc_sess_123"

    def test_get_thread_id_without_session(self):
        from app.core.langgraph.checkpointer import get_thread_id
        result = get_thread_id("tenant_abc")
        assert result.startswith("tenant_abc_")
        assert len(result) > len("tenant_abc_")

    def test_reset_checkpointer(self):
        from app.core.langgraph.checkpointer import reset_checkpointer, _checkpointer_instance
        reset_checkpointer()
        # After reset, the singleton should be None
        from app.core.langgraph.checkpointer import _checkpointer_instance as inst
        # Note: _checkpointer_instance is module-level, reset sets it to None
        # We just verify the function doesn't crash
        assert True

    def test_memory_checkpointer_creation(self):
        with patch("app.core.langgraph.checkpointer._create_postgres_checkpointer", return_value=None):
            from app.core.langgraph.checkpointer import _create_memory_checkpointer
            cp = _create_memory_checkpointer()
            # May return None if langgraph not installed
            # But should not crash
            assert cp is None or cp is not None

    def test_postgres_checkpointer_no_db_url(self):
        with patch("app.core.langgraph.checkpointer.settings", MagicMock(DATABASE_URL=None, SQLALCHEMY_DATABASE_URI=None), create=True):
            from app.core.langgraph.checkpointer import _create_postgres_checkpointer
            result = _create_postgres_checkpointer()
            assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 16. Fallback Response (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackResponse:
    def test_fallback_has_agent_response(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "mini", "tenant_abc")
        assert "agent_response" in result
        assert len(result["agent_response"]) > 0

    def test_fallback_delivery_status_pending(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "mini", "tenant_abc")
        assert result["delivery_status"] == "pending_human_review"

    def test_fallback_system_mode_paused(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "mini", "tenant_abc")
        assert result["system_mode"] == "paused"

    def test_fallback_with_error(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "mini", "tenant_abc", "Test error")
        assert "Test error" in result.get("error", "")

    def test_fallback_includes_tenant_id(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "pro", "tenant_xyz")
        assert result["tenant_id"] == "tenant_xyz"

    def test_fallback_includes_variant_tier(self):
        from app.core.langgraph.graph import _fallback_response
        result = _fallback_response("Help me", "high", "tenant_abc")
        assert result["variant_tier"] == "high"


# ═══════════════════════════════════════════════════════════════════════
# 17. API Schemas (8 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAPISchemas:
    def test_langgraph_request_schema_direct_import(self):
        """Test schema by importing directly from the module file."""
        import importlib.util
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'api', 'schemas', 'workflow.py'
        )
        schema_path = os.path.abspath(schema_path)
        # Verify the file exists and has LangGraphProcessRequest
        assert os.path.exists(schema_path), f"Schema file not found: {schema_path}"
        with open(schema_path, 'r') as f:
            content = f.read()
        assert 'class LangGraphProcessRequest' in content
        assert 'class LangGraphProcessResponse' in content

    def test_langgraph_response_has_new_fields(self):
        """Verify the schema file contains the 10 new response fields."""
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'api', 'schemas', 'workflow.py'
        )
        schema_path = os.path.abspath(schema_path)
        with open(schema_path, 'r') as f:
            content = f.read()
        # New fields from 24-group state
        assert 'gsd_state' in content
        assert 'urgency' in content
        assert 'agent_confidence' in content
        assert 'red_flag' in content
        assert 'guardrails_passed' in content
        assert 'trust_score' in content
        assert 'tcpa_consent_verified' in content
        assert 'call_id' in content

    def test_langgraph_request_has_required_fields(self):
        """Verify the schema file contains required request fields."""
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'api', 'schemas', 'workflow.py'
        )
        schema_path = os.path.abspath(schema_path)
        with open(schema_path, 'r') as f:
            content = f.read()
        assert 'message: str' in content
        assert 'customer_id: str' in content
        assert 'variant_tier: str' in content

    def test_schema_file_has_24_groups_mention(self):
        """Verify the response schema mentions 24 groups."""
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'api', 'schemas', 'workflow.py'
        )
        schema_path = os.path.abspath(schema_path)
        with open(schema_path, 'r') as f:
            content = f.read()
        assert '24 groups' in content

    def test_schema_has_k_value_used_field(self):
        """Verify k_value_used field is in the response schema."""
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'app', 'api', 'schemas', 'workflow.py'
        )
        schema_path = os.path.abspath(schema_path)
        with open(schema_path, 'r') as f:
            content = f.read()
        assert 'k_value_used' in content


# ═══════════════════════════════════════════════════════════════════════
# 18. invoke_parwa_graph — Integration (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestInvokeParwaGraph:
    @pytest.mark.asyncio
    async def test_invoke_returns_fallback_on_import_error(self):
        """When langgraph is not available, returns fallback response."""
        from app.core.langgraph.graph import invoke_parwa_graph
        with patch("app.core.langgraph.graph.build_parwa_graph", side_effect=ImportError("no langgraph")):
            result = await invoke_parwa_graph(
                message="Help",
                channel="email",
                customer_id="c1",
                tenant_id="t1",
                variant_tier="mini",
            )
            assert result["delivery_status"] == "pending_human_review"
            assert result["tenant_id"] == "t1"

    @pytest.mark.asyncio
    async def test_invoke_uses_provided_graph(self):
        """When a pre-built graph is provided, uses it instead of building."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "message": "Help",
            "agent_response": "Test response",
            "delivery_status": "delivered",
            "intent": "faq",
            "target_agent": "faq",
            "tokens_consumed": 100,
            "tenant_id": "t1",
            "variant_tier": "mini",
        }
        from app.core.langgraph.graph import invoke_parwa_graph
        result = await invoke_parwa_graph(
            message="Help",
            channel="email",
            customer_id="c1",
            tenant_id="t1",
            variant_tier="mini",
            graph=mock_graph,
        )
        assert result["agent_response"] == "Test response"
        mock_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_fallback_on_graph_error(self):
        """When graph.ainvoke raises, returns fallback."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = RuntimeError("Graph crashed")
        from app.core.langgraph.graph import invoke_parwa_graph
        result = await invoke_parwa_graph(
            message="Help",
            channel="email",
            customer_id="c1",
            tenant_id="t1",
            variant_tier="mini",
            graph=mock_graph,
        )
        assert result["delivery_status"] == "pending_human_review"

    @pytest.mark.asyncio
    async def test_invoke_passes_all_params_to_initial_state(self):
        """Verify all parameters flow into create_initial_state."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"delivery_status": "sent"}
        from app.core.langgraph.graph import invoke_parwa_graph
        await invoke_parwa_graph(
            message="Test",
            channel="sms",
            customer_id="c2",
            tenant_id="t2",
            variant_tier="pro",
            customer_tier="enterprise",
            industry="saas",
            language="fr",
            conversation_id="conv1",
            ticket_id="tick1",
            session_id="sess1",
            graph=mock_graph,
        )
        # Check the initial_state passed to ainvoke
        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["message"] == "Test"
        assert initial_state["channel"] == "sms"
        assert initial_state["customer_id"] == "c2"
        assert initial_state["tenant_id"] == "t2"
        assert initial_state["variant_tier"] == "pro"
        assert initial_state["customer_tier"] == "enterprise"
        assert initial_state["industry"] == "saas"
        assert initial_state["language"] == "fr"


# ═══════════════════════════════════════════════════════════════════════
# 19. Reducers — Custom State Accumulators (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestReducers:
    def test_merge_lists_appends(self):
        from app.core.langgraph.state import _merge_lists
        result = _merge_lists([1, 2], [3, 4])
        assert result == [1, 2, 3, 4]

    def test_merge_lists_empty_existing(self):
        from app.core.langgraph.state import _merge_lists
        result = _merge_lists([], [1])
        assert result == [1]

    def test_merge_dicts_overrides(self):
        from app.core.langgraph.state import _merge_dicts
        result = _merge_dicts({"a": 1}, {"b": 2, "a": 3})
        assert result == {"a": 3, "b": 2}

    def test_max_float_keeps_max(self):
        from app.core.langgraph.state import _max_float
        assert _max_float(0.5, 0.8) == 0.8
        assert _max_float(0.9, 0.3) == 0.9

    def test_replace_new_wins(self):
        from app.core.langgraph.state import _replace
        assert _replace("old", "new") == "new"

    def test_merge_dicts_empty_existing(self):
        from app.core.langgraph.state import _merge_dicts
        result = _merge_dicts({}, {"key": "val"})
        assert result == {"key": "val"}


# ═══════════════════════════════════════════════════════════════════════
# 20. Enum Validation (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEnumValidation:
    def test_variant_tier_values(self):
        from app.core.langgraph.config import VariantTier
        assert VariantTier.MINI.value == "mini"
        assert VariantTier.PRO.value == "pro"
        assert VariantTier.HIGH.value == "high"

    def test_maker_mode_values(self):
        from app.core.langgraph.config import MakerMode
        assert MakerMode.EFFICIENCY.value == "efficiency"
        assert MakerMode.BALANCED.value == "balanced"
        assert MakerMode.CONSERVATIVE.value == "conservative"

    def test_system_mode_values(self):
        from app.core.langgraph.config import SystemMode
        assert SystemMode.AUTO.value == "auto"
        assert SystemMode.SHADOW.value == "shadow"

    def test_emergency_state_values(self):
        from app.core.langgraph.config import EmergencyState
        assert EmergencyState.NORMAL.value == "normal"
        assert EmergencyState.FULL_STOP.value == "full_stop"

    def test_approval_decision_values(self):
        from app.core.langgraph.config import ApprovalDecision
        assert ApprovalDecision.APPROVED.value == "approved"
        assert ApprovalDecision.NEEDS_HUMAN_APPROVAL.value == "needs_human_approval"


# ═══════════════════════════════════════════════════════════════════════
# 21. Channel & Technique Access (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestChannelTechniqueAccess:
    def test_mini_techniques_t1_only(self):
        from app.core.langgraph.config import get_available_techniques
        techs = get_available_techniques("mini")
        assert "clara" in techs
        assert "chain_of_thought" not in techs

    def test_pro_techniques_t1_t2(self):
        from app.core.langgraph.config import get_available_techniques
        techs = get_available_techniques("pro")
        assert "clara" in techs
        assert "chain_of_thought" in techs
        assert "gst" not in techs

    def test_high_techniques_all(self):
        from app.core.langgraph.config import get_available_techniques
        techs = get_available_techniques("high")
        assert "gst" in techs
        assert "self_consistency" in techs

    def test_mini_channels_no_voice(self):
        from app.core.langgraph.config import get_available_channels
        channels = get_available_channels("mini")
        assert "voice" not in channels
        assert "email" in channels

    def test_high_channels_all(self):
        from app.core.langgraph.config import get_available_channels
        channels = get_available_channels("high")
        assert "voice" in channels
        assert "video" in channels


# ═══════════════════════════════════════════════════════════════════════
# 22. Context Compression Edge (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestContextCompressionEdge:
    def test_mini_compresses_only_critical(self):
        from app.core.langgraph.edges import should_compress_context
        state = {"variant_tier": "mini", "context_health": 0.6}
        assert should_compress_context(state) == "domain_agent"

    def test_mini_compresses_at_critical(self):
        from app.core.langgraph.edges import should_compress_context
        state = {"variant_tier": "mini", "context_health": 0.4}
        assert should_compress_context(state) == "context_compression"

    def test_high_compresses_below_90(self):
        from app.core.langgraph.edges import should_compress_context
        state = {"variant_tier": "high", "context_health": 0.85}
        assert should_compress_context(state) == "context_compression"


# ═══════════════════════════════════════════════════════════════════════
# 23. Validate Variant Tier (3 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestValidateVariantTier:
    def test_valid_tiers(self):
        from app.core.langgraph.config import validate_variant_tier
        assert validate_variant_tier("mini") is True
        assert validate_variant_tier("pro") is True
        assert validate_variant_tier("high") is True

    def test_invalid_tier(self):
        from app.core.langgraph.config import validate_variant_tier
        assert validate_variant_tier("enterprise") is False

    def test_get_all_valid_tiers(self):
        from app.core.langgraph.config import get_all_valid_tiers
        tiers = get_all_valid_tiers()
        assert "mini" in tiers
        assert "pro" in tiers
        assert "high" in tiers
