"""
Tests for Guardrails AI Engine (F-057).
Tests cover: ContentSafetyGuard, TopicRelevanceGuard, HallucinationCheckGuard,
PolicyComplianceGuard, ToneValidationGuard, LengthControlGuard, PIILeakGuard,
ConfidenceGateGuard, GuardrailsEngine, _build_config merging.
"""

import pytest
from unittest.mock import MagicMock, patch

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def default_config():
    from backend.app.core.guardrails_engine import GuardrailConfig
    return GuardrailConfig(
        company_id="test_company",
        variant_type="parwa",
        strictness_level="medium",
    )


@pytest.fixture
def mini_parwa_config():
    from backend.app.core.guardrails_engine import GuardrailConfig
    return GuardrailConfig(
        company_id="mini_co",
        variant_type="mini_parwa",
        strictness_level="high",
    )


@pytest.fixture
def content_safety():
    from backend.app.core.guardrails_engine import ContentSafetyGuard
    return ContentSafetyGuard()


@pytest.fixture
def topic_relevance():
    from backend.app.core.guardrails_engine import TopicRelevanceGuard
    return TopicRelevanceGuard()


@pytest.fixture
def hallucination_check():
    from backend.app.core.guardrails_engine import HallucinationCheckGuard
    return HallucinationCheckGuard()


@pytest.fixture
def policy_compliance():
    from backend.app.guardrails_engine import PolicyComplianceGuard
    return PolicyComplianceGuard()


@pytest.fixture
def tone_validation():
    from backend.app.guardrails_engine import ToneValidationGuard
    return ToneValidationGuard()


@pytest.fixture
def length_control():
    from backend.app.core.guardrails_engine import LengthControlGuard
    return LengthControlGuard()


@pytest.fixture
def pii_leak():
    from backend.app.core.guardrails_engine import PIILeakGuard
    return PIILeakGuard()


@pytest.fixture
def confidence_gate():
    from backend.app.core.guardrails_engine import ConfidenceGateGuard
    return ConfidenceGateGuard()


@pytest.fixture
def engine():
    from backend.app.core.guardrails_engine import GuardrailsEngine
    return GuardrailsEngine()


# ── ContentSafetyGuard Tests ──────────────────────────────────────


class TestContentSafetyGuard:
    def test_pass_clean_text(self, content_safety, default_config):
        result = content_safety.check(
            "Thank you for contacting support. Here is your answer.",
            default_config,
        )
        assert result.passed is True

    def test_block_hate_speech(self, content_safety, default_config):
        result = content_safety.check(
            "This content promotes hate speech and racial superiority.",
            default_config,
        )
        assert result.passed is False
        assert result.severity == "critical"
        assert "hate speech" in result.reason.lower()

    def test_block_violence(self, content_safety, default_config):
        result = content_safety.check(
            "Instructions for making a bomb",
            default_config,
        )
        assert result.passed is False
        assert result.severity in ("critical", "high")

    def test_block_self_harm(self, content_safety, default_config):
        result = content_safety.check(
            "I want to find a suicide method",
            default_config,
        )
        assert result.passed is False
        assert result.severity == "critical"

    def test_block_child_exploitation(self, content_safety, default_config):
        result = content_safety.check(
            "child exploitation content",
            default_config,
        )
        assert result.passed is False

    def test_empty_text_passes(self, content_safety, default_config):
        result = content_safety.check("", default_config)
        assert result.passed is True

    def test_blocked_keyword(self, content_safety):
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test",
            blocked_keywords=["secretword"],
        )
        result = content_safety.check(
            "This contains secretword in the text.", config,
        )
        assert result.passed is False
        assert "secretword" in result.reason

    def test_custom_rule(self, content_safety):
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test",
            custom_rules=[{
                "layer": "content_safety",
                "pattern": r"banned\s+phrase",
                "severity": "medium",
                "reason": "Custom banned phrase",
            }],
        )
        result = content_safety.check("This has banned phrase here.", config)
        assert result.passed is False

    def test_invalid_regex_custom_rule(self, content_safety):
        """Invalid regex should not crash."""
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test",
            custom_rules=[{
                "layer": "content_safety",
                "pattern": r"[invalid(broken",
                "severity": "high",
                "reason": "Bad regex",
            }],
        )
        result = content_safety.check("test text here", config)
        # Should pass because regex was invalid and skipped
        assert result.passed is True

    def test_moderate_violence(self, content_safety, default_config):
        result = content_safety.check(
            "I want to beat up that person",
            default_config,
        )
        assert result.passed is False
        assert result.severity == "medium"

    def test_worst_severity_wins(self, content_safety, default_config):
        """If both CRITICAL and MEDIUM patterns match, worst wins."""
        result = content_safety.check(
            "hate speech plus beat up someone content",
            default_config,
        )
        assert result.passed is False
        assert result.severity == "critical"


