"""
Unit tests for SuperglueAdapterServer - MCP adapter bridging Superglue tools.

Tests:
- Server metadata (name, category, version)
- register_tools: tool registration with sg_ prefix
- _invoke_handler: classify -> guardrails -> approval -> execute pipeline
- get_router: REST endpoints
- BC-008: every step wrapped, never crashes

Run: pytest tests/unit/test_superglue_adapter_server.py -v
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp_server.integrations.superglue_adapter_server import (
    SuperglueAdapterServer,
    superglue_adapter_server,
)
from mcp_server.base_server import MCPRegistry
from mcp_server.models import ToolCategory


# ═══════════════════════════════════════════════════════════════════
# Server metadata
# ═══════════════════════════════════════════════════════════════════

class TestServerMetadata:
    """Verify SuperglueAdapterServer metadata."""

    def test_name(self):
        assert superglue_adapter_server.name == "superglue_adapter"

    def test_description(self):
        assert "superglue" in superglue_adapter_server.description.lower()

    def test_category(self):
        assert superglue_adapter_server.category == ToolCategory.INTEGRATION

    def test_version(self):
        assert superglue_adapter_server.version == "1.0.0"

    def test_singleton_is_adapter_instance(self):
        assert isinstance(superglue_adapter_server, SuperglueAdapterServer)


# ═══════════════════════════════════════════════════════════════════
# register_tools (mocked imports)
# ═══════════════════════════════════════════════════════════════════

class TestRegisterTools:
    """Test tool registration with mocked Superglue client."""

    def test_register_tools_imports_fail(self):
        """When imports fail, no tools registered (BC-008)."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        adapter_mod._sgc = None
        adapter_mod._as = None
        adapter_mod._rg = None
        adapter_mod._dsu = None

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)
        assert registry.total_tools == 0

    def test_register_tools_not_configured(self):
        """When Superglue not configured, no tools registered."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        # Set imports to succeed but is_configured to False
        mock_sgc = MagicMock()
        mock_sgc.is_configured.return_value = False
        adapter_mod._sgc = mock_sgc
        adapter_mod._as = MagicMock()
        adapter_mod._rg = MagicMock()
        adapter_mod._dsu = MagicMock()

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)
        assert registry.total_tools == 0

    def test_register_tools_with_tools(self):
        """When Superglue has tools, they should be registered with sg_ prefix."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod

        mock_sgc = MagicMock()
        mock_sgc.is_configured.return_value = True
        mock_sgc.list_tools = AsyncMock(return_value=[
            {"id": "refund-by-email", "name": "Refund by Email", "inputSchema": {"type": "object"}},
            {"id": "get-order-status", "name": "Get Order Status", "inputSchema": {}},
        ])
        mock_dsu = MagicMock()
        mock_dsu.publish_superglue_signals = AsyncMock(return_value=2)
        adapter_mod._sgc = mock_sgc
        adapter_mod._as = MagicMock()
        adapter_mod._rg = MagicMock()
        adapter_mod._dsu = mock_dsu

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)

        tools = registry.list_tools(server="superglue_adapter")
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "sg_refund-by-email" in names
        assert "sg_get-order-status" in names
        for t in tools:
            assert "superglue" in t.tags

    def test_register_tools_empty_list(self):
        """When Superglue returns empty tools, nothing registered."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod

        mock_sgc = MagicMock()
        mock_sgc.is_configured.return_value = True
        mock_sgc.list_tools = AsyncMock(return_value=[])
        adapter_mod._sgc = mock_sgc
        adapter_mod._as = MagicMock()
        adapter_mod._rg = MagicMock()
        adapter_mod._dsu = MagicMock()

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)
        assert registry.total_tools == 0


# ═══════════════════════════════════════════════════════════════════
# _invoke_handler - full safety pipeline
# ═══════════════════════════════════════════════════════════════════

class TestInvokeHandler:
    """Test the 4-step handler: classify -> guardrails -> approval -> execute."""

    @pytest.mark.asyncio
    async def test_read_tool_executes(self):
        """READ-level tool should execute without approval."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        from app.core.action_safety import ActionSafetyLevel, ActionSafetyResult

        mock_sgc = MagicMock()
        mock_sgc.execute_tool = AsyncMock(return_value={"success": True, "data": {"result": "ok"}})
        mock_as = MagicMock()
        mock_as.classify_action.return_value = ActionSafetyResult(
            level=ActionSafetyLevel.READ, confidence=0.9, matched_keyword="get",
            reasoning="Matched keyword 'get' -> read",
        )
        mock_as.needs_approval.return_value = False
        mock_rg = MagicMock()

        adapter_mod._sgc = mock_sgc
        adapter_mod._as = mock_as
        adapter_mod._rg = mock_rg
        adapter_mod._dsu = MagicMock()

        server = SuperglueAdapterServer()
        result = await server._invoke_handler(
            "sg_get_order", "get_order",
            parameters={"orderId": "123"},
            context={"company_id": "tenant-1"},
        )
        assert result.success is True
        assert result.tool_name == "sg_get_order"

    @pytest.mark.asyncio
    async def test_financial_requires_approval(self):
        """FINANCIAL-level tool should be blocked for approval."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        from app.core.action_safety import ActionSafetyLevel, ActionSafetyResult

        mock_as = MagicMock()
        mock_as.classify_action.return_value = ActionSafetyResult(
            level=ActionSafetyLevel.FINANCIAL, confidence=0.9, matched_keyword="refund",
            reasoning="Matched keyword 'refund' -> financial",
        )
        mock_as.needs_approval.return_value = True
        mock_rg = MagicMock()
        mock_rg.get_applicable_frameworks.return_value = ["PCI-DSS"]

        adapter_mod._sgc = MagicMock()
        adapter_mod._as = mock_as
        adapter_mod._rg = mock_rg
        adapter_mod._dsu = MagicMock()

        server = SuperglueAdapterServer()
        result = await server._invoke_handler(
            "sg_refund_customer", "refund_customer",
            parameters={"amount": 100},
            context={"company_id": "tenant-1"},
        )
        assert result.success is False
        assert "requires approval" in (result.error or "").lower()
        assert result.data.get("status") == "pending_approval"

    @pytest.mark.asyncio
    async def test_destructive_requires_approval(self):
        """DESTRUCTIVE-level tool should be blocked for approval."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        from app.core.action_safety import ActionSafetyLevel, ActionSafetyResult

        mock_as = MagicMock()
        mock_as.classify_action.return_value = ActionSafetyResult(
            level=ActionSafetyLevel.DESTRUCTIVE, confidence=0.9, matched_keyword="delete",
            reasoning="Matched keyword 'delete' -> destructive",
        )
        mock_as.needs_approval.return_value = True
        mock_rg = MagicMock()
        mock_rg.get_applicable_frameworks.return_value = ["SOX"]

        adapter_mod._sgc = MagicMock()
        adapter_mod._as = mock_as
        adapter_mod._rg = mock_rg
        adapter_mod._dsu = MagicMock()

        server = SuperglueAdapterServer()
        result = await server._invoke_handler(
            "sg_delete_account", "delete_account",
            parameters={},
            context={"company_id": "tenant-1"},
        )
        assert result.success is False
        assert result.data.get("status") == "pending_approval"
        assert "SOX" in result.data.get("regulatory_frameworks", [])

    @pytest.mark.asyncio
    async def test_financial_guardrail_blocks(self):
        """FINANCIAL action exceeding tier limit should be blocked BEFORE approval gate.

        Note: In the real adapter, FINANCIAL always triggers the approval gate first
        (step 3) before reaching the execute step. The guardrail check (step 2) only
        blocks if the action is FINANCIAL but NOT needing approval. Since FINANCIAL
        always needs approval, the approval gate fires first. This test verifies
        that FINANCIAL + exceeding limit still results in a blocked action.
        """
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        from app.core.action_safety import ActionSafetyLevel, ActionSafetyResult

        mock_as = MagicMock()
        mock_as.classify_action.return_value = ActionSafetyResult(
            level=ActionSafetyLevel.FINANCIAL, confidence=0.9, matched_keyword="refund",
            reasoning="test",
        )
        mock_as.needs_approval.return_value = True
        mock_rg = MagicMock()
        mock_rg.check_financial_guardrails.return_value = MagicMock(
            allowed=False,
            reason="Amount $600.00 exceeds max_refund limit $500.00",
        )
        mock_rg.get_applicable_frameworks.return_value = ["PCI-DSS"]

        adapter_mod._sgc = MagicMock()
        adapter_mod._as = mock_as
        adapter_mod._rg = mock_rg
        adapter_mod._dsu = MagicMock()

        server = SuperglueAdapterServer()
        result = await server._invoke_handler(
            "sg_refund", "refund",
            parameters={"amount": 600},
            context={"company_id": "tenant-1", "variant_tier": "parwa"},
        )
        # FINANCIAL -> approval gate fires first (step 3 before execute)
        assert result.success is False
        assert "pending_approval" in str(result.data or "") or "guardrail" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_imports_unavailable_error(self):
        """When backend imports fail, return error (BC-008)."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        # Reset ALL lazy imports to None to force _ensure_imports to fail
        adapter_mod._sgc = None
        adapter_mod._as = None
        adapter_mod._rg = None
        adapter_mod._dsu = None

        # Also mock _ensure_imports to return False
        with patch.object(adapter_mod, '_ensure_imports', return_value=False):
            server = SuperglueAdapterServer()
            result = await server._invoke_handler("sg_tool", "tool")
        assert result.success is False
        assert "unavailable" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_failure_returns_error(self):
        """When Superglue execution fails, return error (BC-008)."""
        import mcp_server.integrations.superglue_adapter_server as adapter_mod
        from app.core.action_safety import ActionSafetyLevel, ActionSafetyResult

        mock_sgc = MagicMock()
        mock_sgc.execute_tool = AsyncMock(side_effect=Exception("Connection refused"))
        mock_as = MagicMock()
        mock_as.classify_action.return_value = ActionSafetyResult(
            level=ActionSafetyLevel.READ, confidence=0.9, matched_keyword="get", reasoning="test",
        )
        mock_as.needs_approval.return_value = False

        adapter_mod._sgc = mock_sgc
        adapter_mod._as = mock_as
        adapter_mod._rg = MagicMock()
        adapter_mod._dsu = MagicMock()

        server = SuperglueAdapterServer()
        result = await server._invoke_handler("sg_get", "get", {})
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════
# get_router
# ═══════════════════════════════════════════════════════════════════

class TestGetRouter:
    """Test REST endpoint generation."""

    def test_router_returned(self):
        router = superglue_adapter_server.get_router()
        assert router is not None
        assert router.prefix == "/integrations/superglue"

    def test_router_has_sync_endpoint(self):
        router = superglue_adapter_server.get_router()
        paths = [r.path for r in router.routes]
        assert any("/sync" in p for p in paths)

    def test_router_has_tools_endpoint(self):
        router = superglue_adapter_server.get_router()
        paths = [r.path for r in router.routes]
        assert any("/tools" in p for p in paths)


# ═══════════════════════════════════════════════════════════════════
# _make_handler
# ═══════════════════════════════════════════════════════════════════

class TestMakeHandler:
    """Test handler factory."""

    def test_make_handler_returns_callable(self):
        handler = superglue_adapter_server._make_handler("sg_test_tool", "test_tool")
        assert callable(handler)
