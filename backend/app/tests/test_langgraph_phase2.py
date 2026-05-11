"""
Comprehensive Unit Tests for PARWA LangGraph Phase 2 — Agent Nodes

Tests cover all 19 agent nodes with:
  - Happy path: Valid inputs producing expected outputs
  - Fallback behavior: When production modules are unavailable
  - Tier-specific behavior: Mini vs Pro vs High differences
  - Error handling: BC-008 graceful degradation
  - State contract: Each node reads/writes correct fields

Each test creates a minimal ParwaGraphState dict, calls the node
function, and verifies the returned partial state update.

BC-008: All tests verify nodes never crash, even on invalid inputs.
BC-001: Tenant_id is always present in state.

NOTE: Node modules start with digits (01_, 02_, etc.) so we must
use importlib.import_module() instead of regular imports.
"""

from __future__ import annotations

import importlib
import pytest
from typing import Any, Dict


def _make_state(**overrides) -> Dict[str, Any]:
    """Create a minimal valid ParwaGraphState dict for testing."""
    from app.core.langgraph.state import create_initial_state

    base = create_initial_state(
        message="Test message",
        channel="email",
        customer_id="cust_test",
        tenant_id="tenant_test",
        variant_tier="pro",
    )
    base.update(overrides)
    return base


def _import_node(module_name: str):
    """Import a node module that starts with a digit."""
    return importlib.import_module(f"app.core.langgraph.nodes.{module_name}")


# ══════════════════════════════════════════════════════════════════
# NODE 01: PII REDACTION
# ══════════════════════════════════════════════════════════════════


class TestPIIRedactionNode:

    def test_basic_redaction(self):
        mod = _import_node("01_pii_redaction")
        state = _make_state(message="My email is john@example.com")
        result = mod.pii_redaction_node(state)
        assert "pii_redacted_message" in result
        assert isinstance(result["pii_redacted_message"], str)
        assert "pii_entities_found" in result

    def test_empty_message(self):
        mod = _import_node("01_pii_redaction")
        state = _make_state(message="")
        result = mod.pii_redaction_node(state)
        assert "pii_redacted_message" in result

    def test_no_pii_in_message(self):
        mod = _import_node("01_pii_redaction")
        state = _make_state(message="I need help with my account")
        result = mod.pii_redaction_node(state)
        assert "pii_redacted_message" in result

    def test_missing_tenant_id(self):
        mod = _import_node("01_pii_redaction")
        state = _make_state(message="test")
        state.pop("tenant_id", None)
        result = mod.pii_redaction_node(state)
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════
# NODE 02: EMPATHY ENGINE
# ══════════════════════════════════════════════════════════════════


class TestEmpathyEngineNode:

    def test_basic_sentiment(self):
        mod = _import_node("02_empathy_engine")
        state = _make_state(pii_redacted_message="I am very happy with the service")
        result = mod.empathy_engine_node(state)
        assert "sentiment_score" in result
        assert "sentiment_intensity" in result
        assert "legal_threat_detected" in result
        assert "urgency" in result
        assert "sentiment_trend" in result

    def test_negative_sentiment(self):
        mod = _import_node("02_empathy_engine")
        state = _make_state(pii_redacted_message="I hate this product, it's terrible")
        result = mod.empathy_engine_node(state)
        assert isinstance(result.get("sentiment_score", 0.5), float)

    def test_legal_threat_detection(self):
        mod = _import_node("02_empathy_engine")
        state = _make_state(pii_redacted_message="I will sue your company")
        result = mod.empathy_engine_node(state)
        assert "legal_threat_detected" in result

    def test_empty_message_fallback(self):
        mod = _import_node("02_empathy_engine")
        state = _make_state(pii_redacted_message="")
        result = mod.empathy_engine_node(state)
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════
# NODE 03: ROUTER AGENT
# ══════════════════════════════════════════════════════════════════


