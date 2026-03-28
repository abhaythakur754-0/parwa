"""
Integration Tests for Enterprise Security Features.

Tests for enterprise security integration including:
- SSO integration
- IP allowlisting
- Rate limiting
- API key management
"""

import pytest
from datetime import datetime, timezone, timedelta


class TestEnterpriseSSOIntegration:
    """Integration tests for SSO functionality."""
    
    def test_sso_provider_initialization(self):
        """Test SSO provider initializes correctly."""
        from backend.sso.sso_provider import SSOProvider
        
        provider = SSOProvider(
            entity_id="https://test.parwa.ai/sp/test",
            acs_url="https://test.parwa.ai/sso/acs/test"
        )
        
        assert provider is not None
        assert provider.entity_id == "https://test.parwa.ai/sp/test"
        assert provider.acs_url == "https://test.parwa.ai/sso/acs/test"
    
    def test_saml_placeholder_generation(self):
        """Test SAML placeholder generation."""
        from backend.sso.sso_provider import SSOProvider
        
        provider = SSOProvider(
            entity_id="https://test.parwa.ai/sp/test",
            acs_url="https://test.parwa.ai/sso/acs/test"
        )
        
        assertion = provider.generate_saml_placeholder("user@test.com")
        
        assert assertion is not None
        assert assertion.name_id == "user@test.com"
        
        xml = assertion.to_xml()
        assert "Assertion" in xml
        assert "user@test.com" in xml
    
    def test_sp_metadata_generation(self):
        """Test SP metadata generation."""
        from backend.sso.sp_metadata import SPMetadataGenerator
        
        generator = SPMetadataGenerator(
            entity_id="https://test.parwa.ai/sp/test",
            acs_url="https://test.parwa.ai/sso/acs/test"
        )
        
        metadata = generator.generate()
        
        assert metadata is not None
        assert "EntityDescriptor" in metadata
        assert "https://test.parwa.ai/sp/test" in metadata
        assert generator.validate_for_okta() is True
    
    def test_scim_user_provisioning(self):
        """Test SCIM user provisioning."""
        from backend.sso.scim_stub import SCIMStub
        
        scim = SCIMStub("tenant-123")
        
        # Create user
        user = scim.create_user({
            "userName": "test@example.com",
            "name": {"givenName": "Test", "familyName": "User"}
        })
        
        assert user is not None
        assert user["userName"] == "test@example.com"
        
        # Get user
        retrieved = scim.get_user(user["id"])
        assert retrieved is not None
        
        # Delete user
        assert scim.delete_user(user["id"]) is True


class TestEnterpriseSecurityIntegration:
    """Integration tests for security features."""
    
    def test_ip_allowlist_integration(self):
        """Test IP allowlist integration."""
        from backend.security.ip_allowlist import IPAllowlistService
        
        service = IPAllowlistService()
        
        # Create config
        config = service.create_config(
            tenant_id="tenant-123",
            allowed_ips=["192.168.1.100"],
            enabled=True
        )
        
        assert config is not None
        
        # Check allowed IP
        result = service.check_access("tenant-123", "192.168.1.100")
        assert result["allowed"] is True
        
        # Check blocked IP
        result = service.check_access("tenant-123", "10.0.0.1")
        assert result["allowed"] is False
    
    def test_rate_limiter_integration(self):
        """Test rate limiter integration."""
        from backend.security.rate_limiter_advanced import AdvancedRateLimiter
        
        limiter = AdvancedRateLimiter()
        
        # Configure tenant
        limiter.configure_tenant("tenant-123", "enterprise")
        
        # Check rate limit
        result = limiter.check_rate_limit("tenant-123", "user-1")
        
        assert result is not None
        assert result.allowed is True
    
    def test_session_manager_integration(self):
        """Test session manager integration."""
        from backend.security.session_manager import EnterpriseSessionManager, SessionType
        
        manager = EnterpriseSessionManager()
        
        # Create session
        session = manager.create_session(
            user_id="user-1",
            tenant_id="tenant-123",
            session_type=SessionType.WEB,
            ip_address="192.168.1.1"
        )
        
        assert session is not None
        assert session.user_id == "user-1"
        
        # Validate session
        result = manager.validate_session(session.session_id, "tenant-123")
        assert result["valid"] is True
    
    def test_api_key_manager_integration(self):
        """Test API key manager integration."""
        from backend.security.api_key_manager import APIKeyManager
        
        manager = APIKeyManager()
        
        # Create key
        key_result = manager.create_key(
            tenant_id="tenant-123",
            user_id="user-1",
            name="Test Key",
            scopes=["read", "write"]
        )
        
        assert key_result is not None
        assert "key" in key_result
        
        # Validate key
        validation = manager.validate_key(key_result["key"])
        assert validation["valid"] is True


