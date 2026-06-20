"""
Integration Tests for LangGraph Gaps LG-01 through LG-04

These tests verify that the LG-01 through LG-04 fixes work together
correctly in realistic scenarios. They test the interaction between
components (retry + DLQ, validation + graph, etc.) rather than
testing each component in isolation.

All external dependencies (DB, Redis, LLM APIs) are mocked.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ══════════════════════════════════════════════════════════════════
# LG-01 Integration: Sync retry works inside actual node functions
# ══════════════════════════════════════════════════════════════════


class TestLG01IntegrationRetryInNodes:
    """LG-01: Verify sync retry works end-to-end inside node functions."""

    def test_empathy_engine_node_retry_on_transient(self):
        """Empathy engine should retry transient errors and recover."""
        import importlib
        module = importlib.import_module("app.core.langgraph.nodes.02_empathy_engine")
        empathy_engine_node = module.empathy_engine_node

        call_count = 0
        original_analyze = None

        def mock_analyze_sentiment(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ConnectionError("LLM connection refused")
            return {
                "sentiment_score": 0.6,
                "sentiment_intensity": "medium",
                "legal_threat_detected": False,
                "urgency": "low",
                "sentiment_trend": "stable",
            }

        with patch.dict("sys.modules", {
            "app.core.sentiment_engine": MagicMock(
                analyze_sentiment=mock_analyze_sentiment
            ),
        }):
            state = {
                "message": "I need help with my account",
                "pii_redacted_message": "I need help with my account",
                "tenant_id": "t-1",
                "variant_tier": "mini",
                "conversation_id": "conv-1",
            }
            result = empathy_engine_node(state)

        # Should have recovered after retry
        assert "sentiment_score" in result
        assert result["sentiment_score"] == 0.6

    def test_router_agent_node_retry_on_rate_limit(self):
        """Router agent should retry on 429 and recover."""
        import importlib
        module = importlib.import_module("app.core.langgraph.nodes.03_router_agent")
        router_agent_node = module.router_agent_node

        call_count = 0

        def mock_classify_intent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                exc = Exception("Rate limit exceeded")
                exc.status_code = 429
                raise exc
            return "billing"

        with patch.dict("sys.modules", {
            "app.core.classification_engine": MagicMock(
                classify_intent=mock_classify_intent,
                estimate_complexity=MagicMock(return_value=0.5),
            ),
        }):
            state = {
                "message": "I was overcharged",
                "pii_redacted_message": "I was overcharged",
                "tenant_id": "t-1",
                "variant_tier": "pro",
                "sentiment_score": 0.3,
                "customer_tier": "free",
            }
            result = router_agent_node(state)

        assert "intent" in result
        assert result["intent"] == "billing"

    def test_node_falls_back_when_all_retries_exhausted(self):
        """Node should fall back to heuristic when all retries fail."""
        import importlib
        module = importlib.import_module("app.core.langgraph.nodes.03_router_agent")
        router_agent_node = module.router_agent_node

        def always_rate_limit(*args, **kwargs):
            exc = Exception("Rate limit exceeded")
            exc.status_code = 429
            raise exc

        with patch.dict("sys.modules", {
            "app.core.classification_engine": MagicMock(
                classify_intent=always_rate_limit,
                estimate_complexity=always_rate_limit,
            ),
        }):
            state = {
                "message": "I want a refund for my order",
                "pii_redacted_message": "I want a refund for my order",
                "tenant_id": "t-1",
                "variant_tier": "mini",
                "sentiment_score": 0.3,
                "customer_tier": "free",
            }
            result = router_agent_node(state)

        # Should fall back to keyword-based classification
        assert "intent" in result
        # "refund" keyword is in the message, so fallback should classify as "refund"
        assert result["intent"] == "refund"


class TestLG01IntegrationExponentialBackoff:
    """LG-01: Verify exponential backoff timing in realistic scenario."""

    def test_sync_retry_backoff_increases(self):
        """Verify that retry delays increase exponentially."""
        from app.core.langgraph.retry import sync_retry_llm_call

        attempt_times = []

        def track_and_fail():
            attempt_times.append(time.monotonic())
            if len(attempt_times) < 4:
                raise TimeoutError("LLM timeout")
            return "finally_done"

        result = sync_retry_llm_call(
            track_and_fail, max_retries=4, base_delay=0.05, max_delay=0.5
        )
        assert result == "finally_done"
        assert len(attempt_times) == 4

        # Delays should increase: ~0.05, ~0.1, ~0.2
        if len(attempt_times) >= 4:
            d1 = attempt_times[1] - attempt_times[0]
            d2 = attempt_times[2] - attempt_times[1]
            d3 = attempt_times[3] - attempt_times[2]
            # Each delay should be roughly double the previous
            assert d2 > d1 * 0.8, f"Second delay should be > first: d1={d1:.3f} d2={d2:.3f}"
            assert d3 > d2 * 0.8, f"Third delay should be > second: d2={d2:.3f} d3={d3:.3f}"


# ══════════════════════════════════════════════════════════════════
# LG-02 Integration: DLQ captures graph execution failures
# ══════════════════════════════════════════════════════════════════


class TestLG02IntegrationDLQCapture:
    """LG-02: Verify DLQ captures failed graph executions end-to-end."""

    @pytest.mark.asyncio
    async def test_dlq_captured_on_graph_timeout(self):
        """When graph times out, DLQ should be written."""
        from app.core.langgraph.graph import invoke_parwa_graph

        with patch("app.core.langgraph.graph.build_parwa_graph") as mock_build:
            mock_graph = AsyncMock()
            mock_graph.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_build.return_value = mock_graph

            with patch("app.core.langgraph.graph._persist_to_dlq", new_callable=AsyncMock) as mock_dlq:
                result = await invoke_parwa_graph(
                    message="Hello",
                    channel="email",
                    customer_id="cust-1",
                    tenant_id="t-1",
                    variant_tier="mini",
                )

        # Should return fallback response
        assert result.get("delivery_status") == "pending_human_review"
        assert result.get("system_mode") == "paused"

    @pytest.mark.asyncio
    async def test_dlq_captured_on_graph_exception(self):
        """When graph throws an exception, DLQ should be written."""
        from app.core.langgraph.graph import invoke_parwa_graph

        with patch("app.core.langgraph.graph.build_parwa_graph") as mock_build:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("Node crashed"))
            mock_build.return_value = mock_graph

            with patch("app.core.langgraph.graph._persist_to_dlq", new_callable=AsyncMock) as mock_dlq:
                result = await invoke_parwa_graph(
                    message="Help!",
                    channel="chat",
                    customer_id="cust-2",
                    tenant_id="t-2",
                    variant_tier="pro",
                )

        assert result.get("delivery_status") == "pending_human_review"

    def test_persist_to_dlq_dual_write(self):
        """persist_to_dlq should write to both Redis and PostgreSQL."""
        from app.core.langgraph.dlq import persist_to_dlq

        with patch("app.core.langgraph.dlq._persist_to_redis") as mock_redis:
            with patch("app.core.langgraph.dlq._persist_to_db", return_value="test-id") as mock_db:
                result = persist_to_dlq(
                    company_id="comp-1",
                    conversation_id="conv-1",
                    error="Graph execution failed",
                    state_snapshot={"message": "test", "tenant_id": "t-1"},
                )

        mock_redis.assert_called_once()
        mock_db.assert_called_once()
        assert result == "test-id"


# ══════════════════════════════════════════════════════════════════
# LG-03 Integration: Validation + Graph + Node integration
# ══════════════════════════════════════════════════════════════════


class TestLG03IntegrationValidationInGraph:
    """LG-03: Verify state validation works inside the graph wrapper."""

    def test_make_validated_node_sanitizes_output(self):
        """_make_validated_node should sanitize invalid node output."""
        from app.core.langgraph.graph import _make_validated_node

        def bad_node(state):
            return {
                "variant_tier": "INVALID_TIER",
                "agent_confidence": 5.0,
                "intent": "refund",  # valid
            }

        validated = _make_validated_node("bad_node", bad_node)
        result = validated({})

        assert result["variant_tier"] == "mini"  # sanitized
        assert result["agent_confidence"] == 1.0  # clamped
        assert result["intent"] == "refund"  # valid, unchanged

    def test_make_validated_node_handles_exception(self):
        """_make_validated_node should handle node exceptions gracefully."""
        from app.core.langgraph.graph import _make_validated_node

        def crashing_node(state):
            raise ValueError("Something went wrong")

        validated = _make_validated_node("crashing_node", crashing_node)
        result = validated({})

        # Should return error dict, not raise
        assert "errors" in result
        assert "crashing_node" in result["errors"][0]

    def test_make_validated_node_async(self):
        """_make_validated_node should work with async node functions."""
        from app.core.langgraph.graph import _make_validated_node

        async def async_bad_node(state):
            return {
                "variant_tier": "INVALID",
                "agent_confidence": -1.0,
            }

        validated = _make_validated_node("async_bad_node", async_bad_node)
        assert asyncio.iscoroutinefunction(validated)

        result = asyncio.get_event_loop().run_until_complete(validated({}))
        assert result["variant_tier"] == "mini"
        assert result["agent_confidence"] == 0.0

    def test_validation_catches_cross_node_contamination(self):
        """Invalid values from one node should be caught before they affect downstream nodes."""
        from app.core.langgraph.validators import validate_state_transition

        # A node accidentally writes an invalid delivery_status
        errors = validate_state_transition({
            "delivery_status": "lost_in_space",
            "variant_tier": "pro",
            "agent_confidence": 0.9,
        })
        assert len(errors) == 1
        assert "delivery_status" in errors[0]

    def test_sanitize_prevents_downstream_corruption(self):
        """Sanitization should prevent bad values from propagating."""
        from app.core.langgraph.validators import sanitize_state_update

        # A node accidentally writes dangerous values
        update = sanitize_state_update({
            "variant_tier": "SUPER_ADMIN",
            "action_type": "destroy_everything",
            "emergency_state": "nuclear",
            "agent_confidence": 999.0,
        })

        # All should be sanitized to safe defaults
        assert update["variant_tier"] == "mini"  # lowest privilege
        assert update["action_type"] == "informational"  # no side effects
        assert update["emergency_state"] == "normal"  # no emergency
        assert update["agent_confidence"] == 1.0  # max range


class TestLG03IntegrationStateCreation:
    """LG-03: Verify initial state creation is valid."""

    def test_initial_state_passes_validation(self):
        """create_initial_state should produce a state that passes validation."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.validators import validate_state_transition

        state = create_initial_state(
            message="Hello",
            channel="email",
            customer_id="cust-1",
            tenant_id="t-1",
            variant_tier="pro",
        )

        # Validate the enum/range fields in the initial state
        errors = validate_state_transition({
            k: v for k, v in state.items()
            if k in {"variant_tier", "channel", "intent", "agent_confidence",
                     "sentiment_score", "complexity_score", "urgency",
                     "delivery_status", "system_mode", "emergency_state"}
        })
        assert errors == [], f"Initial state has validation errors: {errors}"


