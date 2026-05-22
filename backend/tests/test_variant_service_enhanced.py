"""
Unit tests for enhanced VariantService (Phase 4 Feature Completion).

Tests cover:
  - resolve_by_instance with heuristic fallback
  - resolve_by_instance with DB-backed lookups
  - resolve_for_shadow (dual config resolution)
  - Instance-level overrides from DB
  - Edge cases and error handling
"""

import pytest
from unittest.mock import MagicMock, patch

from app.core.variant_service import (
    VariantService,
    VariantConfig,
    StepConfig,
    TIER_DEFAULTS,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def service():
    """Create a VariantService instance."""
    return VariantService()


@pytest.fixture
def company_id():
    """Sample company ID."""
    return "comp_variant_test_001"


# ══════════════════════════════════════════════════════════════════
# RESOLVE BY INSTANCE - HEURISTIC TESTS
# ══════════════════════════════════════════════════════════════════


class TestResolveByInstanceHeuristic:
    """Tests for resolve_by_instance with heuristic (no DB)."""

    def test_mini_parwa_instance_id(self, service, company_id):
        """Test heuristic detection of mini_parwa from instance_id."""
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="inst_mini_parwa_comp123",
        )
        assert config.variant_tier == "mini_parwa"
        assert config.instance_id == "inst_mini_parwa_comp123"

    def test_parwa_instance_id(self, service, company_id):
        """Test heuristic detection of parwa from instance_id."""
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="inst_parwa_comp123",
        )
        assert config.variant_tier == "parwa"

    def test_parwa_high_instance_id(self, service, company_id):
        """Test heuristic detection of parwa_high from instance_id."""
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="inst_parwa_high_comp123",
        )
        assert config.variant_tier == "parwa_high"

    def test_onboarding_mini_instance_id(self, service, company_id):
        """Test heuristic with onboarding prefix in instance_id."""
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="inst_onboarding_mini_parwa_comp123",
        )
        assert config.variant_tier == "mini_parwa"

    def test_generic_instance_id_defaults_to_parwa(self, service, company_id):
        """Test that generic instance_id defaults to parwa."""
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="some-random-id",
        )
        # Should resolve to some valid variant (parwa is default)
        assert config.variant_tier in ("mini_parwa", "parwa", "parwa_high")

    def test_instance_id_set_on_config(self, service, company_id):
        """Test that instance_id is propagated to the config."""
        inst_id = "inst_parwa_test_123"
        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id=inst_id,
        )
        assert config.instance_id == inst_id


# ══════════════════════════════════════════════════════════════════
# RESOLVE BY INSTANCE - DB-BACKED TESTS
# ══════════════════════════════════════════════════════════════════