class TestEnterpriseBillingIntegration:
    """Integration tests for enterprise billing."""
    
    def test_contract_creation(self):
        """Test contract creation."""
        from backend.billing.enterprise_billing import EnterpriseBillingService
        
        service = EnterpriseBillingService()
        
        contract = service.create_contract(
            tenant_id="tenant-123",
            company_name="Test Corp",
            seats_included=50,
            contract_duration_months=12
        )
        
        assert contract is not None
        assert contract.tenant_id == "tenant-123"
        assert contract.seats_included == 50
    
    def test_invoice_generation(self):
        """Test invoice generation."""
        from backend.billing.enterprise_billing import EnterpriseBillingService
        
        service = EnterpriseBillingService()
        
        # Create contract first
        contract = service.create_contract(
            tenant_id="tenant-123",
            company_name="Test Corp",
            seats_included=50
        )
        
        # Generate invoice
        invoice = service.generate_contract_invoice(contract.contract_id)
        
        assert invoice is not None
        assert invoice.contract_id == contract.contract_id
        assert invoice.total > 0


class TestEnterpriseOnboardingIntegration:
    """Integration tests for enterprise onboarding."""
    
    def test_onboarding_flow(self):
        """Test complete onboarding flow."""
        from backend.onboarding.enterprise_onboarding import (
            EnterpriseOnboardingService,
            OnboardingStep
        )
        
        service = EnterpriseOnboardingService()
        
        # Start onboarding
        onboarding = service.start_onboarding(
            tenant_id="tenant-123",
            company_name="Test Corp",
            admin_email="admin@test.com",
            admin_name="Admin User"
        )
        
        assert onboarding is not None
        assert onboarding.tenant_id == "tenant-123"
        
        # Complete steps
        service.submit_company_info(
            onboarding.onboarding_id,
            {"address": "123 Test St", "country": "US"}
        )
        
        service.complete_contract_signing(
            onboarding.onboarding_id,
            "admin@test.com",
            datetime.now(timezone.utc)
        )
        
        # Check progress
        checklist = service.get_onboarding_checklist(onboarding.onboarding_id)
        assert len(checklist) > 0


class TestAuditExportIntegration:
    """Integration tests for audit export."""
    
    def test_audit_logging_and_export(self):
        """Test audit logging and CSV export."""
        from backend.compliance.audit_export import AuditExporter
        
        exporter = AuditExporter()
        
        # Log events
        for i in range(5):
            exporter.log_event(
                tenant_id="tenant-123",
                user_id=f"user-{i}",
                action="login",
                resource_type="session",
                resource_id=f"session-{i}",
                ip_address="192.168.1.1",
                status="success"
            )
        
        # Export to CSV
        csv_content = exporter.export_to_csv(tenant_id="tenant-123")
        
        assert csv_content is not None
        assert len(csv_content) > 0
        
        # Check required fields
        import csv
        import io
        
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 5
        required_fields = ["entry_id", "tenant_id", "user_id", "action", "ip_address", "status", "timestamp"]
        for field in required_fields:
            assert field in rows[0], f"Missing field: {field}"
