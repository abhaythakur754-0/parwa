"""Tests for the 7 gap fixes identified in the error handling audit.

GAP-1: reasoning_engine now uses ainvoke_llm() for retry+rate limiting
GAP-2: Rate limiter return value is now checked (timeout raises TimeoutError)
GAP-3: _build_error_result has inner try/except (never crashes)
GAP-4: _handle_loop_back now has @safe_node protection
GAP-5: aprocess_ticket catches graph.ainvoke failures
GAP-6: Rate limiter env var parsing safe on bad input
GAP-7: _merge_dicts concatenates append keys (pipeline_errors, active_frameworks)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from parwa.nodes.reasoning_engine import reasoning_engine


class TestGAP1ReasoningEngineUsesAinvokeLLM:
    """GAP-1 FIX: reasoning_engine now uses ainvoke_llm() for retry+rate limiting"""

    @pytest.mark.asyncio
    async def test_reasoning_llm_uses_ainvoke_llm(self):
        """reasoning_engine._reason_llm should call ainvoke_llm, not raw llm.ainvoke."""
        from parwa.nodes.reasoning_engine import _reason_llm
        import inspect
        source = inspect.getsource(_reason_llm)
        assert "ainvoke_llm" in source
        assert "llm.ainvoke" not in source

    @pytest.mark.asyncio
    async def test_reasoning_graceful_degradation_still_works(self):
        """When LLM fails, reasoning_engine should still degrade to rule-based."""
        with patch("parwa.nodes.reasoning_engine.MOCK_MODE", False):
            with patch("parwa.nodes.reasoning_engine._reason_llm", new_callable=AsyncMock) as mock_llm:
                mock_llm.side_effect = ConnectionError("LLM down")
                result = await reasoning_engine({
                    "raw_message": "I was charged twice",
                    "intent": "refund_request",
                    "faq_match": None, "kb_results": [], "integration_data": {},
                    "active_frameworks": [],
                })
                assert len(result["reasoning_chain"]) > 0
                assert result["reasoning_conclusion"] != ""


class TestGAP2RateLimiterTimeoutChecked:
    """GAP-2 FIX: Rate limiter return value is now checked"""

    @pytest.mark.asyncio
    async def test_sync_rate_limiter_timeout_raises(self):
        """If rate limiter acquire() returns False, TimeoutError should be raised."""
        from parwa.utils.llm import _invoke_llm
        with patch("parwa.utils.llm.get_llm_rate_limiter") as mock_get_limiter:
            mock_limiter = MagicMock()
            mock_limiter.acquire.return_value = False
            mock_get_limiter.return_value = mock_limiter
            with pytest.raises(TimeoutError, match="rate limiter timeout"):
                _invoke_llm(MagicMock(), "test prompt")

    @pytest.mark.asyncio
    async def test_async_rate_limiter_timeout_raises(self):
        """If rate limiter async_acquire() returns False, TimeoutError should be raised."""
        from parwa.utils.llm import _ainvoke_llm
        with patch("parwa.utils.llm.get_llm_rate_limiter") as mock_get_limiter:
            mock_limiter = MagicMock()
            mock_limiter.async_acquire = AsyncMock(return_value=False)
            mock_get_limiter.return_value = mock_limiter
            with pytest.raises(TimeoutError, match="rate limiter timeout"):
                await _ainvoke_llm(MagicMock(), "test prompt")


class TestGAP3BuildErrorResultProtected:
    """GAP-3 FIX: _build_error_result has inner try/except"""

    @pytest.mark.asyncio
    async def test_survives_corrupted_state(self):
        """Even if state is None, error result should still be produced."""
        from parwa.utils.node_base import _build_error_result
        result = _build_error_result(
            "TEST_NODE", RuntimeError("test"), {"key": "val"}, None, 0.1,
        )
        assert isinstance(result, dict)
        assert "node_error" in result
        assert result["node_error"]["node"] == "TEST_NODE"

    @pytest.mark.asyncio
    async def test_survives_non_dict_state(self):
        """If state is not a dict, _build_error_result should still return safe result."""
        from parwa.utils.node_base import _build_error_result
        result = _build_error_result(
            "TEST_NODE", RuntimeError("test"), {"key": "val"}, "not_a_dict", 0.1,
        )
        assert isinstance(result, dict)
        assert "pipeline_errors" in result


class TestGAP4LoopBackHandlerSafeNode:
    """GAP-4 FIX: _handle_loop_back now has @safe_node"""

    @pytest.mark.asyncio
    async def test_loop_back_handler_has_safe_node(self):
        """_handle_loop_back should be wrapped with @safe_node."""
        from parwa.graph import _handle_loop_back
        # @safe_node wraps the function
        assert hasattr(_handle_loop_back, "__wrapped__") or _handle_loop_back.__name__ != "_handle_loop_back"

    @pytest.mark.asyncio
    async def test_loop_back_handles_non_numeric_loop_count(self):
        """If loop_count is a string, guard should handle it gracefully."""
        from parwa.graph import _handle_loop_back
        result = await _handle_loop_back({"loop_count": "bad", "should_loop_back": True})
        assert isinstance(result, dict)
        assert "loop_count" in result


class TestGAP5AprocessTicketTopLevelCatch:
    """GAP-5 FIX: aprocess_ticket catches graph.ainvoke failures"""

    @pytest.mark.asyncio
    async def test_aprocess_ticket_catches_graph_failure(self):
        """If graph.ainvoke raises, aprocess_ticket should return error state."""
        from parwa.graph import aprocess_ticket, reset_parwa_graph
        reset_parwa_graph()
        with patch("parwa.graph.get_parwa_graph") as mock_get_graph:
            mock_graph = AsyncMock()
            mock_graph.ainvoke.side_effect = RuntimeError("Graph engine crash")
            mock_get_graph.return_value = mock_graph
            result = await aprocess_ticket(raw_message="test", variant="parwa")
            assert "error" in result or "final_response" in result
            if "pipeline_errors" in result:
                assert len(result["pipeline_errors"]) > 0


class TestGAP6EnvVarParsingSafe:
    """GAP-6 FIX: Rate limiter env var parsing does not crash on bad input"""

    def test_invalid_llm_rate_env_uses_default(self):
        """If PARWA_LLM_RATE is non-numeric, should use default without crashing."""
        import parwa.utils.rate_limiter as rl
        old_limiter = rl._llm_limiter
        rl._llm_limiter = None
        try:
            with patch.dict("os.environ", {"PARWA_LLM_RATE": "not_a_number"}):
                limiter = rl.get_llm_rate_limiter()
                assert limiter is not None
                assert limiter.rate == 60.0
        finally:
            rl._llm_limiter = old_limiter

    def test_invalid_api_rate_env_uses_default(self):
        """If PARWA_API_RATE is non-numeric, should use default without crashing."""
        import parwa.utils.rate_limiter as rl
        old_limiter = rl._api_limiter
        rl._api_limiter = None
        try:
            with patch.dict("os.environ", {"PARWA_API_RATE": "abc"}):
                limiter = rl.get_api_rate_limiter()
                assert limiter is not None
                assert limiter.rate == 120.0
        finally:
            rl._api_limiter = old_limiter


class TestGAP7MergeReducerConcatenatesAppendKeys:
    """GAP-7 FIX: _merge_dicts concatenates pipeline_errors and active_frameworks"""

    def test_pipeline_errors_concatenated(self):
        """pipeline_errors from two nodes should be concatenated, not replaced."""
        from parwa.graph import _merge_dicts
        left = {"pipeline_errors": [{"node": "A", "error": "err1"}]}
        right = {"pipeline_errors": [{"node": "B", "error": "err2"}]}
        result = _merge_dicts(left, right)
        assert len(result["pipeline_errors"]) == 2
        assert result["pipeline_errors"][0]["node"] == "A"
        assert result["pipeline_errors"][1]["node"] == "B"

    def test_active_frameworks_concatenated(self):
        """active_frameworks should be concatenated across nodes."""
        from parwa.graph import _merge_dicts
        left = {"active_frameworks": ["chain_of_thought"]}
        right = {"active_frameworks": ["reverse_thinking"]}
        result = _merge_dicts(left, right)
        assert len(result["active_frameworks"]) == 2
        assert "chain_of_thought" in result["active_frameworks"]
        assert "reverse_thinking" in result["active_frameworks"]

    def test_non_append_keys_replaced(self):
        """Non-append keys (like audit_log) should use replace semantics."""
        from parwa.graph import _merge_dicts
        left = {"audit_log": [{"entry": 1}]}
        right = {"audit_log": [{"entry": 1}, {"entry": 2}]}
        result = _merge_dicts(left, right)
        assert len(result["audit_log"]) == 2

    def test_non_list_values_replaced(self):
        """Non-list values should always be replaced."""
        from parwa.graph import _merge_dicts
        left = {"quality_score": 50.0, "intent": "general_inquiry"}
        right = {"quality_score": 90.0, "intent": "refund_request"}
        result = _merge_dicts(left, right)
        assert result["quality_score"] == 90.0
        assert result["intent"] == "refund_request"
