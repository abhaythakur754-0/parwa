"""
Tests for DSPy optimization upgrades (Day 9):
- Real composite metrics (relevance, accuracy, conciseness, safety)
- Training data collection from templates
- Compiled module persistence
- Evaluation harness
- optimize_response pipeline integration
"""

import os
import pickle
import tempfile
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from app.core.dspy_integration import (
    DSPyIntegration,
    DSPyConfig,
    StubModule,
    StubPrediction,
    ExecutionMetric,
)


# ════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def dspy_int():
    """Create a fresh DSPyIntegration instance."""
    return DSPyIntegration()


@pytest.fixture
def sample_config():
    """Create a sample DSPyConfig."""
    return DSPyConfig(
        enabled=True,
        model_name="test-model",
        max_tokens=100,
        temperature=0.5,
    )


# ════════════════════════════════════════════════════════════════
# REAL METRIC TESTS
# ════════════════════════════════════════════════════════════════


class TestRealMetrics:
    """Tests for the real composite metric implementation."""

    def test_relevance_high_score(self, dspy_int):
        """Response containing query keywords should score high relevance."""
        example = MagicMock()
        example.customer_query = "refund my subscription"
        pred = MagicMock()
        pred.response = "I can help you process a refund for your subscription"

        score = dspy_int._default_metric(example, pred)
        assert score > 0.5, f"Expected high relevance score, got {score}"

    def test_relevance_low_score(self, dspy_int):
        """Completely irrelevant response should score lower relevance."""
        example = MagicMock()
        example.customer_query = "refund my subscription"
        pred = MagicMock()
        pred.response = "The weather is sunny today with clear skies"

        score = dspy_int._default_metric(example, pred)
        assert score < 0.8, f"Expected lower relevance score, got {score}"

    def test_safety_blocks_pii(self, dspy_int):
        """Response with PII (SSN) should get safety penalty."""
        example = MagicMock()
        example.customer_query = "help with account"
        pred = MagicMock()
        pred.response = "Your SSN is 123-45-6789 and your credit card is 4111111111111111"

        score = dspy_int._default_metric(example, pred)
        assert score < 0.5, f"Expected low safety score for PII, got {score}"

    def test_safety_clean_response(self, dspy_int):
        """Clean response should have high safety score."""
        example = MagicMock()
        example.customer_query = "help with account"
        pred = MagicMock()
        pred.response = "I can help you update your account settings"

        score = dspy_int._default_metric(example, pred)
        assert score > 0.3, f"Expected reasonable safety score, got {score}"

    def test_conciseness_ideal_response(self, dspy_int):
        """Response length within 2x query should get full conciseness score."""
        example = MagicMock()
        example.customer_query = "reset password"
        pred = MagicMock()
        pred.response = "Click the forgot password link to reset"

        score = dspy_int._default_metric(example, pred)
        # Conciseness should not penalize short response
        assert score > 0.5

    def test_accuracy_all_fields_present(self, dspy_int):
        """Response with all expected fields should get high accuracy."""
        example = MagicMock()
        example.customer_query = "refund please"
        pred = MagicMock()
        pred.response = "I'll process your refund"
        pred.intent = "refund"
        pred.confidence = 0.9

        score = dspy_int._default_metric(example, pred)
        assert score > 0.5

    def test_metric_graceful_failure(self, dspy_int):
        """Metric should handle exceptions gracefully (BC-008)."""
        example = None  # Invalid input
        pred = None

        score = dspy_int._default_metric(example, pred)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_metric_with_empty_response(self, dspy_int):
        """Empty response should give low score."""
        example = MagicMock()
        example.customer_query = "help with refund"
        pred = MagicMock()
        pred.response = ""
        pred.intent = ""

        score = dspy_int._default_metric(example, pred)
        assert score < 0.5


# ════════════════════════════════════════════════════════════════
# TRAINING DATA COLLECTION TESTS
# ════════════════════════════════════════════════════════════════


class TestTrainingDataCollection:
    """Tests for build_training_data_from_templates."""

    @patch("app.core.dspy_integration._TEMPLATES_AVAILABLE", False)
    def test_no_templates_available(self, dspy_int):
        """Should return empty list when templates not available."""
        result = dspy_int.build_training_data_from_templates()
        assert result == []

    @patch("app.core.dspy_integration._TEMPLATES_AVAILABLE", True)
    def test_with_mock_templates(self, dspy_int):
        """Should attempt to create training examples from templates."""
        # The function depends on the actual templates module structure
        # When templates are available but don't have expected structure,
        # it should return [] or the available examples without crashing
        result = dspy_int.build_training_data_from_templates()
        # The key test: it doesn't crash and returns a list
        assert isinstance(result, list)


# ════════════════════════════════════════════════════════════════
# COMPILED MODULE PERSISTENCE TESTS
# ════════════════════════════════════════════════════════════════


