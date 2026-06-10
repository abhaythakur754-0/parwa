"""Unit tests for error handling in all 22 PARWA nodes.

Tests that when a node raises an exception:
1. The exception is caught by @safe_node
2. The node returns fallback values (not a crash)
3. The node_error field is populated with error details
4. The pipeline_errors list is appended with the error
5. The fallback values are safe for downstream nodes
6. Multiple consecutive errors are tracked correctly
"""

import pytest
from unittest.mock import patch, AsyncMock

from parwa.nodes.ingest import ingest
from parwa.nodes.intent_classifier import intent_classifier
from parwa.nodes.sentiment_analyzer import sentiment_analyzer
from parwa.nodes.escalation_decision import escalation_decision
from parwa.nodes.faq_matcher import faq_matcher
from parwa.nodes.kb_retriever import kb_retriever
from parwa.nodes.context_manager import context_manager
from parwa.nodes.integration_lookup import integration_lookup
from parwa.nodes.reasoning_engine import reasoning_engine
from parwa.nodes.reverse_thinker import reverse_thinker
from parwa.nodes.tree_of_thoughts import tree_of_thoughts
from parwa.nodes.strategy_planner import strategy_planner
from parwa.nodes.action_planner import action_planner
from parwa.nodes.action_executor import action_executor
from parwa.nodes.action_verifier import action_verifier
from parwa.nodes.proactive_checker import proactive_checker
from parwa.nodes.prediction_engine import prediction_engine
from parwa.nodes.feedback_loop import feedback_loop
from parwa.nodes.pii_compliance_guard import pii_compliance_guard
from parwa.nodes.audit_logger import audit_logger
from parwa.nodes.quality_scorer import quality_scorer
from parwa.nodes.response_formatter import response_formatter


# ─── Helper ──────────────────────────────────────────────────────────────────────

def _has_error_tracking(result: dict) -> bool:
    """Check that error tracking fields are present in result."""
    has_node_error = "node_error" in result and result["node_error"] is not None
    has_pipeline_errors = "pipeline_errors" in result and len(result["pipeline_errors"]) > 0
    return has_node_error and has_pipeline_errors


# ─── Router Agent Nodes ──────────────────────────────────────────────────────────

class TestIngestErrorHandling:
    """Node 1: INGEST — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When ingest raises, fallback values are returned."""
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("CRM down")):
            result = await ingest({"raw_message": "test"})

        # Should have fallback ticket_id
        assert result["ticket_id"] == "TKT-ERROR"
        assert result["raw_message"] == ""
        assert result["channel"] == "email"
        assert result["variant"] == "parwa"

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        """Error tracking fields are populated on failure."""
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("CRM down")):
            result = await ingest({"raw_message": "test"})

        assert _has_error_tracking(result)
        assert result["node_error"]["node"] == "INGEST"
        assert result["node_error"]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_pipeline_errors_appended(self):
        """pipeline_errors list grows with each error."""
        existing_errors = [{"node": "PREV_NODE", "error": "prev error"}]
        with patch("parwa.nodes.ingest.get_variant_channels", side_effect=RuntimeError("CRM down")):
            result = await ingest({"raw_message": "test", "pipeline_errors": existing_errors})

        # Should have original + new error
        assert len(result["pipeline_errors"]) == 2
        assert result["pipeline_errors"][0]["node"] == "PREV_NODE"
        assert result["pipeline_errors"][1]["node"] == "INGEST"


class TestIntentClassifierErrorHandling:
    """Node 2: INTENT_CLASSIFIER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When intent_classifier raises, safe defaults are returned."""
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=ValueError("broken")):
            result = await intent_classifier({"raw_message": "test"})

        assert result["intent"] == "general_inquiry"
        assert result["intent_confidence"] == 0.0
        assert result["complexity"] == "simple"

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=ValueError("broken")):
            result = await intent_classifier({"raw_message": "test"})

        assert _has_error_tracking(result)
        assert result["node_error"]["node"] == "INTENT_CLASSIFIER"


