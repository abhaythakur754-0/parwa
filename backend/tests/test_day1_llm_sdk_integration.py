"""
PARWA LLM/SDK Integration Tests — Day 1

Tests the LLM integration layer end-to-end, verifying:
  1. ZAI SDK client creates, calls, and falls back correctly
  2. AI Service routes to correct models per variant tier
  3. Classification uses LLM with rule-based fallback
  4. Response generation uses correct prompts + sentiment
  5. Variant Pipeline Bridge routes through Mini/Pro/High correctly
  6. Smart Router selects models, tracks health, handles failover

KEY PRINCIPLES:
  - "ZAI SDK is not an API key — use SDK instead"
  - Mock ALL external LLM API calls (ZAI SDK, OpenAI, etc.)
  - Test the LOGIC and INTEGRATION, not the actual AI output
  - Verify correct parameters are passed to SDK calls
  - Verify fallback chains work (BC-008)
  - Use MagicMock for ZAI SDK client

Building Codes: BC-001 (tenant_id), BC-007 (AI through Smart Router),
                BC-008 (never crash), BC-012 (UTC timestamps)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import importlib

import pytest


# ══════════════════════════════════════════════════════════════════
# MODULE-LEVEL HELPERS — digit-prefixed modules need importlib
# ══════════════════════════════════════════════════════════════════

_router_agent_mod = importlib.import_module(
    "app.core.langgraph.nodes.03_router_agent"
)
_fallback_classify_intent = _router_agent_mod._fallback_classify_intent
_fallback_estimate_complexity = _router_agent_mod._fallback_estimate_complexity
_fallback_extract_signals = _router_agent_mod._fallback_extract_signals
_select_model_tier = _router_agent_mod._select_model_tier
_build_technique_stack = _router_agent_mod._build_technique_stack
router_agent_node = _router_agent_mod.router_agent_node
_DEFAULT_STATE = _router_agent_mod._DEFAULT_STATE


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_zai_client_singleton():
    """Reset the ZAI client singleton between tests to avoid state leakage."""
    from app.services.jarvis_agents.zai_client import ZAIClient
    ZAIClient._instance = None
    ZAIClient._sdk = None
    ZAIClient._initialized = False
    yield
    ZAIClient._instance = None
    ZAIClient._sdk = None
    ZAIClient._initialized = False


@pytest.fixture
def mock_zai_sdk():
    """Create a mock z-ai-web-dev-sdk ZAI instance.

    This mocks the SDK itself (not an API key!) and provides
    a .chat.completions.create() async method that returns
    realistic chat completion responses.
    """
    sdk = MagicMock()
    sdk.chat = MagicMock()
    sdk.chat.completions = MagicMock()
    sdk.chat.completions.create = AsyncMock()
    return sdk


def _make_completion(content: str, model: str = "zai-default") -> MagicMock:
    """Build a mock chat completion response object."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.role = "assistant"
    completion = MagicMock()
    completion.choices = [choice]
    completion.model = model
    completion.usage = MagicMock()
    completion.usage.total_tokens = 42
    return completion


@pytest.fixture
def sample_context():
    """Sample context dict for agent calls."""
    return {
        "alert_type": "ticket_volume_spike",
        "severity": "high",
        "ticket_ids": ["T-001", "T-002"],
        "at_risk_count": 5,
        "message": "Ticket volume 3x normal",
    }


# ══════════════════════════════════════════════════════════════════
# 1. TestZaiClientIntegration
# ══════════════════════════════════════════════════════════════════


