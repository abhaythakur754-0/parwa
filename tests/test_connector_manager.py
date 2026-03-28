"""
Week 58 - Builder 2 Tests: Integration Connectors Module
Unit tests for Connector Manager, OAuth Handler, and Connector Pool
"""

import pytest
import time
from parwa_integration_hub.connector_manager import (
    ConnectorManager, Connector, ConnectorConfig, ConnectorStatus,
    OAuthHandler, OAuthConfig, OAuthToken, ConnectorPool, AuthType
)


class TestConnector:
    """Tests for Connector class"""

    @pytest.fixture
    def connector_config(self):
        """Create test connector config"""
        return ConnectorConfig(
            name="test-connector",
            connector_type="rest",
            base_url="https://api.example.com",
            auth_type=AuthType.API_KEY,
            credentials={"api_key": "test-key"}
        )

    def test_connector_creation(self, connector_config):
        """Test connector creation"""
        connector = Connector(connector_config)
        assert connector.config.name == "test-connector"
        assert connector.status == ConnectorStatus.INACTIVE

    def test_connector_connect(self, connector_config):
        """Test connector connection"""
        connector = Connector(connector_config)
        result = connector.connect()

        assert result is True
        assert connector.status == ConnectorStatus.ACTIVE

    def test_connector_disconnect(self, connector_config):
        """Test connector disconnection"""
        connector = Connector(connector_config)
        connector.connect()
        connector.disconnect()

        assert connector.status == ConnectorStatus.INACTIVE

    def test_connector_is_healthy(self, connector_config):
        """Test connector health check"""
        connector = Connector(connector_config)
        assert connector.is_healthy() is False

        connector.connect()
        assert connector.is_healthy() is True

    def test_record_request(self, connector_config):
        """Test request recording"""
        connector = Connector(connector_config)
        connector.record_request()
        connector.record_request()

        assert connector.request_count == 2

    def test_record_error(self, connector_config):
        """Test error recording"""
        connector = Connector(connector_config)
        connector.record_error("Test error")

        assert connector.error_count == 1
        assert connector.last_error == "Test error"

    def test_get_stats(self, connector_config):
        """Test get connector statistics"""
        connector = Connector(connector_config)
        connector.connect()
        connector.record_request()
        connector.record_error("Test error")

        stats = connector.get_stats()
        assert stats["name"] == "test-connector"
        assert stats["requests"] == 1
        assert stats["errors"] == 1


class TestConnectorManager:
    """Tests for ConnectorManager class"""

    @pytest.fixture
    def manager(self):
        """Create test manager"""
        return ConnectorManager()

    @pytest.fixture
    def connector_config(self):
        """Create test connector config"""
        return ConnectorConfig(
            name="test-connector",
            connector_type="rest",
            base_url="https://api.example.com"
        )

    def test_create_connector(self, manager, connector_config):
        """Test connector creation"""
        connector = manager.create_connector(connector_config)

        assert connector is not None
        assert "test-connector" in manager.connectors

    def test_get_connector(self, manager, connector_config):
        """Test get connector by name"""
        manager.create_connector(connector_config)

        connector = manager.get_connector("test-connector")
        assert connector is not None
        assert connector.config.name == "test-connector"

    def test_get_nonexistent_connector(self, manager):
        """Test get nonexistent connector"""
        connector = manager.get_connector("nonexistent")
        assert connector is None

    def test_remove_connector(self, manager, connector_config):
        """Test connector removal"""
        manager.create_connector(connector_config)
        result = manager.remove_connector("test-connector")

        assert result is True
        assert "test-connector" not in manager.connectors

    def test_remove_nonexistent_connector(self, manager):
        """Test removing nonexistent connector"""
        result = manager.remove_connector("nonexistent")
        assert result is False

    def test_connect_all(self, manager):
        """Test connecting all connectors"""
        config1 = ConnectorConfig(name="conn1", connector_type="rest", base_url="http://a")
        config2 = ConnectorConfig(name="conn2", connector_type="rest", base_url="http://b")

        manager.create_connector(config1)
        manager.create_connector(config2)

        results = manager.connect_all()

        assert results["conn1"] is True
        assert results["conn2"] is True

    def test_disconnect_all(self, manager):
        """Test disconnecting all connectors"""
        config = ConnectorConfig(name="conn1", connector_type="rest", base_url="http://a")
        manager.create_connector(config)
        manager.connect_all()

        manager.disconnect_all()

        assert manager.connectors["conn1"].status == ConnectorStatus.INACTIVE

    def test_get_health_status(self, manager, connector_config):
        """Test get health status"""
        manager.create_connector(connector_config)
        manager.connectors["test-connector"].connect()

        health = manager.get_health_status()
        assert "test-connector" in health
        assert health["test-connector"]["healthy"] is True

    def test_list_connectors(self, manager):
        """Test list connectors"""
        config1 = ConnectorConfig(name="conn1", connector_type="rest", base_url="http://a")
        config2 = ConnectorConfig(name="conn2", connector_type="rest", base_url="http://b")

        manager.create_connector(config1)
        manager.create_connector(config2)

        connectors = manager.list_connectors()
        assert len(connectors) == 2
        assert "conn1" in connectors
        assert "conn2" in connectors


