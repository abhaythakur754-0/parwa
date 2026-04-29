"""Tests for DSPy Integration (dspy_integration.py)

Covers:
- is_available (both with and without DSPy)
- Signature definitions
- Module creation
- Optimization
- Execute with stub module
- Bridge to/from PARWA
- Per-tenant configuration
- Metrics tracking
- Graceful fallback when DSPy not installed
- Edge cases

Target: 45+ tests
"""

from __future__ import annotations

import pytest
from app.core.dspy_integration import (
    _DSPY_AVAILABLE,
    PREDEFINED_SIGNATURES,
    DSPyIntegration,
    StubModule,
    StubPrediction,
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def dspy() -> DSPyIntegration:
    d = DSPyIntegration()
    d.reset_metrics()
    yield d
    d.reset_metrics()


@pytest.fixture
def mock_conversation_state():
    """Create a mock ConversationState for bridge tests."""
    from app.core.techniques.base import (
        ConversationState,
        GSDState,
    )

    state = ConversationState(
        query="I want a refund for my order",
        gsd_state=GSDState.DIAGNOSIS,
        ticket_id="tkt_001",
        conversation_id="conv_001",
        company_id="co_test",
    )
    state.gsd_history = [
        GSDState.NEW,
        GSDState.GREETING,
        GSDState.DIAGNOSIS,
    ]
    state.technique_results = {"clara": {"status": "success"}}
    return state


COMPANY_ID = "co_test_dspy"


# ═══════════════════════════════════════════════════════════════════
# 1. Availability
# ═══════════════════════════════════════════════════════════════════


class TestAvailability:

    def test_is_available_returns_bool(self, dspy):
        result = DSPyIntegration.is_available()
        assert isinstance(result, bool)

    def test_is_available_reflects_dspy(self, dspy):
        assert DSPyIntegration.is_available() == _DSPY_AVAILABLE

    def test_stub_module_exists(self):
        stub = StubModule(task_type="test")
        assert stub.task_type == "test"

    def test_stub_prediction_exists(self):
        pred = StubPrediction(task_type="classify")
        assert pred.task_type == "classify"
        assert pred.response == ""
        assert pred.confidence == 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. Signature Definitions
# ═══════════════════════════════════════════════════════════════════


class TestSignatureDefinitions:

    def test_predefined_has_classify(self):
        assert "classify" in PREDEFINED_SIGNATURES

    def test_predefined_has_respond(self):
        assert "respond" in PREDEFINED_SIGNATURES

    def test_predefined_has_summarize(self):
        assert "summarize" in PREDEFINED_SIGNATURES

    def test_predefined_has_escalate(self):
        assert "escalate" in PREDEFINED_SIGNATURES

    def test_classify_has_inputs(self):
        sig = PREDEFINED_SIGNATURES["classify"]
        assert "customer_query" in sig.inputs
        assert "context" in sig.inputs

    def test_classify_has_outputs(self):
        sig = PREDEFINED_SIGNATURES["classify"]
        assert "intent" in sig.outputs
        assert "confidence" in sig.outputs

    def test_define_signature_predefined(self, dspy):
        sig = dspy.define_signature("classify")
        assert sig is not None

    def test_define_signature_custom(self, dspy):
        sig = dspy.define_signature(
            "custom_task",
            inputs=["query", "context"],
            outputs=["answer"],
        )
        assert sig is not None

    def test_define_signature_custom_fields(self, dspy):
        sig = dspy.define_signature(
            "custom",
            inputs=["a", "b"],
            outputs=["c"],
        )
        if hasattr(sig, "inputs"):
            assert "a" in sig.inputs
            assert "b" in sig.inputs

    def test_define_signature_overrides_predefined(self, dspy):
        sig = dspy.define_signature(
            "classify",
            inputs=["custom_input"],
            outputs=["custom_output"],
        )
        assert sig is not None


# ═══════════════════════════════════════════════════════════════════
# 3. Module Creation
# ═══════════════════════════════════════════════════════════════════


class TestModuleCreation:

    def test_create_module_classify(self, dspy):
        module = dspy.create_module("classify")
        assert module is not None

    def test_create_module_respond(self, dspy):
        module = dspy.create_module("respond")
        assert module is not None

    def test_create_module_unknown_type(self, dspy):
        module = dspy.create_module("unknown_task_xyz")
        assert module is not None

    def test_create_module_returns_stub_when_no_dspy(self, dspy):
        module = dspy.create_module("classify")
        if not _DSPY_AVAILABLE:
            assert isinstance(module, StubModule)

    def test_create_module_with_config(self, dspy):
        module = dspy.create_module(
            "classify",
            config={"num_candidates": 3},
        )
        assert module is not None


# ═══════════════════════════════════════════════════════════════════
# 4. Execution
# ═══════════════════════════════════════════════════════════════════


class TestExecution:

    def test_execute_stub_module(self, dspy):
        stub = StubModule(task_type="classify")
        result = dspy.execute(stub, {"customer_query": "hello"})
        assert isinstance(result, dict)
        assert "response" in result

    def test_execute_has_fallback_response(self, dspy):
        stub = StubModule()
        result = dspy.execute(stub, {"customer_query": "refund please"})
        assert "Fallback" in result.get("response", "")
        assert result.get("confidence") == 0.5

    def test_execute_records_metric(self, dspy):
        dspy.reset_metrics()
        stub = StubModule()
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 1

    def test_execute_records_latency(self, dspy):
        dspy.reset_metrics()
        stub = StubModule()
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["avg_latency_ms"] >= 0

    def test_execute_with_empty_inputs(self, dspy):
        stub = StubModule()
        result = dspy.execute(stub, {})
        assert isinstance(result, dict)

    def test_execute_stub_always_succeeds(self, dspy):
        dspy.reset_metrics()
        stub = StubModule()
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["success_rate"] == 100.0


# ═══════════════════════════════════════════════════════════════════
# 5. Bridge to PARWA
# ═══════════════════════════════════════════════════════════════════


class TestBridgeToParwa:

    def test_bridge_maps_response(self, dspy, mock_conversation_state):
        dspy_output = {"response": "Here is your refund info."}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["final_response"] == "Here is your refund info."

    def test_bridge_maps_confidence(self, dspy, mock_conversation_state):
        dspy_output = {"confidence": 0.95}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["signals_confidence"] == 0.95

    def test_bridge_maps_intent(self, dspy, mock_conversation_state):
        dspy_output = {"intent": "refund"}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["signals_intent"] == "refund"

    def test_bridge_maps_follow_up(self, dspy, mock_conversation_state):
        dspy_output = {"follow_up_needed": True}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["follow_up_needed"] is True

    def test_bridge_maps_escalation(self, dspy, mock_conversation_state):
        dspy_output = {"should_escalate": True}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["should_escalate"] is True

    def test_bridge_maps_summary(self, dspy, mock_conversation_state):
        dspy_output = {"summary": "Customer wants refund."}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert updates["summary"] == "Customer wants refund."

    def test_bridge_empty_output(self, dspy, mock_conversation_state):
        updates = dspy.bridge_to_parwa({}, mock_conversation_state)
        assert updates == {}

    def test_bridge_invalid_confidence_ignored(self, dspy, mock_conversation_state):
        dspy_output = {"confidence": "not_a_number"}
        updates = dspy.bridge_to_parwa(dspy_output, mock_conversation_state)
        assert "signals_confidence" not in updates


# ═══════════════════════════════════════════════════════════════════
# 6. Bridge from PARWA
# ═══════════════════════════════════════════════════════════════════


class TestBridgeFromParwa:

    def test_bridge_extracts_query(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert inputs["customer_query"] == "I want a refund for my order"

    def test_bridge_extracts_gsd_state(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert inputs["gsd_state"] == "diagnosis"

    def test_bridge_extracts_conversation_history(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert "conversation_history" in inputs
        assert len(inputs["conversation_history"]) == 3

    def test_bridge_extracts_signals(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert "context" in inputs
        assert "frustration_score" in inputs
        assert "sentiment_score" in inputs
        assert "intent" in inputs
        assert "query_complexity" in inputs

    def test_bridge_has_input_alias(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert "input" in inputs
        assert inputs["input"] == inputs["customer_query"]

    def test_bridge_extracts_knowledge(self, dspy, mock_conversation_state):
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        assert "knowledge" in inputs


# ═══════════════════════════════════════════════════════════════════
# 7. Per-Tenant Configuration
# ═══════════════════════════════════════════════════════════════════


class TestConfiguration:

    def test_default_config(self, dspy):
        config = dspy.get_config("unknown_company")
        assert config.enabled is True
        assert config.model_name == "gpt-4o-mini"
        assert config.max_tokens == 500

    def test_configure_company(self, dspy):
        config = dspy.configure(
            COMPANY_ID,
            {
                "model_name": "gpt-4o",
                "max_tokens": 1000,
                "temperature": 0.5,
            },
        )
        assert config.model_name == "gpt-4o"
        assert config.max_tokens == 1000
        assert config.temperature == 0.5

    def test_get_config_returns_configured(self, dspy):
        dspy.configure(COMPANY_ID, {"model_name": "claude-3"})
        config = dspy.get_config(COMPANY_ID)
        assert config.model_name == "claude-3"

    def test_configure_isolated(self, dspy):
        dspy.configure(COMPANY_ID, {"model_name": "model_a"})
        config_other = dspy.get_config("other_company")
        assert config_other.model_name == "gpt-4o-mini"

    def test_configure_disabled(self, dspy):
        config = dspy.configure(COMPANY_ID, {"enabled": False})
        assert config.enabled is False

    def test_configure_optimizer(self, dspy):
        config = dspy.configure(
            COMPANY_ID,
            {"optimizer": "MIPROv2"},
        )
        assert config.optimizer == "MIPROv2"


# ═══════════════════════════════════════════════════════════════════
# 8. Metrics
# ═══════════════════════════════════════════════════════════════════


class TestMetrics:

    def test_empty_metrics(self, dspy):
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["avg_latency_ms"] == 0.0

    def test_single_execution_metric(self, dspy):
        dspy.reset_metrics()
        stub = StubModule(task_type="classify")
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 1
        assert metrics["success_rate"] == 100.0

    def test_fallback_rate_tracked(self, dspy):
        dspy.reset_metrics()
        stub = StubModule(task_type="classify")
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        if not _DSPY_AVAILABLE:
            assert metrics["fallback_rate"] == 100.0

    def test_by_task_type_metrics(self, dspy):
        dspy.reset_metrics()
        stub = StubModule(task_type="classify")
        dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert "classify" in metrics["by_task_type"]

    def test_reset_metrics(self, dspy):
        stub = StubModule()
        dspy.execute(stub, {"input": "test"})
        dspy.reset_metrics()
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 0

    def test_metrics_has_error_rate(self, dspy):
        metrics = dspy.get_metrics()
        assert "error_rate" in metrics

    def test_multiple_executions_average(self, dspy):
        dspy.reset_metrics()
        stub = StubModule(task_type="respond")
        for _ in range(5):
            dspy.execute(stub, {"input": "test"})
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 5
        assert metrics["by_task_type"]["respond"]["count"] == 5


# ═══════════════════════════════════════════════════════════════════
# 9. Optimization
# ═══════════════════════════════════════════════════════════════════


class TestOptimization:

    def test_optimize_returns_module(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, optimizer_name="BootstrapFewShot")
        assert optimized is not None

    def test_optimize_with_empty_trainset(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, trainset=[])
        assert optimized is not None

    def test_optimize_miprov2(self, dspy):
        module = dspy.create_module("classify")
        optimized = dspy.optimize(module, optimizer_name="MIPROv2")
        assert optimized is not None


# ═══════════════════════════════════════════════════════════════════
# 10. End-to-End Flow
# ═══════════════════════════════════════════════════════════════════


class TestEndToEnd:

    def test_full_classify_flow(self, dspy, mock_conversation_state):
        dspy.reset_metrics()
        # 1. Create module
        module = dspy.create_module("classify")
        # 2. Bridge from PARWA
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        # 3. Execute
        result = dspy.execute(module, inputs)
        # 4. Bridge back to PARWA
        updates = dspy.bridge_to_parwa(result, mock_conversation_state)
        # 5. Check metrics
        metrics = dspy.get_metrics()
        assert metrics["total_executions"] == 1
        assert isinstance(result, dict)
        assert isinstance(updates, dict)

    def test_respond_flow_with_stub(self, dspy, mock_conversation_state):
        module = dspy.create_module("respond")
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        result = dspy.execute(module, inputs)
        assert "response" in result or "Fallback" in str(result)

    def test_summarize_flow(self, dspy, mock_conversation_state):
        module = dspy.create_module("summarize")
        inputs = dspy.bridge_from_parwa(mock_conversation_state)
        result = dspy.execute(module, inputs)
        assert isinstance(result, dict)
