"""Tests for Client 001 configuration and knowledge base"""

import pytest
import json
from pathlib import Path

CLIENT_DIR = Path(__file__).parent.parent.parent / "clients" / "client_001"


class TestClientConfig:
    """Tests for client configuration"""

    def test_config_module_imports(self):
        from clients.client_001.config import ClientConfig, get_client_config
        assert ClientConfig is not None

    def test_config_loads_correctly(self):
        from clients.client_001.config import get_client_config
        config = get_client_config()
        assert config.client_id == "client_001"
        assert config.client_name == "Acme E-commerce"
        assert config.industry == "ecommerce"

    def test_business_hours_configured(self):
        from clients.client_001.config import get_client_config
        config = get_client_config()
        assert config.business_hours.start.hour == 9
        assert config.business_hours.end.hour == 18

    def test_escalation_contacts_configured(self):
        from clients.client_001.config import get_client_config
        config = get_client_config()
        assert config.escalation_contacts.email is not None

    def test_feature_flags_configured(self):
        from clients.client_001.config import get_client_config
        config = get_client_config()
        assert config.feature_flags.shadow_mode is True

    def test_sla_configured(self):
        from clients.client_001.config import get_client_config
        config = get_client_config()
        assert config.sla.first_response_hours > 0


class TestFAQ:
    def test_faq_file_exists(self):
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_loads_correctly(self):
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        assert len(data["entries"]) >= 20

    def test_faq_entries_have_required_fields(self):
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        for entry in data["entries"]:
            assert "id" in entry
            assert "question" in entry
            assert "answer" in entry


class TestProducts:
    def test_products_file_exists(self):
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        assert products_path.exists()

    def test_products_load_correctly(self):
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        assert len(data["products"]) >= 10


class TestPolicies:
    def test_policies_file_exists(self):
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        assert policies_path.exists()

    def test_refund_policy_exists(self):
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        assert "refund" in data["policies"]


class TestDashboard:
    def test_dashboard_file_exists(self):
        dashboard_path = CLIENT_DIR.parent.parent / "monitoring" / "dashboards" / "client_001_dashboard.json"
        assert dashboard_path.exists()

    def test_dashboard_valid_json(self):
        dashboard_path = CLIENT_DIR.parent.parent / "monitoring" / "dashboards" / "client_001_dashboard.json"
        with open(dashboard_path) as f:
            data = json.load(f)
        assert "dashboard" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
