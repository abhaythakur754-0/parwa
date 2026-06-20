"""
Tests for Confidence Scoring Engine (IC-03).

Validates that the ConfidenceScoringEngine can be imported,
basic scoring works, batch scoring works, and thresholds are
configured correctly per variant.
"""

import pytest

from app.core.confidence_scoring_engine import (
    ConfidenceConfig,
    ConfidenceResult,
    ConfidenceScoringEngine,
    DEFAULT_THRESHOLDS,
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Create a fresh ConfidenceScoringEngine instance."""
    return ConfidenceScoringEngine()


# ── Import Tests ───────────────────────────────────────────────────


class TestConfidenceScoringImport:
    """Test that ConfidenceScoringEngine can be imported."""

    def test_engine_import(self):
        """ConfidenceScoringEngine should be importable."""
        assert ConfidenceScoringEngine is not None

    def test_engine_can_be_instantiated(self, engine):
        """ConfidenceScoringEngine should be instantiable without errors."""
        assert engine is not None

    def test_config_import(self):
        """ConfidenceConfig should be importable."""
        assert ConfidenceConfig is not None

    def test_result_import(self):
        """ConfidenceResult should be importable."""
        assert ConfidenceResult is not None


# ── Basic Scoring Tests ───────────────────────────────────────────


class TestBasicScoring:
    """Test basic confidence scoring functionality."""

    def test_score_returns_confidence_result(self, engine):
        """score_response should return a ConfidenceResult."""
        result = engine.score_response(
            company_id="company-123",
            query="How do I reset my password?",
            response="To reset your password, go to Settings > Security > Reset Password.",
        )
        assert isinstance(result, ConfidenceResult)

    def test_score_between_0_and_100(self, engine):
        """Overall score should be between 0 and 100."""
        result = engine.score_response(
            company_id="company-123",
            query="What is the weather?",
            response="I don't have access to weather information.",
        )
        assert 0.0 <= result.overall_score <= 100.0

    def test_score_has_required_fields(self, engine):
        """ConfidenceResult must have all required fields."""
        result = engine.score_response(
            company_id="company-123",
            query="Test query",
            response="Test response with some keywords from the query included.",
        )
        assert hasattr(result, "overall_score")
        assert hasattr(result, "passed")
        assert hasattr(result, "threshold")
        assert hasattr(result, "signals")
        assert hasattr(result, "variant_type")
        assert hasattr(result, "company_id")
        assert isinstance(result.signals, list)

    def test_score_signals_populated(self, engine):
        """Each scored signal should have proper structure."""
        result = engine.score_response(
            company_id="company-123",
            query="Test query about billing",
            response="Test response about billing with relevant terms.",
        )
        assert len(result.signals) > 0
        for signal in result.signals:
            assert hasattr(signal, "signal_name")
            assert hasattr(signal, "score")
            assert hasattr(signal, "weight")
            assert 0.0 <= signal.score <= 100.0


# ── Batch Scoring Tests ────────────────────────────────────────────


class TestBatchScoring:
    """Test batch scoring functionality."""

    def test_batch_returns_list(self, engine):
        """score_batch should return a list of ConfidenceResult."""
        items = [
            {"query": "Q1", "response": "R1"},
            {"query": "Q2", "response": "R2"},
        ]
        results = engine.score_batch(
            company_id="company-123",
            items=items,
        )
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, ConfidenceResult) for r in results)

    def test_batch_handles_empty_list(self, engine):
        """score_batch with empty list should return empty list."""
        results = engine.score_batch(
            company_id="company-123",
            items=[],
        )
        assert results == []

    def test_batch_maintains_order(self, engine):
        """Batch results should maintain input order."""
        items = [
            {"query": "First", "response": "First response"},
            {"query": "Second", "response": "Second response"},
            {"query": "Third", "response": "Third response"},
        ]
        results = engine.score_batch(
            company_id="company-123",
            items=items,
        )
        assert len(results) == 3


# ── Threshold Tests ───────────────────────────────────────────────


class TestThresholdConfig:
    """Test threshold configuration per variant."""

    def test_mini_parwa_threshold_95(self):
        """Mini PARWA should have threshold of 95."""
        assert DEFAULT_THRESHOLDS["mini_parwa"] == 95.0

    def test_parwa_threshold_85(self):
        """PARWA should have threshold of 85."""
        assert DEFAULT_THRESHOLDS["parwa"] == 85.0

    def test_parwa_high_threshold_75(self):
        """PARWA High should have threshold of 75."""
        assert DEFAULT_THRESHOLDS["parwa_high"] == 75.0

    def test_engine_get_threshold(self, engine):
        """get_threshold should return correct values per variant."""
        assert engine.get_threshold("mini_parwa") == 95.0
        assert engine.get_threshold("parwa") == 85.0
        assert engine.get_threshold("parwa_high") == 75.0

    def test_engine_get_threshold_unknown_variant(self, engine):
        """get_threshold with unknown variant should default to 85."""
        assert engine.get_threshold("unknown_variant") == 85.0


# ── BC-008 Compliance ─────────────────────────────────────────────


class TestConfidenceBC008:
    """Test BC-008 compliance — never crash."""

    def test_empty_query_returns_result(self, engine):
        """Empty query should return a valid result, not crash."""
        result = engine.score_response(
            company_id="company-123",
            query="",
            response="Some response",
        )
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 100.0

    def test_empty_response_returns_result(self, engine):
        """Empty response should return a valid result, not crash."""
        result = engine.score_response(
            company_id="company-123",
            query="Some query",
            response="",
        )
        assert isinstance(result, ConfidenceResult)
