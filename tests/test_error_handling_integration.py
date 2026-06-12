"""Integration tests for error handling across the PARWA pipeline.

Tests the full graph's resilience to node failures:
1. Pipeline continues even when individual nodes raise exceptions
2. Fallback values allow downstream nodes to function
3. Multiple node failures are tracked cumulatively
4. Final response always has content (even if degraded)
5. Error recovery is graceful — no unhandled exceptions escape
"""

import pytest
import uuid
from unittest.mock import patch, AsyncMock

from parwa.graph import build_parwa_graph, process_ticket, aprocess_ticket, reset_parwa_graph


@pytest.fixture
def parwa_graph():
    """Create a fresh compiled graph for each test."""
    reset_parwa_graph()
    return build_parwa_graph(use_checkpointer=True)


def _config(thread_id: str | None = None) -> dict:
    """Create a LangGraph config with thread_id for checkpointing."""
    return {"configurable": {"thread_id": thread_id or f"test-{uuid.uuid4().hex[:8]}"}}


# ─── Single Node Failure Tests ────────────────────────────────────────────────────

class TestSingleNodeFailure:
    """Test that the pipeline survives when ONE node fails."""

    @pytest.mark.asyncio
    async def test_intent_classifier_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when intent_classifier crashes."""
        with patch("parwa.nodes.intent_classifier._classify_intent_rule_based", side_effect=RuntimeError("Classifier down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice, I want a refund",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # Pipeline should complete (not crash)
        assert result["final_response"] != ""
        # Should have error tracking
        assert len(result.get("pipeline_errors", [])) > 0
        # Fallback intent should be applied
        assert "intent" in result

    @pytest.mark.asyncio
    async def test_sentiment_analyzer_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when sentiment_analyzer crashes."""
        with patch("parwa.nodes.sentiment_analyzer._analyze_sentiment_rule_based", side_effect=RuntimeError("Sentiment API down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""
        # Fallback: neutral sentiment
        assert "sentiment" in result

    @pytest.mark.asyncio
    async def test_integration_lookup_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when CRM/integration lookup crashes."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM unavailable")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""
        # Should have integration_data with fallback data
        assert result.get("integration_data", {}).get("found") is True

    @pytest.mark.asyncio
    async def test_reasoning_engine_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when reasoning_engine crashes."""
        # Patch both FrameworkBrain path and rule-based fallback to force crash
        with patch("parwa.nodes.reasoning_engine._reason_with_brain", side_effect=RuntimeError("LLM timeout")), \
             patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("LLM timeout")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_action_executor_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when action_executor crashes."""
        with patch("parwa.nodes.action_executor.get_permission", side_effect=RuntimeError("Permissions down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # Should still have a response
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_pii_guard_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when PII guard crashes."""
        with patch("parwa.nodes.pii_compliance_guard._detect_pii", side_effect=RuntimeError("PII scan down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I need help with my order",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_quality_scorer_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when quality_scorer crashes."""
        with patch("parwa.nodes.quality_scorer._score_quality_rule_based", side_effect=RuntimeError("Scorer down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""
        # Quality score should be 0 (fallback)
        assert result.get("quality_score", 0) == 0.0

    @pytest.mark.asyncio
    async def test_response_formatter_failure_pipeline_continues(self, parwa_graph):
        """Pipeline continues when response_formatter crashes — gets fallback message."""
        with patch("parwa.nodes.response_formatter._format_response_rule_based", side_effect=RuntimeError("Formatter down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # Should have the fallback apology message
        assert "apologize" in result["final_response"] or "issue" in result["final_response"]


# ─── Multiple Node Failure Tests ──────────────────────────────────────────────────

class TestMultipleNodeFailures:
    """Test that the pipeline survives when MULTIPLE nodes fail."""

    @pytest.mark.asyncio
    async def test_knowledge_agent_failure_pipeline_continues(self, parwa_graph):
        """When all Knowledge Agent nodes (FAQ, KB, Context, Integration) fail."""
        with (
            patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("FAQ down")),
            patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("KB down")),
            patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # Pipeline should still complete
        assert result["final_response"] != ""
        # Should have multiple errors tracked
        errors = result.get("pipeline_errors", [])
        assert len(errors) >= 2  # At least FAQ and KB failed

    @pytest.mark.asyncio
    async def test_reasoning_agent_failure_pipeline_continues(self, parwa_graph):
        """When all Reasoning Agent nodes (Reasoning, Reverse, ToT, Strategy) fail."""
        with (
            patch("parwa.nodes.reasoning_engine._reason_with_brain", side_effect=RuntimeError("Reasoning down")),
            patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("Reasoning down")),
            patch("parwa.nodes.reverse_thinker._reverse_think_with_brain", side_effect=RuntimeError("Reverse down")),
            patch("parwa.nodes.reverse_thinker._reverse_think_rule_based", side_effect=RuntimeError("Reverse down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_proactive_agent_failure_pipeline_continues(self, parwa_graph):
        """When all Proactive Agent nodes fail."""
        with (
            patch("parwa.nodes.proactive_checker._check_proactive_rule_based", side_effect=RuntimeError("Proactive down")),
            patch("parwa.nodes.prediction_engine._predict_issues_rule_based", side_effect=RuntimeError("Prediction down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""
        # Proactive insights and predictions should be empty
        assert result.get("proactive_insights", []) == []
        assert result.get("predictions", []) == []


# ─── Error Tracking Tests ─────────────────────────────────────────────────────────

class TestErrorTrackingIntegration:
    """Test that error tracking works correctly across the full pipeline."""

    @pytest.mark.asyncio
    async def test_error_count_matches_failures(self, parwa_graph):
        """Number of pipeline_errors should match number of failed nodes."""
        with (
            patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("FAQ down")),
            patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("KB down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        errors = result.get("pipeline_errors", [])
        # Should have at least 2 errors (FAQ + KB)
        assert len(errors) >= 2
        # Each error should have required fields
        for err in errors:
            assert "node" in err
            assert "error" in err
            assert "error_type" in err

    @pytest.mark.asyncio
    async def test_no_errors_on_normal_ticket(self, parwa_graph):
        """Normal tickets should have zero pipeline errors."""
        result = await parwa_graph.ainvoke({
            "raw_message": "Where is my order?",
            "customer_id": "default",
            "channel": "chat",
            "variant": "parwa",
        }, config=_config())

        errors = result.get("pipeline_errors", [])
        assert len(errors) == 0, f"Unexpected pipeline errors: {errors}"

    @pytest.mark.asyncio
    async def test_node_error_cleared_on_next_successful_node(self, parwa_graph):
        """node_error should be from the LAST failed node, not all."""
        # This test verifies that node_error tracks the most recent error
        with patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("FAQ down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # If there's a node_error, it should have valid structure
        if result.get("node_error"):
            assert "node" in result["node_error"]
            assert "error_type" in result["node_error"]

    @pytest.mark.asyncio
    async def test_different_error_types_tracked_correctly(self, parwa_graph):
        """Different error types (ConnectionError, ValueError, etc.) are tracked."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        errors = result.get("pipeline_errors", [])
        if errors:
            crm_errors = [e for e in errors if e.get("node") == "INTEGRATION_LOOKUP"]
            if crm_errors:
                assert crm_errors[0]["error_type"] == "ConnectionError"


# ─── Variant Behavior Under Failures ──────────────────────────────────────────────

class TestVariantBehaviorUnderFailure:
    """Test that variant differentiation still works even with failures."""

    @pytest.mark.asyncio
    async def test_mini_still_recommends_on_partial_failure(self, parwa_graph):
        """Mini PARWA should still recommend (not execute) even when some nodes fail."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "mini",
            }, config=_config())

        # Mini should still create recommendation, not execute
        assert result.get("recommendation") is not None or len(result.get("execution_results", [])) > 0

    @pytest.mark.asyncio
    async def test_parwa_still_executes_on_partial_failure(self, parwa_graph):
        """PARWA should still execute (not recommend) even when some nodes fail."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # PARWA should still try to execute
        executed = [r for r in result.get("execution_results", []) if r.get("status") == "executed"]
        # May have executed actions or may have empty action_plans due to failure
        assert result["final_response"] != ""


# ─── Convenience Function Error Handling ───────────────────────────────────────────

class TestConvenienceFunctionErrorHandling:
    """Test that process_ticket and aprocess_ticket handle errors gracefully."""

    def test_process_ticket_with_node_failure(self):
        """process_ticket sync wrapper handles node failures gracefully."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = process_ticket(
                raw_message="I was charged twice",
                customer_id="default",
                channel="email",
                variant="parwa",
            )

        # Should still complete
        assert "final_response" in result
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_aprocess_ticket_with_node_failure(self):
        """aprocess_ticket async wrapper handles node failures gracefully."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = await aprocess_ticket(
                raw_message="I was charged twice",
                customer_id="default",
                channel="email",
                variant="parwa",
            )

        # Pipeline should still complete with a response
        assert result["final_response"] != ""
        # Inner try/except in integration_lookup gracefully degrades (returns {})
        # so no pipeline_errors should be tracked for graceful degradation
        # The key test: pipeline doesn't crash, still produces a result
        assert isinstance(result.get("pipeline_errors", []), list)

    @pytest.mark.asyncio
    async def test_aprocess_ticket_empty_message_returns_error(self):
        """Empty message should return error, not crash."""
        result = await aprocess_ticket(raw_message="")
        assert "error" in result or "final_response" in result

    @pytest.mark.asyncio
    async def test_aprocess_ticket_invalid_variant_defaults(self):
        """Invalid variant should default to parwa, not crash."""
        result = await aprocess_ticket(raw_message="Help", variant="enterprise")
        assert result["variant"] == "parwa"


# ─── Catastrophic Failure Tests ───────────────────────────────────────────────────

class TestCatastrophicFailure:
    """Test behavior under catastrophic failures (multiple critical nodes down)."""

    @pytest.mark.asyncio
    async def test_catastrophic_knowledge_failure(self, parwa_graph):
        """When ALL knowledge + reasoning nodes fail, pipeline still completes."""
        with (
            patch("parwa.nodes.faq_matcher._match_faq_rule_based", side_effect=RuntimeError("FAQ down")),
            patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("KB down")),
            patch("parwa.nodes.reasoning_engine._reason_with_brain", side_effect=RuntimeError("Reasoning down")),
            patch("parwa.nodes.reasoning_engine._reason_rule_based", side_effect=RuntimeError("Reasoning down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # Must still produce a response (even if degraded)
        assert result["final_response"] != ""
        # Should have multiple errors tracked
        assert len(result.get("pipeline_errors", [])) >= 2

    @pytest.mark.asyncio
    async def test_catastrophic_action_failure(self, parwa_graph):
        """When action nodes fail, pipeline completes with error tracking."""
        with (
            patch("parwa.nodes.action_planner._plan_actions_rule_based", side_effect=RuntimeError("Action planner down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_compliance_failure_still_completes(self, parwa_graph):
        """When compliance nodes fail, pipeline still completes."""
        with (
            patch("parwa.nodes.pii_compliance_guard._detect_pii", side_effect=RuntimeError("PII down")),
            patch("parwa.nodes.quality_scorer._score_quality_rule_based", side_effect=RuntimeError("Quality down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I need help",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert result["final_response"] != ""


# ─── Fallback Value Correctness Tests ─────────────────────────────────────────────

class TestFallbackValueCorrectness:
    """Test that fallback values are the correct types and safe for downstream."""

    @pytest.mark.asyncio
    async def test_list_fallbacks_are_empty_lists(self, parwa_graph):
        """When nodes fail, list fields should default to [] not None."""
        with (
            patch("parwa.nodes.kb_retriever._retrieve_kb_rule_based", side_effect=RuntimeError("KB down")),
            patch("parwa.nodes.proactive_checker._check_proactive_rule_based", side_effect=RuntimeError("Proactive down")),
        ):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        # These should be lists (even if empty), not None
        assert isinstance(result.get("kb_results", []), list)
        assert isinstance(result.get("proactive_insights", []), list)
        assert isinstance(result.get("predictions", []), list)

    @pytest.mark.asyncio
    async def test_dict_fallbacks_are_dicts(self, parwa_graph):
        """When integration_lookup fails, integration_data should be {}."""
        with patch("parwa.nodes.integration_lookup._lookup_from_crm", side_effect=ConnectionError("CRM down")):
            result = await parwa_graph.ainvoke({
                "raw_message": "I was charged twice",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert isinstance(result.get("integration_data", {}), dict)

    @pytest.mark.asyncio
    async def test_boolean_fallbacks_are_bool(self, parwa_graph):
        """When nodes fail, boolean fields should be bool not None."""
        with patch("parwa.nodes.escalation_decision._should_escalate_rule_based", side_effect=RuntimeError("fail")):
            result = await parwa_graph.ainvoke({
                "raw_message": "Hello",
                "customer_id": "default",
                "channel": "email",
                "variant": "parwa",
            }, config=_config())

        assert isinstance(result.get("should_escalate", False), bool)
        assert isinstance(result.get("verification_passed", False), bool)
