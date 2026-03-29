"""
Unit Tests for Enterprise Compliance Module.

Tests for enterprise compliance features including:
- DPA compliance
- SLA monitoring
- Audit log export
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestEnterpriseDPA:
    """Tests for Enterprise Data Processing Agreement compliance."""
    
    def test_dpa_required_sections_present(self):
        """Test that DPA document has all required sections."""
        required_sections = [
            "PARTIES",
            "DEFINITIONS",
            "SCOPE AND PURPOSE",
            "DETAILS OF PROCESSING",
            "OBLIGATIONS OF THE PARTIES",
            "SECURITY MEASURES",
            "SUB-PROCESSORS",
            "DATA SUBJECT RIGHTS",
            "SECURITY INCIDENT NOTIFICATION",
            "DATA RETENTION AND DELETION",
            "AUDIT RIGHTS"
        ]
        
        # Read DPA document
        with open("legal/enterprise_data_processing_agreement.md", "r") as f:
            content = f.read()
        
        # Check each required section is present
        for section in required_sections:
            assert section.upper() in content.upper(), f"Missing required DPA section: {section}"
    
    def test_dpa_gdpr_compliance(self):
        """Test that DPA includes GDPR-specific clauses."""
        with open("legal/enterprise_data_processing_agreement.md", "r") as f:
            content = f.read()
        
        # Check for GDPR references (at least 5 of these should be present)
        gdpr_terms = [
            "GDPR",
            "Data Controller",
            "Data Processor",
            "Data Subject",
            "Personal Data"
        ]
        
        found_count = sum(1 for term in gdpr_terms if term in content)
        assert found_count >= 4, f"Should have at least 4 GDPR terms, found {found_count}"
    
    def test_dpa_sub_processor_list(self):
        """Test that DPA includes sub-processor list."""
        with open("legal/enterprise_data_processing_agreement.md", "r") as f:
            content = f.read()
        
        # Check for sub-processor section
        assert "SUB-PROCESSORS" in content.upper()
        
        # Check for key sub-processors
        assert "Amazon Web Services" in content or "AWS" in content


class TestEnterpriseSLA:
    """Tests for Enterprise SLA compliance."""
    
    def test_sla_required_sections_present(self):
        """Test that SLA document has all required sections."""
        required_sections = [
            "SERVICE AVAILABILITY",
            "UPTIME",
            "RESPONSE TIME",
            "SUPPORT",
            "SECURITY",
            "DATA BACKUP",
            "SERVICE CREDITS"
        ]
        
        with open("legal/enterprise_sla.md", "r") as f:
            content = f.read()
        
        for section in required_sections:
            assert section.upper() in content.upper(), f"Missing required SLA section: {section}"
    
    def test_sla_uptime_commitment(self):
        """Test that SLA specifies uptime commitment."""
        with open("legal/enterprise_sla.md", "r") as f:
            content = f.read()
        
        # Check for 99.9% uptime commitment
        assert "99.9%" in content or "99.95%" in content, "SLA should specify uptime percentage"
    
    def test_sla_response_times(self):
        """Test that SLA specifies support response times."""
        with open("legal/enterprise_sla.md", "r") as f:
            content = f.read()
        
        # Check for response time specifications
        response_terms = ["response time", "response", "minutes", "hours"]
        found = any(term in content.lower() for term in response_terms)
        assert found, "SLA should specify response times"


class TestEnterpriseSecurityGuide:
    """Tests for Enterprise Security Guide."""
    
    def test_security_guide_sections(self):
        """Test that security guide has required sections."""
        required_sections = [
            "SECURITY ARCHITECTURE",
            "DATA PROTECTION",
            "ACCESS CONTROL",
            "NETWORK SECURITY",
            "ENCRYPTION",
            "INCIDENT RESPONSE"
        ]
        
        with open("docs/enterprise_security_guide.md", "r") as f:
            content = f.read()
        
        for section in required_sections:
            assert section.upper() in content.upper(), f"Missing security section: {section}"
    
    def test_encryption_standards(self):
        """Test that security guide specifies encryption standards."""
        with open("docs/enterprise_security_guide.md", "r") as f:
            content = f.read()
        
        # Check for encryption standards
        assert "AES-256" in content or "AES 256" in content, "Should specify AES-256 encryption"
        assert "TLS" in content, "Should specify TLS for transit encryption"
    
    def test_compliance_certifications(self):
        """Test that security guide lists compliance certifications."""
        with open("docs/enterprise_security_guide.md", "r") as f:
            content = f.read()
        
        # Check for compliance mentions
        compliance_terms = ["SOC 2", "GDPR", "HIPAA"]
        found_count = sum(1 for term in compliance_terms if term in content)
        assert found_count >= 2, "Should list at least 2 compliance certifications"


class TestEnterpriseOnboardingGuide:
    """Tests for Enterprise Onboarding Guide."""
    
    def test_onboarding_guide_sections(self):
        """Test that onboarding guide has required sections."""
        required_sections = [
            "SSO CONFIGURATION",
            "TEAM SETUP",
            "KNOWLEDGE BASE",
            "INTEGRATION",
            "TRAINING"
        ]
        
        with open("docs/enterprise_onboarding_guide.md", "r") as f:
            content = f.read()
        
        for section in required_sections:
            assert section.upper() in content.upper(), f"Missing onboarding section: {section}"
    
    def test_sso_configuration_steps(self):
        """Test that SSO configuration steps are detailed."""
        with open("docs/enterprise_onboarding_guide.md", "r") as f:
            content = f.read()
        
        # Check for IdP mentions
        idp_terms = ["Okta", "Azure AD", "SAML"]
        found_count = sum(1 for term in idp_terms if term in content)
        assert found_count >= 2, "Should document at least 2 IdP configurations"
    
    def test_support_contact_info(self):
        """Test that support contact information is provided."""
        with open("docs/enterprise_onboarding_guide.md", "r") as f:
            content = f.read()
        
        # Check for support info
        assert "support@parwa.ai" in content.lower() or "support" in content.lower(), \
            "Should include support contact information"


class TestComplianceIntegration:
    """Integration tests for compliance features."""
    
    def test_all_enterprise_docs_exist(self):
        """Test that all required enterprise documents exist."""
        import os
        
        required_files = [
            "legal/enterprise_data_processing_agreement.md",
            "legal/enterprise_sla.md",
            "docs/enterprise_security_guide.md",
            "docs/enterprise_onboarding_guide.md"
        ]
        
        for filepath in required_files:
            assert os.path.exists(filepath), f"Missing required file: {filepath}"
    
    def test_document_version_control(self):
        """Test that documents include version information."""
        docs = [
            "legal/enterprise_data_processing_agreement.md",
            "legal/enterprise_sla.md",
            "docs/enterprise_security_guide.md",
            "docs/enterprise_onboarding_guide.md"
        ]
        
        for doc in docs:
            with open(doc, "r") as f:
                content = f.read()
            
            # Check for version info
            assert "Version" in content or "version" in content or "v2" in content.lower(), \
                f"Document should include version: {doc}"