class TestZaiClientIntegration:
    """Test the ZAI SDK client wrapper — the LLM brain behind Jarvis."""

    def test_singleton_pattern(self):
        """ZAIClient is a singleton — same instance every time."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client_a = ZAIClient()
        client_b = ZAIClient()
        assert client_a is client_b

    def test_sdk_lazy_initialization_no_sdk(self):
        """When ZAI SDK can't be imported, _ensure_sdk returns False."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        # Without the real SDK installed, _ensure_sdk should return False
        # but should NOT crash (BC-008)
        result = client._ensure_sdk()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_chat_async_with_mock_sdk(self, mock_zai_sdk):
        """chat_async uses the ZAI SDK correctly and parses JSON response."""
        from app.services.jarvis_agents.zai_client import ZAIClient, AGENT_SYSTEM_PROMPTS

        # Arrange: wire in the mock SDK
        llm_response = json.dumps({
            "agent": "escalation_agent",
            "reasoning": "High volume spike detected",
            "urgency": "high",
            "parameters": {"scope": "all_urgent"},
        })
        mock_zai_sdk.chat.completions.create.return_value = _make_completion(llm_response)

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        # Act
        result = await client.chat_async(
            agent_type="command_router",
            user_message="Ticket volume is 3x normal",
            context={"alert_type": "ticket_volume_spike", "severity": "high"},
        )

        # Assert: SDK was called with correct structure
        mock_zai_sdk.chat.completions.create.assert_called_once()
        call_kwargs = mock_zai_sdk.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][0]

        # Verify system prompt matches agent_type
        system_msg = [m for m in messages if m["role"] == "system"][0]
        assert system_msg["content"] == AGENT_SYSTEM_PROMPTS["command_router"]

        # Verify user message includes context
        user_msg = [m for m in messages if m["role"] == "user"][0]
        assert "ticket_volume_spike" in user_msg["content"]
        assert "3x normal" in user_msg["content"]

        # Verify temperature is low (structured decisions)
        assert call_kwargs.kwargs.get("temperature", 0.3) == 0.3

        # Verify response is parsed correctly
        assert result["agent"] == "escalation_agent"
        assert result["urgency"] == "high"
        assert result["_source"] == "zai_llm"
        assert result["_agent_type"] == "command_router"
        assert "_parsed_at" in result

    @pytest.mark.asyncio
    async def test_chat_async_includes_context_in_message(self, mock_zai_sdk):
        """Context dict is serialized and prepended to the user message."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        mock_zai_sdk.chat.completions.create.return_value = _make_completion('{"agent":"faq"}')

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        context = {"quality_score": 0.45, "drift_status": "detected"}
        await client.chat_async(
            agent_type="quality_recovery_agent",
            user_message="What should we do about the quality drop?",
            context=context,
        )

        call_args = mock_zai_sdk.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
        user_msg = [m for m in messages if m["role"] == "user"][0]

        # Context should be JSON-serialized and prepended
        assert "quality_score" in user_msg["content"]
        assert "0.45" in user_msg["content"]

    @pytest.mark.asyncio
    async def test_chat_async_retries_on_failure(self, mock_zai_sdk):
        """chat_async retries up to max_retries times on SDK errors."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        # Fail twice, then succeed
        mock_zai_sdk.chat.completions.create.side_effect = [
            Exception("SDK connection error"),
            Exception("SDK timeout"),
            _make_completion('{"agent":"faq"}'),
        ]

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        with patch("app.services.jarvis_agents.zai_client.time.sleep"):
            result = await client.chat_async(
                agent_type="command_router",
                user_message="test",
                max_retries=3,
            )

        assert result["agent"] == "faq"
        assert result["_source"] == "zai_llm"
        assert mock_zai_sdk.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_chat_async_fallback_to_rule_based(self, mock_zai_sdk):
        """When SDK fails all retries, falls back to rule-based (BC-008)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        mock_zai_sdk.chat.completions.create.side_effect = Exception("SDK permanently down")

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        with patch("app.services.jarvis_agents.zai_client.time.sleep"):
            result = await client.chat_async(
                agent_type="command_router",
                user_message="Volume spike detected",
                context={"alert_type": "ticket_volume_spike", "severity": "high"},
                max_retries=2,
            )

        # Should fall back to rule-based response
        assert result["_source"] == "rule_based_fallback"
        assert result["agent"] == "escalation_agent"  # volume spike → escalation
        assert result["urgency"] == "high"

    @pytest.mark.asyncio
    async def test_chat_async_no_sdk_falls_back_immediately(self):
        """When _sdk is None and _ensure_sdk returns False, uses rule-based."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        client._sdk = None
        client._initialized = True

        result = await client.chat_async(
            agent_type="sla_protection_agent",
            user_message="SLA breach imminent",
            context={"at_risk_count": 12},
        )

        assert result["_source"] == "rule_based_fallback"
        assert result["action"] == "protect_sla"
        assert result["at_risk_count"] == 12

    def test_rule_based_fallback_all_agent_types(self):
        """Every agent type has a rule-based fallback (BC-008)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()

        agent_types = [
            "command_router", "escalation_agent", "sla_protection_agent",
            "quality_recovery_agent", "reassignment_agent", "notification_agent",
            "co_pilot", "pipeline_query_agent",
        ]

        for agent_type in agent_types:
            result = client._rule_based_fallback(
                agent_type=agent_type,
                user_message="test message",
                context={},
            )
            assert result.get("_source") == "rule_based_fallback"
            assert "_agent_type" in result
            assert "_parsed_at" in result
            # Every fallback must return a decision
            assert "agent" in result or "action" in result or "suggestion" in result

    def test_rule_based_fallback_unknown_agent_type(self):
        """Unknown agent type gets a safe no-action fallback."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        result = client._rule_based_fallback(
            agent_type="nonexistent_agent",
            user_message="test",
        )
        assert result["action"] == "no_action"

    def test_parse_llm_response_json(self):
        """_parse_llm_response correctly parses valid JSON."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        content = '{"agent": "faq", "reasoning": "Simple question"}'
        result = client._parse_llm_response(content, "command_router")

        assert result["agent"] == "faq"
        assert result["reasoning"] == "Simple question"
        assert result["_source"] == "zai_llm"
        assert result["_agent_type"] == "command_router"

    def test_parse_llm_response_markdown_code_block(self):
        """_parse_llm_response extracts JSON from markdown code blocks."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        content = '```json\n{"agent": "technical", "urgency": "medium"}\n```'
        result = client._parse_llm_response(content, "command_router")

        assert result["agent"] == "technical"
        assert result["_source"] == "zai_llm"

    def test_parse_llm_response_unparseable(self):
        """_parse_llm_response wraps unparseable text in a fallback structure."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        content = "I think you should escalate this to a human agent"
        result = client._parse_llm_response(content, "command_router")

        assert result["_source"] == "zai_llm_unparsed"
        assert result["raw_response"] == content
        assert "reasoning" in result

    def test_sync_chat_wrapper(self, mock_zai_sdk):
        """The synchronous chat() wrapper works for non-async callers."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        llm_response = json.dumps({"agent": "faq", "reasoning": "test"})
        mock_zai_sdk.chat.completions.create.return_value = _make_completion(llm_response)

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        result = client.chat(
            agent_type="command_router",
            user_message="test sync call",
        )

        assert result["agent"] == "faq"
        assert result["_source"] == "zai_llm"


# ══════════════════════════════════════════════════════════════════
# 2. TestAIServiceRouting
# ══════════════════════════════════════════════════════════════════


