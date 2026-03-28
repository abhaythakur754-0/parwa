"""Tests for Client 009 - HomeFind Realty"""

import pytest
import json
from pathlib import Path
from clients.client_009.config import get_client_config, ClientConfig


class TestClient009Config:
    """Tests for Client 009 configuration"""

    def test_config_loads_correctly(self):
        """Test that client 009 config loads without error"""
        config = get_client_config()
        assert config is not None
        assert isinstance(config, ClientConfig)

    def test_client_id(self):
        """Test client ID is correct"""
        config = get_client_config()
        assert config.client_id == "client_009"

    def test_client_name(self):
        """Test client name is correct"""
        config = get_client_config()
        assert config.client_name == "HomeFind Realty"

    def test_industry(self):
        """Test industry is real_estate"""
        config = get_client_config()
        assert config.industry == "real_estate"

    def test_variant(self):
        """Test variant is parwa_junior"""
        config = get_client_config()
        assert config.variant == "parwa_junior"

    def test_timezone(self):
        """Test timezone is Los Angeles (PST)"""
        config = get_client_config()
        assert config.timezone == "America/Los_Angeles"


class TestClient009FAQ:
    """Tests for Client 009 FAQ knowledge base"""

    @pytest.fixture
    def faq_data(self):
        """Load FAQ JSON data"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_009" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            return json.load(f)

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_009" / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_has_client_id(self, faq_data):
        """Test FAQ has correct client ID"""
        assert faq_data["client_id"] == "client_009"

    def test_faq_has_entries(self, faq_data):
        """Test FAQ has at least 20 entries"""
        entries = faq_data.get("entries", [])
        assert len(entries) >= 20

    def test_faq_real_estate_specific(self, faq_data):
        """Test FAQ contains real estate content"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        real_estate_terms = ["property", "listing", "buy", "sell", "agent"]
        found_terms = [term for term in real_estate_terms if term in all_text]
        assert len(found_terms) >= 4


class TestClient009Isolation:
    """Tests for client isolation"""

    def test_client_id_unique(self):
        """Test client ID is unique from other clients"""
        config = get_client_config()
        assert config.client_id not in [
            "client_001", "client_002", "client_003",
            "client_004", "client_005", "client_006",
            "client_007", "client_008"
        ]

    def test_paddle_account_unique(self):
        """Test Paddle account ID is unique"""
        config = get_client_config()
        assert config.paddle_account_id == "acc_homefind009"
