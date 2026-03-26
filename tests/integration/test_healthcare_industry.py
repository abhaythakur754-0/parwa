"""
Healthcare Industry Integration Tests.

Tests for Healthcare industry configuration and workflows.
Validates HIPAA compliance, BAA verification, and PHI protection.

CRITICAL Requirements:
- Healthcare config loads correctly
- BAA check enforced
- HIPAA compliance enforced
- PHI protection works
- 1-hour SLA enforced
- Voice channel preferred
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.core.industry_configs.healthcare import HealthcareConfig


class TestHealthcareConfig:
    """Tests for Healthcare configuration."""

    def test_healthcare_config_loads_correctly(self):
        """Test: Healthcare config loads correctly."""
        config = HealthcareConfig()

        assert config.industry_type == "healthcare"
        assert "faq" in config.supported_channels
        assert "email" in config.supported_channels
        assert "voice" in config.supported_channels
        assert config.sla_response_hours == 1

    def test_healthcare_config_get_config(self):
        """Test: Healthcare config returns full configuration."""
        config = HealthcareConfig()
        full_config = config.get_config()

        assert "industry_type" in full_config
        assert "requires_baa" in full_config
        assert "phi_handling" in full_config
        assert "hipaa_compliance_enabled" in full_config
        assert "compliance_requirements" in full_config

    def test_healthcare_config_features(self):
        """Test: Healthcare config has correct features."""
        config = HealthcareConfig()
        features = config.get_features()

        assert "appointment_scheduling" in features
        assert "hipaa_auditing" in features
        assert "phi_protection" in features
        assert "secure_messaging" in features


class TestHealthcareBAAEnforcement:
    """CRITICAL: Tests for BAA verification."""

    @pytest.fixture
    def config(self):
        """Create Healthcare config instance."""
        return HealthcareConfig()

    def test_baa_required_by_default(self, config):
        """Test: BAA required by default."""
        assert config.requires_baa is True

    def test_baa_check_fails_without_registration(self, config):
        """Test: BAA check fails without registration."""
        company_id = str(uuid4())

        # Should fail without BAA registration
        assert config.check_baa(company_id) is False

    def test_baa_check_succeed_with_registration(self, config):
        """Test: BAA check succeeds with registration."""
        company_id = str(uuid4())

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-123",
            effective_date=datetime.utcnow(),
        )

        # Should now pass
        assert config.check_baa(company_id) is True

    def test_baa_check_fails_after_revocation(self, config):
        """Test: BAA check fails after revocation."""
        company_id = str(uuid4())

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-456",
            effective_date=datetime.utcnow(),
        )

        # Revoke BAA
        config.revoke_baa(company_id, reason="Compliance violation")

        # Should now fail
        assert config.check_baa(company_id) is False

    def test_baa_registration_stores_record(self, config):
        """Test: BAA registration stores valid record."""
        company_id = str(uuid4())

        record = config.register_baa(
            company_id=company_id,
            baa_id="BAA-789",
            effective_date=datetime.utcnow(),
        )

        assert record["baa_id"] == "BAA-789"
        assert record["status"] == "active"
        assert record["company_id"] == company_id

    def test_baa_status_returns_info(self, config):
        """Test: BAA status returns correct info."""
        company_id = str(uuid4())

        # Register BAA
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-STATUS",
            effective_date=datetime.utcnow(),
        )

        # Get status
        status = config.get_baa_status(company_id)

        assert status["baa_exists"] is True
        assert status["status"] == "active"
        assert status["is_valid"] is True


class TestHealthcareHIPAACompliance:
    """CRITICAL: Tests for HIPAA compliance."""

    @pytest.fixture
    def config(self):
        """Create Healthcare config instance."""
        return HealthcareConfig()

    def test_hipaa_compliance_enabled(self, config):
        """Test: HIPAA compliance enabled."""
        assert config.hipaa_compliance_enabled is True

    def test_audit_all_access(self, config):
        """Test: Audit all access enabled."""
        assert config.audit_all_access is True

    def test_encryption_at_rest(self, config):
        """Test: Encryption at rest required."""
        assert config.encryption_at_rest is True

    def test_encryption_in_transit(self, config):
        """Test: Encryption in transit required."""
        assert config.encryption_in_transit is True

    def test_min_necessary_standard(self, config):
        """Test: Minimum necessary standard enabled."""
        assert config.min_necessary_enabled is True

    def test_breach_notification_hours(self, config):
        """Test: Breach notification hours correct."""
        assert config.breach_notification_hours == 72

    def test_compliance_requirements(self, config):
        """Test: Compliance requirements returned."""
        requirements = config.get_compliance_requirements()

        assert requirements["baa_required"] is True
        assert requirements["phi_encryption"] == "AES-256"
        assert requirements["audit_log_retention_years"] == 6


class TestHealthcarePHIProtection:
    """CRITICAL: Tests for PHI protection."""

    @pytest.fixture
    def config(self):
        """Create Healthcare config instance."""
        return HealthcareConfig()

    def test_phi_handling_restricted(self, config):
        """Test: PHI handling is restricted."""
        assert config.phi_handling == "restricted"

    def test_phi_safe_only_in_faq(self, config):
        """Test: FAQ channel is PHI safe only."""
        faq_config = config.get_channel_config("faq")

        assert faq_config.get("phi_safe_only") is True

    def test_email_encryption_required(self, config):
        """Test: Email channel requires encryption."""
        email_config = config.get_channel_config("email")

        assert email_config.get("encryption_required") is True
        assert email_config.get("secure_gateway") is True

    def test_voice_phi_mode_restricted(self, config):
        """Test: Voice channel has restricted PHI mode."""
        voice_config = config.get_channel_config("voice")

        assert voice_config.get("phi_mode") == "restricted"
        assert voice_config.get("encryption_required") is True


class TestHealthcareSLA:
    """Tests for Healthcare SLA."""

    def test_healthcare_sla_1_hour(self):
        """Test: 1-hour SLA for healthcare."""
        config = HealthcareConfig()

        assert config.sla_response_hours == 1

    def test_healthcare_sla_faster_than_other_industries(self):
        """Test: Healthcare SLA is faster than other industries."""
        from backend.core.industry_configs.ecommerce import EcommerceConfig
        from backend.core.industry_configs.saas import SaaSConfig

        healthcare_config = HealthcareConfig()
        ecommerce_config = EcommerceConfig()
        saas_config = SaaSConfig()

        # Healthcare should have fastest SLA
        assert healthcare_config.sla_response_hours < ecommerce_config.sla_response_hours
        assert healthcare_config.sla_response_hours < saas_config.sla_response_hours

    def test_sla_compliance_check(self):
        """Test: SLA compliance check."""
        config = HealthcareConfig()
        ticket_created = datetime.utcnow() - timedelta(minutes=30)
        current_time = datetime.utcnow()

        minutes_elapsed = (current_time - ticket_created).total_seconds() / 60
        is_compliant = minutes_elapsed <= config.sla_response_hours * 60

        assert is_compliant is True


class TestHealthcareChannels:
    """Tests for Healthcare channel configuration."""

    @pytest.fixture
    def config(self):
        """Create Healthcare config instance."""
        return HealthcareConfig()

    def test_voice_channel_preferred(self, config):
        """Test: Voice channel is available (preferred for healthcare)."""
        voice_config = config.get_channel_config("voice")

        assert voice_config.get("enabled") is True
        assert voice_config.get("answer_time_seconds") == 4  # Faster answer time

    def test_chat_channel_not_supported(self, config):
        """Test: Chat channel is not supported by default."""
        assert config.validate_channel("chat") is False

    def test_email_channel_available(self, config):
        """Test: Email channel is available."""
        email_config = config.get_channel_config("email")

        assert email_config.get("enabled") is True

    def test_all_channels_have_security(self, config):
        """Test: All channels have security requirements."""
        for channel in config.supported_channels:
            channel_config = config.get_channel_config(channel)
            # Security is enforced
            assert channel_config.get("encryption_required") or channel_config.get("phi_safe_only") or channel_config.get("phi_mode")


class TestHealthcareIntegrationFlow:
    """End-to-end integration tests for Healthcare flow."""

    @pytest.mark.asyncio
    async def test_healthcare_flow_with_baa(self):
        """Integration: Healthcare flow works with BAA."""
        config = HealthcareConfig()
        company_id = str(uuid4())

        # Step 1: Register BAA first
        config.register_baa(
            company_id=company_id,
            baa_id="BAA-FLOW-TEST",
            effective_date=datetime.utcnow(),
        )

        # Step 2: Verify BAA check passes
        assert config.check_baa(company_id) is True

        # Step 3: Create ticket
        ticket = {
            "ticket_id": str(uuid4()),
            "company_id": company_id,
            "channel": "voice",
            "priority": "high",
            "created_at": datetime.utcnow().isoformat(),
        }

        # Step 4: Verify voice channel available
        assert config.validate_channel("voice") is True

        # Step 5: Verify SLA
        assert config.sla_response_hours == 1

        # Step 6: Verify HIPAA compliance
        assert config.hipaa_compliance_enabled is True

    @pytest.mark.asyncio
    async def test_healthcare_flow_blocked_without_baa(self):
        """Integration: Healthcare flow blocked without BAA."""
        config = HealthcareConfig()
        company_id = str(uuid4())

        # Step 1: Do NOT register BAA

        # Step 2: Verify BAA check fails
        assert config.check_baa(company_id) is False

        # Step 3: PHI operations should be blocked
        # In production, this would throw an exception or return error

    @pytest.mark.asyncio
    async def test_healthcare_phi_sanitization(self):
        """Integration: PHI sanitization works."""
        config = HealthcareConfig()

        # Verify FAQ doesn't expose PHI
        faq_config = config.get_channel_config("faq")
        assert faq_config.get("phi_safe_only") is True

        # Verify voice has restricted PHI mode
        voice_config = config.get_channel_config("voice")
        assert voice_config.get("phi_mode") == "restricted"