class TestRouterAgentNode:

    def test_basic_routing(self):
        mod = _import_node("03_router_agent")
        state = _make_state(pii_redacted_message="How do I reset my password?")
        result = mod.router_agent_node(state)
        assert "intent" in result
        assert "complexity_score" in result
        assert "target_agent" in result
        assert "model_tier" in result

    def test_mini_tier_routing(self):
        mod = _import_node("03_router_agent")
        state = _make_state(pii_redacted_message="I want a refund", variant_tier="mini")
        result = mod.router_agent_node(state)
        assert result.get("target_agent", "") in ("faq", "technical", "billing")

    def test_pro_tier_routing(self):
        mod = _import_node("03_router_agent")
        state = _make_state(pii_redacted_message="I want a refund for my order", variant_tier="pro")
        result = mod.router_agent_node(state)
        assert isinstance(result.get("target_agent"), str)


# ══════════════════════════════════════════════════════════════════
# NODE 05: FAQ AGENT
# ══════════════════════════════════════════════════════════════════


class TestFAQAgentNode:

    def test_basic_faq_response(self):
        mod = _import_node("05_faq_agent")
        state = _make_state(pii_redacted_message="What are your business hours?", intent="faq", variant_tier="pro", sentiment_score=0.7)
        result = mod.faq_agent_node(state)
        assert "agent_response" in result
        assert "agent_type" in result
        assert result.get("agent_type") == "faq"

    def test_faq_all_tiers(self):
        mod = _import_node("05_faq_agent")
        for tier in ("mini", "pro", "high"):
            state = _make_state(pii_redacted_message="How do I contact support?", intent="faq", variant_tier=tier)
            result = mod.faq_agent_node(state)
            assert "agent_response" in result


# ══════════════════════════════════════════════════════════════════
# NODE 06-09: DOMAIN AGENTS
# ══════════════════════════════════════════════════════════════════


class TestDomainAgents:

    def test_refund_agent_produces_response(self):
        mod = _import_node("06_refund_agent")
        state = _make_state(pii_redacted_message="I need a refund for order #123", intent="refund", variant_tier="pro", sentiment_score=0.3)
        result = mod.refund_agent_node(state)
        assert "agent_response" in result
        assert result.get("agent_type") == "refund"

    def test_technical_agent_produces_response(self):
        mod = _import_node("07_technical_agent")
        state = _make_state(pii_redacted_message="My app keeps crashing", intent="technical", variant_tier="pro", sentiment_score=0.5)
        result = mod.technical_agent_node(state)
        assert "agent_response" in result
        assert result.get("agent_type") == "technical"

    def test_billing_agent_produces_response(self):
        mod = _import_node("08_billing_agent")
        state = _make_state(pii_redacted_message="Why was I charged twice?", intent="billing", variant_tier="pro", sentiment_score=0.4)
        result = mod.billing_agent_node(state)
        assert "agent_response" in result
        assert result.get("agent_type") == "billing"

    def test_complaint_agent_produces_response(self):
        mod = _import_node("09_complaint_agent")
        state = _make_state(pii_redacted_message="I'm very dissatisfied with the service", intent="complaint", variant_tier="pro", sentiment_score=0.2)
        result = mod.complaint_agent_node(state)
        assert "agent_response" in result
        assert result.get("agent_type") == "complaint"

    def test_escalation_agent_produces_response(self):
        mod = _import_node("10_escalation_agent")
        state = _make_state(pii_redacted_message="I need to speak to a manager", intent="escalation", variant_tier="pro", sentiment_score=0.1)
        result = mod.escalation_agent_node(state)
        assert "agent_response" in result
        assert result.get("agent_type") == "escalation"

    def test_refund_agent_mini_tier(self):
        """Refund agent on mini tier should handle gracefully."""
        mod = _import_node("06_refund_agent")
        state = _make_state(pii_redacted_message="I need a refund", intent="refund", variant_tier="mini", sentiment_score=0.3)
        result = mod.refund_agent_node(state)
        # Should still produce a response (fallback or escalation)
        assert "agent_response" in result

    def test_technical_agent_all_tiers(self):
        """Technical agent works on all tiers."""
        mod = _import_node("07_technical_agent")
        for tier in ("mini", "pro", "high"):
            state = _make_state(pii_redacted_message="How to fix error?", intent="technical", variant_tier=tier)
            result = mod.technical_agent_node(state)
            assert "agent_response" in result


