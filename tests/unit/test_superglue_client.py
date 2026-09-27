import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.core.superglue_client import (
    SUPERGLUE_CORE_PORT,
    SUPERGLUE_QUEUE_PORT,
    _get_config,
    _get_core_url,
    _get_queue_url,
    _get_status_url,
    is_configured,
    namespaced_tool_id,
)


# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

class TestConfig:
    """Configuration and URL helpers."""

    def test_get_config_returns_tuple(self):
        url, token = _get_config()
        assert isinstance(url, str)
        assert isinstance(token, str)

    def test_get_config_strips_whitespace(self):
        url, token = _get_config()
        assert url == url.strip()
        assert token == token.strip()

    def test_get_config_strips_trailing_slash(self):
        url, _ = _get_config()
        assert not url.endswith("/")

    def test_get_queue_url(self):
        url = _get_queue_url()
        assert isinstance(url, str)
        assert len(url) > 0

    def test_get_status_url(self):
        url = _get_status_url()
        assert isinstance(url, str)
        assert len(url) > 0

    def test_get_core_url(self):
        url = _get_core_url()
        assert isinstance(url, str)
        assert len(url) > 0

    def test_is_configured_true(self):
        # With default values, should be True
        assert is_configured() is True

    @patch.dict(os.environ, {"SUPERGLUE_API_URL": "", "SUPERGLUE_AUTH_TOKEN": ""})
    def test_is_configured_empty_env(self):
        assert is_configured() is False

    def test_port_constants(self):
        assert SUPERGLUE_CORE_PORT == 3002
        assert SUPERGLUE_QUEUE_PORT == 3003


# ═══════════════════════════════════════════════════════════════════
# namespaced_tool_id
# ═══════════════════════════════════════════════════════════════════

class TestNamespacedToolId:
    """Tenant isolation via namespaced tool IDs. BC-001."""

    def test_basic_namespacing(self):
        result = namespaced_tool_id("refund-by-email", "tenant-abc")
        assert result == "tenant_tenant-abc__refund-by-email"

    def test_already_namespaced_passthrough(self):
        tool_id = "tenant_tenant-abc__refund-by-email"
        result = namespaced_tool_id(tool_id, "tenant-abc")
        assert result == tool_id  # unchanged

    def test_no_tenant_returns_raw(self):
        result = namespaced_tool_id("refund-by-email", "")
        assert result == "refund-by-email"

    def test_none_tenant_returns_raw(self):
        result = namespaced_tool_id("refund-by-email", None)  # type: ignore[arg-type]
        assert result == "refund-by-email"

    def test_different_tenants_different_namespaces(self):
        r1 = namespaced_tool_id("refund", "tenant-a")
        r2 = namespaced_tool_id("refund", "tenant-b")
        assert r1 != r2
        assert "tenant-a" in r1
        assert "tenant-b" in r2

    def test_double_underscore_separator(self):
        result = namespaced_tool_id("tool", "abc")
        parts = result.split("__", 1)
        assert len(parts) == 2
        assert parts[0] == "tenant_abc"
        assert parts[1] == "tool"

    def test_tenant_startswith_tenant_prefix(self):
        """Tool IDs that start with 'tenant_' but have no '__' get re-namespaced."""
        # Actually: the check is tool_id.startswith("tenant_") and "__" in tool_id
        # If tool_id is "tenant_foo" (no __), it will be re-namespaced
        result = namespaced_tool_id("tenant_foo", "tenant-bar")
        assert result == "tenant_tenant-bar__tenant_foo"


# ═══════════════════════════════════════════════════════════════════
# list_tools (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════

class TestListTools:
    """list_tools — mocked HTTP."""

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_list_tools_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "tool-1", "name": "Tool 1"}]}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import list_tools
        tools = await list_tools()
        assert len(tools) == 1
        assert tools[0]["id"] == "tool-1"

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_list_tools_empty_on_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import list_tools
        tools = await list_tools()
        assert tools == []  # BC-008: fail-open

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_list_tools_non_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import list_tools
        tools = await list_tools()
        assert tools == []


# ═══════════════════════════════════════════════════════════════════
# verify_tool_exists (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════

class TestVerifyToolExists:
    """verify_tool_exists — pre-flight check."""

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_tool_exists(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"archived": False}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import verify_tool_exists
        assert await verify_tool_exists("tool-1") is True

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_tool_archived(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"archived": True}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import verify_tool_exists
        assert await verify_tool_exists("tool-1") is False

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_tool_404(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import verify_tool_exists
        assert await verify_tool_exists("tool-1") is False

    @patch("app.core.superglue_client.is_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_not_configured(self, mock_cfg):
        from app.core.superglue_client import verify_tool_exists
        assert await verify_tool_exists("tool-1") is False


# ═══════════════════════════════════════════════════════════════════
# execute_tool (mocked HTTP + DB queue)
# ═══════════════════════════════════════════════════════════════════

class TestExecuteTool:
    """execute_tool — mocked HTTP + DB queue."""

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "success",
            "runId": "run-123",
            "data": {"result": "refunded"},
            "stepResults": [{"stepId": "s1", "success": True}],
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import execute_tool
        result = await execute_tool("refund-by-email", {"email": "test@test.com"})
        assert result["success"] is True
        assert result["data"]["result"] == "refunded"
        assert result["run_id"] == "run-123"
        assert len(result["step_results"]) == 1

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_execute_http_failure(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import execute_tool
        result = await execute_tool("tool-1", {})
        assert result["success"] is False
        assert "500" in result["error"]

    @patch("app.core.superglue_client.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_execute_with_tenant_namespacing(self, mock_client_cls):
        """Verify tenant_id causes namespacing in the API call."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success", "runId": "r1", "data": {}, "stepResults": []}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        from app.core.superglue_client import execute_tool
        await execute_tool("refund-by-email", {}, tenant_id="tenant-abc")

        # Verify the POST was made with namespaced tool ID
        call_args = mock_client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "tenant_tenant-abc__refund-by-email" in url

    @patch.dict(os.environ, {"SUPERGLUE_API_URL": "", "SUPERGLUE_AUTH_TOKEN": ""})
    @pytest.mark.asyncio
    async def test_execute_not_configured(self):
        from app.core.superglue_client import execute_tool
        result = await execute_tool("tool-1", {})
        assert result["success"] is False
        assert "not configured" in result["error"].lower()
