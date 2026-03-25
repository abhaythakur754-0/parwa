"""Tests for Client 010 - StreamPlus Media"""

import pytest
import json
from pathlib import Path
from clients.client_010.config import get_client_config, ClientConfig


class TestClient010Config:
    """Tests for Client 010 configuration"""

    def test_config_loads_correctly(self):
        """Test that client 010 config loads without error"""
        config = get_client_config()
        assert config is not None
        assert isinstance(config, ClientConfig)

    def test_client_id(self):
        """Test client ID is correct"""
        config = get_client_config()
        assert config.client_id == "client_010"

    def test_client_name(self):
        """Test client name is correct"""
        config = get_client_config()
        assert config.client_name == "StreamPlus Media"

    def test_industry(self):
        """Test industry is entertainment"""
        config = get_client_config()
        assert config.industry == "entertainment"

    def test_variant(self):
        """Test variant is parwa_high"""
        config = get_client_config()
        assert config.variant == "parwa_high"

    def test_timezone(self):
        """Test timezone is Los Angeles (PST)"""
        config = get_client_config()
        assert config.timezone == "America/Los_Angeles"

    def test_business_hours_24_7(self):
        """Test business hours are 24/7"""
        config = get_client_config()
        assert config.business_hours.start.hour == 0
        assert config.business_hours.end.hour == 23
        assert config.business_hours.end.minute == 59

    def test_sla_fast_response(self):
        """Test SLA has fast response for streaming issues"""
        config = get_client_config()
        assert config.sla.first_response_hours == 1

    def test_feature_flags_parwa_high(self):
        """Test PARWA High feature flags"""
        config = get_client_config()
        assert config.feature_flags.voice_support is True
        assert config.feature_flags.multi_language is True


class TestClient010FAQ:
    """Tests for Client 010 FAQ knowledge base"""

    @pytest.fixture
    def faq_data(self):
        """Load FAQ JSON data"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_010" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            return json.load(f)

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_010" / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_has_client_id(self, faq_data):
        """Test FAQ has correct client ID"""
        assert faq_data["client_id"] == "client_010"

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

    def test_faq_streaming_specific(self, faq_data):
        """Test FAQ contains streaming/entertainment content"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        streaming_terms = ["stream", "video", "subscription", "watch", "buffering"]
        found_terms = [term for term in streaming_terms if term in all_text]
        assert len(found_terms) >= 4


class TestClient010Isolation:
    """Tests for client isolation"""

    def test_client_id_unique(self):
        """Test client ID is unique from all other clients"""
        config = get_client_config()
        assert config.client_id not in [
            "client_001", "client_002", "client_003",
            "client_004", "client_005", "client_006",
            "client_007", "client_008", "client_009"
        ]

    def test_paddle_account_unique(self):
        """Test Paddle account ID is unique"""
        config = get_client_config()
        assert config.paddle_account_id == "acc_streamplus010"

    def test_no_cross_client_data(self):
        """Test config doesn't reference other clients"""
        config = get_client_config()
        config_str = json.dumps({
            "client_id": config.client_id,
            "client_name": config.client_name,
            "metadata": config.metadata
        })
        other_clients = ["Acme", "TechFlow", "MediCare", "FastShip", "SecureBank",
                        "ShopMax", "EduLearn", "TravelEase", "HomeFind"]
        for client in other_clients:
            assert client not in config_str

    def test_24_7_support_configured(self):
        """Test 24/7 support is configured"""
        config = get_client_config()
        # 24/7 means start at 00:00 and end at 23:59
        assert config.business_hours.start.hour == 0
        assert config.business_hours.start.minute == 0
        assert config.business_hours.end.hour == 23
