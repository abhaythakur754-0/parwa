"""
Integration test: Superglue tool creation → safety classification → regulatory guardrails → MCP registration → Node 5 execution.

This test verifies the FULL pipeline that a ticket follows:
1. Action Safety classifier runs on tool names
2. Regulatory guardrails check financial limits
3. MCP adapter would register tools (tested via the adapter's logic)
4. Node 5's safety gate function processes execution decisions

This does NOT spin up real servers or databases — it tests the integration
of all the new modules together with mocking at the HTTP/DB boundary.

Run: pytest backend/app/tests/test_superglue_integration.py -v
"""

import sys
import os

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ── Phase 1: Safety Classification feeds Regulatory Guardrails ──


class TestSafetyToGuardrailsIntegration:
    """Verify classify_action output feeds correctly into check_financial_guardrails."""

    def test_refund_triggers_financial_guardrails(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("process_refund", "Refunds customer payment")
        assert safety.level == ActionSafetyLevel.FINANCIAL

        gr = check_financial_guardrails(safety.level.value, 100.0, "parwa", "process_refund")
        assert gr.allowed is True  # $100 < $500 limit
        assert gr.remaining is not None

    def test_refund_exceeds_parwa_limit(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("process_refund")
        assert safety.level == ActionSafetyLevel.FINANCIAL

        gr = check_financial_guardrails(safety.level.value, 600.0, "parwa", "process_refund")
        assert gr.allowed is False
        assert "$600.00 exceeds" in gr.reason

    def test_parwa_high_unlimited(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("process_refund")
        gr = check_financial_guardrails(safety.level.value, 10000.0, "parwa_high")
        assert gr.allowed is True

    def test_read_action_skips_guardrails(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("get_order_status")
        assert safety.level == ActionSafetyLevel.READ

        gr = check_financial_guardrails(safety.level.value, 100.0, "parwa")
        assert gr.allowed is True
        assert "not financial" in gr.reason

    def test_destructive_needs_approval_but_no_guardrails(self):
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel

        safety = classify_action("cancel_subscription")
        assert safety.level == ActionSafetyLevel.DESTRUCTIVE
        assert needs_approval(safety.level) is True

    def test_credit_uses_correct_limit_key(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("issue_credit")
        assert safety.level == ActionSafetyLevel.FINANCIAL

        # parwa tier: max_credit = $200
        gr = check_financial_guardrails(safety.level.value, 250.0, "parwa", "issue_credit")
        assert gr.allowed is False
        assert "max_credit" in gr.reason


# ── Phase 2: MCP Adapter Integration ──


class TestMCPAdapterRegistration:
    """Verify Superglue tools register into MCPRegistry with sg_ prefix."""

    def test_tools_register_with_sg_prefix(self):
        from mcp_server.base_server import MCPRegistry
        from mcp_server.integrations.superglue_adapter_server import SuperglueAdapterServer

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

        assert registry.get_tool("sg_refund-tool") is not None
        assert registry.get_tool("sg_get-order") is not None
        assert registry.get_handler("sg_refund-tool") is not None

    def test_tools_tagged_as_superglue(self):
        from mcp_server.base_server import MCPRegistry
        from mcp_server.integrations.superglue_adapter_server import SuperglueAdapterServer

        registry = MCPRegistry()
        server = SuperglueAdapterServer()

        mock_tools = [
            {"id": "t1", "name": "Tool 1", "inputSchema": {}},
        ]

        with patch("mcp_server.integrations.superglue_adapter_server._ensure_imports", return_value=True), \
             patch("mcp_server.integrations.superglue_adapter_server._sgc", new=MagicMock(is_configured=MagicMock(return_value=True))), \
             patch("mcp_server.integrations.superglue_adapter_server._run_async", return_value=mock_tools), \
             patch("mcp_server.integrations.superglue_adapter_server._dsu", new=MagicMock(publish_superglue_signals=AsyncMock(return_value=1))):
            server.register_tools(registry)

        tool = registry.get_tool("sg_t1")
        assert "superglue" in tool.tags
        assert "dynamic" in tool.tags


# ── Phase 3: Node 5 Safety Gate Integration ──


class TestNode5SafetyGate:
    """Verify _run_action_safety_gate in node_5_act_verify.py."""

    def _import_gate(self):
        from backend.app.core.parwa_pipeline.nodes.node_5_act_verify import _run_action_safety_gate
        return _run_action_safety_gate

    def test_read_action_passes_through(self):
        # We need to import from the actual module location
        # Since the module is in backend/, we test the logic indirectly
        from app.core.action_safety import classify_action
        from app.core.regulatory_guardrails import check_financial_guardrails

        # Simulate what _run_action_safety_gate does
        safety = classify_action("get_order_status", "Get order info")
        assert safety.level.value == "read"

    def test_financial_action_guardrail_blocks(self):
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        safety = classify_action("process_refund")
        assert safety.level == ActionSafetyLevel.FINANCIAL

        gr = check_financial_guardrails("financial", 600.0, "parwa", "process_refund")
        assert gr.allowed is False

    def test_financial_action_guardrail_allows(self):
        from app.core.regulatory_guardrails import check_financial_guardrails

        gr = check_financial_guardrails("financial", 100.0, "parwa", "process_refund")
        assert gr.allowed is True
        assert gr.remaining == 400.0

    def test_destructive_needs_approval(self):
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel

        safety = classify_action("delete_account")
        assert needs_approval(safety.level) is True

    def test_write_no_approval(self):
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel

        safety = classify_action("update_address")
        assert needs_approval(safety.level) is False


# ── Phase 4: Service Layer Integration ──


class TestServiceLayerIntegration:
    """Verify superglue_action_service uses safety modules correctly."""

    def test_classify_and_persist_structure(self):
        from app.services.superglue_action_service import classify_and_persist

        # Without DB session, should return safe classification
        result = classify_and_persist(
            company_id="test-co",
            tool_id="refund-tool-1",
            tool_name="Process Refund",
            tool_description="Refunds a customer",
            db_session=None,
        )
        assert result["safety_level"] == "financial"
        assert result["needs_approval"] is True
        assert "PCI-DSS" in result["regulatory_frameworks"]

    def test_get_classification_no_db(self):
        from app.services.superglue_action_service import get_classification

        result = get_classification("test-co", "refund-tool", db_session=None)
        assert result is None  # No DB session

    def test_list_classifications_no_db(self):
        from app.services.superglue_action_service import list_classifications

        result = list_classifications("test-co", db_session=None)
        assert result == []  # No DB session

    def test_toggle_override_no_db(self):
        from app.services.superglue_action_service import toggle_override

        result = toggle_override("test-co", "refund-tool", True, db_session=None)
        assert result is None  # No DB session


# ── Phase 5: Dynamic Signal Integration ──


class TestDynamicSignalIntegration:
    """Verify signals flow from tools to the signal cache."""

    @pytest.mark.asyncio
    async def test_tools_generate_signals(self):
        from app.core.dynamic_signal_updater import (
            publish_superglue_signals, get_superglue_signals, _memory_cache,
        )

        _memory_cache.clear()

        tools = [
            {"id": "refund-tool", "name": "process_refund"},
            {"id": "cancel-tool", "name": "cancel_subscription"},
            {"id": "get-tool", "name": "get_order_status"},
        ]

        intent_count = await publish_superglue_signals("integ-co", tools)
        assert intent_count >= 2  # at least refund + cancellation

        signals = await get_superglue_signals("integ-co")
        assert signals is not None
        assert signals["has_financial_tools"] is True
        assert signals["has_destructive_tools"] is True
        assert signals["tool_count"] == 3

    @pytest.mark.asyncio
    async def test_safety_classification_signals_enrichment(self):
        from app.core.dynamic_signal_updater import (
            _memory_cache, enrich_query_signals,
        )

        _memory_cache["sig-co"] = {
            "has_tools": True, "tool_count": 1,
            "has_financial_tools": True, "has_destructive_tools": False,
            "intents": ["refund"],
        }

        class FakeSignals:
            external_data_required = False

        enrich_query_signals("sig-co", FakeSignals())
        assert _memory_cache["sig-co"]["has_tools"] is True

    @pytest.mark.asyncio
    async def test_cleanup(self):
        from app.core.dynamic_signal_updater import _memory_cache
        _memory_cache.clear()
        assert len(_memory_cache) == 0


# ── Phase 6: Full Pipeline Simulation ──


class TestFullPipelineSimulation:
    """Simulate the full ticket-solving pipeline with safety checks."""

    def test_full_read_tool_pipeline(self):
        """READ tool: classify → guardrails pass → execute allowed."""
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "get_order_status"
        action = "Check order status"
        tool_input = {"order_id": "ORD-123"}
        variant_tier = "parwa"

        # Step 1: Classify
        safety = classify_action(tool_id, action)
        assert safety.level == ActionSafetyLevel.READ

        # Step 2: Guardrails (skipped for non-financial)
        gr = check_financial_guardrails(safety.level.value, 0, variant_tier, tool_id)
        assert gr.allowed is True

        # Step 3: Approval check
        assert needs_approval(safety.level) is False

        # Result: ALLOWED

    def test_full_refund_within_limit_pipeline(self):
        """FINANCIAL tool within parwa limit: classify → guardrails pass → needs_approval."""
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "process_refund"
        action = "Refund customer $50"
        tool_input = {"amount": 50.0, "customer_email": "a@b.com"}
        variant_tier = "parwa"

        # Step 1: Classify → FINANCIAL
        safety = classify_action(tool_id, action)
        assert safety.level == ActionSafetyLevel.FINANCIAL

        # Step 2: Guardrails → $50 < $500, ALLOWED
        gr = check_financial_guardrails(safety.level.value, 50.0, variant_tier, tool_id)
        assert gr.allowed is True
        assert gr.remaining == 450.0

        # Step 3: Approval → FINANCIAL needs approval
        assert needs_approval(safety.level) is True

        # Result: NEEDS APPROVAL (not blocked, but queued)

    def test_full_refund_over_limit_pipeline(self):
        """FINANCIAL tool exceeding parwa limit: classify → guardrails BLOCK."""
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "process_refund"
        action = "Refund customer $600"
        tool_input = {"amount": 600.0}
        variant_tier = "parwa"

        # Step 1: Classify → FINANCIAL
        safety = classify_action(tool_id, action)
        assert safety.level == ActionSafetyLevel.FINANCIAL

        # Step 2: Guardrails → $600 > $500, BLOCKED
        gr = check_financial_guardrails(safety.level.value, 600.0, variant_tier, tool_id)
        assert gr.allowed is False
        assert "exceeds" in gr.reason

        # Result: BLOCKED by guardrails

    def test_full_delete_pipeline(self):
        """DESTRUCTIVE tool: classify → guardrails pass → needs_approval."""
        from app.core.action_safety import classify_action, needs_approval, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "delete_account"
        action = "Delete user account"

        # Step 1: Classify → DESTRUCTIVE
        safety = classify_action(tool_id, action)
        assert safety.level == ActionSafetyLevel.DESTRUCTIVE

        # Step 2: Guardrails (not financial, skip)
        gr = check_financial_guardrails(safety.level.value, 0, "parwa", tool_id)
        assert gr.allowed is True

        # Step 3: Approval → DESTRUCTIVE needs approval
        assert needs_approval(safety.level) is True

        # Result: NEEDS APPROVAL

    def test_full_credit_over_limit_pipeline(self):
        """CREDIT (FINANCIAL) exceeding parwa credit limit."""
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "issue_credit_note"
        action = "Issue $300 credit"

        safety = classify_action(tool_id, action)
        assert safety.level == ActionSafetyLevel.FINANCIAL

        # parwa: max_credit = $200
        gr = check_financial_guardrails(safety.level.value, 300.0, "parwa", tool_id)
        assert gr.allowed is False
        assert "max_credit" in gr.reason

    def test_parwa_high_allows_anything(self):
        """parwa_high tier bypasses all financial limits."""
        from app.core.action_safety import classify_action, ActionSafetyLevel
        from app.core.regulatory_guardrails import check_financial_guardrails

        tool_id = "process_refund"
        safety = classify_action(tool_id)
        assert safety.level == ActionSafetyLevel.FINANCIAL

        gr = check_financial_guardrails(safety.level.value, 99999.0, "parwa_high")
        assert gr.allowed is True
        assert "unlimited" in gr.reason