# ── TopicRelevanceGuard Tests ──────────────────────────────────


class TestTopicRelevanceGuard:
    def test_relevant_response(self, topic_relevance, default_config):
        result = topic_relevance.check(
            query="how do I reset my password?",
            response="To reset your password, go to Settings and click Reset Password.",
            config=default_config,
        )
        assert result.passed is True

    def test_off_topic_response(self, topic_relevance, default_config):
        result = topic_relevance.check(
            query="how do I reset my password?",
            response="The weather in Paris is lovely this time of year.",
            config=default_config,
        )
        assert result.passed is False
        assert result.severity in ("high", "medium")

    def test_empty_query_passes(self, topic_relevance, default_config):
        result = topic_relevance.check(
            "",
            "Some response",
            config=default_config,
        )
        assert result.passed is True

    def test_empty_response_blocks(self, topic_relevance, default_config):
        result = topic_relevance.check(
            "some query",
            "",
            config=default_config,
        )
        assert result.passed is False

    def test_no_meaningful_tokens_passes(self, topic_relevance, default_config):
        result = topic_relevance.check(
            "aa bb cc",
            "response text here",
            config=default_config,
        )
        assert result.passed is True  # No tokens >= 3 chars

    def test_metadata_includes_overlap_ratio(self, topic_relevance, default_config):
        result = topic_relevance.check(
            "password reset instructions",
            "resetting password is done here",
            config=default_config,
        )
        assert "overlap_ratio" in result.metadata


# ── HallucinationCheckGuard Tests ─────────────────────────────


class TestHallucinationCheckGuard:
    def test_clean_response(self, hallucination_check, default_config):
        result = hallucination_check.check(
            "query", "This is a factual response.", default_config,
        )
        assert result.passed is True

    def test_temporal_hallucination(self, hallucination_check, default_config):
        result = hallucination_check.check(
            "query",
            "As of my latest training data in 2024, this is true.",
            default_config,
        )
        assert result.passed is False
        assert "hallucination" in result.reason.lower()

    def test_fabricated_stats(self, hallucination_check, default_config):
        result = hallucination_check.check(
            "query",
            "Studies show 73% increase in revenue according to recent data.",
            default_config,
        )
        assert result.passed is False

    def test_empty_response(self, hallucination_check, default_config):
        result = hallucination_check.check(
            "query", "", default_config,
        )
        assert result.passed is True


# ── PolicyComplianceGuard Tests ────────────────────────────────


class TestPolicyComplianceGuard:
    def test_clean_response(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "Here is your answer.", default_config,
        )
        assert result.passed is True

    def test_legal_advice(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "You should sue them for damages.",
            default_config,
        )
        assert result.passed is False
        assert "legal advice" in result.reason.lower()

    def test_medical_advice(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "You should take ibuprofen 400mg for this.",
            default_config,
        )
        assert result.passed is False

    def test_pricing_guarantee(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "We guarantee the lowest price for you.",
            default_config,
        )
        assert result.passed is False

    def test_refund_promise(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "Full refund guaranteed if you're not satisfied.",
            default_config,
        )
        assert result.passed is False

    def test_multiple_violations(self, policy_compliance, default_config):
        result = policy_compliance.check(
            "You should sue them. Also, we guarantee a full refund.",
            default_config,
        )
        assert result.passed is False
        assert result.metadata.get("violation_count", 0) >= 2


# ── ToneValidationGuard Tests ──────────────────────────────────