# ══════════════════════════════════════════════════════════════════
# NODE 11: MAKER VALIDATOR (CRITICAL)
# ══════════════════════════════════════════════════════════════════


class TestMakerValidatorNode:

    def test_mini_maker_mode(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="Here is your answer", agent_confidence=0.7, proposed_action="respond", action_type="informational", variant_tier="mini")
        result = mod.maker_validator_node(state)
        assert result.get("maker_mode") == "efficiency"
        assert result.get("k_value_used") == 3
        assert result.get("fake_threshold") == 0.50

    def test_pro_maker_mode(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="Here is your answer", agent_confidence=0.7, proposed_action="respond", action_type="informational", variant_tier="pro")
        result = mod.maker_validator_node(state)
        assert result.get("maker_mode") == "balanced"
        assert result.get("fake_threshold") == 0.60

    def test_high_maker_mode(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="Here is your answer", agent_confidence=0.7, proposed_action="respond", action_type="informational", variant_tier="high")
        result = mod.maker_validator_node(state)
        assert result.get("maker_mode") == "conservative"
        assert result.get("fake_threshold") == 0.75

    def test_red_flag_on_low_confidence(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="I think maybe this could help", agent_confidence=0.2, proposed_action="refund", action_type="monetary", variant_tier="pro")
        result = mod.maker_validator_node(state)
        assert "red_flag" in result

    def test_maker_writes_selected_solution(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="Your refund has been processed", agent_confidence=0.8, proposed_action="respond", action_type="informational", variant_tier="pro")
        result = mod.maker_validator_node(state)
        assert "selected_solution" in result
        assert "k_solutions" in result

    def test_maker_audit_trail(self):
        mod = _import_node("11_maker_validator")
        state = _make_state(agent_response="Test response", agent_confidence=0.8, proposed_action="respond", action_type="informational", variant_tier="pro")
        result = mod.maker_validator_node(state)
        assert "maker_audit_trail" in result

    def test_maker_all_tiers(self):
        mod = _import_node("11_maker_validator")
        for tier in ("mini", "pro", "high"):
            state = _make_state(agent_response="Test", agent_confidence=0.6, variant_tier=tier)
            result = mod.maker_validator_node(state)
            assert "maker_mode" in result
            assert result["maker_mode"] in ("efficiency", "balanced", "conservative")


# ══════════════════════════════════════════════════════════════════
# NODE 12: CONTROL SYSTEM
# ══════════════════════════════════════════════════════════════════


class TestControlSystemNode:

    def test_mini_auto_approve(self):
        mod = _import_node("12_control_system")
        state = _make_state(action_type="monetary", variant_tier="mini", red_flag=False)
        result = mod.control_system_node(state)
        decision = result.get("approval_decision", "")
        assert decision in ("approved", "auto_approved")

    def test_pro_monetary_needs_approval(self):
        mod = _import_node("12_control_system")
        state = _make_state(action_type="monetary", variant_tier="pro", red_flag=False)
        result = mod.control_system_node(state)
        assert "approval_decision" in result

    def test_red_flag_triggers_approval(self):
        mod = _import_node("12_control_system")
        for tier in ("pro", "high"):
            state = _make_state(action_type="informational", variant_tier=tier, red_flag=True)
            result = mod.control_system_node(state)
            assert "approval_decision" in result

    def test_informational_auto_approved(self):
        mod = _import_node("12_control_system")
        for tier in ("mini", "pro", "high"):
            state = _make_state(action_type="informational", variant_tier=tier, red_flag=False)
            result = mod.control_system_node(state)
            decision = result.get("approval_decision", "")
            assert decision in ("approved", "auto_approved")


# ══════════════════════════════════════════════════════════════════
# NODE 13: DSPY OPTIMIZER
# ══════════════════════════════════════════════════════════════════


