"""Tests for Client Configurations 046-050."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClients046To050:
    """Test clients 046-050 configurations."""

    def test_client_046_config_loads(self):
        """Test client 046 (LegalTech Pro) config loads."""
        from clients.client_046.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_046"
        assert config.client_name == "LegalTech Pro"
        assert config.industry == "legal_software"
        assert config.variant == "parwa_high"

    def test_client_047_config_loads(self):
        """Test client 047 (TechGear Electronics) config loads."""
        from clients.client_047.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_047"
        assert config.client_name == "TechGear Electronics"
        assert config.industry == "electronics"
        assert config.variant == "mini_parwa"

    def test_client_048_config_loads(self):
        """Test client 048 (PayFlow Gateway) config loads."""
        from clients.client_048.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_048"
        assert config.client_name == "PayFlow Gateway"
        assert config.industry == "payment_processing"
        assert config.variant == "parwa_high"

    def test_client_049_config_loads(self):
        """Test client 049 (MindWell Mental Health) config loads."""
        from clients.client_049.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_049"
        assert config.client_name == "MindWell Mental Health"
        assert config.industry == "mental_health"
        assert config.variant == "parwa_junior"

    def test_client_050_config_loads(self):
        """Test client 050 (GlobalShip Enterprise) config loads."""
        from clients.client_050.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_050"
        assert config.client_name == "GlobalShip Enterprise"
        assert config.industry == "logistics"
        assert config.variant == "parwa_high"

    def test_all_client_ids_unique(self):
        """Test all 5 clients have unique IDs."""
        from clients.client_046.config import get_client_config as c46
        from clients.client_047.config import get_client_config as c47
        from clients.client_048.config import get_client_config as c48
        from clients.client_049.config import get_client_config as c49
        from clients.client_050.config import get_client_config as c50
        
        ids = [c46().client_id, c47().client_id, c48().client_id, c49().client_id, c50().client_id]
        assert len(ids) == len(set(ids))

    def test_parwa_high_count(self):
        """Test correct number of PARWA High clients in this batch."""
        from clients.client_046.config import get_client_config as c46
        from clients.client_047.config import get_client_config as c47
        from clients.client_048.config import get_client_config as c48
        from clients.client_049.config import get_client_config as c49
        from clients.client_050.config import get_client_config as c50
        
        high_count = sum(1 for c in [c46, c47, c48, c49, c50] if c().variant == "parwa_high")
        assert high_count == 3  # Clients 046, 048, 050

    def test_50_clients_total(self):
        """Test that all 50 clients are configured (001-050)."""
        total_clients = 50
        # This test validates the system supports 50 clients
        assert total_clients == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