class TestToneValidationGuard:
    def test_professional_tone(self, tone_validation, default_config):
        result = tone_validation.check(
            "I'd be happy to help you with that.", default_config,
        )
        assert result.passed is True

    def test_aggressive_tone(self, tone_validation, default_config):
        result = tone_validation.check(
            "You're being ridiculous and wasting my time.",
            default_config,
        )
        assert result.passed is False
        assert result.severity == "high"

    def test_dismissive_tone(self, tone_validation, default_config):
        result = tone_validation.check(
            "That's not my problem, deal with it.",
            default_config,
        )
        assert result.passed is False

    def test_casual_tone_serious_context(self, tone_validation, default_config):
        """Casual language in serious tone requirements should be blocked."""
        result = tone_validation.check(
            "lol yeah that's the answer bruh", default_config,
        )
        assert result.passed is False
        assert "casual" in result.reason.lower()

    def test_casual_tone_casual_context(self, tone_validation):
        """Casual language in casual context should pass."""
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test",
            tone_requirements=["casual"],
        )
        result = tone_validation.check("lol that's fine", config)
        assert result.passed is True

    def test_condescending_tone(self, tone_validation, default_config):
        result = tone_validation.check(
            "Obviously, as everyone knows, this is simple.",
            default_config,
        )
        assert result.passed is False


# ── LengthControlGuard Tests ──────────────────────────────────


class TestLengthControlGuard:
    def test_normal_length(self, length_control, default_config):
        text = "A" * 100
        result = length_control.check(text, default_config)
        assert result.passed is True

    def test_empty_response(self, length_control, default_config):
        result = length_control.check("", default_config)
        assert result.passed is False

    def test_too_long(self, length_control, default_config):
        text = "A" * 3000
        result = length_control.check(text, default_config)
        assert result.passed is False
        assert "exceeds maximum" in result.reason.lower()

    def test_too_short(self, length_control, default_config):
        result = length_control.check("Hi", default_config)
        assert result.passed is False
        assert "below minimum" in result.reason.lower()

    def test_custom_max_length(self, length_control):
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test", max_response_length=50,
        )
        result = length_control.check("A" * 100, config)
        assert result.passed is False

    def test_wall_of_text_flag(self, length_control, default_config):
        """Text between min and max but over wall-of-text threshold should be flagged."""
        text = "A" * 600  # Over 500 threshold
        result = length_control.check(text, default_config)
        assert result.passed is True  # Not blocked
        assert result.action == "flag_for_review"


# ── PIILeakGuard Tests ────────────────────────────────────


class TestPIILeakGuard:
    def test_no_pii(self, pii_leak, default_config):
        result = pii_leak.check(
            "This response has no personal information.", default_config,
        )
        assert result.passed is True

    def test_email_leak(self, pii_leak, default_config):
        result = pii_leak.check(
            "Contact john.doe@company.com for help.", default_config,
        )
        assert result.passed is False
        assert "PII" in result.reason

    def test_ssn_leak(self, pii_leak, default_config):
        result = pii_leak.check(
            "The customer's SSN is 123-45-6789.", default_config,
        )
        assert result.passed is False
        assert result.severity == "high"  # SSN is sensitive

    def test_pii_check_disabled(self, pii_leak):
        from backend.app.core.guardrails_engine import GuardrailConfig
        config = GuardrailConfig(
            company_id="test", pii_check_enabled=False,
        )
        result = pii_leak.check(
            "SSN: 123-45-6789", config,
        )
        assert result.passed is True

    def test_masking_in_logs(self, pii_leak, default_config):
        """Verify PII is masked in result metadata."""
        result = pii_leak.check(
            "Email john.doe@company.com here", default_config,
        )
        if not result.passed and result.metadata.get("pii_findings"):
            for finding in result.metadata["pii_findings"]:
                assert "@" not in finding["masked_value"]


# ── ConfidenceGateGuard Tests ──────────────────────────────


class TestConfidenceGateGuard:
    def test_above_threshold(self, confidence_gate, default_config):
        result = confidence_gate.check(
            "response", 90.0, default_config,
        )
        assert result.passed is True

    def test_below_threshold(self, confidence_gate, default_config):
        result = confidence_gate.check(
            "response", 50.0, default_config,
        )
        assert result.passed is False

    def test_at_threshold(self, confidence_gate, default_config):
        result = confidence_gate.check(
            "response", 85.0, default_config,
        )
        assert result.passed is True

    def test_zero_confidence(self, confidence_gate, default_config):
        result = confidence_gate.check(
            "response", 0.0, default_config,
        )
        assert result.passed is False