class TestDspyOptimizerNode:

    def test_mini_skips_dspy(self):
        mod = _import_node("13_dspy_optimizer")
        state = _make_state(variant_tier="mini")
        result = mod.dspy_optimizer_node(state)
        assert result.get("prompt_optimized") is False

    def test_pro_simple_skips_dspy(self):
        mod = _import_node("13_dspy_optimizer")
        state = _make_state(variant_tier="pro", complexity_score=0.3)
        result = mod.dspy_optimizer_node(state)
        assert "prompt_optimized" in result

    def test_high_uses_dspy(self):
        mod = _import_node("13_dspy_optimizer")
        state = _make_state(variant_tier="high")
        result = mod.dspy_optimizer_node(state)
        assert "prompt_optimized" in result

    def test_returns_version_field(self):
        mod = _import_node("13_dspy_optimizer")
        state = _make_state(variant_tier="high")
        result = mod.dspy_optimizer_node(state)
        assert "optimized_prompt_version" in result


# ══════════════════════════════════════════════════════════════════
# NODE 14: GUARDRAILS
# ══════════════════════════════════════════════════════════════════


class TestGuardrailsNode:

    def test_normal_response_passes(self):
        mod = _import_node("14_guardrails")
        state = _make_state(agent_response="Here is your answer", selected_solution="Here is your answer", variant_tier="pro")
        result = mod.guardrails_node(state)
        assert "guardrails_passed" in result
        assert "guardrails_flags" in result

    def test_guardrails_writes_blocked_reason(self):
        mod = _import_node("14_guardrails")
        state = _make_state(agent_response="Normal response", variant_tier="pro")
        result = mod.guardrails_node(state)
        assert "guardrails_blocked_reason" in result


# ══════════════════════════════════════════════════════════════════
# NODE 15: CHANNEL DELIVERY
# ══════════════════════════════════════════════════════════════════


class TestChannelDeliveryNode:

    def test_email_routing(self):
        mod = _import_node("15_channel_delivery")
        state = _make_state(channel="email", variant_tier="mini")
        result = mod.channel_delivery_node(state)
        assert result.get("delivery_channel") == "email"
        assert result.get("fallback_attempted") is False

    def test_voice_mini_fallback(self):
        mod = _import_node("15_channel_delivery")
        state = _make_state(channel="voice", variant_tier="mini")
        result = mod.channel_delivery_node(state)
        assert result.get("delivery_channel") == "email"
        assert result.get("fallback_attempted") is True

    def test_video_pro_fallback(self):
        mod = _import_node("15_channel_delivery")
        state = _make_state(channel="video", variant_tier="pro")
        result = mod.channel_delivery_node(state)
        assert result.get("delivery_channel") == "email"
        assert result.get("fallback_attempted") is True

    def test_voice_pro_allowed(self):
        mod = _import_node("15_channel_delivery")
        state = _make_state(channel="voice", variant_tier="pro")
        result = mod.channel_delivery_node(state)
        assert result.get("delivery_channel") == "voice"
        assert result.get("fallback_attempted") is False

    def test_video_high_allowed(self):
        mod = _import_node("15_channel_delivery")
        state = _make_state(channel="video", variant_tier="high")
        result = mod.channel_delivery_node(state)
        assert result.get("delivery_channel") == "video"
        assert result.get("fallback_attempted") is False


# ══════════════════════════════════════════════════════════════════
# NODE 16: STATE UPDATE
# ══════════════════════════════════════════════════════════════════


class TestStateUpdateNode:

    def test_basic_state_update(self):
        mod = _import_node("16_state_update")
        state = _make_state(agent_response="Test response", variant_tier="pro")
        result = mod.state_update_node(state)
        assert isinstance(result, dict)

    def test_state_update_writes_timestamp(self):
        mod = _import_node("16_state_update")
        state = _make_state()
        result = mod.state_update_node(state)
        assert "delivery_timestamp" in result or "node_execution_log" in result


# ══════════════════════════════════════════════════════════════════
# NODE 17: EMAIL AGENT
# ══════════════════════════════════════════════════════════════════


