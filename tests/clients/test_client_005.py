"""
Tests for Client 005 - PayFlow FinTech
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestClientConfig:
    def test_config_module_imports(self):
        from clients.client_005 import config
        assert config is not None
    
    def test_config_loads_correctly(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.client_id == "client_005"
        assert cfg.client_name == "PayFlow FinTech"
        assert cfg.industry == "fintech"
    
    def test_variant_is_parwa_high(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.variant == "parwa_high"
    
    def test_business_hours_configured(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert "start" in cfg.business_hours
    
    def test_emergency_24_7_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.business_hours.get("emergency_24_7") is True
    
    def test_escalation_contacts_configured(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert "email" in cfg.escalation_contacts
        assert "on_call" in cfg.escalation_contacts
    
    def test_feature_flags_configured(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert "payment_processing" in cfg.features
    
    def test_sla_configured(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.sla["first_response_minutes"] <= 15
    
    def test_tight_escalation_sla(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.sla["escalation_minutes"] <= 30


class TestCompliance:
    def test_pci_dss_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("pci_dss_enabled") is True
    
    def test_soc2_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("soc2_enabled") is True
    
    def test_gdpr_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("gdpr_enabled") is True
    
    def test_aml_kyc_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("aml_kyc_enabled") is True
    
    def test_encryption_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("encryption_at_rest") is True
    
    def test_data_retention_for_fintech(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.compliance.get("data_retention_years") >= 7


class TestFraudDetection:
    def test_fraud_detection_enabled(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.fraud_detection.get("enabled") is True
    
    def test_real_time_monitoring(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.fraud_detection.get("real_time_monitoring") is True
    
    def test_velocity_checks(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.fraud_detection.get("velocity_checks") is True
    
    def test_device_fingerprinting(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert cfg.fraud_detection.get("device_fingerprinting") is True
    
    def test_alert_threshold_configured(self):
        from clients.client_005.config import get_client_config
        cfg = get_client_config()
        assert "alert_threshold" in cfg.fraud_detection


class TestFAQ:
    def test_faq_file_exists(self):
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        assert faq_path.exists()
    
    def test_faq_loads_correctly(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        assert "faqs" in faq_data
        assert len(faq_data["faqs"]) >= 25
    
    def test_faq_entries_have_required_fields(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        for faq in faq_data["faqs"]:
            assert "id" in faq
            assert "question" in faq
    
    def test_faq_categories(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        categories = {faq["category"] for faq in faq_data["faqs"]}
        expected = {"Payments", "Security", "Accounts", "Fees", "Transfers"}
        assert len(categories.intersection(expected)) >= 3
    
    def test_no_sensitive_data_in_faq(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        sensitive_patterns = ["my_password_is", "api_key=", "token=sk_", "credit_card_number", "ssn="]
        for faq in faq_data["faqs"]:
            content = (faq["question"] + " " + faq["answer"]).lower()
            for pattern in sensitive_patterns:
                assert pattern not in content
    
    def test_security_best_practices_in_faq(self):
        import json
        faq_path = Path(__file__).parent.parent.parent / "clients" / "client_005" / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            faq_data = json.load(f)
        security_faqs = [f for f in faq_data["faqs"] if f["category"] == "Security"]
        assert len(security_faqs) >= 2