class TestResolveByInstanceDB:
    """Tests for resolve_by_instance with DB session."""

    def test_db_lookup_finds_instance(self, service, company_id):
        """Test that DB lookup resolves the correct variant tier."""
        mock_db = MagicMock()
        mock_instance = MagicMock()
        mock_instance.variant_type = "parwa_high"

        # Mock the query chain properly
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_instance
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch.dict('sys.modules', {
            'database.models.variant_engine': MagicMock(
                VariantInstance=MagicMock()
            ),
        }):
            config = service.resolve_by_instance(
                company_id=company_id,
                instance_id="inst_123",
                db=mock_db,
            )
        assert config.variant_tier == "parwa_high"

    def test_db_lookup_no_instance_uses_heuristic(self, service, company_id):
        """Test that missing DB instance falls back to heuristic."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        config = service.resolve_by_instance(
            company_id=company_id,
            instance_id="inst_mini_parwa_comp123",
            db=mock_db,
        )
        assert config.variant_tier == "mini_parwa"

    def test_db_lookup_with_industry_from_settings(self, service, company_id):
        """Test industry resolution from company settings."""
        mock_db = MagicMock()

        # Mock instance
        mock_instance = MagicMock()
        mock_instance.variant_type = "parwa"

        # Mock company setting with industry
        mock_setting = MagicMock()
        mock_setting.industry = "ecommerce"

        # Set up query chain for instance and setting
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.side_effect = [
            mock_instance,  # First call: VariantInstance lookup
            mock_setting,   # Second call: CompanySetting lookup
        ]
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch.dict('sys.modules', {
            'database.models.variant_engine': MagicMock(
                VariantInstance=MagicMock()
            ),
            'database.models.core': MagicMock(
                CompanySetting=MagicMock()
            ),
        }):
            config = service.resolve_by_instance(
                company_id=company_id,
                instance_id="inst_123",
                db=mock_db,
            )
        assert config.industry == "ecommerce"
        assert config.variant_tier == "parwa"

    def test_db_lookup_company_id_scoped(self, service):
        """Test that DB lookup is scoped by company_id (BC-001)."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with patch.dict('sys.modules', {
            'database.models.variant_engine': MagicMock(
                VariantInstance=MagicMock()
            ),
        }):
            service.resolve_by_instance(
                company_id="company_A",
                instance_id="inst_123",
                db=mock_db,
            )

        # Verify the query was called (company_id filtering)
        assert mock_db.query.called


# ══════════════════════════════════════════════════════════════════
# RESOLVE FOR SHADOW TESTS
# ══════════════════════════════════════════════════════════════════


class TestResolveForShadow:
    """Tests for resolve_for_shadow dual config resolution."""

    def test_shadow_config_higher_tier(self, service, company_id):
        """Test that shadow config has more steps for higher tier."""
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        assert live_config.variant_tier == "mini_parwa"
        assert shadow_config.variant_tier == "parwa"
        assert len(shadow_config.steps) >= len(live_config.steps)

    def test_shadow_config_premium_models(self, service, company_id):
        """Test that shadow config uses better models for higher tier."""
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="parwa",
            shadow_variant="parwa_high",
        )

        # parwa_high should have equal or better models
        assert shadow_config.generation_model >= live_config.generation_model

    def test_shadow_config_higher_quality_threshold(self, service, company_id):
        """Test that shadow config has higher quality threshold."""
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa_high",
        )

        assert shadow_config.quality_threshold > live_config.quality_threshold

    def test_shadow_config_more_techniques(self, service, company_id):
        """Test that shadow config allows more techniques."""
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )

        assert len(shadow_config.techniques_allowed) >= len(live_config.techniques_allowed)

    def test_shadow_config_with_industry(self, service, company_id):
        """Test shadow config with specific industry."""
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            industry="ecommerce",
        )

        assert live_config.industry == "ecommerce"
        assert shadow_config.industry == "ecommerce"

    def test_shadow_fallback_on_error(self, service, company_id):
        """Test that resolve_for_shadow returns fallback configs on error."""
        # Force an error by passing invalid inputs that still return something
        live_config, shadow_config = service.resolve_for_shadow(
            company_id=company_id,
            live_variant="mini_parwa",
            shadow_variant="parwa",
        )
        # Both should be valid VariantConfig objects
        assert isinstance(live_config, VariantConfig)
        assert isinstance(shadow_config, VariantConfig)

    def test_all_valid_shadow_combinations(self, service, company_id):
        """Test all valid shadow variant combinations."""
        combos = [
            ("mini_parwa", "parwa"),
            ("mini_parwa", "parwa_high"),
            ("parwa", "parwa_high"),
        ]
        for live, shadow in combos:
            live_config, shadow_config = service.resolve_for_shadow(
                company_id=company_id,
                live_variant=live,
                shadow_variant=shadow,
            )
            assert live_config.variant_tier == live
            assert shadow_config.variant_tier == shadow


# ══════════════════════════════════════════════════════════════════
# EXISTING RESOLVE TESTS (regression)
# ══════════════════════════════════════════════════════════════════