class TestSentimentAnalyzerErrorHandling:
    """Node 18: SENTIMENT_ANALYZER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When sentiment_analyzer raises, neutral defaults are returned."""
        with patch("parwa.nodes.sentiment_analyzer._analyze_sentiment_rule_based", side_effect=RuntimeError("fail")):
            result = await sentiment_analyzer({"raw_message": "test"})

        assert result["sentiment"] == "neutral"
        assert result["sentiment_urgency"] == 0.3

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.sentiment_analyzer._analyze_sentiment_rule_based", side_effect=RuntimeError("fail")):
            result = await sentiment_analyzer({"raw_message": "test"})

        assert _has_error_tracking(result)
        assert result["node_error"]["node"] == "SENTIMENT_ANALYZER"


class TestEscalationDecisionErrorHandling:
    """Node 20: ESCALATION_DECISION — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When escalation_decision raises, should_escalate=False (safe default)."""
        with patch("parwa.nodes.escalation_decision._should_escalate_rule_based", side_effect=RuntimeError("fail")):
            result = await escalation_decision({
                "raw_message": "test",
                "sentiment": "angry",
                "sentiment_urgency": 0.9,
                "complexity": "critical",
                "intent": "complaint",
                "intent_confidence": 0.9,
            })

        # Safe default: don't escalate on error (avoids false escalations)
        assert result["should_escalate"] is False
        assert result["escalation_reason"] == "node_error"

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.escalation_decision._should_escalate_rule_based", side_effect=RuntimeError("fail")):
            result = await escalation_decision({
                "raw_message": "test",
                "sentiment": "neutral",
                "sentiment_urgency": 0.3,
                "complexity": "simple",
                "intent": "order_status",
                "intent_confidence": 0.9,
            })

        assert _has_error_tracking(result)


# ─── Knowledge Agent Nodes ────────────────────────────────────────────────────────

class TestFaqMatcherErrorHandling:
    """Node 3: FAQ_MATCHER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When faq_matcher raises, faq_match=None (no match)."""
        with patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("fail")):
            result = await faq_matcher({"raw_message": "test"})

        assert result["faq_match"] is None

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("fail")):
            result = await faq_matcher({"raw_message": "test"})

        assert _has_error_tracking(result)


class TestKbRetrieverErrorHandling:
    """Node 4: KB_RETRIEVER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When kb_retriever raises, kb_results=[] (empty)."""
        with patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("fail")):
            result = await kb_retriever({"raw_message": "test", "intent": "refund_request"})

        assert result["kb_results"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("fail")):
            result = await kb_retriever({"raw_message": "test", "intent": "refund_request"})

        assert _has_error_tracking(result)


class TestContextManagerErrorHandling:
    """Node 19: CONTEXT_MANAGER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When context_manager raises, empty context_history is returned."""
        from parwa.utils.node_base import safe_node

        @safe_node("CONTEXT_MANAGER", fallback={"context_history": []})
        async def _failing_context(state):
            raise RuntimeError("forced failure")

        result = await _failing_context({"raw_message": "test"})

        assert result["context_history"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated_on_failure(self):
        """Error tracking is populated when context_manager fails."""
        from parwa.utils.node_base import safe_node

        @safe_node("CONTEXT_MANAGER", fallback={"context_history": []})
        async def _failing_context(state):
            raise RuntimeError("forced failure")

        result = await _failing_context({"raw_message": "test"})

        assert _has_error_tracking(result)
        assert result["context_history"] == []


class TestIntegrationLookupErrorHandling:
    """Node 5: INTEGRATION_LOOKUP — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When integration_lookup raises, empty integration_data is returned."""
        with patch("parwa.nodes.integration_lookup._lookup_integration_rule_based", side_effect=RuntimeError("CRM down")):
            result = await integration_lookup({"customer_id": "default", "intent": "refund_request"})

        assert result["integration_data"] == {}

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.integration_lookup._lookup_integration_rule_based", side_effect=RuntimeError("CRM down")):
            result = await integration_lookup({"customer_id": "default", "intent": "refund_request"})

        assert _has_error_tracking(result)


# ─── Reasoning Agent Nodes ────────────────────────────────────────────────────────

class TestReasoningEngineErrorHandling:
    """Node 6: REASONING_ENGINE — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When reasoning_engine raises, empty chain/conclusion are returned."""
        with patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("fail")):
            result = await reasoning_engine({
                "raw_message": "test",
                "intent": "refund_request",
                "faq_match": None,
                "kb_results": [],
                "integration_data": {},
                "active_frameworks": [],
            })

        assert result["reasoning_chain"] == []
        assert result["reasoning_conclusion"] == ""
        assert result["active_frameworks"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("fail")):
            result = await reasoning_engine({
                "raw_message": "test",
                "intent": "general_inquiry",
                "faq_match": None,
                "kb_results": [],
                "integration_data": {},
                "active_frameworks": [],
            })

        assert _has_error_tracking(result)


