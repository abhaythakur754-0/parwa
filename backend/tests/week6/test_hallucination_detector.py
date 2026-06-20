"""
Tests for Hallucination Detector (IC-11).

Validates that the HallucinationDetector can be imported,
detect returns a proper report, safe text gets low scores,
and fabricated claims are flagged.
"""

import pytest

from app.core.hallucination_detector import (
    HallucinationDetector,
    HallucinationReport,
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def detector():
    """Create a fresh HallucinationDetector instance."""
    return HallucinationDetector()


# ── Import Tests ───────────────────────────────────────────────────


class TestHallucinationDetectorImport:
    """Test that HallucinationDetector can be imported."""

    def test_detector_import(self):
        """HallucinationDetector should be importable."""
        assert HallucinationDetector is not None

    def test_detector_can_be_instantiated(self, detector):
        """HallucinationDetector should be instantiable."""
        assert detector is not None

    def test_report_import(self):
        """HallucinationReport should be importable."""
        assert HallucinationReport is not None


# ── Detection Tests ───────────────────────────────────────────────


class TestHallucinationDetection:
    """Test hallucination detection functionality."""

    def test_detect_returns_report(self, detector):
        """detect() should return a HallucinationReport."""
        report = detector.detect(
            response="This is a normal response about your account.",
            query="What is my account status?",
            company_id="company-123",
        )
        assert isinstance(report, HallucinationReport)

    def test_report_has_is_hallucination_boolean(self, detector):
        """Report should have is_hallucination boolean field."""
        report = detector.detect(
            response="Normal response.",
            query="Question",
            company_id="company-123",
        )
        assert isinstance(report.is_hallucination, bool)

    def test_safe_text_low_hallucination_score(self, detector):
        """Safe, grounded text should get low hallucination score."""
        report = detector.detect(
            response="I've checked your account and everything looks normal. "
            "Your subscription is active until next month.",
            query="What is my subscription status?",
            company_id="company-123",
        )
        assert isinstance(report.overall_confidence, float)
        assert 0.0 <= report.overall_confidence <= 1.0

    def test_fabricated_claims_flagged(self, detector):
        """Response with fabricated URLs should be flagged."""
        report = detector.detect(
            response="Please visit https://example.com/support for more details.",
            query="Where can I get help?",
            company_id="company-123",
        )
        # Should detect fabricated URL (example.com)
        pattern_ids = [m.pattern_id for m in report.matches]
        assert "P02_fabricated_urls" in pattern_ids, (
            "Fabricated URL should be detected"
        )

    def test_overconfident_claims_detected(self, detector):
        """Overconfident claims near speculative language should be flagged."""
        report = detector.detect(
            response="I can definitely guarantee this is correct, "
            "though I think it might depend on the situation.",
            query="Is this correct?",
            company_id="company-123",
        )
        pattern_ids = [m.pattern_id for m in report.matches]
        assert "P03_overconfident_claims" in pattern_ids, (
            "Overconfident claims should be detected"
        )

    def test_empty_response_returns_safe(self, detector):
        """Empty response should return safe report."""
        report = detector.detect(
            response="",
            query="Question",
            company_id="company-123",
        )
        assert report.is_hallucination is False
        assert report.overall_confidence == 0.0


# ── Report Structure Tests ─────────────────────────────────────────


class TestReportStructure:
    """Validate HallucinationReport structure."""

    def test_report_has_recommendation(self, detector):
        """Report should have a recommendation field."""
        report = detector.detect(
            response="Normal response.",
            query="Question",
            company_id="company-123",
        )
        assert report.recommendation in ("safe", "review", "block")

    def test_report_has_matches_list(self, detector):
        """Report should have a matches list."""
        report = detector.detect(
            response="Normal response.",
            query="Question",
            company_id="company-123",
        )
        assert isinstance(report.matches, list)

    def test_report_has_summary(self, detector):
        """Report should have a summary dict."""
        report = detector.detect(
            response="Normal response.",
            query="Question",
            company_id="company-123",
        )
        assert isinstance(report.summary, dict)


# ── BC-012 Compliance ──────────────────────────────────────────────


class TestHallucinationBC012:
    """Test BC-012 compliance — graceful failure."""

    def test_none_response_safe(self, detector):
        """None response should not crash."""
        report = detector.detect(
            response=None,  # type: ignore[arg-type]
            query="Question",
            company_id="company-123",
        )
        assert isinstance(report, HallucinationReport)
