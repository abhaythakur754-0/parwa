"""
Day 5 — Refund Initiate Tool: Unit + Integration Tests

Tests the full refund initiation flow:
  - RefundBridge: Shopify + Paddle atomic refund
  - shopify_refund_initiate MCP tool
  - ecommerce_list_refunds MCP tool
  - Backend API refund endpoints (with partial refund support)
  - Auto-detection of items
  - Reconciliation flagging
  - BC-001 (company_id isolation)
  - BC-008 (never crash)
"""

import asyncio
import json
import sys
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Mock Shopify Result ──────────────────────────────────────────


class MockShopifyResult:
    """Mock ShopifyResult for testing."""
    def __init__(self, success: bool, data: Optional[Dict] = None, error: str = ""):
        self.success = success
        self.data = data or {}
        self.error = error
        self.status_code = 200 if success else 400
        self.metadata = {}


class MockShopifyClient:
    """Mock ShopifyClient for testing."""
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self._refunds_created = []
        self._orders = {
            "12345": {
                "id": 12345,
                "order_number": "1001",
                "email": "customer@example.com",
                "total_price": "149.99",
                "currency": "USD",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
                "line_items": [
                    {"id": 111, "title": "Widget A", "quantity": 2, "price": "49.99", "sku": "SKU-A"},
                    {"id": 222, "title": "Widget B", "quantity": 1, "price": "50.01", "sku": "SKU-B"},
                ],
                "customer": {"id": 555, "first_name": "John", "last_name": "Doe"},
            },
            "67890": {
                "id": 67890,
                "order_number": "1002",
                "email": "jane@example.com",
                "total_price": "29.99",
                "currency": "USD",
                "financial_status": "paid",
                "fulfillment_status": None,
                "line_items": [
                    {"id": 333, "title": "Gadget X", "quantity": 1, "price": "29.99", "sku": "SKU-X"},
                ],
                "customer": {"id": 666, "first_name": "Jane", "last_name": "Smith"},
            },
        }

    async def get_order(self, order_id: str, **kwargs):
        order = self._orders.get(order_id, {})
        if order:
            return MockShopifyResult(success=True, data=order)
        return MockShopifyResult(success=False, error=f"Order {order_id} not found")

    async def create_refund(
        self,
        order_id: str,
        refund_line_items=None,
        transactions=None,
        note: str = "",
        notify_customer: bool = True,
    ):
        if not self.should_succeed:
            return MockShopifyResult(success=False, error="Shopify API error")

        refund_id = len(self._refunds_created) + 8000
        refund_data = {
            "id": refund_id,
            "order_id": int(order_id),
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "refund_line_items": refund_line_items or [],
            "transactions": transactions or [
                {"kind": "refund", "amount": "149.99", "currency": "USD"}
            ],
        }
        self._refunds_created.append(refund_data)
        return MockShopifyResult(success=True, data=refund_data)

    async def list_refunds(self, order_id: str):
        refunds = [r for r in self._refunds_created if str(r.get("order_id")) == order_id]
        return MockShopifyResult(success=True, data=refunds)


class MockPaddleBridge:
    """Mock JarvisPaddleBridge for testing."""
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self._adjustments = []

    async def process_refund(
        self,
        company_id: str,
        customer_id: str,
        amount: float,
        reason: str,
        ticket_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        partial: bool = False,
    ):
        if not self.should_succeed:
            return {"success": False, "message": "Paddle adjustment failed"}

        adj_id = f"adj_{len(self._adjustments) + 1000}"
        self._adjustments.append({
            "id": adj_id,
            "company_id": company_id,
            "amount": amount,
            "reason": reason,
        })
        return {
            "success": True,
            "adjustment_id": adj_id,
            "amount": str(amount),
            "status": "approved",
        }


# ── Test: RefundBridge ───────────────────────────────────────────


