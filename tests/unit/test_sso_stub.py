"""
Unit Tests for SSO Stub Module.

Tests for SAML 2.0 SSO stub implementation including:
- SAML placeholder generation
- SP metadata generation
- SCIM provisioning stubs
"""

import pytest
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

from backend.sso.sso_provider import (
    SSOProvider,
    SAMLAssertion,
    get_sso_provider_for_tenant
)
from backend.sso.sp_metadata import (
    SPMetadataGenerator,
    generate_sp_metadata_for_tenant
)
from backend.sso.scim_stub import (
    SCIMStub,
    SCIMUser,
    SCIMGroup,
    get_scim_stub_for_tenant
)


class TestSSOProvider:
    """Tests for SSOProvider class."""
    
    def test_sso_provider_initialization(self):
        """Test SSO provider initializes correctly."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test-tenant",
            acs_url="https://api.parwa.ai/sso/acs/test-tenant"
        )
        
        assert provider.entity_id == "https://parwa.ai/sp/test-tenant"
        assert provider.acs_url == "https://api.parwa.ai/sso/acs/test-tenant"
        assert provider.issuer == "PARWA"
    
    def test_generate_saml_request(self):
        """Test SAML request generation."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        request = provider.generate_saml_request()
        
        assert request is not None
        assert isinstance(request, str)
        # Should be base64 encoded
        import base64
        decoded = base64.b64decode(request).decode()
        assert "AuthnRequest" in decoded
        assert "https://api.parwa.ai/sso/acs/test" in decoded
    
    def test_generate_saml_placeholder(self):
        """Test SAML placeholder generation - CRITICAL TEST."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        placeholder = provider.generate_saml_placeholder("test@example.com")
        
        # CRITICAL: Verify correct SAML placeholder
        assert placeholder is not None
        assert isinstance(placeholder, SAMLAssertion)
        assert placeholder.name_id == "test@example.com"
        assert placeholder.issuer == "PARWA"
        assert placeholder.audience == "https://parwa.ai/sp/test"
        
        # Verify XML output
        xml = placeholder.to_xml()
        assert "Assertion" in xml
        assert "test@example.com" in xml
        assert "urn:oasis:names:tc:SAML:2.0:assertion" in xml
    
    def test_saml_assertion_attributes(self):
        """Test SAML assertion includes required attributes."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        assertion = provider.generate_saml_placeholder("user@example.com")
        
        # Check attributes
        assert "email" in assertion.attributes
        assert assertion.attributes["email"] == "user@example.com"
        assert "firstName" in assertion.attributes
        assert "lastName" in assertion.attributes
        assert "role" in assertion.attributes
    
    def test_create_session(self):
        """Test SSO session creation."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        session_id = provider.create_session(
            email="user@example.com",
            tenant_id="tenant-123",
            attributes={"role": "admin"}
        )
        
        assert session_id is not None
        assert isinstance(session_id, str)
        
        # Verify session can be retrieved
        session = provider.get_session(session_id)
        assert session is not None
        assert session["email"] == "user@example.com"
        assert session["tenant_id"] == "tenant-123"
    
    def test_session_expiration(self):
        """Test SSO session expiration."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        session_id = provider.create_session(
            email="user@example.com",
            tenant_id="tenant-123"
        )
        
        # Session should exist
        assert provider.get_session(session_id) is not None
        
        # Invalidate session
        result = provider.invalidate_session(session_id)
        assert result is True
        
        # Session should no longer exist
        assert provider.get_session(session_id) is None
    
    def test_jit_provision_user(self):
        """Test JIT user provisioning."""
        provider = SSOProvider(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        result = provider.jit_provision_user(
            email="newuser@example.com",
            tenant_id="tenant-123",
            attributes={"firstName": "New", "lastName": "User"}
        )
        
        assert result["provisioned"] is True
        assert result["email"] == "newuser@example.com"
        assert result["user_id"] is not None
    
    def test_get_sso_provider_for_tenant(self):
        """Test factory function for tenant SSO provider."""
        provider = get_sso_provider_for_tenant("tenant-123")
        
        assert provider is not None
        assert "tenant-123" in provider.entity_id
        assert "tenant-123" in provider.acs_url


class TestSPMetadataGenerator:
    """Tests for SP Metadata Generator."""
    
    def test_generate_metadata(self):
        """Test SP metadata generation."""
        generator = SPMetadataGenerator(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        metadata = generator.generate()
        
        assert metadata is not None
        assert '<?xml version="1.0"' in metadata
        assert "EntityDescriptor" in metadata
        assert "https://parwa.ai/sp/test" in metadata
        assert "AssertionConsumerService" in metadata
    
    def test_metadata_valid_xml(self):
        """Test that generated metadata is valid XML."""
        generator = SPMetadataGenerator(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        metadata = generator.generate()
        
        # Should parse without error
        root = ET.fromstring(metadata)
        assert root is not None
    
    def test_validate_for_okta(self):
        """Test metadata validation for Okta."""
        generator = SPMetadataGenerator(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        assert generator.validate_for_okta() is True
    
    def test_validate_for_azure_ad(self):
        """Test metadata validation for Azure AD."""
        generator = SPMetadataGenerator(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test"
        )
        
        assert generator.validate_for_azure_ad() is True
    
    def test_metadata_with_slo(self):
        """Test metadata includes SLO URL when provided."""
        generator = SPMetadataGenerator(
            entity_id="https://parwa.ai/sp/test",
            acs_url="https://api.parwa.ai/sso/acs/test",
            slo_url="https://api.parwa.ai/sso/slo/test"
        )
        
        metadata = generator.generate()
        
        assert "SingleLogoutService" in metadata
        assert "https://api.parwa.ai/sso/slo/test" in metadata
    
    def test_generate_sp_metadata_for_tenant(self):
        """Test convenience function for tenant metadata."""
        metadata = generate_sp_metadata_for_tenant("tenant-123")
        
        assert metadata is not None
        assert "tenant-123" in metadata
        assert "EntityDescriptor" in metadata


class TestSCIMStub:
    """Tests for SCIM stub implementation."""
    
    def test_create_user(self):
        """Test SCIM user creation."""
        scim = SCIMStub("tenant-123")
        
        user = scim.create_user({
            "userName": "test@example.com",
            "name": {"givenName": "Test", "familyName": "User"},
            "emails": [{"value": "test@example.com", "primary": "true"}]
        })
        
        assert user is not None
        assert user["userName"] == "test@example.com"
        assert "schemas" in user
        assert "urn:ietf:params:scim:schemas:core:2.0:User" in user["schemas"]
    
    def test_get_user(self):
        """Test getting a SCIM user."""
        scim = SCIMStub("tenant-123")
        
        created = scim.create_user({
            "userName": "test@example.com"
        })
        
        user = scim.get_user(created["id"])
        
        assert user is not None
        assert user["userName"] == "test@example.com"
    
    def test_update_user(self):
        """Test updating a SCIM user."""
        scim = SCIMStub("tenant-123")
        
        created = scim.create_user({
            "userName": "test@example.com",
            "active": True
        })
        
        updated = scim.update_user(created["id"], {
            "active": False
        })
        
        assert updated is not None
        assert updated["active"] is False
    
    def test_delete_user(self):
        """Test deleting a SCIM user (deprovisioning)."""
        scim = SCIMStub("tenant-123")
        
        created = scim.create_user({
            "userName": "test@example.com"
        })
        
        result = scim.delete_user(created["id"])
        assert result is True
        
        # User should no longer exist
        user = scim.get_user(created["id"])
        assert user is None
    
    def test_list_users(self):
        """Test listing SCIM users."""
        scim = SCIMStub("tenant-123")
        
        # Create multiple users
        for i in range(5):
            scim.create_user({
                "userName": f"user{i}@example.com"
            })
        
        result = scim.list_users()
        
        assert result["totalResults"] == 5
        assert len(result["Resources"]) == 5
    
    def test_create_group(self):
        """Test SCIM group creation."""
        scim = SCIMStub("tenant-123")
        
        group = scim.create_group({
            "displayName": "Admins",
            "members": []
        })
        
        assert group is not None
        assert group["displayName"] == "Admins"
        assert "schemas" in group
    
    def test_service_provider_config(self):
        """Test getting service provider config."""
        scim = SCIMStub("tenant-123")
        
        config = scim.get_service_provider_config()
        
        assert config is not None
        assert "schemas" in config
        assert config["patch"]["supported"] is True
        assert config["filter"]["supported"] is True
    
    def test_resource_types(self):
        """Test getting resource types."""
        scim = SCIMStub("tenant-123")
        
        types = scim.get_resource_types()
        
        assert types["totalResults"] == 2
        resource_ids = [r["id"] for r in types["Resources"]]
        assert "User" in resource_ids
        assert "Group" in resource_ids
    
    def test_get_scim_stub_for_tenant(self):
        """Test factory function for tenant SCIM stub."""
        scim = get_scim_stub_for_tenant("tenant-123")
        
        assert scim is not None
        assert scim.tenant_id == "tenant-123"


class TestSAMLAssertion:
    """Tests for SAMLAssertion model."""
    
    def test_saml_assertion_creation(self):
        """Test creating a SAML assertion."""
        assertion = SAMLAssertion(
            issuer="PARWA",
            audience="https://parwa.ai/sp/test",
            subject="user@example.com",
            name_id="user@example.com"
        )
        
        assert assertion.issuer == "PARWA"
        assert assertion.audience == "https://parwa.ai/sp/test"
        assert assertion.name_id == "user@example.com"
    
    def test_saml_assertion_to_xml(self):
        """Test converting SAML assertion to XML."""
        assertion = SAMLAssertion(
            issuer="PARWA",
            audience="https://parwa.ai/sp/test",
            subject="user@example.com",
            name_id="user@example.com",
            attributes={"email": "user@example.com", "role": "admin"}
        )
        
        xml = assertion.to_xml()
        
        assert xml is not None
        assert "Assertion" in xml
        assert "PARWA" in xml
        assert "user@example.com" in xml
        assert "Attribute" in xml
    
    def test_saml_assertion_defaults(self):
        """Test SAML assertion default values."""
        assertion = SAMLAssertion(
            issuer="PARWA",
            audience="https://parwa.ai/sp/test",
            subject="user@example.com",
            name_id="user@example.com"
        )
        
        # Check defaults
        assert assertion.name_id_format == "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        assert assertion.issue_instant is not None
        assert assertion.not_on_or_after > assertion.issue_instant
