"""
Unit tests for Industry Configurations module.

Tests for:
- Ecommerce config loads
- SaaS config loads
- Healthcare config + BAA check
- Logistics config loads
"""
import pytest
from datetime import datetime, timedelta

from backend.core.industry_configs import (
    IndustryType,
    get_industry_config,
    get_all_industry_configs,
    validate_industry,
)
from backend.core.industry_configs.ecommerce import EcommerceConfig
from backend.core.industry_configs.saas import SaaSConfig
from backend.core.industry_configs.healthcare import HealthcareConfig
from backend.core.industry_configs.logistics import LogisticsConfig


class TestEcommerceConfig:
    """Tests for E-commerce industry configuration."""

    @pytest.fixture
    def config(self):
        """Create EcommerceConfig fixture."""
        return EcommerceConfig()

    def test_industry_type(self, config):
        """Test industry type is correct."""
        assert config.industry_type == "ecommerce"

    def test_supported_channels(self, config):
        """Test supported channels."""
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "chat" in config.supported_channels
        assert "sms" in config.supported_channels
        assert "voice" in config.supported_channels

    def test_refund_policy_days(self, config):
        """Test refund policy days."""
        assert config.refund_policy_days == 30

    def test_sla_response_hours(self, config):
        """Test SLA response hours."""
        assert config.sla_response_hours == 4

    def test_get_config(self, config):
        """Test get_config returns full configuration."""
        full_config = config.get_config()

        assert full_config["industry_type"] == "ecommerce"
        assert full_config["refund_policy_days"] == 30
        assert "features" in full_config
        assert "integrations" in full_config

    def test_get_features(self, config):
        """Test get_features returns feature list."""
        features = config.get_features()

        assert "order_tracking" in features
        assert "refund_processing" in features
        assert "shipping_updates" in features

    def test_get_integrations(self, config):
        """Test get_integrations returns integration list."""
        integrations = config.get_integrations()

        assert "shopify" in integrations
        assert "stripe" in integrations
        assert "ups" in integrations

    def test_validate_channel(self, config):
        """Test channel validation."""
        assert config.validate_channel("faq") is True
        assert config.validate_channel("email") is True
        assert config.validate_channel("voice") is True
        assert config.validate_channel("invalid_channel") is False

    def test_get_channel_config(self, config):
        """Test channel-specific configuration."""
        chat_config = config.get_channel_config("chat")

        assert chat_config["enabled"] is True
        assert "response_time_seconds" in chat_config


class TestSaaSConfig:
    """Tests for SaaS industry configuration."""

    @pytest.fixture
    def config(self):
        """Create SaaSConfig fixture."""
        return SaaSConfig()

    def test_industry_type(self, config):
        """Test industry type is correct."""
        assert config.industry_type == "saas"

    def test_supported_channels(self, config):
        """Test supported channels."""
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "chat" in config.supported_channels
        # SaaS doesn't include SMS or voice by default
        assert "sms" not in config.supported_channels

    def test_refund_policy_days(self, config):
        """Test refund policy days (shorter for SaaS)."""
        assert config.refund_policy_days == 14

    def test_sla_response_hours(self, config):
        """Test SLA response hours (faster for SaaS)."""
        assert config.sla_response_hours == 2

    def test_get_config(self, config):
        """Test get_config returns full configuration."""
        full_config = config.get_config()

        assert full_config["industry_type"] == "saas"
        assert full_config["refund_policy_days"] == 14
        assert "features" in full_config
        assert "integrations" in full_config

    def test_get_features(self, config):
        """Test get_features returns feature list."""
        features = config.get_features()

        assert "technical_support" in features
        assert "api_documentation" in features
        assert "subscription_management" in features

    def test_get_integrations(self, config):
        """Test get_integrations returns integration list."""
        integrations = config.get_integrations()

        assert "stripe" in integrations
        assert "paddle" in integrations
        assert "github" in integrations

    def test_get_tier_limits(self, config):
        """Test tier limits configuration."""
        tiers = config.get_tier_limits()

        assert "free_tier" in tiers
        assert "enterprise" in tiers
        assert tiers["enterprise"]["support_level"] == "dedicated"


