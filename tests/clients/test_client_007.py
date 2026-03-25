"""Tests for Client 007 - EduLearn Academy"""

import pytest
import json
from pathlib import Path
from clients.client_007.config import get_client_config, ClientConfig


class TestClient007Config:
    """Tests for Client 007 configuration"""

    def test_config_loads_correctly(self):
        """Test that client 007 config loads without error"""
        config = get_client_config()
        assert config is not None
        assert isinstance(config, ClientConfig)

    def test_client_id(self):
        """Test client ID is correct"""
        config = get_client_config()
        assert config.client_id == "client_007"

    def test_client_name(self):
        """Test client name is correct"""
        config = get_client_config()
        assert config.client_name == "EduLearn Academy"

    def test_industry(self):
        """Test industry is education"""
        config = get_client_config()
        assert config.industry == "education"

    def test_variant(self):
        """Test variant is parwa_junior"""
        config = get_client_config()
        assert config.variant == "parwa_junior"

    def test_timezone(self):
        """Test timezone is New York (EST)"""
        config = get_client_config()
        assert config.timezone == "America/New_York"

    def test_business_hours(self):
        """Test business hours are extended for student support (8am-8pm)"""
        config = get_client_config()
        assert config.business_hours.start.hour == 8
        assert config.business_hours.end.hour == 20  # 8 PM
        assert config.business_hours.timezone == "America/New_York"

    def test_escalation_contacts(self):
        """Test escalation contacts are configured"""
        config = get_client_config()
        assert config.escalation_contacts.email == "support@edulearn-academy.edu"
        assert config.escalation_contacts.phone == "+1-555-0157"

    def test_feature_flags(self):
        """Test feature flags are set"""
        config = get_client_config()
        assert config.feature_flags.shadow_mode is True
        assert config.feature_flags.multi_language is True  # International students

    def test_sla_config(self):
        """Test SLA configuration - faster for students"""
        config = get_client_config()
        assert config.sla.first_response_hours == 2  # Faster response
        assert config.sla.resolution_hours == 24

    def test_compliance_ferpa(self):
        """Test FERPA compliance is enabled"""
        config = get_client_config()
        assert hasattr(config, 'compliance')
        assert config.compliance.ferpa_enabled is True

    def test_metadata(self):
        """Test metadata is populated"""
        config = get_client_config()
        assert config.metadata["website"] == "https://edulearn-academy.edu"
        assert "student_count" in config.metadata
        assert config.metadata["student_count"] == 15000

    def test_programs_offered(self):
        """Test programs are defined"""
        config = get_client_config()
        programs = config.metadata.get("programs", [])
        assert len(programs) > 0
        assert "Computer Science" in programs

    def test_features_enabled(self):
        """Test education-specific features"""
        config = get_client_config()
        features = config.metadata.get("features", {})
        assert features.get("live_classes") is True
        assert features.get("certificates") is True


class TestClient007FAQ:
    """Tests for Client 007 FAQ knowledge base"""

    @pytest.fixture
    def faq_data(self):
        """Load FAQ JSON data"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_007" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            return json.load(f)

    def test_faq_file_exists(self):
        """Test FAQ file exists"""
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_007" / "knowledge_base" / "faq.json"
        assert faq_path.exists()

    def test_faq_has_client_id(self, faq_data):
        """Test FAQ has correct client ID"""
        assert faq_data["client_id"] == "client_007"

    def test_faq_has_categories(self, faq_data):
        """Test FAQ has categories defined"""
        categories = faq_data.get("categories", [])
        assert len(categories) >= 5
        assert "Enrollment" in categories
        assert "Courses" in categories
        assert "Certificates" in categories

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

    def test_faq_education_specific_content(self, faq_data):
        """Test FAQ contains education-specific content"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        # Check for education-specific terms
        edu_terms = ["course", "student", "certificate", "enrollment"]
        found_terms = [term for term in edu_terms if term in all_text]
        assert len(found_terms) >= 3

    def test_faq_mentions_ferpa(self, faq_data):
        """Test FAQ mentions FERPA for student data protection"""
        entries = faq_data.get("entries", [])
        all_text = " ".join([
            entry["question"] + " " + entry["answer"]
            for entry in entries
        ]).lower()

        assert "ferpa" in all_text


class TestClient007Isolation:
    """Tests for client isolation"""

    def test_client_id_unique(self):
        """Test client ID is unique from other clients"""
        config = get_client_config()
        # Should not be client_001 through client_006
        assert config.client_id not in [
            "client_001", "client_002", "client_003",
            "client_004", "client_005", "client_006"
        ]

    def test_paddle_account_unique(self):
        """Test Paddle account ID is unique"""
        config = get_client_config()
        assert config.paddle_account_id == "acc_edulearn007"

    def test_no_cross_client_data(self):
        """Test config doesn't reference other clients"""
        config = get_client_config()
        config_str = json.dumps({
            "client_id": config.client_id,
            "client_name": config.client_name,
            "metadata": config.metadata
        })
        # Should not contain other client names
        other_clients = ["Acme", "TechFlow", "MediCare", "FastShip", "SecureBank", "ShopMax"]
        for client in other_clients:
            assert client not in config_str

    def test_ferpa_compliance_enabled(self):
        """Test FERPA compliance is strictly enabled"""
        config = get_client_config()
        assert config.compliance.ferpa_enabled is True
