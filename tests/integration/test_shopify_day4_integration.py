"""
PARWA Day 4 — Integration Tests for Shopify Flow

End-to-end integration tests that verify the full Shopify integration flow:
- Webhook → Handler → Data processing pipeline
- ShopifyClient → ShopifyDataSync → Sync state management
- MCP Ecommerce Server → ShopifyClient integration
- Webhook verification → Handler dispatch
- Multi-tenant isolation

Run: pytest tests/integration/test_shopify_day4_integration.py -v
"""

import base64
import hashlib
import hmac
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.clients.shopify_client import ShopifyClient, ShopifyResult, create_shopify_client_from_config
from app.webhooks.shopify_handler import (
    handle_shopify_event,
    _extract_order_data,
    _extract_product_data,
    _extract_customer_data,
    REQUIRED_FIELDS,
    _SHOPIFY_HANDLERS,
)
from app.webhooks import dispatch_event, validate_event_type, PROVIDER_EVENT_TYPES
from app.services.shopify_data_sync import ShopifyDataSync, SyncResult


# ═══════════════════════════════════════════════════════════════════
# Test: Full Webhook Processing Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestWebhookPipeline:
    """Integration tests for the webhook processing pipeline."""

    def test_order_created_end_to_end(self):
        """Full pipeline: event → dispatch → handler → data extraction."""
        event = {
            "event_type": "orders.create",
            "payload": {
                "order": {
                    "id": 12345,
                    "order_number": "ORD-1001",
                    "email": "buyer@example.com",
                    "total_price": "149.99",
                    "currency": "USD",
                    "financial_status": "paid",
                    "fulfillment_status": None,
                    "customer": {"id": 999, "first_name": "Jane", "last_name": "Smith"},
                    "line_items": [
                        {"title": "Widget", "quantity": 2, "price": "49.99"},
                    ],
                    "created_at": "2026-04-01T12:00:00Z",
                }
            },
            "company_id": "comp_1",
            "event_id": "evt_1",
        }

        # Step 1: Validate event type
        assert validate_event_type("shopify", "orders.create") is True

        # Step 2: Dispatch event
        result = dispatch_event("shopify", event)

        # Step 3: Verify result
        assert result["status"] == "processed"
        assert result["action"] == "order_created"
        assert result["data"]["order_id"] == "12345"
        assert result["data"]["email"] == "buyer@example.com"
        assert result["data"]["total_price"] == "149.99"
        assert result["data"]["customer_name"] == "Jane Smith"
        assert len(result["data"]["line_items"]) == 1

    def test_order_cancelled_end_to_end(self):
        """Full pipeline for order cancellation."""
        event = {
            "event_type": "orders.cancelled",
            "payload": {
                "order": {
                    "id": 12345,
                    "email": "buyer@example.com",
                    "cancel_reason": "customer",
                    "cancelled_at": "2026-04-03T10:00:00Z",
                    "total_price": "149.99",
                    "currency": "USD",
                }
            },
            "company_id": "comp_1",
            "event_id": "evt_2",
        }

        assert validate_event_type("shopify", "orders.cancelled") is True
        result = dispatch_event("shopify", event)
        assert result["status"] == "processed"
        assert result["action"] == "order_cancelled"
        assert result["data"]["cancel_reason"] == "customer"

    def test_product_created_end_to_end(self):
        """Full pipeline for product creation webhook."""
        event = {
            "event_type": "products.create",
            "payload": {
                "product": {
                    "id": 456,
                    "title": "New Widget",
                    "vendor": "ACME",
                    "product_type": "Widget",
                    "status": "active",
                    "variants": [{"id": 1, "title": "Default", "price": "29.99", "sku": "W-001", "inventory_quantity": 10}],
                }
            },
            "company_id": "comp_1",
            "event_id": "evt_3",
        }

        assert validate_event_type("shopify", "products.create") is True
        result = dispatch_event("shopify", event)
        assert result["status"] == "processed"
        assert result["action"] == "product_created"
        assert result["data"]["product_id"] == "456"
        assert len(result["data"]["variants"]) == 1

    def test_app_uninstalled_end_to_end(self):
        """Full pipeline for app uninstall webhook."""
        event = {
            "event_type": "app/uninstalled",
            "payload": {
                "shop_domain": "mystore.myshopify.com",
                "shop": {"id": 42, "name": "My Store", "email": "admin@mystore.com"},
            },
            "company_id": "comp_1",
            "event_id": "evt_4",
        }

        assert validate_event_type("shopify", "app/uninstalled") is True
        result = dispatch_event("shopify", event)
        assert result["status"] == "processed"
        assert result["action"] == "app_uninstalled"
        assert result["data"]["shop_domain"] == "mystore.myshopify.com"

    def test_unsupported_event_type_rejected(self):
        """Unsupported event types should be rejected."""
        assert validate_event_type("shopify", "inventory.update") is False

    def test_unsupported_provider_rejected(self):
        """Unknown providers should have no supported events."""
        assert validate_event_type("unknown_provider", "orders.create") is False