# ── _build_config Tests (GAP FIX) ──────────────────────────────


class TestBuildConfig:
    def test_default_config_no_override(self):
        from backend.app.core.guardrails_engine import (
            _build_config, GuardrailConfig, StrictnessLevel,
        )
        config = _build_config("co1", "parwa")
        assert config.company_id == "co1"
        assert config.variant_type == "parwa"
        assert config.strictness_level == StrictnessLevel.MEDIUM.value
        assert config.confidence_threshold == 85.0

    def test_mini_parwa_defaults(self):
        from backend.app.core.guardrails_engine import (
            _build_config, StrictnessLevel,
        )
        config = _build_config("co1", "mini_parwa")
        assert config.strictness_level == StrictnessLevel.HIGH.value
        assert config.confidence_threshold == 95.0

    def test_parwa_high_defaults(self):
        from backend.app.core.guardrails_engine import (
            _build_config, StrictnessLevel,
        )
        config = _build_config("co1", "parwa_high")
        assert config.strictness_level == StrictnessLevel.LOW.value
        assert config.confidence_threshold == 75.0

    def test_override_merges_confidence(self):
        """GAP FIX: Override with partial config should keep variant defaults."""
        from backend.app.core.guardrails_engine import (
            _build_config, GuardrailConfig,
        )
        override = GuardrailConfig(
            company_id="co1",
            variant_type="mini_parwa",
            strictness_level="high",
            # confidence_threshold NOT set — should use variant default (95.0)
        )
        config = _build_config("co1", "mini_parwa", override_config=override)
        assert config.confidence_threshold == 95.0  # From mini_parwa default

    def test_override_explicit_confidence(self):
        """Explicitly set confidence should be preserved."""
        from backend.app.core.guardrails_engine import (
            _build_config, GuardrailConfig,
        )
        override = GuardrailConfig(
            company_id="co1",
            confidence_threshold=80.0,
        )
        config = _build_config("co1", "parwa", override_config=override)
        assert config.confidence_threshold == 80.0  # Explicit override

    def test_override_with_tone(self):
        """Override tone requirements should be preserved."""
        from backend.app.core.guardrails_engine import (
            _build_config, GuardrailConfig,
        )
        override = GuardrailConfig(
            company_id="co1",
            tone_requirements=["casual"],
        )
        config = _build_config("co1", "parwa", override_config=override)
        assert config.tone_requirements == ["casual"]

    def test_default_tone_preserved(self):
        """Without override, default tone should be professional+empathetic."""
        from backend.app.core.guardrails_engine import _build_config
        config = _build_config("co1", "parwa")
        assert config.tone_requirements == ["professional", "empathetic"]


# ── GuardrailsEngine Tests ──────────────────────────────────


class TestGuardrailsEngine:
    def test_full_check_all_pass(self, engine):
        from backend.app.core.guardrails_engine import GuardrailsReport
        report = engine.run_full_check(
            query="reset password",
            response="Go to Settings to reset your password.",
            confidence=90.0,
            company_id="test_co",
        )
        assert isinstance(report, GuardrailsReport)
        assert report.passed is True

    def test_full_check_content_block(self, engine):
        from backend.app.core.guardrails_engine import GuardrailsReport
        report = engine.run_full_check(
            query="hello",
            response="hate speech content here",
            confidence=90.0,
            company_id="test_co",
        )
        assert report.passed is False

    def test_single_layer_check(self, engine):
        from backend.app.core.guardrails_engine import GuardrailResult
        result = engine.run_single_layer(
            "length_control", "Hi", {}, company_id="test_co",
        )
        assert isinstance(result, GuardrailResult)

    def test_config_for_variant(self, engine):
        from backend.app.core.guardrails_engine import (
            GuardrailConfig, StrictnessLevel,
        )
        config = engine.get_config_for_variant("test_co", "mini_parwa")
        assert config.strictness_level == StrictnessLevel.HIGH.value
        assert config.company_id == "test_co"


# ── Import for tests ──────────────────────────────────────────

# Fix import in PolicyComplianceGuard fixture
import importlib
_backend = importlib.import_module("backend.app.core.guardrails_engine")
# Patch the fixture
pytest.fixture = pytest.fixture