class TestHealthcareConfig:
    """Tests for Healthcare industry configuration with BAA requirements."""

    @pytest.fixture
    def config(self):
        """Create HealthcareConfig fixture."""
        return HealthcareConfig()

    def test_industry_type(self, config):
        """Test industry type is correct."""
        assert config.industry_type == "healthcare"

    def test_requires_baa(self, config):
        """CRITICAL: Healthcare must require BAA."""
        assert config.requires_baa is True

    def test_phi_handling(self, config):
        """Test PHI handling mode."""
        assert config.phi_handling == "restricted"

    def test_supported_channels(self, config):
        """Test supported channels."""
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "voice" in config.supported_channels
        # Healthcare doesn't include chat by default
        assert "chat" not in config.supported_channels

    def test_sla_response_hours(self, config):
        """Test SLA response hours (faster for healthcare)."""
        assert config.sla_response_hours == 1

    def test_get_config(self, config):
        """Test get_config returns full configuration."""
        full_config = config.get_config()

        assert full_config["industry_type"] == "healthcare"
        assert full_config["requires_baa"] is True
        assert "compliance_requirements" in full_config

    def test_get_compliance_requirements(self, config):
        """Test HIPAA compliance requirements."""
        compliance = config.get_compliance_requirements()

        assert compliance["baa_required"] is True
        assert compliance["phi_encryption"] == "AES-256"
        assert compliance["audit_log_retention_years"] == 6
        assert compliance["breach_notification_hours"] == 72

    def test_check_baa_no_baa(self, config):
        """Test BAA check fails when no BAA registered."""
        result = config.check_baa("nonexistent_company")

        assert result is False

    def test_register_baa(self, config):
        """Test BAA registration."""
        company_id = "healthcare_company_1"
        baa_id = "BAA-12345"
        effective_date = datetime.utcnow()
        expiry_date = datetime.utcnow() + timedelta(days=365)

        result = config.register_baa(
            company_id=company_id,
            baa_id=baa_id,
            effective_date=effective_date,
            expiry_date=expiry_date
        )

        assert result["baa_id"] == baa_id
        assert result["company_id"] == company_id
        assert result["status"] == "active"

    def test_check_baa_with_valid_baa(self, config):
        """Test BAA check passes with valid BAA."""
        company_id = "valid_baa_company"

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-VALID",
            effective_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=365)
        )

        # Check should pass
        result = config.check_baa(company_id)
        assert result is True

    def test_check_baa_with_expired_baa(self, config):
        """Test BAA check fails with expired BAA."""
        company_id = "expired_baa_company"

        # Register expired BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-EXPIRED",
            effective_date=datetime.utcnow() - timedelta(days=730),
            expiry_date=datetime.utcnow() - timedelta(days=1)
        )

        # Check should fail
        result = config.check_baa(company_id)
        assert result is False

    def test_revoke_baa(self, config):
        """Test BAA revocation."""
        company_id = "revoke_baa_company"

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-REVOKE",
            effective_date=datetime.utcnow()
        )

        # Revoke it
        result = config.revoke_baa(company_id, reason="Compliance violation")

        assert result["status"] == "revoked"

        # Check should fail now
        assert config.check_baa(company_id) is False

    def test_get_baa_status(self, config):
        """Test getting BAA status."""
        company_id = "status_check_company"

        # No BAA registered
        status = config.get_baa_status(company_id)
        assert status["baa_exists"] is False

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-STATUS",
            effective_date=datetime.utcnow()
        )

        # Check status
        status = config.get_baa_status(company_id)
        assert status["baa_exists"] is True
        assert status["is_valid"] is True


