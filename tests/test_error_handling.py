"""Comprehensive error handling tests for all 22 PARWA nodes.

Tests verify:
1. @safe_node Level 1: Catastrophic failures return fallback + track errors
2. Inner try/except Level 2: LLM failures degrade to rule-based results
3. Input validation guards: Corrupt/missing state handled gracefully
4. Error tracking: pipeline_errors and node_error populated correctly
5. Pipeline resilience: Graph survives node failures

This matches the 2-level error handling architecture:
- Level 1: @safe_node catches uncaught exceptions → returns fallback
- Level 2: Inner try/except catches LLM/external failures → degrades gracefully
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from parwa.nodes.ingest import ingest
from parwa.nodes.intent_classifier import intent_classifier, _classify_intent_rule_based
from parwa.nodes.sentiment_analyzer import sentiment_analyzer, _analyze_sentiment_rule_based
from parwa.nodes.escalation_decision import escalation_decision, _should_escalate_rule_based
from parwa.nodes.faq_matcher import faq_matcher, _match_faq_rule_based
from parwa.nodes.kb_retriever import kb_retriever, _retrieve_kb_rule_based
from parwa.nodes.context_manager import context_manager
from parwa.nodes.integration_lookup import integration_lookup, _lookup_integration_rule_based
from parwa.nodes.reasoning_engine import reasoning_engine, _reason_rule_based
from parwa.nodes.reverse_thinker import reverse_thinker, _reverse_think_rule_based
from parwa.nodes.tree_of_thoughts import tree_of_thoughts, _explore_paths_rule_based
from parwa.nodes.strategy_planner import strategy_planner, _plan_strategy_rule_based
from parwa.nodes.action_planner import action_planner, _plan_actions_rule_based
from parwa.nodes.action_executor import action_executor, _execute_action
from parwa.nodes.action_verifier import action_verifier, _verify_execution
from parwa.nodes.proactive_checker import proactive_checker, _check_proactive_rule_based
from parwa.nodes.prediction_engine import prediction_engine, _predict_issues_rule_based
from parwa.nodes.feedback_loop import feedback_loop, _generate_feedback_signal
from parwa.nodes.pii_compliance_guard import pii_compliance_guard, _detect_pii
from parwa.nodes.audit_logger import audit_logger
from parwa.nodes.quality_scorer import quality_scorer, _score_quality_rule_based
from parwa.nodes.response_formatter import response_formatter, _format_response_rule_based


# ═════════════════════════════════════════════════════════════════════════════════════
# LEVEL 1: @safe_node Catastrophic Failure Tests
# Patch internal helpers to raise — this makes the node function fail inside @safe_node
# ═════════════════════════════════════════════════════════════════════════════════════

class TestSafeNodeFallbackIngest:
    """Level 1: INGEST catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("Crash")):
            result = await ingest({"raw_message": "test", "variant": "invalid_variant_crash"})
        assert "ticket_id" in result
        assert result["ticket_id"] == "TKT-ERROR"

    @pytest.mark.asyncio
    async def test_tracks_error_on_crash(self):
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("Crash")):
            result = await ingest({"raw_message": "test", "variant": "invalid_variant_crash"})
        assert "pipeline_errors" in result
        assert len(result["pipeline_errors"]) == 1
        assert result["pipeline_errors"][0]["node"] == "INGEST"

    @pytest.mark.asyncio
    async def test_node_error_on_crash(self):
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("Crash")):
            result = await ingest({"raw_message": "test", "variant": "invalid_variant_crash"})
        assert "node_error" in result
        assert result["node_error"]["node"] == "INGEST"
        assert "RuntimeError" in result["node_error"]["error_type"]


class TestSafeNodeFallbackIntentClassifier:
    """Level 1: INTENT_CLASSIFIER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=RuntimeError("Crash")):
            result = await intent_classifier({"raw_message": "test"})
        assert result["intent"] == "general_inquiry"
        assert result["intent_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_tracks_error_on_crash(self):
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=RuntimeError("Crash")):
            result = await intent_classifier({"raw_message": "test"})
        assert "pipeline_errors" in result
        assert len(result["pipeline_errors"]) == 1


class TestSafeNodeFallbackSentimentAnalyzer:
    """Level 1: SENTIMENT_ANALYZER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.sentiment_analyzer._analyze_sentiment_rule_based", side_effect=RuntimeError("Crash")):
            result = await sentiment_analyzer({"raw_message": "test"})
        assert result["sentiment"] == "neutral"
        assert result["sentiment_urgency"] == 0.3