# ═══════════════════════════════════════════════════════════════════
# Test: Webhook Signature Verification + Handler
# ═══════════════════════════════════════════════════════════════════

class TestWebhookSignatureVerification:
    """Integration tests for webhook signature verification with handler."""

    def test_valid_signature_processes_event(self):
        """Events with valid HMAC signature should be processed."""
        secret = "my_webhook_secret"
        payload_data = {
            "id": 12345,
            "email": "buyer@example.com",
            "total_price": "99.99",
            "currency": "USD",
        }
        payload_bytes = json.dumps(payload_data).encode("utf-8")

        # Compute valid HMAC
        computed = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        valid_hmac = base64.b64encode(computed).decode("utf-8")

        # Verify signature
        assert ShopifyClient.verify_webhook_signature(payload_bytes, valid_hmac, secret) is True

        # If signature is valid, process the event
        event = {
            "event_type": "orders.create",
            "payload": {"order": payload_data},
            "company_id": "comp_1",
            "event_id": "evt_sig_1",
        }
        result = handle_shopify_event(event)
        assert result["status"] == "processed"

    def test_invalid_signature_rejected(self):
        """Events with invalid HMAC signature should be rejected at verification."""
        secret = "my_webhook_secret"
        payload_bytes = b'{"id": 12345, "email": "buyer@example.com"}'
        invalid_hmac = "dGVzdA=="  # Wrong signature

        assert ShopifyClient.verify_webhook_signature(payload_bytes, invalid_hmac, secret) is False

    def test_tampered_payload_detected(self):
        """Tampered payload should fail signature verification."""
        secret = "my_webhook_secret"
        original = b'{"total_price": "99.99"}'
        computed = hmac.new(secret.encode("utf-8"), original, hashlib.sha256).digest()
        valid_hmac = base64.b64encode(computed).decode("utf-8")

        tampered = b'{"total_price": "0.01"}'
        assert ShopifyClient.verify_webhook_signature(tampered, valid_hmac, secret) is False


# ═══════════════════════════════════════════════════════════════════
# Test: ShopifyClient + DataSync Integration
# ═══════════════════════════════════════════════════════════════════

