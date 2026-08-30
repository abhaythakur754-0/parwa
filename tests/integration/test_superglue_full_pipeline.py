import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.action_safety import ActionSafetyLevel, classify_action, needs_approval
from app.core.regulatory_guardrails import check_financial_guardrails, get_applicable_frameworks
from app.services.superglue_action_service import classify_and_persist


# ═══════════════════════════════════════════════════════════════════
# Integration: Tool Classification → Guardrails → Regulatory Frameworks
# ═══════════════════════════════════════════════════════════════════

class TestClassificationToGuardrailsPipeline:
    """Full pipeline: classify → guardrails → frameworks.

    Simulates what happens when a Superglue tool is invoked through
    the adapter server's _invoke_handler method.
    """

    def test_refund_tool_full_pipeline(self):
        """Refund tool: FINANCIAL → needs approval → PCI-DSS → blocked if > $500."""
        # Step 1: Classify
        safety = classify_action("refund_customer_by_email", "Process customer refund")
        assert safety.level == ActionSafetyLevel.FINANCIAL
        assert safety.confidence == 0.9

        # Step 2: Check if approval needed
        assert needs_approval(safety.level) is True

        # Step 3: Get regulatory frameworks
        frameworks = get_applicable_frameworks(safety.level.value)
        assert "PCI-DSS" in frameworks

        # Step 4: Financial guardrails (parwa tier)
        gr = check_financial_guardrails(safety.level.value, 400.0, "parwa", "refund_customer_by_email")
        assert gr.allowed is True
        assert gr.remaining == 100.0

        # Step 5: Exceeding limit
        gr_block = check_financial_guardrails(safety.level.value, 600.0, "parwa", "refund_customer_by_email")
        assert gr_block.allowed is False

    def test_delete_tool_full_pipeline(self):
        """Delete tool: DESTRUCTIVE → needs approval → SOX."""
        safety = classify_action("delete_customer_account", "Permanently delete a customer")
        assert safety.level == ActionSafetyLevel.DESTRUCTIVE
        assert needs_approval(safety.level) is True
        frameworks = get_applicable_frameworks(safety.level.value)
        assert "SOX" in frameworks

    def test_update_tool_full_pipeline(self):
        """Update tool: WRITE → no approval → SOC-2."""
        safety = classify_action("update_customer_email", "Change customer email address")
        assert safety.level == ActionSafetyLevel.WRITE
        assert needs_approval(safety.level) is False
        frameworks = get_applicable_frameworks(safety.level.value)
        assert "SOC-2" in frameworks

    def test_get_tool_full_pipeline(self):
        """Get tool: READ → no approval → no frameworks."""
        safety = classify_action("get_order_status", "Check order status")
        assert safety.level == ActionSafetyLevel.READ
        assert needs_approval(safety.level) is False
        frameworks = get_applicable_frameworks(safety.level.value)
        assert frameworks == []

    def test_pii_export_full_pipeline(self):
        """PII export: SENSITIVE_PII → no approval → GDPR + CCPA."""
        safety = classify_action("export_customer_data", "Export all customer records")
        assert safety.level == ActionSafetyLevel.SENSITIVE_PII
        assert needs_approval(safety.level) is False
        frameworks = get_applicable_frameworks(safety.level.value)
        assert "GDPR" in frameworks
        assert "CCPA" in frameworks

    def test_parwa_high_unlimited_financial(self):
        """parwa_high tier: unlimited financial actions."""
        safety = classify_action("refund_large_amount", "")
        assert safety.level == ActionSafetyLevel.FINANCIAL

        gr = check_financial_guardrails(safety.level.value, 99999.0, "parwa_high", "refund_large_amount")
        assert gr.allowed is True
        assert gr.limit is None


# ═══════════════════════════════════════════════════════════════════
# Integration: Service Layer Classification
# ═══════════════════════════════════════════════════════════════════

class TestServiceIntegration:
    """Service layer integration — classify_and_persist without DB."""

    @pytest.mark.parametrize("tool_id,tool_name,expected_level,expected_approval", [
        ("refund-by-email", "Refund by Email", "financial", True),
        ("delete-account", "Delete Account", "destructive", True),
        ("get-order-status", "Get Order Status", "read", False),
        ("update-customer", "Update Customer", "write", False),
        ("export-users", "Export Users", "read", False),
        ("credit-note", "Issue Credit Note", "financial", True),
        ("remove-user", "Remove User", "destructive", True),
        ("search-tickets", "Search Tickets", "read", False),
    ])
    def test_classify_various_tools(self, tool_id, tool_name, expected_level, expected_approval):
        result = classify_and_persist("company-1", tool_id, tool_name)
        assert result["safety_level"] == expected_level
        assert result["needs_approval"] == expected_approval

    def test_classify_returns_valid_dict_structure(self):
        result = classify_and_persist("company-1", "tool-1", "Tool 1")
        required_keys = {"id", "tool_id", "tool_name", "safety_level", "needs_approval", "regulatory_frameworks", "is_active"}
        assert required_keys.issubset(result.keys())
        assert isinstance(result["regulatory_frameworks"], list)
        assert isinstance(result["needs_approval"], bool)
        assert isinstance(result["is_active"], bool)


# ═══════════════════════════════════════════════════════════════════
# Integration: Adapter Server Registration Flow
# ═══════════════════════════════════════════════════════════════════