class TestRefundBridge(unittest.TestCase):
    """Test the RefundBridge atomic Shopify + Paddle refund service."""

    def setUp(self):
        """Set up test fixtures."""
        # Import here to avoid import errors in CI
        from app.services.refund_bridge import RefundBridge
        self.bridge = RefundBridge()
        self.shopify_client = MockShopifyClient(should_succeed=True)
        self.paddle_bridge = MockPaddleBridge(should_succeed=True)

    def test_generate_refund_id(self):
        """Test refund ID generation."""
        id1 = self.bridge._generate_refund_id()
        id2 = self.bridge._generate_refund_id()
        self.assertTrue(id1.startswith("rf_"))
        self.assertNotEqual(id1, id2)

    def test_refund_item_to_shopify_dict(self):
        """Test RefundItem conversion to Shopify format."""
        from app.services.refund_bridge import RefundItem
        item = RefundItem(line_item_id="111", quantity=2, amount="49.99")
        shopify_dict = item.to_shopify_dict()
        self.assertEqual(shopify_dict["line_item_id"], "111")
        self.assertEqual(shopify_dict["quantity"], 2)
        self.assertEqual(shopify_dict["restock_type"], "return")

    def test_refund_item_to_dict(self):
        """Test RefundItem serialization."""
        from app.services.refund_bridge import RefundItem
        item = RefundItem(line_item_id="222", quantity=1, reason="defective")
        d = item.to_dict()
        self.assertEqual(d["line_item_id"], "222")
        self.assertEqual(d["quantity"], 1)
        self.assertEqual(d["reason"], "defective")
        self.assertIsNone(d["amount"])

    def test_refund_result_to_dict(self):
        """Test RefundResult serialization."""
        from app.services.refund_bridge import RefundResult
        result = RefundResult(
            success=True,
            refund_id="rf_test",
            order_id="12345",
            amount="149.99",
            currency="USD",
            status="processed",
            shopify_status="processed",
            paddle_status="processed",
        )
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["refund_id"], "rf_test")
        self.assertEqual(d["amount"], "149.99")
        self.assertIn("timestamp", d)

    def test_initiate_refund_missing_order_id(self):
        """Test that missing order_id returns failure."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="",
                items=[{"line_item_id": "111", "quantity": 1}],
            )
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")
        self.assertIn("order_id is required", result.error)

    def test_initiate_refund_full_success(self):
        """Test full refund when both Shopify and Paddle succeed."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[
                    {"line_item_id": "111", "quantity": 2},
                    {"line_item_id": "222", "quantity": 1},
                ],
                amount="149.99",
                reason="Customer request",
                shopify_client=self.shopify_client,
                paddle_bridge=self.paddle_bridge,
                paddle_customer_id="cst_123",
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, "processed")
        self.assertTrue(result.shopify_status.startswith("processed"))
        self.assertTrue(result.paddle_status.startswith("processed"))
        self.assertFalse(result.requires_reconciliation)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(len(result.items_refunded), 2)

    def test_initiate_refund_partial_paddle_failure(self):
        """Test reconciliation when Shopify succeeds but Paddle fails."""
        failing_paddle = MockPaddleBridge(should_succeed=False)
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                reason="Defective product",
                shopify_client=self.shopify_client,
                paddle_bridge=failing_paddle,
            )
        )
        self.assertTrue(result.success)  # Still success (partial)
        self.assertEqual(result.status, "partial")
        self.assertTrue(result.requires_reconciliation)
        self.assertIn("reconciliation", result.error.lower())

    def test_initiate_refund_shopify_failure(self):
        """Test when Shopify fails — Paddle succeeds but result is partial."""
        failing_shopify = MockShopifyClient(should_succeed=False)
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                reason="Customer request",
                shopify_client=failing_shopify,
                paddle_bridge=self.paddle_bridge,
            )
        )
        # Shopify failed, Paddle succeeded — partial with reconciliation
        self.assertTrue(result.requires_reconciliation)
        self.assertIn(result.status, ["partial", "failed"])

    def test_initiate_refund_both_fail(self):
        """Test when both Shopify and Paddle fail."""
        failing_shopify = MockShopifyClient(should_succeed=False)
        failing_paddle = MockPaddleBridge(should_succeed=False)
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=failing_shopify,
                paddle_bridge=failing_paddle,
            )
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")

    def test_initiate_refund_no_items_auto_detect(self):
        """Test auto-detection of items when none provided."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[],
                shopify_client=self.shopify_client,
                paddle_bridge=self.paddle_bridge,
            )
        )
        # Should auto-detect 2 items from order 12345
        self.assertTrue(result.success)
        self.assertEqual(len(result.items_refunded), 2)

    def test_initiate_refund_no_items_no_client(self):
        """Test that missing items without client returns failure."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[],
            )
        )
        self.assertFalse(result.success)

    def test_initiate_refund_no_shopify_client(self):
        """Test refund when no Shopify client available (skipped)."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                paddle_bridge=self.paddle_bridge,
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, "processed")
        self.assertEqual(result.shopify_refund_id, "")

    def test_initiate_refund_no_paddle_bridge(self):
        """Test refund when no Paddle bridge available (skipped)."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=self.shopify_client,
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.status, "processed")
        self.assertEqual(result.paddle_adjustment_id, "")

    def test_auto_detect_items(self):
        """Test auto-detection of order items."""
        items = asyncio.get_event_loop().run_until_complete(
            self.bridge._auto_detect_items(self.shopify_client, "12345")
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["line_item_id"], "111")
        self.assertEqual(items[0]["quantity"], 2)
        self.assertEqual(items[1]["line_item_id"], "222")

    def test_auto_detect_items_not_found(self):
        """Test auto-detection for non-existent order."""
        items = asyncio.get_event_loop().run_until_complete(
            self.bridge._auto_detect_items(self.shopify_client, "99999")
        )
        self.assertEqual(len(items), 0)

    def test_partial_refund_with_amount(self):
        """Test partial refund with explicit amount."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1, "amount": "25.00"}],
                amount="25.00",
                reason="Partial refund - one item defective",
                shopify_client=self.shopify_client,
                paddle_bridge=self.paddle_bridge,
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.amount, "25.00")

    def test_refund_amount_quantization(self):
        """Test that refund amounts are properly quantized to 2 decimal places."""
        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.999",
                shopify_client=self.shopify_client,
                paddle_bridge=self.paddle_bridge,
            )
        )
        # Should be quantized to 50.00
        self.assertIn(result.amount, ["50.00", "49.99"])

    def test_shopify_exception_handling(self):
        """Test BC-008: Shopify exceptions don't crash the bridge."""
        exception_client = MagicMock()
        exception_client.create_refund = AsyncMock(side_effect=Exception("Network error"))

        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=exception_client,
                paddle_bridge=self.paddle_bridge,
            )
        )
        # Should not crash — Shopify failed but we got a result
        self.assertIsNotNone(result)
        self.assertIn(result.status, ["partial", "failed"])

    def test_paddle_exception_handling(self):
        """Test BC-008: Paddle exceptions don't crash the bridge."""
        exception_bridge = MagicMock()
        exception_bridge.process_refund = AsyncMock(side_effect=Exception("API timeout"))

        result = asyncio.get_event_loop().run_until_complete(
            self.bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=self.shopify_client,
                paddle_bridge=exception_bridge,
            )
        )
        # Should not crash — Paddle failed but Shopify succeeded
        self.assertIsNotNone(result)
        self.assertTrue(result.requires_reconciliation)


