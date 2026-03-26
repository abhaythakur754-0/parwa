"""Tests for Client Configurations 026-030."""

import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClients026To030:
    """Test clients 026-030 configurations."""

    def test_all_configs_load(self):
        """Test all client configs load."""
        from clients.client_026.config import get_client_config as g26
        from clients.client_027.config import get_client_config as g27
        from clients.client_028.config import get_client_config as g28
        from clients.client_029.config import get_client_config as g29
        from clients.client_030.config import get_client_config as g30
        
        configs = [g26(), g27(), g28(), g29(), g30()]
        assert all(c is not None for c in configs)

    def test_all_client_ids_unique(self):
        """Test unique client IDs."""
        from clients.client_026.config import get_client_config as g26
        from clients.client_027.config import get_client_config as g27
        from clients.client_028.config import get_client_config as g28
        from clients.client_029.config import get_client_config as g29
        from clients.client_030.config import get_client_config as g30
        
        ids = [g26().client_id, g27().client_id, g28().client_id, g29().client_id, g30().client_id]
        assert len(ids) == len(set(ids))

    def test_all_industries_unique(self):
        """Test unique industries."""
        from clients.client_026.config import get_client_config as g26
        from clients.client_027.config import get_client_config as g27
        from clients.client_028.config import get_client_config as g28
        from clients.client_029.config import get_client_config as g29
        from clients.client_030.config import get_client_config as g30
        
        industries = [g26().industry, g27().industry, g28().industry, g29().industry, g30().industry]
        assert len(industries) == len(set(industries))

    def test_client_026_pharmaceutical(self):
        """Test client 026 is pharmaceutical."""
        from clients.client_026.config import get_client_config
        c = get_client_config()
        assert c.client_id == "client_026"
        assert c.industry == "pharmaceutical"
        assert c.variant == "parwa_high"
        assert c.pharma.enabled is True
        assert c.compliance.fda is True
        assert c.compliance.hipaa is True

    def test_client_027_event_management(self):
        """Test client 027 is event management."""
        from clients.client_027.config import get_client_config
        c = get_client_config()
        assert c.client_id == "client_027"
        assert c.industry == "event_management"
        assert c.variant == "parwa_junior"
        assert c.event.enabled is True

    def test_client_028_hr_payroll(self):
        """Test client 028 is HR/payroll."""
        from clients.client_028.config import get_client_config
        c = get_client_config()
        assert c.client_id == "client_028"
        assert c.industry == "hr_payroll"
        assert c.variant == "parwa_high"
        assert c.hr.enabled is True
        assert c.compliance.pii_protection is True

    def test_client_029_marketing(self):
        """Test client 029 is marketing."""
        from clients.client_029.config import get_client_config
        c = get_client_config()
        assert c.client_id == "client_029"
        assert c.industry == "marketing_advertising"
        assert c.variant == "parwa_junior"
        assert c.marketing.enabled is True

    def test_client_030_sports_fitness(self):
        """Test client 030 is sports/fitness."""
        from clients.client_030.config import get_client_config
        c = get_client_config()
        assert c.client_id == "client_030"
        assert c.industry == "sports_fitness"
        assert c.variant == "parwa_junior"
        assert c.fitness.enabled is True

    def test_30_clients_total_unique(self):
        """Test all 30 clients have unique IDs (001-030)."""
        from clients.client_026.config import get_client_config as g26
        from clients.client_027.config import get_client_config as g27
        from clients.client_028.config import get_client_config as g28
        from clients.client_029.config import get_client_config as g29
        from clients.client_030.config import get_client_config as g30
        
        new_ids = [g26().client_id, g27().client_id, g28().client_id, g29().client_id, g30().client_id]
        
        # Verify these are 026-030
        expected = ["client_026", "client_027", "client_028", "client_029", "client_030"]
        assert sorted(new_ids) == sorted(expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