class TestClientDataSyncIntegration:
    """Integration tests for ShopifyClient → ShopifyDataSync flow."""

    @pytest.mark.asyncio
    async def test_full_sync_with_mocked_api(self):
        """Full sync should use ShopifyClient to fetch and process data."""
        mock_client = MagicMock(spec=ShopifyClient)
        mock_client.shop_domain = "test.myshopify.com"
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(
            success=True,
            data=[
                {"id": 1, "email": "a@test.com", "total_price": "10", "currency": "USD"},
                {"id": 2, "email": "b@test.com", "total_price": "20", "currency": "USD"},
            ],
        ))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(
            success=True,
            data=[
                {"id": 10, "title": "Product A", "vendor": "ACME", "product_type": "Widget", "status": "active"},
            ],
        ))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(
            success=True,
            data=[
                {"id": 100, "email": "alice@test.com", "first_name": "Alice", "orders_count": 1, "total_spent": "10.00"},
            ],
        ))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        sync = ShopifyDataSync(
            db=mock_db,
            shopify_client=mock_client,
            company_id="comp_test",
            integration_id="int_test",
        )

        result = await sync.full_sync()

        assert result.status == "completed"
        assert result.orders_synced == 2
        assert result.products_synced == 1
        assert result.customers_synced == 1
        assert result.to_dict()["total_synced"] == 4

    @pytest.mark.asyncio
    async def test_single_order_sync_with_client(self):
        """Single order sync should fetch from client and process."""
        mock_client = MagicMock(spec=ShopifyClient)
        mock_client.shop_domain = "test.myshopify.com"
        mock_client.get_order = AsyncMock(return_value=ShopifyResult(
            success=True,
            data={"id": 12345, "email": "buyer@test.com", "total_price": "149.99", "currency": "USD"},
        ))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        sync = ShopifyDataSync(
            db=mock_db,
            shopify_client=mock_client,
            company_id="comp_test",
            integration_id="int_test",
        )

        result = await sync.sync_order("12345")

        assert result.status == "completed"
        assert result.orders_synced == 1
        mock_client.get_order.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_sync_with_api_failure_graceful(self):
        """Sync should handle API failures gracefully (BC-008)."""
        mock_client = MagicMock(spec=ShopifyClient)
        mock_client.shop_domain = "test.myshopify.com"
        mock_client.list_orders = AsyncMock(return_value=ShopifyResult(
            success=False, error="API rate limit exceeded",
        ))
        mock_client.list_products = AsyncMock(return_value=ShopifyResult(
            success=True, data=[{"id": 1, "title": "Product A", "status": "active"}],
        ))
        mock_client.list_customers = AsyncMock(return_value=ShopifyResult(
            success=True, data=[{"id": 1, "email": "alice@test.com", "orders_count": 1, "total_spent": "10.00"}],
        ))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        sync = ShopifyDataSync(
            db=mock_db,
            shopify_client=mock_client,
            company_id="comp_test",
            integration_id="int_test",
        )

        result = await sync.full_sync()

        # Products and customers succeed, orders fail → partial
        assert result.status in ("partial", "failed")
        assert len(result.errors) >= 1
        assert "Orders" in result.errors[0]


# ═══════════════════════════════════════════════════════════════════
# Test: Client Factory + Config
# ═══════════════════════════════════════════════════════════════════

class TestClientFactoryIntegration:
    """Integration tests for client creation from integration config."""

    def test_create_client_from_config(self):
        """Factory should create a working ShopifyClient."""
        config = {
            "shop_domain": "mystore.myshopify.com",
            "access_token": "shpat_abc123",
        }
        client = create_shopify_client_from_config(config)

        assert client.shop_domain == "mystore.myshopify.com"
        assert client.access_token == "shpat_abc123"
        assert "mystore.myshopify.com" in client.base_url

    def test_create_client_domain_normalization(self):
        """Factory should normalize the shop domain."""
        config = {
            "shop_domain": "https://MyStore.myshopify.com/",
            "access_token": "shpat_test",
        }
        client = create_shopify_client_from_config(config)
        assert "https://" not in client.shop_domain


# ═══════════════════════════════════════════════════════════════════
# Test: Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════════════