class TestOAuthHandler:
    """Tests for OAuthHandler class"""

    @pytest.fixture
    def oauth_handler(self):
        """Create test OAuth handler"""
        return OAuthHandler()

    @pytest.fixture
    def oauth_config(self):
        """Create test OAuth config"""
        return OAuthConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            redirect_uri="https://app.example.com/callback",
            scopes=["read", "write"]
        )

    def test_register_provider(self, oauth_handler, oauth_config):
        """Test provider registration"""
        oauth_handler.register_provider("test-provider", oauth_config)

        assert "test-provider" in oauth_handler.configs

    def test_generate_auth_url(self, oauth_handler, oauth_config):
        """Test auth URL generation"""
        oauth_handler.register_provider("test-provider", oauth_config)

        url = oauth_handler.generate_auth_url("test-provider")

        assert url is not None
        assert "https://auth.example.com/authorize" in url
        assert "client_id=test-client-id" in url

    def test_validate_state(self, oauth_handler):
        """Test state validation"""
        state = "test-state-123"
        oauth_handler.pending_states[state] = time.time()

        result = oauth_handler.validate_state(state)
        assert result is True

    def test_validate_expired_state(self, oauth_handler):
        """Test expired state validation"""
        state = "expired-state"
        oauth_handler.pending_states[state] = time.time() - 700  # Expired

        result = oauth_handler.validate_state(state)
        assert result is False

    def test_store_and_get_token(self, oauth_handler):
        """Test token storage and retrieval"""
        token = OAuthToken(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            expires_in=3600
        )

        oauth_handler.store_token("test-provider", token)

        retrieved = oauth_handler.get_token("test-provider")
        assert retrieved.access_token == "test-access-token"

    def test_get_valid_token(self, oauth_handler):
        """Test get valid token"""
        token = OAuthToken(
            access_token="test-access-token",
            expires_in=3600
        )
        oauth_handler.store_token("test-provider", token)

        access_token = oauth_handler.get_valid_token("test-provider")
        assert access_token == "test-access-token"

    def test_get_expired_token(self, oauth_handler):
        """Test get expired token returns None"""
        token = OAuthToken(
            access_token="test-access-token",
            expires_in=1
        )
        token.created_at = time.time() - 100  # Expired
        oauth_handler.store_token("test-provider", token)

        access_token = oauth_handler.get_valid_token("test-provider")
        assert access_token is None

    def test_revoke_token(self, oauth_handler):
        """Test token revocation"""
        token = OAuthToken(access_token="test-token")
        oauth_handler.store_token("test-provider", token)

        result = oauth_handler.revoke_token("test-provider")
        assert result is True
        assert oauth_handler.get_token("test-provider") is None

    def test_token_is_expired(self):
        """Test token expiration check"""
        token = OAuthToken(access_token="test", expires_in=3600)
        assert token.is_expired() is False

        token.created_at = time.time() - 3700
        assert token.is_expired() is True


class TestConnectorPool:
    """Tests for ConnectorPool class"""

    def test_get_connection(self):
        """Test getting connection from pool"""
        pool = ConnectorPool(max_size=5)

        conn = pool.get_connection("test-connector")

        assert conn is not None
        assert "id" in conn

    def test_return_connection(self):
        """Test returning connection to pool"""
        pool = ConnectorPool(max_size=5)

        conn = pool.get_connection("test-connector")
        pool.return_connection("test-connector", conn)

        pool_size = pool.get_pool_size("test-connector")
        assert pool_size == 1

    def test_pool_reuse(self):
        """Test connection reuse"""
        pool = ConnectorPool(max_size=5)

        conn1 = pool.get_connection("test-connector")
        pool.return_connection("test-connector", conn1)

        conn2 = pool.get_connection("test-connector")

        assert conn1["id"] == conn2["id"]

    def test_pool_max_size(self):
        """Test pool max size limit"""
        pool = ConnectorPool(max_size=2)

        conn1 = pool.get_connection("test-connector")
        conn2 = pool.get_connection("test-connector")

        assert pool.pool_sizes["test-connector"] == 2

    def test_clear_pool(self):
        """Test clearing pool"""
        pool = ConnectorPool(max_size=5)

        pool.get_connection("test-connector")
        pool.get_connection("test-connector")

        count = pool.clear_pool("test-connector")
        assert count >= 0

    def test_get_stats(self):
        """Test get pool statistics"""
        pool = ConnectorPool(max_size=5)

        pool.get_connection("test-connector")
        pool.get_connection("test-connector")

        stats = pool.get_stats()
        assert "test-connector" in stats
        assert stats["test-connector"]["created"] == 2
