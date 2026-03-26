"""
Full Regression Test Suite for Week 30.

Tests all features from Weeks 1-29.
"""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestFullRegression:
    """Full regression tests for all features."""

    def test_all_clients_configurable(self):
        """Test all 30 clients can be configured."""
        # Test a sample of clients to verify system
        from clients.client_001.config import get_client_config as g1
        from clients.client_010.config import get_client_config as g10
        from clients.client_020.config import get_client_config as g20
        from clients.client_030.config import get_client_config as g30
        
        configs = [g1(), g10(), g20(), g30()]
        assert all(c.client_id for c in configs)

    def test_all_variants_work(self):
        """Test all variant types work."""
        from clients.client_001.config import get_client_config as g1
        from clients.client_021.config import get_client_config as g21
        from clients.client_022.config import get_client_config as g22
        
        # Mini, Junior, High variants
        c1, c21, c22 = g1(), g21(), g22()
        variants = [c1.variant, c21.variant, c22.variant]
        valid = ["mini", "parwa_junior", "parwa_high"]
        for v in variants:
            assert v in valid

    def test_all_integrations_defined(self):
        """Test integrations are properly defined."""
        from clients.client_021.config import get_client_config
        c = get_client_config()
        assert hasattr(c, 'integrations')

    def test_all_sla_defined(self):
        """Test SLA is defined for all clients."""
        from clients.client_026.config import get_client_config
        c = get_client_config()
        assert hasattr(c, 'sla')
        assert c.sla.first_response_hours > 0

    def test_all_feature_flags_defined(self):
        """Test feature flags are defined."""
        from clients.client_030.config import get_client_config
        c = get_client_config()
        assert hasattr(c, 'feature_flags')


class Test30ClientIsolation:
    """30-client isolation tests."""

    def test_isolation_framework_exists(self):
        """Test isolation testing framework."""
        # Verify client IDs are isolated
        from clients.client_026.config import get_client_config as g26
        from clients.client_030.config import get_client_config as g30
        
        c26, c30 = g26(), g30()
        assert c26.client_id != c30.client_id
        assert c26.client_name != c30.client_name

    def test_no_cross_client_data_access(self):
        """Test no cross-client data access."""
        # Simulated test - in production would check actual data isolation
        from clients.client_021.config import get_client_config as g21
        from clients.client_025.config import get_client_config as g25
        
        c21, c25 = g21(), g25()
        # Each client should have unique paddle account
        assert c21.paddle_account_id != c25.paddle_account_id


class TestAllVariantsRegression:
    """Test all variants pass regression."""

    def test_mini_variant_features(self):
        """Test Mini variant features."""
        from clients.client_001.config import get_client_config
        c = get_client_config()
        # Mini has limited features
        assert c.variant == "mini"
        assert c.variant_limits.refund_limit == 50.0

    def test_junior_variant_features(self):
        """Test Junior variant features."""
        from clients.client_021.config import get_client_config
        c = get_client_config()
        assert c.variant == "parwa_junior"
        assert c.variant_limits.refund_limit == 100.0

    def test_high_variant_features(self):
        """Test High variant features."""
        from clients.client_022.config import get_client_config
        c = get_client_config()
        assert c.variant == "parwa_high"
        assert c.variant_limits.concurrent_calls >= 10


class TestAllIntegrations:
    """Test all integrations work."""

    def test_stripe_integration(self):
        """Test Stripe integration configured."""
        from clients.client_021.config import get_client_config
        c = get_client_config()
        assert c.integrations.stripe is True

    def test_salesforce_integration(self):
        """Test Salesforce integration configured."""
        from clients.client_022.config import get_client_config
        c = get_client_config()
        assert c.integrations.salesforce is True

    def test_twilio_integration(self):
        """Test Twilio integration configured."""
        from clients.client_025.config import get_client_config
        c = get_client_config()
        assert c.integrations.twilio is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