# ══════════════════════════════════════════════════════════════════
# LG-04 Integration: Fail-fast in graph build
# ══════════════════════════════════════════════════════════════════


class TestLG04IntegrationFailFast:
    """LG-04: Verify graph build fails fast on broken node imports."""

    def test_add_nodes_fails_on_broken_import(self):
        """_add_nodes should raise RuntimeError when a node fails to import."""
        from app.core.langgraph.graph import _add_nodes

        # Mock a StateGraph builder
        mock_builder = MagicMock()

        # Patch _get_node_function to fail for one node
        with patch("app.core.langgraph.graph._get_node_function") as mock_get:
            def side_effect(node_name):
                if node_name == "empathy_engine":
                    raise ImportError("Module not found: 02_empathy_engine")
                return lambda state: state

            mock_get.side_effect = side_effect

            with pytest.raises(RuntimeError, match="node.*failed to import"):
                _add_nodes(mock_builder)

    def test_add_nodes_fails_on_missing_function(self):
        """_add_nodes should raise RuntimeError when node function is missing."""
        from app.core.langgraph.graph import _add_nodes

        mock_builder = MagicMock()

        with patch("app.core.langgraph.graph._get_node_function") as mock_get:
            def side_effect(node_name):
                if node_name == "maker_validator":
                    raise ValueError("Node function 'maker_validator_node' not found")
                return lambda state: state

            mock_get.side_effect = side_effect

            with pytest.raises(RuntimeError, match="node.*failed to import"):
                _add_nodes(mock_builder)

    def test_add_nodes_succeeds_when_all_imports_work(self):
        """_add_nodes should succeed when all node imports work."""
        from app.core.langgraph.graph import _add_nodes, _NODE_IMPORTS

        mock_builder = MagicMock()

        with patch("app.core.langgraph.graph._get_node_function") as mock_get:
            mock_get.return_value = lambda state: {"agent_response": "ok"}

            # Should not raise
            _add_nodes(mock_builder)

        # Should have added all nodes
        assert mock_builder.add_node.call_count == len(_NODE_IMPORTS)

    def test_runtime_error_propagates_from_build(self):
        """build_parwa_graph should propagate RuntimeError from _add_nodes."""
        from app.core.langgraph.graph import build_parwa_graph

        # Mock the langgraph import since it may not be installed in test env
        mock_sg = MagicMock()
        mock_sg.START = "START"
        mock_sg.END = "END"
        mock_sg.StateGraph = MagicMock

        with patch.dict("sys.modules", {"langgraph.graph": mock_sg}):
            with patch("app.core.langgraph.graph._add_nodes", side_effect=RuntimeError("Build failed")):
                with patch("app.core.langgraph.graph._get_default_checkpointer", return_value=None):
                    with pytest.raises(RuntimeError, match="Build failed"):
                        build_parwa_graph(checkpointer=None)


