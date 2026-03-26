"""
Unit tests for PARWA Mini Configuration and Anti-Arbitrage Config.

Tests MiniConfig and AntiArbitrageConfig classes.
"""
import pytest

from variants.mini.config import (
    MiniConfig,
    get_mini_config,
    DEFAULT_MINI_CONFIG,
)
from variants.mini.anti_arbitrage_config import (
    AntiArbitrageConfig,
    get_anti_arbitrage_config,
    calculate_mini_roi,
    DEFAULT_ANTI_ARBITRAGE_CONFIG,
)


class TestMiniConfig:
    """Tests for MiniConfig class."""

    def test_mini_config_defaults(self):
        """Test default configuration values."""
        config = MiniConfig()

        assert config.max_concurrent_calls == 2
        assert config.escalation_threshold == 0.70
        assert config.refund_limit == 50.0
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels

    def test_get_variant_name(self):
        """Test variant name."""
        config = MiniConfig()
        assert config.get_variant_name() == "Mini PARWA"

    def test_get_variant_id(self):
        """Test variant ID."""
        config = MiniConfig()
        assert config.get_variant_id() == "mini"

    def test_is_channel_supported_true(self):
        """Test channel support check returns True."""
        config = MiniConfig()

        assert config.is_channel_supported("faq") is True
        assert config.is_channel_supported("email") is True
        assert config.is_channel_supported("chat") is True
        assert config.is_channel_supported("sms") is True

    def test_is_channel_supported_false(self):
        """Test channel support check returns False for unsupported."""
        config = MiniConfig()

        assert config.is_channel_supported("voice") is False
        assert config.is_channel_supported("ticket") is False

    def test_can_handle_refund_amount_true(self):
        """Test refund within limit."""
        config = MiniConfig()

        assert config.can_handle_refund_amount(25.0) is True
        assert config.can_handle_refund_amount(50.0) is True

    def test_can_handle_refund_amount_false(self):
        """Test refund over limit."""
        config = MiniConfig()

        assert config.can_handle_refund_amount(51.0) is False
        assert config.can_handle_refund_amount(100.0) is False

    def test_should_escalate_refund(self):
        """Test refund escalation check."""
        config = MiniConfig()

        assert config.should_escalate_refund(30.0) is False
        assert config.should_escalate_refund(100.0) is True

    def test_get_mini_config(self):
        """Test getting default config."""
        config = get_mini_config()

        assert config is DEFAULT_MINI_CONFIG
        assert config.max_concurrent_calls == 2


