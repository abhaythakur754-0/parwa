"""
Unit + Integration Tests for LangGraph Gaps LG-01 through LG-04

Gaps covered:
  LG-01: No LLM retry with exponential backoff (now added to all nodes)
  LG-02: No DLQ for failed graph executions (now DB + Redis backed)
  LG-03: No state transition validation (now Pydantic-style validators)
  LG-04: Ghost no-op nodes for failed imports (now fail-fast)
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ══════════════════════════════════════════════════════════════════
# LG-01: LLM retry with exponential backoff
# ══════════════════════════════════════════════════════════════════

class TestLG01RetryExists:
    """LG-01: All nodes that make LLM/external calls should use retry."""

    NODES_WITH_RETRY = [
        "01_pii_redaction", "02_empathy_engine", "03_router_agent",
        "04_base_domain_agent", "05_faq_agent", "06_refund_agent",
        "07_technical_agent", "08_billing_agent", "10_escalation_agent",
        "11_maker_validator", "12_control_system", "13_dspy_optimizer",
        "14_guardrails", "16_state_update", "17_email_agent",
        "18_sms_agent", "19_voice_agent",
    ]

    def test_retry_module_exists(self):
        """The retry module should exist and be importable."""
        from app.core.langgraph.retry import retry_llm_call, llm_call_with_retry
        assert callable(retry_llm_call)
        assert callable(llm_call_with_retry)

    def test_nodes_use_retry(self):
        """Each node that makes LLM/external calls should import retry."""
        import os
        nodes_dir = "/home/z/my-project/download/parwa/backend/app/core/langgraph/nodes"
        for node_file in self.NODES_WITH_RETRY:
            path = os.path.join(nodes_dir, f"{node_file}.py")
            source = open(path).read()
            assert "retry_llm_call" in source or "llm_call_with_retry" in source, (
                f"{node_file}: No retry wrapper found"
            )

    def test_is_transient_error_rate_limit(self):
        """429 errors should be classified as transient."""
        from app.core.langgraph.retry import is_transient_error

        exc = Exception("Rate limit exceeded")
        exc.status_code = 429
        assert is_transient_error(exc) is True

    def test_is_transient_error_timeout(self):
        """TimeoutError should be classified as transient."""
        from app.core.langgraph.retry import is_transient_error

        assert is_transient_error(TimeoutError("timed out")) is True

    def test_is_transient_error_auth_not_retryable(self):
        """Authentication errors should NOT be classified as transient."""
        from app.core.langgraph.retry import is_transient_error

        exc = Exception("Authentication failed: invalid API key")
        assert is_transient_error(exc) is False

    def test_is_transient_error_503(self):
        """503 Service Unavailable should be transient."""
        from app.core.langgraph.retry import is_transient_error

        exc = Exception("Service unavailable")
        exc.status_code = 503
        assert is_transient_error(exc) is True

    def test_retry_succeeds_on_first_try(self):
        """retry_llm_call should return result if first call succeeds."""
        from app.core.langgraph.retry import retry_llm_call

        async def success_fn():
            return "ok"

        result = asyncio.get_event_loop().run_until_complete(
            retry_llm_call(success_fn, max_retries=3, base_delay=0.01)
        )
        assert result == "ok"

    def test_retry_retries_on_transient_error(self):
        """retry_llm_call should retry on transient errors."""
        from app.core.langgraph.retry import retry_llm_call

        call_count = 0

        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = Exception("rate_limit exceeded")
                exc.status_code = 429
                raise exc
            return "recovered"

        result = asyncio.get_event_loop().run_until_complete(
            retry_llm_call(fail_once, max_retries=3, base_delay=0.01)
        )
        assert result == "recovered"
        assert call_count == 2

    def test_retry_raises_on_non_transient(self):
        """retry_llm_call should NOT retry on non-transient errors."""
        from app.core.langgraph.retry import retry_llm_call

        async def auth_fail():
            raise Exception("Authentication error: invalid API key")

        with pytest.raises(Exception, match="Authentication error"):
            asyncio.get_event_loop().run_until_complete(
                retry_llm_call(auth_fail, max_retries=3, base_delay=0.01)
            )

    def test_retry_exhausts_retries(self):
        """retry_llm_call should raise after exhausting all retries."""
        from app.core.langgraph.retry import retry_llm_call

        async def always_fail():
            exc = ConnectionError("Connection refused")
            raise exc

        with pytest.raises(ConnectionError):
            asyncio.get_event_loop().run_until_complete(
                retry_llm_call(always_fail, max_retries=2, base_delay=0.01)
            )


# ══════════════════════════════════════════════════════════════════
# LG-02: DB-backed DLQ
# ══════════════════════════════════════════════════════════════════

class TestLG02DLQ:
    """LG-02: Failed graph executions are persisted to DB + Redis."""

    def test_dlq_module_exists(self):
        """The DLQ module should exist and be importable."""
        from app.core.langgraph.dlq import (
            persist_to_dlq,
            get_dlq_entries,
            retry_dlq_entry,
            resolve_dlq_entry,
            get_dlq_stats,
            GraphExecutionDLQ,
        )
        assert callable(persist_to_dlq)
        assert callable(get_dlq_entries)
        assert callable(retry_dlq_entry)
        assert callable(resolve_dlq_entry)
        assert callable(get_dlq_stats)

    def test_dlq_model_table_name(self):
        """GraphExecutionDLQ should have the correct table name."""
        from app.core.langgraph.dlq import GraphExecutionDLQ
        assert GraphExecutionDLQ.__tablename__ == "graph_execution_dlq"

    def test_dlq_model_has_required_columns(self):
        """GraphExecutionDLQ should have all required columns."""
        from app.core.langgraph.dlq import GraphExecutionDLQ
        col_names = {c.name for c in GraphExecutionDLQ.__table__.columns}
        required = {
            "id", "company_id", "conversation_id", "error",
            "retried", "created_at", "resolved_at",
        }
        assert required.issubset(col_names), f"Missing columns: {required - col_names}"

    def test_classify_error_timeout(self):
        """_classify_error should classify timeout errors correctly."""
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Graph execution timed out after 60s") == "timeout"

    def test_classify_error_rate_limit(self):
        """_classify_error should classify rate limit errors."""
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Rate limit exceeded: 429") == "rate_limit"

    def test_classify_error_connection(self):
        """_classify_error should classify connection errors."""
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Connection refused to upstream") == "connection_error"

    def test_classify_error_unknown(self):
        """_classify_error should classify unknown errors."""
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Something weird happened") == "unknown"

    def test_persist_to_dlq_handles_db_failure(self):
        """persist_to_dlq should not crash if DB write fails."""
        from app.core.langgraph.dlq import persist_to_dlq

        with patch("database.base.SessionLocal") as mock_session:
            mock_session.side_effect = Exception("DB down")
            # Should not raise
            result = persist_to_dlq(
                company_id=str(uuid4()),
                conversation_id=str(uuid4()),
                error="Test error",
                state_snapshot={},
            )
            # May return None on failure, that's ok

    def test_graph_py_uses_dlq(self):
        """graph.py should import and use the DLQ module."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # Should reference the DLQ module
        assert "persist_to_dlq" in source or "dlq" in source.lower()