class TestAIServiceRouting:
    """Test that AI Service routes to correct models based on variant tier."""

    def test_mini_parwa_uses_lighter_model_tier(self):
        """Mini PARWA should never use the 'heavy' model tier."""
        # High complexity + bad sentiment would normally be "heavy"
        model_tier = _select_model_tier(
            complexity_score=0.9,
            sentiment_score=0.1,  # very negative
            variant_tier="mini",
        )
        # Mini tier caps at medium for cost control
        assert model_tier == "medium"
        assert model_tier != "heavy"

    def test_parwa_high_uses_heavy_model_for_complex(self):
        """PARWA High can use 'heavy' tier for complex/negative queries."""
        model_tier = _select_model_tier(
            complexity_score=0.8,
            sentiment_score=0.1,
            variant_tier="high",
        )
        assert model_tier == "heavy"

    def test_pro_uses_medium_for_average_complexity(self):
        """PARWA Pro uses 'medium' for moderate complexity."""
        model_tier = _select_model_tier(
            complexity_score=0.5,
            sentiment_score=0.5,
            variant_tier="pro",
        )
        assert model_tier == "medium"

    def test_low_complexity_uses_light_tier(self):
        """Simple queries always get light tier regardless of variant."""
        for tier in ("mini", "pro", "high"):
            model_tier = _select_model_tier(
                complexity_score=0.1,
                sentiment_score=0.8,
                variant_tier=tier,
            )
            assert model_tier == "light"

    def test_negative_sentiment_upgrades_tier(self):
        """Very negative sentiment (<= 0.2) triggers heavier tier."""
        # Low complexity + very negative sentiment → heavy for pro/high
        model_tier_pro = _select_model_tier(
            complexity_score=0.1,
            sentiment_score=0.15,
            variant_tier="pro",
        )
        model_tier_high = _select_model_tier(
            complexity_score=0.1,
            sentiment_score=0.15,
            variant_tier="high",
        )

        assert model_tier_pro == "heavy"
        assert model_tier_high == "heavy"

    def test_variant_config_model_limits(self):
        """Each variant has appropriate max_tokens and pipeline timeouts."""
        from app.core.langgraph.config import VARIANT_CONFIG

        mini = VARIANT_CONFIG["mini"]
        pro = VARIANT_CONFIG["pro"]
        high = VARIANT_CONFIG["high"]

        # Timeout and token limits scale with tier
        assert mini["pipeline_timeout_seconds"] <= pro["pipeline_timeout_seconds"]
        assert pro["pipeline_timeout_seconds"] <= high["pipeline_timeout_seconds"]
        assert mini["max_tokens_per_response"] <= pro["max_tokens_per_response"]
        assert pro["max_tokens_per_response"] <= high["max_tokens_per_response"]

    def test_ai_service_process_message_returns_result(self):
        """AI Service process_message returns AIProcessResult with metadata."""
        from app.services.ai_service import process_message, AIProcessRequest

        request = AIProcessRequest(
            user_message="I'm having trouble with my subscription",
            session_id="sess-123",
            user_id="user-456",
            company_id="comp-789",
            variant_type="parwa",
        )

        # Mock sentiment and knowledge since those may not be available
        with patch("app.services.ai_service._analyze_sentiment", return_value=None), \
             patch("app.services.ai_service._search_knowledge", return_value=[]), \
             patch("app.services.ai_service._get_trained_responses", return_value=None), \
             patch("app.services.ai_service._evaluate_escalation", return_value=None):

            result = process_message(request)

        assert result.tone_recommendation == "standard"
        assert result.knowledge_used == []
        assert result.escalation_triggered is False

    def test_ai_service_frustrated_user_gets_deescalation_tone(self):
        """High frustration score triggers de-escalation tone recommendation."""
        from app.services.ai_service import process_message, AIProcessRequest

        frustrated_sentiment = {
            "frustration_score": 85,
            "emotion": "angry",
            "urgency_level": "high",
            "tone_recommendation": "de-escalation",
            "conversation_trend": "worsening",
        }

        request = AIProcessRequest(
            user_message="This is terrible! I want a refund NOW!",
            session_id="sess-frust",
            user_id="user-angry",
            company_id="comp-789",
        )

        with patch("app.services.ai_service._analyze_sentiment", return_value=frustrated_sentiment), \
             patch("app.services.ai_service._search_knowledge", return_value=[]), \
             patch("app.services.ai_service._get_trained_responses", return_value=None), \
             patch("app.services.ai_service._evaluate_escalation", return_value=None):

            result = process_message(request)

        assert result.tone_recommendation == "de-escalation"
        assert result.sentiment["frustration_score"] == 85

    def test_provider_failover_on_primary_failure(self):
        """When primary LLM provider fails, fallback chain activates."""
        from app.core.model_failover import FailoverManager, FailoverChainExecutor, FailoverReason

        manager = FailoverManager()
        executor = FailoverChainExecutor(manager)

        # Primary provider fails, secondary succeeds
        call_count = {"attempts": 0}

        def mock_call_fn(provider, model_id):
            call_count["attempts"] += 1
            if call_count["attempts"] == 1:
                raise ConnectionError("Primary provider down")
            return {"content": "Response from backup", "latency_ms": 100}

        chain = [("cerebras", "llama-3.1-8b"), ("groq", "llama-3.1-8b")]
        result = executor.execute_with_failover(
            company_id="comp-123",
            chain=chain,
            call_fn=mock_call_fn,
            max_retries=1,
        )

        assert result["content"] == "Response from backup"
        assert result.get("_failover_used") is True or call_count["attempts"] > 1

    def test_all_providers_fail_returns_graceful_response(self):
        """When ALL providers fail, returns graceful degradation (BC-008)."""
        from app.core.model_failover import FailoverManager, FailoverChainExecutor

        manager = FailoverManager()
        executor = FailoverChainExecutor(manager)

        def always_fails(provider, model_id):
            raise ConnectionError("All providers down")

        chain = [("cerebras", "llama-3.1-8b")]
        result = executor.execute_with_failover(
            company_id="comp-123",
            chain=chain,
            call_fn=always_fails,
            max_retries=1,
        )

        # BC-008: Never crash — always return something usable
        assert "content" in result or "text" in result
        assert result.get("_all_providers_failed") is True


# ══════════════════════════════════════════════════════════════════
# 3. TestLLMClassificationIntegration
# ══════════════════════════════════════════════════════════════════