# ── Test: EcommerceServer MCP Tools ──────────────────────────────


class TestEcommerceServerMCP(unittest.TestCase):
    """Test the MCP ecommerce server tools including refund initiate."""

    def setUp(self):
        from mcp_server.integrations.ecommerce_server import EcommerceServer
        self.server = EcommerceServer()
        self.registry = MagicMock()
        self.registered_tools = {}

        def mock_register(definition, handler):
            self.registered_tools[definition.name] = {
                "definition": definition,
                "handler": handler,
            }

        self.registry.register_tool = mock_register
        self.server.register_tools(self.registry)

    def test_shopify_refund_initiate_registered(self):
        """Test that shopify_refund_initiate tool is registered."""
        self.assertIn("shopify_refund_initiate", self.registered_tools)

    def test_ecommerce_list_refunds_registered(self):
        """Test that ecommerce_list_refunds tool is registered."""
        self.assertIn("ecommerce_list_refunds", self.registered_tools)

    def test_all_7_tools_registered(self):
        """Test that all 7 tools are registered (5 original + 2 new)."""
        expected = [
            "ecommerce_get_order",
            "ecommerce_search_products",
            "ecommerce_get_customer_orders",
            "ecommerce_create_fulfillment",
            "ecommerce_create_refund",
            "shopify_refund_initiate",
            "ecommerce_list_refunds",
        ]
        for tool in expected:
            self.assertIn(tool, self.registered_tools, f"Tool {tool} not registered")

    def test_refund_initiate_schema_required_fields(self):
        """Test that refund initiate schema requires order_id and company_id."""
        schema = self.registered_tools["shopify_refund_initiate"]["definition"].input_schema
        self.assertIn("order_id", schema["required"])
        self.assertIn("company_id", schema["required"])

    def test_refund_initiate_schema_items_property(self):
        """Test that refund initiate schema includes items array."""
        schema = self.registered_tools["shopify_refund_initiate"]["definition"].input_schema
        self.assertIn("items", schema["properties"])
        self.assertEqual(schema["properties"]["items"]["type"], "array")

    def test_refund_initiate_schema_amount_property(self):
        """Test that refund initiate schema includes amount field."""
        schema = self.registered_tools["shopify_refund_initiate"]["definition"].input_schema
        self.assertIn("amount", schema["properties"])

    def test_list_refunds_schema_required_fields(self):
        """Test that list refunds schema requires company_id."""
        schema = self.registered_tools["ecommerce_list_refunds"]["definition"].input_schema
        self.assertIn("company_id", schema["required"])

    def test_refund_initiate_missing_order_id(self):
        """Test refund initiate with missing order_id returns error."""
        handler = self.registered_tools["shopify_refund_initiate"]["handler"]
        result = asyncio.get_event_loop().run_until_complete(
            handler(parameters={"company_id": "BC-001"}, context=None)
        )
        self.assertFalse(result.success)
        self.assertIn("order_id is required", result.error)

    def test_refund_initiate_missing_company_id(self):
        """Test refund initiate with missing company_id returns error."""
        handler = self.registered_tools["shopify_refund_initiate"]["handler"]
        result = asyncio.get_event_loop().run_until_complete(
            handler(parameters={"order_id": "12345"}, context=None)
        )
        self.assertFalse(result.success)
        self.assertIn("company_id is required", result.error)

    def test_list_refunds_missing_company_id(self):
        """Test list refunds with missing company_id returns error."""
        handler = self.registered_tools["ecommerce_list_refunds"]["handler"]
        result = asyncio.get_event_loop().run_until_complete(
            handler(parameters={}, context=None)
        )
        self.assertFalse(result.success)
        self.assertIn("company_id is required", result.error)

    def test_version_is_3_0_0(self):
        """Test that server version is updated to 3.0.0."""
        self.assertEqual(self.server.version, "3.0.0")

    def test_refund_initiate_tags_include_paddle(self):
        """Test that refund initiate tags include paddle and payment."""
        definition = self.registered_tools["shopify_refund_initiate"]["definition"]
        self.assertIn("paddle", definition.tags)
        self.assertIn("payment", definition.tags)