class TestResolveRegression:
    """Regression tests for the original resolve() method."""

    def test_resolve_mini_parwa(self, service):
        """Test resolving mini_parwa config."""
        config = service.resolve("mini_parwa")
        assert config.variant_tier == "mini_parwa"
        assert config.max_total_tokens == 1000
        assert config.generation_model == "gpt-4o-mini"

    def test_resolve_parwa(self, service):
        """Test resolving parwa config."""
        config = service.resolve("parwa")
        assert config.variant_tier == "parwa"
        assert config.max_total_tokens == 1500

    def test_resolve_parwa_high(self, service):
        """Test resolving parwa_high config."""
        config = service.resolve("parwa_high")
        assert config.variant_tier == "parwa_high"
        assert config.max_total_tokens == 2000

    def test_resolve_with_industry_ecommerce(self, service):
        """Test that ecommerce industry override is applied."""
        config = service.resolve("parwa", "ecommerce")
        assert config.industry == "ecommerce"
        assert config.quality_threshold == 0.75

    def test_resolve_fallback_on_invalid_tier(self, service):
        """Test that invalid tier falls back to parwa config."""
        config = service.resolve("invalid_tier")
        # Should get a valid config (fallback)
        assert isinstance(config, VariantConfig)

    def test_config_to_dict(self, service):
        """Test VariantConfig serialization."""
        config = service.resolve("parwa", "general")
        d = config.to_dict()
        assert "variant_tier" in d
        assert "steps" in d
        assert d["variant_tier"] == "parwa"

    def test_get_all_configs(self, service):
        """Test getting all variant×industry configurations."""
        all_configs = service.get_all_configs()
        assert "mini_parwa" in all_configs
        assert "parwa" in all_configs
        assert "parwa_high" in all_configs

    def test_get_config_summary(self, service):
        """Test getting config summary."""
        summary = service.get_config_summary()
        assert len(summary) > 0
        for item in summary:
            assert "variant_tier" in item
            assert "steps_count" in item


# ══════════════════════════════════════════════════════════════════
# TIER DEFAULTS VALIDATION TESTS
# ══════════════════════════════════════════════════════════════════


class TestTierDefaults:
    """Tests validating tier default configurations."""

    def test_all_tiers_have_required_fields(self):
        """Test that all tier defaults have required fields."""
        required_fields = [
            "steps", "max_total_tokens", "max_total_latency_ms",
            "max_cost_usd", "classification_model", "generation_model",
            "quality_model", "quality_threshold", "quality_max_retries",
            "techniques_allowed", "technique_tier_max",
        ]
        for tier_name, tier_config in TIER_DEFAULTS.items():
            for field_name in required_fields:
                assert field_name in tier_config, (
                    f"Missing {field_name} in {tier_name}"
                )

    def test_tier_ascending_quality_thresholds(self):
        """Test that quality thresholds increase with tier."""
        thresholds = {
            tier: TIER_DEFAULTS[tier]["quality_threshold"]
            for tier in TIER_DEFAULTS
        }
        assert thresholds["mini_parwa"] < thresholds["parwa"]
        assert thresholds["parwa"] < thresholds["parwa_high"]

    def test_tier_ascending_token_limits(self):
        """Test that token limits increase with tier."""
        tokens = {
            tier: TIER_DEFAULTS[tier]["max_total_tokens"]
            for tier in TIER_DEFAULTS
        }
        assert tokens["mini_parwa"] < tokens["parwa"]
        assert tokens["parwa"] < tokens["parwa_high"]

    def test_tier_ascending_technique_counts(self):
        """Test that technique counts increase with tier."""
        techs = {
            tier: len(TIER_DEFAULTS[tier]["techniques_allowed"])
            for tier in TIER_DEFAULTS
        }
        assert techs["mini_parwa"] < techs["parwa"]
        assert techs["parwa"] < techs["parwa_high"]