class TestLLMClassificationIntegration:
    """Test that classification uses LLM with rule-based fallback."""

    def test_fallback_classify_intent_refund(self):
        """Keyword-based fallback correctly identifies refund intent."""
        assert _fallback_classify_intent("I want a refund for my order") == "refund"
        assert _fallback_classify_intent("Money back please") == "refund"
        assert _fallback_classify_intent("I want to cancel order and get refund") == "refund"

    def test_fallback_classify_intent_billing(self):
        """Keyword-based fallback identifies billing intent."""
        assert _fallback_classify_intent("My bill is incorrect") == "billing"
        assert _fallback_classify_intent("I was overcharged on my invoice") == "billing"

    def test_fallback_classify_intent_technical(self):
        """Keyword-based fallback identifies technical intent."""
        assert _fallback_classify_intent("The app is not working") == "technical"
        assert _fallback_classify_intent("I can't access my account, login issue") == "technical"

    def test_fallback_classify_intent_escalation(self):
        """Keyword-based fallback identifies escalation intent."""
        assert _fallback_classify_intent("I want to speak to a manager") == "escalation"
        assert _fallback_classify_intent("Let me talk to a real person") == "escalation"

    def test_fallback_classify_intent_faq(self):
        """Keyword-based fallback identifies FAQ/general intent."""
        assert _fallback_classify_intent("How do I reset my password?") == "faq"
        assert _fallback_classify_intent("What is this?") == "faq"
        # Note: "return" keyword matches refund intent, so "return policy" → refund
        assert _fallback_classify_intent("What is your return policy?") == "refund"

    def test_fallback_classify_intent_complaint(self):
        """Keyword-based fallback identifies complaint intent."""
        assert _fallback_classify_intent("This is terrible service, I'm furious") == "complaint"
        assert _fallback_classify_intent("I'm filing a complaint") == "complaint"

    def test_fallback_classify_intent_general_default(self):
        """Ambiguous messages default to 'general' intent."""
        assert _fallback_classify_intent("Hello there") == "general"
        assert _fallback_classify_intent("Thanks") == "general"

    def test_router_agent_node_uses_fallback_when_llm_unavailable(self):
        """Router agent falls back to keyword classification when LLM fails."""
        # With classification_engine unavailable (ImportError),
        # it should use _fallback_classify_intent
        state = {
            "pii_redacted_message": "I want a refund for my damaged product",
            "tenant_id": "tenant-123",
            "variant_tier": "mini",
            "sentiment_score": 0.3,
            "customer_tier": "free",
        }

        result = router_agent_node(state)

        assert result["intent"] == "refund"
        assert result["target_agent"] is not None
        assert 0.0 <= result["complexity_score"] <= 1.0
        assert result["model_tier"] in ("light", "medium", "heavy")

    def test_router_agent_safe_defaults_on_total_failure(self):
        """Router agent returns safe defaults if everything fails (BC-008)."""
        # Pass empty/broken state
        result = router_agent_node({})

        assert "intent" in result
        assert "complexity_score" in result
        assert "target_agent" in result
        assert "model_tier" in result
        assert "technique_stack" in result

    def test_complexity_estimation_scales_with_length(self):
        """Longer messages get higher complexity scores."""
        short = "Hi there"
        medium = (
            "I have a question about my subscription billing "
            "and I need to understand the charges that were applied"
        )
        long_msg = (
            "I'm experiencing multiple issues with my account. "
            "First, I can't log in, and additionally my subscription "
            "shows the wrong plan. Furthermore, I was charged twice "
            "last month. Also, the app crashes every time I open settings. "
            "This is complicated and I need all of these resolved."
        )

        c_short = _fallback_estimate_complexity(short)
        c_medium = _fallback_estimate_complexity(medium)
        c_long = _fallback_estimate_complexity(long_msg)

        assert c_short <= c_medium
        assert c_medium <= c_long
        assert c_short < c_long  # At least short vs long must differ

    def test_signal_extraction_from_message(self):
        """Signal extraction pulls structured features from messages."""
        signals = _fallback_extract_signals(
            "Can you help me with 3 items: order #12345? Also https://example.com/faq"
        )

        assert signals["has_question"] is True
        assert signals["contains_numbers"] is True
        assert signals["contains_url"] is True
        assert signals["word_count"] > 5

    def test_technique_stack_mini_tier(self):
        """Mini tier only gets Tier 1 techniques."""
        from app.core.langgraph.config import TECHNIQUE_TIER_ACCESS

        available = TECHNIQUE_TIER_ACCESS["mini"]["techniques"]
        stack = _build_technique_stack(
            variant_tier="mini",
            intent="faq",
            complexity_score=0.3,
            signals={},
        )

        # All techniques in stack must be available for mini tier
        for technique in stack:
            assert technique in available

    def test_technique_stack_pro_adds_advanced(self):
        """Pro tier can add CoT, ReAct, etc. for complex queries."""
        stack = _build_technique_stack(
            variant_tier="pro",
            intent="technical",
            complexity_score=0.8,
            signals={"multi_step": True},
        )

        # Pro should get chain_of_thought for high complexity
        assert "chain_of_thought" in stack
        # Technical intent should get react
        assert "react" in stack

    def test_technique_stack_high_gets_tree_of_thoughts(self):
        """High tier can add tree_of_thoughts for very complex queries."""
        stack = _build_technique_stack(
            variant_tier="high",
            intent="complaint",
            complexity_score=0.9,
            signals={"multi_step": True},
        )

        assert "tree_of_thoughts" in stack
        assert "reverse_thinking" in stack  # complaint intent


# ══════════════════════════════════════════════════════════════════
# 4. TestLLMResponseGeneration
# ══════════════════════════════════════════════════════════════════


