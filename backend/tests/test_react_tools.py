"""
Comprehensive tests for PARWA ReAct Tools (F-157).

Tests cover:
- BaseReactTool: validation, execution, timeout, retry, health check
- OrderTool: get_order, list_orders, cancel_order, get_order_status,
              update_shipping, refund_order
- BillingTool: get_invoice, list_invoices, process_payment,
               get_subscription_status, apply_credit, get_payment_history
- CRMTool: get_customer, search_customers, update_customer,
            get_interaction_history, add_note, get_customer_stats
- TicketTool: get_ticket, create_ticket, update_ticket, add_comment,
              list_tickets, get_ticket_history
- ReActToolRegistry: registration, lookup, execution, parallel execution

All tools use in-memory mock data and require no external services.
"""

from __future__ import annotations
from app.core.react_tools import ReActToolRegistry
from app.core.react_tools.ticket_tool import TicketTool
from app.core.react_tools.order_tool import OrderTool
from app.core.react_tools.crm_tool import CRMTool
from app.core.react_tools.billing_tool import BillingTool
from app.core.react_tools.base import (
    ActionSchema,
    BaseReactTool,
    ToolCall,
    ToolResult,
    ToolSchema,
    ValidationResult,
)

import asyncio
from typing import Any

import pytest

# ── Environment bootstrap ─────────────────────────────────────────
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault(
    "DATA_ENCRYPTION_KEY",
    "12345678901234567890123456789012")


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

COMPANY_ID = "co-test-001"
OTHER_COMPANY = "co-test-002"


# ── Minimal concrete subclass for base class tests ───────────────


class _StubTool(BaseReactTool):
    """Concrete tool for testing BaseReactTool behaviour."""

    def __init__(self) -> None:
        self.call_log: list[tuple[str, str, dict]] = []
        self._should_fail: bool = False
        self._delay: float = 0.0
        self._action_count = 0

    @property
    def name(self) -> str:
        return "stub_tool"

    @property
    def description(self) -> str:
        return "A stub tool for testing."

    @property
    def actions(self) -> list[str]:
        return ["do_thing", "fail_thing"]

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="do_thing",
                    description="Do a thing.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "A key."},
                        },
                        "required": ["key"],
                    },
                    required_params=["key"],
                    returns="Result of doing the thing.",
                ),
                ActionSchema(
                    name="fail_thing",
                    description="Always fails.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                    required_params=[],
                    returns="Never succeeds.",
                ),
            ],
        )

    async def _do_execute(
        self, action: str, company_id: str, **params: Any,
    ) -> ToolResult:
        self.call_log.append((action, company_id, params))
        self._action_count += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._should_fail:
            raise RuntimeError("Intentional failure")
        return ToolResult(
            success=True,
            error=None,
            data={"action": action, "company_id": company_id, **params},
            execution_time_ms=0,
        )


# ── Timeout tool for testing execution timeout ───────────────────


class _SlowTool(BaseReactTool):
    """A tool that always times out."""

    def __init__(self) -> None:
        self._delay: float = 15.0

    @property
    def name(self) -> str:
        return "slow_tool"

    @property
    def description(self) -> str:
        return "Always slow."

    @property
    def actions(self) -> list[str]:
        return ["slow_action"]

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="slow_action",
                    description="Takes forever.",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                    required_params=[],
                    returns="Never returns in time.",
                ),
            ],
        )

    async def _do_execute(
        self, action: str, company_id: str, **params: Any,
    ) -> ToolResult:
        await asyncio.sleep(self._delay)
        return ToolResult(
            success=True, error=None, data={
                "ok": True}, execution_time_ms=0)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def stub():
    return _StubTool()


@pytest.fixture
def order():
    return OrderTool()


@pytest.fixture
def billing():
    return BillingTool()


@pytest.fixture
def crm():
    return CRMTool()


@pytest.fixture
def ticket():
    return TicketTool()


@pytest.fixture
def registry():
    reg = ReActToolRegistry()
    reg.register_tool_sync(OrderTool())
    reg.register_tool_sync(BillingTool())
    reg.register_tool_sync(CRMTool())
    reg.register_tool_sync(TicketTool())
    return reg


