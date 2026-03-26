"""All Integrations Tests."""

import pytest


class TestAllIntegrations:
    """Test all integrations work."""

    def test_stripe_integration(self):
        from clients.client_021.config import get_client_config
        assert get_client_config().integrations.stripe is True

    def test_salesforce_integration(self):
        from clients.client_022.config import get_client_config
        assert get_client_config().integrations.salesforce is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