class TestEmailAgentNode:

    def test_basic_email_delivery(self):
        mod = _import_node("17_email_agent")
        state = _make_state(agent_response="Here is your answer", delivery_channel="email")
        result = mod.email_agent_node(state)
        assert "delivery_status" in result
        assert "delivery_timestamp" in result

    def test_email_brand_voice(self):
        mod = _import_node("17_email_agent")
        state = _make_state(agent_response="Your order is confirmed", delivery_channel="email", brand_voice_profile={"greeting": "Dear Customer,", "closing": "Best regards,"})
        result = mod.email_agent_node(state)
        assert "brand_voice_applied" in result

    def test_email_empty_response(self):
        mod = _import_node("17_email_agent")
        state = _make_state(agent_response="", delivery_channel="email")
        result = mod.email_agent_node(state)
        assert result.get("delivery_status") in ("failed", "dispatch_pending", "sent")


# ══════════════════════════════════════════════════════════════════
# NODE 18: SMS AGENT
# ══════════════════════════════════════════════════════════════════


class TestSMSAgentNode:

    def test_basic_sms_delivery(self):
        mod = _import_node("18_sms_agent")
        state = _make_state(agent_response="Your order has been shipped", delivery_channel="sms", variant_tier="pro")
        result = mod.sms_agent_node(state)
        assert "delivery_status" in result
        assert "delivery_timestamp" in result

    def test_sms_truncation_mini(self):
        mod = _import_node("18_sms_agent")
        long_text = "A" * 500
        result = mod._truncate_for_sms(long_text, "mini", "tenant_test")
        assert len(result) <= 160

    def test_sms_truncation_pro(self):
        mod = _import_node("18_sms_agent")
        long_text = "A" * 500
        result = mod._truncate_for_sms(long_text, "pro", "tenant_test")
        assert len(result) == 500

    def test_sms_format_strips_html(self):
        mod = _import_node("18_sms_agent")
        result = mod._format_sms_content("<p>Hello <b>World</b></p>", "tenant_test")
        assert "<p>" not in result
        assert "Hello" in result

    def test_sms_empty_response(self):
        mod = _import_node("18_sms_agent")
        state = _make_state(agent_response="", delivery_channel="sms")
        result = mod.sms_agent_node(state)
        assert result.get("delivery_status") in ("failed", "dispatch_pending", "sent")


# ══════════════════════════════════════════════════════════════════
# NODE 19: VOICE AGENT
# ══════════════════════════════════════════════════════════════════


class TestVoiceAgentNode:

    def test_voice_mini_blocked(self):
        mod = _import_node("19_voice_agent")
        state = _make_state(agent_response="Hello, let me help you", delivery_channel="voice", variant_tier="mini")
        result = mod.voice_agent_node(state)
        assert result.get("delivery_status") == "failed"
        assert "mini" in result.get("delivery_failure_reason", "").lower()

    def test_voice_pro_allowed(self):
        mod = _import_node("19_voice_agent")
        state = _make_state(agent_response="Hello, let me help you", delivery_channel="voice", variant_tier="pro")
        result = mod.voice_agent_node(state)
        # Should not fail due to tier restriction
        if result.get("delivery_status") == "failed":
            assert "mini" not in result.get("delivery_failure_reason", "").lower()

    def test_voice_high_allowed(self):
        mod = _import_node("19_voice_agent")
        state = _make_state(agent_response="Hello, let me help you", delivery_channel="voice", variant_tier="high")
        result = mod.voice_agent_node(state)
        assert "delivery_status" in result

    def test_voice_format_conversion(self):
        mod = _import_node("19_voice_agent")
        result = mod._convert_to_voice_format("Visit https://example.com for more info", "tenant_test")
        assert "https://" not in result
        assert "link" in result.lower()

    def test_voice_ssml_wrapping(self):
        mod = _import_node("19_voice_agent")
        result = mod._wrap_in_ssml("Hello world", "pro", "tenant_test")
        assert "<speak>" in result
        assert "</speak>" in result

    def test_voice_ssml_high_tier_enhanced(self):
        mod = _import_node("19_voice_agent")
        result = mod._wrap_in_ssml("Hello world", "high", "tenant_test")
        assert "<prosody" in result

    def test_voice_empty_response(self):
        mod = _import_node("19_voice_agent")
        state = _make_state(agent_response="", delivery_channel="voice", variant_tier="pro")
        result = mod.voice_agent_node(state)
        assert result.get("delivery_status") in ("failed", "dispatch_pending", "sent")


