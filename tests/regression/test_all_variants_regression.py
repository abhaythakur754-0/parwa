"""All Variants Regression Tests."""

import pytest


class TestAllVariantsRegression:
    """Test all variants pass."""

    def test_mini_variant_exists(self):
        """Test Mini variant works."""
        from clients.client_006.config import get_client_config
        c = get_client_config()
        assert c.variant == "mini"

    def test_junior_variant_exists(self):
        """Test Junior variant works."""
        from clients.client_021.config import get_client_config
        c = get_client_config()
        assert c.variant == "parwa_junior"

    def test_high_variant_exists(self):
        """Test High variant works."""
        from clients.client_022.config import get_client_config
        c = get_client_config()
        assert c.variant == "parwa_high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
