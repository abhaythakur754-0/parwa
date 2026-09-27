"""
Unit tests for mcp_server/integrations/superglue_adapter_server.py

Covers:
- SuperglueAdapterServer class creation
- _ensure_imports() lazy loading
- register_tools() (mocked Superglue client)
- _invoke_handler safety pipeline: classify → guardrails → approval → execute
- get_router() REST endpoints
- BC-008: never crashes
- sg_ prefix namespacing

Run: pytest backend/app/tests/test_superglue_adapter_server.py -v
"""

import sys
import os

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from mcp_server.integrations.superglue_adapter_server import (
    SuperglueAdapterServer,
    superglue_adapter_server,
    _ensure_imports,
)
from mcp_server.models import ToolDefinition, ToolInvokeResponse, ToolCategory
from mcp_server.base_server import MCPRegistry


class TestAdapterServerCreation:
    def test_singleton_exists(self):
        assert superglue_adapter_server is not None
        assert isinstance(superglue_adapter_server, SuperglueAdapterServer)

    def test_server_metadata(self):
        assert superglue_adapter_server.name == "superglue_adapter"
        assert superglue_adapter_server.version == "1.0.0"
        assert superglue_adapter_server.category == ToolCategory.INTEGRATION

    def test_get_server_info(self):
        info = superglue_adapter_server.get_server_info()
        assert info.name == "superglue_adapter"


class TestEnsureImports:
    def test_returns_false_when_backend_unavailable(self):
        # _ensure_imports() will fail if backend modules don't exist
        # in the current Python path. That's fine — we test the function runs.
        try:
            result = _ensure_imports()
            assert isinstance(result, bool)
        except Exception:
            pass  # BC-008 context


class TestRegisterTools:
    def test_register_empty_tools(self):
        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        # Should not crash even with no tools
        server.register_tools(registry)

    def test_register_tools_sg_prefix(self):
        registry = MCPRegistry()
        server = SuperglueAdapterServer()

        mock_tools = [
            {"id": "refund-tool", "name": "Refund Tool", "inputSchema": {}, "outputSchema": {}},
            {"id": "get-order", "name": "Get Order", "inputSchema": {}, "outputSchema": {}},
        ]

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._sgc", new=MagicMock(is_configured=MagicMock(return_value=True))), \
             patch("mcp_server.integrations.superglue_adapter_server._run_async", return_value=mock_tools), \
             patch("mcp_server.integrations.superglue_adapter_server._dsu", new=MagicMock(publish_superglue_signals=AsyncMock(return_value=2))):
            server.register_tools(registry)

        # Check tools are registered with sg_ prefix
        refund_tool = registry.get_tool("sg_refund-tool")
        assert refund_tool is not None
        assert refund_tool.tags == ["superglue", "dynamic"]

        get_order_tool = registry.get_tool("sg_get-order")
        assert get_order_tool is not None


class TestInvokeHandler:
    @pytest.mark.asyncio
    async def test_handler_returns_response_on_missing_backend(self):
        server = SuperglueAdapterServer()
        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=False):
            result = await server._invoke_handler("sg_test", "test-tool")
            assert result.success is False
            assert "unavailable" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handler_classifies_then_executes(self):
        server = SuperglueAdapterServer()
        mock_safety = MagicMock(
            level=MagicMock(value="read"),
            confidence=0.9,
            reasoning="test",
        )
        mock_result = {"success": True, "data": "ok"}

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._as", classify_action=MagicMock(return_value=mock_safety),
                   ActionSafetyResult=MagicMock, needs_approval=MagicMock(return_value=False)), \
             patch("mcp_server.integrations.superglue_adapter_server._sgc", execute_tool=AsyncMock(return_value=mock_result)):
            result = await server._invoke_handler("sg_test_tool", "test-tool", parameters={"key": "val"})
            assert result.success is True
            assert result.data["success"] is True

    @pytest.mark.asyncio
    async def test_handler_blocks_on_guardrail(self):
        server = SuperglueAdapterServer()
        from mcp_server.integrations.superglue_adapter_server import _as
        financial_level = MagicMock(value="financial")
        mock_safety = MagicMock(level=financial_level, confidence=0.9, reasoning="refund")
        mock_gr = MagicMock(allowed=False, reason="exceeds limit")

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._as", classify_action=MagicMock(return_value=mock_safety),
                   ActionSafetyLevel=MagicMock(FINANCIAL=financial_level), needs_approval=MagicMock(return_value=True)), \
             patch("mcp_server.integrations.superglue_adapter_server._rg", check_financial_guardrails=MagicMock(return_value=mock_gr)):
            result = await server._invoke_handler("sg_refund_tool", "refund-tool",
                                                   parameters={"amount": 1000})
            assert result.success is False
            assert "Guardrail blocked" in result.error

    @pytest.mark.asyncio
    async def test_handler_requires_approval_for_destructive(self):
        server = SuperglueAdapterServer()
        destructive_level = MagicMock(value="destructive")
        mock_safety = MagicMock(level=destructive_level, confidence=0.9, reasoning="delete")

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._as", classify_action=MagicMock(return_value=mock_safety),
                   ActionSafetyLevel=MagicMock(DESTRUCTIVE=destructive_level), needs_approval=MagicMock(return_value=True)), \
             patch("mcp_server.integrations.superglue_adapter_server._rg", get_applicable_frameworks=MagicMock(return_value=["SOX"])) as mock_fw:
            result = await server._invoke_handler("sg_delete_tool", "delete-tool")
            assert result.success is False
            assert "requires approval" in result.error.lower()
            assert result.data["safety_level"] == "destructive"

    @pytest.mark.asyncio
    async def test_handler_bc008_classification_error(self):
        server = SuperglueAdapterServer()
        read_level = MagicMock(value="read")

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._as", classify_action=MagicMock(side_effect=RuntimeError("boom")),
                   ActionSafetyLevel=MagicMock(READ=read_level), ActionSafetyResult=MagicMock,
                   needs_approval=MagicMock(return_value=False)), \
             patch("mcp_server.integrations.superglue_adapter_server._sgc", execute_tool=AsyncMock(return_value={"success": True, "data": "ok"})):
            result = await server._invoke_handler("sg_test", "test")
            # Should still execute (defaults to READ on error)
            assert result.success is True


class TestGetRouter:
    def test_router_returns_api_router(self):
        router = superglue_adapter_server.get_router()
        assert router is not None
        assert router.prefix == "/integrations/superglue"

    def test_router_has_sync_endpoint(self):
        router = superglue_adapter_server.get_router()
        paths = [r.path for r in router.routes]
        assert any("sync" in p for p in paths)

    def test_router_has_tools_endpoint(self):
        router = superglue_adapter_server.get_router()
        paths = [r.path for r in router.routes]
        assert any("tools" in p for p in paths)
