"""Tests for Client Configurations 041-045."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClients041To045:
    """Test clients 041-045 configurations."""

    def test_client_041_config_loads(self):
        """Test client 041 (PeopleFirst HR) config loads."""
        from parwa.clients.client_041.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_041"
        assert config.client_name == "PeopleFirst HR"
        assert config.industry == "hr_software"
        assert config.variant == "parwa_junior"

    def test_client_042_config_loads(self):
        """Test client 042 (StyleHub Fashion) config loads."""
        from parwa.clients.client_042.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_042"
        assert config.client_name == "StyleHub Fashion"
        assert config.industry == "ecommerce"
        assert config.variant == "mini_parwa"

    def test_client_043_config_loads(self):
        """Test client 043 (WealthWise Capital) config loads."""
        from parwa.clients.client_043.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_043"
        assert config.client_name == "WealthWise Capital"
        assert config.industry == "wealth_management"
        assert config.variant == "parwa_high"

    def test_client_044_config_loads(self):
        """Test client 044 (PetCare Veterinary) config loads."""
        from parwa.clients.client_044.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_044"
        assert config.client_name == "PetCare Veterinary"
        assert config.industry == "veterinary"
        assert config.variant == "parwa_junior"

    def test_client_045_config_loads(self):
        """Test client 045 (ExpressCourier X) config loads."""
        from parwa.clients.client_045.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_045"
        assert config.client_name == "ExpressCourier X"
        assert config.industry == "courier"
        assert config.variant == "parwa_junior"

    def test_all_client_ids_unique(self):
        """Test all 5 clients have unique IDs."""
        from parwa.clients.client_041.config import get_client_config as c41
        from parwa.clients.client_042.config import get_client_config as c42
        from parwa.clients.client_043.config import get_client_config as c43
        from parwa.clients.client_044.config import get_client_config as c44
        from parwa.clients.client_045.config import get_client_config as c45
        
        ids = [c41().client_id, c42().client_id, c43().client_id, c44().client_id, c45().client_id]
        assert len(ids) == len(set(ids))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
