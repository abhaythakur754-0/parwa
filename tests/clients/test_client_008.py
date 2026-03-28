"""Tests for Client 008 - TravelEase"""

import pytest
import json
from pathlib import Path
from clients.client_008.config import get_client_config, ClientConfig


class TestClient008Config:
    """Tests for Client 008 configuration"""

    def test_config_loads_correctly(self):
        """Test that client 008 config loads without error"""
        config = get_client_config()
        assert config is not None
        assert isinstance(config, ClientConfig)

    def test_client_id(self):
        """Test client ID is correct"""
        config = get_client_config()
        assert config.client_id == "client_008"

    def test_client_name(self):
        """Test client name is correct"""
        config = get_client_config()
        assert config.client_name == "TravelEase"

    def test_industry(self):
        """Test industry is travel"""
        config = get_client_config()
        assert config.industry == "travel"

    def test_variant(self):
        """Test variant is parwa_high"""
        config = get_client_config()
        assert config.variant == "parwa_high"

    def test_timezone(self):
        """Test timezone is UTC (global)"""
        config = get_client_config()
        assert config.timezone == "UTC"

    def test_business_hours_24_7(self):
        """Test business hours are 24/7"""
        config = get_client_config()
        assert config.business_hours.start.hour == 0
        assert config.business_hours.start.minute == 0
        assert config.business_hours.end.hour == 23
        assert config.business_hours.end.minute == 59

    def test_escalation_contacts(self):
        """Test escalation contacts are configured"""
        config = get_client_config()
        assert config.escalation_contacts.email == "support@travelease.com"
        assert config.escalation_contacts.phone == "+1-555-0158"

    def test_feature_flags_parwa_high(self):
        """Test PARWA High feature flags"""
        config = get_client_config()
        assert config.feature_flags.multi_language is True  # Global travel
        assert config.feature_flags.voice_support is True  # PARWA High feature

    def test_sla_fast_response(self):
        """Test SLA has fast response for travel emergencies"""
        config = get_client_config()
        assert config.sla.first_response_hours == 1  # 1 hour
        assert config.sla.resolution_hours == 12

    def test_metadata(self):
        """Test metadata is populated"""
        config = get_client_config()
        assert config.metadata["website"] == "https://travelease.com"
        assert "destinations" in config.metadata
        assert config.metadata["destinations"] == 190

    def test_partner_network(self):
        """Test partner network is defined"""
        config = get_client_config()
        partners = config.metadata.get("partners", {})
        assert partners.get("airlines") == 50
        assert partners.get("hotels") == 10000

    def test_languages_supported(self):
        """Test multiple languages supported for global travel"""
        config = get_client_config()
        languages = config.metadata.get("languages_supported", [])
        assert len(languages) >= 10
        assert "English" in languages
        assert "Spanish" in languages

    def test_emergency_support(self):
        """Test emergency support is configured"""
        config = get_client_config()
        emergency = config.metadata.get("emergency_support", {})
        assert emergency.get("available") is True
        assert emergency.get("response_time_minutes") == 15


class TestClient008FAQ:
    """Tests for Client 008 FAQ knowledge base"""

    @pytest.fixture
    def faq_data(self):
        """Load FAQ JSON data"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_008" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            return json.load(f)

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_008" / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_has_client_id(self, faq_data):
        """Test FAQ has correct client ID"""
        assert faq_data["client_id"] == "client_008"

    def test_faq_has_categories(self, faq_data):
        """Test FAQ has travel-specific categories"""
        categories = faq_data.get("categories", [])
        assert len(categories) >= 5
        assert "Bookings" in categories
        assert "Flights" in categories
        assert "Hotels" in categories

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

    def test_faq_travel_specific_content(self, faq_data):
        """Test FAQ contains travel-specific content"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        # Check for travel-specific terms
        travel_terms = ["flight", "hotel", "booking", "travel", "cancellation"]
        found_terms = [term for term in travel_terms if term in all_text]
        assert len(found_terms) >= 4


class TestClient008Isolation:
    """Tests for client isolation"""

    def test_client_id_unique(self):
        """Test client ID is unique from other clients"""
        config = get_client_config()
        # Should not be client_001 through client_007
        assert config.client_id not in [
            "client_001", "client_002", "client_003",
            "client_004", "client_005", "client_006", "client_007"
        ]

    def test_paddle_account_unique(self):
        """Test Paddle account ID is unique"""
        config = get_client_config()
        assert config.paddle_account_id == "acc_travelease008"

    def test_no_cross_client_data(self):
        """Test config doesn't reference other clients"""
        config = get_client_config()
        config_str = json.dumps({
            "client_id": config.client_id,
            "client_name": config.client_name,
            "metadata": config.metadata
        })
        # Should not contain other client names
        other_clients = ["Acme", "TechFlow", "MediCare", "FastShip", "SecureBank", "ShopMax", "EduLearn"]
        for client in other_clients:
            assert client not in config_str

    def test_24_7_support_enabled(self):
        """Test 24/7 support is configured"""
        config = get_client_config()
        # 24/7 means start at 00:00 and end at 23:59
        assert config.business_hours.start.hour == 0
        assert config.business_hours.end.hour == 23