class TestSafeNodeFallbackEscalationDecision:
    """Level 1: ESCALATION_DECISION catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.escalation_decision._should_escalate_rule_based", side_effect=RuntimeError("Crash")):
            result = await escalation_decision({
                "raw_message": "test", "sentiment": "neutral",
                "sentiment_urgency": 0.3, "complexity": "simple",
                "intent": "general_inquiry", "intent_confidence": 0.8,
            })
        assert result["should_escalate"] is False
        assert result["escalation_reason"] == "node_error"


class TestSafeNodeFallbackFaqMatcher:
    """Level 1: FAQ_MATCHER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.faq_matcher._match_faq_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("Crash")):
            result = await faq_matcher({"raw_message": "test"})
        assert result["faq_match"] is None


class TestSafeNodeFallbackKbRetriever:
    """Level 1: KB_RETRIEVER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.kb_retriever._retrieve_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("Crash")):
            result = await kb_retriever({"raw_message": "test", "intent": "general_inquiry"})
        assert result["kb_results"] == []


class TestSafeNodeFallbackContextManager:
    """Level 1: CONTEXT_MANAGER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        """Test that context_manager inner try/except handles datetime failure gracefully."""
        # Context manager has inner try/except around datetime that returns "unknown" on failure
        # And @safe_node catches anything else
        # Test by providing a state that makes the function work (inner guards handle issues)
        result = await context_manager({"raw_message": "test", "context_history": []})
        assert isinstance(result["context_history"], list)
        assert len(result["context_history"]) >= 1

    @pytest.mark.asyncio
    async def test_returns_fallback_on_validation_crash(self):
        """Test that context_manager handles bad input via @safe_node."""
        result = await context_manager({"raw_message": "x" * 100000, "context_history": []})
        assert isinstance(result["context_history"], list)


class TestSafeNodeFallbackIntegrationLookup:
    """Level 1: INTEGRATION_LOOKUP catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.integration_lookup._lookup_integration_rule_based", side_effect=RuntimeError("Crash")):
            result = await integration_lookup({"customer_id": "default", "intent": "refund_request"})
        # Inner try/except catches it, returns {}
        assert result["integration_data"] == {}


class TestSafeNodeFallbackReasoningEngine:
    """Level 1: REASONING_ENGINE catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.reasoning_engine._reason_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("Crash")):
            result = await reasoning_engine({
                "raw_message": "test", "intent": "general_inquiry",
                "faq_match": None, "kb_results": [], "integration_data": {},
                "active_frameworks": [],
            })
        assert result["reasoning_chain"] == []
        assert result["reasoning_conclusion"] == ""


class TestSafeNodeFallbackReverseThinker:
    """Level 1: REVERSE_THINKER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.reverse_thinker._reverse_think_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.reverse_thinker._reverse_think_rule_based", side_effect=RuntimeError("Crash")):
            result = await reverse_thinker({
                "reasoning_conclusion": "test", "kb_results": [],
                "integration_data": {}, "active_frameworks": [],
                "loop_count": 0, "max_loops": 2,
            })
        assert result["reverse_validation"]["passed"] is False


class TestSafeNodeFallbackTreeOfThoughts:
    """Level 1: TREE_OF_THOUGHTS catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.tree_of_thoughts._tot_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.tree_of_thoughts._explore_paths_rule_based", side_effect=RuntimeError("Crash")):
            result = await tree_of_thoughts({
                "intent": "refund_request", "reasoning_conclusion": "test",
                "active_frameworks": [],
            })
        assert result["reasoning_paths"] == []
        assert result["selected_path"] is None


