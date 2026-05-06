"""
Unit tests for MCP Client.
"""
import os
import uuid
import pytest
import asyncio

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.mcp_client.client import MCPClient, MCPClientState
from shared.mcp_client.auth import MCPAuthManager, MCPAuthToken
from shared.mcp_client.registry import MCPRegistry, MCPServerInfo, RegistryStatus


class TestMCPClient:
    """Tests for MCP Client."""

    def test_client_creation(self):
        """Test creating MCP client."""
        client = MCPClient(
            server_url="http://localhost:8080",
            company_id=uuid.uuid4(),
        )
        assert client.server_url == "http://localhost:8080"
        assert client.state == MCPClientState.DISCONNECTED
        assert client.is_connected == False

    def test_client_default_timeout(self):
        """Test client default timeout."""
        client = MCPClient()
        assert client.timeout == MCPClient.DEFAULT_TIMEOUT

    @pytest.mark.asyncio
    async def test_client_connect(self):
        """Test client connection."""
        client = MCPClient()
        result = await client.connect()
        assert result == True
        assert client.is_connected == True
        assert client.state == MCPClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_client_disconnect(self):
        """Test client disconnection."""
        client = MCPClient()
        await client.connect()
        await client.disconnect()
        assert client.state == MCPClientState.DISCONNECTED
        assert client.is_connected == False

    @pytest.mark.asyncio
    async def test_client_health_check(self):
        """Test client health check."""
        client = MCPClient()
        await client.connect()
        health = await client.health_check()
        assert health["healthy"] == True
        assert health["state"] == MCPClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_invoke_tool_without_connection_raises(self):
        """Test invoking tool without connection raises error."""
        client = MCPClient()
        with pytest.raises(ValueError, match="not connected"):
            await client.invoke_tool("test_tool")

    @pytest.mark.asyncio
    async def test_invoke_tool(self):
        """Test invoking a tool."""
        client = MCPClient()
        await client.connect()
        result = await client.invoke_tool("test_tool", {"arg": "value"})
        assert result["success"] == True
        assert result["tool"] == "test_tool"

    def test_register_tool(self):
        """Test registering a tool."""
        client = MCPClient()
        client.register_tool("my_tool", {"description": "Test tool"})
        assert "my_tool" in client.get_available_tools()

    def test_register_resource(self):
        """Test registering a resource."""
        client = MCPClient()
        client.register_resource("resource://test", {"type": "test"})
        assert "resource://test" in client.get_available_resources()


