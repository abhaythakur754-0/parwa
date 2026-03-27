"""Tests for Client Configurations 036-040."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClients036To040:
    """Test clients 036-040 configurations."""

    def test_client_036_config_loads(self):
        """Test client 036 (PropTech Realty) config loads."""
        from parwa.clients.client_036.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_036"
        assert config.client_name == "PropTech Realty"
        assert config.industry == "real_estate"
        assert config.variant == "parwa_junior"

    def test_client_037_config_loads(self):
        """Test client 037 (GameZone Entertainment) config loads."""
        from parwa.clients.client_037.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_037"
        assert config.client_name == "GameZone Entertainment"
        assert config.industry == "gaming"
        assert config.variant == "mini_parwa"

    def test_client_038_config_loads(self):
        """Test client 038 (CryptoVault Exchange) config loads."""
        from parwa.clients.client_038.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_038"
        assert config.client_name == "CryptoVault Exchange"
        assert config.industry == "cryptocurrency"
        assert config.variant == "parwa_high"

    def test_client_039_config_loads(self):
        """Test client 039 (DentalCare Plus) config loads."""
        from parwa.clients.client_039.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_039"
        assert config.client_name == "DentalCare Plus"
        assert config.industry == "healthcare"
        assert config.variant == "parwa_junior"

    def test_client_040_config_loads(self):
        """Test client 040 (ShipFast Global) config loads."""
        from parwa.clients.client_040.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_040"
        assert config.client_name == "ShipFast Global"
        assert config.industry == "shipping"
        assert config.variant == "parwa_junior"

    def test_all_client_ids_unique(self):
        """Test all 5 clients have unique IDs."""
        from parwa.clients.client_036.config import get_client_config as c36
        from parwa.clients.client_037.config import get_client_config as c37
        from parwa.clients.client_038.config import get_client_config as c38
        from parwa.clients.client_039.config import get_client_config as c39
        from parwa.clients.client_040.config import get_client_config as c40
        
        ids = [c36().client_id, c37().client_id, c38().client_id, c39().client_id, c40().client_id]
        assert len(ids) == len(set(ids))

    def test_all_variants_valid(self):
        """Test all 5 clients have valid variants."""
        valid_variants = ["mini_parwa", "parwa_junior", "parwa_high"]
        from parwa.clients.client_036.config import get_client_config as c36
        from parwa.clients.client_037.config import get_client_config as c37
        from parwa.clients.client_038.config import get_client_config as c38
        from parwa.clients.client_039.config import get_client_config as c39
        from parwa.clients.client_040.config import get_client_config as c40
        
        for get_config in [c36, c37, c38, c39, c40]:
            config = get_config()
            assert config.variant in valid_variants


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