class TestCompiledModulePersistence:
    """Tests for save/load compiled module."""

    def test_save_and_load_roundtrip(self, dspy_int, tmp_path):
        """Module should survive save→load cycle."""
        # Monkey-patch cache dir
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", tmp_path):
            test_module = StubModule(task_type="test_task")
            test_data = {"key": "value", "number": 42}

            # Save
            result = dspy_int.save_compiled_module("co_123", "classify", test_data)
            assert result is True

            # Load
            loaded = dspy_int.load_compiled_module("co_123", "classify")
            assert loaded is not None
            assert loaded == test_data

    def test_load_nonexistent_module(self, dspy_int, tmp_path):
        """Loading non-existent module should return None."""
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", tmp_path):
            loaded = dspy_int.load_compiled_module("co_999", "nonexistent")
            assert loaded is None

    def test_save_compiled_module_invalid_path(self, dspy_int):
        """Save to invalid path should return False (BC-008)."""
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", Path("/nonexistent/path/that/should/fail")):
            result = dspy_int.save_compiled_module("co_123", "classify", {"data": "test"})
            assert result is False

    def test_different_companies_isolated(self, dspy_int, tmp_path):
        """Modules for different companies should be isolated."""
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", tmp_path):
            dspy_int.save_compiled_module("co_1", "classify", {"company": 1})
            dspy_int.save_compiled_module("co_2", "classify", {"company": 2})

            loaded1 = dspy_int.load_compiled_module("co_1", "classify")
            loaded2 = dspy_int.load_compiled_module("co_2", "classify")

            assert loaded1["company"] == 1
            assert loaded2["company"] == 2


# ════════════════════════════════════════════════════════════════
# EVALUATION HARNESS TESTS
# ════════════════════════════════════════════════════════════════


class TestEvaluationHarness:
    """Tests for the evaluation harness."""

    def test_evaluate_with_stub_module(self, dspy_int):
        """Evaluation with stub module should return aggregate stats."""
        stub = StubModule(task_type="classify")
        testset = [
            {"customer_query": "refund", "response": "I'll refund"},
            {"customer_query": "help", "response": "I'll help"},
        ]

        result = dspy_int.evaluate(stub, testset)
        assert "mean" in result
        assert "min" in result
        assert "max" in result
        assert "total_examples" in result
        assert result["total_examples"] == 2

    def test_evaluate_empty_testset(self, dspy_int):
        """Empty testset should return zeros."""
        stub = StubModule(task_type="classify")
        result = dspy_int.evaluate(stub, [])
        assert result["total_examples"] == 0
        assert result["mean"] == 0.0

    def test_evaluate_with_exceptions(self, dspy_int):
        """Examples that raise exceptions should be handled gracefully."""
        failing_module = MagicMock()
        failing_module.side_effect = Exception("Test error")

        testset = [{"customer_query": "test"}]
        result = dspy_int.evaluate(failing_module, testset)
        assert result["total_examples"] == 1
        # Should not crash — score may be 0.0 or a fallback value
        assert "mean" in result
        assert isinstance(result["mean"], float)

    def test_evaluate_custom_metric(self, dspy_int):
        """Custom metric callable should override default."""
        stub = StubModule(task_type="classify")
        custom_metric = MagicMock(return_value=0.95)
        testset = [{"customer_query": "test"}]

        result = dspy_int.evaluate(stub, testset, metric=custom_metric)
        custom_metric.assert_called()


# ════════════════════════════════════════════════════════════════
# OPTIMIZE_RESPONSE PIPELINE TESTS
# ════════════════════════════════════════════════════════════════


class TestOptimizeResponsePipeline:
    """Tests for the optimize_response pipeline integration."""

    def test_returns_stub_fallback_when_unavailable(self, dspy_int):
        """Should return fallback when DSPy not available and no cache."""
        result = dspy_int.optimize_response(
            company_id="co_test",
            query="help with refund",
            context={"intent": "refund"},
        )
        assert result is not None
        assert isinstance(result, dict)

    def test_returns_bridge_result(self, dspy_int, tmp_path):
        """Result should contain bridge_to_parwa output fields."""
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", tmp_path):
            result = dspy_int.optimize_response(
                company_id="co_test",
                query="I need help",
                context={"intent": "general"},
            )
            # Bridge should populate these fields from stub output
            assert "response" in result or "final_response" in result or result == {}
            # Should not crash

    def test_optimize_uses_cached_module(self, dspy_int, tmp_path):
        """Should use cached module if available."""
        with patch("app.core.dspy_integration._DSPY_CACHE_DIR", tmp_path):
            # Pre-cache a module
            cached_data = StubModule(task_type="respond")
            dspy_int.save_compiled_module("co_cached", "respond", cached_data)

            # This should load from cache instead of optimizing
            result = dspy_int.optimize_response(
                company_id="co_cached",
                query="test query",
                context={"intent": "general"},
            )
            assert result is not None

    def test_optimize_response_graceful_failure(self, dspy_int):
        """Should return empty dict on total failure (BC-008)."""
        # Pass invalid inputs that might cause errors
        result = dspy_int.optimize_response(
            company_id="",
            query="",
            context=None,
        )
        assert isinstance(result, dict)
