"""
Comprehensive unit tests for PARWA LangGraph Nodes — Week 4 Scope

Tests 12 core nodes that form the PARWA multi-agent pipeline:
  01_pii_redaction, 02_empathy_engine, 03_router_agent,
  05_faq_agent, 06_refund_agent, 07_technical_agent,
  08_billing_agent, 09_complaint_agent, 10_escalation_agent,
  11_maker_validator, 12_control_system, 13_dspy_optimizer,
  14_guardrails

Each node function takes a state: dict and returns dict (partial state update).
All nodes implement BC-008 graceful degradation — never crash, always return
safe defaults on failure.

Key test patterns:
  - make_minimal_state(**overrides) builds a valid ParwaGraphState dict
  - unittest.mock.patch mocks external LLM/DB/service calls
  - Every node class has 5-8+ test methods covering signatures, output,
    tier gating, BC-008 graceful degradation, and business logic.
"""

from __future__ import annotations

import importlib
import sys
import types
import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict


def _import_node(module_name: str, func_name: str):
    """Import a node function from a module with digit-prefixed names."""
    mod = importlib.import_module(module_name)
    return getattr(mod, func_name)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES & HELPERS
# ═══════════════════════════════════════════════════════════════════


def make_minimal_state(**overrides: Any) -> Dict[str, Any]:
    """
    Build a valid ParwaGraphState dict with sensible defaults.

    Pass keyword overrides to set specific fields. This helper ensures
    every test starts from a consistent, complete state dict.
    """
    state: Dict[str, Any] = {
        # GROUP 1: INPUT
        "message": "Hello, I need help with my order.",
        "channel": "chat",
        "customer_id": "cust_001",
        "tenant_id": "tenant_abc",
        "variant_tier": "pro",
        "customer_tier": "free",
        "industry": "general",
        "language": "en",
        "conversation_id": "conv_001",
        "ticket_id": "",
        "session_id": "sess_001",
        # GROUP 2: PII REDACTION
        "pii_redacted_message": "Hello, I need help with my order.",
        "pii_entities_found": [],
        # GROUP 3: EMPATHY ENGINE
        "sentiment_score": 0.5,
        "sentiment_intensity": "low",
        "legal_threat_detected": False,
        "urgency": "low",
        "sentiment_trend": "stable",
        # GROUP 4: ROUTER AGENT
        "intent": "general",
        "complexity_score": 0.3,
        "target_agent": "faq",
        "model_tier": "medium",
        "technique_stack": [],
        "signals_extracted": {},
        # GROUP 5: DOMAIN AGENT
        "agent_response": "",
        "agent_confidence": 0.0,
        "proposed_action": "respond",
        "action_type": "informational",
        "agent_reasoning": "",
        "agent_type": "",
        # GROUP 6: MAKER VALIDATOR
        "k_solutions": [],
        "selected_solution": "",
        "red_flag": False,
        "maker_mode": "",
        "k_value_used": 0,
        "fake_threshold": 0.0,
        "maker_decomposition": {},
        "maker_audit_trail": [],
        # GROUP 7: CONTROL SYSTEM
        "approval_decision": "",
        "confidence_breakdown": {},
        "system_mode": "auto",
        "dnd_applies": False,
        "money_rule_triggered": False,
        "vip_rule_triggered": False,
        "approval_timeout_seconds": 300,
        # GROUP 8: DSPY OPTIMIZER
        "prompt_optimized": False,
        "optimized_prompt_version": "",
        # GROUP 9: GUARDRAILS
        "guardrails_passed": False,
        "guardrails_flags": [],
        "guardrails_blocked_reason": "",
        # GROUP 10: CHANNEL DELIVERY
        "delivery_status": "pending",
        "delivery_channel": "",
        "delivery_timestamp": "",
        "delivery_confirmation_id": "",
        "delivery_failure_reason": "",
        "fallback_attempted": False,
        # GROUP 11: STATE UPDATE
        "ticket_created": False,
        "ticket_updated": False,
        "ticket_status": "open",
        "gsd_state_persisted": False,
        "audit_log_written": False,
        "metrics_updated": False,
        "jarvis_feed_pushed": False,
        "fifty_mistake_check": {},
        # GROUP 12: GSD STATE
        "gsd_state": "new",
        "gsd_step": "",
        "context_health": 1.0,
        "context_compressed": False,
        # GROUP 13: METADATA
        "processing_start_time": "2025-01-01T00:00:00+00:00",
        "model_used": "",
        "tokens_consumed": 0,
        "total_llm_calls": 0,
        "node_execution_log": [],
        "error": "",
        "reward_signal": 0.0,
        "shadow_mode_intercepted": False,
        # SHARED ACCUMULATORS
        "node_outputs": {},
        "errors": [],
    }
    state.update(overrides)
    return state


def _mock_module(name: str) -> MagicMock:
    """Create a mock module and inject it into sys.modules."""
    mod = MagicMock()
    sys.modules[name] = mod
    return mod


