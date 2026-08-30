"""
Unit tests for app/core/superglue_client.py

Covers:
- is_configured()
- namespaced_tool_id()
- _get_config()
- list_tools() (mocked HTTP)
- execute_tool() (mocked HTTP)
- verify_tool_exists() (mocked HTTP)
- BC-008: never crashes on network errors
- Tenant isolation (namespacing)

Run: pytest backend/app/tests/test_superglue_client.py -v
"""

import sys
import os

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.superglue_client import (
    is_configured,
    namespaced_tool_id,
    _get_config,
    DEFAULT_SUPERGLUE_URL,
    DEFAULT_SUPERGLUE_TOKEN,
)


# ── Config ──


class TestGetConfig:
    def test_returns_defaults_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove env vars to test defaults
            url, token = _get_config()
            assert url == DEFAULT_SUPERGLUE_URL
            assert token == DEFAULT_SUPERGLUE_TOKEN

    def test_env_overrides_defaults(self):
        with patch.dict(os.environ, {
            "SUPERGLUE_API_URL": "https://custom.example.com",
            "SUPERGLUE_AUTH_TOKEN": "custom-token-123",
        }, clear=False):
            url, token = _get_config()
            assert url == "https://custom.example.com"
            assert token == "custom-token-123"

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {
            "SUPERGLUE_API_URL": "  https://example.com/  ",
            "SUPERGLUE_AUTH_TOKEN": "  tok  ",
        }, clear=False):
            url, token = _get_config()
            assert url == "https://example.com"
            assert token == "tok"

    def test_strips_trailing_slash(self):
        with patch.dict(os.environ, {
            "SUPERGLUE_API_URL": "https://example.com/api/",
        }, clear=False):
            url, _ = _get_config()
            assert not url.endswith("/")


class TestIsConfigured:
    def test_configured_with_defaults(self):
        # Defaults are always set
        assert is_configured() is True

    def test_configured_empty_url(self):
        with patch.dict(os.environ, {"SUPERGLUE_API_URL": "", "SUPERGLUE_AUTH_TOKEN": "tok"}):
            assert is_configured() is False

    def test_configured_empty_token(self):
        with patch.dict(os.environ, {"SUPERGLUE_API_URL": "https://x.com", "SUPERGLUE_AUTH_TOKEN": ""}):
            assert is_configured() is False


# ── Tenant Isolation ──


class TestNamespacedToolId:
    def test_basic_namespacing(self):
        result = namespaced_tool_id("refund-tool", "tenant-abc")
        assert result == "tenant_tenant-abc__refund-tool"

    def test_already_namespaced_passthrough(self):
        tool_id = "tenant_tenant-abc__refund-tool"
        result = namespaced_tool_id(tool_id, "tenant-abc")
        assert result == tool_id

    def test_no_tenant_returns_raw(self):
        result = namespaced_tool_id("refund-tool", "")
        assert result == "refund-tool"

    def test_none_tenant_returns_raw(self):
        result = namespaced_tool_id("refund-tool", None)
        assert result == "refund-tool"

    def test_different_tenants_different_ids(self):
        id1 = namespaced_tool_id("refund-tool", "tenant-1")
        id2 = namespaced_tool_id("refund-tool", "tenant-2")
        assert id1 != id2

    def test_uuid_tenant(self):
        result = namespaced_tool_id("get-order", "abc-123-def-456")
        assert result == "tenant_abc-123-def-456__get-order"


# ── List Tools (mocked HTTP) ──


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_tools_on_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "t1", "name": "Refund"}]}

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import list_tools
            tools = await list_tools()
            assert len(tools) == 1
            assert tools[0]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_returns_empty_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import list_tools
            tools = await list_tools()
            assert tools == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_network_error(self):
        with patch("app.core.superglue_client.httpx.AsyncClient", side_effect=Exception("network down")):
            from app.core.superglue_client import list_tools
            tools = await list_tools()
            assert tools == []


# ── Execute Tool (mocked HTTP) ──


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_success_response(self):
        # execute_tool checks res.json()["status"] == "success" to determine success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {"result": "refund_processed"}}

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import execute_tool
            result = await execute_tool("refund-tool", {"email": "a@b.com"})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_applies_tenant_namespace(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}, "success": True}

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import execute_tool
            await execute_tool("refund-tool", {}, tenant_id="t-123")
            # Verify the URL contains the namespaced tool_id
            call_args = mock_client.post.call_args
            assert "tenant_t-123__refund-tool" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_network_error_returns_failure(self):
        with patch("app.core.superglue_client.httpx.AsyncClient", side_effect=Exception("timeout")):
            from app.core.superglue_client import execute_tool
            result = await execute_tool("refund-tool", {"email": "a@b.com"})
            assert result["success"] is False
            assert "error" in result


# ── Verify Tool Exists ──


class TestVerifyToolExists:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"archived": False}

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import verify_tool_exists
            assert await verify_tool_exists("refund-tool") is True

    @pytest.mark.asyncio
    async def test_returns_false_on_archived(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"archived": True}

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import verify_tool_exists
            assert await verify_tool_exists("refund-tool") is False

    @pytest.mark.asyncio
    async def test_returns_false_on_404(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("app.core.superglue_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from app.core.superglue_client import verify_tool_exists
            assert await verify_tool_exists("refund-tool") is False

    @pytest.mark.asyncio
    async def test_returns_true_on_network_error(self):
        """BC-008: Assume tool exists if we can't reach Superglue."""
        with patch("app.core.superglue_client.httpx.AsyncClient", side_effect=Exception("network")):
            from app.core.superglue_client import verify_tool_exists
            assert await verify_tool_exists("refund-tool") is True
