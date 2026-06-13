"""
Unit tests for Shadow Mode Service (Phase 4 Feature Completion).

Tests cover:
  - Enable/disable shadow mode
  - SHADOW→SUPERVISED→GRADUATED progression
  - Sample rate filtering
  - Comparison recording and auto-graduation
  - Quality streak tracking
  - Human review workflow
  - Statistics and comparison history
  - Edge cases and error handling
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.shadow_mode_service import (
    ShadowModeService,
    ShadowComparison,
    ShadowModeStatus,
    get_shadow_mode_service,
    VALID_VARIANT_TYPES,
    VARIANT_RANKING,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def service():
    """Create a fresh ShadowModeService instance for each test."""
    return ShadowModeService()


@pytest.fixture
def company_id():
    """Sample company ID."""
    return "comp_shadow_test_001"


@pytest.fixture
def enabled_service(service, company_id):
    """Service with shadow mode enabled for a test company."""
    service.enable_shadow_mode(
        company_id=company_id,
        live_variant="mini_parwa",
        shadow_variant="parwa",
        sample_rate=1.0,
    )
    return service


# ══════════════════════════════════════════════════════════════════
# ENABLE SHADOW MODE TESTS
# ══════════════════════════════════════════════════════════════════


class TestEnableShadowMode:
    """Tests for enabling shadow mode."""

    def test_enable_success(self, service, company_id):
        """Test successful shadow mode enablement."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        assert result["success"] is True
        assert result["status"] == "shadow"
        assert result["live_variant"] == "mini_parwa"
        assert result["shadow_variant"] == "parwa"
        assert "config_id" in result

    def test_enable_with_custom_settings(self, service, company_id):
        """Test enablement with custom sample rate and thresholds."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="parwa_high",
            sample_rate=0.5,
            auto_graduation_threshold=0.90,
            auto_graduation_window=50,
            supervised_timeout_seconds=600,
        )
        assert result["success"] is True
        assert result["sample_rate"] == 0.5

    def test_enable_rejects_invalid_live_variant(self, service, company_id):
        """Test that invalid live_variant is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="invalid_variant",
            shadow_variant="parwa",
        )
        assert result["success"] is False
        assert "Invalid live_variant" in result["error"]

    def test_enable_rejects_invalid_shadow_variant(self, service, company_id):
        """Test that invalid shadow_variant is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="not_a_variant",
        )
        assert result["success"] is False
        assert "Invalid shadow_variant" in result["error"]

    def test_enable_rejects_downgrade_direction(self, service, company_id):
        """Test that shadow variant lower than live is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="mini_parwa",
        )
        assert result["success"] is False
        assert "must be higher" in result["error"]

    def test_enable_rejects_same_variant(self, service, company_id):
        """Test that same live and shadow variant is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="parwa",
        )
        assert result["success"] is False

    def test_enable_rejects_invalid_sample_rate(self, service, company_id):
        """Test that invalid sample rate is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=0.0,
        )
        assert result["success"] is False
        assert "sample rate" in result["error"].lower()

    def test_enable_rejects_sample_rate_above_one(self, service, company_id):
        """Test that sample rate > 1.0 is rejected."""
        result = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=1.5,
        )
        assert result["success"] is False

    def test_enable_replaces_existing_config(self, service, company_id):
        """Test that enabling when already active disables the old config first."""
        # Enable once
        result1 = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        assert result1["success"] is True

        # Enable again with different config
        result2 = service.enable_shadow_mode(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="parwa_high",
        )
        assert result2["success"] is True
        assert result2["live_variant"] == "parwa"
        assert result2["shadow_variant"] == "parwa_high"

    def test_enable_all_tier_combinations(self, service, company_id):
        """Test all valid tier upgrade combinations."""
        valid_combos = [
            ("mini_parwa", "parwa"),
            ("mini_parwa", "parwa_high"),
            ("parwa", "parwa_high"),
        ]
        for live, shadow in valid_combos:
            svc = ShadowModeService()  # Fresh for each
            result = svc.enable_shadow_mode(
                company_id=company_id,
                live_variant=live,
                shadow_variant=shadow,
            )
            assert result["success"] is True, f"Failed for {live} → {shadow}"