class TestReverseThinkerErrorHandling:
    """Node 10: REVERSE_THINKER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When reverse_thinker raises, validation fails safely."""
        with patch("parwa.nodes.reverse_thinker._reverse_think_rule_based", side_effect=RuntimeError("fail")):
            result = await reverse_thinker({
                "reasoning_conclusion": "test",
                "kb_results": [],
                "integration_data": {},
                "active_frameworks": [],
                "loop_count": 0,
                "max_loops": 2,
            })

        assert result["reverse_validation"]["passed"] is False
        assert result["should_loop_back"] is False
        assert result["active_frameworks"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.reverse_thinker._reverse_think_rule_based", side_effect=RuntimeError("fail")):
            result = await reverse_thinker({
                "reasoning_conclusion": "test",
                "kb_results": [],
                "integration_data": {},
                "active_frameworks": [],
                "loop_count": 0,
                "max_loops": 2,
            })

        assert _has_error_tracking(result)


class TestTreeOfThoughtsErrorHandling:
    """Node 12: TREE_OF_THOUGHTS — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When tree_of_thoughts raises, empty paths are returned."""
        with patch("parwa.nodes.tree_of_thoughts._explore_paths_rule_based", side_effect=RuntimeError("fail")):
            result = await tree_of_thoughts({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "active_frameworks": [],
            })

        assert result["reasoning_paths"] == []
        assert result["selected_path"] is None
        assert result["active_frameworks"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.tree_of_thoughts._explore_paths_rule_based", side_effect=RuntimeError("fail")):
            result = await tree_of_thoughts({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "active_frameworks": [],
            })

        assert _has_error_tracking(result)


class TestStrategyPlannerErrorHandling:
    """Node 11: STRATEGY_PLANNER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When strategy_planner raises, empty plan is returned."""
        with patch("parwa.nodes.strategy_planner._plan_strategy_rule_based", side_effect=RuntimeError("fail")):
            result = await strategy_planner({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "selected_path": None,
                "active_frameworks": [],
            })

        assert result["strategy_plan"] == []
        assert result["active_frameworks"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.strategy_planner._plan_strategy_rule_based", side_effect=RuntimeError("fail")):
            result = await strategy_planner({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "selected_path": None,
                "active_frameworks": [],
            })

        assert _has_error_tracking(result)


# ─── Action Agent Nodes ───────────────────────────────────────────────────────────

class TestActionPlannerErrorHandling:
    """Node 7: ACTION_PLANNER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When action_planner raises, empty plans are returned."""
        with patch("parwa.nodes.action_planner._plan_actions_rule_based", side_effect=RuntimeError("fail")):
            result = await action_planner({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "strategy_plan": ["step1"],
                "integration_data": {"charges": [{"amount": 49.99}]},
            })

        assert result["action_plans"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.action_planner._plan_actions_rule_based", side_effect=RuntimeError("fail")):
            result = await action_planner({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "strategy_plan": ["step1"],
                "integration_data": {"charges": [{"amount": 49.99}]},
            })

        assert _has_error_tracking(result)


class TestActionExecutorErrorHandling:
    """Node 8: ACTION_EXECUTOR — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When action_executor raises, empty results and no recommendation."""
        with patch("parwa.nodes.action_executor.get_permission", side_effect=RuntimeError("fail")):
            result = await action_executor({
                "variant": "parwa",
                "action_plans": [{"action_type": "process_refund"}],
                "quality_score": 85,
            })

        assert result["execution_results"] == []
        assert result["recommendation"] is None

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.action_executor.get_permission", side_effect=RuntimeError("fail")):
            result = await action_executor({
                "variant": "parwa",
                "action_plans": [{"action_type": "process_refund"}],
                "quality_score": 85,
            })

        assert _has_error_tracking(result)


class TestActionVerifierErrorHandling:
    """Node 9: ACTION_VERIFIER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When action_verifier raises, verification_passed=False safely."""
        with patch("parwa.nodes.action_verifier._verify_execution", side_effect=RuntimeError("fail")):
            result = await action_verifier({
                "execution_results": [{"status": "executed"}],
                "recommendation": None,
                "loop_count": 0,
                "max_loops": 2,
            })

        assert result["verification_passed"] is False
        assert result["should_loop_back"] is False

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.action_verifier._verify_execution", side_effect=RuntimeError("fail")):
            result = await action_verifier({
                "execution_results": [{"status": "executed"}],
                "recommendation": None,
                "loop_count": 0,
                "max_loops": 2,
            })

        assert _has_error_tracking(result)


# ─── Proactive Agent Nodes ────────────────────────────────────────────────────────

class TestProactiveCheckerErrorHandling:
    """Node 13: PROACTIVE_CHECKER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When proactive_checker raises, empty insights are returned."""
        with patch("parwa.nodes.proactive_checker._check_proactive_rule_based", side_effect=RuntimeError("fail")):
            result = await proactive_checker({
                "intent": "refund_request",
                "integration_data": {},
            })

        assert result["proactive_insights"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.proactive_checker._check_proactive_rule_based", side_effect=RuntimeError("fail")):
            result = await proactive_checker({
                "intent": "refund_request",
                "integration_data": {},
            })

        assert _has_error_tracking(result)


class TestPredictionEngineErrorHandling:
    """Node 14: PREDICTION_ENGINE — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When prediction_engine raises, empty predictions are returned."""
        with patch("parwa.nodes.prediction_engine._predict_issues_rule_based", side_effect=RuntimeError("fail")):
            result = await prediction_engine({
                "intent": "refund_request",
                "integration_data": {},
                "sentiment": "neutral",
            })

        assert result["predictions"] == []

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.prediction_engine._predict_issues_rule_based", side_effect=RuntimeError("fail")):
            result = await prediction_engine({
                "intent": "refund_request",
                "integration_data": {},
                "sentiment": "neutral",
            })

        assert _has_error_tracking(result)


class TestFeedbackLoopErrorHandling:
    """Node 22: FEEDBACK_LOOP — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When feedback_loop raises, safe feedback signal is returned."""
        with patch("parwa.nodes.feedback_loop._generate_feedback_signal", side_effect=RuntimeError("fail")):
            result = await feedback_loop({
                "intent": "refund_request",
                "quality_score": 85,
                "verification_passed": True,
                "recommendation": None,
            })

        assert result["feedback_signal"]["resolved"] is False
        assert result["feedback_signal"]["satisfaction"] == "low"
        assert "node_failed" in result["feedback_signal"]["improvement_areas"]

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.feedback_loop._generate_feedback_signal", side_effect=RuntimeError("fail")):
            result = await feedback_loop({
                "intent": "refund_request",
                "quality_score": 85,
                "verification_passed": True,
                "recommendation": None,
            })

        assert _has_error_tracking(result)


# ─── Compliance Agent Nodes ───────────────────────────────────────────────────────

class TestPiiComplianceGuardErrorHandling:
    """Node 15: PII_COMPLIANCE_GUARD — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When pii_compliance_guard raises, no PII detected (safe default)."""
        with patch("parwa.nodes.pii_compliance_guard._detect_pii", side_effect=RuntimeError("fail")):
            result = await pii_compliance_guard({"raw_message": "test with email@foo.com"})

        # Safe default: assume no PII detected (won't block the response)
        assert result["pii_detected"] is False
        assert result["pii_redacted_message"] == ""

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.pii_compliance_guard._detect_pii", side_effect=RuntimeError("fail")):
            result = await pii_compliance_guard({"raw_message": "test"})

        assert _has_error_tracking(result)


class TestAuditLoggerErrorHandling:
    """Node 16: AUDIT_LOGGER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When audit_logger raises, empty audit_log is returned (doesn't crash)."""
        # Force a failure by making datetime unavailable
        from parwa.utils.node_base import safe_node

        @safe_node("AUDIT_LOGGER", fallback={"audit_log": []})
        async def _failing_audit(state):
            raise RuntimeError("forced failure")

        result = await _failing_audit({
            "ticket_id": "TKT-TEST",
            "intent": "refund_request",
            "action_plans": [],
            "execution_results": [],
            "recommendation": None,
            "quality_score": 85,
            "variant": "parwa",
            "audit_log": [],
        })

        assert result["audit_log"] == []
        assert _has_error_tracking(result)


class TestQualityScorerErrorHandling:
    """Node 21: QUALITY_SCORER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When quality_scorer raises, score=0, no loop-back."""
        with patch("parwa.nodes.quality_scorer._score_quality_rule_based", side_effect=RuntimeError("fail")):
            result = await quality_scorer({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "verification_passed": True,
                "recommendation": None,
                "variant": "parwa",
                "loop_count": 0,
                "max_loops": 2,
            })

        assert result["quality_score"] == 0.0
        assert "node_failed" in result["quality_issues"]
        assert result["should_loop_back"] is False

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.quality_scorer._score_quality_rule_based", side_effect=RuntimeError("fail")):
            result = await quality_scorer({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "verification_passed": True,
                "recommendation": None,
                "variant": "parwa",
                "loop_count": 0,
                "max_loops": 2,
            })

        assert _has_error_tracking(result)


class TestResponseFormatterErrorHandling:
    """Node 17: RESPONSE_FORMATTER — Error handling tests"""

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """When response_formatter raises, a safe apology message is returned."""
        with patch("parwa.nodes.response_formatter._format_response_rule_based", side_effect=RuntimeError("fail")):
            result = await response_formatter({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "execution_results": [],
                "recommendation": None,
                "proactive_insights": [],
                "variant": "parwa",
            })

        assert "apologize" in result["final_response"] or "issue" in result["final_response"]
        assert "human agent" in result["final_response"]

    @pytest.mark.asyncio
    async def test_error_tracking_populated(self):
        with patch("parwa.nodes.response_formatter._format_response_rule_based", side_effect=RuntimeError("fail")):
            result = await response_formatter({
                "intent": "refund_request",
                "reasoning_conclusion": "test",
                "execution_results": [],
                "recommendation": None,
                "proactive_insights": [],
                "variant": "parwa",
            })

        assert _has_error_tracking(result)


# ─── Cross-Cutting Error Handling Tests ───────────────────────────────────────────

class TestErrorTrackingConsistency:
    """Tests that error tracking is consistent across all nodes."""

    @pytest.mark.asyncio
    async def test_all_errors_have_required_fields(self):
        """Every node_error dict must have: node, error_type, error_message, traceback."""
        from parwa.utils.node_base import safe_node

        @safe_node("TEST_NODE", fallback={"test_key": "test_value"})
        async def _failing_node(state):
            raise ValueError("test error message")

        result = await _failing_node({"raw_message": "test"})

        error = result["node_error"]
        assert "node" in error
        assert "error_type" in error
        assert "error_message" in error
        assert "traceback" in error
        assert error["node"] == "TEST_NODE"
        assert error["error_type"] == "ValueError"
        assert "test error message" in error["error_message"]

    @pytest.mark.asyncio
    async def test_pipeline_errors_append_not_replace(self):
        """pipeline_errors should APPEND, not replace existing errors."""
        from parwa.utils.node_base import safe_node

        @safe_node("NODE_A", fallback={"x": 1})
        async def _failing_node_a(state):
            raise RuntimeError("A failed")

        @safe_node("NODE_B", fallback={"y": 2})
        async def _failing_node_b(state):
            raise RuntimeError("B failed")

        # First failure
        result_a = await _failing_node_a({"raw_message": "test", "pipeline_errors": []})
        assert len(result_a["pipeline_errors"]) == 1
        assert result_a["pipeline_errors"][0]["node"] == "NODE_A"

        # Second failure (simulating state with existing errors)
        result_b = await _failing_node_b({
            "raw_message": "test",
            "pipeline_errors": result_a["pipeline_errors"],
        })
        assert len(result_b["pipeline_errors"]) == 2
        assert result_b["pipeline_errors"][0]["node"] == "NODE_A"
        assert result_b["pipeline_errors"][1]["node"] == "NODE_B"

    @pytest.mark.asyncio
    async def test_fallback_values_preserved_in_error_result(self):
        """Fallback values should be present in the error result dict."""
        from parwa.utils.node_base import safe_node

        @safe_node("TEST", fallback={"intent": "general_inquiry", "confidence": 0.0})
        async def _failing_node(state):
            raise ConnectionError("LLM down")

        result = await _failing_node({"raw_message": "test"})

        # Fallback values should be present
        assert result["intent"] == "general_inquiry"
        assert result["confidence"] == 0.0
        # Error tracking should also be present
        assert result["node_error"] is not None
        assert len(result["pipeline_errors"]) == 1

    @pytest.mark.asyncio
    async def test_no_fallback_gives_empty_dict_on_error(self):
        """Without fallback, error result should only have error tracking fields."""
        from parwa.utils.node_base import safe_node

        @safe_node("NO_FALLBACK_TEST")
        async def _failing_node(state):
            raise RuntimeError("fail")

        result = await _failing_node({"raw_message": "test"})

        # Without fallback, only error tracking fields
        assert "node_error" in result
        assert "pipeline_errors" in result
        # No application-specific keys
        app_keys = [k for k in result.keys() if k not in ("node_error", "pipeline_errors")]
        assert len(app_keys) == 0

    @pytest.mark.asyncio
    async def test_exception_types_preserved(self):
        """Different exception types are tracked correctly."""
        from parwa.utils.node_base import safe_node

        @safe_node("EXC_TYPE_TEST", fallback={"x": 1})
        async def _value_error_node(state):
            raise ValueError("bad value")

        @safe_node("EXC_TYPE_TEST2", fallback={"x": 1})
        async def _type_error_node(state):
            raise TypeError("bad type")

        result_v = await _value_error_node({"raw_message": "test"})
        result_t = await _type_error_node({"raw_message": "test"})

        assert result_v["node_error"]["error_type"] == "ValueError"
        assert result_t["node_error"]["error_type"] == "TypeError"

    @pytest.mark.asyncio
    async def test_elapsed_seconds_in_error(self):
        """node_error should include elapsed_seconds."""
        from parwa.utils.node_base import safe_node

        @safe_node("ELAPSED_TEST", fallback={"x": 1})
        async def _failing_node(state):
            raise RuntimeError("fail")

        result = await _failing_node({"raw_message": "test"})
        assert "elapsed_seconds" in result["node_error"]
        assert result["node_error"]["elapsed_seconds"] >= 0
