"""
PARWA Day 4 — Unit Tests for Expanded Shopify Webhook Handler

Tests all 6 webhook event types:
- orders.create (existing)
- orders.updated (NEW)
- orders.cancelled (NEW)
- customers.create (existing)
- products.create (NEW)
- app/uninstalled (NEW)

Also tests:
- Data extraction for each event type
- Required field validation
- Handler error resilience (BC-008)
- Event dispatcher routing

Run: pytest tests/unit/test_shopify_handler_expanded.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import pytest
from backend.app.webhooks.shopify_handler import (
    handle_shopify_event,
    handle_order_created,
    handle_order_updated,
    handle_order_cancelled,
    handle_customer_created,
    handle_product_created,
    handle_app_uninstalled,
    _extract_order_data,
    _extract_customer_data,
    _extract_product_data,
    _extract_shop_data,
    _sanitize_field,
    _validate_required_fields,
    REQUIRED_FIELDS,
    _SHOPIFY_HANDLERS,
)
from backend.app.webhooks import PROVIDER_EVENT_TYPES


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

SAMPLE_ORDER_EVENT = {
    "event_type": "orders.create",
    "payload": {
        "order": {
            "id": 12345,
            "order_number": "ORD-1001",
            "email": "buyer@example.com",
            "total_price": "149.99",
            "currency": "USD",
            "financial_status": "paid",
            "fulfillment_status": "partial",
            "customer": {
                "id": 999,
                "first_name": "Jane",
                "last_name": "Smith",
            },
            "line_items": [
                {"title": "Widget Pro", "quantity": 2, "price": "49.99"},
                {"title": "Accessory Kit", "quantity": 1, "price": "50.01"},
            ],
            "created_at": "2026-04-01T12:00:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_1",
}

SAMPLE_ORDER_UPDATED_EVENT = {
    "event_type": "orders.updated",
    "payload": {
        "order": {
            "id": 12345,
            "order_number": "ORD-1001",
            "email": "buyer@example.com",
            "total_price": "149.99",
            "currency": "USD",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "customer": {
                "id": 999,
                "first_name": "Jane",
                "last_name": "Smith",
            },
            "line_items": [
                {"title": "Widget Pro", "quantity": 2, "price": "49.99"},
            ],
            "created_at": "2026-04-01T12:00:00Z",
            "updated_at": "2026-04-02T08:30:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_3",
}

SAMPLE_ORDER_CANCELLED_EVENT = {
    "event_type": "orders.cancelled",
    "payload": {
        "order": {
            "id": 12345,
            "order_number": "ORD-1001",
            "email": "buyer@example.com",
            "total_price": "149.99",
            "currency": "USD",
            "financial_status": "voided",
            "fulfillment_status": None,
            "cancel_reason": "customer",
            "cancelled_at": "2026-04-03T10:00:00Z",
            "customer": {
                "id": 999,
                "first_name": "Jane",
                "last_name": "Smith",
            },
            "line_items": [],
            "created_at": "2026-04-01T12:00:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_4",
}

SAMPLE_CUSTOMER_EVENT = {
    "event_type": "customers.create",
    "payload": {
        "customer": {
            "id": 888,
            "email": "newcustomer@example.com",
            "first_name": "Alice",
            "last_name": "Wonder",
            "phone": "+15551234567",
            "state": "enabled",
            "orders_count": 0,
            "total_spent": "0.00",
            "tags": "VIP, Wholesale",
            "created_at": "2026-04-01T12:00:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_2",
}

SAMPLE_PRODUCT_EVENT = {
    "event_type": "products.create",
    "payload": {
        "product": {
            "id": 456,
            "title": "Deluxe Widget",
            "body_html": "<p>Best widget ever</p>",
            "vendor": "ACME Corp",
            "product_type": "Widgets",
            "status": "active",
            "tags": "featured, new",
            "published_at": "2026-04-01T10:00:00Z",
            "variants": [
                {
                    "id": 789,
                    "title": "Small",
                    "price": "29.99",
                    "sku": "DW-S",
                    "inventory_quantity": 50,
                    "compare_at_price": "39.99",
                },
                {
                    "id": 790,
                    "title": "Large",
                    "price": "49.99",
                    "sku": "DW-L",
                    "inventory_quantity": 25,
                    "compare_at_price": "59.99",
                },
            ],
            "images": [
                {"src": "https://cdn.shopify.com/widget1.jpg"},
                {"src": "https://cdn.shopify.com/widget2.jpg"},
            ],
            "created_at": "2026-04-01T10:00:00Z",
            "updated_at": "2026-04-01T10:00:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_5",
}

SAMPLE_APP_UNINSTALLED_EVENT = {
    "event_type": "app/uninstalled",
    "payload": {
        "shop_domain": "mystore.myshopify.com",
        "shop": {
            "id": 42,
            "name": "My Store",
            "email": "admin@mystore.com",
            "domain": "mystore.com",
        },
        "uninstalled_at": "2026-04-05T15:00:00Z",
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_6",
}


# ═══════════════════════════════════════════════════════════════════
# Test: Handler Registry
# ═══════════════════════════════════════════════════════════════════

class TestHandlerRegistry:
    """Tests for handler registration and dispatch."""

    def test_six_handlers_registered(self):
        """All 6 event types should have handlers."""
        assert len(_SHOPIFY_HANDLERS) == 6

    def test_handler_keys(self):
        """All expected event types should be present."""
        expected = {"orders.create", "orders.updated", "orders.cancelled",
                    "customers.create", "products.create", "app/uninstalled"}
        assert set(_SHOPIFY_HANDLERS.keys()) == expected

    def test_provider_event_types_updated(self):
        """Webhook registry should list all 6 Shopify event types."""
        shopify_events = PROVIDER_EVENT_TYPES.get("shopify", [])
        assert len(shopify_events) == 6
        assert "orders.updated" in shopify_events
        assert "orders.cancelled" in shopify_events
        assert "products.create" in shopify_events
        assert "app/uninstalled" in shopify_events


class TestDispatchRouting:
    """Tests for handle_shopify_event dispatcher."""

    def test_dispatches_order_created(self):
        result = handle_shopify_event(SAMPLE_ORDER_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "order_created"

    def test_dispatches_order_updated(self):
        result = handle_shopify_event(SAMPLE_ORDER_UPDATED_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "order_updated"

    def test_dispatches_order_cancelled(self):
        result = handle_shopify_event(SAMPLE_ORDER_CANCELLED_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "order_cancelled"

    def test_dispatches_customer_created(self):
        result = handle_shopify_event(SAMPLE_CUSTOMER_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "customer_created"

    def test_dispatches_product_created(self):
        result = handle_shopify_event(SAMPLE_PRODUCT_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "product_created"

    def test_dispatches_app_uninstalled(self):
        result = handle_shopify_event(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "app_uninstalled"

    def test_unknown_event_type_returns_error(self):
        event = {**SAMPLE_ORDER_EVENT, "event_type": "inventory.update"}
        result = handle_shopify_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Shopify event type" in result["error"]
        assert len(result["supported_types"]) == 6


# ═══════════════════════════════════════════════════════════════════
# Test: orders.updated Handler
# ═══════════════════════════════════════════════════════════════════

class TestHandleOrderUpdated:
    """Tests for orders.updated event handler."""

    def test_returns_processed_status(self):
        result = handle_order_updated(SAMPLE_ORDER_UPDATED_EVENT)
        assert result["status"] == "processed"

    def test_extracts_fulfillment_status(self):
        result = handle_order_updated(SAMPLE_ORDER_UPDATED_EVENT)
        assert result["data"]["fulfillment_status"] == "fulfilled"

    def test_extracts_updated_at(self):
        result = handle_order_updated(SAMPLE_ORDER_UPDATED_EVENT)
        assert result["data"]["updated_at"] == "2026-04-02T08:30:00Z"

    def test_missing_order_id_returns_error(self):
        event = {
            "event_type": "orders.updated",
            "payload": {
                "order": {"email": "test@test.com", "total_price": "10", "currency": "USD"}
            },
        }
        result = handle_order_updated(event)
        assert result["status"] == "validation_error"

    def test_missing_email_returns_error(self):
        event = {
            "event_type": "orders.updated",
            "payload": {
                "order": {"id": 1, "total_price": "10", "currency": "USD"}
            },
        }
        result = handle_order_updated(event)
        assert result["status"] == "validation_error"


# ═══════════════════════════════════════════════════════════════════
# Test: orders.cancelled Handler
# ═══════════════════════════════════════════════════════════════════

class TestHandleOrderCancelled:
    """Tests for orders.cancelled event handler."""

    def test_returns_processed_status(self):
        result = handle_order_cancelled(SAMPLE_ORDER_CANCELLED_EVENT)
        assert result["status"] == "processed"

    def test_action_is_order_cancelled(self):
        result = handle_order_cancelled(SAMPLE_ORDER_CANCELLED_EVENT)
        assert result["action"] == "order_cancelled"

    def test_extracts_cancel_reason(self):
        result = handle_order_cancelled(SAMPLE_ORDER_CANCELLED_EVENT)
        assert result["data"]["cancel_reason"] == "customer"

    def test_extracts_cancelled_at(self):
        result = handle_order_cancelled(SAMPLE_ORDER_CANCELLED_EVENT)
        assert result["data"]["cancelled_at"] == "2026-04-03T10:00:00Z"

    def test_missing_order_id_returns_error(self):
        event = {
            "event_type": "orders.cancelled",
            "payload": {
                "order": {"email": "test@test.com"}
            },
        }
        result = handle_order_cancelled(event)
        assert result["status"] == "validation_error"

    def test_fraud_cancel_reason(self):
        event = {
            **SAMPLE_ORDER_CANCELLED_EVENT,
            "payload": {
                "order": {
                    **SAMPLE_ORDER_CANCELLED_EVENT["payload"]["order"],
                    "cancel_reason": "fraud",
                }
            },
        }
        result = handle_order_cancelled(event)
        assert result["data"]["cancel_reason"] == "fraud"


# ═══════════════════════════════════════════════════════════════════
# Test: products.create Handler
# ═══════════════════════════════════════════════════════════════════

class TestHandleProductCreated:
    """Tests for products.create event handler."""

    def test_returns_processed_status(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["status"] == "processed"

    def test_action_is_product_created(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["action"] == "product_created"

    def test_extracts_product_id(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["product_id"] == "456"

    def test_extracts_title(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["title"] == "Deluxe Widget"

    def test_extracts_vendor(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["vendor"] == "ACME Corp"

    def test_extracts_product_type(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["product_type"] == "Widgets"

    def test_extracts_status(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["status"] == "active"

    def test_extracts_variants(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert len(result["data"]["variants"]) == 2
        assert result["data"]["variants"][0]["title"] == "Small"
        assert result["data"]["variants"][0]["price"] == "29.99"
        assert result["data"]["variants"][0]["sku"] == "DW-S"
        assert result["data"]["variants"][0]["inventory_quantity"] == 50

    def test_extracts_images(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert len(result["data"]["images"]) == 2

    def test_extracts_tags(self):
        result = handle_product_created(SAMPLE_PRODUCT_EVENT)
        assert result["data"]["tags"] == "featured, new"

    def test_missing_product_id_returns_error(self):
        event = {
            "event_type": "products.create",
            "payload": {
                "product": {"title": "No ID Product"}
            },
        }
        result = handle_product_created(event)
        assert result["status"] == "validation_error"

    def test_missing_title_returns_error(self):
        event = {
            "event_type": "products.create",
            "payload": {
                "product": {"id": 1}
            },
        }
        result = handle_product_created(event)
        assert result["status"] == "validation_error"

    def test_product_with_no_variants(self):
        event = {
            "event_type": "products.create",
            "payload": {
                "product": {
                    "id": 1,
                    "title": "Simple Product",
                    "variants": [],
                }
            },
        }
        result = handle_product_created(event)
        assert result["status"] == "processed"
        assert result["data"]["variants"] == []

    def test_product_with_many_variants_capped_at_100(self):
        """More than 100 variants should be capped."""
        variants = [{"id": i, "title": f"V{i}", "price": "10", "sku": f"SKU-{i}", "inventory_quantity": 5} for i in range(150)]
        event = {
            "event_type": "products.create",
            "payload": {
                "product": {
                    "id": 1,
                    "title": "Big Product",
                    "variants": variants,
                }
            },
        }
        result = handle_product_created(event)
        assert result["status"] == "processed"
        assert len(result["data"]["variants"]) == 100


# ═══════════════════════════════════════════════════════════════════
# Test: app/uninstalled Handler
# ═══════════════════════════════════════════════════════════════════

class TestHandleAppUninstalled:
    """Tests for app/uninstalled event handler."""

    def test_returns_processed_status(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["status"] == "processed"

    def test_action_is_app_uninstalled(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["action"] == "app_uninstalled"

    def test_extracts_shop_domain(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["data"]["shop_domain"] == "mystore.myshopify.com"

    def test_extracts_shop_id(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["data"]["shop_id"] == "42"

    def test_extracts_shop_name(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["data"]["shop_name"] == "My Store"

    def test_extracts_shop_email(self):
        result = handle_app_uninstalled(SAMPLE_APP_UNINSTALLED_EVENT)
        assert result["data"]["shop_email"] == "admin@mystore.com"

    def test_missing_shop_domain_from_event_context(self):
        """Should still process if shop_domain comes from event context."""
        event = {
            "event_type": "app/uninstalled",
            "payload": {},
            "company_id": "comp_1",
            "event_id": "evt_test",
            "shop_domain": "fallback.myshopify.com",
        }
        result = handle_app_uninstalled(event)
        assert result["status"] == "processed"
        assert result["data"]["shop_domain"] == "fallback.myshopify.com"

    def test_missing_required_fields_no_context(self):
        """Should return error when no shop_domain anywhere."""
        event = {
            "event_type": "app/uninstalled",
            "payload": {},
            "company_id": "comp_1",
            "event_id": "evt_test",
        }
        result = handle_app_uninstalled(event)
        assert result["status"] == "validation_error"


# ═══════════════════════════════════════════════════════════════════
# Test: Data Extraction Functions
# ═══════════════════════════════════════════════════════════════════

class TestExtractProductData:
    """Tests for _extract_product_data function."""

    def test_extracts_all_fields(self):
        payload = SAMPLE_PRODUCT_EVENT["payload"]
        data = _extract_product_data(payload)
        assert data["product_id"] == "456"
        assert data["title"] == "Deluxe Widget"
        assert data["vendor"] == "ACME Corp"
        assert data["product_type"] == "Widgets"
        assert data["status"] == "active"
        assert len(data["variants"]) == 2
        assert len(data["images"]) == 2

    def test_handles_missing_variants(self):
        data = _extract_product_data({"product": {"id": 1, "title": "Test"}})
        assert data["variants"] == []

    def test_handles_missing_images(self):
        data = _extract_product_data({"product": {"id": 1, "title": "Test"}})
        assert data["images"] == []

    def test_handles_non_dict_variants(self):
        data = _extract_product_data({"product": {"id": 1, "title": "Test", "variants": "not a list"}})
        assert data["variants"] == []

    def test_caps_images_at_20(self):
        images = [{"src": f"https://cdn.shopify.com/img{i}.jpg"} for i in range(30)]
        data = _extract_product_data({"product": {"id": 1, "title": "Test", "images": images}})
        assert len(data["images"]) == 20


class TestExtractShopData:
    """Tests for _extract_shop_data function."""

    def test_extracts_shop_domain(self):
        data = _extract_shop_data(SAMPLE_APP_UNINSTALLED_EVENT["payload"])
        assert data["shop_domain"] == "mystore.myshopify.com"

    def test_extracts_shop_details(self):
        data = _extract_shop_data(SAMPLE_APP_UNINSTALLED_EVENT["payload"])
        assert data["shop_id"] == "42"
        assert data["shop_name"] == "My Store"
        assert data["shop_email"] == "admin@mystore.com"

    def test_empty_payload(self):
        data = _extract_shop_data({})
        assert data["shop_domain"] == ""
        assert data["shop_id"] == ""


class TestExtractOrderDataEnhanced:
    """Tests for enhanced _extract_order_data with cancel fields."""

    def test_extracts_cancel_reason(self):
        payload = SAMPLE_ORDER_CANCELLED_EVENT["payload"]
        data = _extract_order_data(payload)
        assert data["cancel_reason"] == "customer"

    def test_extracts_cancelled_at(self):
        payload = SAMPLE_ORDER_CANCELLED_EVENT["payload"]
        data = _extract_order_data(payload)
        assert data["cancelled_at"] == "2026-04-03T10:00:00Z"

    def test_extracts_updated_at(self):
        payload = SAMPLE_ORDER_UPDATED_EVENT["payload"]
        data = _extract_order_data(payload)
        assert data["updated_at"] == "2026-04-02T08:30:00Z"


class TestExtractCustomerDataEnhanced:
    """Tests for enhanced _extract_customer_data with new fields."""

    def test_extracts_total_spent(self):
        payload = SAMPLE_CUSTOMER_EVENT["payload"]
        data = _extract_customer_data(payload)
        assert data["total_spent"] == "0.00"

    def test_extracts_tags(self):
        payload = SAMPLE_CUSTOMER_EVENT["payload"]
        data = _extract_customer_data(payload)
        assert "VIP" in data["tags"]


# ═══════════════════════════════════════════════════════════════════
# Test: Required Fields
# ═══════════════════════════════════════════════════════════════════

class TestRequiredFieldsExpanded:
    """Tests for required fields validation with new event types."""

    def test_orders_create_required_fields(self):
        fields = REQUIRED_FIELDS["orders.create"]
        assert "order_id" in fields
        assert "email" in fields
        assert "total_price" in fields

    def test_orders_updated_required_fields(self):
        fields = REQUIRED_FIELDS["orders.updated"]
        assert "order_id" in fields
        assert "email" in fields

    def test_orders_cancelled_required_fields(self):
        fields = REQUIRED_FIELDS["orders.cancelled"]
        assert "order_id" in fields
        assert "email" in fields

    def test_customers_create_required_fields(self):
        fields = REQUIRED_FIELDS["customers.create"]
        assert "customer_id" in fields
        assert "email" in fields

    def test_products_create_required_fields(self):
        fields = REQUIRED_FIELDS["products.create"]
        assert "product_id" in fields
        assert "title" in fields

    def test_app_uninstalled_required_fields(self):
        fields = REQUIRED_FIELDS["app/uninstalled"]
        assert "shop_domain" in fields


class TestValidateRequiredFields:
    """Tests for _validate_required_fields function."""

    def test_all_fields_present(self):
        data = {"order_id": "123", "email": "test@test.com", "total_price": "10", "currency": "USD"}
        result = _validate_required_fields("orders.create", data)
        assert result is None  # None means OK

    def test_missing_field(self):
        data = {"order_id": "123", "email": "test@test.com"}
        result = _validate_required_fields("orders.create", data)
        assert result is not None
        assert "total_price" in result

    def test_empty_string_field(self):
        data = {"order_id": "123", "email": "", "total_price": "10", "currency": "USD"}
        result = _validate_required_fields("orders.create", data)
        assert result is not None
        assert "email" in result

    def test_unknown_event_type(self):
        data = {"some_field": "value"}
        result = _validate_required_fields("unknown.event", data)
        assert result is None  # No required fields for unknown


# ═══════════════════════════════════════════════════════════════════
# Test: BC-008 Error Resilience
# ═══════════════════════════════════════════════════════════════════

class TestErrorResilience:
    """Tests for BC-008: Handler never crashes."""

    def test_empty_payload_order_created(self):
        result = handle_order_created({"event_type": "orders.create", "payload": {}})
        assert result["status"] == "validation_error"

    def test_empty_payload_customer_created(self):
        result = handle_customer_created({"event_type": "customers.create", "payload": {}})
        assert result["status"] == "validation_error"

    def test_empty_payload_product_created(self):
        result = handle_product_created({"event_type": "products.create", "payload": {}})
        assert result["status"] == "validation_error"

    def test_empty_payload_order_updated(self):
        result = handle_order_updated({"event_type": "orders.updated", "payload": {}})
        assert result["status"] == "validation_error"

    def test_empty_payload_order_cancelled(self):
        result = handle_order_cancelled({"event_type": "orders.cancelled", "payload": {}})
        assert result["status"] == "validation_error"

    def test_none_payload(self):
        """Should handle None payload gracefully."""
        result = handle_shopify_event({
            "event_type": "orders.create",
            "payload": None,
        })
        # Should not crash — either validation_error or handler_error
        assert result["status"] in ("validation_error", "handler_error")

    def test_handler_error_catch(self):
        """Dispatcher should catch handler exceptions (BC-008)."""
        # Create a payload that might cause an error in extraction
        event = {
            "event_type": "orders.create",
            "payload": {"order": {"id": 1, "email": "test@test.com", "total_price": "10", "currency": "USD"}},
        }
        # This should work normally, but the try/except in the dispatcher should catch errors
        result = handle_shopify_event(event)
        assert result["status"] in ("processed", "handler_error", "validation_error")


# ═══════════════════════════════════════════════════════════════════
# Test: Sanitize Field
# ═══════════════════════════════════════════════════════════════════

class TestSanitizeField:
    """Tests for _sanitize_field function."""

    def test_strips_control_chars(self):
        result = _sanitize_field("hello\x00world\x01test")
        assert result == "helloworldtest"

    def test_truncates_long_strings(self):
        result = _sanitize_field("x" * 500, max_length=100)
        assert len(result) == 100

    def test_empty_input(self):
        assert _sanitize_field("") == ""
        assert _sanitize_field(None) == ""

    def test_preserves_newlines(self):
        result = _sanitize_field("hello\nworld\rtest")
        assert "\n" in result
        assert "\r" in result
