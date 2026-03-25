"""Tests for Client 006 - ShopMax Retail"""

import pytest
import json
from pathlib import Path
from clients.client_006.config import get_client_config, ClientConfig


class TestClient006Config:
    """Tests for Client 006 configuration"""

    def test_config_loads_correctly(self):
        """Test that client 006 config loads without error"""
        config = get_client_config()
        assert config is not None
        assert isinstance(config, ClientConfig)

    def test_client_id(self):
        """Test client ID is correct"""
        config = get_client_config()
        assert config.client_id == "client_006"

    def test_client_name(self):
        """Test client name is correct"""
        config = get_client_config()
        assert config.client_name == "ShopMax Retail"

    def test_industry(self):
        """Test industry is retail"""
        config = get_client_config()
        assert config.industry == "retail"

    def test_variant(self):
        """Test variant is mini"""
        config = get_client_config()
        assert config.variant == "mini"

    def test_timezone(self):
        """Test timezone is Chicago (CST)"""
        config = get_client_config()
        assert config.timezone == "America/Chicago"

    def test_business_hours(self):
        """Test business hours are extended retail hours (9am-9pm)"""
        config = get_client_config()
        assert config.business_hours.start.hour == 9
        assert config.business_hours.end.hour == 21  # 9 PM
        assert config.business_hours.timezone == "America/Chicago"

    def test_escalation_contacts(self):
        """Test escalation contacts are configured"""
        config = get_client_config()
        assert config.escalation_contacts.email == "support@shopmax-retail.com"
        assert config.escalation_contacts.phone == "+1-555-0156"

    def test_feature_flags(self):
        """Test feature flags are set"""
        config = get_client_config()
        assert config.feature_flags.shadow_mode is True
        assert config.feature_flags.auto_escalation is True
        assert config.feature_flags.knowledge_base_search is True

    def test_sla_config(self):
        """Test SLA configuration"""
        config = get_client_config()
        assert config.sla.first_response_hours == 4
        assert config.sla.resolution_hours == 24
        assert config.sla.escalation_hours == 2

    def test_metadata(self):
        """Test metadata is populated"""
        config = get_client_config()
        assert config.metadata["website"] == "https://shopmax-retail.com"
        assert "store_count" in config.metadata
        assert config.metadata["store_count"] == 45

    def test_product_categories(self):
        """Test product categories are defined"""
        config = get_client_config()
        categories = config.metadata.get("product_categories", [])
        assert len(categories) > 0
        assert "Electronics" in categories

    def test_special_features(self):
        """Test special features are configured"""
        config = get_client_config()
        features = config.metadata.get("special_features", {})
        assert features.get("loyalty_program") is True
        assert features.get("store_pickup") is True


class TestClient006FAQ:
    """Tests for Client 006 FAQ knowledge base"""

    @pytest.fixture
    def faq_data(self):
        """Load FAQ JSON data"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_006" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            return json.load(f)

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_006" / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_has_client_id(self, faq_data):
        """Test FAQ has correct client ID"""
        assert faq_data["client_id"] == "client_006"

    def test_faq_has_categories(self, faq_data):
        """Test FAQ has categories defined"""
        categories = faq_data.get("categories", [])
        assert len(categories) >= 5
        assert "Orders" in categories
        assert "Returns" in categories
        assert "Shipping" in categories

    def test_faq_has_entries(self, faq_data):
        """Test FAQ has at least 20 entries"""
        entries = faq_data.get("entries", [])
        assert len(entries) >= 20

    def test_faq_entry_structure(self, faq_data):
        """Test each FAQ entry has required fields"""
        entries = faq_data.get("entries", [])
        for entry in entries:
            assert "id" in entry
            assert "category" in entry
            assert "question" in entry
            assert "answer" in entry
            assert "keywords" in entry
            assert isinstance(entry["keywords"], list)

    def test_faq_categories_match(self, faq_data):
        """Test FAQ entries reference valid categories"""
        categories = set(faq_data.get("categories", []))
        entries = faq_data.get("entries", [])
        for entry in entries:
            assert entry["category"] in categories

    def test_faq_keywords_not_empty(self, faq_data):
        """Test FAQ entries have keywords"""
        entries = faq_data.get("entries", [])
        for entry in entries:
            assert len(entry["keywords"]) > 0

    def test_faq_unique_ids(self, faq_data):
        """Test all FAQ entry IDs are unique"""
        entries = faq_data.get("entries", [])
        ids = [entry["id"] for entry in entries]
        assert len(ids) == len(set(ids))

    def test_faq_retail_specific_content(self, faq_data):
        """Test FAQ contains retail-specific content"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        # Check for retail-specific terms
        retail_terms = ["store", "shop", "retail", "purchase"]
        found_terms = [term for term in retail_terms if term in all_text]
        assert len(found_terms) > 0


class TestClient006Isolation:
    """Tests for client isolation"""

    def test_client_id_unique(self):
        """Test client ID is unique from other clients"""
        config = get_client_config()
        # Should not be client_001 through client_005
        assert config.client_id not in [
            "client_001", "client_002", "client_003", "client_004", "client_005"
        ]

    def test_paddle_account_unique(self):
        """Test Paddle account ID is unique"""
        config = get_client_config()
        assert config.paddle_account_id == "acc_shopmax006"

    def test_no_cross_client_data(self):
        """Test config doesn't reference other clients"""
        config = get_client_config()
        config_str = json.dumps({
            "client_id": config.client_id,
            "client_name": config.client_name,
            "metadata": config.metadata
        })
        # Should not contain other client names
        other_clients = ["Acme", "TechFlow", "MediCare", "FastShip", "SecureBank"]
        for client in other_clients:
            assert client not in config_str