class TestLogisticsConfig:
    """Tests for Logistics industry configuration."""

    @pytest.fixture
    def config(self):
        """Create LogisticsConfig fixture."""
        return LogisticsConfig()

    def test_industry_type(self, config):
        """Test industry type is correct."""
        assert config.industry_type == "logistics"

    def test_supported_channels(self, config):
        """Test supported channels."""
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "chat" in config.supported_channels
        assert "sms" in config.supported_channels
        assert "voice" in config.supported_channels

    def test_tracking_integration(self, config):
        """Test tracking integration enabled."""
        assert config.tracking_integration is True

    def test_sla_response_hours(self, config):
        """Test SLA response hours."""
        assert config.sla_response_hours == 6

    def test_get_config(self, config):
        """Test get_config returns full configuration."""
        full_config = config.get_config()

        assert full_config["industry_type"] == "logistics"
        assert full_config["tracking_integration"] is True
        assert "features" in full_config
        assert "integrations" in full_config

    def test_get_features(self, config):
        """Test get_features returns feature list."""
        features = config.get_features()

        assert "shipment_tracking" in features
        assert "delivery_status" in features
        assert "proof_of_delivery" in features

    def test_get_integrations(self, config):
        """Test get_integrations returns integration list."""
        integrations = config.get_integrations()

        assert "ups" in integrations
        assert "fedex" in integrations
        assert "usps" in integrations

    def test_get_tracking_providers(self, config):
        """Test tracking providers list."""
        providers = config.get_tracking_providers()

        assert "ups" in providers
        assert "fedex" in providers
        assert "dhl" in providers

    def test_get_shipment_status_codes(self, config):
        """Test shipment status codes."""
        codes = config.get_shipment_status_codes()

        assert codes["DE"] == "Delivered"
        assert codes["IT"] == "In Transit"
        assert codes["EX"] == "Exception"

    def test_get_exception_types(self, config):
        """Test exception types list."""
        exceptions = config.get_exception_types()

        assert "delivery_attempt_failed" in exceptions
        assert "lost_package" in exceptions


class TestIndustryConfigModule:
    """Tests for the industry_configs module functions."""

    def test_get_industry_config_ecommerce(self):
        """Test getting ecommerce config."""
        config = get_industry_config("ecommerce")
        assert isinstance(config, EcommerceConfig)
        assert config.industry_type == "ecommerce"

    def test_get_industry_config_saas(self):
        """Test getting SaaS config."""
        config = get_industry_config("saas")
        assert isinstance(config, SaaSConfig)
        assert config.industry_type == "saas"

    def test_get_industry_config_healthcare(self):
        """Test getting healthcare config."""
        config = get_industry_config("healthcare")
        assert isinstance(config, HealthcareConfig)
        assert config.industry_type == "healthcare"
        assert config.requires_baa is True

    def test_get_industry_config_logistics(self):
        """Test getting logistics config."""
        config = get_industry_config("logistics")
        assert isinstance(config, LogisticsConfig)
        assert config.industry_type == "logistics"

    def test_get_industry_config_case_insensitive(self):
        """Test industry type is case insensitive."""
        config = get_industry_config("ECOMMERCE")
        assert config.industry_type == "ecommerce"

    def test_get_industry_config_invalid(self):
        """Test invalid industry type raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_industry_config("invalid_industry")

        assert "Unknown industry type" in str(exc_info.value)

    def test_get_all_industry_configs(self):
        """Test getting all industry configs."""
        all_configs = get_all_industry_configs()

        assert "ecommerce" in all_configs
        assert "saas" in all_configs
        assert "healthcare" in all_configs
        assert "logistics" in all_configs

        # Each should be a dict
        assert isinstance(all_configs["ecommerce"], dict)

    def test_validate_industry_valid(self):
        """Test validating valid industry types."""
        assert validate_industry("ecommerce") is True
        assert validate_industry("saas") is True
        assert validate_industry("healthcare") is True
        assert validate_industry("logistics") is True

    def test_validate_industry_invalid(self):
        """Test validating invalid industry types."""
        assert validate_industry("invalid") is False
        assert validate_industry("retail") is False

    def test_industry_type_enum(self):
        """Test IndustryType enum values."""
        assert IndustryType.ECOMMERCE == "ecommerce"
        assert IndustryType.SAAS == "saas"
        assert IndustryType.HEALTHCARE == "healthcare"
        assert IndustryType.LOGISTICS == "logistics"
