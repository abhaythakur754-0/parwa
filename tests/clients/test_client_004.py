"""
Tests for Client 004 - FastFreight Logistics
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClientConfig:
    def test_config_module_imports(self):
        from clients.client_004 import config
        assert config is not None
    
    def test_config_loads_correctly(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.client_id == "client_004"
        assert cfg.client_name == "FastFreight Logistics"
        assert cfg.industry == "logistics"
    
    def test_variant_is_parwa_junior(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.variant == "parwa_junior"
    
    def test_business_hours_configured(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert "start" in cfg.business_hours
        assert cfg.business_hours["start"] == "06:00"
    
    def test_escalation_contacts_configured(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert "email" in cfg.escalation_contacts
    
    def test_feature_flags_configured(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.features.get("tracking_integration") is True
    
    def test_tracking_integration_configured(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.features.get("tracking_integration") is True
    
    def test_sla_configured(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.sla["first_response_minutes"] == 30


class TestFAQ:
    def test_faq_file_exists(self):
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_004" / "knowledge_base" / "faq.json"
        assert faq_path.exists()
    
    def test_faq_loads_correctly(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_004" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        assert "faqs" in faq_data
        assert len(faq_data["faqs"]) >= 25
    
    def test_faq_entries_have_required_fields(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_004" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        for faq in faq_data["faqs"]:
            assert "id" in faq
            assert "question" in faq
            assert "answer" in faq
    
    def test_faq_categories(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_004" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        categories = {faq["category"] for faq in faq_data["faqs"]}
        assert len(categories) >= 3
    
    def test_tracking_number_format_in_faq(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_004" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        tracking_faqs = [f for f in faq_data["faqs"] if "track" in f["question"].lower()]
        assert len(tracking_faqs) >= 2


class TestIndustrySpecific:
    def test_logistics_specific_config(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        assert cfg.features.get("shipment_apis") is True
    
    def test_business_hours_extended(self):
        from clients.client_004.config import get_client_config
        cfg = get_client_config()
        start = int(cfg.business_hours["start"].split(":")[0])
        end = int(cfg.business_hours["end"].split(":")[0])
        assert start <= 6
        assert end >= 22