class TestLLMResponseGeneration:
    """Test response generation uses correct prompts + sentiment integration."""

    def test_enrich_system_prompt_deescalation_tone(self):
        """De-escalation tone adds extreme empathy guidance."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a customer care agent.",
            sentiment_data={"frustration_score": 85, "emotion": "angry",
                            "urgency_level": "high", "conversation_trend": "worsening"},
            tone_recommendation="de-escalation",
        )

        assert "CRITICAL" in result
        assert "empathy" in result.lower()
        assert "frustrat" in result.lower()

    def test_enrich_system_prompt_empathetic_tone(self):
        """Empathetic tone adds understanding guidance."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data={"frustration_score": 40},
            tone_recommendation="empathetic",
        )

        assert "empathetic" in result.lower()
        assert "understanding" in result.lower()

    def test_enrich_system_prompt_urgent_tone(self):
        """Urgent tone adds direct/efficient guidance."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data={"frustration_score": 30, "urgency_level": "high"},
            tone_recommendation="urgent",
        )

        assert "direct" in result.lower() or "efficient" in result.lower()

    def test_enrich_system_prompt_standard_tone(self):
        """Standard tone adds professional/friendly guidance."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data=None,
            tone_recommendation="standard",
        )

        assert "professional" in result.lower() or "friendly" in result.lower()

    def test_enrich_system_prompt_with_knowledge_snippets(self):
        """Knowledge snippets are injected into the prompt."""
        from app.services.ai_service import enrich_system_prompt

        snippets = [
            "Refund policy: Full refund within 30 days",
            "Return process: Contact support with order ID",
        ]

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data=None,
            tone_recommendation="standard",
            knowledge_snippets=snippets,
        )

        assert "Refund policy" in result
        assert "Return process" in result
        assert "Knowledge Base" in result

    def test_enrich_system_prompt_with_escalation(self):
        """Escalation status is injected into the prompt."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data=None,
            tone_recommendation="standard",
            is_escalated=True,
        )

        assert "ESCALATION ACTIVE" in result
        assert "human agent" in result.lower()

    def test_enrich_system_prompt_with_trained_response(self):
        """Trained response hints are injected into the prompt."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="You are a helper.",
            sentiment_data=None,
            tone_recommendation="standard",
            trained_response="For refund requests, direct them to /refunds",
        )

        assert "Trained Response Available" in result
        assert "/refunds" in result

    def test_sentiment_context_injection_high_frustration(self):
        """High frustration triggers ACTION REQUIRED in prompt."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="Base",
            sentiment_data={
                "frustration_score": 75,
                "emotion": "furious",
                "urgency_level": "critical",
                "conversation_trend": "worsening",
            },
            tone_recommendation="de-escalation",
        )

        assert "ACTION REQUIRED" in result
        assert "75/100" in result

    def test_sentiment_context_moderate_frustration(self):
        """Moderate frustration triggers CAUTION in prompt."""
        from app.services.ai_service import enrich_system_prompt

        result = enrich_system_prompt(
            base_prompt="Base",
            sentiment_data={
                "frustration_score": 45,
                "emotion": "annoyed",
                "urgency_level": "medium",
                "conversation_trend": "stable",
            },
            tone_recommendation="empathetic",
        )

        assert "CAUTION" in result
        assert "45/100" in result

    def test_llm_gateway_returns_empty_on_failure(self):
        """LLM Gateway never crashes — returns LLMResponse with error on failure."""
        from app.core.llm_gateway import LLMGateway, LLMProvider

        gateway = LLMGateway(provider=LLMProvider.LITELLM)
        # No real API keys set, should fail gracefully

        result = asyncio.get_event_loop().run_until_complete(
            gateway.generate(
                system_prompt="test",
                user_message="test",
                technique_id="test_technique",
                company_id="comp-123",
            )
        )

        # BC-008: Never crash, return usable response
        assert result.error is not None or result.text == ""

    def test_llm_gateway_json_parse_failure(self):
        """LLM Gateway generate_json returns {} on parse failure."""
        from app.core.llm_gateway import LLMGateway, LLMResponse

        gateway = LLMGateway()

        # Mock generate to return non-JSON
        with patch.object(gateway, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(text="This is not JSON at all")
            result = asyncio.get_event_loop().run_until_complete(
                gateway.generate_json("sys", "user", company_id="c1")
            )

        assert result == {}


# ══════════════════════════════════════════════════════════════════
# 5. TestVariantPipelineBridge
# ══════════════════════════════════════════════════════════════════


class TestVariantPipelineBridge:
    """Test variant pipeline bridge routes through correct pipelines."""

    def test_has_variant_tier_in_context_valid(self):
        """Valid variant_tier values return True."""
        from app.core.variant_pipeline_bridge import has_variant_tier_in_context

        assert has_variant_tier_in_context({"variant_tier": "mini_parwa"}) is True
        assert has_variant_tier_in_context({"variant_tier": "parwa"}) is True
        assert has_variant_tier_in_context({"variant_tier": "parwa_high"}) is True

    def test_has_variant_tier_in_context_invalid(self):
        """Invalid or missing variant_tier returns False."""
        from app.core.variant_pipeline_bridge import has_variant_tier_in_context

        assert has_variant_tier_in_context({}) is False
        assert has_variant_tier_in_context({"variant_tier": None}) is False
        assert has_variant_tier_in_context({"variant_tier": "unknown"}) is False
        assert has_variant_tier_in_context({"variant_tier": ""}) is False

    def test_pipeline_result_serialization(self):
        """PipelineResult.to_dict() includes all expected fields."""
        from app.core.variant_pipeline_bridge import PipelineResult

        result = PipelineResult(
            response_text="Your refund is being processed.",
            variant_tier="parwa",
            industry="ecommerce",
            pipeline_status="completed",
            quality_score=0.92,
            total_latency_ms=450.0,
            billing_tokens=150,
            steps_completed=["classify", "generate", "format"],
            technique_used="chain_of_thought",
            emergency_flag=False,
            empathy_score=0.85,
            classification_intent="refund",
        )

        d = result.to_dict()
        assert d["variant_tier"] == "parwa"
        assert d["pipeline_status"] == "completed"
        assert d["quality_score"] == 0.92
        assert d["billing_tokens"] == 150
        assert "classify" in d["steps_completed"]
        assert d["technique_used"] == "chain_of_thought"
        assert d["classification_intent"] == "refund"

    @pytest.mark.asyncio
    async def test_run_pipeline_routes_to_mini_parwa(self):
        """_run_pipeline with mini_parwa tier calls _run_mini_parwa."""
        from app.core.variant_pipeline_bridge import _run_pipeline

        with patch(
            "app.core.variant_pipeline_bridge._run_mini_parwa",
            new_callable=AsyncMock,
        ) as mock_mini:
            mock_mini.return_value = MagicMock(
                response_text="Mini response",
                variant_tier="mini_parwa",
                pipeline_status="completed",
            )

            await _run_pipeline(
                variant_tier="mini_parwa",
                query="Simple question",
                company_id="comp-123",
                industry="general",
            )

            mock_mini.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_routes_to_parwa(self):
        """_run_pipeline with parwa tier calls _run_parwa."""
        from app.core.variant_pipeline_bridge import _run_pipeline

        with patch(
            "app.core.variant_pipeline_bridge._run_parwa",
            new_callable=AsyncMock,
        ) as mock_parwa:
            mock_parwa.return_value = MagicMock(
                response_text="Pro response",
                variant_tier="parwa",
                pipeline_status="completed",
            )

            await _run_pipeline(
                variant_tier="parwa",
                query="Complex issue",
                company_id="comp-123",
                industry="saas",
            )

            mock_parwa.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_routes_to_parwa_high(self):
        """_run_pipeline with parwa_high tier calls _run_parwa_high."""
        from app.core.variant_pipeline_bridge import _run_pipeline

        with patch(
            "app.core.variant_pipeline_bridge._run_parwa_high",
            new_callable=AsyncMock,
        ) as mock_high:
            mock_high.return_value = MagicMock(
                response_text="High response",
                variant_tier="parwa_high",
                pipeline_status="completed",
            )

            await _run_pipeline(
                variant_tier="parwa_high",
                query="Critical issue",
                company_id="comp-123",
                industry="ecommerce",
            )

            mock_high.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_unknown_tier_defaults_to_mini(self):
        """Unknown variant tier defaults to mini_parwa (safest)."""
        from app.core.variant_pipeline_bridge import _run_pipeline

        with patch(
            "app.core.variant_pipeline_bridge._run_mini_parwa",
            new_callable=AsyncMock,
        ) as mock_mini:
            mock_mini.return_value = MagicMock(
                response_text="Fallback response",
                variant_tier="mini_parwa",
                pipeline_status="completed",
            )

            await _run_pipeline(
                variant_tier="unknown_tier",
                query="Test",
                company_id="comp-123",
                industry="general",
            )

            mock_mini.assert_called_once()

    @pytest.mark.asyncio
    async def test_customer_care_message_returns_pipeline_result(self):
        """process_customer_care_message returns PipelineResult even on error (BC-008)."""
        from app.core.variant_pipeline_bridge import process_customer_care_message

        with patch(
            "app.core.variant_pipeline_bridge._run_pipeline",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = Exception("Pipeline explosion!")

            result = await process_customer_care_message(
                query="Help me",
                company_id="comp-123",
                session_context={"variant_tier": "mini_parwa", "industry": "general"},
            )

        # BC-008: Never crash
        assert result.pipeline_status == "failed"
        assert "apologize" in result.response_text.lower() or "trouble" in result.response_text.lower()

    @pytest.mark.asyncio
    async def test_onboarding_message_returns_pipeline_result(self):
        """process_onboarding_message returns PipelineResult even on error (BC-008)."""
        from app.core.variant_pipeline_bridge import process_onboarding_message

        with patch(
            "app.core.variant_pipeline_bridge._run_pipeline",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = Exception("Onboarding pipeline broke!")

            result = await process_onboarding_message(
                query="Tell me about PARWA",
                company_id="comp-123",
                session_context={"variant_tier": "parwa", "industry": "saas"},
            )

        assert result.pipeline_status == "failed"

    @pytest.mark.asyncio
    async def test_mini_parwa_pipeline_unavailable_fallback(self):
        """When Mini Parwa pipeline is unavailable, returns fallback response."""
        from app.core.variant_pipeline_bridge import _run_mini_parwa

        with patch(
            "app.core.variant_pipeline_bridge._get_mini_parwa_pipeline",
            return_value=None,
        ):
            result = await _run_mini_parwa(
                query="test", company_id="comp-1", industry="general",
            )

        assert result.pipeline_status == "pipeline_unavailable"
        assert "temporary issue" in result.response_text.lower()

    @pytest.mark.asyncio
    async def test_parwa_high_falls_back_to_pro_when_unavailable(self):
        """When Parwa High pipeline is unavailable, falls back to Pro."""
        from app.core.variant_pipeline_bridge import _run_parwa_high

        with patch(
            "app.core.variant_pipeline_bridge._get_parwa_high_pipeline",
            return_value=None,
        ), patch(
            "app.core.variant_pipeline_bridge._run_parwa",
            new_callable=AsyncMock,
        ) as mock_pro:
            mock_pro.return_value = MagicMock(
                response_text="Pro fallback",
                variant_tier="parwa",
                pipeline_status="completed",
            )

            result = await _run_parwa_high(
                query="Complex", company_id="comp-1", industry="general",
            )

        # Should fall back to pro pipeline
        mock_pro.assert_called_once()


# ══════════════════════════════════════════════════════════════════
# 6. TestSmartRouterModelSelection
# ══════════════════════════════════════════════════════════════════


class TestSmartRouterModelSelection:
    """Test Smart Router selects models correctly per variant, health, and cost."""

    def test_route_returns_valid_decision(self):
        """Smart Router always returns a RoutingDecision (BC-008)."""
        from app.core.smart_router import SmartRouter, AtomicStepType

        router = SmartRouter()
        decision = router.route(
            company_id="comp-123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )

        assert decision is not None
        assert decision.atomic_step_type == AtomicStepType.INTENT_CLASSIFICATION
        assert decision.model_config is not None
        assert decision.provider is not None
        assert decision.tier is not None
        assert decision.routing_reason

    def test_mini_parwa_never_gets_heavy_tier(self):
        """Mini PARWA can only access LIGHT and GUARDRAIL tiers."""
        from app.core.smart_router import SmartRouter, AtomicStepType, VARIANT_MODEL_ACCESS

        allowed = VARIANT_MODEL_ACCESS["mini_parwa"]
        from app.core.smart_router import ModelTier

        assert ModelTier.HEAVY not in allowed
        assert ModelTier.MEDIUM not in allowed
        assert ModelTier.LIGHT in allowed

    def test_parwa_gets_light_and_medium(self):
        """PARWA (Pro) can access LIGHT and MEDIUM but not HEAVY."""
        from app.core.smart_router import SmartRouter, ModelTier, VARIANT_MODEL_ACCESS

        allowed = VARIANT_MODEL_ACCESS["parwa"]
        assert ModelTier.LIGHT in allowed
        assert ModelTier.MEDIUM in allowed
        assert ModelTier.HEAVY not in allowed

    def test_parwa_high_gets_all_tiers(self):
        """PARWA High can access LIGHT, MEDIUM, and HEAVY."""
        from app.core.smart_router import ModelTier, VARIANT_MODEL_ACCESS

        allowed = VARIANT_MODEL_ACCESS["parwa_high"]
        assert ModelTier.LIGHT in allowed
        assert ModelTier.MEDIUM in allowed
        assert ModelTier.HEAVY in allowed

    def test_route_step_tier_mapping(self):
        """Each atomic step type maps to the expected model tier."""
        from app.core.smart_router import STEP_TIER_MAPPING, AtomicStepType, ModelTier

        assert STEP_TIER_MAPPING[AtomicStepType.INTENT_CLASSIFICATION] == ModelTier.LIGHT
        assert STEP_TIER_MAPPING[AtomicStepType.PII_REDACTION] == ModelTier.LIGHT
        assert STEP_TIER_MAPPING[AtomicStepType.DRAFT_RESPONSE_MODERATE] == ModelTier.MEDIUM
        assert STEP_TIER_MAPPING[AtomicStepType.DRAFT_RESPONSE_COMPLEX] == ModelTier.MEDIUM
        assert STEP_TIER_MAPPING[AtomicStepType.GUARDRAIL_CHECK] == ModelTier.GUARDRAIL

    def test_route_batch_returns_decisions_for_all_steps(self):
        """route_batch returns one RoutingDecision per step."""
        from app.core.smart_router import SmartRouter, AtomicStepType

        router = SmartRouter()
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.SENTIMENT_ANALYSIS,
            AtomicStepType.DRAFT_RESPONSE_SIMPLE,
        ]

        decisions = router.route_batch(
            company_id="comp-123",
            variant_type="parwa",
            steps=steps,
        )

        assert len(decisions) == 3
        for i, decision in enumerate(decisions):
            assert decision.atomic_step_type == steps[i]

    def test_provider_health_tracker_records_success(self):
        """ProviderHealthTracker records successes and resets failures."""
        from app.core.smart_router import ProviderHealthTracker, ModelProvider

        tracker = ProviderHealthTracker()
        tracker.record_success(
            provider=ModelProvider.CEREBRAS,
            model_id="llama-3.1-8b",
            tokens_used=100,
        )

        assert tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")
        assert tracker.get_daily_usage(ModelProvider.CEREBRAS, "llama-3.1-8b") == 1

    def test_provider_health_tracker_marks_unhealthy(self):
        """Provider is marked unhealthy after consecutive failure threshold."""
        from app.core.smart_router import ProviderHealthTracker, ModelProvider

        tracker = ProviderHealthTracker()
        threshold = ProviderHealthTracker.CONSECUTIVE_FAILURE_THRESHOLD

        for i in range(threshold):
            tracker.record_failure(
                provider=ModelProvider.GROQ,
                model_id="llama-3.1-8b",
                error_msg=f"Failure {i+1}",
            )

        assert not tracker.is_available(ModelProvider.GROQ, "llama-3.1-8b")

    def test_provider_health_tracker_rate_limit_cooldown(self):
        """Rate-limited providers are unavailable during cooldown period."""
        from app.core.smart_router import ProviderHealthTracker, ModelProvider

        tracker = ProviderHealthTracker()
        tracker.record_rate_limit(
            provider=ModelProvider.GOOGLE,
            model_id="gemma-3-27b-it",
            retry_after_seconds=120,
        )

        # Should be unavailable right after rate limit
        assert not tracker.is_available(ModelProvider.GOOGLE, "gemma-3-27b-it")

    def test_provider_health_tracker_daily_limit(self):
        """Provider becomes unavailable after hitting daily request limit."""
        from app.core.smart_router import ProviderHealthTracker, ModelProvider

        tracker = ProviderHealthTracker()

        # Manually set usage to near limit
        for _ in range(14400):
            tracker.record_success(
                provider=ModelProvider.CEREBRAS,
                model_id="llama-3.1-8b",
                tokens_used=10,
            )

        # Should be unavailable after hitting daily limit
        assert not tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")

    def test_get_variant_info_structure(self):
        """get_variant_info returns expected structure."""
        from app.core.smart_router import SmartRouter

        router = SmartRouter()
        info = router.get_variant_info("parwa")

        assert "variant_type" in info
        assert "allowed_tiers" in info
        assert "available_models" in info
        assert "total_available" in info
        assert info["variant_type"] == "parwa"

    def test_model_registry_has_all_tiers(self):
        """MODEL_REGISTRY contains models in all required tiers."""
        from app.core.smart_router import MODEL_REGISTRY, ModelTier

        tiers_present = {config.tier for config in MODEL_REGISTRY.values()}
        assert ModelTier.LIGHT in tiers_present
        assert ModelTier.MEDIUM in tiers_present
        assert ModelTier.HEAVY in tiers_present
        assert ModelTier.GUARDRAIL in tiers_present

    def test_unknown_variant_defaults_to_mini(self):
        """Unknown variant type gets mini_parwa access (safest)."""
        from app.core.smart_router import SmartRouter, AtomicStepType, VARIANT_MODEL_ACCESS, ModelTier

        router = SmartRouter()
        decision = router.route(
            company_id="comp-123",
            variant_type="nonexistent_variant",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )

        # Should still return a valid decision (BC-008)
        assert decision is not None
        # Should be limited to mini_parwa tiers
        mini_allowed = VARIANT_MODEL_ACCESS["mini_parwa"]
        assert decision.tier in mini_allowed

    def test_degraded_response_detector_empty(self):
        """DegradedResponseDetector flags empty responses."""
        from app.core.model_failover import DegradedResponseDetector

        detector = DegradedResponseDetector()
        is_degraded, reason = detector.is_degraded("")
        assert is_degraded
        assert reason == "empty_response"

    def test_degraded_response_detector_error_pattern(self):
        """DegradedResponseDetector flags error patterns in responses."""
        from app.core.model_failover import DegradedResponseDetector

        detector = DegradedResponseDetector()
        is_degraded, reason = detector.is_degraded(
            "Internal server error occurred while processing your request. "
            "This is a very long response that exceeds the minimum length."
        )
        assert is_degraded
        assert "error_pattern" in reason

    def test_degraded_response_detector_good_response(self):
        """DegradedResponseDetector passes good responses."""
        from app.core.model_failover import DegradedResponseDetector

        detector = DegradedResponseDetector()
        is_degraded, reason = detector.is_degraded(
            "I understand your frustration with the billing issue. "
            "Let me help you resolve this right away. I can see that "
            "there was an overcharge on your last invoice, and I will "
            "process a refund for the difference immediately."
        )
        assert not is_degraded
        assert reason == "ok"

    def test_failover_manager_circuit_breaker_opens(self):
        """Circuit breaker opens after threshold failures."""
        from app.core.model_failover import FailoverManager, FailoverReason, ProviderState

        manager = FailoverManager(recovery_threshold=3)

        for i in range(3):
            manager.report_failure(
                provider="cerebras",
                model_id="llama-3.1-8b",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Error {i}",
            )

        state = manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.CIRCUIT_OPEN

    def test_failover_manager_success_resets_circuit(self):
        """A successful call can reset a degraded circuit."""
        from app.core.model_failover import FailoverManager, FailoverReason, ProviderState

        manager = FailoverManager()

        # Degrade it
        manager.report_failure(
            provider="groq", model_id="llama-3.1-8b",
            reason=FailoverReason.TIMEOUT, error_msg="Timeout",
        )

        # Verify degraded
        state_before = manager.get_provider_state("groq", "llama-3.1-8b")
        assert state_before in (ProviderState.DEGRADED, ProviderState.CIRCUIT_OPEN)

        # Report success
        manager.report_success(
            provider="groq", model_id="llama-3.1-8b",
            latency_ms=200, response={"content": "OK"},
        )

        # Should be healthy now
        state_after = manager.get_provider_state("groq", "llama-3.1-8b")
        assert state_after == ProviderState.HEALTHY

    def test_failover_chain_skips_unhealthy_providers(self):
        """get_failover_chain skips circuit-open providers."""
        from app.core.model_failover import FailoverManager, FailoverReason

        manager = FailoverManager()

        # Open circuit for primary light provider
        for _ in range(3):
            manager.report_failure(
                provider="cerebras", model_id="llama-3.1-8b",
                reason=FailoverReason.SERVER_ERROR, error_msg="Down",
            )

        chain = manager.get_failover_chain("light")
        # Cerebras should be skipped
        for provider, model_id in chain:
            if provider == "cerebras" and model_id == "llama-3.1-8b":
                pytest.fail("Cerebras should be skipped in failover chain")

    def test_smart_router_execute_llm_call_never_crashes(self):
        """SmartRouter.execute_llm_call returns a dict even on total failure (BC-008)."""
        from app.core.smart_router import SmartRouter, AtomicStepType

        router = SmartRouter()
        decision = router.route(
            company_id="comp-123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )

        # Even without real API keys, should not crash
        result = router.execute_llm_call(
            company_id="comp-123",
            routing_decision=decision,
            messages=[
                {"role": "system", "content": "test"},
                {"role": "user", "content": "test"},
            ],
        )

        assert isinstance(result, dict)
        assert "content" in result


# ══════════════════════════════════════════════════════════════════
# 7. Cross-Cutting Integration Tests
# ══════════════════════════════════════════════════════════════════


class TestLLMIntegrationCrossCutting:
    """Cross-cutting tests that verify the entire LLM integration stack."""

    @pytest.mark.asyncio
    async def test_end_to_end_zai_client_to_router(self, mock_zai_sdk):
        """Verify ZAI client can feed decisions into the router agent."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        # 1. ZAI client classifies an alert
        llm_response = json.dumps({
            "agent": "sla_protection_agent",
            "reasoning": "SLA breach risk detected",
            "urgency": "high",
        })
        mock_zai_sdk.chat.completions.create.return_value = _make_completion(llm_response)

        client = ZAIClient()
        client._sdk = mock_zai_sdk
        client._initialized = True

        zai_result = await client.chat_async(
            agent_type="command_router",
            user_message="SLA breach risk: 12 tickets at risk",
            context={"alert_type": "sla_breach_risk", "severity": "high"},
        )

        assert zai_result["agent"] == "sla_protection_agent"

        # 2. Router agent processes a customer message (fallback path)
        state = {
            "pii_redacted_message": "My order hasn't arrived and I want a refund",
            "tenant_id": "tenant-123",
            "variant_tier": "mini",
            "sentiment_score": 0.2,
            "customer_tier": "free",
        }
        router_result = router_agent_node(state)

        # Router should classify as refund intent
        assert router_result["intent"] == "refund"
        # Mini tier should not get heavy model
        assert router_result["model_tier"] in ("light", "medium")

    def test_variant_tier_mapper_maps_correctly(self):
        """Variant tier mapper correctly maps frontend IDs to backend tiers."""
        from app.core.variant_tier_mapper import (
            variant_id_to_tier,
            variant_name_to_tier,
            industry_label_to_enum,
        )

        assert variant_id_to_tier("starter") == "mini_parwa"
        assert variant_id_to_tier("growth") == "parwa"
        assert variant_id_to_tier("high") == "parwa_high"
        assert variant_id_to_tier("unknown") == "mini_parwa"  # default

        assert variant_name_to_tier("PARWA Starter") == "mini_parwa"
        assert variant_name_to_tier("parwa growth") == "parwa"

        assert industry_label_to_enum("E-commerce") == "ecommerce"
        assert industry_label_to_enum("SaaS") == "saas"
        assert industry_label_to_enum("Others") == "general"

    def test_maker_k_value_per_variant(self):
        """MAKER K value scales with variant tier (more solutions for higher tiers)."""
        from app.core.langgraph.config import get_maker_k_value

        # Mini: K=3 (fixed)
        k_mini = get_maker_k_value("mini", 0.5)
        assert k_mini == 3

        # Pro: K varies with complexity (3-5)
        k_pro_low = get_maker_k_value("pro", 0.1)
        k_pro_mid = get_maker_k_value("pro", 0.5)
        k_pro_high = get_maker_k_value("pro", 0.9)
        assert k_pro_low <= k_pro_mid <= k_pro_high
        assert 3 <= k_pro_low <= 5
        assert 3 <= k_pro_high <= 5

        # High: K varies (5-7)
        k_high_low = get_maker_k_value("high", 0.1)
        k_high_high = get_maker_k_value("high", 0.9)
        assert 5 <= k_high_low <= 7
        assert 5 <= k_high_high <= 7

    def test_control_system_approval_per_tier(self):
        """Control system approval requirements scale with variant tier."""
        from app.core.langgraph.config import needs_human_approval, ActionType

        # Mini: No human approval needed
        assert not needs_human_approval("informational", "mini")
        assert not needs_human_approval("monetary", "mini")
        assert not needs_human_approval("destructive", "mini")

        # Pro: Human approval for monetary + destructive
        assert not needs_human_approval("informational", "pro")
        assert needs_human_approval("monetary", "pro")
        assert needs_human_approval("destructive", "pro")

        # High: Human approval for monetary + destructive + escalation
        assert not needs_human_approval("informational", "high")
        assert needs_human_approval("monetary", "high")
        assert needs_human_approval("destructive", "high")
        assert needs_human_approval("escalation", "high")

    def test_agent_availability_per_tier(self):
        """Agent availability scales correctly with variant tier."""
        from app.core.langgraph.config import get_available_agents

        mini_agents = get_available_agents("mini")
        pro_agents = get_available_agents("pro")
        high_agents = get_available_agents("high")

        # Mini has 3 agents
        assert len(mini_agents) == 3
        assert "faq" in mini_agents
        assert "technical" in mini_agents
        assert "billing" in mini_agents

        # Mini does NOT have refund/complaint/escalation
        assert "refund" not in mini_agents
        assert "complaint" not in mini_agents
        assert "escalation" not in mini_agents

        # Pro and High have all 6
        assert len(pro_agents) == 6
        assert len(high_agents) == 6

    def test_intent_to_agent_respects_tier(self):
        """map_intent_to_agent falls back correctly when agent isn't available."""
        from app.core.langgraph.config import map_intent_to_agent

        # Refund intent → refund agent (pro/high) → faq fallback (mini)
        assert map_intent_to_agent("refund", "pro") == "refund"
        assert map_intent_to_agent("refund", "high") == "refund"
        assert map_intent_to_agent("refund", "mini") == "faq"  # fallback

        # Escalation intent → escalation agent (pro/high) → faq fallback (mini)
        assert map_intent_to_agent("escalation", "pro") == "escalation"
        assert map_intent_to_agent("escalation", "mini") == "faq"  # fallback

    def test_utc_timestamps_in_all_responses(self):
        """All LLM integration responses use UTC timestamps (BC-012)."""
        from app.services.jarvis_agents.zai_client import ZAIClient

        client = ZAIClient()
        result = client._rule_based_fallback("command_router", "test", {})

        # Verify _parsed_at is ISO-8601 with UTC
        parsed_at = result.get("_parsed_at", "")
        assert parsed_at  # Not empty
        # UTC timestamps should end with +00:00 or Z
        assert "+00:00" in parsed_at or parsed_at.endswith("Z")

    @pytest.mark.asyncio
    async def test_tier_mapper_integrates_with_pipeline_bridge(self):
        """Variant tier mapper outputs correctly feed into pipeline bridge."""
        from app.core.variant_tier_mapper import variant_id_to_tier
        from app.core.variant_pipeline_bridge import _run_pipeline

        # Simulate frontend selecting "starter" → should route to mini_parwa
        tier = variant_id_to_tier("starter")
        assert tier == "mini_parwa"

        with patch(
            "app.core.variant_pipeline_bridge._run_mini_parwa",
            new_callable=AsyncMock,
        ) as mock_mini:
            mock_mini.return_value = MagicMock(
                response_text="Mini response",
                variant_tier="mini_parwa",
                pipeline_status="completed",
            )

            await _run_pipeline(
                variant_tier=tier,
                query="test query",
                company_id="comp-1",
                industry="general",
            )

            mock_mini.assert_called_once()
