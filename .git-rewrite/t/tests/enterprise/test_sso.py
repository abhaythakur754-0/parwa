"""
Week 41 Builder 3 - Enterprise SSO Tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestSAMLHandler:
    """Test SAML handler"""

    def test_handler_exists(self):
        """Test SAML handler exists"""
        from enterprise.sso.saml_handler import SAMLHandler
        assert SAMLHandler is not None

    def test_generate_auth_request(self):
        """Test generating auth request"""
        from enterprise.sso.saml_handler import SAMLHandler, SAMLConfig

        config = SAMLConfig(
            entity_id="https://app.example.com",
            sso_url="https://idp.example.com/sso",
            slo_url="https://idp.example.com/slo",
            certificate="test_cert"
        )
        handler = SAMLHandler("test_client", config)
        request = handler.generate_auth_request("https://app.example.com/callback")

        assert request is not None
        assert len(request) > 0


class TestOAuthHandler:
    """Test OAuth handler"""

    def test_handler_exists(self):
        """Test OAuth handler exists"""
        from enterprise.sso.oauth_handler import OAuthHandler
        assert OAuthHandler is not None

    def test_get_authorization_url(self):
        """Test getting authorization URL"""
        from enterprise.sso.oauth_handler import OAuthHandler, OAuthConfig, OAuthProvider

        config = OAuthConfig(
            provider=OAuthProvider.GOOGLE,
            client_id="test_client_id",
            client_secret="test_secret",
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
            redirect_uri="https://app.example.com/callback"
        )
        handler = OAuthHandler("test_client", config)
        url = handler.get_authorization_url()

        assert "accounts.google.com" in url
        assert "client_id=test_client_id" in url


class TestLDAPConnector:
    """Test LDAP connector"""

    def test_connector_exists(self):
        """Test LDAP connector exists"""
        from enterprise.sso.ldap_connector import LDAPConnector
        assert LDAPConnector is not None

    def test_connect(self):
        """Test LDAP connection"""
        from enterprise.sso.ldap_connector import LDAPConnector, LDAPConfig, LDAPStatus

        config = LDAPConfig(
            server_url="ldap://ldap.example.com",
            base_dn="dc=example,dc=com",
            bind_dn="cn=admin,dc=example,dc=com",
            bind_password="password",
            user_search_base="ou=users,dc=example,dc=com"
        )
        connector = LDAPConnector("test_client", config)
        result = connector.connect()

        assert result is True
        assert connector.status == LDAPStatus.CONNECTED


class TestSessionManager:
    """Test session manager"""

    def test_manager_exists(self):
        """Test session manager exists"""
        from enterprise.sso.session_manager import SessionManager
        assert SessionManager is not None

    def test_create_session(self):
        """Test creating session"""
        from enterprise.sso.session_manager import SessionManager, SessionStatus

        manager = SessionManager("test_client")
        session = manager.create_session("user_001", "saml")

        assert session.status == SessionStatus.ACTIVE
        assert session.user_id == "user_001"

    def test_validate_session(self):
        """Test validating session"""
        from enterprise.sso.session_manager import SessionManager

        manager = SessionManager("test_client")
        session = manager.create_session("user_001", "oauth")
        validated = manager.validate_session(session.session_id)

        assert validated is not None
        assert validated.session_id == session.session_id


class TestUserProvisioner:
    """Test user provisioner"""

    def test_provisioner_exists(self):
        """Test provisioner exists"""
        from enterprise.sso.user_provisioner import UserProvisioner
        assert UserProvisioner is not None

    def test_provision_user(self):
        """Test provisioning user"""
        from enterprise.sso.user_provisioner import UserProvisioner

        provisioner = UserProvisioner("test_client")
        user = provisioner.provision_user(
            user_id="user_001",
            email="user@example.com",
            name="Test User"
        )

        assert user.user_id == "user_001"
        assert user.email == "user@example.com"
        assert user.active is True

    def test_sync_users(self):
        """Test syncing users"""
        from enterprise.sso.user_provisioner import UserProvisioner

        provisioner = UserProvisioner("test_client")
        results = provisioner.sync_users([
            {"user_id": "user_001", "email": "user1@example.com"},
            {"user_id": "user_002", "email": "user2@example.com"}
        ])

        assert results["created"] == 2
