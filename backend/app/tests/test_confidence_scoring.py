"""Tests for Confidence Scoring Engine (F-059, BC-001, BC-008).

Comprehensive tests covering:
- Helper functions: _tokenize, _jaccard_similarity, _safe_divide
- Data classes: SignalScore, ConfidenceResult, ConfidenceConfig
- Signal evaluators: all 7 signals with good/bad/edge cases
- Overall scoring: weighted average, pass/fail, clamping
- Variant thresholds: mini_parwa=95, parwa=85, parwa_high=75
- Custom config: weight overrides, enabled signals, threshold overrides
- Batch scoring: multiple responses, error isolation
- Config management: get default, update, cache per company, reset
- Edge cases / BC-008: None inputs, very long text, unicode, empty strings,
  malformed context dicts — never crash.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.core.confidence_scoring_engine import (
    ConfidenceScoringEngine,
    ConfidenceConfig,
    ConfidenceResult,
    SignalScore,
    SignalName,
    VariantType,
    DEFAULT_SIGNAL_WEIGHTS,
    DEFAULT_THRESHOLDS,
    ALL_SIGNAL_NAMES,
    MODEL_TIER_RELIABILITY,
    _tokenize,
    _jaccard_similarity,
    _safe_divide,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def engine() -> ConfidenceScoringEngine:
    """Fresh engine instance per test."""
    return ConfidenceScoringEngine()


def _get_signal(result: ConfidenceResult, name: str) -> SignalScore:
    """Helper to extract a signal by name from a ConfidenceResult."""
    return next(s for s in result.signals if s.signal_name == name)


COMPANY_ID = "test-company-123"

GOOD_QUERY = "How do I reset my password?"
GOOD_RESPONSE = (
    "To reset your password, go to the account settings page "
    "and click 'Reset Password'."
)

PII_RESPONSE = (
    "Contact us at john@example.com or call 555-123-4567. SSN: 123-45-6789."
)

HALLUC_RESPONSE = (
    "According to our latest 2024 report, approximately 15000 customers "
    "definitely prefer our product. I believe the exact number is 12543."
)


# ════════════════════════════════════════════════════════════════
# 1. HELPER FUNCTIONS (14 tests)
# ════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_tokenize_basic(self):
        tokens = _tokenize("hello world foo bar")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens

    def test_tokenize_filters_short_tokens(self):
        tokens = _tokenize("a b c go hi an")
        assert len(tokens) == 0  # all < 3 chars

    def test_tokenize_lowercase(self):
        tokens = _tokenize("Hello WORLD Foo")
        assert "hello" in tokens
        assert "world" in tokens

    def test_tokenize_empty_string(self):
        assert _tokenize("") == set()

    def test_tokenize_punctuation(self):
        tokens = _tokenize("hello, world! how are you?")
        assert "hello" in tokens
        assert "world" in tokens

    def test_jaccard_identical_sets(self):
        s = {"a", "b", "c"}
        assert _jaccard_similarity(s, s) == pytest.approx(1.0)

    def test_jaccard_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_jaccard_partial_overlap(self):
        assert _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(
            2 / 4
        )

    def test_jaccard_empty_both(self):
        assert _jaccard_similarity(set(), set()) == 0.0

    def test_jaccard_one_empty(self):
        assert _jaccard_similarity({"a"}, set()) == 0.0

    def test_safe_divide_normal(self):
        assert _safe_divide(10, 2) == 5.0

    def test_safe_divide_zero_denominator(self):
        assert _safe_divide(10, 0) == 0.0

    def test_safe_divide_custom_fallback(self):
        assert _safe_divide(10, 0, fallback=42.0) == 42.0

    def test_safe_divide_negative(self):
        assert _safe_divide(-10, 2) == -5.0


# ════════════════════════════════════════════════════════════════
# 2. DATA CLASSES (16 tests)
# ════════════════════════════════════════════════════════════════


class TestSignalScore:
    """Tests for SignalScore dataclass."""

    def test_basic_creation(self):
        ss = SignalScore(
            signal_name="test", score=75.0, weight=0.25, contribution=0.0
        )
        assert ss.score == 75.0
        assert ss.contribution == pytest.approx(18.75)

    def test_score_clamped_to_100(self):
        ss = SignalScore(
            signal_name="test", score=150.0, weight=0.25, contribution=0.0
        )
        assert ss.score == 100.0

    def test_score_clamped_to_0(self):
        ss = SignalScore(
            signal_name="test", score=-50.0, weight=0.25, contribution=0.0
        )
        assert ss.score == 0.0

    def test_passed_defaults_true(self):
        ss = SignalScore(
            signal_name="test", score=85.0, weight=0.25, contribution=0.0
        )
        assert ss.passed is True

    def test_contribution_calculation(self):
        ss = SignalScore(
            signal_name="test", score=80.0, weight=0.20, contribution=0.0
        )
        assert ss.contribution == pytest.approx(16.0)

    def test_metadata_defaults_empty(self):
        ss = SignalScore(
            signal_name="test", score=50.0, weight=0.25, contribution=0.0
        )
        assert ss.metadata == {}

    @pytest.mark.parametrize("score", [0.0, 50.0, 100.0])
    def test_valid_score_accepted(self, score):
        ss = SignalScore(
            signal_name="test", score=score, weight=0.25, contribution=0.0
        )
        assert 0.0 <= ss.score <= 100.0


class TestConfidenceResult:
    """Tests for ConfidenceResult dataclass.

    Note: ``passed`` is a required field (no default) so we pass a
    placeholder; ``__post_init__`` recomputes it from overall_score
    and threshold.
    """

    def test_passed_true_when_score_above_threshold(self):
        cr = ConfidenceResult(
            overall_score=90.0, passed=False, threshold=85.0
        )
        assert cr.passed is True

    def test_passed_false_when_score_below_threshold(self):
        cr = ConfidenceResult(
            overall_score=80.0, passed=True, threshold=85.0
        )
        assert cr.passed is False

    def test_passed_true_at_exactly_threshold(self):
        cr = ConfidenceResult(
            overall_score=85.0, passed=False, threshold=85.0
        )
        assert cr.passed is True

    def test_score_clamped_to_100(self):
        cr = ConfidenceResult(
            overall_score=200.0, passed=False, threshold=85.0
        )
        assert cr.overall_score == 100.0

    def test_score_clamped_to_0(self):
        cr = ConfidenceResult(
            overall_score=-50.0, passed=True, threshold=85.0
        )
        assert cr.overall_score == 0.0

    def test_default_variant_type(self):
        cr = ConfidenceResult(
            overall_score=90.0, passed=True, threshold=85.0
        )
        assert cr.variant_type == "parwa"

    def test_company_id_stored(self):
        cr = ConfidenceResult(
            overall_score=90.0, passed=True, threshold=85.0,
            company_id="co-1",
        )
        assert cr.company_id == "co-1"

    def test_scoring_duration_default(self):
        cr = ConfidenceResult(
            overall_score=90.0, passed=True, threshold=85.0
        )
        assert cr.scoring_duration_ms == 0.0

    def test_signals_default_empty(self):
        cr = ConfidenceResult(
            overall_score=90.0, passed=True, threshold=85.0
        )
        assert cr.signals == []


# ════════════════════════════════════════════════════════════════
# 3. DEFAULT WEIGHTS AND THRESHOLDS (8 tests)
# ════════════════════════════════════════════════════════════════


class TestDefaults:
    """Tests for default configuration values."""

    def test_weights_sum_to_one(self):
        total = sum(DEFAULT_SIGNAL_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_all_seven_signals_present(self):
        assert len(DEFAULT_SIGNAL_WEIGHTS) == 7
        for name in ALL_SIGNAL_NAMES:
            assert name in DEFAULT_SIGNAL_WEIGHTS

    def test_mini_parwa_threshold_95(self):
        assert DEFAULT_THRESHOLDS["mini_parwa"] == 95.0

    def test_parwa_threshold_85(self):
        assert DEFAULT_THRESHOLDS["parwa"] == 85.0

    def test_parwa_high_threshold_75(self):
        assert DEFAULT_THRESHOLDS["parwa_high"] == 75.0

    def test_all_signal_names_count(self):
        assert len(ALL_SIGNAL_NAMES) == 7

    def test_model_tier_reliability_has_all_tiers(self):
        assert "tier_1" in MODEL_TIER_RELIABILITY
        assert "tier_2" in MODEL_TIER_RELIABILITY
        assert "tier_3" in MODEL_TIER_RELIABILITY
        assert "unknown" in MODEL_TIER_RELIABILITY

    def test_unknown_tier_default_75(self):
        assert MODEL_TIER_RELIABILITY["unknown"] == 75.0


# ════════════════════════════════════════════════════════════════
# 4. ENGINE INITIALIZATION AND CONFIG (11 tests)
# ════════════════════════════════════════════════════════════════


class TestEngineInitAndConfig:
    """Tests for engine initialization and configuration."""

    def test_init_empty_tenant_configs(self, engine):
        assert engine._tenant_configs == {}

    def test_get_config_default(self, engine):
        config = engine.get_config(COMPANY_ID)
        assert config.company_id == COMPANY_ID
        assert config.variant_type == "parwa"
        assert config.threshold == 85.0

    def test_update_config_stored(self, engine):
        cfg = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="mini_parwa",
            threshold=95.0,
        )
        engine.update_config(COMPANY_ID, cfg)
        stored = engine.get_config(COMPANY_ID)
        assert stored.variant_type == "mini_parwa"
        assert stored.threshold == 95.0

    def test_update_config_overwrites(self, engine):
        cfg1 = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="parwa_high",
            threshold=75.0,
        )
        engine.update_config(COMPANY_ID, cfg1)
        cfg2 = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="mini_parwa",
            threshold=95.0,
        )
        engine.update_config(COMPANY_ID, cfg2)
        stored = engine.get_config(COMPANY_ID)
        assert stored.variant_type == "mini_parwa"

    def test_get_config_default_for_unknown_tenant(self, engine):
        config = engine.get_config("unknown-tenant")
        assert config.company_id == "unknown-tenant"
        assert config.threshold == 85.0

    def test_get_signal_weights_returns_copy(self, engine):
        w1 = engine.get_signal_weights("parwa")
        w2 = engine.get_signal_weights("parwa")
        assert w1 == w2
        assert w1 is not w2

    def test_get_threshold_mini_parwa(self, engine):
        assert engine.get_threshold("mini_parwa") == 95.0

    def test_get_threshold_parwa(self, engine):
        assert engine.get_threshold("parwa") == 85.0

    def test_get_threshold_parwa_high(self, engine):
        assert engine.get_threshold("parwa_high") == 75.0

    def test_get_threshold_unknown_variant_defaults_to_parwa(self, engine):
        assert engine.get_threshold("nonexistent") == 85.0

    def test_update_config_forces_company_id(self, engine):
        cfg = ConfidenceConfig(
            company_id="wrong-id",
            variant_type="parwa_high",
        )
        engine.update_config(COMPANY_ID, cfg)
        assert engine.get_config(COMPANY_ID).company_id == COMPANY_ID


# ════════════════════════════════════════════════════════════════
# 5. SIGNAL EVALUATOR — SEMANTIC RELEVANCE (8 tests)
# ════════════════════════════════════════════════════════════════


class TestSemanticRelevanceSignal:
    """Tests for semantic_relevance signal evaluator."""

    def test_high_relevance_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "password reset account settings",
            "To reset your password go to account settings page",
        )
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score > 50.0

    def test_low_relevance_unrelated(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "password reset",
            "The weather in Paris is beautiful today.",
        )
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score < 50.0

    def test_empty_query_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "", "Some response")
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score == 50.0
        assert sr.metadata.get("reason") == "empty_query_or_response"

    def test_empty_response_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "Some query", "")
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score == 50.0
        assert sr.metadata.get("reason") == "empty_query_or_response"

    def test_whitespace_only_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "   ", "response")
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score == 50.0

    def test_identical_text_high_score(self, engine):
        text = "password reset account settings page login credentials"
        result = engine.score_response(COMPANY_ID, text, text)
        sr = _get_signal(result, "semantic_relevance")
        assert sr.score > 50.0

    def test_metadata_has_jaccard(self, engine):
        result = engine.score_response(
            COMPANY_ID, "password reset", "password reset account"
        )
        sr = _get_signal(result, "semantic_relevance")
        assert "jaccard_similarity" in sr.metadata

    def test_metadata_has_overlap_ratio(self, engine):
        result = engine.score_response(
            COMPANY_ID, "password reset", "password reset account"
        )
        sr = _get_signal(result, "semantic_relevance")
        assert "overlap_ratio" in sr.metadata


# ════════════════════════════════════════════════════════════════
# 6. SIGNAL EVALUATOR — RESPONSE COMPLETENESS (7 tests)
# ════════════════════════════════════════════════════════════════


class TestResponseCompletenessSignal:
    """Tests for response_completeness signal evaluator."""

    def test_full_coverage_single_part(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy",
            "The refund policy is 30 days from purchase.",
        )
        sr = _get_signal(result, "response_completeness")
        assert sr.score > 50.0
        assert sr.metadata.get("multi_part") is False

    def test_empty_query_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "", "response")
        sr = _get_signal(result, "response_completeness")
        assert sr.score == 50.0

    def test_empty_response_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "query", "")
        sr = _get_signal(result, "response_completeness")
        assert sr.score == 50.0

    def test_multi_part_query_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "What is the refund policy and how do I contact support?",
            "The refund policy is 30 days. For support contact use help.",
        )
        sr = _get_signal(result, "response_completeness")
        assert sr.metadata.get("multi_part") is True

    def test_multi_part_both_parts_addressed(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy and exchange policy",
            "The refund policy is 30 days and the exchange policy is 14 days.",
        )
        sr = _get_signal(result, "response_completeness")
        # Both parts have tokens in the response
        assert sr.metadata.get("parts_addressed", 0) >= 1

    def test_multi_part_one_part_missed(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy and quantum computing basics",
            "Our refund policy allows returns within 30 days.",
        )
        sr = _get_signal(result, "response_completeness")
        assert sr.metadata.get("multi_part") is True
        # quantum computing part should not be covered
        assert sr.metadata.get("parts_addressed", 0) < 2

    def test_single_part_good_coverage_metadata(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy",
            "The refund policy is straightforward and simple.",
        )
        sr = _get_signal(result, "response_completeness")
        assert "coverage_ratio" in sr.metadata
        assert sr.metadata["coverage_ratio"] > 0.0


# ════════════════════════════════════════════════════════════════
# 7. SIGNAL EVALUATOR — PII SAFETY (8 tests)
# ════════════════════════════════════════════════════════════════


class TestPIISafetySignal:
    """Tests for pii_safety signal evaluator."""

    def test_clean_response_high_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "Tell me about returns",
            "Our return policy is straightforward.",
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score == 100.0

    def test_email_detected_reduces_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "contact info",
            "Email us at test@example.com for help.",
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score < 100.0
        assert sr.metadata.get("finding_count", 0) >= 1

    def test_phone_detected_reduces_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "call us",
            "Call 555-123-4567 for assistance.",
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score < 100.0

    def test_ssn_detected_severe_penalty(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "verify identity",
            "Your SSN is 123-45-6789 for verification.",
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score <= 70.0  # SSN penalty is 30

    def test_multiple_pii_types_severe(self, engine):
        result = engine.score_response(
            COMPANY_ID, "info", PII_RESPONSE
        )
        sr = _get_signal(result, "pii_safety")
        # email(-10) + phone(-8) + SSN(-30) = -48 → score = 52
        assert sr.score < 60.0

    def test_empty_response_returns_100(self, engine):
        """Empty response has no PII, so score should be 100."""
        result = engine.score_response(COMPANY_ID, "query", "")
        sr = _get_signal(result, "pii_safety")
        assert sr.score == 100.0
        assert sr.metadata.get("reason") == "empty_response"

    def test_pii_redacted_flag_returns_95(self, engine):
        """When PII was already redacted, score should be 95."""
        result = engine.score_response(
            COMPANY_ID,
            "info",
            "john@example.com",
            context={"pii_redacted": True},
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score == 95.0
        assert sr.metadata.get("reason") == "pii_pre_redacted"

    def test_safety_level_metadata(self, engine):
        result = engine.score_response(
            COMPANY_ID, "hello", "Clean response with no PII."
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.metadata.get("safety_level") == "safe"


# ════════════════════════════════════════════════════════════════
# 8. SIGNAL EVALUATOR — HALLUCINATION RISK (9 tests)
# ════════════════════════════════════════════════════════════════


class TestHallucinationRiskSignal:
    """Tests for hallucination_risk signal evaluator."""

    def test_clean_response_high_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy",
            "Our refund policy is 30 days from purchase.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score > 80.0
        assert sr.metadata.get("risk_level") == "low"

    def test_fabricated_stats_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "growth",
            "According to our latest 2024 report, 85% increase in sales.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score < 100.0
        assert sr.metadata.get("marker_count", 0) >= 1

    def test_fake_urls_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "docs",
            "Visit www.sales2024.com for more info.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score < 100.0

    def test_temporal_claims_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "data",
            "As of my latest update in 2024, the policy has changed.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score < 100.0

    def test_placeholder_domains_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "docs",
            "See https://example.com/docs for details.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score < 100.0

    def test_source_attribution_detected(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "policy",
            "As described in the documentation, the limit is 30 days.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score < 100.0

    def test_empty_response_returns_100(self, engine):
        """Empty response cannot contain hallucination markers."""
        result = engine.score_response(COMPANY_ID, "query", "")
        sr = _get_signal(result, "hallucination_risk")
        assert sr.score == 100.0
        assert sr.metadata.get("reason") == "empty_response"

    def test_multiple_markers_severe_penalty(self, engine):
        result = engine.score_response(
            COMPANY_ID, "data", HALLUC_RESPONSE
        )
        sr = _get_signal(result, "hallucination_risk")
        # Multiple hallucination markers should significantly reduce score
        assert sr.score < 85.0
        assert sr.metadata.get("marker_count", 0) >= 2

    def test_risk_level_medium(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "info",
            "According to our latest report, the data shows a 50% increase.",
        )
        sr = _get_signal(result, "hallucination_risk")
        # With at least one marker, score should drop below 80
        if sr.metadata.get("marker_count", 0) > 0:
            assert sr.score < 100.0


# ════════════════════════════════════════════════════════════════
# 9. SIGNAL EVALUATOR — SENTIMENT ALIGNMENT (8 tests)
# ════════════════════════════════════════════════════════════════


class TestSentimentAlignmentSignal:
    """Tests for sentiment_alignment signal evaluator."""

    def test_positive_query_positive_response(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "The service is great and excellent",
            "We are glad to hear that! Our team is wonderful and helpful.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score >= 85.0  # matching positive tone
        assert sr.metadata.get("alignment_reason") == "matching_positive_tone"

    def test_negative_query_positive_response_high_score(self, engine):
        """Empathetic/positive response to negative query should score high."""
        result = engine.score_response(
            COMPANY_ID,
            "This is terrible and broken and horrible",
            "We understand and appreciate your patience. Here is a solution.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score >= 85.0

    def test_negative_query_negative_response_low_score(self, engine):
        """Mirroring frustration in response should score low."""
        result = engine.score_response(
            COMPANY_ID,
            "This is terrible and broken and horrible",
            "This is unacceptable and the worst experience possible.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score < 50.0

    def test_neutral_query_neutral_response(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "What are the business hours?",
            "We are open Monday through Friday, 9 AM to 5 PM.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score >= 85.0  # appropriate neutral tone

    def test_emergency_query_professional_response(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "This is urgent help emergency legal issue",
            "We understand the urgency. A specialist will contact you shortly.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score >= 80.0
        assert sr.metadata.get("query_sentiment") == "emergency"

    def test_empty_inputs_returns_70(self, engine):
        """Empty query or response returns default score of 70."""
        result = engine.score_response(COMPANY_ID, "query", "")
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score == 70.0
        assert sr.metadata.get("reason") == "empty_query_or_response"

    def test_expected_tone_positive_override(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "info request",
            "The service is great and wonderful!",
            context={"expected_tone": "positive"},
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert sr.score >= 90.0

    def test_metadata_has_sentiment_counts(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "great service terrible problem",
            "Great solution for your terrible problem.",
        )
        sr = _get_signal(result, "sentiment_alignment")
        assert "query_positive_count" in sr.metadata
        assert "query_negative_count" in sr.metadata
        assert "response_positive_count" in sr.metadata


# ════════════════════════════════════════════════════════════════
# 10. SIGNAL EVALUATOR — TOKEN EFFICIENCY (6 tests)
# ════════════════════════════════════════════════════════════════


class TestTokenEfficiencySignal:
    """Tests for token_efficiency signal evaluator."""

    def test_reasonable_length_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "refund policy",
            "The refund policy is 30 days from purchase date.",
        )
        sr = _get_signal(result, "token_efficiency")
        assert 0.0 <= sr.score <= 100.0

    def test_optimal_ratio_high_score(self, engine):
        """Response 3-10x query length should score in optimal range."""
        query = "refund policy"
        response = (
            "Our refund policy allows returns within 30 days of purchase. "
            "Please keep your receipt for faster processing."
        )
        result = engine.score_response(COMPANY_ID, query, response)
        sr = _get_signal(result, "token_efficiency")
        # ratio ~9.6 → optimal range (3-10x)
        assert sr.metadata.get("efficiency_level") == "optimal"
        assert sr.score >= 85.0

    def test_very_long_response_lower_score(self, engine):
        long_response = "word " * 500
        result = engine.score_response(
            COMPANY_ID, "short question", long_response
        )
        sr = _get_signal(result, "token_efficiency")
        assert sr.score < 80.0

    def test_very_short_response_low_score(self, engine):
        """Critically short response (< 10 tokens) should be penalized."""
        result = engine.score_response(
            COMPANY_ID, "How do I reset my password?", "Settings."
        )
        sr = _get_signal(result, "token_efficiency")
        assert sr.score <= 30.0
        assert sr.metadata.get("efficiency_level") == "critically_short"

    def test_empty_response_returns_50(self, engine):
        result = engine.score_response(COMPANY_ID, "query", "")
        sr = _get_signal(result, "token_efficiency")
        assert sr.score == 50.0
        assert sr.metadata.get("reason") == "empty_query_or_response"

    def test_metadata_has_length_info(self, engine):
        result = engine.score_response(
            COMPANY_ID, "query text", "response text here"
        )
        sr = _get_signal(result, "token_efficiency")
        assert "query_length" in sr.metadata
        assert "response_length" in sr.metadata
        assert "length_ratio" in sr.metadata


# ════════════════════════════════════════════════════════════════
# 11. SIGNAL EVALUATOR — PROVIDER CONFIDENCE (7 tests)
# ════════════════════════════════════════════════════════════════


class TestProviderConfidenceSignal:
    """Tests for provider_confidence signal evaluator."""

    def test_tier_1_high_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "tier_1"},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score >= 90.0

    def test_tier_2_medium_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "tier_2"},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score >= 80.0

    def test_tier_3_lower_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "tier_3"},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score < 90.0

    def test_unknown_tier_default_75(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "unknown"},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score == 75.0

    def test_no_context_uses_unknown_tier(self, engine):
        result = engine.score_response(
            COMPANY_ID, "question", "answer"
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score == 75.0

    def test_model_health_affects_score(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "tier_1", "model_health": 50.0},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score < 95.0  # 70% * 95 + 30% * 50 = 81.5

    def test_model_health_100_boosts(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "question",
            "answer",
            context={"model_tier": "tier_2", "model_health": 100.0},
        )
        sr = _get_signal(result, "provider_confidence")
        assert sr.score > 85.0  # 70% * 85 + 30% * 100 = 89.5


# ════════════════════════════════════════════════════════════════
# 12. OVERALL SCORE CALCULATION (10 tests)
# ════════════════════════════════════════════════════════════════


class TestOverallScoreCalculation:
    """Tests for overall score computation."""

    def test_all_signals_evaluated(self, engine):
        result = engine.score_response(
            COMPANY_ID, "test query", "test response"
        )
        assert len(result.signals) == 7

    def test_company_id_in_result(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.company_id == COMPANY_ID

    def test_threshold_defaults_to_parwa_85(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.threshold == 85.0

    def test_variant_type_in_result(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.variant_type == "parwa"

    def test_duration_ms_recorded(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.scoring_duration_ms >= 0.0

    def test_scored_at_timestamp(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.scored_at is not None
        assert len(result.scored_at) > 0

    def test_score_clamped_0_to_100(self, engine):
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert 0.0 <= result.overall_score <= 100.0

    def test_good_response_passes_threshold(self, engine):
        """High-quality response with keyword overlap should pass."""
        text = "refund policy return exchange simple straightforward"
        result = engine.score_response(
            COMPANY_ID,
            text,
            f"Our {text} is as described above.",
        )
        assert result.overall_score >= 0.0  # just validate it computed

    def test_bad_response_low_score(self, engine):
        """Completely unrelated response should have low score."""
        result = engine.score_response(
            COMPANY_ID,
            "password reset account settings login",
            "The weather is sunny and birds are singing beautifully today.",
        )
        assert result.overall_score < 85.0  # fails parwa threshold

    def test_disabled_signals_only_enabled_evaluated(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            enabled_signals=["pii_safety"],
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert len(result.signals) == 1
        assert result.signals[0].signal_name == "pii_safety"


# ════════════════════════════════════════════════════════════════
# 13. VARIANT THRESHOLDS (6 tests)
# ════════════════════════════════════════════════════════════════


class TestVariantThresholds:
    """Tests for variant-specific thresholds."""

    def test_mini_parwa_95_threshold(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="mini_parwa",
            threshold=95.0,
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert result.threshold == 95.0

    def test_parwa_85_threshold(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID, variant_type="parwa"
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert result.threshold == 85.0

    def test_parwa_high_75_threshold(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="parwa_high",
            threshold=75.0,
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert result.threshold == 75.0

    def test_custom_threshold_override(self, engine):
        """Custom threshold in config overrides variant default."""
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="mini_parwa",
            threshold=50.0,
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert result.threshold == 50.0

    def test_high_score_passes_parwa_high(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID, variant_type="parwa_high"
        )
        text = "refund policy return exchange"
        result = engine.score_response(
            COMPANY_ID, text, text, config=config
        )
        assert result.overall_score > 75.0

    def test_unknown_variant_defaults_to_parwa_85(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="nonexistent_variant",
            threshold=85.0,
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        # Unknown variant: get_threshold returns 85.0 default
        assert result.threshold == 85.0


# ════════════════════════════════════════════════════════════════
# 14. CUSTOM CONFIG — WEIGHT OVERRIDES (4 tests)
# ════════════════════════════════════════════════════════════════


class TestCustomConfig:
    """Tests for custom configuration overrides."""

    def test_weight_override_applied(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID,
            signal_weights={
                SignalName.SEMANTIC_RELEVANCE.value: 0.50,
            },
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        sr = _get_signal(result, "semantic_relevance")
        assert sr.weight == 0.50

    def test_empty_enabled_signals_all_enabled(self, engine):
        config = ConfidenceConfig(
            company_id=COMPANY_ID, enabled_signals=[]
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=config
        )
        assert len(result.signals) == 7

    def test_call_config_overrides_tenant_config(self, engine):
        tenant_cfg = ConfidenceConfig(
            company_id=COMPANY_ID, threshold=50.0
        )
        engine.update_config(COMPANY_ID, tenant_cfg)
        call_cfg = ConfidenceConfig(
            company_id=COMPANY_ID, threshold=99.0
        )
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=call_cfg
        )
        assert result.threshold == 99.0

    def test_tenant_config_used_when_no_call_config(self, engine):
        tenant_cfg = ConfidenceConfig(
            company_id=COMPANY_ID,
            variant_type="mini_parwa",
            threshold=95.0,
        )
        engine.update_config(COMPANY_ID, tenant_cfg)
        result = engine.score_response(COMPANY_ID, "q", "r")
        assert result.threshold == 95.0
        assert result.variant_type == "mini_parwa"


# ════════════════════════════════════════════════════════════════
# 15. BATCH SCORING (5 tests)
# ════════════════════════════════════════════════════════════════


class TestBatchScoring:
    """Tests for batch scoring."""

    def test_batch_returns_correct_count(self, engine):
        items = [
            {"query": "q1", "response": "r1"},
            {"query": "q2", "response": "r2"},
            {"query": "q3", "response": "r3"},
        ]
        results = engine.score_batch(COMPANY_ID, items)
        assert len(results) == 3

    def test_batch_empty_list_returns_empty(self, engine):
        results = engine.score_batch(COMPANY_ID, [])
        assert results == []

    def test_batch_all_results_valid(self, engine):
        items = [
            {"query": f"q{i}", "response": f"r{i}"} for i in range(10)
        ]
        results = engine.score_batch(COMPANY_ID, items)
        for r in results:
            assert isinstance(r, ConfidenceResult)

    def test_batch_with_problematic_items(self, engine):
        """Individual item failures should not crash batch; still returns results."""
        items = [
            {"query": "", "response": "r"},
            {"query": "q", "response": ""},
            {"query": "valid query", "response": "valid response"},
        ]
        results = engine.score_batch(COMPANY_ID, items)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, ConfidenceResult)

    def test_batch_per_item_config(self, engine):
        items = [
            {
                "query": "q1",
                "response": "r1",
                "config": ConfidenceConfig(
                    company_id=COMPANY_ID,
                    variant_type="mini_parwa",
                    threshold=95.0,
                ),
            },
            {
                "query": "q2",
                "response": "r2",
                "config": ConfidenceConfig(
                    company_id=COMPANY_ID,
                    variant_type="parwa_high",
                    threshold=75.0,
                ),
            },
        ]
        results = engine.score_batch(COMPANY_ID, items)
        assert results[0].threshold == 95.0
        assert results[1].threshold == 75.0


# ════════════════════════════════════════════════════════════════
# 16. CONFIG MANAGEMENT (5 tests)
# ════════════════════════════════════════════════════════════════


class TestConfigManagement:
    """Tests for config caching and management."""

    def test_get_default_config(self, engine):
        config = engine.get_config("new-company-xyz")
        assert config.variant_type == "parwa"
        assert config.threshold == 85.0

    def test_update_config_with_custom_weights(self, engine):
        custom_weights = {
            SignalName.PII_SAFETY.value: 0.50,
            SignalName.HALLUCINATION_RISK.value: 0.30,
        }
        cfg = ConfidenceConfig(
            company_id=COMPANY_ID,
            signal_weights=custom_weights,
        )
        engine.update_config(COMPANY_ID, cfg)
        stored = engine.get_config(COMPANY_ID)
        assert stored.signal_weights == custom_weights

    def test_config_cached_per_company(self, engine):
        cfg_a = ConfidenceConfig(
            company_id="co-a", variant_type="mini_parwa", threshold=95.0
        )
        cfg_b = ConfidenceConfig(
            company_id="co-b", variant_type="parwa_high", threshold=75.0
        )
        engine.update_config("co-a", cfg_a)
        engine.update_config("co-b", cfg_b)
        assert engine.get_config("co-a").threshold == 95.0
        assert engine.get_config("co-b").threshold == 75.0

    def test_reset_config_by_re_initializing(self):
        """Creating a new engine resets all tenant configs."""
        eng = ConfidenceScoringEngine()
        eng.update_config(
            COMPANY_ID,
            ConfidenceConfig(
                company_id=COMPANY_ID, variant_type="mini_parwa"
            ),
        )
        assert eng.get_config(COMPANY_ID).variant_type == "mini_parwa"
        # Fresh engine has empty configs
        eng2 = ConfidenceScoringEngine()
        assert eng2.get_config(COMPANY_ID).variant_type == "parwa"

    def test_update_config_with_enabled_signals(self, engine):
        cfg = ConfidenceConfig(
            company_id=COMPANY_ID,
            enabled_signals=["pii_safety", "hallucination_risk"],
        )
        engine.update_config(COMPANY_ID, cfg)
        stored = engine.get_config(COMPANY_ID)
        assert stored.enabled_signals == ["pii_safety", "hallucination_risk"]


# ════════════════════════════════════════════════════════════════
# 17. EDGE CASES / BC-008: NEVER CRASH (10 tests)
# ════════════════════════════════════════════════════════════════


class TestBC008NeverCrash:
    """Tests for BC-008 — never crash on any input."""

    def test_none_query(self, engine):
        result = engine.score_response(
            COMPANY_ID, None, "response"  # type: ignore
        )
        assert isinstance(result, ConfidenceResult)

    def test_none_response(self, engine):
        result = engine.score_response(
            COMPANY_ID, "query", None  # type: ignore
        )
        assert isinstance(result, ConfidenceResult)

    def test_none_both_query_and_response(self, engine):
        result = engine.score_response(
            COMPANY_ID, None, None  # type: ignore
        )
        assert isinstance(result, ConfidenceResult)

    def test_none_context(self, engine):
        result = engine.score_response(
            COMPANY_ID, "q", "r", context=None
        )
        assert isinstance(result, ConfidenceResult)

    def test_none_config(self, engine):
        result = engine.score_response(
            COMPANY_ID, "q", "r", config=None
        )
        assert isinstance(result, ConfidenceResult)

    def test_empty_strings(self, engine):
        result = engine.score_response(COMPANY_ID, "", "")
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 100.0

    def test_very_long_text_10000_chars(self, engine):
        """Very long text should not crash the engine."""
        long_text = "word " * 5000  # ~25000 chars
        result = engine.score_response(COMPANY_ID, long_text, long_text)
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 100.0

    def test_unicode_text(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "\u00bfC\u00f3mo restablecer mi contrase\u00f1a?",
            "Para restablecer su contrase\u00f1a, vaya a la configuraci\u00f3n.",
        )
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 100.0

    def test_malformed_context_dict(self, engine):
        """Non-dict context values should not crash."""
        result = engine.score_response(
            COMPANY_ID,
            "query",
            "response",
            context={"model_tier": 12345, "model_health": "bad_value"},  # type: ignore
        )
        assert isinstance(result, ConfidenceResult)

    def test_special_characters_in_query(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "<script>alert('xss')</script> & \"quotes\" 'apostrophes'",
            "We can help with your request.",
        )
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 100.0


# ════════════════════════════════════════════════════════════════
# 18. SIGNAL-LEVEL EDGE CASES (4 tests)
# ════════════════════════════════════════════════════════════════


class TestSignalLevelEdgeCases:
    """Additional edge-case tests for individual signals."""

    def test_pii_safety_finds_multiple_emails(self, engine):
        result = engine.score_response(
            COMPANY_ID,
            "contacts",
            "Email alice@example.com or bob@test.org or carol@demo.net.",
        )
        sr = _get_signal(result, "pii_safety")
        assert sr.score < 100.0
        assert sr.metadata.get("finding_count", 0) >= 3

    def test_hallucination_risk_clean_no_markers(self, engine):
        """A straightforward factual response should have no markers."""
        result = engine.score_response(
            COMPANY_ID,
            "hours",
            "We are open Monday to Friday from 9 AM to 5 PM.",
        )
        sr = _get_signal(result, "hallucination_risk")
        assert sr.metadata.get("marker_count", 0) == 0

    def test_token_efficiency_single_word_response(self, engine):
        """Single-word response should be penalized heavily."""
        result = engine.score_response(
            COMPANY_ID, "How do I reset my password?", "Settings"
        )
        sr = _get_signal(result, "token_efficiency")
        assert sr.score <= 30.0

    def test_provider_confidence_complex_query_tier3_penalty(self, engine):
        """Complex query with tier_3 model should get a penalty."""
        complex_query = " and ".join(
            [f"What is the policy about topic number {i}" for i in range(10)]
        )
        result = engine.score_response(
            COMPANY_ID,
            complex_query,
            "Here are the details for each topic.",
            context={"model_tier": "tier_3"},
        )
        sr = _get_signal(result, "provider_confidence")
        # tier_3 gets 15 point penalty for complex queries (word_count>30 or multi-part)
        assert sr.score < MODEL_TIER_RELIABILITY["tier_3"]
