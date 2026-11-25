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
    _get_llm_key,
    DEFAULT_SUPERGLUE_URL,
)


class _QueueQuery:
    def filter(self, *args, **kwargs):
        return self

    def delete(self):
        return 0

    def first(self):
        return None


class _QueueDB:
    bind = None

    def add(self, row):
        self.row = row

    def query(self, model):
        return _QueueQuery()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ── Config ──


@pytest.fixture(autouse=True)
def fake_superglue_credentials(monkeypatch):
    """Mock HTTP tests use synthetic credentials, never production secrets."""
    monkeypatch.setenv("SUPERGLUE_AUTH_TOKEN", "test-superglue-token")
    monkeypatch.setenv("SUPERGLUE_LLM_API_KEY", "test-superglue-llm-key")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")
    from app.core import superglue_client
    from database import base
    monkeypatch.setattr(superglue_client, "_get_tenant_api_key", lambda tenant_id: "test-tenant-key")
    monkeypatch.setattr(base, "SessionLocal", lambda: _QueueDB())


class TestGetConfig:
    def test_fails_closed_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            url, token = _get_config()
            assert url == DEFAULT_SUPERGLUE_URL
            assert token == ""
            assert _get_llm_key() == ""


class TestIsConfigured:
    def test_missing_environment_credentials_disable_superglue(self):
        with patch.dict(os.environ, {}, clear=True):
            assert is_configured() is False

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
    async def test_requires_tenant_context(self):
        from app.core.superglue_client import execute_tool

        result = await execute_tool("refund-tool", {"email": "a@b.com"})
        assert result["success"] is False
        assert "Tenant context" in result["error"]

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
            result = await execute_tool("refund-tool", {"email": "a@b.com"}, tenant_id="tenant-test")
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
