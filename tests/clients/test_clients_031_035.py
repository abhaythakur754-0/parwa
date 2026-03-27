"""Tests for Client Configurations 031-035."""

import pytest
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClients031To035:
    """Test clients 031-035 configurations."""

    def test_client_031_config_loads(self):
        """Test client 031 (EduTech Academy) config loads."""
        from parwa.clients.client_031.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_031"
        assert config.client_name == "EduTech Academy"
        assert config.industry == "education_technology"
        assert config.variant == "parwa_junior"

    def test_client_032_config_loads(self):
        """Test client 032 (FoodDash Delivery) config loads."""
        from parwa.clients.client_032.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_032"
        assert config.client_name == "FoodDash Delivery"
        assert config.industry == "food_delivery"
        assert config.variant == "mini_parwa"

    def test_client_033_config_loads(self):
        """Test client 033 (SecureLife Insurance) config loads."""
        from parwa.clients.client_033.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_033"
        assert config.client_name == "SecureLife Insurance"
        assert config.industry == "insurtech"
        assert config.variant == "parwa_high"

    def test_client_034_config_loads(self):
        """Test client 034 (TeleCare Health) config loads."""
        from parwa.clients.client_034.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_034"
        assert config.client_name == "TeleCare Health"
        assert config.industry == "telehealth"
        assert config.variant == "parwa_high"

    def test_client_035_config_loads(self):
        """Test client 035 (FreightPro Logistics) config loads."""
        from parwa.clients.client_035.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_035"
        assert config.client_name == "FreightPro Logistics"
        assert config.industry == "logistics"
        assert config.variant == "parwa_junior"

    def test_all_client_ids_unique(self):
        """Test all 5 clients have unique IDs."""
        from parwa.clients.client_031.config import get_client_config as c31
        from parwa.clients.client_032.config import get_client_config as c32
        from parwa.clients.client_033.config import get_client_config as c33
        from parwa.clients.client_034.config import get_client_config as c34
        from parwa.clients.client_035.config import get_client_config as c35
        
        ids = [c31().client_id, c32().client_id, c33().client_id, c34().client_id, c35().client_id]
        assert len(ids) == len(set(ids))

    def test_all_industries_valid(self):
        """Test all 5 clients have valid industries."""
        from parwa.clients.client_031.config import get_client_config as c31
        from parwa.clients.client_032.config import get_client_config as c32
        from parwa.clients.client_033.config import get_client_config as c33
        from parwa.clients.client_034.config import get_client_config as c34
        from parwa.clients.client_035.config import get_client_config as c35
        
        industries = [c31().industry, c32().industry, c33().industry, c34().industry, c35().industry]
        for industry in industries:
            assert industry is not None
            assert len(industry) > 0

    def test_parwa_high_voice_support_enabled(self):
        """Test PARWA High clients have voice support enabled."""
        from parwa.clients.client_033.config import get_client_config
        config = get_client_config()
        assert config.variant == "parwa_high"
        assert config.feature_flags.voice_support is True

    def test_parwa_junior_voice_support_disabled(self):
        """Test PARWA Junior clients have voice support disabled."""
        from parwa.clients.client_031.config import get_client_config
        config = get_client_config()
        assert config.variant == "parwa_junior"
        assert config.feature_flags.voice_support is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