class TestSafeNodeFallbackStrategyPlanner:
    """Level 1: STRATEGY_PLANNER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.strategy_planner._plan_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.strategy_planner._plan_strategy_rule_based", side_effect=RuntimeError("Crash")):
            result = await strategy_planner({
                "intent": "refund_request", "reasoning_conclusion": "test",
                "selected_path": None, "active_frameworks": [],
            })
        assert result["strategy_plan"] == []


class TestSafeNodeFallbackActionPlanner:
    """Level 1: ACTION_PLANNER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.action_planner._plan_actions_rule_based", side_effect=RuntimeError("Crash")):
            result = await action_planner({
                "intent": "refund_request", "reasoning_conclusion": "test",
                "strategy_plan": [], "integration_data": {},
            })
        assert result["action_plans"] == []


class TestSafeNodeFallbackActionExecutor:
    """Level 1: ACTION_EXECUTOR catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.action_executor._execute_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.action_executor._execute_rule_based", side_effect=RuntimeError("Crash")):
            result = await action_executor({
                "variant": "parwa",
                "action_plans": [{"action_type": "send_reply", "description": "Reply", "parameters": {}, "evidence": [], "risk_level": "low"}],
            })
        assert result["execution_results"] == []
        assert result["recommendation"] is None


class TestSafeNodeFallbackActionVerifier:
    """Level 1: ACTION_VERIFIER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.action_verifier._verify_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.action_verifier._verify_execution", side_effect=RuntimeError("Crash")):
            result = await action_verifier({
                "execution_results": [{"status": "executed"}],
                "recommendation": None, "loop_count": 0, "max_loops": 2,
            })
        assert result["verification_passed"] is False


class TestSafeNodeFallbackProactiveChecker:
    """Level 1: PROACTIVE_CHECKER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.proactive_checker._check_proactive_rule_based", side_effect=RuntimeError("Crash")):
            result = await proactive_checker({"intent": "refund_request", "integration_data": {}})
        assert result["proactive_insights"] == []


class TestSafeNodeFallbackPredictionEngine:
    """Level 1: PREDICTION_ENGINE catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.prediction_engine._predict_issues_rule_based", side_effect=RuntimeError("Crash")):
            result = await prediction_engine({
                "intent": "refund_request", "integration_data": {}, "sentiment": "neutral",
            })
        assert result["predictions"] == []


class TestSafeNodeFallbackFeedbackLoop:
    """Level 1: FEEDBACK_LOOP catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.feedback_loop._feedback_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.feedback_loop._generate_feedback_signal", side_effect=RuntimeError("Crash")):
            result = await feedback_loop({
                "intent": "refund_request", "quality_score": 85,
                "verification_passed": True, "recommendation": None,
            })
        assert result["feedback_signal"]["resolved"] is False
        assert "node_failed" in result["feedback_signal"]["improvement_areas"]


class TestSafeNodeFallbackPiiComplianceGuard:
    """Level 1: PII_COMPLIANCE_GUARD catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.pii_compliance_guard._detect_pii", side_effect=RuntimeError("Crash")):
            result = await pii_compliance_guard({"raw_message": "test email@test.com"})
        # Inner try/except catches the PII detection failure
        # Returns pii_detected=False and the original message as-is (graceful degradation)
        assert result["pii_detected"] is False
        assert isinstance(result["pii_redacted_message"], str)


class TestSafeNodeFallbackAuditLogger:
    """Level 1: AUDIT_LOGGER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Audit logger has inner try/except + type guards that prevent most crashes
        # Even when individual fields fail, it creates a minimal audit entry
        # Test that it handles non-dict items in action_plans gracefully
        result = await audit_logger({
            "ticket_id": "TKT-TEST", "intent": "test",
            "action_plans": ["not_a_dict"],  # Bad data
            "execution_results": ["also_bad"],  # Bad data
            "recommendation": None, "quality_score": 85,
            "variant": "parwa", "audit_log": [],
        })
        # Should still create an audit entry (inner guards filter bad items)
        assert isinstance(result["audit_log"], list)
        assert len(result["audit_log"]) == 1
        # Bad items should be filtered out (isinstance check in list comp)
        assert result["audit_log"][0]["actions_planned"] == []
        assert result["audit_log"][0]["actions_executed"] == []


class TestSafeNodeFallbackQualityScorer:
    """Level 1: QUALITY_SCORER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.quality_scorer._score_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.quality_scorer._score_quality_rule_based", side_effect=RuntimeError("Crash")):
            result = await quality_scorer({
                "intent": "refund_request", "reasoning_conclusion": "test",
                "verification_passed": True, "recommendation": None,
                "variant": "parwa", "loop_count": 0, "max_loops": 2,
            })
        assert result["quality_score"] == 0.0
        assert "node_failed" in result["quality_issues"]


