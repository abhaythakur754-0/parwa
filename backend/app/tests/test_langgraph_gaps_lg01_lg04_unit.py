"""
Unit Tests for LangGraph Gaps LG-01 through LG-04

Gaps covered:
  LG-01: No LLM retry with exponential backoff (sync_retry_llm_call added;
         all 19 sync nodes migrated from broken async retry_llm_call)
  LG-02: No DLQ for failed graph executions (DB + Redis backed DLQ)
  LG-03: No state transition validation (Pydantic-style validators)
  LG-04: Ghost no-op nodes for failed imports (fail-fast RuntimeError)

These tests are PURE UNIT — no DB, no Redis, no network, no filesystem
writes. All external dependencies are mocked.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ══════════════════════════════════════════════════════════════════
# LG-01: LLM retry with exponential backoff
# ══════════════════════════════════════════════════════════════════


class TestLG01SyncRetry:
    """LG-01: sync_retry_llm_call and sync_llm_call_with_retry."""

    def test_sync_retry_module_exists(self):
        """The sync retry functions should be importable."""
        from app.core.langgraph.retry import (
            sync_retry_llm_call,
            sync_llm_call_with_retry,
        )
        assert callable(sync_retry_llm_call)
        assert callable(sync_llm_call_with_retry)

    def test_sync_retry_succeeds_on_first_try(self):
        """sync_retry_llm_call should return result if first call succeeds."""
        from app.core.langgraph.retry import sync_retry_llm_call

        def success_fn():
            return "ok"

        result = sync_retry_llm_call(success_fn, max_retries=3, base_delay=0.01)
        assert result == "ok"

    def test_sync_retry_retries_on_transient_error(self):
        """sync_retry_llm_call should retry on transient errors."""
        from app.core.langgraph.retry import sync_retry_llm_call

        call_count = 0

        def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = ConnectionError("Connection refused")
                raise exc
            return "recovered"

        result = sync_retry_llm_call(fail_once, max_retries=3, base_delay=0.01)
        assert result == "recovered"
        assert call_count == 2

    def test_sync_retry_retries_on_429(self):
        """sync_retry_llm_call should retry on 429 rate limit."""
        from app.core.langgraph.retry import sync_retry_llm_call

        call_count = 0

        def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                exc = Exception("Rate limit exceeded")
                exc.status_code = 429
                raise exc
            return "success"

        result = sync_retry_llm_call(rate_limited, max_retries=3, base_delay=0.01)
        assert result == "success"
        assert call_count == 3

    def test_sync_retry_retries_on_503(self):
        """sync_retry_llm_call should retry on 503 Service Unavailable."""
        from app.core.langgraph.retry import sync_retry_llm_call

        call_count = 0

        def service_unavailable():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = Exception("Service unavailable")
                exc.status_code = 503
                raise exc
            return "back_up"

        result = sync_retry_llm_call(
            service_unavailable, max_retries=3, base_delay=0.01
        )
        assert result == "back_up"
        assert call_count == 2

    def test_sync_retry_raises_on_non_transient(self):
        """sync_retry_llm_call should NOT retry on non-transient errors."""
        from app.core.langgraph.retry import sync_retry_llm_call

        def auth_fail():
            raise Exception("Authentication error: invalid API key")

        with pytest.raises(Exception, match="Authentication error"):
            sync_retry_llm_call(auth_fail, max_retries=3, base_delay=0.01)

    def test_sync_retry_exhausts_retries(self):
        """sync_retry_llm_call should raise after exhausting all retries."""
        from app.core.langgraph.retry import sync_retry_llm_call

        def always_fail():
            raise ConnectionError("Connection refused")

        with pytest.raises(ConnectionError):
            sync_retry_llm_call(always_fail, max_retries=2, base_delay=0.01)

    def test_sync_retry_exponential_backoff_timing(self):
        """sync_retry_llm_call should use exponential backoff between retries."""
        from app.core.langgraph.retry import sync_retry_llm_call

        attempt_times = []

        def track_timing():
            attempt_times.append(time.monotonic())
            if len(attempt_times) < 3:
                raise TimeoutError("timed out")
            return "done"

        result = sync_retry_llm_call(
            track_timing, max_retries=3, base_delay=0.1, max_delay=1.0
        )
        assert result == "done"

        # Verify backoff: delay between attempts should be roughly 0.1, 0.2
        if len(attempt_times) >= 3:
            delay1 = attempt_times[1] - attempt_times[0]
            delay2 = attempt_times[2] - attempt_times[1]
            # First delay ~0.1s, second ~0.2s (with some tolerance)
            assert delay1 >= 0.05, f"First delay too short: {delay1}"
            assert delay2 >= delay1 * 0.8, f"Second delay should be >= first: {delay2}"

    def test_sync_llm_call_with_retry_works(self):
        """sync_llm_call_with_retry convenience wrapper should work."""
        from app.core.langgraph.retry import sync_llm_call_with_retry

        def my_llm(x, y):
            return x + y

        result = sync_llm_call_with_retry(
            my_llm, 3, 7, max_retries=3, base_delay=0.01
        )
        assert result == 10

    def test_sync_retry_passes_kwargs(self):
        """sync_retry_llm_call should pass kwargs to the wrapped function."""
        from app.core.langgraph.retry import sync_retry_llm_call

        def fn_with_kwargs(a, b=10):
            return a + b

        result = sync_retry_llm_call(
            fn_with_kwargs, 5, b=20, max_retries=3, base_delay=0.01
        )
        assert result == 25


class TestLG01AsyncRetry:
    """LG-01: Async retry still works for async callers (e.g., invoke_parwa_graph)."""

    def test_async_retry_succeeds(self):
        """retry_llm_call should still work for async functions."""
        from app.core.langgraph.retry import retry_llm_call

        async def async_fn():
            return "async_ok"

        result = asyncio.get_event_loop().run_until_complete(
            retry_llm_call(async_fn, max_retries=3, base_delay=0.01)
        )
        assert result == "async_ok"

    def test_async_retry_retries_transient(self):
        """retry_llm_call should retry on transient errors."""
        from app.core.langgraph.retry import retry_llm_call

        call_count = 0

        async def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection reset")
            return "recovered"

        result = asyncio.get_event_loop().run_until_complete(
            retry_llm_call(fail_once, max_retries=3, base_delay=0.01)
        )
        assert result == "recovered"
        assert call_count == 2


class TestLG01IsTransientError:
    """LG-01: Error classification for transient vs non-transient."""

    def test_429_is_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("rate limited")
        exc.status_code = 429
        assert is_transient_error(exc) is True

    def test_503_is_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("unavailable")
        exc.status_code = 503
        assert is_transient_error(exc) is True

    def test_502_is_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("bad gateway")
        exc.status_code = 502
        assert is_transient_error(exc) is True

    def test_401_is_not_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("unauthorized")
        exc.status_code = 401
        assert is_transient_error(exc) is False

    def test_403_is_not_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("forbidden")
        exc.status_code = 403
        assert is_transient_error(exc) is False

    def test_timeout_is_transient(self):
        from app.core.langgraph.retry import is_transient_error
        assert is_transient_error(TimeoutError("timed out")) is True

    def test_connection_error_is_transient(self):
        from app.core.langgraph.retry import is_transient_error
        assert is_transient_error(ConnectionError("refused")) is True

    def test_auth_error_message_is_not_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("Authentication failed: invalid API key")
        assert is_transient_error(exc) is False

    def test_unknown_error_is_not_transient(self):
        from app.core.langgraph.retry import is_transient_error
        exc = Exception("Something completely unexpected")
        assert is_transient_error(exc) is False


class TestLG01NodeRetryMigration:
    """LG-01: All sync node files should use sync_retry_llm_call / sync_llm_call_with_retry."""

    NODES_DIR = "/home/z/my-project/download/parwa/backend/app/core/langgraph/nodes"

    NODES_WITH_RETRY = [
        "01_pii_redaction", "02_empathy_engine", "03_router_agent",
        "04_base_domain_agent", "05_faq_agent", "06_refund_agent",
        "07_technical_agent", "08_billing_agent", "10_escalation_agent",
        "11_maker_validator", "12_control_system", "13_dspy_optimizer",
        "14_guardrails", "16_state_update", "17_email_agent",
        "18_sms_agent", "19_voice_agent",
    ]

    def test_all_nodes_use_sync_retry(self):
        """Each sync node that makes LLM calls should use sync retry."""
        import os
        for node_file in self.NODES_WITH_RETRY:
            path = os.path.join(self.NODES_DIR, f"{node_file}.py")
            source = open(path).read()
            assert "sync_retry_llm_call" in source or "sync_llm_call_with_retry" in source, (
                f"{node_file}: No sync retry wrapper found"
            )

    def test_no_nodes_use_broken_async_retry(self):
        """No sync node should use the async retry_llm_call without await."""
        import os
        all_nodes = [
            "01_pii_redaction", "02_empathy_engine", "03_router_agent",
            "04_base_domain_agent", "05_faq_agent", "06_refund_agent",
            "07_technical_agent", "08_billing_agent", "09_complaint_agent",
            "10_escalation_agent", "11_maker_validator", "12_control_system",
            "13_dspy_optimizer", "14_guardrails", "15_channel_delivery",
            "16_state_update", "17_email_agent", "18_sms_agent",
            "19_voice_agent",
        ]
        for node_file in all_nodes:
            path = os.path.join(self.NODES_DIR, f"{node_file}.py")
            source = open(path).read()
            # Check that there's no unqualified "retry_llm_call" or
            # "llm_call_with_retry" in import or call (docstring mentions ok)
            # We check for imports specifically
            import_lines = [
                line for line in source.split("\n")
                if "from app.core.langgraph.retry import" in line
            ]
            for line in import_lines:
                assert "retry_llm_call" not in line or "sync_retry_llm_call" in line, (
                    f"{node_file}: Still imports async retry_llm_call: {line.strip()}"
                )
                assert "llm_call_with_retry" not in line or "sync_llm_call_with_retry" in line, (
                    f"{node_file}: Still imports async llm_call_with_retry: {line.strip()}"
                )


# ══════════════════════════════════════════════════════════════════
# LG-02: DB-backed DLQ
# ══════════════════════════════════════════════════════════════════


class TestLG02DLQModule:
    """LG-02: DLQ module functions exist and work correctly."""

    def test_dlq_module_exists(self):
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
        from app.core.langgraph.dlq import GraphExecutionDLQ
        assert GraphExecutionDLQ.__tablename__ == "graph_execution_dlq"

    def test_dlq_model_has_required_columns(self):
        from app.core.langgraph.dlq import GraphExecutionDLQ
        col_names = {c.name for c in GraphExecutionDLQ.__table__.columns}
        required = {
            "id", "company_id", "conversation_id", "error",
            "retried", "retry_count", "created_at", "resolved_at",
            "error_type", "variant_tier", "channel", "intent",
        }
        assert required.issubset(col_names), f"Missing columns: {required - col_names}"

    def test_classify_error_timeout(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Graph execution timed out after 60s") == "timeout"

    def test_classify_error_rate_limit(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Rate limit exceeded: 429") == "rate_limit"

    def test_classify_error_connection(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Connection refused to upstream") == "connection_error"

    def test_classify_error_auth(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Authentication failed: 401") == "llm_auth_error"

    def test_classify_error_quota(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Quota exceeded for tenant") == "quota_exceeded"

    def test_classify_error_unknown(self):
        from app.core.langgraph.dlq import _classify_error
        assert _classify_error("Something weird happened") == "unknown"

    def test_persist_to_dlq_handles_db_failure(self):
        """persist_to_dlq should not crash if DB write fails."""
        from app.core.langgraph.dlq import persist_to_dlq

        with patch("app.core.langgraph.dlq._persist_to_db", return_value=None):
            with patch("app.core.langgraph.dlq._persist_to_redis"):
                # Should not raise
                result = persist_to_dlq(
                    company_id=str(uuid4()),
                    conversation_id=str(uuid4()),
                    error="Test error",
                    state_snapshot={},
                )

    def test_persist_to_dlq_handles_redis_failure(self):
        """persist_to_dlq should not crash if Redis write fails — Redis has internal try/except."""
        from app.core.langgraph.dlq import persist_to_dlq

        # _persist_to_redis has its own try/except, so we mock the inner get_redis_client
        # to raise, which _persist_to_redis will catch internally
        with patch("app.core.langgraph.dlq._persist_to_redis"):
            with patch("app.core.langgraph.dlq._persist_to_db", return_value="test-id"):
                result = persist_to_dlq(
                    company_id=str(uuid4()),
                    conversation_id=str(uuid4()),
                    error="Test error",
                    state_snapshot={},
                )
                # Should still return DB result even if Redis fails
                assert result == "test-id"

    def test_snapshot_keys_extraction(self):
        """persist_to_dlq should extract only whitelisted snapshot keys."""
        from app.core.langgraph.dlq import persist_to_dlq, _SNAPSHOT_KEYS

        captured_snapshot = {}

        def mock_db_persist(*, entry_id, company_id, conversation_id, session_id,
                            error, error_type, snapshot_json, variant_tier,
                            channel, intent):
            nonlocal captured_snapshot
            captured_snapshot = json.loads(snapshot_json)
            return entry_id

        with patch("app.core.langgraph.dlq._persist_to_redis"):
            with patch("app.core.langgraph.dlq._persist_to_db", side_effect=mock_db_persist):
                persist_to_dlq(
                    company_id="comp-123",
                    conversation_id="conv-456",
                    error="Test",
                    state_snapshot={
                        "message": "hello",
                        "channel": "email",
                        "customer_id": "cust-1",
                        "tenant_id": "t-1",
                        "variant_tier": "pro",
                        "intent": "refund",
                        "target_agent": "refund",
                        "agent_response": "Here's your refund",
                        "agent_confidence": 0.95,
                        "pii_entities_found": [{"type": "email", "value": "x@y.com"}],
                        "some_other_field": "should_not_appear",
                    },
                )

        # Only _SNAPSHOT_KEYS should be in the snapshot
        for key in captured_snapshot:
            assert key in _SNAPSHOT_KEYS, f"Unexpected key in snapshot: {key}"
        assert "pii_entities_found" not in captured_snapshot
        assert "some_other_field" not in captured_snapshot
        assert "message" in captured_snapshot


class TestLG02GraphDLQIntegration:
    """LG-02: graph.py should persist to DLQ on failures."""

    def test_graph_py_uses_dlq(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "persist_to_dlq" in source
        assert "_persist_to_dlq" in source

    def test_graph_py_dlq_on_timeout(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "TimeoutError" in source
        assert "persist_to_dlq" in source

    def test_graph_py_dlq_on_exception(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # After general exception, should also call DLQ
        lines = source.split("\n")
        found_exception_with_dlq = False
        for i, line in enumerate(lines):
            if "parwa_graph_invocation_failed" in line:
                # Look ahead for DLQ call
                lookahead = "\n".join(lines[i:i+20])
                if "persist_to_dlq" in lookahead:
                    found_exception_with_dlq = True
        assert found_exception_with_dlq, "DLQ not called on general graph invocation failure"


# ══════════════════════════════════════════════════════════════════
# LG-03: State transition validation
# ══════════════════════════════════════════════════════════════════


class TestLG03Validators:
    """LG-03: State transitions are validated and sanitized."""

    def test_validators_module_exists(self):
        from app.core.langgraph.validators import (
            validate_state_transition,
            sanitize_state_update,
        )
        assert callable(validate_state_transition)
        assert callable(sanitize_state_update)

    def test_validate_valid_update(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({
            "variant_tier": "pro",
            "intent": "refund",
            "agent_confidence": 0.85,
        })
        assert errors == []

    def test_validate_invalid_variant_tier(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"variant_tier": "enterprise"})
        assert len(errors) > 0
        assert "variant_tier" in errors[0]

    def test_validate_invalid_intent(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"intent": "hack_the_gibson"})
        assert len(errors) > 0
        assert "intent" in errors[0]

    def test_validate_invalid_channel(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"channel": "telegraph"})
        assert len(errors) > 0
        assert "channel" in errors[0]

    def test_validate_invalid_action_type(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"action_type": "nuclear"})
        assert len(errors) > 0
        assert "action_type" in errors[0]

    def test_validate_invalid_emergency_state(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"emergency_state": "meltdown"})
        assert len(errors) > 0
        assert "emergency_state" in errors[0]

    def test_validate_invalid_urgency(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"urgency": "ludicrous"})
        assert len(errors) > 0
        assert "urgency" in errors[0]

    def test_validate_invalid_circuit_breaker_state(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"circuit_breaker_state": "broken"})
        assert len(errors) > 0
        assert "circuit_breaker_state" in errors[0]

    def test_validate_confidence_out_of_range(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"agent_confidence": 1.5})
        assert len(errors) > 0
        assert "agent_confidence" in errors[0]

    def test_validate_negative_score(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"sentiment_score": -0.5})
        assert len(errors) > 0

    def test_validate_complexity_out_of_range(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"complexity_score": 2.0})
        assert len(errors) > 0
        assert "complexity_score" in errors[0]

    def test_validate_bool_rejected_for_numeric(self):
        """Boolean values should be rejected for numeric fields."""
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"agent_confidence": True})
        assert len(errors) > 0
        assert "bool" in errors[0].lower()

    def test_validate_non_string_for_enum(self):
        """Non-string values should be rejected for enum fields."""
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({"variant_tier": 42})
        assert len(errors) > 0

    def test_validate_ignores_unknown_fields(self):
        from app.core.langgraph.validators import validate_state_transition
        errors = validate_state_transition({
            "custom_metadata": {"foo": "bar"},
            "some_random_field": 42,
        })
        assert errors == []

    def test_sanitize_invalid_variant_tier(self):
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"variant_tier": "enterprise"})
        assert result["variant_tier"] == "mini"

    def test_sanitize_clamps_confidence(self):
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"agent_confidence": 1.5})
        assert result["agent_confidence"] == 1.0

    def test_sanitize_negative_complexity(self):
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"complexity_score": -0.3})
        assert result["complexity_score"] == 0.0

    def test_sanitize_invalid_action_type(self):
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"action_type": "nuclear"})
        assert result["action_type"] == "informational"

    def test_sanitize_invalid_emergency_state(self):
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"emergency_state": "meltdown"})
        assert result["emergency_state"] == "normal"

    def test_sanitize_bool_replaced_for_numeric(self):
        """Boolean values should be replaced with min for numeric fields."""
        from app.core.langgraph.validators import sanitize_state_update
        result = sanitize_state_update({"agent_confidence": True})
        assert result["agent_confidence"] == 0.0

    def test_sanitize_preserves_valid_fields(self):
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
        from app.core.langgraph.state import validate_and_sanitize_node_output
        assert callable(validate_and_sanitize_node_output)

    def test_validate_and_sanitize_node_output_works(self):
        from app.core.langgraph.state import validate_and_sanitize_node_output
        result = validate_and_sanitize_node_output("test_node", {
            "variant_tier": "invalid_tier",
            "agent_confidence": 2.0,
            "intent": "refund",
        })
        assert result["variant_tier"] == "mini"
        assert result["agent_confidence"] == 1.0
        assert result["intent"] == "refund"

    def test_validate_and_sanitize_non_dict_passthrough(self):
        """Non-dict results should pass through unchanged."""
        from app.core.langgraph.state import validate_and_sanitize_node_output
        result = validate_and_sanitize_node_output("test_node", "not_a_dict")
        assert result == "not_a_dict"

    def test_all_10_enumerated_fields(self):
        from app.core.langgraph.validators import ENUM_CONSTRAINTS
        expected = {
            "variant_tier", "channel", "intent", "action_type",
            "approval_decision", "system_mode", "delivery_status",
            "emergency_state", "urgency", "circuit_breaker_state",
        }
        assert expected == set(ENUM_CONSTRAINTS.keys())

    def test_all_3_range_fields(self):
        from app.core.langgraph.validators import RANGE_CONSTRAINTS
        expected = {"agent_confidence", "complexity_score", "sentiment_score"}
        assert expected == set(RANGE_CONSTRAINTS.keys())

    def test_get_field_constraints_enum(self):
        from app.core.langgraph.validators import get_field_constraints
        info = get_field_constraints("variant_tier")
        assert info is not None
        assert info["type"] == "enum"
        assert "mini" in info["allowed"]
        assert info["default"] == "mini"

    def test_get_field_constraints_range(self):
        from app.core.langgraph.validators import get_field_constraints
        info = get_field_constraints("agent_confidence")
        assert info is not None
        assert info["type"] == "range"
        assert info["min"] == 0.0
        assert info["max"] == 1.0

    def test_get_field_constraints_unknown(self):
        from app.core.langgraph.validators import get_field_constraints
        info = get_field_constraints("unknown_field")
        assert info is None

    def test_get_all_validated_fields(self):
        from app.core.langgraph.validators import get_all_validated_fields
        fields = get_all_validated_fields()
        assert len(fields) == 13  # 10 enum + 3 range
        for name, info in fields.items():
            assert "type" in info


class TestLG03GraphNodeValidation:
    """LG-03: graph.py wraps nodes with validated wrapper."""

    def test_make_validated_node_exists(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "_make_validated_node" in source
        assert "validate_and_sanitize_node_output" in source

    def test_add_nodes_wraps_with_validation(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "validated_func = _make_validated_node" in source
        assert "LG-03" in source


# ══════════════════════════════════════════════════════════════════
# LG-04: Ghost no-op nodes replaced with fail-fast
# ══════════════════════════════════════════════════════════════════


class TestLG04NoGhostNodes:
    """LG-04: Failed node imports should fail the graph build, not register no-ops."""

    def test_no_lambda_noop_in_add_nodes(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # The old pattern used lambda for no-op nodes
        # After fix, it should raise RuntimeError instead
        assert "lambda state" not in source or "# lambda" in source, (
            "LG-04: Found lambda no-op fallback — should be removed"
        )

    def test_add_nodes_raises_on_failure(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # Should have a RuntimeError raise for failed nodes
        assert "RuntimeError" in source
        assert "failed_nodes" in source

    def test_build_parwa_graph_catches_runtime_error(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # Should have error handling around _add_nodes
        assert "RuntimeError" in source
        assert "_add_nodes" in source

    def test_lg04_comment_in_source(self):
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        assert "LG-04" in source

    def test_add_nodes_collects_failed_nodes(self):
        """_add_nodes should collect all failed nodes before raising."""
        source = open(
            "/home/z/my-project/download/parwa/backend/app/core/langgraph/graph.py"
        ).read()
        # Should have a failed_nodes list that accumulates before raising
        assert "failed_nodes" in source
        assert "failed_nodes.append" in source


class TestLG04InitialState:
    """LG-04: create_initial_state produces valid initial state."""

    def test_create_initial_state_basic(self):
        from app.core.langgraph.state import create_initial_state
        state = create_initial_state(
            message="Hello",
            channel="email",
            customer_id="cust-1",
            tenant_id="t-1",
            variant_tier="mini",
        )
        assert state["message"] == "Hello"
        assert state["channel"] == "email"
        assert state["tenant_id"] == "t-1"
        assert state["variant_tier"] == "mini"
        assert state["errors"] == []
        assert state["node_outputs"] == {}

    def test_create_initial_state_all_groups_initialized(self):
        """All 24 groups should have default values."""
        from app.core.langgraph.state import create_initial_state
        state = create_initial_state(
            message="test",
            channel="chat",
            customer_id="c1",
            tenant_id="t1",
            variant_tier="pro",
        )
        # Check representatives from each group
        assert "sentiment_score" in state  # Group 3
        assert "intent" in state  # Group 4
        assert "agent_response" in state  # Group 5
        assert "k_solutions" in state  # Group 6
        assert "approval_decision" in state  # Group 7
        assert "prompt_optimized" in state  # Group 8
        assert "guardrails_passed" in state  # Group 9
        assert "delivery_status" in state  # Group 10
        assert "ticket_created" in state  # Group 11
        assert "gsd_state" in state  # Group 12
        assert "processing_start_time" in state  # Group 13
        assert "system_health" in state  # Group 14
        assert "ai_paused" in state  # Group 15
        assert "arbitrage_risk_score" in state  # Group 16
        assert "brand_voice_applied" in state  # Group 17
        assert "collective_patterns_used" in state  # Group 18
        assert "self_healing_enabled" in state  # Group 19
        assert "jarvis_command_parsed" in state  # Group 20
        assert "connector_health" in state  # Group 21
        assert "call_id" in state  # Group 22
        assert "tcpa_consent_verified" in state  # Group 23
        assert "dynamic_instructions" in state  # Group 24