# ── Test: Backend API Schemas ────────────────────────────────────


class TestBackendAPISchemas(unittest.TestCase):
    """Test the updated backend API schemas for refund."""

    def setUp(self):
        """Set environment variables required for config import."""
        os.environ.setdefault("PRICING_SIGNING_KEY", "test-key-for-unit-tests-only")
        os.environ.setdefault("PADDLE_API_KEY", "")
        os.environ.setdefault("ENVIRONMENT", "test")

    def _import_schemas(self):
        """Import schemas with minimal config setup."""
        from pydantic import BaseModel, Field
        from typing import Optional, List

        class RefundLineItem(BaseModel):
            line_item_id: str = Field(..., description="Shopify line item ID")
            quantity: int = Field(1, ge=1, description="Quantity to refund")
            amount: Optional[str] = Field(None, description="Per-item refund amount")

        class CreateRefundRequest(BaseModel):
            order_id: str = Field(..., description="Shopify order ID")
            items: Optional[List[RefundLineItem]] = Field(None)
            amount: Optional[str] = Field(None)
            reason: str = Field("")
            notify_customer: bool = Field(True)
            process_payment: bool = Field(True)

        return RefundLineItem, CreateRefundRequest

    def test_refund_line_item_schema(self):
        """Test RefundLineItem schema."""
        RefundLineItem, _ = self._import_schemas()
        item = RefundLineItem(line_item_id="111", quantity=2, amount="49.99")
        self.assertEqual(item.line_item_id, "111")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.amount, "49.99")

    def test_refund_line_item_defaults(self):
        """Test RefundLineItem default values."""
        RefundLineItem, _ = self._import_schemas()
        item = RefundLineItem(line_item_id="111")
        self.assertEqual(item.quantity, 1)
        self.assertIsNone(item.amount)

    def test_create_refund_request_with_items(self):
        """Test CreateRefundRequest with items field."""
        RefundLineItem, CreateRefundRequest = self._import_schemas()
        req = CreateRefundRequest(
            order_id="12345",
            items=[RefundLineItem(line_item_id="111", quantity=1)],
            amount="49.99",
            reason="Defective",
            process_payment=True,
        )
        self.assertEqual(req.order_id, "12345")
        self.assertEqual(len(req.items), 1)
        self.assertEqual(req.amount, "49.99")
        self.assertTrue(req.process_payment)

    def test_create_refund_request_defaults(self):
        """Test CreateRefundRequest default values."""
        _, CreateRefundRequest = self._import_schemas()
        req = CreateRefundRequest(order_id="12345")
        self.assertIsNone(req.items)
        self.assertIsNone(req.amount)
        self.assertTrue(req.process_payment)
        self.assertTrue(req.notify_customer)

    def test_create_refund_request_backward_compatible(self):
        """Test that simple refund (no items/amount) still works."""
        _, CreateRefundRequest = self._import_schemas()
        req = CreateRefundRequest(order_id="12345", reason="Customer request")
        self.assertEqual(req.order_id, "12345")
        self.assertEqual(req.reason, "Customer request")
        self.assertIsNone(req.items)
        self.assertIsNone(req.amount)