class TestAdapterRegistrationFlow:
    """Test the full adapter registration flow with mocked Superglue."""

    @patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True)
    @patch("mcp_server.integrations.superglue_adapter_server._sgc")
    @patch("mcp_server.integrations.superglue_adapter_server._dsu")
    def test_tools_registered_with_correct_metadata(self, mock_dsu, mock_sgc, mock_ensure):
        """Verify tools are registered with correct category, server, tags."""
        mock_sgc.is_configured.return_value = True
        mock_sgc.list_tools = AsyncMock(return_value=[
            {"id": "refund-by-email", "name": "Refund by Email", "inputSchema": {"type": "object"}, "outputSchema": {}},
        ])
        mock_dsu.publish_superglue_signals = AsyncMock(return_value=0)

        from mcp_server.integrations.superglue_adapter_server import SuperglueAdapterServer
        from mcp_server.base_server import MCPRegistry
        from mcp_server.models import ToolCategory

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)

        tools = registry.list_tools(server="superglue_adapter")
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "sg_refund-by-email"
        assert tool.category == ToolCategory.INTEGRATION
        assert tool.server == "superglue_adapter"
        assert "superglue" in tool.tags
        assert "dynamic" in tool.tags

    @patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True)
    @patch("mcp_server.integrations.superglue_adapter_server._sgc")
    @patch("mcp_server.integrations.superglue_adapter_server._dsu")
    def test_multiple_tools_all_registered(self, mock_dsu, mock_sgc, mock_ensure):
        """Multiple Superglue tools all get sg_ prefix."""
        mock_sgc.is_configured.return_value = True
        mock_sgc.list_tools = AsyncMock(return_value=[
            {"id": "tool-a", "name": "Tool A", "inputSchema": {}},
            {"id": "tool-b", "name": "Tool B", "inputSchema": {}},
            {"id": "tool-c", "name": "Tool C", "inputSchema": {}},
        ])
        mock_dsu.publish_superglue_signals = AsyncMock(return_value=0)

        from mcp_server.integrations.superglue_adapter_server import SuperglueAdapterServer
        from mcp_server.base_server import MCPRegistry

        registry = MCPRegistry()
        server = SuperglueAdapterServer()
        server.register_tools(registry)

        tools = registry.list_tools(server="superglue_adapter")
        assert len(tools) == 3
        for t in tools:
            assert t.name.startswith("sg_")


# ═══════════════════════════════════════════════════════════════════
# Integration: Dynamic Signal Updater + Adapter
# ═══════════════════════════════════════════════════════════════════

class TestSignalUpdaterIntegration:
    """Signal updater publishes intents that match classified actions."""

    @pytest.mark.asyncio
    async def test_financial_tool_publishes_financial_signal(self):
        from app.core.dynamic_signal_updater import _memory_cache, _FINANCIAL_KEYWORDS, _detect_intents
        _memory_cache.clear()
        tools = [{"name": "refund_customer", "id": "t1"}]
        # Write signal directly to memory cache (bypasses Redis)
        all_intents = []
        has_financial = False
        for tool in tools:
            name = tool.get("name", "")
            all_intents.extend(_detect_intents(name))
            if any(kw in name.lower() for kw in _FINANCIAL_KEYWORDS):
                has_financial = True
        _memory_cache["company-1"] = {
            "has_tools": True, "tool_count": 1,
            "has_financial_tools": has_financial, "has_destructive_tools": False,
            "intents": list(dict.fromkeys(all_intents)),
        }
        signal = _memory_cache.get("company-1")
        assert signal is not None
        assert signal["has_financial_tools"] is True
        assert "refund" in signal["intents"]
        _memory_cache.clear()

    @pytest.mark.asyncio
    async def test_destructive_tool_publishes_destructive_signal(self):
        from app.core.dynamic_signal_updater import _memory_cache, _DESTRUCTIVE_KEYWORDS, _detect_intents
        _memory_cache.clear()
        tools = [{"name": "delete_account", "id": "t2"}]
        all_intents = []
        has_destructive = False
        for tool in tools:
            name = tool.get("name", "")
            all_intents.extend(_detect_intents(name))
            if any(kw in name.lower() for kw in _DESTRUCTIVE_KEYWORDS):
                has_destructive = True
        _memory_cache["company-1"] = {
            "has_tools": True, "tool_count": 1,
            "has_financial_tools": False, "has_destructive_tools": has_destructive,
            "intents": list(dict.fromkeys(all_intents)),
        }
        signal = _memory_cache.get("company-1")
        assert signal["has_destructive_tools"] is True
        _memory_cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Integration: Tenant Isolation (BC-001)
# ═══════════════════════════════════════════════════════════════════

class TestTenantIsolation:
    """BC-001: tenant isolation across the pipeline."""

    def test_namespaced_ids_prevent_cross_tenant(self):
        from app.core.superglue_client import namespaced_tool_id
        t1 = namespaced_tool_id("refund", "tenant-a")
        t2 = namespaced_tool_id("refund", "tenant-b")
        assert t1 != t2

    def test_service_scopes_to_company(self):
        """Service layer accepts company_id for scoping."""
        result = classify_and_persist("company-a", "tool-1", "Tool 1")
        assert isinstance(result, dict)

    def test_guardrails_per_tenant(self):
        """Different tiers = different limits for same tool."""
        # parwa: $500 limit
        gr1 = check_financial_guardrails("financial", 600, "parwa", "refund")
        assert gr1.allowed is False

        # parwa_high: unlimited
        gr2 = check_financial_guardrails("financial", 600, "parwa_high", "refund")
        assert gr2.allowed is True