# ══════════════════════════════════════════════════════════════════
# 1. TOOL RESULT & SCHEMA DATA CLASSES
# ══════════════════════════════════════════════════════════════════


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_to_dict(self):
        result = ToolResult(
            success=True,
            error=None,
            data={"key": "value"},
            execution_time_ms=42,
            action="test_action",
            tool_name="test_tool",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert d["execution_time_ms"] == 42
        assert d["action"] == "test_action"
        assert d["tool_name"] == "test_tool"

    def test_to_dict_failure(self):
        result = ToolResult(
            success=False,
            error="Something went wrong",
            data=None,
            execution_time_ms=10,
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Something went wrong"
        assert d["data"] is None


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        vr = ValidationResult(is_valid=True, errors=[], missing_params=[])
        assert vr.is_valid is True
        assert vr.errors == []
        assert vr.missing_params == []

    def test_invalid_result(self):
        vr = ValidationResult(
            is_valid=False,
            errors=["Missing: key"],
            missing_params=["key"],
        )
        assert vr.is_valid is False
        assert "key" in vr.missing_params


class TestToolSchema:
    """Test ToolSchema serialization."""

    def test_to_dict(self, stub):
        schema = stub.get_schema()
        d = schema.to_dict()
        assert d["tool_name"] == "stub_tool"
        assert isinstance(d["actions"], list)
        assert len(d["actions"]) == 2
        assert d["actions"][0]["name"] == "do_thing"
        assert "required_params" in d["actions"][0]


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_tool_call_creation(self):
        tc = ToolCall(
            tool_name="order_management",
            action="get_order",
            company_id="co-1",
            params={"order_id": "ORD-123"},
        )
        assert tc.tool_name == "order_management"
        assert tc.action == "get_order"
        assert tc.company_id == "co-1"
        assert tc.params == {"order_id": "ORD-123"}

    def test_tool_call_default_params(self):
        tc = ToolCall(
            tool_name="billing",
            action="get_subscription_status",
            company_id="co-1",
        )
        assert tc.params == {}


# ══════════════════════════════════════════════════════════════════
# 2. BASE TOOL TESTS
# ══════════════════════════════════════════════════════════════════


class TestBaseReactTool:
    """Test BaseReactTool abstract base behaviour."""

    @pytest.mark.asyncio
    async def test_execute_success(self, stub):
        """Successful execute returns a ToolResult with success=True."""
        result = await stub.execute("do_thing", COMPANY_ID, key="val")
        assert result.success is True
        assert result.data["action"] == "do_thing"
        assert result.action == "do_thing"
        assert result.tool_name == "stub_tool"
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_sets_action_and_tool_name(self, stub):
        """Execute populates action and tool_name on the result."""
        result = await stub.execute("do_thing", COMPANY_ID, key="v")
        assert result.action == "do_thing"
        assert result.tool_name == "stub_tool"

    @pytest.mark.asyncio
    async def test_execute_retry_on_failure(self, stub):
        """Tool retries once on transient failure (MAX_RETRIES=1)."""
        stub._should_fail = True
        stub.MAX_RETRIES = 1
        result = await stub.execute("do_thing", COMPANY_ID, key="v")
        assert result.success is False
        assert "Intentional failure" in result.error
        # Should have attempted MAX_RETRIES + 1 = 2 times
        assert stub._action_count == 2

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Tool execution times out after EXECUTION_TIMEOUT seconds."""
        slow = _SlowTool()
        slow.EXECUTION_TIMEOUT = 1
        slow._delay = 5.0
        result = await slow.execute("slow_action", COMPANY_ID)
        assert result.success is False
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_timeout_result_fields(self):
        """Timeout result carries proper metadata."""
        slow = _SlowTool()
        slow.EXECUTION_TIMEOUT = 1
        slow._delay = 5.0
        result = await slow.execute("slow_action", COMPANY_ID)
        assert result.action == "slow_action"
        assert result.tool_name == "slow_tool"
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_health_check_success(self, stub):
        """Health check returns True for a working tool."""
        result = await stub.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check returns False for a failing tool."""
        stub = _StubTool()
        stub._should_fail = True
        result = await stub.health_check()
        assert result is False

    def test_validate_params_valid(self, stub):
        """Validation passes with correct params."""
        vr = stub.validate_params("do_thing", {"key": "value"})
        assert vr.is_valid is True
        assert vr.errors == []

    def test_validate_params_missing_required(self, stub):
        """Validation fails when required param is missing."""
        vr = stub.validate_params("do_thing", {})
        assert vr.is_valid is False
        assert "key" in vr.missing_params

    def test_validate_params_unknown_action(self, stub):
        """Unknown action returns validation error."""
        vr = stub.validate_params("nonexistent", {})
        assert vr.is_valid is False
        assert "Unknown action" in vr.errors[0]

    def test_validate_params_type_check_string(self, stub):
        """Type check catches non-string when string expected."""
        vr = stub.validate_params("do_thing", {"key": 12345})
        assert vr.is_valid is False
        assert any("string" in e for e in vr.errors)

    def test_validate_params_null_value_treated_as_missing(self, stub):
        """None value for required param is treated as missing."""
        vr = stub.validate_params("do_thing", {"key": None})
        assert vr.is_valid is False
        assert "key" in vr.missing_params

    @pytest.mark.asyncio
    async def test_execute_concurrency_limited(self):
        """Concurrent executions are limited by semaphore."""
        stub = _StubTool()
        stub._delay = 0.1

        async def run_action():
            return await stub.execute("do_thing", COMPANY_ID, key="v")

        # Run many concurrent actions
        tasks = [run_action() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)


# ══════════════════════════════════════════════════════════════════
# 3. ORDER TOOL TESTS
# ══════════════════════════════════════════════════════════════════


class TestOrderTool:
    """Test OrderTool actions."""

    @pytest.mark.asyncio
    async def test_get_order_success(self, order):
        """get_order returns an order with the requested ID."""
        result = await order.execute("get_order", COMPANY_ID, order_id="ORD-001")
        assert result.success is True
        assert result.data["order_id"] == "ORD-001"
        assert result.data["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_get_order_cached(self, order):
        """Subsequent get_order for same ID returns cached version."""
        r1 = await order.execute("get_order", COMPANY_ID, order_id="ORD-CACHE")
        r2 = await order.execute("get_order", COMPANY_ID, order_id="ORD-CACHE")
        assert r1.data["order_id"] == r2.data["order_id"]

    @pytest.mark.asyncio
    async def test_get_order_wrong_company(self, order):
        """get_order for a different company returns error."""
        # First, store an order under COMPANY_ID
        await order.execute("get_order", COMPANY_ID, order_id="ORD-SCOPE")
        # Then try to get it from another company
        result = await order.execute("get_order", OTHER_COMPANY, order_id="ORD-SCOPE")
        assert result.success is False
        assert "not found in company scope" in result.error

    @pytest.mark.asyncio
    async def test_list_orders_success(self, order):
        """list_orders returns a list of orders."""
        result = await order.execute("list_orders", COMPANY_ID)
        assert result.success is True
        assert "orders" in result.data
        assert "total" in result.data

    @pytest.mark.asyncio
    async def test_list_orders_with_status_filter(self, order):
        """list_orders with status filter works."""
        result = await order.execute(
            "list_orders", COMPANY_ID, status="shipped",
        )
        assert result.success is True
        for o in result.data["orders"]:
            assert o["status"] == "shipped"

    @pytest.mark.asyncio
    async def test_list_orders_with_limit(self, order):
        """list_orders respects limit parameter."""
        result = await order.execute("list_orders", COMPANY_ID, limit=3)
        assert result.success is True
        assert len(result.data["orders"]) <= 3

    @pytest.mark.asyncio
    async def test_cancel_order_pending(self, order):
        """cancel_order works for pending orders."""
        # Create a pending order
        await order.execute("get_order", COMPANY_ID, order_id="ORD-CAN")
        # Store it as pending
        order._store["ORD-CAN"]["status"] = "pending"
        result = await order.execute(
            "cancel_order", COMPANY_ID, order_id="ORD-CAN", reason="Test cancel",
        )
        assert result.success is True
        assert result.data["status"] == "cancelled"
        assert result.data["cancellation_reason"] == "Test cancel"

    @pytest.mark.asyncio
    async def test_cancel_order_delivered_fails(self, order):
        """cancel_order fails for delivered orders."""
        order._store["ORD-DEL"] = {
            "order_id": "ORD-DEL",
            "company_id": COMPANY_ID,
            "status": "delivered",
        }
        result = await order.execute(
            "cancel_order", COMPANY_ID, order_id="ORD-DEL",
        )
        assert result.success is False
        assert "Cannot cancel" in result.error

    @pytest.mark.asyncio
    async def test_get_order_status_success(self, order):
        """get_order_status returns status for multiple orders."""
        result = await order.execute(
            "get_order_status", COMPANY_ID, order_ids="ORD-A,ORD-B",
        )
        assert result.success is True
        assert "statuses" in result.data
        assert len(result.data["statuses"]) == 2

    @pytest.mark.asyncio
    async def test_get_order_status_empty(self, order):
        """get_order_status with empty string returns error."""
        result = await order.execute(
            "get_order_status", COMPANY_ID, order_ids="",
        )
        assert result.success is False
        assert "No order IDs" in result.error

    @pytest.mark.asyncio
    async def test_update_shipping_success(self, order):
        """update_shipping updates carrier and tracking."""
        order._store["ORD-SHIP"] = {
            "order_id": "ORD-SHIP",
            "company_id": COMPANY_ID,
            "status": "processing",
            "carrier": None,
            "tracking_number": None,
            "shipping_address": {},
        }
        result = await order.execute(
            "update_shipping",
            COMPANY_ID,
            order_id="ORD-SHIP",
            carrier="FedEx",
            tracking_number="1Z999",
        )
        assert result.success is True
        assert "carrier" in result.data["updated_fields"]

    @pytest.mark.asyncio
    async def test_update_shipping_delivered_fails(self, order):
        """update_shipping fails for delivered orders."""
        order._store["ORD-DEL2"] = {
            "order_id": "ORD-DEL2",
            "company_id": COMPANY_ID,
            "status": "delivered",
        }
        result = await order.execute(
            "update_shipping", COMPANY_ID, order_id="ORD-DEL2", carrier="UPS",
        )
        assert result.success is False
        assert "Cannot update shipping" in result.error

    @pytest.mark.asyncio
    async def test_update_shipping_no_fields(self, order):
        """update_shipping with no fields to update returns error."""
        order._store["ORD-NOUPD"] = {
            "order_id": "ORD-NOUPD",
            "company_id": COMPANY_ID,
            "status": "processing",
        }
        result = await order.execute(
            "update_shipping", COMPANY_ID, order_id="ORD-NOUPD",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_refund_order_success(self, order):
        """refund_order works for delivered orders."""
        order._store["ORD-REF"] = {
            "order_id": "ORD-REF",
            "company_id": COMPANY_ID,
            "status": "delivered",
            "total": 100.00,
            "currency": "USD",
        }
        result = await order.execute(
            "refund_order", COMPANY_ID, order_id="ORD-REF", reason="Defective",
        )
        assert result.success is True
        assert result.data["status"] == "processed"
        assert result.data["amount"] == 100.00
        assert "refund_id" in result.data

    @pytest.mark.asyncio
    async def test_refund_partial_amount(self, order):
        """Partial refund is capped to order total."""
        order._store["ORD-PART"] = {
            "order_id": "ORD-PART",
            "company_id": COMPANY_ID,
            "status": "delivered",
            "total": 50.00,
            "currency": "USD",
        }
        result = await order.execute(
            "refund_order", COMPANY_ID, order_id="ORD-PART", amount=200.00,
        )
        assert result.success is True
        assert result.data["amount"] == 50.00

    @pytest.mark.asyncio
    async def test_refund_already_refunded_fails(self, order):
        """Refunding an already-refunded order fails (status check)."""
        # Status "refunded" is not in the allowed set, so the status
        # check fires before the duplicate-refund guard.
        order._store["ORD-DBLREF"] = {
            "order_id": "ORD-DBLREF",
            "company_id": COMPANY_ID,
            "status": "refunded",
            "refunded": True,
            "total": 50.00,
            "currency": "USD",
        }
        result = await order.execute(
            "refund_order", COMPANY_ID, order_id="ORD-DBLREF",
        )
        assert result.success is False
        assert "refunded" in result.error

    @pytest.mark.asyncio
    async def test_unknown_action(self, order):
        """Unknown action returns an error result."""
        result = await order.execute("nonexistent", COMPANY_ID)
        assert result.success is False
        assert "Unknown action" in result.error

    def test_order_tool_name(self, order):
        assert order.name == "order_management"

    def test_order_tool_actions(self, order):
        assert "get_order" in order.actions
        assert "list_orders" in order.actions
        assert "cancel_order" in order.actions

    def test_order_tool_schema(self, order):
        schema = order.get_schema()
        assert schema.tool_name == "order_management"
        assert len(schema.actions) == 6

    @pytest.mark.asyncio
    async def test_health_check(self, order):
        result = await order.health_check()
        assert result is True


# ══════════════════════════════════════════════════════════════════
# 4. BILLING TOOL TESTS
# ══════════════════════════════════════════════════════════════════


class TestBillingTool:
    """Test BillingTool actions."""

    @pytest.mark.asyncio
    async def test_get_invoice_success(self, billing):
        """get_invoice returns an invoice."""
        result = await billing.execute(
            "get_invoice", COMPANY_ID, invoice_id="INV-001",
        )
        assert result.success is True
        assert result.data["invoice_id"] == "INV-001"
        assert result.data["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_get_invoice_cached(self, billing):
        """get_invoice returns cached invoice on second call."""
        r1 = await billing.execute(
            "get_invoice", COMPANY_ID, invoice_id="INV-CACHE",
        )
        r2 = await billing.execute(
            "get_invoice", COMPANY_ID, invoice_id="INV-CACHE",
        )
        assert r1.data["invoice_id"] == r2.data["invoice_id"]

    @pytest.mark.asyncio
    async def test_get_invoice_wrong_company(self, billing):
        """get_invoice for other company returns error."""
        await billing.execute(
            "get_invoice", COMPANY_ID, invoice_id="INV-SCOPE",
        )
        result = await billing.execute(
            "get_invoice", OTHER_COMPANY, invoice_id="INV-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_invoices_success(self, billing):
        """list_invoices returns invoice list."""
        result = await billing.execute("list_invoices", COMPANY_ID)
        assert result.success is True
        assert "invoices" in result.data
        assert "total" in result.data

    @pytest.mark.asyncio
    async def test_list_invoices_status_filter(self, billing):
        """list_invoices with status filter."""
        result = await billing.execute(
            "list_invoices", COMPANY_ID, status="paid",
        )
        assert result.success is True
        for inv in result.data["invoices"]:
            assert inv["status"] == "paid"

    @pytest.mark.asyncio
    async def test_process_payment_success(self, billing):
        """process_payment succeeds with valid amount."""
        result = await billing.execute(
            "process_payment",
            COMPANY_ID,
            amount=49.99,
            payment_method="visa_****4242",
        )
        assert result.success is True
        assert result.data["status"] == "succeeded"
        assert result.data["amount"] == 49.99

    @pytest.mark.asyncio
    async def test_process_payment_zero_amount_fails(self, billing):
        """process_payment with zero amount fails."""
        result = await billing.execute(
            "process_payment",
            COMPANY_ID,
            amount=0,
            payment_method="visa_****4242",
        )
        assert result.success is False
        assert "positive" in result.error

    @pytest.mark.asyncio
    async def test_process_payment_negative_amount_fails(self, billing):
        """process_payment with negative amount fails."""
        result = await billing.execute(
            "process_payment",
            COMPANY_ID,
            amount=-10,
            payment_method="visa_****4242",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_process_payment_no_method_fails(self, billing):
        """process_payment without payment_method fails."""
        result = await billing.execute(
            "process_payment", COMPANY_ID, amount=50,
        )
        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_payment_uses_credit(self, billing):
        """process_payment applies credit balance."""
        billing._credits[COMPANY_ID] = 20.00
        result = await billing.execute(
            "process_payment",
            COMPANY_ID,
            amount=50.00,
            payment_method="visa_****4242",
        )
        assert result.success is True
        assert result.data["credit_applied"] == 20.00
        assert result.data["net_amount"] == 30.00

    @pytest.mark.asyncio
    async def test_process_payment_marks_invoice_paid(self, billing):
        """process_payment marks associated invoice as paid."""
        billing._invoices["INV-PAY"] = {
            "invoice_id": "INV-PAY",
            "company_id": COMPANY_ID,
            "status": "unpaid",
        }
        result = await billing.execute(
            "process_payment",
            COMPANY_ID,
            amount=50.00,
            payment_method="visa_****4242",
            invoice_id="INV-PAY",
        )
        assert result.success is True
        assert billing._invoices["INV-PAY"]["status"] == "paid"

    @pytest.mark.asyncio
    async def test_get_subscription_status(self, billing):
        """get_subscription_status returns subscription info."""
        result = await billing.execute(
            "get_subscription_status", COMPANY_ID,
        )
        assert result.success is True
        assert "plan_name" in result.data
        assert result.data["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_subscription_includes_credit(self, billing):
        """Subscription status includes credit balance."""
        billing._credits[COMPANY_ID] = 15.00
        result = await billing.execute(
            "get_subscription_status", COMPANY_ID,
        )
        assert result.data["credit_balance"] == 15.00

    @pytest.mark.asyncio
    async def test_apply_credit_success(self, billing):
        """apply_credit adds to company balance."""
        result = await billing.execute(
            "apply_credit",
            COMPANY_ID,
            amount=50.00,
            reason="Loyalty reward",
        )
        assert result.success is True
        assert result.data["amount_applied"] == 50.00
        assert result.data["new_balance"] == 50.00
        assert "credit_id" in result.data

    @pytest.mark.asyncio
    async def test_apply_credit_accumulates(self, billing):
        """Multiple credits accumulate."""
        await billing.execute(
            "apply_credit", COMPANY_ID, amount=10, reason="R1",
        )
        result = await billing.execute(
            "apply_credit", COMPANY_ID, amount=20, reason="R2",
        )
        assert result.data["previous_balance"] == 10.00
        assert result.data["new_balance"] == 30.00

    @pytest.mark.asyncio
    async def test_apply_credit_zero_fails(self, billing):
        """apply_credit with zero amount fails."""
        result = await billing.execute(
            "apply_credit", COMPANY_ID, amount=0, reason="Test",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_apply_credit_no_reason_fails(self, billing):
        """apply_credit without reason fails."""
        result = await billing.execute(
            "apply_credit", COMPANY_ID, amount=10,
        )
        assert result.success is False
        assert "Reason" in result.error

    @pytest.mark.asyncio
    async def test_get_payment_history(self, billing):
        """get_payment_history returns payment records."""
        result = await billing.execute(
            "get_payment_history", COMPANY_ID,
        )
        assert result.success is True
        assert "payments" in result.data
        assert "total_succeeded_amount" in result.data

    @pytest.mark.asyncio
    async def test_get_payment_history_status_filter(self, billing):
        """Payment history can be filtered by status."""
        result = await billing.execute(
            "get_payment_history", COMPANY_ID, status="succeeded",
        )
        assert result.success is True
        for p in result.data["payments"]:
            assert p["status"] == "succeeded"

    @pytest.mark.asyncio
    async def test_unknown_action(self, billing):
        """Unknown action returns error."""
        result = await billing.execute("nonexistent", COMPANY_ID)
        assert result.success is False

    def test_billing_tool_name(self, billing):
        assert billing.name == "billing_system"

    def test_billing_tool_actions_count(self, billing):
        assert len(billing.actions) == 6

    @pytest.mark.asyncio
    async def test_health_check(self, billing):
        assert await billing.health_check() is True


# ══════════════════════════════════════════════════════════════════
# 5. CRM TOOL TESTS
# ══════════════════════════════════════════════════════════════════


class TestCRMTool:
    """Test CRMTool actions."""

    @pytest.mark.asyncio
    async def test_get_customer_success(self, crm):
        """get_customer returns a customer profile."""
        result = await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-001",
        )
        assert result.success is True
        assert result.data["customer_id"] == "CUST-001"
        assert result.data["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_get_customer_cached(self, crm):
        """get_customer returns cached customer."""
        r1 = await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-CACHE",
        )
        r2 = await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-CACHE",
        )
        assert r1.data["customer_id"] == r2.data["customer_id"]

    @pytest.mark.asyncio
    async def test_get_customer_wrong_company(self, crm):
        """get_customer for wrong company returns error."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-SCOPE",
        )
        result = await crm.execute(
            "get_customer", OTHER_COMPANY, customer_id="CUST-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_search_customers_success(self, crm):
        """search_customers returns results."""
        result = await crm.execute(
            "search_customers", COMPANY_ID, query="Alice",
        )
        assert result.success is True
        assert "customers" in result.data

    @pytest.mark.asyncio
    async def test_search_customers_with_tier(self, crm):
        """search_customers with tier filter."""
        result = await crm.execute(
            "search_customers", COMPANY_ID, tier="enterprise",
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_customer_name(self, crm):
        """update_customer updates name."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-UPD",
        )
        result = await crm.execute(
            "update_customer",
            COMPANY_ID,
            customer_id="CUST-UPD",
            name="New Name",
        )
        assert result.success is True
        assert "name" in result.data["updated_fields"]
        assert crm._customers["CUST-UPD"]["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_customer_splits_name(self, crm):
        """Updating name splits first/last name."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-SPLIT",
        )
        await crm.execute(
            "update_customer",
            COMPANY_ID,
            customer_id="CUST-SPLIT",
            name="Jane Doe",
        )
        assert crm._customers["CUST-SPLIT"]["first_name"] == "Jane"
        assert crm._customers["CUST-SPLIT"]["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_update_customer_email(self, crm):
        """update_customer updates email."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-EMAIL",
        )
        result = await crm.execute(
            "update_customer",
            COMPANY_ID,
            customer_id="CUST-EMAIL",
            email="new@example.com",
        )
        assert result.success is True
        assert crm._customers["CUST-EMAIL"]["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_update_customer_invalid_tier(self, crm):
        """update_customer with invalid tier returns error."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-TIER",
        )
        result = await crm.execute(
            "update_customer",
            COMPANY_ID,
            customer_id="CUST-TIER",
            tier="platinum",
        )
        assert result.success is False
        assert "Invalid tier" in result.error

    @pytest.mark.asyncio
    async def test_update_customer_no_fields(self, crm):
        """update_customer with no fields to update returns error."""
        await crm.execute(
            "get_customer", COMPANY_ID, customer_id="CUST-NOUPD",
        )
        result = await crm.execute(
            "update_customer", COMPANY_ID, customer_id="CUST-NOUPD",
        )
        assert result.success is False
        assert "No fields" in result.error

    @pytest.mark.asyncio
    async def test_get_interaction_history(self, crm):
        """get_interaction_history returns interactions."""
        result = await crm.execute(
            "get_interaction_history",
            COMPANY_ID,
            customer_id="CUST-001",
        )
        assert result.success is True
        assert "interactions" in result.data
        assert result.data["total"] > 0

    @pytest.mark.asyncio
    async def test_get_interaction_history_with_channel(self, crm):
        """Interaction history can be filtered by channel."""
        result = await crm.execute(
            "get_interaction_history",
            COMPANY_ID,
            customer_id="CUST-001",
            channel="email",
        )
        assert result.success is True
        for i in result.data["interactions"]:
            assert i["channel"] == "email"

    @pytest.mark.asyncio
    async def test_add_note_success(self, crm):
        """add_note attaches a note to a customer."""
        result = await crm.execute(
            "add_note",
            COMPANY_ID,
            customer_id="CUST-NOTE",
            content="Important note about this customer",
            author="Agent Smith",
            tags="vip,follow-up",
        )
        assert result.success is True
        assert result.data["content"] == "Important note about this customer"
        assert result.data["author"] == "Agent Smith"
        assert "vip" in result.data["tags"]
        assert "follow-up" in result.data["tags"]

    @pytest.mark.asyncio
    async def test_add_note_empty_content_fails(self, crm):
        """add_note with empty content fails."""
        result = await crm.execute(
            "add_note",
            COMPANY_ID,
            customer_id="CUST-NOTE",
            content="   ",
        )
        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_customer_stats(self, crm):
        """get_customer_stats returns aggregate stats."""
        result = await crm.execute(
            "get_customer_stats",
            COMPANY_ID,
            customer_id="CUST-STATS",
        )
        assert result.success is True
        assert "lifetime_value" in result.data
        assert "interaction_count" in result.data
        assert "engagement_score" in result.data
        assert 0 <= result.data["engagement_score"] <= 100

    @pytest.mark.asyncio
    async def test_get_customer_stats_includes_account_age(self, crm):
        """Customer stats include account_age_days."""
        result = await crm.execute(
            "get_customer_stats",
            COMPANY_ID,
            customer_id="CUST-AGE",
        )
        assert "account_age_days" in result.data
        assert result.data["account_age_days"] >= 0

    @pytest.mark.asyncio
    async def test_unknown_action(self, crm):
        """Unknown action returns error."""
        result = await crm.execute("nonexistent", COMPANY_ID)
        assert result.success is False

    def test_crm_tool_name(self, crm):
        assert crm.name == "crm_integration"

    def test_crm_tool_actions_count(self, crm):
        assert len(crm.actions) == 6

    @pytest.mark.asyncio
    async def test_health_check(self, crm):
        assert await crm.health_check() is True


# ══════════════════════════════════════════════════════════════════
# 6. TICKET TOOL TESTS
# ══════════════════════════════════════════════════════════════════


class TestTicketTool:
    """Test TicketTool actions."""

    @pytest.mark.asyncio
    async def test_get_ticket_success(self, ticket):
        """get_ticket returns a ticket."""
        result = await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-001",
        )
        assert result.success is True
        assert result.data["ticket_id"] == "TKT-001"
        assert result.data["company_id"] == COMPANY_ID

    @pytest.mark.asyncio
    async def test_get_ticket_with_comments(self, ticket):
        """get_ticket includes comment_count."""
        # Add a comment first
        await ticket.execute(
            "add_comment",
            COMPANY_ID,
            ticket_id="TKT-CMT",
            content="Test comment",
        )
        result = await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-CMT",
        )
        assert result.data.get("comment_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_get_ticket_wrong_company(self, ticket):
        """get_ticket for wrong company returns error."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-SCOPE",
        )
        result = await ticket.execute(
            "get_ticket", OTHER_COMPANY, ticket_id="TKT-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, ticket):
        """create_ticket creates a new ticket."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="Cannot access dashboard",
            description="Getting a 403 error when trying to access the analytics dashboard.",
            priority="high",
            category="technical",
        )
        assert result.success is True
        assert result.data["status"] == "open"
        assert result.data["priority"] == "high"
        assert result.data["category"] == "technical"
        assert "ticket_id" in result.data

    @pytest.mark.asyncio
    async def test_create_ticket_with_tags(self, ticket):
        """create_ticket parses comma-separated tags."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="Bug report",
            description="Found a bug.",
            tags="urgent,frontend",
        )
        assert result.success is True
        assert "urgent" in result.data["tags"]
        assert "frontend" in result.data["tags"]

    @pytest.mark.asyncio
    async def test_create_ticket_empty_subject_fails(self, ticket):
        """create_ticket without subject fails."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="",
            description="Some description",
        )
        assert result.success is False
        assert "subject" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_empty_description_fails(self, ticket):
        """create_ticket without description fails."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="Subject",
            description="   ",
        )
        assert result.success is False
        assert "description" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_invalid_priority(self, ticket):
        """create_ticket with invalid priority fails."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="Subject",
            description="Description",
            priority="critical",
        )
        assert result.success is False
        assert "Invalid priority" in result.error

    @pytest.mark.asyncio
    async def test_create_ticket_invalid_category(self, ticket):
        """create_ticket with invalid category fails."""
        result = await ticket.execute(
            "create_ticket",
            COMPANY_ID,
            subject="Subject",
            description="Description",
            category="nonexistent",
        )
        assert result.success is False
        assert "Invalid category" in result.error

    @pytest.mark.asyncio
    async def test_update_ticket_status(self, ticket):
        """update_ticket changes status."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-UPD",
        )
        result = await ticket.execute(
            "update_ticket",
            COMPANY_ID,
            ticket_id="TKT-UPD",
            status="in_progress",
        )
        assert result.success is True
        assert "status" in result.data["updated_fields"]
        assert ticket._tickets["TKT-UPD"]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_ticket_assignee(self, ticket):
        """update_ticket sets assignee."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-ASN",
        )
        result = await ticket.execute(
            "update_ticket",
            COMPANY_ID,
            ticket_id="TKT-ASN",
            assignee_id="AGENT-005",
        )
        assert result.success is True
        assert ticket._tickets["TKT-ASN"]["assignee_name"] == "Agent 005"

    @pytest.mark.asyncio
    async def test_update_ticket_resolved_sets_resolved_at(self, ticket):
        """Updating to resolved sets resolved_at timestamp."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-RES",
        )
        result = await ticket.execute(
            "update_ticket",
            COMPANY_ID,
            ticket_id="TKT-RES",
            status="resolved",
        )
        assert result.success is True
        assert ticket._tickets["TKT-RES"]["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_update_ticket_invalid_status(self, ticket):
        """update_ticket with invalid status fails."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-INV",
        )
        result = await ticket.execute(
            "update_ticket",
            COMPANY_ID,
            ticket_id="TKT-INV",
            status="invalid_status",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_update_ticket_no_fields(self, ticket):
        """update_ticket with no fields to update fails."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-NOUPD",
        )
        result = await ticket.execute(
            "update_ticket", COMPANY_ID, ticket_id="TKT-NOUPD",
        )
        assert result.success is False
        assert "No fields" in result.error

    @pytest.mark.asyncio
    async def test_add_comment_success(self, ticket):
        """add_comment adds a comment to a ticket."""
        result = await ticket.execute(
            "add_comment",
            COMPANY_ID,
            ticket_id="TKT-CMT2",
            content="This is a test comment.",
            author_id="AGENT-001",
            author_type="agent",
        )
        assert result.success is True
        assert result.data["content"] == "This is a test comment."
        assert result.data["author_type"] == "agent"
        assert "comment_id" in result.data

    @pytest.mark.asyncio
    async def test_add_comment_empty_fails(self, ticket):
        """add_comment with empty content fails."""
        result = await ticket.execute(
            "add_comment",
            COMPANY_ID,
            ticket_id="TKT-CMT3",
            content="",
        )
        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_comment_invalid_author_type(self, ticket):
        """add_comment with invalid author_type fails."""
        result = await ticket.execute(
            "add_comment",
            COMPANY_ID,
            ticket_id="TKT-CMT4",
            content="Comment",
            author_type="system",
        )
        assert result.success is False
        assert "agent" in result.error or "customer" in result.error

    @pytest.mark.asyncio
    async def test_add_comment_internal_flag(self, ticket):
        """add_comment can mark comment as internal."""
        result = await ticket.execute(
            "add_comment",
            COMPANY_ID,
            ticket_id="TKT-INT",
            content="Internal note",
            author_type="agent",
            internal=True,
        )
        assert result.success is True
        assert result.data["internal"] is True

    @pytest.mark.asyncio
    async def test_list_tickets_success(self, ticket):
        """list_tickets returns ticket list."""
        result = await ticket.execute("list_tickets", COMPANY_ID)
        assert result.success is True
        assert "tickets" in result.data

    @pytest.mark.asyncio
    async def test_list_tickets_status_filter(self, ticket):
        """list_tickets with status filter."""
        result = await ticket.execute(
            "list_tickets", COMPANY_ID, status="open",
        )
        assert result.success is True
        for t in result.data["tickets"]:
            assert t["status"] == "open"

    @pytest.mark.asyncio
    async def test_list_tickets_priority_filter(self, ticket):
        """list_tickets with priority filter."""
        result = await ticket.execute(
            "list_tickets", COMPANY_ID, priority="urgent",
        )
        assert result.success is True
        for t in result.data["tickets"]:
            assert t["priority"] == "urgent"

    @pytest.mark.asyncio
    async def test_get_ticket_history(self, ticket):
        """get_ticket_history returns audit trail."""
        result = await ticket.execute(
            "get_ticket_history",
            COMPANY_ID,
            ticket_id="TKT-HIST",
        )
        assert result.success is True
        assert "history_entries" in result.data
        assert result.data["total_entries"] > 0

    @pytest.mark.asyncio
    async def test_get_ticket_history_after_update(self, ticket):
        """Ticket history includes update events."""
        await ticket.execute(
            "get_ticket", COMPANY_ID, ticket_id="TKT-HUPD",
        )
        await ticket.execute(
            "update_ticket",
            COMPANY_ID,
            ticket_id="TKT-HUPD",
            status="in_progress",
        )
        result = await ticket.execute(
            "get_ticket_history",
            COMPANY_ID,
            ticket_id="TKT-HUPD",
        )
        field_changes = [
            e for e in result.data["history_entries"]
            if e.get("field") == "status"
        ]
        assert len(field_changes) >= 1

    @pytest.mark.asyncio
    async def test_unknown_action(self, ticket):
        """Unknown action returns error."""
        result = await ticket.execute("nonexistent", COMPANY_ID)
        assert result.success is False

    def test_ticket_tool_name(self, ticket):
        assert ticket.name == "ticket_system"

    def test_ticket_tool_actions_count(self, ticket):
        assert len(ticket.actions) == 6

    @pytest.mark.asyncio
    async def test_health_check(self, ticket):
        assert await ticket.health_check() is True


# ══════════════════════════════════════════════════════════════════
# 7. REGISTRY TESTS
# ══════════════════════════════════════════════════════════════════


class TestReActToolRegistry:
    """Test ReActToolRegistry."""

    def test_register_tool_sync(self):
        """Synchronous tool registration works."""
        reg = ReActToolRegistry()
        tool = _StubTool()
        reg.register_tool_sync(tool)
        assert "stub_tool" in reg._tools

    @pytest.mark.asyncio
    async def test_register_tool_async(self):
        """Async tool registration works."""
        reg = ReActToolRegistry()
        tool = _StubTool()
        await reg.register_tool(tool)
        assert "stub_tool" in reg._tools

    @pytest.mark.asyncio
    async def test_get_tool(self):
        """get_tool retrieves a registered tool."""
        reg = ReActToolRegistry()
        reg.register_tool_sync(_StubTool())
        tool = await reg.get_tool("stub_tool")
        assert tool is not None
        assert tool.name == "stub_tool"

    @pytest.mark.asyncio
    async def test_get_tool_not_found(self):
        """get_tool returns None for unknown tool."""
        reg = ReActToolRegistry()
        tool = await reg.get_tool("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """list_tools returns schemas for all registered tools."""
        reg = ReActToolRegistry()
        reg.initialize_defaults_sync()
        schemas = await reg.list_tools()
        names = [s.tool_name for s in schemas]
        assert "order_management" in names
        assert "billing_system" in names
        assert "crm_integration" in names
        assert "ticket_system" in names

    def test_get_available_actions(self, registry):
        """get_available_actions returns all tool actions."""
        actions = registry.get_available_actions()
        assert "order_management" in actions
        assert "get_order" in actions["order_management"]
        assert "billing_system" in actions
        assert "crm_integration" in actions
        assert "ticket_system" in actions

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, registry):
        """execute_tool dispatches to the correct tool."""
        result = await registry.execute_tool(
            "order_management",
            "get_order",
            COMPANY_ID,
            order_id="ORD-REG",
        )
        assert result.success is True
        assert result.data["order_id"] == "ORD-REG"

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_tool(self, registry):
        """execute_tool with unknown tool returns error."""
        result = await registry.execute_tool(
            "nonexistent_tool", "action", COMPANY_ID,
        )
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_action(self, registry):
        """execute_tool with unknown action returns error."""
        result = await registry.execute_tool(
            "order_management", "nonexistent_action", COMPANY_ID,
        )
        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_validation_failure(self, registry):
        """execute_tool validates params before execution."""
        result = await registry.execute_tool(
            "order_management",
            "get_order",
            COMPANY_ID,
            # missing required: order_id
        )
        assert result.success is False
        assert "Validation" in result.error

    @pytest.mark.asyncio
    async def test_execute_parallel(self, registry):
        """execute_parallel runs multiple calls concurrently."""
        calls = [
            ToolCall(
                tool_name="order_management",
                action="get_order",
                company_id=COMPANY_ID,
                params={"order_id": f"ORD-P-{i}"},
            )
            for i in range(5)
        ]
        results = await registry.execute_parallel(calls)
        assert len(results) == 5
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_parallel_mixed_tools(self, registry):
        """execute_parallel handles calls to different tools."""
        calls = [
            ToolCall(
                tool_name="order_management",
                action="get_order",
                company_id=COMPANY_ID,
                params={"order_id": "ORD-MIX"},
            ),
            ToolCall(
                tool_name="billing_system",
                action="get_invoice",
                company_id=COMPANY_ID,
                params={"invoice_id": "INV-MIX"},
            ),
            ToolCall(
                tool_name="crm_integration",
                action="get_customer",
                company_id=COMPANY_ID,
                params={"customer_id": "CUST-MIX"},
            ),
            ToolCall(
                tool_name="ticket_system",
                action="get_ticket",
                company_id=COMPANY_ID,
                params={"ticket_id": "TKT-MIX"},
            ),
        ]
        results = await registry.execute_parallel(calls)
        assert len(results) == 4
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_parallel_partial_failure(self, registry):
        """execute_parallel continues even if some calls fail."""
        calls = [
            ToolCall(
                tool_name="order_management",
                action="get_order",
                company_id=COMPANY_ID,
                params={"order_id": "ORD-OK"},
            ),
            ToolCall(
                tool_name="order_management",
                action="nonexistent_action",
                company_id=COMPANY_ID,
            ),
        ]
        results = await registry.execute_parallel(calls)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    def test_initialize_defaults_sync(self):
        """Synchronous default initialization registers all tools."""
        reg = ReActToolRegistry()
        reg.initialize_defaults_sync()
        assert len(reg._tools) == 4
        assert reg._initialized is True

    def test_initialize_defaults_idempotent(self):
        """Calling initialize_defaults_sync twice doesn't duplicate tools."""
        reg = ReActToolRegistry()
        reg.initialize_defaults_sync()
        reg.initialize_defaults_sync()
        assert len(reg._tools) == 4

    @pytest.mark.asyncio
    async def test_initialize_defaults_async(self):
        """Async default initialization registers all tools."""
        reg = ReActToolRegistry()
        await reg.initialize_defaults()
        assert len(reg._tools) == 4
        assert reg._initialized is True

    @pytest.mark.asyncio
    async def test_registry_company_scoping_order(self, registry):
        """Registry passes company_id for scoping."""
        # Register an order under COMPANY_ID
        await registry.execute_tool(
            "order_management", "get_order", COMPANY_ID, order_id="ORD-REG-SCOPE",
        )
        # Try from OTHER_COMPANY
        result = await registry.execute_tool(
            "order_management", "get_order", OTHER_COMPANY, order_id="ORD-REG-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_registry_company_scoping_crm(self, registry):
        """Registry CRM company scoping works."""
        await registry.execute_tool(
            "crm_integration", "get_customer", COMPANY_ID, customer_id="CUST-REG-SCOPE",
        )
        result = await registry.execute_tool(
            "crm_integration", "get_customer", OTHER_COMPANY, customer_id="CUST-REG-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_registry_company_scoping_ticket(self, registry):
        """Registry ticket company scoping works."""
        await registry.execute_tool(
            "ticket_system", "get_ticket", COMPANY_ID, ticket_id="TKT-REG-SCOPE",
        )
        result = await registry.execute_tool(
            "ticket_system", "get_ticket", OTHER_COMPANY, ticket_id="TKT-REG-SCOPE",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_registry_company_scoping_billing(self, registry):
        """Registry billing company scoping works."""
        await registry.execute_tool(
            "billing_system", "get_invoice", COMPANY_ID, invoice_id="INV-REG-SCOPE",
        )
        result = await registry.execute_tool(
            "billing_system", "get_invoice", OTHER_COMPANY, invoice_id="INV-REG-SCOPE",
        )
        assert result.success is False