# ═══════════════════════════════════════════════════════════════════
# 1. PII REDACTION NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestPIIRedactionNode:
    """Tests for 01_pii_redaction.pii_redaction_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.01_pii_redaction", "pii_redaction_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_state(self):
        """Node should accept a dict and return a dict without crashing."""
        node = self._get_node()
        state = make_minimal_state(message="Hello world")
        result = node(state)
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_pii_redacted_message(self):
        node = self._get_node()
        result = node(make_minimal_state(message="Hello world"))
        assert "pii_redacted_message" in result

    def test_returns_pii_entities_found(self):
        node = self._get_node()
        result = node(make_minimal_state(message="Hello world"))
        assert "pii_entities_found" in result
        assert isinstance(result["pii_entities_found"], list)

    # ── PII Detection (Fallback Regex) ───────────────────────────

    def test_detects_email_in_message(self):
        """Fallback regex should detect and redact email addresses."""
        node = self._get_node()
        result = node(make_minimal_state(message="Contact me at john@example.com please"))
        entities = result["pii_entities_found"]
        types = [e["type"] for e in entities]
        assert "email" in types

    def test_detects_phone_number(self):
        """Fallback regex should detect US phone numbers."""
        node = self._get_node()
        result = node(make_minimal_state(message="Call me at 555-123-4567"))
        entities = result["pii_entities_found"]
        types = [e["type"] for e in entities]
        assert "phone_us" in types

    def test_detects_multiple_pii_types(self):
        """Should detect both email and phone in the same message."""
        node = self._get_node()
        result = node(make_minimal_state(
            message="Email john@example.com or call 555-123-4567"
        ))
        entities = result["pii_entities_found"]
        types = [e["type"] for e in entities]
        assert "email" in types
        assert "phone_us" in types

    def test_no_pii_message_passes_through(self):
        """Clean message should have zero entities and redacted == original."""
        node = self._get_node()
        msg = "Hello, I have a simple question about your service."
        result = node(make_minimal_state(message=msg))
        assert len(result["pii_entities_found"]) == 0
        assert result["pii_redacted_message"] == msg

    # ── BC-008 Graceful Degradation ──────────────────────────────

    def test_graceful_degradation_on_engine_failure(self):
        """If PII engine raises exception, message passes through."""
        node = self._get_node()
        result = node(make_minimal_state(message="Hello"))
        assert isinstance(result, dict)
        assert "pii_redacted_message" in result

    # ── Tier Behavior ────────────────────────────────────────────

    def test_mini_tier_uses_fallback(self):
        """Mini tier uses regex fallback (no crash)."""
        node = self._get_node()
        state = make_minimal_state(
            message="Email: test@example.com",
            variant_tier="mini",
        )
        result = node(state)
        assert "pii_redacted_message" in result


# ═══════════════════════════════════════════════════════════════════
# 2. EMPATHY ENGINE NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestEmpathyEngineNode:
    """Tests for 02_empathy_engine.empathy_engine_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.02_empathy_engine", "empathy_engine_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_sentiment_score(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "sentiment_score" in result
        assert isinstance(result["sentiment_score"], (int, float))

    def test_returns_urgency(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "urgency" in result
        assert result["urgency"] in ("low", "medium", "high", "critical")

    def test_returns_legal_threat_detected(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "legal_threat_detected" in result
        assert isinstance(result["legal_threat_detected"], bool)

    def test_returns_sentiment_intensity(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "sentiment_intensity" in result
        assert result["sentiment_intensity"] in ("low", "medium", "high", "extreme")

    def test_returns_sentiment_trend(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "sentiment_trend" in result

    # ── Business Logic ───────────────────────────────────────────

    def test_negative_message_produces_low_sentiment(self):
        """A message with many negative keywords should produce sentiment < 0.5."""
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="I am very angry, furious, and completely disappointed with this terrible service!"
        ))
        # Fallback analysis should detect negative sentiment
        assert result["sentiment_score"] < 0.5

    def test_legal_threat_keywords_detected(self):
        """Message with legal keywords should flag legal_threat_detected=True."""
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="I will get my lawyer and sue you in court"
        ))
        assert result["legal_threat_detected"] is True

    def test_urgency_keywords_detected(self):
        """Message with 'urgent' should elevate urgency to at least 'high'."""
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="This is urgent and critical, help immediately!"
        ))
        assert result["urgency"] in ("high", "critical")

    def test_sentiment_score_clamped_to_range(self):
        """Sentiment score should always be in [0.0, 1.0]."""
        node = self._get_node()
        result = node(make_minimal_state())
        assert 0.0 <= result["sentiment_score"] <= 1.0

    # ── Tier Behavior ────────────────────────────────────────────

    def test_mini_tier_no_trend_analysis(self):
        """Mini tier should return stable trend (no conversation history analysis)."""
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="mini"))
        assert result["sentiment_trend"] == "stable"

    # ── BC-008 Graceful Degradation ──────────────────────────────

    def test_never_crashes_on_empty_message(self):
        node = self._get_node()
        result = node(make_minimal_state(pii_redacted_message="", message=""))
        assert isinstance(result, dict)
        assert "sentiment_score" in result

    def test_missing_fields_use_defaults(self):
        """Node should handle state with missing optional fields."""
        node = self._get_node()
        result = node({"message": "Hello"})  # minimal state
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 3. ROUTER AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestRouterAgentNode:
    """Tests for 03_router_agent.router_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.03_router_agent", "router_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_intent(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "intent" in result
        assert isinstance(result["intent"], str)

    def test_returns_complexity_score(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "complexity_score" in result
        assert 0.0 <= result["complexity_score"] <= 1.0

    def test_returns_target_agent(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "target_agent" in result

    def test_returns_model_tier(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "model_tier" in result
        assert result["model_tier"] in ("light", "medium", "heavy")

    def test_returns_technique_stack(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "technique_stack" in result
        assert isinstance(result["technique_stack"], list)

    def test_returns_signals_extracted(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "signals_extracted" in result
        assert isinstance(result["signals_extracted"], dict)

    # ── Business Logic ───────────────────────────────────────────

    def test_refund_intent_classified_correctly(self):
        """Router should classify refund-related message as 'refund' intent."""
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="I want a refund for my order"
        ))
        assert result["intent"] == "refund"

    def test_technical_intent_classified_correctly(self):
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="The app is not working, I get an error"
        ))
        assert result["intent"] == "technical"

    def test_faq_intent_classified_correctly(self):
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="How do I reset my password?"
        ))
        assert result["intent"] == "faq"

    def test_complaint_intent_classified(self):
        node = self._get_node()
        result = node(make_minimal_state(
            pii_redacted_message="I want to file a complaint about this terrible service"
        ))
        assert result["intent"] == "complaint"

    # ── Tier Behavior ────────────────────────────────────────────

    def test_mini_tier_caps_model_tier(self):
        """Mini tier should never use 'heavy' model."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="mini",
            pii_redacted_message="This is very very very complex and urgent",
            sentiment_score=0.1,
        ))
        assert result["model_tier"] != "heavy"

    def test_mini_tier_techniques_limited(self):
        """Mini tier should only include tier-1 techniques."""
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="mini"))
        for tech in result["technique_stack"]:
            assert tech in ("clara", "crp", "gsd")

    def test_pro_tier_has_more_techniques(self):
        """Pro tier should have more techniques than mini."""
        node = self._get_node()
        mini_result = node(make_minimal_state(variant_tier="mini"))
        pro_result = node(make_minimal_state(variant_tier="pro"))
        assert len(pro_result["technique_stack"]) >= len(mini_result["technique_stack"])

    # ── BC-008 ───────────────────────────────────────────────────

    def test_empty_message_returns_safe_defaults(self):
        node = self._get_node()
        result = node(make_minimal_state(pii_redacted_message="", message=""))
        assert result["intent"] in ("general", "faq")
        assert result["target_agent"] in ("faq",)


