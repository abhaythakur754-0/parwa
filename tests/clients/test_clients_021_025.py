"""
Tests for Client Configurations 021-025.

Validates all new client configurations for Week 30 milestone.
"""

import pytest
from pathlib import Path
import sys

# Add clients to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClient021Config:
    """Test Client 021 (GameVerse Entertainment) configuration."""

    def test_client_021_config_loads(self):
        """Test that client 021 config loads correctly."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        assert config is not None

    def test_client_021_basic_info(self):
        """Test client 021 basic information."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_021"
        assert config.client_name == "GameVerse Entertainment"
        assert config.industry == "gaming_entertainment"
        assert config.variant == "parwa_junior"

    def test_client_021_variant_limits(self):
        """Test client 021 variant limits."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        
        assert config.variant_limits.refund_limit == 100.0
        assert config.variant_limits.escalation_threshold == 0.45

    def test_client_021_integrations(self):
        """Test client 021 integrations."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        
        assert config.integrations.discord is True
        assert config.integrations.stripe is True
        assert config.integrations.zendesk is True

    def test_client_021_gaming_config(self):
        """Test client 021 gaming-specific configuration."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        
        assert config.gaming.enabled is True
        assert config.gaming.in_game_support is True
        assert config.gaming.dlc_support is True
        assert config.gaming.multiplayer_support is True

    def test_client_021_is_24_7(self):
        """Test client 021 is 24/7 for global gamers."""
        from clients.client_021.config import get_client_config
        config = get_client_config()
        
        assert config.business_hours.start.hour == 0
        assert config.business_hours.end.hour == 23


class TestClient022Config:
    """Test Client 022 (AutoDrive Motors) configuration."""

    def test_client_022_config_loads(self):
        """Test that client 022 config loads correctly."""
        from clients.client_022.config import get_client_config
        config = get_client_config()
        assert config is not None

    def test_client_022_basic_info(self):
        """Test client 022 basic information."""
        from clients.client_022.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_022"
        assert config.client_name == "AutoDrive Motors"
        assert config.industry == "automotive"
        assert config.variant == "parwa_high"

    def test_client_022_variant_limits(self):
        """Test client 022 variant limits."""
        from clients.client_022.config import get_client_config
        config = get_client_config()
        
        assert config.variant_limits.refund_limit == 500.0  # Parts/service

    def test_client_022_integrations(self):
        """Test client 022 integrations."""
        from clients.client_022.config import get_client_config
        config = get_client_config()
        
        assert config.integrations.salesforce is True
        assert config.integrations.sap is True
        assert config.integrations.twilio is True

    def test_client_022_automotive_config(self):
        """Test client 022 automotive-specific configuration."""
        from clients.client_022.config import get_client_config
        config = get_client_config()
        
        assert config.automotive.enabled is True
        assert config.automotive.service_appointment_handling is True
        assert config.automotive.warranty_claims is True
        assert config.automotive.roadside_assistance is True


class TestClient023Config:
    """Test Client 023 (PowerGrid Utilities) configuration."""

    def test_client_023_config_loads(self):
        """Test that client 023 config loads correctly."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        assert config is not None

    def test_client_023_basic_info(self):
        """Test client 023 basic information."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_023"
        assert config.client_name == "PowerGrid Utilities"
        assert config.industry == "energy_utilities"
        assert config.variant == "parwa_high"

    def test_client_023_variant_limits(self):
        """Test client 023 variant limits."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        
        assert config.variant_limits.refund_limit == 200.0  # Billing adjustments

    def test_client_023_energy_config(self):
        """Test client 023 energy-specific configuration."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        
        assert config.energy.enabled is True
        assert config.energy.outage_management is True
        assert config.energy.billing_inquiry is True
        assert config.energy.emergency_protocols is True

    def test_client_023_is_24_7(self):
        """Test client 023 is 24/7 for utilities."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        
        assert config.business_hours.start.hour == 0
        assert config.business_hours.end.hour == 23

    def test_client_023_fast_sla(self):
        """Test client 023 has fast SLA for utilities."""
        from clients.client_023.config import get_client_config
        config = get_client_config()
        
        assert config.sla.first_response_hours == 1


class TestClient024Config:
    """Test Client 024 (Daily Herald Media) configuration."""

    def test_client_024_config_loads(self):
        """Test that client 024 config loads correctly."""
        from clients.client_024.config import get_client_config
        config = get_client_config()
        assert config is not None

    def test_client_024_basic_info(self):
        """Test client 024 basic information."""
        from clients.client_024.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_024"
        assert config.client_name == "Daily Herald Media"
        assert config.industry == "media_publishing"
        assert config.variant == "parwa_junior"

    def test_client_024_variant_limits(self):
        """Test client 024 variant limits."""
        from clients.client_024.config import get_client_config
        config = get_client_config()
        
        assert config.variant_limits.refund_limit == 50.0  # Subscriptions

    def test_client_024_integrations(self):
        """Test client 024 integrations."""
        from clients.client_024.config import get_client_config
        config = get_client_config()
        
        assert config.integrations.stripe is True
        assert config.integrations.mailchimp is True
        assert config.integrations.wordpress is True

    def test_client_024_media_config(self):
        """Test client 024 media-specific configuration."""
        from clients.client_024.config import get_client_config
        config = get_client_config()
        
        assert config.media.enabled is True
        assert config.media.subscription_management is True
        assert config.media.content_inquiries is True