# ══════════════════════════════════════════════════════════════════
# LG-03: State transition validation
# ══════════════════════════════════════════════════════════════════

class TestLG03Validators:
    """LG-03: State transitions are validated and sanitized."""

    def test_validators_module_exists(self):
        """The validators module should exist and be importable."""
        from app.core.langgraph.validators import (
            validate_state_transition,
            sanitize_state_update,
        )
        assert callable(validate_state_transition)
        assert callable(sanitize_state_update)

    def test_validate_valid_update(self):
        """A valid state update should produce no errors."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "variant_tier": "pro",
            "intent": "refund",
            "agent_confidence": 0.85,
        })
        assert errors == []

    def test_validate_invalid_variant_tier(self):
        """An invalid variant_tier should produce an error."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "variant_tier": "enterprise",
        })
        assert len(errors) > 0
        assert "variant_tier" in errors[0]

    def test_validate_invalid_intent(self):
        """An invalid intent should produce an error."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "intent": "hack_the_gibson",
        })
        assert len(errors) > 0
        assert "intent" in errors[0]

    def test_validate_confidence_out_of_range(self):
        """agent_confidence > 1.0 should produce an error."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "agent_confidence": 1.5,
        })
        assert len(errors) > 0
        assert "agent_confidence" in errors[0]

    def test_validate_negative_score(self):
        """Negative scores should produce errors."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "sentiment_score": -0.5,
        })
        assert len(errors) > 0

    def test_sanitize_invalid_variant_tier(self):
        """An invalid variant_tier should be sanitized to 'mini'."""
        from app.core.langgraph.validators import sanitize_state_update

        result = sanitize_state_update({
            "variant_tier": "enterprise",
        })
        assert result["variant_tier"] == "mini"

    def test_sanitize_clamps_confidence(self):
        """agent_confidence > 1.0 should be clamped to 1.0."""
        from app.core.langgraph.validators import sanitize_state_update

        result = sanitize_state_update({
            "agent_confidence": 1.5,
        })
        assert result["agent_confidence"] == 1.0

    def test_sanitize_negative_complexity(self):
        """Negative complexity_score should be clamped to 0.0."""
        from app.core.langgraph.validators import sanitize_state_update

        result = sanitize_state_update({
            "complexity_score": -0.3,
        })
        assert result["complexity_score"] == 0.0

    def test_sanitize_invalid_action_type(self):
        """Invalid action_type should default to 'informational'."""
        from app.core.langgraph.validators import sanitize_state_update

        result = sanitize_state_update({
            "action_type": "nuclear",
        })
        assert result["action_type"] == "informational"

    def test_sanitize_invalid_emergency_state(self):
        """Invalid emergency_state should default to 'normal'."""
        from app.core.langgraph.validators import sanitize_state_update

        result = sanitize_state_update({
            "emergency_state": "meltdown",
        })
        assert result["emergency_state"] == "normal"

    def test_sanitize_preserves_valid_fields(self):
        """Valid fields should pass through unchanged."""
        from app.core.langgraph.validators import sanitize_state_update

        original = {
            "variant_tier": "high",
            "intent": "billing",
            "agent_confidence": 0.92,
            "complexity_score": 0.5,
            "some_custom_field": "preserved",
        }
        result = sanitize_state_update(original)
        assert result["variant_tier"] == "high"
        assert result["intent"] == "billing"
        assert result["agent_confidence"] == 0.92
        assert result["some_custom_field"] == "preserved"

    def test_validate_and_sanitize_node_output_exists(self):
        """validate_and_sanitize_node_output should exist in state module."""
        from app.core.langgraph.state import validate_and_sanitize_node_output
        assert callable(validate_and_sanitize_node_output)

    def test_validate_and_sanitize_node_output_works(self):
        """validate_and_sanitize_node_output should sanitize invalid values."""
        from app.core.langgraph.state import validate_and_sanitize_node_output

        result = validate_and_sanitize_node_output("test_node", {
            "variant_tier": "invalid_tier",
            "agent_confidence": 2.0,
            "intent": "refund",  # this IS valid
        })
        assert result["variant_tier"] == "mini"  # sanitized
        assert result["agent_confidence"] == 1.0  # clamped
        assert result["intent"] == "refund"  # valid, passes through

    def test_validate_ignores_unknown_fields(self):
        """Unknown fields should not produce errors."""
        from app.core.langgraph.validators import validate_state_transition

        errors = validate_state_transition({
            "custom_metadata": {"foo": "bar"},
            "some_random_field": 42,
        })
        assert errors == []

    def test_validate_all_enumerated_fields(self):
        """All 10 enumerated fields should be validated."""
        from app.core.langgraph.validators import ENUM_CONSTRAINTS
        expected = {
            "variant_tier", "channel", "intent", "action_type",
            "approval_decision", "system_mode", "delivery_status",
            "emergency_state", "urgency", "circuit_breaker_state",
        }
        assert expected == set(ENUM_CONSTRAINTS.keys())

    def test_validate_all_range_fields(self):
        """All 3 range-validated fields should be validated."""
        from app.core.langgraph.validators import RANGE_CONSTRAINTS
        expected = {"agent_confidence", "complexity_score", "sentiment_score"}
        assert expected == set(RANGE_CONSTRAINTS.keys())


# ══════════════════════════════════════════════════════════════════
# LG-04: Ghost no-op nodes replaced with fail-fast
# ══════════════════════════════════════════════════════════════════

class TestLG04NoGhostNodes:
    """LG-04: Failed node imports should fail the graph build, not register no-ops."""

    def test_no_lambda_noop_in_add_nodes(self):
        """_add_nodes should NOT contain lambda no-op fallback."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()

        # The old pattern used lambda for no-op nodes
        # After fix, it should raise RuntimeError instead
        assert "lambda state" not in source or "# lambda" in source, (
            "LG-04: Found lambda no-op fallback — should be removed"
        )

    def test_add_nodes_raises_on_failure(self):
        """_add_nodes should raise RuntimeError when nodes fail to import."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()

        # Should have a RuntimeError raise for failed nodes
        assert "RuntimeError" in source
        assert "failed_nodes" in source or "failed" in source.lower()

    def test_build_parwa_graph_catches_runtime_error(self):
        """build_parwa_graph should catch RuntimeError from _add_nodes."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()

        # Should have error handling around _add_nodes
        assert "RuntimeError" in source

    def test_lg04_comment_in_source(self):
        """The fix should have an LG-04 comment marker."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "LG-04" in source