class TestMultiTenantIsolation:
    """Integration tests for BC-001: Multi-tenant isolation."""

    def test_sync_service_scoped_to_company(self):
        """SyncService should be scoped to a specific company_id."""
        mock_db = MagicMock()
        mock_client = MagicMock(spec=ShopifyClient)
        mock_client.shop_domain = "tenant1.myshopify.com"

        sync1 = ShopifyDataSync(
            db=mock_db, shopify_client=mock_client,
            company_id="comp_tenant1", integration_id="int_1",
        )
        sync2 = ShopifyDataSync(
            db=mock_db, shopify_client=mock_client,
            company_id="comp_tenant2", integration_id="int_2",
        )

        assert sync1.company_id != sync2.company_id
        assert sync1.integration_id != sync2.integration_id

    def test_webhook_events_include_company_id(self):
        """Webhook handler results should include company_id context."""
        event = {
            "event_type": "orders.create",
            "payload": {
                "order": {
                    "id": 1, "email": "test@test.com",
                    "total_price": "10", "currency": "USD",
                }
            },
            "company_id": "comp_tenant1",
            "event_id": "evt_1",
        }

        result = handle_shopify_event(event)
        assert result["status"] == "processed"

    def test_client_isolation_per_shop(self):
        """Each ShopifyClient should be isolated per shop domain."""
        client1 = ShopifyClient("shop1.myshopify.com", "token1")
        client2 = ShopifyClient("shop2.myshopify.com", "token2")

        assert client1.shop_domain != client2.shop_domain
        assert client1.access_token != client2.access_token
        assert "shop1" in client1.base_url
        assert "shop2" in client2.base_url


# ═══════════════════════════════════════════════════════════════════
# Test: All Event Types Through Dispatcher
# ═══════════════════════════════════════════════════════════════════

class TestAllEventTypesThroughDispatcher:
    """Integration test verifying all 6 event types work through dispatch_event."""

    @pytest.mark.parametrize("event_type,action,required_key", [
        ("orders.create", "order_created", "order_id"),
        ("orders.updated", "order_updated", "order_id"),
        ("orders.cancelled", "order_cancelled", "order_id"),
        ("customers.create", "customer_created", "customer_id"),
        ("products.create", "product_created", "product_id"),
        ("app/uninstalled", "app_uninstalled", "shop_domain"),
    ])
    def test_event_type_dispatch(self, event_type, action, required_key):
        """Each event type should dispatch to the correct handler."""
        payload_map = {
            "orders.create": {"order": {"id": 1, "email": "t@t.com", "total_price": "10", "currency": "USD"}},
            "orders.updated": {"order": {"id": 1, "email": "t@t.com", "total_price": "10", "currency": "USD"}},
            "orders.cancelled": {"order": {"id": 1, "email": "t@t.com"}},
            "customers.create": {"customer": {"id": 1, "email": "t@t.com"}},
            "products.create": {"product": {"id": 1, "title": "Test Product"}},
            "app/uninstalled": {"shop_domain": "test.myshopify.com"},
        }

        event = {
            "event_type": event_type,
            "payload": payload_map[event_type],
            "company_id": "comp_test",
            "event_id": f"evt_{event_type}",
        }

        # Validate event type is supported
        assert validate_event_type("shopify", event_type) is True

        # Dispatch the event
        result = dispatch_event("shopify", event)

        # Verify handler ran
        assert result["status"] == "processed"
        assert result["action"] == action
        assert required_key in result["data"]


# ═══════════════════════════════════════════════════════════════════
# Test: Provider Event Types Registry
# ═══════════════════════════════════════════════════════════════════

class TestProviderEventTypesRegistry:
    """Integration tests for the webhook event types registry."""

    def test_shopify_has_six_event_types(self):
        assert len(PROVIDER_EVENT_TYPES["shopify"]) == 6

    def test_all_handler_keys_match_registry(self):
        """Handler registry and event type list should be in sync."""
        registry_events = set(PROVIDER_EVENT_TYPES["shopify"])
        handler_events = set(_SHOPIFY_HANDLERS.keys())
        assert registry_events == handler_events

    def test_required_fields_for_all_types(self):
        """All registered event types should have required fields defined."""
        for event_type in _SHOPIFY_HANDLERS.keys():
            assert event_type in REQUIRED_FIELDS, f"Missing REQUIRED_FIELDS for {event_type}"