class TestClient025Config:
    """Test Client 025 (ConnectTel Communications) configuration."""

    def test_client_025_config_loads(self):
        """Test that client 025 config loads correctly."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        assert config is not None

    def test_client_025_basic_info(self):
        """Test client 025 basic information."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_025"
        assert config.client_name == "ConnectTel Communications"
        assert config.industry == "telecommunications"
        assert config.variant == "parwa_high"

    def test_client_025_variant_limits(self):
        """Test client 025 variant limits."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.variant_limits.refund_limit == 300.0  # Service credits
        assert config.variant_limits.concurrent_calls == 20

    def test_client_025_integrations(self):
        """Test client 025 integrations."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.integrations.salesforce is True
        assert config.integrations.sap is True
        assert config.integrations.twilio is True

    def test_client_025_telecom_config(self):
        """Test client 025 telecom-specific configuration."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.telecom.enabled is True
        assert config.telecom.technical_support is True
        assert config.telecom.network_troubleshooting is True
        assert config.telecom.number_porting is True

    def test_client_025_is_24_7(self):
        """Test client 025 is 24/7 for telecom."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.business_hours.start.hour == 0
        assert config.business_hours.end.hour == 23

    def test_client_025_fast_sla(self):
        """Test client 025 has fast SLA for telecom."""
        from clients.client_025.config import get_client_config
        config = get_client_config()
        
        assert config.sla.first_response_hours == 1


class TestClientsUniqueIDs:
    """Test that all client IDs are unique."""

    def test_all_client_ids_unique(self):
        """Test that clients 021-025 have unique IDs."""
        from clients.client_021.config import get_client_config as get_021
        from clients.client_022.config import get_client_config as get_022
        from clients.client_023.config import get_client_config as get_023
        from clients.client_024.config import get_client_config as get_024
        from clients.client_025.config import get_client_config as get_025
        
        configs = [get_021(), get_022(), get_023(), get_024(), get_025()]
        client_ids = [c.client_id for c in configs]
        
        # Check all unique
        assert len(client_ids) == len(set(client_ids))

    def test_all_client_names_unique(self):
        """Test that clients 021-025 have unique names."""
        from clients.client_021.config import get_client_config as get_021
        from clients.client_022.config import get_client_config as get_022
        from clients.client_023.config import get_client_config as get_023
        from clients.client_024.config import get_client_config as get_024
        from clients.client_025.config import get_client_config as get_025
        
        configs = [get_021(), get_022(), get_023(), get_024(), get_025()]
        client_names = [c.client_name for c in configs]
        
        # Check all unique
        assert len(client_names) == len(set(client_names))

    def test_all_industries_unique(self):
        """Test that clients 021-025 represent different industries."""
        from clients.client_021.config import get_client_config as get_021
        from clients.client_022.config import get_client_config as get_022
        from clients.client_023.config import get_client_config as get_023
        from clients.client_024.config import get_client_config as get_024
        from clients.client_025.config import get_client_config as get_025
        
        configs = [get_021(), get_022(), get_023(), get_024(), get_025()]
        industries = [c.industry for c in configs]
        
        # Check all unique
        assert len(industries) == len(set(industries))


class TestClientsVariantsValid:
    """Test that all variant assignments are valid."""

    def test_all_variants_valid(self):
        """Test that all clients have valid variant assignments."""
        from clients.client_021.config import get_client_config as get_021
        from clients.client_022.config import get_client_config as get_022
        from clients.client_023.config import get_client_config as get_023
        from clients.client_024.config import get_client_config as get_024
        from clients.client_025.config import get_client_config as get_025
        
        valid_variants = ["mini", "parwa_junior", "parwa_high"]
        
        configs = [get_021(), get_022(), get_023(), get_024(), get_025()]
        
        for config in configs:
            assert config.variant in valid_variants, \
                f"{config.client_id} has invalid variant: {config.variant}"

    def test_parwa_high_clients(self):
        """Test that automotive, energy, and telecom use PARWA High."""
        from clients.client_022.config import get_client_config as get_022
        from clients.client_023.config import get_client_config as get_023
        from clients.client_025.config import get_client_config as get_025
        
        # Automotive, Energy, Telecom should be PARWA High
        assert get_022().variant == "parwa_high"
        assert get_023().variant == "parwa_high"
        assert get_025().variant == "parwa_high"

    def test_parwa_junior_clients(self):
        """Test that gaming and media use PARWA Junior."""
        from clients.client_021.config import get_client_config as get_021
        from clients.client_024.config import get_client_config as get_024
        
        # Gaming, Media should be PARWA Junior
        assert get_021().variant == "parwa_junior"
        assert get_024().variant == "parwa_junior"


class TestClientFilesExist:
    """Test that all required client files exist."""

    def test_client_021_files_exist(self):
        """Test client 021 directory structure."""
        base = Path("clients/client_021")
        assert (base / "config.py").exists()
        assert (base / "__init__.py").exists()

    def test_client_022_files_exist(self):
        """Test client 022 directory structure."""
        base = Path("clients/client_022")
        assert (base / "config.py").exists()
        assert (base / "__init__.py").exists()

    def test_client_023_files_exist(self):
        """Test client 023 directory structure."""
        base = Path("clients/client_023")
        assert (base / "config.py").exists()
        assert (base / "__init__.py").exists()

    def test_client_024_files_exist(self):
        """Test client 024 directory structure."""
        base = Path("clients/client_024")
        assert (base / "config.py").exists()
        assert (base / "__init__.py").exists()

    def test_client_025_files_exist(self):
        """Test client 025 directory structure."""
        base = Path("clients/client_025")
        assert (base / "config.py").exists()
        assert (base / "__init__.py").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
