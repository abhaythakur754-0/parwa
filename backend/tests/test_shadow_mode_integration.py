"""
Integration tests for Shadow Mode + VariantService + Pipeline Bridge.

Tests cover:
  - End-to-end shadow mode flow: enable → process → compare → graduate
  - Shadow mode integration with variant pipeline bridge
  - VariantService resolve_for_shadow integration
  - Full SHADOW→SUPERVISED→GRADUATED progression
  - Multi-tenant isolation in shadow mode
  - API router integration
  - Database model creation and validation
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.shadow_mode_service import (
    ShadowModeService,
    ShadowComparison,
    ShadowModeStatus,
    get_shadow_mode_service,
)
from app.core.variant_service import (
    VariantService,
    VariantConfig,
)
from app.core.variant_pipeline_bridge import PipelineResult


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def shadow_service():
    """Create a fresh ShadowModeService."""
    return ShadowModeService()


@pytest.fixture
def variant_service():
    """Create a VariantService instance."""
    return VariantService()


@pytest.fixture
def company_a():
    """Company A ID."""
    return "company_A_integration"


@pytest.fixture
def company_b():
    """Company B ID."""
    return "company_B_integration"


# ══════════════════════════════════════════════════════════════════
# END-TO-END SHADOW MODE FLOW
# ══════════════════════════════════════════════════════════════════


class TestEndToEndShadowModeFlow:
    """Integration tests for the complete shadow mode lifecycle."""

    def test_full_shadow_to_graduated_flow(self, shadow_service, company_a):
        """Test complete flow: enable → shadow → supervised → graduated."""
        # Step 1: Enable shadow mode
        result = shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=5,
            auto_promote_to_supervised=True,
        )
        assert result["success"] is True
        assert result["status"] == "shadow"

        # Step 2: Verify shadow mode is active
        status = shadow_service.get_status(company_id=company_a)
        assert status.is_active is True
        assert status.status == "shadow"

        # Step 3: Process messages and record comparisons
        for i in range(5):
            comp = ShadowComparison(
                company_id=company_a,
                config_id=result.get("config_id", ""),
                ticket_id=f"ticket_{i}",
                live_variant="mini_parwa",
                shadow_variant="parwa",
                live_quality_score=0.70,
                shadow_quality_score=0.80,
                quality_delta=0.10,
                shadow_winner=True,
                mode_at_comparison="shadow",
            )
            record = shadow_service.record_comparison(
                company_id=company_a, comparison=comp,
            )
            assert record["success"] is True

        # Step 4: Should have auto-promoted to supervised
        status = shadow_service.get_status(company_id=company_a)
        assert status.status == "supervised"
        assert status.total_comparisons == 5
        assert status.shadow_wins == 5

        # Step 5: Manually graduate
        grad_result = shadow_service.complete_graduation(company_id=company_a)
        assert grad_result["success"] is True
        assert grad_result["new_live_variant"] == "parwa"

        # Step 6: Verify shadow mode is now disabled
        status = shadow_service.get_status(company_id=company_a)
        assert status.is_active is False

    def test_shadow_mode_with_mixed_results(self, shadow_service, company_a):
        """Test shadow mode with mixed quality results."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=10,
        )

        # Mix of wins and losses
        results = [True, True, False, True, True, False, True, True]
        for win in results:
            comp = ShadowComparison(
                company_id=company_a,
                config_id="test",
                shadow_winner=win,
                quality_delta=0.05 if win else -0.05,
                live_quality_score=0.70 if not win else 0.65,
                shadow_quality_score=0.70 if win else 0.65,
            )
            shadow_service.record_comparison(
                company_id=company_a, comparison=comp,
            )

        stats = shadow_service.get_statistics(company_id=company_a)
        assert stats["total_comparisons"] == 8
        assert stats["shadow_wins"] == 6
        assert stats["win_rate"] == 0.75

    def test_shadow_mode_disable_mid_flow(self, shadow_service, company_a):
        """Test disabling shadow mode mid-flow."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        # Record a few comparisons
        for _ in range(3):
            comp = ShadowComparison(
                company_id=company_a,
                config_id="test",
                shadow_winner=True,
                quality_delta=0.05,
            )
            shadow_service.record_comparison(
                company_id=company_a, comparison=comp,
            )

        # Disable mid-flow
        result = shadow_service.disable_shadow_mode(
            company_id=company_a, reason="emergency stop",
        )
        assert result["success"] is True

        # Should no longer process
        should, _ = shadow_service.should_process_shadow(company_id=company_a)
        assert should is False

    def test_shadow_mode_with_sample_rate(self, shadow_service, company_a):
        """Test shadow mode with reduced sample rate."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=0.5,
        )

        # Should process some messages
        processed = 0
        for _ in range(100):
            should, _ = shadow_service.should_process_shadow(company_id=company_a)
            if should:
                processed += 1

        # With 50% sample rate, expect roughly 50 out of 100
        assert 20 < processed < 80  # Wide margin for randomness


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE + VARIANT SERVICE INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestShadowModeVariantServiceIntegration:
    """Tests for Shadow Mode + VariantService working together."""

    def test_resolve_for_shadow_matches_config(self, shadow_service, variant_service, company_a):
        """Test that resolve_for_shadow returns configs matching shadow mode config."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        config = shadow_service.get_shadow_config(company_a)
        live_config, shadow_config = variant_service.resolve_for_shadow(
            company_id=company_a,
            live_variant=config["live_variant"],
            shadow_variant=config["shadow_variant"],
        )

        assert live_config.variant_tier == config["live_variant"]
        assert shadow_config.variant_tier == config["shadow_variant"]

    def test_shadow_variant_has_more_capabilities(self, variant_service, company_a):
        """Test that shadow variant always has >= capabilities than live."""
        combos = [
            ("mini_parwa", "parwa"),
            ("mini_parwa", "parwa_high"),
            ("parwa", "parwa_high"),
        ]

        for live, shadow in combos:
            live_config, shadow_config = variant_service.resolve_for_shadow(
                company_id=company_a,
                live_variant=live,
                shadow_variant=shadow,
            )

            # Shadow should have at least as many steps
            assert len(shadow_config.steps) >= len(live_config.steps)
            # Shadow should have at least as many techniques
            assert len(shadow_config.techniques_allowed) >= len(live_config.techniques_allowed)
            # Shadow should have higher or equal quality threshold
            assert shadow_config.quality_threshold >= live_config.quality_threshold

    def test_resolve_by_instance_for_shadow_config(self, variant_service, company_a):
        """Test resolve_by_instance with shadow mode instance IDs."""
        # Live instance
        live_config = variant_service.resolve_by_instance(
            company_id=company_a,
            instance_id=f"inst_mini_parwa_{company_a}",
        )
        assert live_config.variant_tier == "mini_parwa"

        # Shadow instance
        shadow_config = variant_service.resolve_by_instance(
            company_id=company_a,
            instance_id=f"inst_parwa_{company_a}",
        )
        assert shadow_config.variant_tier == "parwa"


# ══════════════════════════════════════════════════════════════════
# MULTI-TENANT ISOLATION IN SHADOW MODE
# ══════════════════════════════════════════════════════════════════


class TestMultiTenantShadowIsolation:
    """Tests for multi-tenant isolation in shadow mode."""

    def test_independent_shadow_configs(self, shadow_service, company_a, company_b):
        """Test that two companies have independent shadow configs."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        shadow_service.enable_shadow_mode(
            company_id=company_b,
            live_variant="parwa",
            shadow_variant="parwa_high",
        )

        status_a = shadow_service.get_status(company_id=company_a)
        status_b = shadow_service.get_status(company_id=company_b)

        assert status_a.live_variant == "mini_parwa"
        assert status_b.live_variant == "parwa"
        assert status_a.shadow_variant == "parwa"
        assert status_b.shadow_variant == "parwa_high"

    def test_independent_progression(self, shadow_service, company_a, company_b):
        """Test that companies can be in different shadow mode phases."""
        # Company A: auto-graduate to supervised
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_graduation_window=3,
            auto_promote_to_supervised=True,
        )
        # Company B: stays in shadow
        shadow_service.enable_shadow_mode(
            company_id=company_b,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            auto_promote_to_supervised=False,
        )

        # Record wins for both
        for _ in range(3):
            comp_a = ShadowComparison(
                company_id=company_a, config_id="test",
                shadow_winner=True, quality_delta=0.05,
            )
            shadow_service.record_comparison(
                company_id=company_a, comparison=comp_a,
            )

            comp_b = ShadowComparison(
                company_id=company_b, config_id="test",
                shadow_winner=True, quality_delta=0.05,
            )
            shadow_service.record_comparison(
                company_id=company_b, comparison=comp_b,
            )

        status_a = shadow_service.get_status(company_id=company_a)
        status_b = shadow_service.get_status(company_id=company_b)

        assert status_a.status == "supervised"
        assert status_b.status == "shadow"

    def test_disable_one_doesnt_affect_other(self, shadow_service, company_a, company_b):
        """Test that disabling shadow mode for one company doesn't affect another."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        shadow_service.enable_shadow_mode(
            company_id=company_b,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        shadow_service.disable_shadow_mode(company_id=company_a)

        status_a = shadow_service.get_status(company_id=company_a)
        status_b = shadow_service.get_status(company_id=company_b)

        assert status_a.is_active is False
        assert status_b.is_active is True

    def test_comparisons_dont_leak(self, shadow_service, company_a, company_b):
        """Test that comparison data doesn't leak between companies."""
        shadow_service.enable_shadow_mode(
            company_id=company_a,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        shadow_service.enable_shadow_mode(
            company_id=company_b,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        # Record comparison for company A only
        comp = ShadowComparison(
            company_id=company_a, config_id="test",
            shadow_winner=True, quality_delta=0.05,
        )
        shadow_service.record_comparison(company_id=company_a, comparison=comp)

        # Company B should have no comparisons
        stats_b = shadow_service.get_statistics(company_id=company_b)
        assert stats_b["total_comparisons"] == 0


# ══════════════════════════════════════════════════════════════════
# SHADOW MODE + PIPELINE BRIDGE INTEGRATION
# ══════════════════════════════════════════════════════════════════


class TestShadowModePipelineBridgeIntegration:
    """Tests for Shadow Mode integration with the variant pipeline bridge."""

    def test_pipeline_result_has_shadow_metadata(self):
        """Test that PipelineResult can carry shadow mode metadata."""
        result = PipelineResult(
            response_text="Test response",
            variant_tier="parwa",
            industry="general",
            quality_score=0.85,
            metadata={"shadow_mode": "shadow", "shadow_processed": True},
        )
        assert result.metadata["shadow_mode"] == "shadow"
        assert result.metadata["shadow_processed"] is True

    def test_pipeline_result_supervised_metadata(self):
        """Test PipelineResult with supervised mode metadata."""
        result = PipelineResult(
            response_text="Shadow response",
            variant_tier="parwa_high",
            industry="general",
            quality_score=0.90,
            metadata={
                "shadow_mode": "supervised",
                "requires_human_review": True,
                "live_variant": "parwa",
            },
        )
        assert result.metadata["requires_human_review"] is True
        assert result.metadata["live_variant"] == "parwa"

    def test_pipeline_result_comparison_data(self):
        """Test creating a ShadowComparison from PipelineResults."""
        live_result = PipelineResult(
            response_text="Live response",
            variant_tier="mini_parwa",
            industry="general",
            quality_score=0.70,
            total_latency_ms=500,
            billing_tokens=100,
        )
        shadow_result = PipelineResult(
            response_text="Shadow response",
            variant_tier="parwa",
            industry="general",
            quality_score=0.80,
            total_latency_ms=800,
            billing_tokens=150,
        )

        comparison = ShadowComparison(
            company_id="comp_1",
            config_id="config_1",
            live_variant=live_result.variant_tier,
            live_response=live_result.response_text[:500],
            live_quality_score=live_result.quality_score,
            live_latency_ms=int(live_result.total_latency_ms),
            live_tokens_used=live_result.billing_tokens,
            shadow_variant=shadow_result.variant_tier,
            shadow_response=shadow_result.response_text[:500],
            shadow_quality_score=shadow_result.quality_score,
            shadow_latency_ms=int(shadow_result.total_latency_ms),
            shadow_tokens_used=shadow_result.billing_tokens,
            quality_delta=round(
                shadow_result.quality_score - live_result.quality_score, 4
            ),
            latency_delta_ms=int(
                shadow_result.total_latency_ms - live_result.total_latency_ms
            ),
            token_delta=shadow_result.billing_tokens - live_result.billing_tokens,
            shadow_winner=shadow_result.quality_score >= live_result.quality_score,
        )

        assert comparison.shadow_winner is True
        assert comparison.quality_delta == 0.10
        assert comparison.latency_delta_ms == 300
        assert comparison.token_delta == 50


# ══════════════════════════════════════════════════════════════════
# DATABASE MODEL VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestShadowModeDatabaseModels:
    """Tests for shadow mode database model validation."""

    def _get_model_path(self):
        import os
        return os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "models", "shadow_mode.py",
        )

    def test_shadow_mode_model_file_exists(self):
        """Test that the shadow mode model file exists."""
        import os
        model_path = self._get_model_path()
        assert os.path.exists(model_path), f"shadow_mode.py not found at {model_path}"

    def test_shadow_mode_model_defines_classes(self):
        """Test that the model file defines the expected classes."""
        import os
        model_path = self._get_model_path()
        with open(model_path) as f:
            content = f.read()
        assert "class ShadowModeConfig" in content
        assert "class ShadowModeResult" in content
        assert "__tablename__" in content
        assert "shadow_mode_configs" in content
        assert "shadow_mode_results" in content

    def test_config_model_has_required_columns(self):
        """Test that ShadowModeConfig has all required columns in the file."""
        import os
        model_path = self._get_model_path()
        with open(model_path) as f:
            content = f.read()
        required_columns = [
            "id", "company_id", "live_variant", "shadow_variant",
            "status", "sample_rate", "is_active", "created_at",
        ]
        for col in required_columns:
            assert col in content, f"Missing column definition: {col}"

    def test_result_model_has_required_columns(self):
        """Test that ShadowModeResult has all required columns in the file."""
        import os
        model_path = self._get_model_path()
        with open(model_path) as f:
            content = f.read()
        required_columns = [
            "id", "company_id", "config_id", "live_variant",
            "shadow_variant", "shadow_winner", "created_at",
        ]
        for col in required_columns:
            assert col in content, f"Missing column definition: {col}"

    def test_config_model_has_check_constraints(self):
        """Test that ShadowModeConfig has check constraints."""
        import os
        model_path = self._get_model_path()
        with open(model_path) as f:
            content = f.read()
        assert "ck_shadow_config_valid_status" in content
        assert "ck_shadow_config_sample_rate_range" in content

    def test_result_model_has_check_constraints(self):
        """Test that ShadowModeResult has check constraints."""
        import os
        model_path = self._get_model_path()
        with open(model_path) as f:
            content = f.read()
        assert "ck_shadow_result_valid_mode" in content
        assert "ck_shadow_result_valid_verdict" in content


# ══════════════════════════════════════════════════════════════════
# API ROUTER VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestShadowModeAPIRouter:
    """Tests for shadow mode API router validation via file inspection."""

    def test_router_file_exists(self):
        """Test that the shadow mode router file exists."""
        import os
        router_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "api", "shadow_mode.py",
        )
        assert os.path.exists(router_path), "shadow_mode.py router file not found"

    def test_router_has_all_endpoints(self):
        """Test that the router defines all expected endpoints."""
        import os
        router_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "api", "shadow_mode.py",
        )
        with open(router_path) as f:
            content = f.read()
        expected_paths = [
            "/enable", "/disable", "/status", "/promote",
            "/graduate", "/comparisons", "/statistics", "/review",
        ]
        for path in expected_paths:
            assert f'"{path}"' in content or f"'{path}'" in content, \
                f"Missing endpoint: {path}"

    def test_router_has_pydantic_models(self):
        """Test that all request schemas are defined in the router file."""
        import os
        router_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "api", "shadow_mode.py",
        )
        with open(router_path) as f:
            content = f.read()
        expected_models = [
            "EnableShadowModeRequest",
            "DisableShadowModeRequest",
            "PromoteShadowModeRequest",
            "HumanReviewRequest",
        ]
        for model in expected_models:
            assert model in content, f"Missing Pydantic model: {model}"

    def test_router_prefix(self):
        """Test that the router has the correct prefix."""
        import os
        router_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "api", "shadow_mode.py",
        )
        with open(router_path) as f:
            content = f.read()
        assert "/api/shadow-mode" in content


# ══════════════════════════════════════════════════════════════════
# MIGRATION VALIDATION
# ══════════════════════════════════════════════════════════════════


class TestMigrationValidation:
    """Tests for the shadow mode Alembic migration."""

    def _get_migration_path(self):
        import os
        return os.path.join(
            os.path.dirname(__file__),
            "..", "..", "database", "alembic", "versions",
            "024_shadow_mode_tables.py",
        )

    def test_migration_file_exists(self):
        """Test that the migration file exists."""
        import os
        migration_path = self._get_migration_path()
        assert os.path.exists(migration_path), f"Migration file not found at {migration_path}"

    def test_migration_has_upgrade_and_downgrade(self):
        """Test that the migration has both upgrade and downgrade."""
        import os
        migration_path = self._get_migration_path()
        with open(migration_path) as f:
            content = f.read()
        assert "def upgrade()" in content
        assert "def downgrade()" in content
        assert "shadow_mode_configs" in content
        assert "shadow_mode_results" in content