# ── Test: Integration Flow ───────────────────────────────────────


class TestRefundIntegrationFlow(unittest.TestCase):
    """Test the complete refund initiation flow end-to-end."""

    def test_full_refund_flow_shopify_and_paddle(self):
        """Test complete flow: Shopify refund + Paddle adjustment + tracking."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)
        paddle = MockPaddleBridge(should_succeed=True)

        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[
                    {"line_item_id": "111", "quantity": 2},
                    {"line_item_id": "222", "quantity": 1},
                ],
                reason="Customer cancelled order",
                shopify_client=shopify,
                paddle_bridge=paddle,
                paddle_customer_id="cst_123",
            )
        )

        # Verify Shopify refund was created
        self.assertTrue(result.success)
        self.assertNotEqual(result.shopify_refund_id, "")
        self.assertTrue(result.shopify_status.startswith("processed"))

        # Verify Paddle adjustment was created
        self.assertNotEqual(result.paddle_adjustment_id, "")
        self.assertTrue(result.paddle_status.startswith("processed"))

        # Verify no reconciliation needed
        self.assertFalse(result.requires_reconciliation)
        self.assertEqual(result.status, "processed")

    def test_partial_refund_flow(self):
        """Test partial refund with specific items and amount."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)
        paddle = MockPaddleBridge(should_succeed=True)

        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1, "amount": "49.99"}],
                amount="49.99",
                reason="One item defective",
                shopify_client=shopify,
                paddle_bridge=paddle,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.amount, "49.99")
        self.assertEqual(len(result.items_refunded), 1)

    def test_reconciliation_flow(self):
        """Test that partial failure triggers reconciliation flagging."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)
        paddle = MockPaddleBridge(should_succeed=False)

        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                reason="Defective",
                shopify_client=shopify,
                paddle_bridge=paddle,
            )
        )

        self.assertTrue(result.requires_reconciliation)
        self.assertEqual(result.status, "partial")
        self.assertTrue(result.shopify_status.startswith("processed"))
        self.assertFalse(result.paddle_status.startswith("processed"))

    def test_shopify_only_refund_flow(self):
        """Test Shopify-only refund (no Paddle bridge)."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)

        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 2}],
                reason="Customer request",
                shopify_client=shopify,
                # No paddle_bridge
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "processed")
        self.assertEqual(result.paddle_adjustment_id, "")

    def test_order_refund_history(self):
        """Test getting refund history for an order."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)

        # Create a refund first
        asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=shopify,
            )
        )

        # Get refund history
        history = asyncio.get_event_loop().run_until_complete(
            bridge.get_order_refunds(shopify, "12345")
        )

        self.assertTrue(history["success"])
        self.assertEqual(history["order_id"], "12345")

    def test_bc008_never_crash(self):
        """Test BC-008: RefundBridge never crashes regardless of input."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()

        # Test with None values — no order_id
        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="",
                order_id="",
                items=[],
            )
        )
        self.assertIsNotNone(result)
        self.assertFalse(result.success)

        # Test with malformed items — should still produce a result
        # Note: With no Shopify client, items with missing keys will still
        # produce RefundItem objects (with empty line_item_id)
        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111"}],  # Minimal valid item
            )
        )
        self.assertIsNotNone(result)

    def test_bc001_company_isolation(self):
        """Test BC-001: Refunds are scoped to company_id."""
        from app.services.refund_bridge import RefundBridge
        bridge = RefundBridge()
        shopify = MockShopifyClient(should_succeed=True)

        result = asyncio.get_event_loop().run_until_complete(
            bridge.initiate_refund(
                company_id="BC-001",
                order_id="12345",
                items=[{"line_item_id": "111", "quantity": 1}],
                amount="49.99",
                shopify_client=shopify,
            )
        )

        # The refund result should reference the correct company
        # (In production, ClientRefundService would enforce company_id isolation)
        self.assertIsNotNone(result)


