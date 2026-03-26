"""Tests for Client 002 configuration and knowledge base"""

import pytest
import json
from pathlib import Path

CLIENT_DIR = Path(__file__).parent.parent.parent / "clients" / "client_002"


class TestClientConfig:
    """Tests for client 002 configuration"""

    def test_config_module_imports(self):
        """Test that config module can be imported"""
        from clients.client_002.config import ClientConfig, get_client_config
        assert ClientConfig is not None
        assert get_client_config is not None

    def test_config_loads_correctly(self):
        """Test that config loads with correct values"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_002"
        assert config.client_name == "TechStart SaaS"
        assert config.industry == "saas"
        assert config.variant == "parwa_high"
        assert config.timezone == "America/Los_Angeles"

    def test_business_hours_extended(self):
        """Test extended business hours (8am-8pm)"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.business_hours.start.hour == 8
        assert config.business_hours.end.hour == 20  # 8pm = 20:00

    def test_escalation_contacts_configured(self):
        """Test escalation contacts including PagerDuty"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.escalation_contacts.email is not None
        assert config.escalation_contacts.pagerduty_key is not None

    def test_feature_flags_for_saas(self):
        """Test SaaS-specific feature flags"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.feature_flags.api_integration is True
        assert config.feature_flags.advanced_analytics is True
        assert config.feature_flags.multi_language is True

    def test_sla_configured(self):
        """Test SLA is configured with tighter times"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.sla.first_response_hours == 2
        assert config.sla.resolution_hours == 8

    def test_compliance_settings(self):
        """Test compliance configuration"""
        from clients.client_002.config import get_client_config
        config = get_client_config()
        
        assert config.compliance.gdpr_enabled is True
        assert config.compliance.soc2_enabled is True


class TestFAQ:
    """Tests for FAQ knowledge base"""

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        assert faq_path.exists(), "FAQ file not found"

    def test_faq_loads_correctly(self):
        """Test FAQ loads as valid JSON"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        assert "entries" in data
        assert len(data["entries"]) >= 25

    def test_faq_entries_have_required_fields(self):
        """Test all FAQ entries have required fields"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        for entry in data["entries"]:
            assert "id" in entry
            assert "category" in entry
            assert "question" in entry
            assert "answer" in entry
            assert "keywords" in entry

    def test_faq_saas_categories(self):
        """Test SaaS-specific categories are covered"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        categories = {e["category"] for e in data["entries"]}
        required = {"Account", "Billing", "Features", "Integrations", "API"}
        
        assert required.issubset(categories)

    def test_faq_api_questions(self):
        """Test API-related FAQs exist"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        api_faqs = [e for e in data["entries"] if e["category"] == "API"]
        assert len(api_faqs) >= 5, "Should have at least 5 API FAQs"


class TestProducts:
    """Tests for product catalog"""

    def test_products_file_exists(self):
        """Test products file exists"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        assert products_path.exists(), "Products file not found"

    def test_products_load_correctly(self):
        """Test products load as valid JSON"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        assert "products" in data
        assert len(data["products"]) >= 3  # Free, Pro, Enterprise

    def test_saas_tiers_exist(self):
        """Test SaaS tiers are defined"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        tiers = {p["tier"] for p in data["products"]}
        required = {"free", "pro", "enterprise"}
        
        assert required.issubset(tiers)

    def test_products_have_pricing(self):
        """Test products have pricing info"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        for product in data["products"]:
            assert "price_monthly" in product
            assert "features" in product

    def test_addons_exist(self):
        """Test add-ons are defined"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        assert "addons" in data
        assert len(data["addons"]) >= 1


class TestPolicies:
    """Tests for policies"""

    def test_policies_file_exists(self):
        """Test policies file exists"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        assert policies_path.exists(), "Policies file not found"

    def test_policies_load_correctly(self):
        """Test policies load as valid JSON"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "policies" in data

    def test_refund_policy_exists(self):
        """Test 14-day refund policy"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "refund" in data["policies"]
        assert data["policies"]["refund"]["window_days"] == 14

    def test_sla_policy_exists(self):
        """Test SLA policy is defined"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "sla" in data["policies"]
        assert "uptime_target" in data["policies"]["sla"]

    def test_api_rate_limits(self):
        """Test API rate limits are defined"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "api_rate_limits" in data["policies"]
        assert "free" in data["policies"]["api_rate_limits"]


class TestDashboard:
    """Tests for Grafana dashboard"""

    def test_dashboard_file_exists(self):
        """Test dashboard file exists"""
        dashboard_path = CLIENT_DIR.parent.parent / "monitoring" / "dashboards" / "client_002_dashboard.json"
        assert dashboard_path.exists(), "Dashboard file not found"

    def test_dashboard_valid_json(self):
        """Test dashboard is valid JSON"""
        dashboard_path = CLIENT_DIR.parent.parent / "monitoring" / "dashboards" / "client_002_dashboard.json"
        with open(dashboard_path) as f:
            data = json.load(f)
        
        assert "dashboard" in data
        assert "panels" in data

    def test_dashboard_has_api_panel(self):
        """Test dashboard has API usage panel for SaaS"""
        dashboard_path = CLIENT_DIR.parent.parent / "monitoring" / "dashboards" / "client_002_dashboard.json"
        with open(dashboard_path) as f:
            data = json.load(f)
        
        panel_titles = {p["title"] for p in data["panels"]}
        assert "API Usage" in panel_titles


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