# ══════════════════════════════════════════════════════════════════
# DISABLE SHADOW MODE TESTS
# ══════════════════════════════════════════════════════════════════


class TestDisableShadowMode:
    """Tests for disabling shadow mode."""

    def test_disable_success(self, enabled_service, company_id):
        """Test successful disablement."""
        result = enabled_service.disable_shadow_mode(
            company_id=company_id,
            reason="testing complete",
        )
        assert result["success"] is True

    def test_disable_no_active_config(self, service, company_id):
        """Test disabling when no config exists."""
        result = service.disable_shadow_mode(company_id=company_id)
        assert result["success"] is False
        assert "No active" in result["error"]

    def test_status_after_disable(self, enabled_service, company_id):
        """Test that status is disabled after disablement."""
        enabled_service.disable_shadow_mode(company_id=company_id)
        status = enabled_service.get_status(company_id=company_id)
        assert status.is_active is False
        assert status.status == "disabled"


# ══════════════════════════════════════════════════════════════════
# GET STATUS TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetStatus:
    """Tests for getting shadow mode status."""

    def test_status_when_disabled(self, service, company_id):
        """Test status when shadow mode is not enabled."""
        status = service.get_status(company_id=company_id)
        assert status.is_active is False
        assert status.status == "disabled"

    def test_status_when_enabled(self, enabled_service, company_id):
        """Test status when shadow mode is active."""
        status = enabled_service.get_status(company_id=company_id)
        assert status.is_active is True
        assert status.status == "shadow"
        assert status.live_variant == "mini_parwa"
        assert status.shadow_variant == "parwa"
        assert status.sample_rate == 1.0

    def test_status_with_comparisons(self, enabled_service, company_id):
        """Test status reflects comparison counts."""
        # Record some comparisons
        for i in range(5):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test_config",
                shadow_winner=True,
                quality_delta=0.05,
                latency_delta_ms=100,
            )
            enabled_service.record_comparison(company_id=company_id, comparison=comp)

        status = enabled_service.get_status(company_id=company_id)
        assert status.total_comparisons == 5
        assert status.shadow_wins == 5
        assert status.win_rate == 1.0


# ══════════════════════════════════════════════════════════════════
# SHOULD PROCESS SHADOW TESTS
# ══════════════════════════════════════════════════════════════════


class TestShouldProcessShadow:
    """Tests for determining if a message should be shadow-processed."""

    def test_should_process_when_active(self, enabled_service, company_id):
        """Test that messages are processed when shadow mode is active."""
        should, reason = enabled_service.should_process_shadow(
            company_id=company_id,
        )
        assert should is True
        assert "shadow" in reason

    def test_should_not_process_when_disabled(self, service, company_id):
        """Test that messages are not processed when shadow mode is disabled."""
        should, reason = service.should_process_shadow(company_id=company_id)
        assert should is False
        assert "no_active" in reason

    def test_sample_rate_filtering(self, service, company_id):
        """Test that sample rate controls which messages are processed."""
        # Enable with very low sample rate
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=0.01,  # 1% sample rate
        )

        # Run many times - most should be excluded
        processed = 0
        total = 1000
        for _ in range(total):
            should, _ = service.should_process_shadow(company_id=company_id)
            if should:
                processed += 1

        # With 1% sample rate, expect roughly 1% (allow wide margin)
        assert processed < total * 0.1  # Less than 10% should pass

    def test_should_not_process_when_graduated(self, enabled_service, company_id):
        """Test that messages are not processed after graduation."""
        enabled_service.promote(company_id=company_id, target_status="graduated")
        should, reason = enabled_service.should_process_shadow(
            company_id=company_id,
        )
        assert should is False
        assert "graduated" in reason


# ══════════════════════════════════════════════════════════════════
# COMPARISON RECORDING TESTS
# ══════════════════════════════════════════════════════════════════