class TestAntiArbitrageConfig:
    """Tests for AntiArbitrageConfig class."""

    def test_default_config(self):
        """Test default anti-arbitrage configuration."""
        config = AntiArbitrageConfig()

        assert config.mini_hourly_rate == 15.0
        assert config.manager_hourly_rate == 75.0
        assert config.starter_monthly == 99.0
        assert config.growth_monthly == 299.0
        assert config.scale_monthly == 599.0

    def test_get_savings_ratio(self):
        """Test savings ratio calculation."""
        config = AntiArbitrageConfig()
        ratio = config.get_savings_ratio()

        # Manager is 5x Mini cost
        assert ratio == 5.0

    def test_calculate_manager_time(self):
        """Test manager time calculation."""
        config = AntiArbitrageConfig()
        time_saved = config.calculate_manager_time(complexity=1.0)

        assert time_saved == 5.0  # Default 5 minutes

    def test_calculate_manager_time_with_complexity(self):
        """Test manager time with complexity multiplier."""
        config = AntiArbitrageConfig()
        time_saved = config.calculate_manager_time(complexity=2.0)

        assert time_saved == 10.0  # 5 * 2.0

    def test_calculate_roi_positive(self):
        """Test ROI calculation with positive savings."""
        config = AntiArbitrageConfig()
        result = config.calculate_roi(
            queries_handled=1000,
            manager_time_saved=500,  # 500 minutes
            subscription_cost=99.0
        )

        # 500 minutes = 8.33 hours
        # Manager cost = 8.33 * 75 = $625
        # Mini cost = $99
        # Net savings = $526
        assert result["is_positive_roi"] is True
        assert result["net_savings"] > 0

    def test_calculate_roi_negative(self):
        """Test ROI calculation with negative savings."""
        config = AntiArbitrageConfig()
        result = config.calculate_roi(
            queries_handled=10,
            manager_time_saved=10,  # Only 10 minutes
            subscription_cost=999.0  # High cost
        )

        assert result["is_positive_roi"] is False

    def test_validate_pricing_starter(self):
        """Test pricing validation for starter tier."""
        config = AntiArbitrageConfig()
        result = config.validate_pricing("starter")

        assert result["valid"] is True
        assert result["price"] == 99.0

    def test_validate_pricing_growth(self):
        """Test pricing validation for growth tier."""
        config = AntiArbitrageConfig()
        result = config.validate_pricing("growth")

        assert result["valid"] is True
        assert result["price"] == 299.0

    def test_validate_pricing_scale(self):
        """Test pricing validation for scale tier."""
        config = AntiArbitrageConfig()
        result = config.validate_pricing("scale")

        assert result["valid"] is True
        assert result["price"] == 599.0

    def test_validate_pricing_unknown_tier(self):
        """Test validation for unknown tier."""
        config = AntiArbitrageConfig()
        result = config.validate_pricing("unknown")

        assert result["valid"] is False

    def test_get_tier_pricing(self):
        """Test getting all tier pricing."""
        config = AntiArbitrageConfig()
        pricing = config.get_tier_pricing()

        assert "starter" in pricing
        assert "growth" in pricing
        assert "scale" in pricing
        assert pricing["starter"]["monthly"] == 99.0

    def test_validation_manager_rate_must_exceed_mini(self):
        """Test validation requires manager rate > mini rate."""
        with pytest.raises(ValueError):
            AntiArbitrageConfig(
                mini_hourly_rate=100.0,
                manager_hourly_rate=50.0
            )

    def test_get_anti_arbitrage_config(self):
        """Test getting default config."""
        config = get_anti_arbitrage_config()

        assert config is DEFAULT_ANTI_ARBITRAGE_CONFIG


class TestCalculateMiniROI:
    """Tests for calculate_mini_roi convenience function."""

    def test_calculate_roi_with_defaults(self):
        """Test ROI calculation with defaults."""
        result = calculate_mini_roi(queries_handled=500)

        assert "queries_handled" in result
        assert "net_savings" in result
        assert "roi_percent" in result

    def test_calculate_roi_with_tier(self):
        """Test ROI calculation with specific tier."""
        result = calculate_mini_roi(
            queries_handled=1000,
            subscription_tier="growth"
        )

        assert result["mini_cost"] == 299.0  # Growth tier price


class TestMiniConfigIntegration:
    """Integration tests for Mini configuration."""

    def test_config_matches_refund_agent_limit(self):
        """Test MiniConfig refund limit matches RefundAgent."""
        config = MiniConfig()

        # MiniConfig refund limit should be $50
        assert config.refund_limit == 50.0

    def test_config_matches_escalation_threshold(self):
        """Test MiniConfig escalation threshold is correct."""
        config = MiniConfig()

        # Escalation threshold should be 70%
        assert config.escalation_threshold == 0.70

    def test_roi_shows_value(self):
        """Test ROI calculation shows value for reasonable usage."""
        config = AntiArbitrageConfig()

        # 500 queries at 5 minutes each = 2500 minutes = 41.67 hours
        # Manager cost = 41.67 * 75 = $3125
        # Mini starter cost = $99
        result = config.calculate_roi(
            queries_handled=500,
            manager_time_saved=2500,
            subscription_cost=99.0
        )

        # Should show significant savings
        assert result["is_positive_roi"] is True
        assert result["net_savings"] > 2000

    def test_2x_mini_cost_shows_manager_time(self):
        """Test that 2x Mini cost shows manager time saved correctly."""
        config = AntiArbitrageConfig()

        # If Mini costs 2x as much (say $198/month for double usage)
        # Manager time at $75/hr = $198 / $75 = 2.64 hours = 158 minutes
        hours_needed = config.starter_monthly * 2 / config.manager_hourly_rate

        # This shows the break-even manager time
        assert hours_needed > 2.0
        assert hours_needed < 3.0