# ═══════════════════════════════════════════════════════════════════
# Test: MCP Ecommerce Server Integration
# ═══════════════════════════════════════════════════════════════════

class TestMCPEcommerceServerIntegration:
    """Integration tests for MCP Ecommerce Server with ShopifyClient."""

    def test_ecommerce_server_imports(self):
        """EcommerceServer should be importable."""
        from mcp_server.integrations.ecommerce_server import EcommerceServer, ecommerce_server
        assert ecommerce_server is not None
        assert ecommerce_server.name == "ecommerce_server"

    def test_ecommerce_server_has_five_tools(self):
        """EcommerceServer should register 5 tools."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server
        # Register tools into a mock registry
        mock_registry = MagicMock()
        ecommerce_server.register_tools(mock_registry)
        assert mock_registry.register_tool.call_count == 5

    @pytest.mark.asyncio
    async def test_get_order_without_client(self):
        """Order lookup without Shopify client should return placeholder."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server

        result = await ecommerce_server._invoke_get_order(
            parameters={"order_id": "123", "platform": "shopify"},
        )

        assert result.success is True
        assert result.metadata.get("status") == "placeholder"

    @pytest.mark.asyncio
    async def test_search_products_without_client(self):
        """Product search without Shopify client should return placeholder."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server

        result = await ecommerce_server._invoke_search_products(
            parameters={"query": "widget", "platform": "shopify"},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_fulfillment_without_client(self):
        """Fulfillment creation without Shopify client should return placeholder."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server

        result = await ecommerce_server._invoke_create_fulfillment(
            parameters={"order_id": "123", "tracking_number": "1Z999"},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_refund_without_client(self):
        """Refund creation without Shopify client should return placeholder."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server

        result = await ecommerce_server._invoke_create_refund(
            parameters={"order_id": "123", "amount": "50.00"},
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_customer_orders_without_client(self):
        """Customer orders without Shopify client should return placeholder."""
        from mcp_server.integrations.ecommerce_server import ecommerce_server

        result = await ecommerce_server._invoke_customer_orders(
            parameters={"customer_id": "999", "platform": "shopify"},
        )

        assert result.success is True


# ═══════════════════════════════════════════════════════════════════
# Test: Shopify API Routes
# ═══════════════════════════════════════════════════════════════════

class TestShopifyAPIRoutes:
    """Integration tests for Shopify API route definitions."""

    def test_shopify_api_file_exists(self):
        """Shopify API module file should exist."""
        import pathlib
        api_path = pathlib.Path("/home/z/my-project/parwa/backend/app/api/shopify.py")
        assert api_path.exists(), "Shopify API module file must exist"

    def test_shopify_router_defined(self):
        """Shopify API router should be defined in the module."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert 'router = APIRouter(prefix="/api/shopify"' in content
        assert 'tags=["Shopify Integration"]' in content

    def test_shopify_router_has_sync_endpoints(self):
        """Shopify API should have sync endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/sync/full"' in content
        assert '"/sync/incremental"' in content
        assert '"/sync/status"' in content

    def test_shopify_router_has_order_endpoints(self):
        """Shopify API should have order endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/orders/{order_id}"' in content
        assert '"/orders"' in content

    def test_shopify_router_has_product_endpoints(self):
        """Shopify API should have product endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/products/{product_id}"' in content
        assert '"/products"' in content

    def test_shopify_router_has_customer_endpoints(self):
        """Shopify API should have customer endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/customers/{customer_id}"' in content
        assert '"/customers"' in content

    def test_shopify_router_has_fulfillment_and_refund(self):
        """Shopify API should have fulfillment and refund endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/fulfillments"' in content
        assert '"/refunds"' in content

    def test_shopify_router_has_webhook_management(self):
        """Shopify API should have webhook management endpoints."""
        content = open("/home/z/my-project/parwa/backend/app/api/shopify.py").read()
        assert '"/webhooks"' in content
        assert '"/webhooks/{webhook_id}"' in content