class TestMCPAuth:
    """Tests for MCP Authentication."""

    def test_auth_manager_creation(self):
        """Test creating auth manager."""
        manager = MCPAuthManager(company_id=uuid.uuid4())
        assert manager.company_id is not None

    def test_generate_token(self):
        """Test generating auth token."""
        manager = MCPAuthManager()
        token = manager.generate_token()
        assert token.token is not None
        assert token.token_type == "bearer"
        assert token.is_expired == False

    def test_generate_token_with_scopes(self):
        """Test generating token with custom scopes."""
        manager = MCPAuthManager()
        token = manager.generate_token(scopes=["read", "write", "admin"])
        assert "read" in token.scopes
        assert "write" in token.scopes
        assert "admin" in token.scopes

    def test_validate_token(self):
        """Test validating auth token."""
        manager = MCPAuthManager()
        token = manager.generate_token()
        payload = manager.validate_token(token.token)
        assert payload is not None
        assert payload["type"] == "mcp_access"

    def test_validate_invalid_token_raises(self):
        """Test validating invalid token raises error."""
        manager = MCPAuthManager()
        with pytest.raises(ValueError, match="validation failed"):
            manager.validate_token("invalid_token_string")

    def test_revoke_token(self):
        """Test revoking token."""
        manager = MCPAuthManager()
        token = manager.generate_token()
        session_id = manager.validate_token(token.token)["session_id"]
        result = manager.revoke_token(session_id)
        assert result == True

    def test_generate_api_key(self):
        """Test generating API key."""
        manager = MCPAuthManager()
        api_key = manager.generate_api_key(
            name="test_key",
            company_id=uuid.uuid4(),
        )
        assert api_key.startswith("mcp_")

    def test_create_auth_header(self):
        """Test creating auth header."""
        manager = MCPAuthManager()
        token = manager.generate_token()
        header = manager.create_auth_header(token)
        assert "Authorization" in header
        assert header["Authorization"].startswith("Bearer ")

    def test_token_expiry(self):
        """Test token expiry check."""
        from datetime import datetime, timedelta, timezone

        # Create expired token
        expired_token = MCPAuthToken(
            token="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert expired_token.is_expired == True

        # Create valid token
        valid_token = MCPAuthToken(
            token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert valid_token.is_expired == False


class TestMCPRegistry:
    """Tests for MCP Registry."""

    def test_registry_creation(self):
        """Test creating registry."""
        registry = MCPRegistry(
            registry_url="http://registry:8080",
            company_id=uuid.uuid4(),
        )
        assert registry.registry_url == "http://registry:8080"
        assert registry.status == RegistryStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_registry_connect(self):
        """Test registry connection."""
        registry = MCPRegistry()
        result = await registry.connect()
        assert result == True
        assert registry.is_connected == True

    @pytest.mark.asyncio
    async def test_registry_disconnect(self):
        """Test registry disconnection."""
        registry = MCPRegistry()
        await registry.connect()
        await registry.disconnect()
        assert registry.status == RegistryStatus.DISCONNECTED

    def test_register_server(self):
        """Test registering server."""
        registry = MCPRegistry()
        server = registry.register_server(
            name="test_server",
            url="http://localhost:9000",
            server_type="knowledge",
            capabilities=["embed", "search"],
        )
        assert server.server_id is not None
        assert server.name == "test_server"
        assert server.is_healthy == True

    def test_unregister_server(self):
        """Test unregistering server."""
        registry = MCPRegistry()
        server = registry.register_server("test", "http://localhost:9000")
        result = registry.unregister_server(server.server_id)
        assert result == True
        assert registry.get_server(server.server_id) is None

    def test_get_servers_by_type(self):
        """Test getting servers by type."""
        registry = MCPRegistry()
        registry.register_server("kb1", "http://kb1", server_type="knowledge")
        registry.register_server("tool1", "http://tool1", server_type="tool")

        knowledge_servers = registry.get_servers_by_type("knowledge")
        assert len(knowledge_servers) == 1
        assert knowledge_servers[0].server_type == "knowledge"

    def test_get_servers_by_capability(self):
        """Test getting servers by capability."""
        registry = MCPRegistry()
        registry.register_server(
            "server1", "http://s1",
            capabilities=["embed", "search"]
        )
        registry.register_server(
            "server2", "http://s2",
            capabilities=["invoke"]
        )

        servers = registry.get_servers_by_capability("embed")
        assert len(servers) == 1
        assert "embed" in servers[0].capabilities

    def test_register_tool(self):
        """Test registering tool."""
        registry = MCPRegistry()
        server = registry.register_server("test", "http://test")
        registry.register_tool("embed_text", server.server_id)

        servers = registry.get_servers_for_tool("embed_text")
        assert len(servers) == 1

    def test_register_resource(self):
        """Test registering resource."""
        registry = MCPRegistry()
        server = registry.register_server("test", "http://test")
        registry.register_resource("kb://documents", server.server_id)

        servers = registry.get_servers_for_resource("kb://documents")
        assert len(servers) == 1

    def test_update_heartbeat(self):
        """Test updating server heartbeat."""
        registry = MCPRegistry()
        server = registry.register_server("test", "http://test")
        result = registry.update_server_heartbeat(server.server_id)
        assert result == True
        assert server.last_heartbeat is not None

    def test_mark_unhealthy(self):
        """Test marking server unhealthy."""
        registry = MCPRegistry()
        server = registry.register_server("test", "http://test")
        registry.mark_server_unhealthy(server.server_id)
        assert server.is_healthy == False

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test registry health check."""
        registry = MCPRegistry()
        await registry.connect()
        health = await registry.health_check()
        assert health["is_connected"] == True
        assert "servers" in health

    def test_get_registry_stats(self):
        """Test getting registry stats."""
        registry = MCPRegistry()
        registry.register_server("kb1", "http://kb1", server_type="knowledge")
        registry.register_server("kb2", "http://kb2", server_type="knowledge")
        registry.register_server("tool1", "http://tool1", server_type="tool")

        stats = registry.get_registry_stats()
        assert stats["total_servers"] == 3
        assert stats["server_types"]["knowledge"] == 2
        assert stats["server_types"]["tool"] == 1


class TestMCPServerInfo:
    """Tests for MCP Server Info."""

    def test_server_info_creation(self):
        """Test creating server info."""
        server = MCPServerInfo(
            server_id="test-id",
            name="test_server",
            url="http://localhost:9000",
            server_type="knowledge",
            capabilities=["embed", "search"],
        )
        assert server.server_id == "test-id"
        assert server.name == "test_server"
        assert server.is_healthy == True

    def test_server_info_to_dict(self):
        """Test converting server info to dict."""
        server = MCPServerInfo(
            server_id="test-id",
            name="test_server",
            url="http://localhost:9000",
        )
        data = server.to_dict()
        assert data["server_id"] == "test-id"
        assert data["name"] == "test_server"
        assert "registered_at" in data


class TestIntegration:
    """Integration tests for MCP Client chain."""

    @pytest.mark.asyncio
    async def test_full_mcp_workflow(self):
        """Test complete MCP workflow."""
        # Create auth manager and generate token
        auth_manager = MCPAuthManager(company_id=uuid.uuid4())
        token = auth_manager.generate_token(scopes=["read", "invoke"])

        # Create registry and register server
        registry = MCPRegistry()
        await registry.connect()
        server = registry.register_server(
            name="knowledge_server",
            url="http://knowledge:9000",
            server_type="knowledge",
            capabilities=["embed", "search", "retrieve"],
        )
        registry.register_tool("embed_text", server.server_id)
        registry.register_resource("kb://documents", server.server_id)

        # Create client and connect
        client = MCPClient(company_id=auth_manager.company_id)
        await client.connect()

        # Verify everything works
        assert client.is_connected
        assert registry.is_connected
        assert len(registry.get_servers_for_tool("embed_text")) == 1

        # Health checks
        client_health = await client.health_check()
        registry_health = await registry.health_check()

        assert client_health["healthy"] == True
        assert registry_health["is_connected"] == True

        # Cleanup
        await client.disconnect()
        await registry.disconnect()