class TestRecordComparison:
    """Tests for recording comparison results."""

    def test_record_shadow_win(self, enabled_service, company_id):
        """Test recording a comparison where shadow wins."""
        comp = ShadowComparison(
            company_id=company_id,
            config_id="test",
            shadow_winner=True,
            quality_delta=0.1,
            live_quality_score=0.7,
            shadow_quality_score=0.8,
        )
        result = enabled_service.record_comparison(
            company_id=company_id, comparison=comp,
        )
        assert result["success"] is True
        assert result["total_comparisons"] == 1
        assert result["shadow_wins"] == 1
        assert result["current_quality_streak"] == 1

    def test_record_live_win(self, enabled_service, company_id):
        """Test recording a comparison where live wins."""
        comp = ShadowComparison(
            company_id=company_id,
            config_id="test",
            shadow_winner=False,
            quality_delta=-0.1,
            live_quality_score=0.8,
            shadow_quality_score=0.7,
        )
        result = enabled_service.record_comparison(
            company_id=company_id, comparison=comp,
        )
        assert result["success"] is True
        assert result["shadow_wins"] == 0
        assert result["current_quality_streak"] == 0

    def test_streak_resets_on_live_win(self, enabled_service, company_id):
        """Test that quality streak resets when live wins."""
        # Build up a streak
        for _ in range(5):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        status = enabled_service.get_status(company_id=company_id)
        assert status.current_quality_streak == 5

        # Live wins - streak should reset
        comp = ShadowComparison(
            company_id=company_id,
            config_id="test",
            shadow_winner=False,
            quality_delta=-0.1,
        )
        enabled_service.record_comparison(
            company_id=company_id, comparison=comp,
        )

        status = enabled_service.get_status(company_id=company_id)
        assert status.current_quality_streak == 0

    def test_auto_graduation_to_supervised(self, service, company_id):
        """Test auto-graduation from shadow to supervised after streak."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=10,
            auto_promote_to_supervised=True,
        )

        # Record 10 consecutive shadow wins
        for _ in range(10):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            result = service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        # Should have auto-graduated
        status = service.get_status(company_id=company_id)
        assert status.status == "supervised"

    def test_no_auto_graduation_when_disabled(self, service, company_id):
        """Test that auto-graduation doesn't happen when disabled."""
        service.enable_shadow_mode(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=5,
            auto_promote_to_supervised=False,  # Disabled
        )

        # Record 5 consecutive wins
        for _ in range(5):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            service.record_comparison(company_id=company_id, comparison=comp)

        status = service.get_status(company_id=company_id)
        assert status.status == "shadow"  # Still in shadow


# ══════════════════════════════════════════════════════════════════
# PROMOTE TESTS
# ══════════════════════════════════════════════════════════════════


class TestPromote:
    """Tests for manual promotion."""

    def test_promote_shadow_to_supervised(self, enabled_service, company_id):
        """Test promoting from shadow to supervised."""
        result = enabled_service.promote(company_id=company_id)
        assert result["success"] is True
        assert result["new_status"] == "supervised"

    def test_promote_supervised_to_graduated(self, enabled_service, company_id):
        """Test promoting from supervised to graduated."""
        enabled_service.promote(company_id=company_id)  # shadow → supervised
        result = enabled_service.promote(company_id=company_id)
        assert result["success"] is True
        assert result["new_status"] == "graduated"

    def test_promote_with_target_status(self, enabled_service, company_id):
        """Test promoting directly to a target status."""
        result = enabled_service.promote(
            company_id=company_id,
            target_status="graduated",
        )
        assert result["success"] is True
        assert result["new_status"] == "graduated"

    def test_promote_invalid_target(self, enabled_service, company_id):
        """Test promoting to an invalid target status."""
        result = enabled_service.promote(
            company_id=company_id,
            target_status="invalid_status",
        )
        assert result["success"] is False

    def test_promote_no_active_config(self, service, company_id):
        """Test promoting when no config exists."""
        result = service.promote(company_id=company_id)
        assert result["success"] is False
        assert "No active" in result["error"]


