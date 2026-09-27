"""Tests for Shopify webhook handler."""

import backend.app.webhooks.shopify_handler  # noqa: F401
from backend.app.webhooks.shopify_handler import (
    handle_shopify_event,
    handle_order_created,
    handle_customer_created,
    _extract_order_data,
    _extract_customer_data,
    REQUIRED_FIELDS,
)

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
            "created_at": "2026-04-01T12:00:00Z",
        }
    },
    "company_id": "comp_1",
    "event_id": "evt_shop_2",
}


class TestHandleShopifyEvent:
    def test_dispatches_order_created(self):
        result = handle_shopify_event(SAMPLE_ORDER_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "order_created"

    def test_dispatches_customer_created(self):
        result = handle_shopify_event(SAMPLE_CUSTOMER_EVENT)
        assert result["action"] == "customer_created"

    def test_unknown_event_type_returns_error(self):
        event = {**SAMPLE_ORDER_EVENT, "event_type": "products.update"}
        result = handle_shopify_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Shopify event type" in result["error"]

    def test_unknown_event_includes_supported_types(self):
        event = {**SAMPLE_ORDER_EVENT, "event_type": "unknown"}
        result = handle_shopify_event(event)
        assert "supported_types" in result
        assert len(result["supported_types"]) == 2


class TestHandleOrderCreated:
    def test_returns_processed_status(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["status"] == "processed"

    def test_extracts_order_id(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["order_id"] == "12345"

    def test_extracts_order_number(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["order_number"] == "ORD-1001"

    def test_extracts_email(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["email"] == "buyer@example.com"

    def test_extracts_total_price(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["total_price"] == "149.99"

    def test_extracts_currency(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["currency"] == "USD"

    def test_extracts_financial_status(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["financial_status"] == "paid"

    def test_extracts_fulfillment_status(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["fulfillment_status"] == "partial"

    def test_extracts_line_items(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert len(result["data"]["line_items"]) == 2
        assert result["data"]["line_items"][0]["title"] == "Widget Pro"

    def test_extracts_customer_name(self):
        result = handle_order_created(SAMPLE_ORDER_EVENT)
        assert result["data"]["customer_name"] == "Jane Smith"

    def test_missing_order_id_returns_error(self):
        event = {
            **SAMPLE_ORDER_EVENT,
            "payload": {"order": {"email": "test@test.com", "total_price": "10", "currency": "USD"}},
        }
        result = handle_order_created(event)
        assert result["status"] == "validation_error"

    def test_missing_email_returns_error(self):
        event = {
            **SAMPLE_ORDER_EVENT,
            "payload": {"order": {"id": 1, "total_price": "10", "currency": "USD"}},
        }
        result = handle_order_created(event)
        assert result["status"] == "validation_error"


class TestHandleCustomerCreated:
    def test_returns_processed_status(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["status"] == "processed"

    def test_extracts_customer_id(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["customer_id"] == "888"

    def test_extracts_email(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["email"] == "newcustomer@example.com"

    def test_extracts_first_name(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["first_name"] == "Alice"

    def test_extracts_last_name(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["last_name"] == "Wonder"

    def test_extracts_phone(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["phone"] == "+15551234567"

    def test_extracts_orders_count(self):
        result = handle_customer_created(SAMPLE_CUSTOMER_EVENT)
        assert result["data"]["orders_count"] == 0

    def test_missing_customer_id_returns_error(self):
        event = {
            **SAMPLE_CUSTOMER_EVENT,
            "payload": {"customer": {"email": "test@test.com"}},
        }
        result = handle_customer_created(event)
        assert result["status"] == "validation_error"

    def test_missing_email_returns_error(self):
        event = {
            **SAMPLE_CUSTOMER_EVENT,
            "payload": {"customer": {"id": 1}},
        }
        result = handle_customer_created(event)
        assert result["status"] == "validation_error"


class TestExtractOrderData:
    def test_limits_line_items_to_100(self):
        items = [{"title": f"Item {i}", "quantity": 1, "price": "10"} for i in range(150)]
        event = {
            "order": {
                "id": 1, "email": "test@test.com",
                "total_price": "100", "currency": "USD",
                "line_items": items,
            }
        }
        data = _extract_order_data(event)
        assert len(data["line_items"]) == 100

    def test_default_currency_is_usd(self):
        event = {"order": {"id": 1, "email": "t@t.com", "total_price": "10"}}
        data = _extract_order_data(event)
        assert data["currency"] == "USD"


class TestRequiredFields:
    def test_orders_create_required_fields(self):
        fields = REQUIRED_FIELDS["orders.create"]
        assert "order_id" in fields
        assert "email" in fields
        assert "total_price" in fields

    def test_customers_create_required_fields(self):
        fields = REQUIRED_FIELDS["customers.create"]
        assert "customer_id" in fields
        assert "email" in fields