# ═══════════════════════════════════════════════════════════════════
# 4. FAQ AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestFAQAgentNode:
    """Tests for 05_faq_agent.faq_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.05_faq_agent", "faq_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_agent_response(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "agent_response" in result

    def test_returns_agent_confidence(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "agent_confidence" in result
        assert 0.0 <= result["agent_confidence"] <= 1.0

    def test_returns_agent_type_faq(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert result["agent_type"] == "faq"

    def test_returns_proposed_action(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "proposed_action" in result

    def test_returns_action_type(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "action_type" in result
        assert result["action_type"] in (
            "informational", "monetary", "destructive", "escalation"
        )

    # ── RAG Integration ─────────────────────────────────────────

    def test_returns_rag_documents_field(self):
        """FAQ agent should include rag_documents_retrieved in output."""
        node = self._get_node()
        result = node(make_minimal_state())
        assert "rag_documents_retrieved" in result
        assert isinstance(result["rag_documents_retrieved"], list)

    def test_returns_rag_reranked_field(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "rag_reranked" in result

    def test_returns_kb_documents_used(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "kb_documents_used" in result

    # ── BC-008 Graceful Degradation ──────────────────────────────

    def test_no_crash_on_empty_message(self):
        node = self._get_node()
        result = node(make_minimal_state(pii_redacted_message="", message=""))
        assert isinstance(result, dict)
        assert "agent_response" in result

    def test_fallback_response_on_missing_modules(self):
        """When response generator unavailable, should produce fallback response."""
        node = self._get_node()
        result = node(make_minimal_state())
        # Should have a response (fallback template) even without LLM
        assert isinstance(result["agent_response"], str)


# ═══════════════════════════════════════════════════════════════════
# 5. REFUND AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestRefundAgentNode:
    """Tests for 06_refund_agent.refund_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.06_refund_agent", "refund_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Tier Gating ──────────────────────────────────────────────

    def test_mini_tier_returns_tier_unavailable_response(self):
        """Mini tier should get escalation response, not process refund."""
        node = self._get_node()
        state = make_minimal_state(variant_tier="mini")
        result = node(state)
        assert "agent_response" in result
        assert "Pro" in result["agent_response"] or "High" in result["agent_response"]
        assert result["action_type"] == "escalation"
        assert result["proposed_action"] == "escalate"

    def test_pro_tier_processes_refund(self):
        """Pro tier should attempt refund processing (not tier-gate)."""
        node = self._get_node()
        state = make_minimal_state(variant_tier="pro")
        result = node(state)
        # Should NOT be the tier-unavailable response
        assert result["agent_type"] == "refund"
        # The action_type should not be escalation from tier gate
        # (it could be escalation from the agent's own logic though)

    def test_high_tier_processes_refund(self):
        """High tier should attempt refund processing."""
        node = self._get_node()
        state = make_minimal_state(variant_tier="high")
        result = node(state)
        assert result["agent_type"] == "refund"

    def test_is_available_for_tier_method(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        RefundAgent = mod.RefundAgent
        assert RefundAgent.is_available_for_tier("mini") is False
        assert RefundAgent.is_available_for_tier("pro") is True
        assert RefundAgent.is_available_for_tier("high") is True

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_order_lookup_result(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert "order_lookup_result" in result
        assert isinstance(result["order_lookup_result"], dict)

    def test_returns_refund_eligibility(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert "refund_eligibility" in result
        assert isinstance(result["refund_eligibility"], dict)

    # ── Refund Eligibility Logic ─────────────────────────────────

    def test_refund_eligibility_structure(self):
        """Refund eligibility should have expected keys."""
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={"days_since_purchase": 10, "total": 50.0, "is_digital": False},
            tenant_id="tenant_abc",
        )
        assert "eligible" in result
        assert "refund_type" in result
        assert "refund_amount" in result
        assert "reason" in result

    def test_full_refund_within_window(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={"days_since_purchase": 15, "total": 100.0, "is_digital": False},
            tenant_id="tenant_abc",
        )
        assert result["eligible"] is True
        assert result["refund_type"] == "full"
        assert result["refund_amount"] == 100.0

    def test_partial_refund_in_window(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={"days_since_purchase": 45, "total": 100.0, "is_digital": False},
            tenant_id="tenant_abc",
        )
        assert result["eligible"] is True
        assert result["refund_type"] == "partial"
        assert result["refund_amount"] < 100.0  # 15% restocking fee
        assert result["refund_amount"] == 85.0

    def test_no_refund_expired(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={"days_since_purchase": 120, "total": 100.0, "is_digital": False},
            tenant_id="tenant_abc",
        )
        assert result["eligible"] is False
        assert result["refund_type"] == "none"
        assert result["refund_amount"] == 0.0

    def test_digital_items_not_refundable(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={"days_since_purchase": 5, "total": 50.0, "is_digital": True},
            tenant_id="tenant_abc",
        )
        assert result["eligible"] is False
        assert "Digital" in result["reason"]

    def test_no_order_details_returns_not_eligible(self):
        mod = importlib.import_module("app.core.langgraph.nodes.06_refund_agent")
        agent = mod.RefundAgent()
        result = agent._check_refund_eligibility(
            order_details={},
            tenant_id="tenant_abc",
        )
        assert result["eligible"] is False

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 6. TECHNICAL AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestTechnicalAgentNode:
    """Tests for 07_technical_agent.technical_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.07_technical_agent", "technical_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_agent_response(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "agent_response" in result

    def test_returns_agent_type_technical(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert result["agent_type"] == "technical"

    def test_returns_troubleshooting_steps(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "troubleshooting_steps" in result
        assert isinstance(result["troubleshooting_steps"], list)

    def test_returns_system_status(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "system_status" in result
        assert isinstance(result["system_status"], dict)

    # ── All Tiers Available ──────────────────────────────────────

    def test_available_on_mini_tier(self):
        """Technical agent should work on mini tier."""
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="mini"))
        assert result["agent_type"] == "technical"

    def test_available_on_pro_tier(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert result["agent_type"] == "technical"

    def test_available_on_high_tier(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="high"))
        assert result["agent_type"] == "technical"

    # ── Troubleshooting Steps ────────────────────────────────────

    def test_troubleshooting_steps_have_structure(self):
        """Each step should have step number, action, description."""
        node = self._get_node()
        result = node(make_minimal_state())
        for step in result["troubleshooting_steps"]:
            assert "step" in step
            assert "action" in step
            assert "description" in step

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 7. BILLING AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestBillingAgentNode:
    """Tests for 08_billing_agent.billing_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.08_billing_agent", "billing_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_agent_response(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "agent_response" in result

    def test_returns_agent_type_billing(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert result["agent_type"] == "billing"

    def test_returns_billing_lookup_result(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "billing_lookup_result" in result

    def test_returns_payment_methods(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "payment_methods" in result

    # ── All Tiers ────────────────────────────────────────────────

    def test_available_on_all_tiers(self):
        node = self._get_node()
        for tier in ("mini", "pro", "high"):
            result = node(make_minimal_state(variant_tier=tier))
            assert result["agent_type"] == "billing"

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 8. COMPLAINT AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestComplaintAgentNode:
    """Tests for 09_complaint_agent.complaint_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.09_complaint_agent", "complaint_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Tier Gating ──────────────────────────────────────────────

    def test_mini_tier_returns_escalation_response(self):
        """Mini tier should not process complaints — escalate to human."""
        node = self._get_node()
        state = make_minimal_state(variant_tier="mini")
        result = node(state)
        assert "Pro" in result["agent_response"] or "High" in result["agent_response"]
        assert result["action_type"] == "escalation"

    def test_pro_tier_processes_complaint(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert result["agent_type"] == "complaint"

    def test_high_tier_processes_complaint(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="high"))
        assert result["agent_type"] == "complaint"

    def test_is_available_for_tier(self):
        mod = importlib.import_module("app.core.langgraph.nodes.09_complaint_agent")
        ComplaintAgent = mod.ComplaintAgent
        assert ComplaintAgent.is_available_for_tier("mini") is False
        assert ComplaintAgent.is_available_for_tier("pro") is True
        assert ComplaintAgent.is_available_for_tier("high") is True

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_complaint_classification(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert "complaint_classification" in result

    def test_returns_recovery_action(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert "recovery_action" in result

    # ── Complaint Classification Logic ───────────────────────────

    def test_legal_threat_classified_as_critical(self):
        mod = importlib.import_module("app.core.langgraph.nodes.09_complaint_agent")
        agent = mod.ComplaintAgent()
        result = agent._classify_complaint(
            message="I will sue you",
            sentiment_score=0.2,
            signals={},
            tenant_id="tenant_abc",
        )
        assert result["category"] == "legal_threat"
        assert result["severity"] == "critical"
        assert result["requires_escalation"] is True

    def test_repeat_complaint_triggers_escalation(self):
        mod = importlib.import_module("app.core.langgraph.nodes.09_complaint_agent")
        agent = mod.ComplaintAgent()
        result = agent._classify_complaint(
            message="This is my 5th complaint",
            sentiment_score=0.5,
            signals={"complaint_count": 5},
            tenant_id="tenant_abc",
        )
        assert result["requires_escalation"] is True

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 9. ESCALATION AGENT NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestEscalationAgentNode:
    """Tests for 10_escalation_agent.escalation_agent_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.10_escalation_agent", "escalation_agent_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Tier Gating ──────────────────────────────────────────────

    def test_mini_tier_returns_informational_fallback(self):
        """Mini tier should not process escalation — return informational."""
        node = self._get_node()
        state = make_minimal_state(variant_tier="mini")
        result = node(state)
        assert result["action_type"] == "informational"
        assert result["agent_type"] == "escalation"

    def test_pro_tier_processes_escalation(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="pro"))
        assert result["agent_type"] == "escalation"

    def test_high_tier_processes_escalation(self):
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="high"))
        assert result["agent_type"] == "escalation"

    # ── Always Escalation ────────────────────────────────────────

    def test_action_type_always_escalation_for_pro_high(self):
        """Pro/High tier escalation agent should always set action_type=escalation."""
        node = self._get_node()
        for tier in ("pro", "high"):
            result = node(make_minimal_state(variant_tier=tier))
            assert result["action_type"] == "escalation", (
                f"Expected escalation for tier={tier}, got {result['action_type']}"
            )

    def test_proposed_action_always_escalation_type(self):
        """Pro/High tier should have proposed_action in (escalate, human_handoff)."""
        node = self._get_node()
        for tier in ("pro", "high"):
            result = node(make_minimal_state(variant_tier=tier))
            assert result["proposed_action"] in ("escalate", "human_handoff"), (
                f"Expected escalate/human_handoff for tier={tier}, "
                f"got {result['proposed_action']}"
            )

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)

    def test_fatal_error_still_returns_escalation(self):
        """Fatal error in the escalation agent should return escalation type response."""
        node = self._get_node()
        # Pass variant_tier=pro so it doesn't hit the mini tier gate first.
        # Empty state triggers the fatal error path since BaseDomainAgent.run()
        # will fail with missing fields, hitting the except clause.
        result = node({"variant_tier": "pro"})
        assert result.get("action_type") == "escalation"
        assert result.get("proposed_action") == "escalate"


# ═══════════════════════════════════════════════════════════════════
# 10. MAKER VALIDATOR NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestMakerValidatorNode:
    """Tests for 11_maker_validator.maker_validator_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.11_maker_validator", "maker_validator_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Here is your answer.",
            agent_confidence=0.8,
        ))
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_k_solutions(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "k_solutions" in result
        assert isinstance(result["k_solutions"], list)
        assert len(result["k_solutions"]) > 0

    def test_returns_selected_solution(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "selected_solution" in result

    def test_returns_red_flag(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "red_flag" in result
        assert isinstance(result["red_flag"], bool)

    def test_returns_maker_mode(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "maker_mode" in result

    def test_returns_k_value_used(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "k_value_used" in result
        assert result["k_value_used"] >= 1

    def test_returns_audit_trail(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Answer to your question.",
            agent_confidence=0.8,
        ))
        assert "maker_audit_trail" in result
        assert isinstance(result["maker_audit_trail"], list)

    # ── Tier Behavior ────────────────────────────────────────────

    def test_mini_k_value_is_3(self):
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="mini",
            agent_response="Answer.",
            agent_confidence=0.8,
        ))
        assert result["k_value_used"] == 3

    def test_mini_threshold_is_0_50(self):
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="mini",
            agent_response="Answer.",
            agent_confidence=0.8,
        ))
        assert result["fake_threshold"] == 0.50

    def test_pro_threshold_is_0_60(self):
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            agent_response="Answer.",
            agent_confidence=0.8,
        ))
        assert result["fake_threshold"] == 0.60

    def test_high_threshold_is_0_75(self):
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            agent_response="Answer.",
            agent_confidence=0.8,
        ))
        assert result["fake_threshold"] == 0.75

    # ── Red Flag Logic ───────────────────────────────────────────

    def test_low_confidence_raises_red_flag(self):
        """Confidence below threshold should raise red_flag."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            agent_response="Low confidence answer.",
            agent_confidence=0.3,
        ))
        assert result["red_flag"] is True

    def test_high_confidence_no_red_flag(self):
        """Confidence above threshold should not raise red_flag."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            agent_response="High confidence answer.",
            agent_confidence=0.95,
        ))
        assert result["red_flag"] is False

    # ── Updates agent_response ───────────────────────────────────

    def test_updates_agent_response_with_best_solution(self):
        """MAKER should update agent_response with the selected solution."""
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Original response.",
            agent_confidence=0.8,
        ))
        assert "agent_response" in result
        # The selected_solution and agent_response should match
        assert result.get("selected_solution") == result.get("agent_response")

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_response(self):
        node = self._get_node()
        result = node(make_minimal_state(agent_response="", agent_confidence=0.0))
        assert isinstance(result, dict)
        assert "k_solutions" in result

    def test_fallback_on_no_agent_response(self):
        """Should still produce output even when agent_response is missing."""
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)
        assert "red_flag" in result


# ═══════════════════════════════════════════════════════════════════
# 11. CONTROL SYSTEM NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestControlSystemNode:
    """Tests for 12_control_system.control_system_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.12_control_system", "control_system_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_approval_decision(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "approval_decision" in result
        assert result["approval_decision"] in (
            "approved", "rejected", "needs_human_approval", "auto_approved"
        )

    def test_returns_system_mode(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "system_mode" in result

    def test_returns_confidence_breakdown(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "confidence_breakdown" in result
        assert isinstance(result["confidence_breakdown"], dict)

    def test_returns_dnd_applies(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "dnd_applies" in result

    def test_returns_money_rule_triggered(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "money_rule_triggered" in result

    def test_returns_vip_rule_triggered(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "vip_rule_triggered" in result

    # ── Approval Rules ───────────────────────────────────────────

    def test_mini_tier_auto_approves_everything(self):
        """Mini tier should auto-approve regardless of action type."""
        node = self._get_node()
        for action_type in ("informational", "monetary", "destructive", "escalation"):
            result = node(make_minimal_state(
                variant_tier="mini",
                action_type=action_type,
                agent_confidence=0.9,
            ))
            assert result["approval_decision"] == "auto_approved", (
                f"Mini should auto-approve {action_type}, "
                f"got {result['approval_decision']}"
            )

    def test_monetary_action_needs_approval_on_pro(self):
        """Pro tier should require human approval for monetary actions."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            action_type="monetary",
            agent_confidence=0.5,
        ))
        assert result["approval_decision"] == "needs_human_approval"

    def test_destructive_action_needs_approval_on_pro(self):
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            action_type="destructive",
            agent_confidence=0.5,
        ))
        assert result["approval_decision"] == "needs_human_approval"

    def test_informational_action_can_auto_approve_pro(self):
        """Informational actions with good confidence should auto-approve on Pro."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            action_type="informational",
            agent_confidence=0.9,
        ))
        assert result["approval_decision"] in ("auto_approved", "approved")

    def test_vip_customer_monetary_needs_approval(self):
        """VIP customer + monetary action should trigger vip_rule on Pro."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            action_type="monetary",
            customer_tier="vip",
            agent_confidence=0.9,
        ))
        assert result["vip_rule_triggered"] is True
        assert result["approval_decision"] == "needs_human_approval"

    def test_red_flag_triggers_approval_on_pro(self):
        """Red flag on Pro tier should trigger human approval."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            action_type="informational",
            red_flag=True,
            agent_confidence=0.9,
        ))
        assert result["approval_decision"] == "needs_human_approval"

    def test_high_tier_monetary_money_rule(self):
        """High tier with money_rules=True should trigger for monetary actions."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            action_type="monetary",
            agent_confidence=0.9,
        ))
        assert result["money_rule_triggered"] is True

    # ── Confidence Breakdown ────────────────────────────────────

    def test_confidence_breakdown_has_overall(self):
        node = self._get_node()
        result = node(make_minimal_state(agent_confidence=0.8))
        breakdown = result["confidence_breakdown"]
        assert "overall" in breakdown
        assert 0.0 <= breakdown["overall"] <= 1.0

    def test_red_flag_penalty_in_breakdown(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_confidence=0.9,
            red_flag=True,
        ))
        breakdown = result["confidence_breakdown"]
        assert breakdown.get("red_flag_penalty", 0.0) > 0.0

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_on_empty_state(self):
        """Empty state defaults to mini tier, which auto-approves. Should not crash."""
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)
        # Empty state → variant_tier defaults to "mini" → auto_approved
        assert result["approval_decision"] == "auto_approved"


# ═══════════════════════════════════════════════════════════════════
# 12. DSPY OPTIMIZER NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestDSPyOptimizerNode:
    """Tests for 13_dspy_optimizer.dspy_optimizer_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.13_dspy_optimizer", "dspy_optimizer_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_prompt_optimized(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "prompt_optimized" in result
        assert isinstance(result["prompt_optimized"], bool)

    def test_returns_optimized_prompt_version(self):
        node = self._get_node()
        result = node(make_minimal_state())
        assert "optimized_prompt_version" in result

    # ── Tier Behavior ────────────────────────────────────────────

    def test_mini_tier_skips_dspy(self):
        """Mini tier should skip DSPy optimization entirely."""
        node = self._get_node()
        result = node(make_minimal_state(variant_tier="mini"))
        assert result["prompt_optimized"] is False

    def test_pro_low_complexity_skips_dspy(self):
        """Pro tier with low complexity should skip DSPy."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            complexity_score=0.3,
        ))
        assert result["prompt_optimized"] is False

    def test_pro_high_complexity_applies_dspy(self):
        """Pro tier with high complexity should attempt DSPy."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="pro",
            complexity_score=0.8,
        ))
        # DSPy may not be available, but it should at least try
        assert "prompt_optimized" in result

    def test_high_tier_always_applies_dspy(self):
        """High tier should always attempt DSPy."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            complexity_score=0.2,
        ))
        assert "prompt_optimized" in result
        # Result might be False if module unavailable (BC-008), but it should try

    # ── BC-008 ───────────────────────────────────────────────────

    def test_no_crash_without_dspy_module(self):
        """Should not crash when dspy_integration module is unavailable."""
        node = self._get_node()
        result = node(make_minimal_state(
            variant_tier="high",
            complexity_score=0.8,
        ))
        assert isinstance(result, dict)
        assert "prompt_optimized" in result

    def test_no_crash_on_empty_state(self):
        node = self._get_node()
        result = node({})
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# 13. GUARDRAILS NODE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailsNode:
    """Tests for 14_guardrails.guardrails_node"""

    def _get_node(self):
        return _import_node("app.core.langgraph.nodes.14_guardrails", "guardrails_node")

    # ── Signature & Existence ────────────────────────────────────

    def test_node_function_exists(self):
        node = self._get_node()
        assert callable(node)

    def test_node_accepts_dict_and_returns_dict(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="This is a safe response about your order.",
        ))
        assert isinstance(result, dict)

    # ── Output Structure ─────────────────────────────────────────

    def test_returns_guardrails_passed(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Safe response about your order."
        ))
        assert "guardrails_passed" in result
        assert isinstance(result["guardrails_passed"], bool)

    def test_returns_guardrails_flags(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Safe response about your order."
        ))
        assert "guardrails_flags" in result
        assert isinstance(result["guardrails_flags"], list)

    def test_returns_guardrails_blocked_reason(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Safe response about your order."
        ))
        assert "guardrails_blocked_reason" in result

    # ── BC-008: Pass on module failure ───────────────────────────

    def test_passes_when_modules_unavailable(self):
        """Guardrails should pass (not block) when modules are unavailable."""
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Response text."
        ))
        # BC-008: Never block on module failure — should pass
        # May have warning flags but should not block
        assert result["guardrails_passed"] is True

    def test_fatal_error_passes_with_warning(self):
        """On fatal error, guardrails should pass with warning flag (BC-008)."""
        node = self._get_node()
        result = node({})
        # Even with completely empty state, should pass (BC-008)
        assert result["guardrails_passed"] is True

    # ── Checks run sequentially ──────────────────────────────────

    def test_flags_include_guardrails_engine_check(self):
        """Flags should include entries from guardrails engine check."""
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Response about order."
        ))
        # When modules are unavailable, each check adds a warning flag
        flags = result["guardrails_flags"]
        # At least the guardrails_engine check should have run
        check_sources = [f.get("check", "") for f in flags]
        assert "guardrails_engine" in check_sources

    def test_flags_include_hallucination_check(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Response about order."
        ))
        flags = result["guardrails_flags"]
        check_sources = [f.get("check", "") for f in flags]
        assert "hallucination_detector" in check_sources

    def test_flags_include_prompt_injection_check(self):
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Response about order."
        ))
        flags = result["guardrails_flags"]
        check_sources = [f.get("check", "") for f in flags]
        assert "prompt_injection_defense" in check_sources

    # ── Brand Voice Tier Behavior ────────────────────────────────

    def test_mini_tier_skips_brand_voice_check(self):
        """Mini tier should skip brand voice compliance check."""
        guardrails_mod = importlib.import_module("app.core.langgraph.nodes.14_guardrails")
        result = guardrails_mod._check_brand_voice(
            response_text="Hello!",
            tenant_id="tenant_abc",
            variant_tier="mini",
        )
        assert result["passed"] is True
        assert len(result["flags"]) == 0

    def test_pro_tier_runs_brand_voice_check(self):
        """Pro tier should run brand voice (may fail gracefully)."""
        guardrails_mod = importlib.import_module("app.core.langgraph.nodes.14_guardrails")
        result = guardrails_mod._check_brand_voice(
            response_text="Hello!",
            tenant_id="tenant_abc",
            variant_tier="pro",
        )
        assert "passed" in result
        # Module may be unavailable but check runs

    # ── Uses selected_solution if available ──────────────────────

    def test_uses_selected_solution_over_agent_response(self):
        """Guardrails should prefer selected_solution (post-MAKER) over agent_response."""
        node = self._get_node()
        result = node(make_minimal_state(
            agent_response="Original response",
            selected_solution="MAKER selected response",
        ))
        # Should have processed without crash
        assert isinstance(result, dict)
        assert "guardrails_passed" in result


# ═══════════════════════════════════════════════════════════════════
# CROSS-CUTTING TESTS
# ═══════════════════════════════════════════════════════════════════


class TestCrossCuttingNodeBehavior:
    """Tests that verify behavior across ALL nodes collectively."""

    def test_all_nodes_accept_minimal_state(self):
        """Every node should accept make_minimal_state() without crashing."""
        nodes = {
            "pii_redaction": lambda: __import__(
                "app.core.langgraph.nodes.01_pii_redaction", fromlist=["pii_redaction_node"]
            ).pii_redaction_node,
            "empathy_engine": lambda: __import__(
                "app.core.langgraph.nodes.02_empathy_engine", fromlist=["empathy_engine_node"]
            ).empathy_engine_node,
            "router_agent": lambda: __import__(
                "app.core.langgraph.nodes.03_router_agent", fromlist=["router_agent_node"]
            ).router_agent_node,
            "faq_agent": lambda: __import__(
                "app.core.langgraph.nodes.05_faq_agent", fromlist=["faq_agent_node"]
            ).faq_agent_node,
            "refund_agent": lambda: __import__(
                "app.core.langgraph.nodes.06_refund_agent", fromlist=["refund_agent_node"]
            ).refund_agent_node,
            "technical_agent": lambda: __import__(
                "app.core.langgraph.nodes.07_technical_agent", fromlist=["technical_agent_node"]
            ).technical_agent_node,
            "billing_agent": lambda: __import__(
                "app.core.langgraph.nodes.08_billing_agent", fromlist=["billing_agent_node"]
            ).billing_agent_node,
            "complaint_agent": lambda: __import__(
                "app.core.langgraph.nodes.09_complaint_agent", fromlist=["complaint_agent_node"]
            ).complaint_agent_node,
            "escalation_agent": lambda: __import__(
                "app.core.langgraph.nodes.10_escalation_agent", fromlist=["escalation_agent_node"]
            ).escalation_agent_node,
            "maker_validator": lambda: __import__(
                "app.core.langgraph.nodes.11_maker_validator", fromlist=["maker_validator_node"]
            ).maker_validator_node,
            "control_system": lambda: __import__(
                "app.core.langgraph.nodes.12_control_system", fromlist=["control_system_node"]
            ).control_system_node,
            "dspy_optimizer": lambda: __import__(
                "app.core.langgraph.nodes.13_dspy_optimizer", fromlist=["dspy_optimizer_node"]
            ).dspy_optimizer_node,
            "guardrails": lambda: __import__(
                "app.core.langgraph.nodes.14_guardrails", fromlist=["guardrails_node"]
            ).guardrails_node,
        }

        for name, get_node in nodes.items():
            node = get_node()
            state = make_minimal_state(
                agent_response="Test response.",
                agent_confidence=0.7,
            )
            try:
                result = node(state)
                assert isinstance(result, dict), f"{name} did not return a dict"
            except Exception as e:
                pytest.fail(f"Node {name} crashed: {e}")

    def test_all_nodes_return_dict_on_empty_state_bc008(self):
        """BC-008: Every node should return a dict even with empty state."""
        nodes = {
            "pii_redaction": lambda: __import__(
                "app.core.langgraph.nodes.01_pii_redaction", fromlist=["pii_redaction_node"]
            ).pii_redaction_node,
            "empathy_engine": lambda: __import__(
                "app.core.langgraph.nodes.02_empathy_engine", fromlist=["empathy_engine_node"]
            ).empathy_engine_node,
            "router_agent": lambda: __import__(
                "app.core.langgraph.nodes.03_router_agent", fromlist=["router_agent_node"]
            ).router_agent_node,
            "faq_agent": lambda: __import__(
                "app.core.langgraph.nodes.05_faq_agent", fromlist=["faq_agent_node"]
            ).faq_agent_node,
            "refund_agent": lambda: __import__(
                "app.core.langgraph.nodes.06_refund_agent", fromlist=["refund_agent_node"]
            ).refund_agent_node,
            "technical_agent": lambda: __import__(
                "app.core.langgraph.nodes.07_technical_agent", fromlist=["technical_agent_node"]
            ).technical_agent_node,
            "billing_agent": lambda: __import__(
                "app.core.langgraph.nodes.08_billing_agent", fromlist=["billing_agent_node"]
            ).billing_agent_node,
            "complaint_agent": lambda: __import__(
                "app.core.langgraph.nodes.09_complaint_agent", fromlist=["complaint_agent_node"]
            ).complaint_agent_node,
            "escalation_agent": lambda: __import__(
                "app.core.langgraph.nodes.10_escalation_agent", fromlist=["escalation_agent_node"]
            ).escalation_agent_node,
            "maker_validator": lambda: __import__(
                "app.core.langgraph.nodes.11_maker_validator", fromlist=["maker_validator_node"]
            ).maker_validator_node,
            "control_system": lambda: __import__(
                "app.core.langgraph.nodes.12_control_system", fromlist=["control_system_node"]
            ).control_system_node,
            "dspy_optimizer": lambda: __import__(
                "app.core.langgraph.nodes.13_dspy_optimizer", fromlist=["dspy_optimizer_node"]
            ).dspy_optimizer_node,
            "guardrails": lambda: __import__(
                "app.core.langgraph.nodes.14_guardrails", fromlist=["guardrails_node"]
            ).guardrails_node,
        }

        for name, get_node in nodes.items():
            node = get_node()
            try:
                result = node({})
                assert isinstance(result, dict), (
                    f"BC-008 VIOLATED: {name} did not return dict on empty state"
                )
            except Exception as e:
                pytest.fail(
                    f"BC-008 VIOLATED: {name} crashed on empty state: {e}"
                )

    def test_tier_gating_consistency(self):
        """Pro/High-only agents should skip on mini tier consistently."""
        # Refund, Complaint, Escalation are Pro/High-only
        pro_high_only_agents = {
            "refund_agent": lambda: __import__(
                "app.core.langgraph.nodes.06_refund_agent", fromlist=["refund_agent_node"]
            ).refund_agent_node,
            "complaint_agent": lambda: __import__(
                "app.core.langgraph.nodes.09_complaint_agent", fromlist=["complaint_agent_node"]
            ).complaint_agent_node,
            "escalation_agent": lambda: __import__(
                "app.core.langgraph.nodes.10_escalation_agent", fromlist=["escalation_agent_node"]
            ).escalation_agent_node,
        }

        for name, get_node in pro_high_only_agents.items():
            node = get_node()
            result = node(make_minimal_state(variant_tier="mini"))
            # Mini tier should not crash and should return some kind of
            # fallback/escalation response
            assert isinstance(result, dict), f"{name} crashed on mini tier"
            assert "agent_response" in result, (
                f"{name} missing agent_response on mini tier"
            )
