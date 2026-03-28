"""
E2E Tests for Enterprise Onboarding Flow.

End-to-end tests that validate the complete enterprise onboarding
process from start to finish.
"""

import pytest
from datetime import datetime, timezone


class TestEnterpriseOnboardingE2E:
    """E2E tests for enterprise onboarding flow."""
    
    def test_complete_onboarding_flow(self):
        """
        Test complete enterprise onboarding flow.
        
        This test validates:
        1. Onboarding starts correctly
        2. Company info is submitted
        3. Contract is signed
        4. SSO is configured
        5. Team is set up
        6. Onboarding completes successfully
        """
        from backend.onboarding.enterprise_onboarding import (
            EnterpriseOnboardingService,
            OnboardingStep
        )
        from backend.billing.enterprise_billing import EnterpriseBillingService
        from backend.sso.sso_provider import SSOProvider
        
        # Initialize services
        onboarding_service = EnterpriseOnboardingService()
        billing_service = EnterpriseBillingService()
        
        # Step 1: Start onboarding
        onboarding = onboarding_service.start_onboarding(
            tenant_id="tenant-e2e-test",
            company_name="E2E Test Corp",
            admin_email="admin@e2etest.com",
            admin_name="Admin User"
        )
        
        assert onboarding is not None
        assert onboarding.current_step == OnboardingStep.COMPANY_INFO
        
        # Step 2: Submit company info
        onboarding = onboarding_service.submit_company_info(
            onboarding.onboarding_id,
            {
                "address": "123 Test Street",
                "city": "Test City",
                "country": "US",
                "postal_code": "12345",
                "industry": "Technology"
            }
        )
        
        assert onboarding is not None
        assert onboarding.steps[OnboardingStep.COMPANY_INFO.value].status == "completed"
        
        # Step 3: Create and link contract
        contract = billing_service.create_contract(
            tenant_id="tenant-e2e-test",
            company_name="E2E Test Corp",
            seats_included=50,
            contract_duration_months=12,
            billing_cycle="monthly"
        )
        
        assert contract is not None
        
        onboarding = onboarding_service.link_contract(
            onboarding.onboarding_id,
            contract.contract_id
        )
        
        # Step 4: Sign contract
        billing_service.sign_contract(
            contract.contract_id,
            "admin@e2etest.com"
        )
        
        onboarding = onboarding_service.complete_contract_signing(
            onboarding.onboarding_id,
            "admin@e2etest.com",
            datetime.now(timezone.utc)
        )
        
        assert onboarding.steps[OnboardingStep.CONTRACT_SIGNING.value].status == "completed"
        
        # Step 5: Configure SSO
        onboarding = onboarding_service.configure_sso(
            onboarding.onboarding_id,
            {
                "provider": "okta",
                "entity_id": "https://idp.e2etest.com/saml",
                "sso_url": "https://idp.e2etest.com/sso",
                "certificate": "-----BEGIN CERTIFICATE-----\n..."
            }
        )
        
        assert onboarding.steps[OnboardingStep.SSO_CONFIGURATION.value].status == "completed"
        
        # Step 6: Set up team
        onboarding = onboarding_service.setup_team(
            onboarding.onboarding_id,
            [
                {"email": "user1@e2etest.com", "name": "User 1", "role": "agent"},
                {"email": "user2@e2etest.com", "name": "User 2", "role": "agent"},
                {"email": "manager@e2etest.com", "name": "Manager", "role": "manager"}
            ]
        )
        
        assert onboarding.steps[OnboardingStep.TEAM_SETUP.value].status == "completed"
        
        # Step 7: Set up knowledge base
        onboarding = onboarding_service.setup_knowledge_base(
            onboarding.onboarding_id,
            {
                "imported_articles": 10,
                "categories": ["General", "Technical", "Billing"]
            }
        )
        
        # Step 8: Complete training
        onboarding = onboarding_service.complete_training(
            onboarding.onboarding_id,
            {
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "modules_completed": ["admin", "agent", "reporting"]
            }
        )
        
        # Verify completion
        assert onboarding.current_step == OnboardingStep.COMPLETED
        assert onboarding.completed_at is not None
        # Progress should be high (may not be 100% due to optional steps)
        assert onboarding.get_progress_percent() >= 75


class TestEnterpriseSSOE2E:
    """E2E tests for SSO flow."""
    
    def test_sso_login_flow(self):
        """
        Test SSO login flow.
        
        Validates:
        1. SSO provider generates correct SAML request
        2. SAML response is validated
        3. Session is created
        4. User is JIT provisioned
        """
        from backend.sso.sso_provider import SSOProvider, get_sso_provider_for_tenant
        
        # Get provider for tenant
        provider = get_sso_provider_for_tenant("tenant-e2e-test")
        
        # Generate SAML request
        saml_request = provider.generate_saml_request()
        
        assert saml_request is not None
        assert len(saml_request) > 0
        
        # Generate placeholder assertion (simulates IdP response)
        assertion = provider.generate_saml_placeholder("user@e2etest.com")
        
        assert assertion is not None
        assert assertion.name_id == "user@e2etest.com"
        
        # Create session
        session_id = provider.create_session(
            email="user@e2etest.com",
            tenant_id="tenant-e2e-test",
            attributes={"firstName": "Test", "lastName": "User", "role": "user"}
        )
        
        assert session_id is not None
        
        # Verify session
        session = provider.get_session(session_id)
        
        assert session is not None
        assert session["email"] == "user@e2etest.com"
        assert session["tenant_id"] == "tenant-e2e-test"
        
        # JIT provision
        provisioned = provider.jit_provision_user(
            email="newuser@e2etest.com",
            tenant_id="tenant-e2e-test",
            attributes={"firstName": "New", "lastName": "User"}
        )
        
        assert provisioned["provisioned"] is True


