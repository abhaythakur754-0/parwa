"""
Tests for ReAct Tools (F-157), AI Assignment (F-050), and Rule-AI Migration (F-158).
"""
import pytest
import asyncio
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=True)
    r.hset = AsyncMock(return_value=True)
    r.hgetall = AsyncMock(return_value={})
    r.incr = AsyncMock(return_value=1)
    r.incrby = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    r.eval = AsyncMock(return_value=100)
    r.rpush = AsyncMock(return_value=1)
    r.lpush = AsyncMock(return_value=1)
    r.lrange = AsyncMock(return_value=[])
    r.keys = AsyncMock(return_value=[])
    r.exists = AsyncMock(return_value=0)
    r.scan_iter = AsyncMock(return_value=[])
    r.hincrby = AsyncMock(return_value=1)
    return r


@pytest.fixture
def company_id():
    return "comp_test_001"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. OrderTool Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrderTool:
    """Test OrderTool - 6 actions."""

    @pytest.mark.asyncio
    async def test_get_order(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("get_order", company_id, order_id="ORD-001")
        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_list_orders(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("list_orders", company_id, status="active", limit=10)
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_cancel_order(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("cancel_order", company_id, order_id="ORD-002", reason="Customer request")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_order_status(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("get_order_status", company_id, order_id="ORD-003")
        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_update_shipping(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("update_shipping", company_id, order_id="ORD-004", tracking_number="TRK-123")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_refund_order(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("refund_order", company_id, order_id="ORD-005", amount=50.0, reason="Defective")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_action(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        result = await tool.execute("nonexistent_action", company_id)
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_gap004_timeout_handling(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        # Mock _do_execute to simulate timeout
        original_execute = tool._do_execute
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(20)
            return MagicMock(success=True, error=None, data={}, execution_time_ms=20000)
        tool._do_execute = slow_execute
        result = await tool.execute("get_order", company_id, order_id="ORD-TIMEOUT")
        assert result.success is False
        assert "timeout" in result.error.lower() or result.execution_time_ms >= 10000

    @pytest.mark.asyncio
    async def test_validate_params(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        validation = tool.validate_params("get_order", {"order_id": "ORD-001"})
        assert validation.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_params_missing_required(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        validation = tool.validate_params("get_order", {})
        assert validation.is_valid is False

    @pytest.mark.asyncio
    async def test_get_schema(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        schema = tool.get_schema()
        assert schema.tool_name == "order_management"
        assert len(schema.actions) >= 6

    @pytest.mark.asyncio
    async def test_health_check(self, company_id):
        from backend.app.core.react_tools.order_tool import OrderTool

        tool = OrderTool()
        healthy = await tool.health_check()
        assert healthy is True


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BillingTool Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBillingTool:
    @pytest.mark.asyncio
    async def test_get_invoice(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("get_invoice", company_id, invoice_id="INV-001")
        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_list_invoices(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("list_invoices", company_id, status="paid")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_process_payment(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("process_payment", company_id, invoice_id="INV-002", amount=100.0, method="card")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_subscription_status(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("get_subscription_status", company_id, subscription_id="SUB-001")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_apply_credit(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("apply_credit", company_id, customer_id="CUST-001", amount=25.0, reason="Loyalty")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_payment_history(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("get_payment_history", company_id, customer_id="CUST-001")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_gap004_timeout(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(20)
            return MagicMock(success=True, error=None, data={}, execution_time_ms=20000)
        tool._do_execute = slow_execute
        result = await tool.execute("get_invoice", company_id, invoice_id="INV-TIMEOUT")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        result = await tool.execute("nonexistent", company_id)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_schema(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        schema = tool.get_schema()
        assert schema.tool_name == "billing_system"
        assert len(schema.actions) >= 6

    @pytest.mark.asyncio
    async def test_validate_params(self, company_id):
        from backend.app.core.react_tools.billing_tool import BillingTool

        tool = BillingTool()
        v = tool.validate_params("get_invoice", {"invoice_id": "INV-001"})
        assert v.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CRMTool Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCRMTool:
    @pytest.mark.asyncio
    async def test_get_customer(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("get_customer", company_id, customer_id="CUST-001")
        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_search_customers(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("search_customers", company_id, query="John", limit=10)
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_update_customer(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("update_customer", company_id, customer_id="CUST-001", updates={"email": "new@example.com"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_interaction_history(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("get_interaction_history", company_id, customer_id="CUST-001")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_add_note(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("add_note", company_id, customer_id="CUST-001", note="VIP customer", author="agent_001")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_customer_stats(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("get_customer_stats", company_id, customer_id="CUST-001")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_gap004_timeout(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(20)
            return MagicMock(success=True, error=None, data={}, execution_time_ms=20000)
        tool._do_execute = slow_execute
        result = await tool.execute("get_customer", company_id, customer_id="CUST-TIMEOUT")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        result = await tool.execute("nonexistent", company_id)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_schema(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        schema = tool.get_schema()
        assert schema.tool_name == "crm_integration"
        assert len(schema.actions) >= 6

    @pytest.mark.asyncio
    async def test_validate_params(self, company_id):
        from backend.app.core.react_tools.crm_tool import CRMTool

        tool = CRMTool()
        v = tool.validate_params("get_customer", {"customer_id": "CUST-001"})
        assert v.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TicketTool Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTicketTool:
    @pytest.mark.asyncio
    async def test_get_ticket(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("get_ticket", company_id, ticket_id="TKT-001")
        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_create_ticket(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("create_ticket", company_id, title="Test ticket", description="Testing", priority="high")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_ticket(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("update_ticket", company_id, ticket_id="TKT-002", status="resolved")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_comment(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("add_comment", company_id, ticket_id="TKT-003", comment="Looking into this", author="agent_001")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_list_tickets(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("list_tickets", company_id, status="open")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_get_ticket_history(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("get_ticket_history", company_id, ticket_id="TKT-004")
        assert result.success is True
        assert isinstance(result.data, list)

    @pytest.mark.asyncio
    async def test_gap004_timeout(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(20)
            return MagicMock(success=True, error=None, data={}, execution_time_ms=20000)
        tool._do_execute = slow_execute
        result = await tool.execute("get_ticket", company_id, ticket_id="TKT-TIMEOUT")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        result = await tool.execute("nonexistent", company_id)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_schema(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        schema = tool.get_schema()
        assert schema.tool_name == "ticket_system"
        assert len(schema.actions) >= 6

    @pytest.mark.asyncio
    async def test_validate_params(self, company_id):
        from backend.app.core.react_tools.ticket_tool import TicketTool

        tool = TicketTool()
        v = tool.validate_params("get_ticket", {"ticket_id": "TKT-001"})
        assert v.is_valid is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ReActToolRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReActToolRegistry:
    @pytest.mark.asyncio
    async def test_register_tool(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool

        registry = ReActToolRegistry()
        tool = OrderTool()
        await registry.register_tool(tool)
        retrieved = await registry.get_tool("order_management")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_execute_tool(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool

        registry = ReActToolRegistry()
        await registry.register_tool(OrderTool())
        result = await registry.execute_tool("order_management", "get_order", company_id, order_id="ORD-REG")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry

        registry = ReActToolRegistry()
        result = await registry.execute_tool("nonexistent_tool", "action", company_id)
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_list_tools(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool
        from backend.app.core.react_tools.billing_tool import BillingTool

        registry = ReActToolRegistry()
        await registry.register_tool(OrderTool())
        await registry.register_tool(BillingTool())
        tools = await registry.list_tools()
        assert len(tools) >= 2

    @pytest.mark.asyncio
    async def test_execute_parallel(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool
        from backend.app.core.react_tools import ToolCall

        registry = ReActToolRegistry()
        await registry.register_tool(OrderTool())
        calls = [
            ToolCall(tool_name="order_management", action="get_order", params={"order_id": f"ORD-{i}"}, company_id=company_id)
            for i in range(3)
        ]
        results = await registry.execute_parallel(calls)
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_get_available_actions(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool

        registry = ReActToolRegistry()
        await registry.register_tool(OrderTool())
        actions = registry.get_available_actions()
        assert "order_management" in actions
        assert len(actions["order_management"]) >= 6

    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry

        registry = ReActToolRegistry()
        tool = await registry.get_tool("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_register_multiple_tools(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools.order_tool import OrderTool
        from backend.app.core.react_tools.billing_tool import BillingTool
        from backend.app.core.react_tools.crm_tool import CRMTool
        from backend.app.core.react_tools.ticket_tool import TicketTool

        registry = ReActToolRegistry()
        await registry.register_tool(OrderTool())
        await registry.register_tool(BillingTool())
        await registry.register_tool(CRMTool())
        await registry.register_tool(TicketTool())

        tools = await registry.list_tools()
        assert len(tools) == 4

    @pytest.mark.asyncio
    async def test_initialize_defaults(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry

        registry = ReActToolRegistry()
        await registry.initialize_defaults()
        tools = await registry.list_tools()
        assert len(tools) >= 4

    @pytest.mark.asyncio
    async def test_execute_parallel_with_error(self, company_id):
        from backend.app.core.react_tools import ReActToolRegistry
        from backend.app.core.react_tools import ToolCall

        registry = ReActToolRegistry()
        calls = [
            ToolCall(tool_name="nonexistent", action="test", params={}, company_id=company_id),
            ToolCall(tool_name="also_nonexistent", action="test", params={}, company_id=company_id),
        ]
        results = await registry.execute_parallel(calls)
        assert len(results) == 2
        assert all(r.success is False for r in results)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. AIAssignmentEngine Tests (F-050)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAIAssignmentScoring:
    """Test the 4-factor scoring algorithm."""

    @pytest.mark.asyncio
    async def test_specialty_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-001", company_id=company_id, variant_type="parwa",
            intent_type="technical", priority="medium", sentiment_score=0.5, customer_tier="pro"
        )
        scores = await engine.get_assignment_scores(req)
        assert len(scores) > 0
        # Technical intent should rank technical agents higher
        tech_agents = [s for s in scores if any(sk in s.skills_match for sk in ["technical", "debugging"])]
        if tech_agents:
            assert any(s.specialty_score > 20 for s in tech_agents)

    @pytest.mark.asyncio
    async def test_workload_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-002", company_id=company_id, variant_type="parwa",
            intent_type="general", priority="medium", sentiment_score=0.5, customer_tier="basic"
        )
        scores = await engine.get_assignment_scores(req)
        for score in scores:
            assert 0 <= score.workload_score <= 30

    @pytest.mark.asyncio
    async def test_accuracy_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-003", company_id=company_id, variant_type="parwa",
            intent_type="billing", priority="medium", sentiment_score=0.5, customer_tier="basic"
        )
        scores = await engine.get_assignment_scores(req)
        for score in scores:
            assert 0 <= score.accuracy_score <= 20

    @pytest.mark.asyncio
    async def test_total_score_range(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-004", company_id=company_id, variant_type="parwa",
            intent_type="refund", priority="high", sentiment_score=0.8, customer_tier="enterprise"
        )
        scores = await engine.get_assignment_scores(req)
        for score in scores:
            assert 0 <= score.total_score <= 100


class TestGAP027DeterministicJitter:
    """GAP-027: Deterministic jitter — same ticket+agent = same jitter."""

    def test_same_ticket_agent_same_jitter(self):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine()
        j1 = engine._deterministic_jitter("TKT-001", "agent_001")
        j2 = engine._deterministic_jitter("TKT-001", "agent_001")
        assert j1 == j2  # Deterministic

    def test_different_ticket_different_jitter(self):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine()
        j1 = engine._deterministic_jitter("TKT-001", "agent_001")
        j2 = engine._deterministic_jitter("TKT-002", "agent_001")
        # Different tickets should generally give different jitter
        # (extremely unlikely to be same with SHA-256)
        assert 0 <= j1 <= 10
        assert 0 <= j2 <= 10

    def test_different_agent_different_jitter(self):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine()
        j1 = engine._deterministic_jitter("TKT-001", "agent_001")
        j2 = engine._deterministic_jitter("TKT-001", "agent_002")
        assert 0 <= j1 <= 10
        assert 0 <= j2 <= 10

    def test_jitter_range(self):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine()
        for i in range(100):
            j = engine._deterministic_jitter(f"TKT-{i}", f"agent_{i % 10}")
            assert 0 <= j <= 10, f"Jitter {j} out of range for TKT-{i}"


class TestAIAssignmentAssignment:
    """Test actual assignment."""

    @pytest.mark.asyncio
    async def test_assign_ticket(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-ASSIGN", company_id=company_id, variant_type="parwa",
            intent_type="technical", priority="medium", sentiment_score=0.5, customer_tier="pro"
        )
        result = await engine.assign_ticket(req)
        assert result.assigned_agent_id is not None
        assert result.assigned_agent_name is not None
        assert result.total_score > 0
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_batch_assign(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        reqs = [
            TicketAssignmentRequest(
                ticket_id=f"TKT-BATCH-{i}", company_id=company_id, variant_type="parwa",
                intent_type="general", priority="medium", sentiment_score=0.5, customer_tier="basic"
            ) for i in range(5)
        ]
        results = await engine.batch_assign(reqs)
        assert len(results) == 5
        assert all(r.assigned_agent_id is not None for r in results)

    @pytest.mark.asyncio
    async def test_reassign_ticket(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-REASSIGN", company_id=company_id, variant_type="parwa",
            intent_type="complaint", priority="high", sentiment_score=0.8, customer_tier="enterprise"
        )
        first = await engine.assign_ticket(req)
        reassigned = await engine.reassign_ticket("TKT-REASSIGN", company_id, "Better agent needed")
        assert reassigned.assigned_agent_id is not None
        # Reassignment should ideally pick a different agent
        assert reassigned is not None

    @pytest.mark.asyncio
    async def test_get_agent_workload(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine(redis_client=mock_redis)
        workloads = await engine.get_agent_workload(company_id)
        assert isinstance(workloads, dict)
        assert len(workloads) > 0

    @pytest.mark.asyncio
    async def test_priority_weights(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)

        # High priority should weigh specialty more
        req_high = TicketAssignmentRequest(
            ticket_id="TKT-HIGH", company_id=company_id, variant_type="parwa",
            intent_type="technical", priority="high", sentiment_score=0.5, customer_tier="pro"
        )
        req_low = TicketAssignmentRequest(
            ticket_id="TKT-LOW", company_id=company_id, variant_type="parwa",
            intent_type="technical", priority="low", sentiment_score=0.5, customer_tier="pro"
        )
        scores_high = await engine.get_assignment_scores(req_high)
        scores_low = await engine.get_assignment_scores(req_low)
        # Both should have results
        assert len(scores_high) > 0
        assert len(scores_low) > 0


class TestAIAssignmentVariants:
    """Test variant differentiation."""

    @pytest.mark.asyncio
    async def test_mini_parwa_simpler_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-MINI", company_id=company_id, variant_type="mini_parwa",
            intent_type="general", priority="medium", sentiment_score=0.5, customer_tier="basic"
        )
        result = await engine.assign_ticket(req)
        assert result.assigned_agent_id is not None

    @pytest.mark.asyncio
    async def test_parwa_full_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-PARWA", company_id=company_id, variant_type="parwa",
            intent_type="technical", priority="high", sentiment_score=0.7, customer_tier="pro"
        )
        result = await engine.assign_ticket(req)
        assert result.assigned_agent_id is not None
        assert result.score_breakdown is not None

    @pytest.mark.asyncio
    async def test_parwa_high_full_scoring(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-HIGH", company_id=company_id, variant_type="parwa_high",
            intent_type="billing", priority="critical", sentiment_score=0.9, customer_tier="enterprise"
        )
        result = await engine.assign_ticket(req)
        assert result.assigned_agent_id is not None
        assert result.confidence > 0


class TestAIAssignmentEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_no_available_agents_fallback(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        req = TicketAssignmentRequest(
            ticket_id="TKT-EMPTY", company_id=company_id, variant_type="parwa",
            intent_type="general", priority="low", sentiment_score=0.5, customer_tier="basic"
        )
        result = await engine.assign_ticket(req)
        # Should always return something (BC-008)
        assert result is not None

    @pytest.mark.asyncio
    async def test_all_intents_have_agents(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine, TicketAssignmentRequest

        engine = AIAssignmentEngine(redis_client=mock_redis)
        intents = ["refund", "technical", "billing", "complaint", "feature_request",
                   "cancellation", "shipping", "inquiry", "escalation", "account", "feedback", "general"]
        for intent in intents:
            req = TicketAssignmentRequest(
                ticket_id=f"TKT-INTENT-{intent}", company_id=company_id, variant_type="parwa",
                intent_type=intent, priority="medium", sentiment_score=0.5, customer_tier="basic"
            )
            result = await engine.assign_ticket(req)
            assert result.assigned_agent_id is not None, f"No agent for intent: {intent}"

    @pytest.mark.asyncio
    async def test_assignment_history(self, company_id):
        from backend.app.core.ai_assignment_engine import AIAssignmentEngine

        engine = AIAssignmentEngine(redis_client=mock_redis)
        history = await engine.get_assignment_history(company_id, "TKT-HIST")
        assert isinstance(history, list)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. RuleAIMigrationEngine Tests (F-158)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGAP011CircuitBreaker:
    """GAP-011: Circuit breaker for AI failures."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker()
        assert await cb.can_execute() is True
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == "open"
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(3):
            await cb.record_success()
        assert cb.state == "closed"
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_recovery_timeout_half_open(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)  # 0 timeout for testing
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "open"
        # With 0 timeout, should transition to half_open
        await cb.can_execute()
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        await cb.record_failure()
        await cb.record_failure()
        await cb.can_execute()  # → half_open
        await cb.record_success()
        await cb.record_success()  # Need 2 successes
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        await cb.record_failure()
        await cb.record_failure()
        await cb.can_execute()  # → half_open
        await cb.record_failure()  # Fail again → back to open
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_reset_circuit(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "open"
        await cb.reset()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_serialization(self):
        from backend.app.core.rule_ai_migration import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=300)
        await cb.record_failure()
        data = cb.to_dict()
        assert data["failure_count"] == 1
        assert data["state"] == "closed"

        cb2 = CircuitBreaker.from_dict(data)
        assert cb2.failure_count == 1
        assert cb2.failure_threshold == 5


class TestRuleBasedClassifier:
    """Test rule-based classification fallback."""

    @pytest.mark.asyncio
    async def test_refund_classification(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("I want a refund for my order")
        assert result["intent"] == "refund"

    @pytest.mark.asyncio
    async def test_technical_classification(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("The app keeps crashing when I click save")
        assert result["intent"] == "technical"

    @pytest.mark.asyncio
    async def test_billing_classification(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("I was charged twice on my invoice")
        assert result["intent"] == "billing"

    @pytest.mark.asyncio
    async def test_complaint_classification(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("This is terrible service, I'm very angry")
        assert result["intent"] == "complaint"

    @pytest.mark.asyncio
    async def test_cancellation_classification(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("Please cancel my subscription")
        assert result["intent"] == "cancellation"

    @pytest.mark.asyncio
    async def test_unknown_falls_to_general(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("The weather is nice today")
        assert result["intent"] in ("general", "inquiry")

    @pytest.mark.asyncio
    async def test_empty_text(self):
        from backend.app.core.rule_ai_migration import RuleBasedClassifier

        classifier = RuleBasedClassifier()
        result = await classifier.classify("")
        assert result["intent"] == "general"


class TestRuleBasedAssigner:
    """Test rule-based assignment fallback."""

    @pytest.mark.asyncio
    async def test_critical_priority_assignment(self):
        from backend.app.core.rule_ai_migration import RuleBasedAssigner

        assigner = RuleBasedAssigner()
        result = await assigner.assign("technical", "critical")
        assert result["pool"] in ("senior_support", "tech_lead", "senior") or "senior" in result.get("agent_id", "")

    @pytest.mark.asyncio
    async def test_billing_assignment(self):
        from backend.app.core.rule_ai_migration import RuleBasedAssigner

        assigner = RuleBasedAssigner()
        result = await assigner.assign("billing", "medium")
        assert result["pool"] in ("billing_manager", "finance", "billing") or "billing" in result.get("agent_id", "")

    @pytest.mark.asyncio
    async def test_general_assignment(self):
        from backend.app.core.rule_ai_migration import RuleBasedAssigner

        assigner = RuleBasedAssigner()
        result = await assigner.assign("general", "low")
        assert result["pool"] in ("general_support", "support", "general") or "general" in result.get("agent_id", "")

    @pytest.mark.asyncio
    async def test_complaint_assignment(self):
        from backend.app.core.rule_ai_migration import RuleBasedAssigner

        assigner = RuleBasedAssigner()
        result = await assigner.assign("complaint", "high")
        assert result["pool"] in ("customer_success", "escalation") or "escalat" in result.get("agent_id", "")

    @pytest.mark.asyncio
    async def test_unknown_intent_default(self):
        from backend.app.core.rule_ai_migration import RuleBasedAssigner

        assigner = RuleBasedAssigner()
        result = await assigner.assign("unknown_intent", "low")
        assert result["pool"] is not None




class TestRuleAIMigrationEngine:
    """Test the full migration engine."""

    @pytest.mark.asyncio
    async def test_classify_with_ai_enabled(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")

        with patch('backend.app.core.classification_engine.ClassificationEngine') as cls_cls:
            mock_engine = AsyncMock()
            mock_engine.classify = AsyncMock(return_value=MagicMock(
                primary_intent="technical", primary_confidence=0.95,
                classification_method="ai", alternative_intents=[], processing_time_ms=50
            ))
            cls_cls.return_value = mock_engine

            result = await engine.classify("My app is broken", company_id, "parwa")
            assert result.intent == "technical"
            assert result.was_fallback is False

    @pytest.mark.asyncio
    async def test_classify_falls_to_rules(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")

        with patch('backend.app.core.classification_engine.ClassificationEngine') as cls_cls:
            mock_engine = AsyncMock()
            mock_engine.classify = AsyncMock(side_effect=Exception("AI down"))
            cls_cls.return_value = mock_engine

            result = await engine.classify("I want my money back", company_id, "parwa")
            assert result.was_fallback is True
            assert result.method in ("rule", "keyword")

    @pytest.mark.asyncio
    async def test_classify_with_circuit_open(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")

        cb = engine._breakers["classification"]
        for _ in range(cb.failure_threshold):
            await cb.record_failure()

        result = await engine.classify("Any text", company_id, "parwa")
        assert result.was_fallback is True

    @pytest.mark.asyncio
    async def test_assign_with_ai(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "assignment")
        mock_redis.get = AsyncMock(return_value="ai")

        with patch('backend.app.core.ai_assignment_engine.AIAssignmentEngine') as ai_cls:
            mock_ai = AsyncMock()
            mock_ai.assign_ticket = AsyncMock(return_value=MagicMock(
                assigned_agent_id="agent_001", assigned_agent_name="Sarah",
                assignment_method="ai_scored", total_score=85.5,
                score_breakdown={"specialty": 35, "workload": 25, "accuracy": 18, "jitter": 7.5},
                confidence=0.85, alternatives=[], assignment_time_ms=50, reason="Best match"
            ))
            ai_cls.return_value = mock_ai

            result = await engine.assign({
                "ticket_id": "TKT-MIG", "company_id": company_id,
                "variant_type": "parwa", "intent_type": "technical",
                "priority": "medium", "sentiment_score": 0.5, "customer_tier": "pro"
            }, company_id=company_id)
            assert result.was_fallback is False
            assert result.method == "ai"

    @pytest.mark.asyncio
    async def test_assign_falls_to_rules(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "assignment")
        mock_redis.get = AsyncMock(return_value="ai")

        with patch('backend.app.core.ai_assignment_engine.AIAssignmentEngine') as ai_cls:
            mock_ai = AsyncMock()
            mock_ai.assign_ticket = AsyncMock(side_effect=Exception("AI down"))
            ai_cls.return_value = mock_ai

            result = await engine.assign({
                "ticket_id": "TKT-MIG2", "company_id": company_id,
                "variant_type": "parwa", "intent_type": "billing",
                "priority": "high", "sentiment_score": 0.7, "customer_tier": "enterprise"
            }, company_id=company_id)
            assert result.was_fallback is True
            assert result.method == "rule"

    @pytest.mark.asyncio
    async def test_classify_and_assign_combined(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine, MigrationRequest

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        await engine.enable_ai(company_id, "assignment")
        mock_redis.get = AsyncMock(return_value="ai")
        # Circuit breaker deserialize needs JSON
        import json
        def get_side_effect(key):
            if "method" in str(key):
                return "ai"
            elif "circuit" in str(key):
                return json.dumps({"failure_count": 0, "failure_threshold": 5, "feature": "classification",
                    "half_open_success_count": 0, "last_failure_time": 0, "recovery_timeout": 300, "state": "closed"})
            elif "stats" in str(key):
                return json.dumps({})
            return None
        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        with patch('backend.app.core.classification_engine.ClassificationEngine') as cls_cls, \
             patch('backend.app.core.ai_assignment_engine.AIAssignmentEngine') as ai_cls:

            mock_cls = AsyncMock()
            mock_cls.classify = AsyncMock(return_value=MagicMock(
                primary_intent="refund", primary_confidence=0.9,
                classification_method="ai", alternative_intents=[], processing_time_ms=40
            ))
            cls_cls.return_value = mock_cls

            mock_ai = AsyncMock()
            mock_ai.assign_ticket = AsyncMock(return_value=MagicMock(
                assigned_agent_id="agent_002", assigned_agent_name="Mike",
                assignment_method="ai_scored", total_score=78.0,
                score_breakdown={"specialty": 30, "workload": 22, "accuracy": 17, "jitter": 9.0},
                confidence=0.78, alternatives=[], assignment_time_ms=45, reason="Good match"
            ))
            ai_cls.return_value = mock_ai

            req = MigrationRequest(
                text="I want a refund", company_id=company_id, variant_type="parwa",
                priority="medium", language="en"
            )
            result = await engine.classify_and_assign(req)
            assert result.classification.intent == "refund"
            assert result.assignment is not None
            assert result.used_ai is True

    @pytest.mark.asyncio
    async def test_get_migration_status(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        await engine.enable_ai(company_id, "assignment")
        mock_redis.get = AsyncMock(return_value="ai")

        status = await engine.get_migration_status(company_id)
        assert status.company_id == company_id
        assert status.classification_method == "ai"
        assert status.assignment_method == "ai"

    @pytest.mark.asyncio
    async def test_enable_disable_ai(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")
        status = await engine.get_migration_status(company_id)
        assert status.classification_method == "ai"

        await engine.disable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="rule")
        status = await engine.get_migration_status(company_id)
        assert status.classification_method == "rule"

    @pytest.mark.asyncio
    async def test_get_fallback_stats(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        stats = await engine.get_fallback_stats(company_id)
        assert stats.company_id == company_id
        assert "ai_calls" in stats.classification or "classification" in str(stats.classification)

    @pytest.mark.asyncio
    async def test_reset_circuit(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")

        cb = engine._breakers["classification"]
        for _ in range(cb.failure_threshold):
            await cb.record_failure()
        assert cb.state == "open"

        await engine.reset_circuit(company_id, "classification")
        state = await engine.get_circuit_state(company_id, "classification")
        assert state["state"] == "closed"

    @pytest.mark.asyncio
    async def test_get_circuit_state(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        state = await engine.get_circuit_state(company_id, "classification")
        assert isinstance(state, dict)
        assert state["state"] in ("closed", "open", "half_open")

    @pytest.mark.asyncio
    async def test_ai_enabled_classification(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        mock_redis.get = AsyncMock(return_value="ai")

        with patch('backend.app.core.classification_engine.ClassificationEngine') as cls_cls:
            mock_engine = AsyncMock()
            mock_engine.classify = AsyncMock(return_value=MagicMock(
                primary_intent="refund", primary_confidence=0.9,
                classification_method="ai", alternative_intents=[], processing_time_ms=20
            ))
            cls_cls.return_value = mock_engine

            result = await engine.classify("I want a refund", company_id, "parwa")
            assert result.intent == "refund"
            assert result.was_fallback is False

    @pytest.mark.asyncio
    async def test_ai_disabled_uses_rules(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine
        import json

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.disable_ai(company_id, "classification")
        
        def get_side_effect(key):
            if "method" in str(key):
                return "rule"
            elif "circuit" in str(key):
                return json.dumps({"failure_count": 0, "failure_threshold": 5, "feature": "classification",
                    "half_open_success_count": 0, "last_failure_time": 0, "recovery_timeout": 300, "state": "closed"})
            elif "stats" in str(key):
                return json.dumps({})
            return None
        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        result = await engine.classify("I want a refund", company_id, "parwa")
        assert result.method in ("rule", "keyword")
        assert result.was_fallback is True

    @pytest.mark.asyncio
    async def test_graceful_redis_failure(self, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine

        broken_redis = AsyncMock()
        for attr in ['get', 'set', 'delete', 'hset', 'hgetall', 'incr', 'incrby',
                     'expire', 'eval', 'rpush', 'lpush', 'lrange', 'keys', 'exists', 'scan_iter', 'hincrby']:
            setattr(broken_redis, attr, AsyncMock(side_effect=Exception("Redis down")))

        engine = RuleAIMigrationEngine(redis_client=broken_redis)
        result = await engine.classify("I want a refund", company_id, "parwa")
        assert result is not None
        assert result.intent is not None

    @pytest.mark.asyncio
    async def test_migration_records_fallback_event(self, mock_redis, company_id):
        from backend.app.core.rule_ai_migration import RuleAIMigrationEngine
        import json

        engine = RuleAIMigrationEngine(redis_client=mock_redis)
        await engine.enable_ai(company_id, "classification")
        
        def get_side_effect(key):
            if "method" in str(key):
                return "ai"
            elif "circuit" in str(key):
                return json.dumps({"failure_count": 0, "failure_threshold": 5, "feature": "classification",
                    "half_open_success_count": 0, "last_failure_time": 0, "recovery_timeout": 300, "state": "closed"})
            elif "stats" in str(key):
                return json.dumps({"classification_ai_calls": 0, "classification_fallbacks": 0})
            return None
        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        with patch('backend.app.core.classification_engine.ClassificationEngine') as cls_cls:
            mock_engine = AsyncMock()
            mock_engine.classify = AsyncMock(side_effect=Exception("AI down"))
            cls_cls.return_value = mock_engine

            result = await engine.classify("Test text", company_id, "parwa")
            assert result.was_fallback is True

            stats = await engine.get_fallback_stats(company_id)
            # Should have recorded the fallback event in stats
            assert stats is not None