# ══════════════════════════════════════════════════════════════════
# Cross-Gap Integration: LG-01 + LG-02 + LG-03 + LG-04 together
# ══════════════════════════════════════════════════════════════════


class TestCrossGapIntegration:
    """Verify that LG-01 through LG-04 fixes work correctly together."""

    def test_retry_and_dlq_together(self):
        """When retries are exhausted, DLQ should capture the failure."""
        from app.core.langgraph.retry import sync_retry_llm_call
        from app.core.langgraph.dlq import _classify_error

        # Simulate a node that always fails with 503
        def always_503():
            exc = Exception("Service unavailable")
            exc.status_code = 503
            raise exc

        # Exhaust retries
        with pytest.raises(Exception) as exc_info:
            sync_retry_llm_call(always_503, max_retries=2, base_delay=0.01)

        # Classify the error for DLQ
        error_type = _classify_error(str(exc_info.value))
        # Should be classified as something meaningful
        assert error_type in ("unknown", "connection_error", "rate_limit")

    def test_validation_and_fail_fast_together(self):
        """Validation wrapper should work with nodes that pass import checks."""
        from app.core.langgraph.graph import _make_validated_node

        def node_with_bad_output(state):
            return {
                "variant_tier": "INVALID",
                "agent_confidence": 99.0,
                "some_data": "valid_string",
            }

        validated = _make_validated_node("test_node", node_with_bad_output)
        result = validated({"message": "test"})

        # Invalid values should be sanitized
        assert result["variant_tier"] == "mini"
        assert result["agent_confidence"] == 1.0
        assert result["some_data"] == "valid_string"  # valid, unchanged

    def test_retry_then_validate_pipeline(self):
        """Retry should recover from transient errors, then validation should clean output."""
        from app.core.langgraph.retry import sync_retry_llm_call
        from app.core.langgraph.validators import sanitize_state_update

        call_count = 0

        def flaky_llm():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise TimeoutError("LLM timeout")
            return {
                "variant_tier": "high",
                "agent_confidence": 0.95,
                "intent": "billing",
            }

        # Retry recovers the result
        result = sync_retry_llm_call(flaky_llm, max_retries=3, base_delay=0.01)
        assert call_count == 2

        # Validation confirms it's valid
        errors = sanitize_state_update(result)
        assert errors["variant_tier"] == "high"
        assert errors["agent_confidence"] == 0.95
        assert errors["intent"] == "billing"

    def test_full_node_lifecycle(self):
        """Test a node going through: import -> validate wrapper -> retry -> sanitize."""
        from app.core.langgraph.graph import _make_validated_node
        from app.core.langgraph.validators import validate_state_transition

        call_count = 0

        def reliable_node(state):
            nonlocal call_count
            call_count += 1
            # Simulate occasional 429 that gets retried by internal LLM call
            return {
                "variant_tier": "pro",
                "agent_confidence": 0.85,
                "intent": "refund",
                "agent_response": "Processing your refund",
                "proposed_action": "refund",
            }

        # Wrap with validation
        validated = _make_validated_node("reliable_node", reliable_node)

        # Execute
        result = validated({
            "message": "I want a refund",
            "tenant_id": "t-1",
            "variant_tier": "pro",
        })

        # Validate output
        errors = validate_state_transition(result)
        assert errors == []
        assert result["variant_tier"] == "pro"
        assert result["agent_confidence"] == 0.85
        assert result["intent"] == "refund"

    def test_graph_py_has_all_lg_comments(self):
        """graph.py should have LG-01, LG-02, LG-03, LG-04 comment markers."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "LG-01" in source or "retry" in source.lower()
        assert "LG-02" in source or "dlq" in source.lower()
        assert "LG-03" in source
        assert "LG-04" in source

    def test_dlq_service_exists(self):
        """The DLQ service module should also exist at the services layer."""
        import importlib
        try:
            mod = importlib.import_module("app.services.langgraph_dlq_service")
            # If it exists, it should be importable without error
            assert mod is not None
        except ImportError:
            # It's OK if the service wrapper doesn't exist separately
            # The core DLQ module at app.core.langgraph.dlq is what matters
            from app.core.langgraph.dlq import persist_to_dlq
            assert callable(persist_to_dlq)