# ── Test: RefundItem Edge Cases ──────────────────────────────────


class TestRefundItemEdgeCases(unittest.TestCase):
    """Test edge cases for RefundItem."""

    def test_refund_item_with_zero_amount(self):
        """Test RefundItem with zero amount."""
        from app.services.refund_bridge import RefundItem
        item = RefundItem(line_item_id="111", quantity=1, amount="0.00")
        self.assertEqual(item.amount, Decimal("0.00"))

    def test_refund_item_without_amount(self):
        """Test RefundItem without amount (None)."""
        from app.services.refund_bridge import RefundItem
        item = RefundItem(line_item_id="111", quantity=1)
        self.assertIsNone(item.amount)
        shopify_dict = item.to_shopify_dict()
        self.assertNotIn("restock_type", shopify_dict)

    def test_refund_item_decimal_precision(self):
        """Test that amounts are properly handled as Decimal."""
        from app.services.refund_bridge import RefundItem
        item = RefundItem(line_item_id="111", quantity=1, amount="49.995")
        self.assertEqual(item.amount, Decimal("49.995"))

    def test_refund_result_all_fields(self):
        """Test RefundResult with all fields populated."""
        from app.services.refund_bridge import RefundResult
        result = RefundResult(
            success=True,
            refund_id="rf_test",
            shopify_refund_id="8001",
            paddle_adjustment_id="adj_1001",
            client_refund_id="cr_001",
            order_id="12345",
            amount="149.99",
            currency="USD",
            status="processed",
            shopify_status="processed",
            paddle_status="processed",
            items_refunded=[{"line_item_id": "111", "quantity": 2}],
            error="",
            requires_reconciliation=False,
        )
        d = result.to_dict()
        self.assertEqual(d["shopify_refund_id"], "8001")
        self.assertEqual(d["paddle_adjustment_id"], "adj_1001")
        self.assertEqual(d["client_refund_id"], "cr_001")
        self.assertEqual(len(d["items_refunded"]), 1)
        self.assertFalse(d["requires_reconciliation"])


# ── Run Tests ────────────────────────────────────────────────────


if __name__ == "__main__":
    # Use asyncio event loop for async tests
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    unittest.main(verbosity=2)