# ══════════════════════════════════════════════════════════════════
# COMPLETE GRADUATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestCompleteGraduation:
    """Tests for completing graduation."""

    def test_graduation_from_supervised(self, enabled_service, company_id):
        """Test completing graduation from supervised mode."""
        enabled_service.promote(company_id=company_id)  # shadow → supervised
        result = enabled_service.complete_graduation(company_id=company_id)
        assert result["success"] is True
        assert result["new_live_variant"] == "parwa"

    def test_graduation_from_graduated(self, enabled_service, company_id):
        """Test completing graduation from already graduated status."""
        enabled_service.promote(company_id=company_id, target_status="graduated")
        result = enabled_service.complete_graduation(company_id=company_id)
        assert result["success"] is True

    def test_graduation_from_shadow_rejected(self, enabled_service, company_id):
        """Test that graduation from shadow status is rejected."""
        result = enabled_service.complete_graduation(company_id=company_id)
        assert result["success"] is False
        assert "Cannot complete graduation" in result["error"]

    def test_graduation_disables_config(self, enabled_service, company_id):
        """Test that graduation disables the shadow mode config."""
        enabled_service.promote(company_id=company_id, target_status="graduated")
        enabled_service.complete_graduation(company_id=company_id)
        status = enabled_service.get_status(company_id=company_id)
        assert status.is_active is False


# ══════════════════════════════════════════════════════════════════
# COMPARISON HISTORY TESTS
# ══════════════════════════════════════════════════════════════════


class TestComparisonHistory:
    """Tests for comparison history retrieval."""

    def test_empty_history(self, enabled_service, company_id):
        """Test getting history when no comparisons exist."""
        history = enabled_service.get_comparison_history(company_id=company_id)
        assert history == []

    def test_history_with_comparisons(self, enabled_service, company_id):
        """Test getting history with comparisons."""
        for i in range(5):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=(i % 2 == 0),
                quality_delta=0.05 if i % 2 == 0 else -0.05,
                latency_delta_ms=100,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        history = enabled_service.get_comparison_history(company_id=company_id)
        assert len(history) > 0

    def test_history_with_pagination(self, enabled_service, company_id):
        """Test history pagination."""
        for i in range(20):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        page1 = enabled_service.get_comparison_history(
            company_id=company_id, limit=5, offset=0,
        )
        page2 = enabled_service.get_comparison_history(
            company_id=company_id, limit=5, offset=5,
        )
        assert len(page1) <= 5
        assert len(page2) <= 5


# ══════════════════════════════════════════════════════════════════
# STATISTICS TESTS
# ══════════════════════════════════════════════════════════════════