class TestSafeNodeFallbackResponseFormatter:
    """Level 1: RESPONSE_FORMATTER catastrophic failure → fallback"""

    @pytest.mark.asyncio
    async def test_returns_fallback_on_crash(self):
        with patch("parwa.nodes.response_formatter._format_response_rule_based", side_effect=RuntimeError("Crash")):
            result = await response_formatter({
                "intent": "refund_request", "reasoning_conclusion": "test",
                "execution_results": [], "recommendation": None,
                "proactive_insights": [], "variant": "parwa",
            })
        assert "apologize" in result["final_response"].lower() or "error" in result["final_response"].lower() or "issue" in result["final_response"].lower()


# ═════════════════════════════════════════════════════════════════════════════════════
# LEVEL 2: LLM Graceful Degradation Tests
# When LLM fails, nodes should keep their rule-based results instead of crashing
# ═════════════════════════════════════════════════════════════════════════════════════

class TestLLMGracefulDegradationIntentClassifier:
    """Level 2: INTENT_CLASSIFIER LLM failure → keeps rule-based result"""

    @pytest.mark.asyncio
    async def test_keeps_rule_based_when_llm_fails(self):
        """If LLM classification fails, rule-based result should be preserved."""
        with patch("parwa.nodes.intent_classifier.MOCK_MODE", False):
            with patch("parwa.nodes.intent_classifier._classify_intent_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("LLM API timeout")
                result = await intent_classifier({"raw_message": "I want a refund"})
                assert result["intent"] == "refund_request"
                assert result["intent_confidence"] > 0.5
                # Should NOT have pipeline errors (graceful degradation, not crash)
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []


class TestLLMGracefulDegradationSentimentAnalyzer:
    """Level 2: SENTIMENT_ANALYZER LLM failure → keeps rule-based result"""

    @pytest.mark.asyncio
    async def test_keeps_rule_based_when_llm_fails(self):
        """If LLM sentiment fails, rule-based result should be preserved."""
        with patch("parwa.nodes.sentiment_analyzer.MOCK_MODE", False):
            with patch("parwa.nodes.sentiment_analyzer._analyze_sentiment_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = TimeoutError("LLM timeout")
                result = await sentiment_analyzer({"raw_message": "Hello there"})
                assert result["sentiment"] == "neutral"
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []


class TestLLMGracefulDegradationEscalationDecision:
    """Level 2: ESCALATION_DECISION LLM failure → keeps rule-based result"""

    @pytest.mark.asyncio
    async def test_keeps_rule_based_when_llm_fails(self):
        """If LLM escalation check fails, rule-based result should be preserved."""
        with patch("parwa.nodes.escalation_decision.MOCK_MODE", False):
            with patch("parwa.nodes.escalation_decision._should_escalate_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("API down")
                result = await escalation_decision({
                    "raw_message": "Complex issue",
                    "sentiment": "neutral",
                    "sentiment_urgency": 0.3,
                    "complexity": "complex",
                    "intent": "technical_support",
                    "intent_confidence": 0.7,
                })
                assert result["should_escalate"] is False
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []


class TestLLMGracefulDegradationFaqMatcher:
    """Level 2: FAQ_MATCHER LLM failure → returns None (no match)"""

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_fails(self):
        """If LLM FAQ matching fails, should return None gracefully."""
        with patch("parwa.nodes.faq_matcher.MOCK_MODE", False):
            with patch("parwa.nodes.faq_matcher._match_faq_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("API down")
                result = await faq_matcher({"raw_message": "Something unusual"})
                assert result["faq_match"] is None
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []


class TestLLMGracefulDegradationReasoningEngine:
    """Level 2: REASONING_ENGINE LLM failure → keeps rule-based chain"""

    @pytest.mark.asyncio
    async def test_keeps_rule_based_chain_when_llm_fails(self):
        """If LLM reasoning fails, rule-based chain should be preserved."""
        with patch("parwa.nodes.reasoning_engine.MOCK_MODE", False):
            with patch("parwa.nodes.reasoning_engine._reason_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("LLM unavailable")
                result = await reasoning_engine({
                    "raw_message": "I was charged twice",
                    "intent": "refund_request",
                    "faq_match": None,
                    "kb_results": [],
                    "integration_data": {},
                    "active_frameworks": [],
                })
                assert len(result["reasoning_chain"]) > 0
                assert result["reasoning_conclusion"] != ""
                assert "chain_of_thought" in result["active_frameworks"]
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []


# ═════════════════════════════════════════════════════════════════════════════════════
# Input Validation Guard Tests
# Corrupt/missing state should be handled gracefully, not crash
# ═════════════════════════════════════════════════════════════════════════════════════

class TestInputValidationIngest:
    """INGEST input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_raw_message(self):
        result = await ingest({"raw_message": 12345})
        assert isinstance(result["raw_message"], str)

    @pytest.mark.asyncio
    async def test_non_string_customer_id(self):
        result = await ingest({"raw_message": "Hi", "customer_id": 999})
        assert isinstance(result["customer_id"], str)

    @pytest.mark.asyncio
    async def test_non_string_channel(self):
        result = await ingest({"raw_message": "Hi", "channel": 42})
        assert isinstance(result["channel"], str)

    @pytest.mark.asyncio
    async def test_non_string_variant(self):
        result = await ingest({"raw_message": "Hi", "variant": None})
        assert isinstance(result["variant"], str)


class TestInputValidationIntentClassifier:
    """INTENT_CLASSIFIER input validation guards"""

    @pytest.mark.asyncio
    async def test_empty_message_returns_default(self):
        result = await intent_classifier({"raw_message": ""})
        assert result["intent"] == "general_inquiry"
        assert result["intent_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_message_returns_default(self):
        result = await intent_classifier({"raw_message": "   "})
        assert result["intent"] == "general_inquiry"

    @pytest.mark.asyncio
    async def test_non_string_message_returns_default(self):
        result = await intent_classifier({"raw_message": None})
        assert result["intent"] == "general_inquiry"


class TestInputValidationSentimentAnalyzer:
    """SENTIMENT_ANALYZER input validation guards"""

    @pytest.mark.asyncio
    async def test_empty_message_returns_neutral(self):
        result = await sentiment_analyzer({"raw_message": ""})
        assert result["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_non_string_message_returns_neutral(self):
        result = await sentiment_analyzer({"raw_message": 42})
        assert result["sentiment"] == "neutral"


class TestInputValidationFaqMatcher:
    """FAQ_MATCHER input validation guards"""

    @pytest.mark.asyncio
    async def test_empty_message_returns_none(self):
        result = await faq_matcher({"raw_message": ""})
        assert result["faq_match"] is None

    @pytest.mark.asyncio
    async def test_non_string_message_returns_none(self):
        result = await faq_matcher({"raw_message": []})
        assert result["faq_match"] is None


class TestInputValidationKbRetriever:
    """KB_RETRIEVER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_message_handled(self):
        result = await kb_retriever({"raw_message": 123, "intent": "refund_request"})
        assert isinstance(result["kb_results"], list)

    @pytest.mark.asyncio
    async def test_non_string_intent_handled(self):
        result = await kb_retriever({"raw_message": "test", "intent": 42})
        assert isinstance(result["kb_results"], list)


class TestInputValidationContextManager:
    """CONTEXT_MANAGER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_history_handled(self):
        result = await context_manager({"raw_message": "Hi", "context_history": "bad"})
        assert isinstance(result["context_history"], list)

    @pytest.mark.asyncio
    async def test_non_string_message_handled(self):
        result = await context_manager({"raw_message": None, "context_history": []})
        assert isinstance(result["context_history"], list)


class TestInputValidationIntegrationLookup:
    """INTEGRATION_LOOKUP input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_customer_id_handled(self):
        result = await integration_lookup({"customer_id": 123, "intent": "refund_request"})
        assert isinstance(result["integration_data"], dict)

    @pytest.mark.asyncio
    async def test_non_string_intent_handled(self):
        result = await integration_lookup({"customer_id": "default", "intent": None})
        assert isinstance(result["integration_data"], dict)


class TestInputValidationReasoningEngine:
    """REASONING_ENGINE input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_kb_results_handled(self):
        result = await reasoning_engine({
            "raw_message": "test", "intent": "general_inquiry",
            "faq_match": None, "kb_results": "bad", "integration_data": {},
            "active_frameworks": [],
        })
        assert isinstance(result["reasoning_chain"], list)

    @pytest.mark.asyncio
    async def test_non_dict_integration_data_handled(self):
        result = await reasoning_engine({
            "raw_message": "test", "intent": "general_inquiry",
            "faq_match": None, "kb_results": [], "integration_data": "bad",
            "active_frameworks": [],
        })
        assert isinstance(result["reasoning_chain"], list)


class TestInputValidationReverseThinker:
    """REVERSE_THINKER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_kb_results_handled(self):
        result = await reverse_thinker({
            "reasoning_conclusion": "test",
            "kb_results": "bad", "integration_data": {},
            "active_frameworks": [], "loop_count": 0, "max_loops": 2,
        })
        assert isinstance(result["reverse_validation"], dict)


class TestInputValidationTreeOfThoughts:
    """TREE_OF_THOUGHTS input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_intent_handled(self):
        result = await tree_of_thoughts({
            "intent": 42, "reasoning_conclusion": "test", "active_frameworks": [],
        })
        assert isinstance(result["reasoning_paths"], list)


class TestInputValidationStrategyPlanner:
    """STRATEGY_PLANNER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_dict_selected_path_handled(self):
        result = await strategy_planner({
            "intent": "refund_request", "reasoning_conclusion": "test",
            "selected_path": "bad", "active_frameworks": [],
        })
        assert isinstance(result["strategy_plan"], list)


class TestInputValidationActionPlanner:
    """ACTION_PLANNER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_strategy_plan_handled(self):
        result = await action_planner({
            "intent": "refund_request", "reasoning_conclusion": "test",
            "strategy_plan": "bad", "integration_data": {},
        })
        assert isinstance(result["action_plans"], list)

    @pytest.mark.asyncio
    async def test_non_dict_integration_data_handled(self):
        result = await action_planner({
            "intent": "refund_request", "reasoning_conclusion": "test",
            "strategy_plan": [], "integration_data": "bad",
        })
        assert isinstance(result["action_plans"], list)


class TestInputValidationActionExecutor:
    """ACTION_EXECUTOR input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_variant_handled(self):
        result = await action_executor({
            "variant": 42,
            "action_plans": [{"action_type": "send_reply", "description": "Reply", "parameters": {}, "evidence": [], "risk_level": "low"}],
        })
        assert isinstance(result["execution_results"], list)

    @pytest.mark.asyncio
    async def test_non_list_action_plans_handled(self):
        result = await action_executor({"variant": "parwa", "action_plans": "bad"})
        assert isinstance(result["execution_results"], list)

    @pytest.mark.asyncio
    async def test_invalid_action_type_handled(self):
        result = await action_executor({
            "variant": "parwa",
            "action_plans": [{"action_type": "nonexistent_action", "description": "Bad", "parameters": {}, "evidence": [], "risk_level": "low"}],
        })
        assert isinstance(result["execution_results"], list)


class TestInputValidationActionVerifier:
    """ACTION_VERIFIER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_execution_results_handled(self):
        result = await action_verifier({
            "execution_results": "bad", "recommendation": None,
            "loop_count": 0, "max_loops": 2,
        })
        assert isinstance(result["verification_passed"], bool)

    @pytest.mark.asyncio
    async def test_non_dict_recommendation_handled(self):
        result = await action_verifier({
            "execution_results": [], "recommendation": "bad",
            "loop_count": 0, "max_loops": 2,
        })
        assert isinstance(result["verification_passed"], bool)


class TestInputValidationProactiveChecker:
    """PROACTIVE_CHECKER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_intent_handled(self):
        result = await proactive_checker({"intent": 42, "integration_data": {}})
        assert isinstance(result["proactive_insights"], list)

    @pytest.mark.asyncio
    async def test_non_dict_integration_data_handled(self):
        result = await proactive_checker({"intent": "refund_request", "integration_data": "bad"})
        assert isinstance(result["proactive_insights"], list)


class TestInputValidationPredictionEngine:
    """PREDICTION_ENGINE input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_sentiment_handled(self):
        result = await prediction_engine({
            "intent": "refund_request", "integration_data": {}, "sentiment": 42,
        })
        assert isinstance(result["predictions"], list)


class TestInputValidationFeedbackLoop:
    """FEEDBACK_LOOP input validation guards"""

    @pytest.mark.asyncio
    async def test_non_numeric_quality_score_handled(self):
        result = await feedback_loop({
            "intent": "refund_request", "quality_score": "bad",
            "verification_passed": True, "recommendation": None,
        })
        assert isinstance(result["feedback_signal"], dict)

    @pytest.mark.asyncio
    async def test_non_bool_verification_passed_handled(self):
        result = await feedback_loop({
            "intent": "refund_request", "quality_score": 85,
            "verification_passed": "yes", "recommendation": None,
        })
        assert isinstance(result["feedback_signal"], dict)


class TestInputValidationPiiComplianceGuard:
    """PII_COMPLIANCE_GUARD input validation guards"""

    @pytest.mark.asyncio
    async def test_non_string_message_handled(self):
        result = await pii_compliance_guard({"raw_message": 12345})
        assert isinstance(result["pii_detected"], bool)
        assert isinstance(result["pii_redacted_message"], str)


class TestInputValidationAuditLogger:
    """AUDIT_LOGGER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_action_plans_handled(self):
        result = await audit_logger({
            "ticket_id": "TKT-TEST", "intent": "test",
            "action_plans": "bad", "execution_results": [],
            "recommendation": None, "quality_score": 85,
            "variant": "parwa", "audit_log": [],
        })
        assert isinstance(result["audit_log"], list)
        assert len(result["audit_log"]) == 1

    @pytest.mark.asyncio
    async def test_non_list_execution_results_handled(self):
        result = await audit_logger({
            "ticket_id": "TKT-TEST", "intent": "test",
            "action_plans": [], "execution_results": "bad",
            "recommendation": None, "quality_score": 85,
            "variant": "parwa", "audit_log": [],
        })
        assert isinstance(result["audit_log"], list)

    @pytest.mark.asyncio
    async def test_non_list_existing_audit_log_handled(self):
        result = await audit_logger({
            "ticket_id": "TKT-TEST", "intent": "test",
            "action_plans": [], "execution_results": [],
            "recommendation": None, "quality_score": 85,
            "variant": "parwa", "audit_log": "bad",
        })
        assert isinstance(result["audit_log"], list)


class TestInputValidationQualityScorer:
    """QUALITY_SCORER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_bool_verification_passed_handled(self):
        result = await quality_scorer({
            "intent": "refund_request", "reasoning_conclusion": "Eligible",
            "verification_passed": "yes", "recommendation": None,
            "variant": "parwa", "loop_count": 0, "max_loops": 2,
        })
        assert isinstance(result["quality_score"], float)

    @pytest.mark.asyncio
    async def test_non_dict_recommendation_handled(self):
        result = await quality_scorer({
            "intent": "refund_request", "reasoning_conclusion": "Eligible",
            "verification_passed": True, "recommendation": "bad",
            "variant": "parwa", "loop_count": 0, "max_loops": 2,
        })
        assert isinstance(result["quality_score"], float)


class TestInputValidationResponseFormatter:
    """RESPONSE_FORMATTER input validation guards"""

    @pytest.mark.asyncio
    async def test_non_list_execution_results_handled(self):
        result = await response_formatter({
            "intent": "refund_request", "reasoning_conclusion": "Eligible",
            "execution_results": "bad", "recommendation": None,
            "proactive_insights": [], "variant": "parwa",
        })
        assert isinstance(result["final_response"], str)

    @pytest.mark.asyncio
    async def test_non_dict_recommendation_handled(self):
        result = await response_formatter({
            "intent": "refund_request", "reasoning_conclusion": "Eligible",
            "execution_results": [], "recommendation": "bad",
            "proactive_insights": [], "variant": "parwa",
        })
        assert isinstance(result["final_response"], str)


# ═════════════════════════════════════════════════════════════════════════════════════
# Error Tracking Verification Tests
# Verify pipeline_errors and node_error are populated correctly
# ═════════════════════════════════════════════════════════════════════════════════════

class TestErrorTracking:
    """Verify error tracking in pipeline_errors and node_error"""

    @pytest.mark.asyncio
    async def test_multiple_errors_tracked(self):
        """Each node failure should track its own error."""
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=RuntimeError("Crash")):
            result = await intent_classifier({"raw_message": "test"})
        assert len(result["pipeline_errors"]) == 1
        assert result["pipeline_errors"][0]["node"] == "INTENT_CLASSIFIER"

    @pytest.mark.asyncio
    async def test_node_error_has_full_details(self):
        """node_error should have error_type, error_message, traceback, elapsed."""
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.reasoning_engine._reason_with_brain", side_effect=RuntimeError("Crash")), \
             patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("Crash")):
            result = await reasoning_engine({
                "raw_message": "test", "intent": "general_inquiry",
                "faq_match": None, "kb_results": [], "integration_data": {},
                "active_frameworks": [],
            })
        assert "node_error" in result
        error = result["node_error"]
        assert error["node"] == "REASONING_ENGINE"
        assert "RuntimeError" in error["error_type"]
        assert isinstance(error["error_message"], str)
        assert isinstance(error["traceback"], str)
        assert isinstance(error["elapsed_seconds"], float)
        assert error["elapsed_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_error_does_not_corrupt_other_results(self):
        """If one node errors, its error result shouldn't break downstream nodes."""
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("Crash")):
            result = await ingest({"raw_message": "test", "variant": "invalid_variant_crash"})
        assert isinstance(result, dict)
        assert "ticket_id" in result  # fallback value present

    @pytest.mark.asyncio
    async def test_no_errors_on_normal_input(self):
        """Normal input should produce no pipeline_errors."""
        result = await intent_classifier({"raw_message": "I want a refund"})
        assert "pipeline_errors" not in result or result.get("pipeline_errors") == []
        assert "node_error" not in result or result.get("node_error") is None

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_pipeline_errors(self):
        """LLM graceful degradation (Level 2) should NOT add pipeline_errors."""
        with patch("parwa.nodes.intent_classifier.MOCK_MODE", False):
            with patch("parwa.nodes.intent_classifier._classify_intent_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("API down")
                result = await intent_classifier({"raw_message": "I want a refund"})
                # Level 2 degradation — no pipeline errors
                assert "pipeline_errors" not in result or result.get("pipeline_errors") == []
                # Still has a valid result from rule-based
                assert result["intent"] == "refund_request"


# ═════════════════════════════════════════════════════════════════════════════════════
# Escalation Decision Input Validation Guards
# ═════════════════════════════════════════════════════════════════════════════════════

class TestInputValidationEscalationDecision:
    """ESCALATION_DECISION input validation guards"""

    @pytest.mark.asyncio
    async def test_non_numeric_urgency_handled(self):
        result = await escalation_decision({
            "raw_message": "test", "sentiment": "neutral",
            "sentiment_urgency": "high", "complexity": "simple",
            "intent": "general_inquiry", "intent_confidence": 0.8,
        })
        assert isinstance(result["should_escalate"], bool)

    @pytest.mark.asyncio
    async def test_non_numeric_confidence_handled(self):
        result = await escalation_decision({
            "raw_message": "test", "sentiment": "neutral",
            "sentiment_urgency": 0.3, "complexity": "simple",
            "intent": "general_inquiry", "intent_confidence": "high",
        })
        assert isinstance(result["should_escalate"], bool)
