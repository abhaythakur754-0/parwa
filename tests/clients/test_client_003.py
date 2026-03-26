"""Tests for Client 003 configuration and HIPAA compliance"""

import pytest
import json
from pathlib import Path

CLIENT_DIR = Path(__file__).parent.parent.parent / "clients" / "client_003"


class TestClientConfig:
    """Tests for client 003 healthcare configuration"""

    def test_config_module_imports(self):
        """Test that config module can be imported"""
        from clients.client_003.config import ClientConfig, get_client_config
        assert ClientConfig is not None
        assert get_client_config is not None

    def test_config_loads_correctly(self):
        """Test that config loads with healthcare values"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.client_id == "client_003"
        assert config.client_name == "MediCare Health"
        assert config.industry == "healthcare"
        assert config.variant == "parwa_high"
        assert config.timezone == "America/New_York"

    def test_business_hours_24_7(self):
        """Test 24/7 business hours for healthcare"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.business_hours.is_24_7 is True

    def test_escalation_contacts_includes_emergency(self):
        """Test emergency escalation contacts"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.escalation_contacts.emergency_line is not None
        assert config.escalation_contacts.on_call_phone is not None

    def test_hipaa_config_enabled(self):
        """Test HIPAA configuration is enabled"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.compliance.hipaa.enabled is True
        assert config.compliance.hipaa.baa_signed is True
        assert config.compliance.hipaa.phi_handling_enabled is True

    def test_hipaa_data_retention(self):
        """Test HIPAA data retention is 7 years"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.compliance.hipaa.data_retention_years == 7

    def test_sla_faster_for_healthcare(self):
        """Test SLA is faster for healthcare"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.sla.first_response_hours == 1
        assert config.sla.emergency_response_minutes == 5

    def test_healthcare_features(self):
        """Test healthcare-specific features"""
        from clients.client_003.config import get_client_config
        config = get_client_config()
        
        assert config.feature_flags.telehealth_integration is True
        assert config.feature_flags.prescription_refill is True
        assert config.feature_flags.voice_support is True


class TestFAQ:
    """Tests for healthcare FAQ knowledge base"""

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
        assert len(data["entries"]) >= 30

    def test_healthcare_categories(self):
        """Test healthcare-specific categories"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        categories = {e["category"] for e in data["entries"]}
        required = {"Appointments", "Billing", "Insurance", "Prescriptions", "Medical Records", "Telehealth"}
        
        assert required.issubset(categories)

    def test_no_phi_in_faqs(self):
        """Test no PHI in FAQ content"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            content = f.read()
        
        # Should not contain SSN patterns
        import re
        ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
        assert not re.search(ssn_pattern, content), "FAQ contains potential SSN"

    def test_phi_warning_present(self):
        """Test PHI warning is present"""
        faq_path = CLIENT_DIR / "knowledge_base" / "faq.json"
        with open(faq_path) as f:
            data = json.load(f)
        
        assert "phi_warning" in data


class TestProducts:
    """Tests for healthcare services"""

    def test_products_file_exists(self):
        """Test products file exists"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        assert products_path.exists(), "Products file not found"

    def test_service_tiers_exist(self):
        """Test service tiers are defined"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        tiers = {s["tier"] for s in data.get("services", [])}
        required = {"basic", "premium", "vip"}
        
        assert required.issubset(tiers)

    def test_telehealth_services(self):
        """Test telehealth services are defined"""
        products_path = CLIENT_DIR / "knowledge_base" / "products.json"
        with open(products_path) as f:
            data = json.load(f)
        
        assert "telehealth_services" in data


class TestPolicies:
    """Tests for healthcare policies"""

    def test_policies_file_exists(self):
        """Test policies file exists"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        assert policies_path.exists(), "Policies file not found"

    def test_hipaa_policy_exists(self):
        """Test HIPAA policy is defined"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "hipaa_compliance" in data["policies"]

    def test_phi_handling_policy(self):
        """Test PHI handling policy exists"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "phi_handling" in data["policies"]

    def test_emergency_escalation_policy(self):
        """Test emergency escalation policy"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        assert "emergency_escalation" in data["policies"]

    def test_data_retention_7_years(self):
        """Test 7-year data retention"""
        policies_path = CLIENT_DIR / "knowledge_base" / "policies.json"
        with open(policies_path) as f:
            data = json.load(f)
        
        retention = data["policies"].get("data_retention", {})
        assert "7 years" in str(retention.get("medical_records", ""))


class TestHIPAACompliance:
    """Tests for HIPAA compliance module"""

    def test_hipaa_module_imports(self):
        """Test HIPAA module can be imported"""
        from clients.client_003.hipaa_compliance import HIPAACompliance, PHIHandler
        assert HIPAACompliance is not None
        assert PHIHandler is not None

    def test_phi_detection_ssn(self):
        """Test SSN detection"""
        from clients.client_003.hipaa_compliance import PHIHandler
        handler = PHIHandler()
        
        text = "Patient SSN: 123-45-6789"
        detected = handler.detect_phi(text)
        
        assert len(detected) > 0
        assert any(p.field_type == "SSN" for p in detected)

    def test_phi_sanitization(self):
        """Test PHI sanitization"""
        from clients.client_003.hipaa_compliance import PHIHandler
        handler = PHIHandler()
        
        text = "SSN: 123-45-6789, Phone: 555-123-4567"
        sanitized = handler.sanitize(text)
        
        assert "123-45-6789" not in sanitized
        assert "555-123-4567" not in sanitized
        assert "[REDACTED]" in sanitized or "REDACTED" in sanitized

    def test_audit_logging(self):
        """Test PHI access audit logging"""
        from clients.client_003.hipaa_compliance import HIPAACompliance
        compliance = HIPAACompliance()
        
        entry = compliance.log_phi_access(
            user_id="test_user",
            action="VIEW_RECORD",
            resource_type="patient_record",
            resource_id="patient_123",
            justification="Treatment purposes"
        )
        
        assert entry.user_id == "test_user"
        assert entry.phi_accessed is True

    def test_minimum_necessary_check(self):
        """Test minimum necessary principle"""
        from clients.client_003.hipaa_compliance import HIPAACompliance
        compliance = HIPAACompliance()
        
        # Support role should not access medical records
        allowed, _ = compliance.check_minimum_necessary(
            user_role="support",
            requested_data="medical_records",
            purpose="support ticket"
        )
        assert allowed is False
        
        # Provider role should access medical records
        allowed, _ = compliance.check_minimum_necessary(
            user_role="provider",
            requested_data="medical_records",
            purpose="treatment"
        )
        assert allowed is True

    def test_baa_verification(self):
        """Test BAA verification"""
        from clients.client_003.hipaa_compliance import HIPAACompliance
        compliance = HIPAACompliance()
        
        assert compliance.verify_baa() is True

    def test_message_phi_validation(self):
        """Test message PHI validation"""
        from clients.client_003.hipaa_compliance import HIPAACompliance
        compliance = HIPAACompliance()
        
        result = compliance.validate_message_for_phi("Patient John Doe called about appointment")
        assert isinstance(result, dict)
        assert "contains_phi" in result
        assert "sanitized_content" in result

    def test_emergency_access_logged(self):
        """Test emergency access is logged"""
        from clients.client_003.hipaa_compliance import HIPAACompliance
        compliance = HIPAACompliance()
        
        granted, message = compliance.emergency_access(
            user_id="dr_smith",
            patient_id="patient_123",
            reason="Patient unconscious, no ID available"
        )
        
        assert granted is True
        assert "reviewed" in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