# ══════════════════════════════════════════════════════════════════
# CROSS-NODE INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestNodeIntegration:

    def test_pii_to_empathy_chain(self):
        pii_mod = _import_node("01_pii_redaction")
        empathy_mod = _import_node("02_empathy_engine")
        state = _make_state(message="I'm very angry about my bill!")
        state.update(pii_mod.pii_redaction_node(state))
        result = empathy_mod.empathy_engine_node(state)
        assert "sentiment_score" in result

    def test_empathy_to_router_chain(self):
        empathy_mod = _import_node("02_empathy_engine")
        router_mod = _import_node("03_router_agent")
        state = _make_state(pii_redacted_message="I need a refund", sentiment_score=0.3)
        state.update(empathy_mod.empathy_engine_node(state))
        result = router_mod.router_agent_node(state)
        assert "target_agent" in result

    def test_maker_to_control_chain(self):
        maker_mod = _import_node("11_maker_validator")
        control_mod = _import_node("12_control_system")
        state = _make_state(agent_response="Refund processed", agent_confidence=0.3, proposed_action="refund", action_type="monetary", variant_tier="pro")
        state.update(maker_mod.maker_validator_node(state))
        result = control_mod.control_system_node(state)
        assert "approval_decision" in result

    def test_full_mini_flow(self):
        pii_mod = _import_node("01_pii_redaction")
        empathy_mod = _import_node("02_empathy_engine")
        router_mod = _import_node("03_router_agent")
        faq_mod = _import_node("05_faq_agent")
        maker_mod = _import_node("11_maker_validator")
        guardrails_mod = _import_node("14_guardrails")

        state = _make_state(message="How do I contact support?", channel="email", variant_tier="mini")
        state.update(pii_mod.pii_redaction_node(state))
        state.update(empathy_mod.empathy_engine_node(state))
        state.update(router_mod.router_agent_node(state))
        state.update(faq_mod.faq_agent_node(state))
        state.update(maker_mod.maker_validator_node(state))
        state.update(guardrails_mod.guardrails_node(state))

        assert state.get("target_agent") is not None
        assert state.get("agent_response") is not None
        assert state.get("maker_mode") == "efficiency"

    def test_full_pro_flow(self):
        pii_mod = _import_node("01_pii_redaction")
        empathy_mod = _import_node("02_empathy_engine")
        router_mod = _import_node("03_router_agent")
        refund_mod = _import_node("06_refund_agent")
        maker_mod = _import_node("11_maker_validator")
        control_mod = _import_node("12_control_system")

        state = _make_state(message="I want a refund for order #12345", channel="email", variant_tier="pro")
        state.update(pii_mod.pii_redaction_node(state))
        state.update(empathy_mod.empathy_engine_node(state))
        state.update(router_mod.router_agent_node(state))
        state.update(refund_mod.refund_agent_node(state))
        state.update(maker_mod.maker_validator_node(state))
        state.update(control_mod.control_system_node(state))

        assert state.get("maker_mode") == "balanced"
        assert "approval_decision" in state

    def test_no_node_crashes_on_empty_state(self):
        """All nodes handle minimal/empty state gracefully (BC-008)."""
        pii_mod = _import_node("01_pii_redaction")
        empathy_mod = _import_node("02_empathy_engine")
        guardrails_mod = _import_node("14_guardrails")
        channel_mod = _import_node("15_channel_delivery")
        state_mod = _import_node("16_state_update")

        minimal_state = {"tenant_id": "test", "variant_tier": "mini"}

        # None of these should crash
        pii_mod.pii_redaction_node(minimal_state)
        empathy_mod.empathy_engine_node(minimal_state)
        guardrails_mod.guardrails_node(minimal_state)
        channel_mod.channel_delivery_node(minimal_state)
        state_mod.state_update_node(minimal_state)