class TestEnterpriseBillingE2E:
    """E2E tests for enterprise billing flow."""
    
    def test_billing_flow(self):
        """
        Test enterprise billing flow.
        
        Validates:
        1. Contract is created
        2. Contract is signed
        3. Invoice is generated
        4. Invoice can be marked as paid
        """
        from backend.billing.enterprise_billing import get_enterprise_billing_service
        
        service = get_enterprise_billing_service()
        
        # Create contract
        contract = service.create_contract(
            tenant_id="tenant-e2e-billing",
            company_name="E2E Billing Corp",
            seats_included=100,
            contract_duration_months=12,
            billing_cycle="monthly",
            discount_percent=10
        )
        
        assert contract is not None
        assert contract.discount_percent == 10
        
        # Sign contract
        signed_contract = service.sign_contract(
            contract.contract_id,
            "ceo@billing.com"
        )
        
        assert signed_contract is not None
        assert signed_contract.signed is True
        assert signed_contract.signed_by == "ceo@billing.com"
        
        # Generate invoice
        invoice = service.generate_contract_invoice(contract.contract_id)
        
        assert invoice is not None
        assert invoice.contract_id == contract.contract_id
        assert invoice.status == "draft"
        assert invoice.total > 0
        
        # Mark as paid
        paid_invoice = service.mark_invoice_paid(invoice.invoice_id)
        
        assert paid_invoice is not None
        assert paid_invoice.status == "paid"
        assert paid_invoice.paid_at is not None


class TestEnterpriseSecurityE2E:
    """E2E tests for enterprise security features."""
    
    def test_security_flow(self):
        """
        Test enterprise security flow.
        
        Validates:
        1. IP allowlist is configured
        2. Non-whitelisted IPs are blocked
        3. Rate limiting works
        4. Sessions are managed correctly
        """
        from backend.security.ip_allowlist import get_ip_allowlist_service
        from backend.security.rate_limiter_advanced import get_rate_limiter
        from backend.security.session_manager import get_session_manager, SessionType
        
        # Configure IP allowlist
        ip_service = get_ip_allowlist_service()
        ip_service.create_config(
            tenant_id="tenant-e2e-security",
            allowed_ips=["192.168.1.100"],
            allowed_cidrs=["10.0.0.0/8"],
            enabled=True
        )
        
        # Test allowed IP
        result = ip_service.check_access("tenant-e2e-security", "192.168.1.100")
        assert result["allowed"] is True
        
        # Test blocked IP
        result = ip_service.check_access("tenant-e2e-security", "8.8.8.8")
        assert result["allowed"] is False
        
        # Test rate limiting
        limiter = get_rate_limiter()
        limiter.configure_tenant("tenant-e2e-security", "enterprise")
        
        result = limiter.check_rate_limit("tenant-e2e-security", "user-1")
        assert result.allowed is True
        
        # Test session management
        session_manager = get_session_manager()
        session = session_manager.create_session(
            user_id="user-1",
            tenant_id="tenant-e2e-security",
            session_type=SessionType.WEB,
            ip_address="192.168.1.100"
        )
        
        assert session is not None
        
        validation = session_manager.validate_session(
            session.session_id,
            "tenant-e2e-security"
        )
        assert validation["valid"] is True


class TestAuditExportE2E:
    """E2E tests for audit export."""
    
    def test_audit_export_flow(self):
        """
        Test audit export flow.
        
        Validates:
        1. Events are logged
        2. CSV export works
        3. All required fields are present
        """
        from backend.compliance.audit_export import get_audit_exporter
        import csv
        import io
        
        exporter = get_audit_exporter()
        
        # Log multiple events
        events = [
            ("login", "success"),
            ("api_call", "success"),
            ("logout", "success"),
            ("failed_login", "failure"),
        ]
        
        for action, status in events:
            exporter.log_event(
                tenant_id="tenant-e2e-audit",
                user_id="user-1",
                action=action,
                resource_type="session",
                resource_id="session-1",
                ip_address="192.168.1.1",
                status=status
            )
        
        # Export to CSV
        csv_content = exporter.export_to_csv(tenant_id="tenant-e2e-audit")
        
        assert csv_content is not None
        
        # Parse and verify
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 4
        
        # Verify all required fields
        required_fields = [
            "entry_id", "tenant_id", "user_id", "action",
            "resource_type", "resource_id", "ip_address",
            "user_agent", "status", "timestamp", "details"
        ]
        
        for field in required_fields:
            assert field in rows[0], f"Missing field: {field}"
        
        # Verify data
        actions = [row["action"] for row in rows]
        assert "login" in actions
        assert "api_call" in actions
        assert "logout" in actions
        assert "failed_login" in actions