class TestStatistics:
    """Tests for shadow mode statistics."""

    def test_statistics_no_config(self, service, company_id):
        """Test statistics when no config exists."""
        stats = service.get_statistics(company_id=company_id)
        assert stats["is_active"] is False

    def test_statistics_with_comparisons(self, enabled_service, company_id):
        """Test statistics with recorded comparisons."""
        for _ in range(10):
            comp = ShadowComparison(
                company_id=company_id,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
                latency_delta_ms=100,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        stats = enabled_service.get_statistics(company_id=company_id)
        assert stats["total_comparisons"] == 10
        assert stats["shadow_wins"] == 10
        assert stats["win_rate"] == 1.0
        assert stats["current_quality_streak"] == 10

    def test_statistics_mixed_results(self, enabled_service, company_id):
        """Test statistics with mixed win/loss results."""
        # 3 wins
        for _ in range(3):
            comp = ShadowComparison(
                company_id=company_id, config_id="test",
                shadow_winner=True, quality_delta=0.05,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        # 2 losses
        for _ in range(2):
            comp = ShadowComparison(
                company_id=company_id, config_id="test",
                shadow_winner=False, quality_delta=-0.05,
            )
            enabled_service.record_comparison(
                company_id=company_id, comparison=comp,
            )

        stats = enabled_service.get_statistics(company_id=company_id)
        assert stats["total_comparisons"] == 5
        assert stats["shadow_wins"] == 3
        assert stats["win_rate"] == 0.6


# ══════════════════════════════════════════════════════════════════
# HUMAN REVIEW TESTS
# ══════════════════════════════════════════════════════════════════


class TestHumanReview:
    """Tests for human review workflow."""

    def test_valid_review_verdicts(self, enabled_service, company_id):
        """Test all valid review verdicts."""
        valid_verdicts = ("shadow_better", "live_better", "equal", "skip")
        for verdict in valid_verdicts:
            result = enabled_service.record_human_review(
                company_id=company_id,
                result_id="result_001",
                verdict=verdict,
                reviewer_id="reviewer_001",
                notes="Test review",
            )
            assert result["success"] is True
            assert result["verdict"] == verdict

    def test_invalid_review_verdict(self, enabled_service, company_id):
        """Test that invalid verdicts are rejected."""
        result = enabled_service.record_human_review(
            company_id=company_id,
            result_id="result_001",
            verdict="invalid_verdict",
        )
        assert result["success"] is False
        assert "Invalid verdict" in result["error"]


# ══════════════════════════════════════════════════════════════════
# DATA CLASS TESTS
# ══════════════════════════════════════════════════════════════════


class TestDataClasses:
    """Tests for data class serialization."""

    def test_shadow_comparison_to_dict(self):
        """Test ShadowComparison serialization."""
        comp = ShadowComparison(
            company_id="comp1",
            config_id="config1",
            ticket_id="ticket1",
            live_variant="mini_parwa",
            shadow_variant="parwa",
            shadow_winner=True,
            quality_delta=0.05,
        )
        d = comp.to_dict()
        assert d["company_id"] == "comp1"
        assert d["shadow_winner"] is True
        assert d["quality_delta"] == 0.05

    def test_shadow_mode_status_to_dict(self):
        """Test ShadowModeStatus serialization."""
        status = ShadowModeStatus(
            company_id="comp1",
            is_active=True,
            status="shadow",
            live_variant="mini_parwa",
            shadow_variant="parwa",
            total_comparisons=10,
            shadow_wins=8,
            win_rate=0.8,
        )
        d = status.to_dict()
        assert d["company_id"] == "comp1"
        assert d["is_active"] is True
        assert d["win_rate"] == 0.8


# ══════════════════════════════════════════════════════════════════
# SINGLETON TESTS
# ══════════════════════════════════════════════════════════════════


class TestSingleton:
    """Tests for the singleton pattern."""

    def test_get_shadow_mode_service_returns_instance(self):
        """Test that the singleton getter returns a service instance."""
        service = get_shadow_mode_service()
        assert isinstance(service, ShadowModeService)

    def test_get_shadow_mode_service_returns_same_instance(self):
        """Test that repeated calls return the same instance."""
        service1 = get_shadow_mode_service()
        service2 = get_shadow_mode_service()
        assert service1 is service2


# ══════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_multiple_companies_isolated(self, service):
        """Test that shadow mode configs are isolated per company."""
        service.enable_shadow_mode(
            company_id="company_A",
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        service.enable_shadow_mode(
            company_id="company_B",
            live_variant="parwa",
            shadow_variant="parwa_high",
        )

        status_a = service.get_status(company_id="company_A")
        status_b = service.get_status(company_id="company_B")

        assert status_a.live_variant == "mini_parwa"
        assert status_b.live_variant == "parwa"
        assert status_a.shadow_variant == "parwa"
        assert status_b.shadow_variant == "parwa_high"

    def test_comparisons_isolated_per_company(self, service):
        """Test that comparisons are isolated per company."""
        service.enable_shadow_mode(
            company_id="company_A",
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        service.enable_shadow_mode(
            company_id="company_B",
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        comp_a = ShadowComparison(
            company_id="company_A",
            config_id="test",
            shadow_winner=True,
            quality_delta=0.05,
        )
        service.record_comparison(company_id="company_A", comparison=comp_a)

        stats_b = service.get_statistics(company_id="company_B")
        assert stats_b["total_comparisons"] == 0

    def test_hash_message_deterministic(self, service):
        """Test that message hashing is deterministic."""
        hash1 = service._hash_message("hello world")
        hash2 = service._hash_message("hello world")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

    def test_hash_message_different_for_different_input(self, service):
        """Test that different messages produce different hashes."""
        hash1 = service._hash_message("hello")
        hash2 = service._hash_message("world")
        assert hash1 != hash2
