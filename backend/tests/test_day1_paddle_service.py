"""
Comprehensive unit tests for Paddle Service (Phase 10 — Week 6 Day 7)

Tests cover:
1. Demo pack checkout creation
2. Demo pack webhook processing
3. Variant subscription checkout creation
4. Subscription webhook processing
5. Payment status queries
6. Idempotency helpers
7. Price ID loading & merging
8. Error classes
9. Factory / singleton behavior

All external Paddle API calls are mocked — no real API keys are used.
"""

import os
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# ── Set Paddle-related env vars BEFORE any app imports ────────────────
os.environ.setdefault("PADDLE_API_KEY", "test_api_key_000000")
os.environ.setdefault("PADDLE_CLIENT_TOKEN", "test_client_token_000")
os.environ.setdefault("PADDLE_WEBHOOK_SECRET", "test_wh_secret_00000000")
os.environ.setdefault("PADDLE_PRICE_IDS", "")

from app.services.paddle_service import (
    PaddleService,
    PaddleServiceError,
    DemoPackAlreadyActiveError,
    CheckoutCreationError,
    PaymentNotFoundError,
    WebhookProcessingError,
    get_paddle_service,
    _load_price_ids,
    _DEFAULT_PRICE_IDS,
    DEMO_PACK_PRICE_ID,
    PLAN_PRICE_IDS,
    VARIANT_PRICE_IDS,
    DEMO_PACK_AMOUNT,
    DEMO_PACK_CURRENCY,
    DEMO_PACK_MESSAGES,
    DEMO_PACK_CALL_MINUTES,
    DEMO_PACK_DURATION_HOURS,
)
from app.clients.paddle_client import PaddleClient, PaddleError


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_client():
    """Create a PaddleClient with _request mocked as AsyncMock."""
    client = PaddleClient(
        api_key="test_key",
        client_token="test_token",
        sandbox=True,
        webhook_secret="test_secret",
    )
    client._request = AsyncMock()
    return client


@pytest.fixture
def service(mock_client):
    """PaddleService with mocked client (no lazy init)."""
    return PaddleService(client=mock_client)


# ══════════════════════════════════════════════════════════════════════════
# 1. TestCreateDemoPackCheckout
# ══════════════════════════════════════════════════════════════════════════

class TestCreateDemoPackCheckout:
    """Tests for PaddleService.create_demo_pack_checkout."""

    @pytest.mark.asyncio
    async def test_creates_checkout_with_correct_items(self, service, mock_client):
        """Checkout request includes the DEMO_PACK_PRICE_ID with quantity 1."""
        mock_client._request.return_value = {
            "id": "txn_abc123",
            "checkout": {"url": "https://checkout.paddle.com/abc"},
        }

        await service.create_demo_pack_checkout(session_id="sess_001")

        mock_client._request.assert_awaited_once()
        call_kwargs = mock_client._request.call_args
        json_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

        assert json_body["items"] == [{"price_id": DEMO_PACK_PRICE_ID, "quantity": 1}]

    @pytest.mark.asyncio
    async def test_custom_data_includes_session_id(self, service, mock_client):
        """custom_data links checkout to session, pack_type, and source."""
        mock_client._request.return_value = {
            "id": "txn_abc123",
            "checkout": {"url": "https://checkout.paddle.com/abc"},
        }

        await service.create_demo_pack_checkout(session_id="sess_042")

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["custom_data"]["session_id"] == "sess_042"
        assert json_body["custom_data"]["pack_type"] == "demo"
        assert json_body["custom_data"]["source"] == "jarvis_onboarding"

    @pytest.mark.asyncio
    async def test_returns_checkout_url_and_transaction_id(self, service, mock_client):
        """Returns dict with checkout_url, transaction_id, and metadata."""
        mock_client._request.return_value = {
            "id": "txn_xyz789",
            "checkout": {"url": "https://checkout.paddle.com/pay/xyz789"},
        }

        result = await service.create_demo_pack_checkout(session_id="sess_100")

        assert result["checkout_url"] == "https://checkout.paddle.com/pay/xyz789"
        assert result["transaction_id"] == "txn_xyz789"
        assert result["status"] == "pending"
        assert result["amount"] == DEMO_PACK_AMOUNT
        assert result["currency"] == DEMO_PACK_CURRENCY
        assert result["pack_type"] == "demo"

    @pytest.mark.asyncio
    async def test_raises_checkout_creation_error_when_no_url(self, service, mock_client):
        """Raises CheckoutCreationError when Paddle returns no checkout URL."""
        mock_client._request.return_value = {"id": "txn_no_url", "checkout": {}}

        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_demo_pack_checkout(session_id="sess_200")

        assert "no checkout url" in str(exc_info.value.message).lower()
        assert exc_info.value.details is not None

    @pytest.mark.asyncio
    async def test_raises_checkout_creation_error_on_paddle_error(self, service, mock_client):
        """Raises CheckoutCreationError wrapping PaddleError."""
        mock_client._request.side_effect = PaddleError("API timeout")

        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_demo_pack_checkout(session_id="sess_300")

        assert "Paddle API error" in str(exc_info.value.message)
        assert exc_info.value.details is not None
        assert "paddle_error" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_handles_customer_email_prefill(self, service, mock_client):
        """When customer_email is provided, it's passed in checkout customer data."""
        mock_client._request.return_value = {
            "id": "txn_email",
            "checkout": {"url": "https://checkout.paddle.com/email"},
        }

        await service.create_demo_pack_checkout(
            session_id="sess_email",
            customer_email="alice@example.com",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["customer"]["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_handles_customer_name_prefill(self, service, mock_client):
        """When customer_name is provided, it's passed in checkout customer data."""
        mock_client._request.return_value = {
            "id": "txn_name",
            "checkout": {"url": "https://checkout.paddle.com/name"},
        }

        await service.create_demo_pack_checkout(
            session_id="sess_name",
            customer_name="Alice Smith",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["customer"]["name"] == "Alice Smith"

    @pytest.mark.asyncio
    async def test_no_customer_data_when_not_provided(self, service, mock_client):
        """When no customer info provided, no 'customer' key in request."""
        mock_client._request.return_value = {
            "id": "txn_nocust",
            "checkout": {"url": "https://checkout.paddle.com/nocust"},
        }

        await service.create_demo_pack_checkout(session_id="sess_nocust")

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert "customer" not in json_body

    @pytest.mark.asyncio
    async def test_uses_correct_demo_pack_price_id(self, service, mock_client):
        """The items list uses the module-level DEMO_PACK_PRICE_ID."""
        mock_client._request.return_value = {
            "id": "txn_price",
            "checkout": {"url": "https://checkout.paddle.com/price"},
        }

        await service.create_demo_pack_checkout(session_id="sess_price")

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["items"][0]["price_id"] == DEMO_PACK_PRICE_ID

    @pytest.mark.asyncio
    async def test_raises_on_unexpected_exception(self, service, mock_client):
        """Non-PaddleError exceptions are wrapped in CheckoutCreationError."""
        mock_client._request.side_effect = RuntimeError("something broke")

        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_demo_pack_checkout(session_id="sess_err")

        assert "Unexpected error" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_posts_to_transactions_endpoint(self, service, mock_client):
        """Request uses POST /transactions."""
        mock_client._request.return_value = {
            "id": "txn_method",
            "checkout": {"url": "https://checkout.paddle.com/method"},
        }

        await service.create_demo_pack_checkout(session_id="sess_meth")

        call_args = mock_client._request.call_args
        assert call_args.args[0] == "POST" or call_args.kwargs.get("method") == "POST" \
            or call_args[0][0] == "POST"
        # Check positional arg or keyword
        endpoint = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("endpoint")
        assert endpoint == "/transactions"


# ══════════════════════════════════════════════════════════════════════════
# 2. TestHandleDemoPackWebhook
# ══════════════════════════════════════════════════════════════════════════

class TestHandleDemoPackWebhook:
    """Tests for PaddleService.handle_demo_pack_webhook."""

    @pytest.mark.asyncio
    async def test_processes_transaction_completed_event(self, service):
        """Processes a transaction.completed event and returns success result."""
        event_data = {
            "transaction_id": "txn_completed_001",
            "custom_data": {
                "session_id": "sess_demo",
                "pack_type": "demo",
            },
            "amount": "1.00",
            "currency": "USD",
        }

        result = await service.handle_demo_pack_webhook(event_data)

        assert result["status"] == "processed"
        assert result["action"] == "demo_pack_activated"

    @pytest.mark.asyncio
    async def test_extracts_session_id_from_custom_data(self, service):
        """session_id is extracted from event_data.custom_data."""
        event_data = {
            "transaction_id": "txn_sid",
            "custom_data": {"session_id": "sess_unique_42"},
        }

        result = await service.handle_demo_pack_webhook(event_data)

        assert result["session_id"] == "sess_unique_42"

    @pytest.mark.asyncio
    async def test_raises_webhook_processing_error_when_no_session_id(self, service):
        """Raises WebhookProcessingError when custom_data has no session_id."""
        event_data = {
            "transaction_id": "txn_nosid",
            "custom_data": {},
        }

        with pytest.raises(WebhookProcessingError) as exc_info:
            await service.handle_demo_pack_webhook(event_data)

        assert "No session_id" in str(exc_info.value.message)
        assert exc_info.value.details["transaction_id"] == "txn_nosid"

    @pytest.mark.asyncio
    async def test_raises_when_custom_data_missing_entirely(self, service):
        """Raises WebhookProcessingError when custom_data key is absent."""
        event_data = {"transaction_id": "txn_nocustom"}

        with pytest.raises(WebhookProcessingError):
            await service.handle_demo_pack_webhook(event_data)

    @pytest.mark.asyncio
    async def test_calculates_24h_expiry(self, service):
        """Pack expiry is approximately 24 hours from now."""
        before = datetime.now(timezone.utc) + timedelta(hours=DEMO_PACK_DURATION_HOURS)

        event_data = {
            "transaction_id": "txn_expiry",
            "custom_data": {"session_id": "sess_exp"},
        }
        result = await service.handle_demo_pack_webhook(event_data)

        after = datetime.now(timezone.utc) + timedelta(hours=DEMO_PACK_DURATION_HOURS)

        expiry_str = result["pack_expiry"]
        expiry_dt = datetime.fromisoformat(expiry_str)

        # Expiry should be between "before" and "after" (tiny window for test execution)
        assert before <= expiry_dt <= after or abs((expiry_dt - before).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_returns_correct_result_dict_with_all_fields(self, service):
        """All expected fields are present in the result dict."""
        event_data = {
            "transaction_id": "txn_fields",
            "custom_data": {"session_id": "sess_fields"},
            "amount": "1.00",
            "currency": "USD",
        }

        result = await service.handle_demo_pack_webhook(event_data)

        expected_keys = {
            "status", "action", "session_id", "transaction_id",
            "amount", "currency", "pack_type", "pack_expiry",
            "messages_allowed", "message_count_today", "remaining_today",
            "demo_call_remaining", "demo_call_minutes", "activated_at",
        }
        assert expected_keys.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_sets_messages_allowed_500(self, service):
        """messages_allowed is set to 500 (DEMO_PACK_MESSAGES)."""
        event_data = {
            "transaction_id": "txn_msgs",
            "custom_data": {"session_id": "sess_msgs"},
        }

        result = await service.handle_demo_pack_webhook(event_data)

        assert result["messages_allowed"] == 500
        assert result["remaining_today"] == 500
        assert result["message_count_today"] == 0

    @pytest.mark.asyncio
    async def test_sets_demo_call_remaining_true(self, service):
        """demo_call_remaining is True after activation."""
        event_data = {
            "transaction_id": "txn_call",
            "custom_data": {"session_id": "sess_call"},
        }

        result = await service.handle_demo_pack_webhook(event_data)

        assert result["demo_call_remaining"] is True
        assert result["demo_call_minutes"] == DEMO_PACK_CALL_MINUTES


# ══════════════════════════════════════════════════════════════════════════
# 3. TestCreateVariantCheckout
# ══════════════════════════════════════════════════════════════════════════

class TestCreateVariantCheckout:
    """Tests for PaddleService.create_variant_checkout."""

    @pytest.mark.asyncio
    async def test_builds_checkout_items_from_variant_list(self, service, mock_client):
        """Each variant is converted to a checkout item with price_id and quantity."""
        mock_client._request.return_value = {
            "id": "txn_var1",
            "checkout": {"url": "https://checkout.paddle.com/var1"},
        }

        variants = [
            {"id": "returns_refunds", "name": "Returns & Refunds", "quantity": 2, "price": 29},
            {"id": "product_faq", "name": "Product FAQ", "quantity": 1, "price": 19},
        ]

        result = await service.create_variant_checkout(
            session_id="sess_var1",
            variants=variants,
            industry="e-commerce",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert len(json_body["items"]) == 2
        # returns_refunds should map to VARIANT_PRICE_IDS
        assert json_body["items"][0]["price_id"] == VARIANT_PRICE_IDS.get("returns_refunds")
        assert json_body["items"][0]["quantity"] == 2
        assert json_body["items"][1]["price_id"] == VARIANT_PRICE_IDS.get("product_faq")
        assert json_body["items"][1]["quantity"] == 1

    @pytest.mark.asyncio
    async def test_looks_up_price_ids_from_variant_price_ids(self, service, mock_client):
        """Known variant IDs are resolved from VARIANT_PRICE_IDS."""
        mock_client._request.return_value = {
            "id": "txn_lookup",
            "checkout": {"url": "https://checkout.paddle.com/lookup"},
        }

        variants = [{"id": "technical_support", "quantity": 1, "price": 39}]

        await service.create_variant_checkout(
            session_id="sess_lookup",
            variants=variants,
            industry="saas",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["items"][0]["price_id"] == VARIANT_PRICE_IDS["technical_support"]

    @pytest.mark.asyncio
    async def test_uses_fallback_price_id_for_unknown_variants(self, service, mock_client):
        """Unknown variant IDs get a fallback price_id of pri_{variant_id}_01."""
        mock_client._request.return_value = {
            "id": "txn_unknown",
            "checkout": {"url": "https://checkout.paddle.com/unknown"},
        }

        variants = [{"id": "custom_magic_variant", "quantity": 1, "price": 99}]

        await service.create_variant_checkout(
            session_id="sess_unknown",
            variants=variants,
            industry="custom",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["items"][0]["price_id"] == "pri_custom_magic_variant_01"

    @pytest.mark.asyncio
    async def test_calculates_total_monthly_correctly(self, service, mock_client):
        """total_monthly = sum(price * quantity) for all variants."""
        mock_client._request.return_value = {
            "id": "txn_total",
            "checkout": {"url": "https://checkout.paddle.com/total"},
        }

        variants = [
            {"id": "returns_refunds", "quantity": 2, "price": 29},
            {"id": "product_faq", "quantity": 3, "price": 19},
        ]

        result = await service.create_variant_checkout(
            session_id="sess_total",
            variants=variants,
            industry="e-commerce",
        )

        # 2*29 + 3*19 = 58 + 57 = 115
        assert result["total_monthly"] == "115"
        assert result["amount"] == "115"

    @pytest.mark.asyncio
    async def test_raises_checkout_creation_error_when_no_variants(self, service, mock_client):
        """Raises CheckoutCreationError when empty variant list is provided."""
        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_variant_checkout(
                session_id="sess_empty",
                variants=[],
                industry="e-commerce",
            )

        assert "No variants selected" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_raises_checkout_creation_error_when_no_url(self, service, mock_client):
        """Raises CheckoutCreationError when Paddle returns no checkout URL."""
        mock_client._request.return_value = {
            "id": "txn_nourl",
            "checkout": {},
        }

        variants = [{"id": "returns_refunds", "quantity": 1, "price": 29}]

        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_variant_checkout(
                session_id="sess_nourl",
                variants=variants,
                industry="e-commerce",
            )

        assert "no checkout url" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_raises_on_paddle_error(self, service, mock_client):
        """PaddleError is wrapped in CheckoutCreationError."""
        mock_client._request.side_effect = PaddleError("rate limited")

        variants = [{"id": "returns_refunds", "quantity": 1, "price": 29}]

        with pytest.raises(CheckoutCreationError) as exc_info:
            await service.create_variant_checkout(
                session_id="sess_paddle_err",
                variants=variants,
                industry="e-commerce",
            )

        assert "Paddle API error" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_custom_data_includes_variant_ids_and_industry(self, service, mock_client):
        """custom_data records variant_ids, quantities, industry, and session_id."""
        mock_client._request.return_value = {
            "id": "txn_custom",
            "checkout": {"url": "https://checkout.paddle.com/custom"},
        }

        variants = [
            {"id": "shipping_inquiries", "quantity": 2, "price": 25},
        ]

        await service.create_variant_checkout(
            session_id="sess_custom",
            variants=variants,
            industry="e-commerce",
            customer_email="bob@example.com",
        )

        json_body = mock_client._request.call_args.kwargs.get("json") or \
                    mock_client._request.call_args[1].get("json")

        assert json_body["custom_data"]["session_id"] == "sess_custom"
        assert json_body["custom_data"]["pack_type"] == "subscription"
        assert json_body["custom_data"]["industry"] == "e-commerce"
        assert "shipping_inquiries" in json_body["custom_data"]["variant_ids"]
        assert json_body["custom_data"]["variant_quantities"]["shipping_inquiries"] == 2
        assert json_body["customer"]["email"] == "bob@example.com"

    @pytest.mark.asyncio
    async def test_result_includes_variant_count_and_industry(self, service, mock_client):
        """Return dict includes variant_count and industry."""
        mock_client._request.return_value = {
            "id": "txn_count",
            "checkout": {"url": "https://checkout.paddle.com/count"},
        }

        variants = [
            {"id": "returns_refunds", "quantity": 1, "price": 29},
            {"id": "product_faq", "quantity": 1, "price": 19},
        ]

        result = await service.create_variant_checkout(
            session_id="sess_count",
            variants=variants,
            industry="saas",
        )

        assert result["variant_count"] == 2
        assert result["industry"] == "saas"
        assert "items" in result

    @pytest.mark.asyncio
    async def test_uses_price_per_month_key_as_fallback(self, service, mock_client):
        """Variant dict may use 'price_per_month' instead of 'price'."""
        mock_client._request.return_value = {
            "id": "txn_ppm",
            "checkout": {"url": "https://checkout.paddle.com/ppm"},
        }

        variants = [{"id": "billing_support", "quantity": 1, "price_per_month": 49}]

        result = await service.create_variant_checkout(
            session_id="sess_ppm",
            variants=variants,
            industry="saas",
        )

        assert result["total_monthly"] == "49"


# ══════════════════════════════════════════════════════════════════════════
# 4. TestHandleSubscriptionWebhook
# ══════════════════════════════════════════════════════════════════════════

class TestHandleSubscriptionWebhook:
    """Tests for PaddleService.handle_subscription_webhook."""

    @pytest.mark.asyncio
    async def test_processes_subscription_activated_event(self, service):
        """Returns processed result for subscription.activated."""
        event_data = {
            "subscription_id": "sub_activated_001",
            "customer_id": "ctm_001",
            "custom_data": {
                "session_id": "sess_sub",
                "variant_ids": ["returns_refunds", "product_faq"],
                "industry": "e-commerce",
                "variant_quantities": {"returns_refunds": 2, "product_faq": 1},
            },
        }

        result = await service.handle_subscription_webhook(event_data)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_activated"

    @pytest.mark.asyncio
    async def test_builds_hired_variants_list_with_quantities(self, service):
        """hired_variants contains id, quantity, and paddle_price_id for each variant."""
        event_data = {
            "subscription_id": "sub_variants",
            "customer_id": "ctm_002",
            "custom_data": {
                "session_id": "sess_hv",
                "variant_ids": ["returns_refunds", "shipping_inquiries"],
                "industry": "e-commerce",
                "variant_quantities": {"returns_refunds": 3, "shipping_inquiries": 1},
            },
        }

        result = await service.handle_subscription_webhook(event_data)

        assert len(result["hired_variants"]) == 2

        rv = next(v for v in result["hired_variants"] if v["id"] == "returns_refunds")
        assert rv["quantity"] == 3
        assert rv["paddle_price_id"] == VARIANT_PRICE_IDS.get("returns_refunds", "")

        sv = next(v for v in result["hired_variants"] if v["id"] == "shipping_inquiries")
        assert sv["quantity"] == 1
        assert sv["paddle_price_id"] == VARIANT_PRICE_IDS.get("shipping_inquiries", "")

    @pytest.mark.asyncio
    async def test_extracts_variant_ids_and_industry_from_custom_data(self, service):
        """variant_ids and industry come from custom_data."""
        event_data = {
            "subscription_id": "sub_extract",
            "custom_data": {
                "session_id": "sess_ext",
                "variant_ids": ["api_support"],
                "industry": "saas",
                "variant_quantities": {"api_support": 5},
            },
        }

        result = await service.handle_subscription_webhook(event_data)

        assert result["industry"] == "saas"
        assert result["variant_count"] == 1
        assert result["hired_variants"][0]["id"] == "api_support"

    @pytest.mark.asyncio
    async def test_raises_webhook_processing_error_when_no_session_id(self, service):
        """Raises WebhookProcessingError when custom_data has no session_id."""
        event_data = {
            "subscription_id": "sub_nosid",
            "custom_data": {"variant_ids": [], "industry": "unknown"},
        }

        with pytest.raises(WebhookProcessingError) as exc_info:
            await service.handle_subscription_webhook(event_data)

        assert "No session_id" in str(exc_info.value.message)
        assert exc_info.value.details["subscription_id"] == "sub_nosid"

    @pytest.mark.asyncio
    async def test_default_quantity_is_1_when_not_specified(self, service):
        """Variants without explicit quantity default to 1."""
        event_data = {
            "subscription_id": "sub_defqty",
            "custom_data": {
                "session_id": "sess_defqty",
                "variant_ids": ["billing_support"],
                "industry": "saas",
                # variant_quantities omits billing_support
                "variant_quantities": {},
            },
        }

        result = await service.handle_subscription_webhook(event_data)

        hv = result["hired_variants"][0]
        assert hv["id"] == "billing_support"
        assert hv["quantity"] == 1

    @pytest.mark.asyncio
    async def test_result_includes_subscription_and_customer_id(self, service):
        """Result dict includes subscription_id and customer_id."""
        event_data = {
            "subscription_id": "sub_ids",
            "customer_id": "ctm_999",
            "custom_data": {
                "session_id": "sess_ids",
                "variant_ids": ["fleet_management"],
                "industry": "logistics",
                "variant_quantities": {"fleet_management": 1},
            },
        }

        result = await service.handle_subscription_webhook(event_data)

        assert result["subscription_id"] == "sub_ids"
        assert result["customer_id"] == "ctm_999"
        assert "activated_at" in result


# ══════════════════════════════════════════════════════════════════════════
# 5. TestGetPaymentStatus
# ══════════════════════════════════════════════════════════════════════════

class TestGetPaymentStatus:
    """Tests for PaddleService.get_payment_status."""

    @pytest.mark.asyncio
    async def test_returns_default_none_status(self, service):
        """Default payment status is 'none'."""
        result = await service.get_payment_status(session_id="sess_status")

        assert result["status"] == "none"

    @pytest.mark.asyncio
    async def test_returns_correct_default_fields(self, service):
        """All default fields are present with expected values."""
        result = await service.get_payment_status(session_id="sess_fields")

        assert result["paddle_transaction_id"] is None
        assert result["amount"] is None
        assert result["currency"] == "USD"
        assert result["paid_at"] is None
        assert result["pack_type"] == "free"
        assert result["session_id"] == "sess_fields"


# ══════════════════════════════════════════════════════════════════════════
# 6. TestIdempotency
# ══════════════════════════════════════════════════════════════════════════

class TestIdempotency:
    """Tests for PaddleService.is_duplicate_event and mark_event_processed."""

    def test_is_duplicate_returns_true_for_processed_event_id(self):
        """Returns True when event_id is in the processed_ids set."""
        processed = {"evt_001", "evt_002", "evt_003"}

        assert PaddleService.is_duplicate_event("evt_001", processed) is True

    def test_is_duplicate_returns_false_for_new_event_id(self):
        """Returns False when event_id is not in processed_ids."""
        processed = {"evt_001", "evt_002"}

        assert PaddleService.is_duplicate_event("evt_new", processed) is False

    def test_is_duplicate_returns_false_when_processed_ids_is_none(self):
        """Returns False when processed_ids is None (no tracking)."""
        assert PaddleService.is_duplicate_event("evt_any", None) is False

    def test_mark_event_processed_adds_to_set(self):
        """mark_event_processed adds the event_id to the set."""
        processed = set()

        PaddleService.mark_event_processed("evt_100", processed)

        assert "evt_100" in processed

    def test_mark_event_processed_does_not_duplicate(self):
        """Adding same event_id twice doesn't create duplicates in set."""
        processed = set()

        PaddleService.mark_event_processed("evt_200", processed)
        PaddleService.mark_event_processed("evt_200", processed)

        assert len(processed) == 1
        assert "evt_200" in processed

    def test_is_duplicate_after_mark(self):
        """After marking, is_duplicate_event returns True."""
        processed = set()

        assert PaddleService.is_duplicate_event("evt_300", processed) is False

        PaddleService.mark_event_processed("evt_300", processed)

        assert PaddleService.is_duplicate_event("evt_300", processed) is True


# ══════════════════════════════════════════════════════════════════════════
# 7. TestPriceIdLoading
# ══════════════════════════════════════════════════════════════════════════

class TestPriceIdLoading:
    """Tests for _load_price_ids, PLAN_PRICE_IDS, and VARIANT_PRICE_IDS."""

    def test_load_price_ids_returns_defaults(self):
        """When no env override, _load_price_ids returns defaults."""
        with patch("app.config.get_settings") as mock_settings:
            # Simulate empty PADDLE_PRICE_IDS
            mock_settings.return_value.PADDLE_PRICE_IDS = ""

            result = _load_price_ids()

            assert result == _DEFAULT_PRICE_IDS

    def test_load_price_ids_merges_env_overrides(self):
        """Env overrides are merged on top of defaults."""
        override_json = json.dumps({"demo_pack": "pri_override_demo", "mini_parwa": "pri_override_mini"})

        with patch("app.config.get_settings") as mock_settings:
            mock_settings.return_value.PADDLE_PRICE_IDS = override_json

            result = _load_price_ids()

            # Overridden keys
            assert result["demo_pack"] == "pri_override_demo"
            assert result["mini_parwa"] == "pri_override_mini"
            # Unchanged keys keep defaults
            assert result["parwa"] == _DEFAULT_PRICE_IDS["parwa"]
            assert result["returns_refunds"] == _DEFAULT_PRICE_IDS["returns_refunds"]

    def test_load_price_ids_returns_copy_of_defaults_on_exception(self):
        """If get_settings() raises, falls back to a copy of defaults."""
        with patch("app.config.get_settings", side_effect=Exception("no config")):
            result = _load_price_ids()

            assert result == _DEFAULT_PRICE_IDS
            # Verify it's a copy, not the same object
            assert result is not _DEFAULT_PRICE_IDS

    def test_plan_price_ids_has_correct_keys(self):
        """PLAN_PRICE_IDS contains mini_parwa, parwa, parwa_high."""
        assert "mini_parwa" in PLAN_PRICE_IDS
        assert "parwa" in PLAN_PRICE_IDS
        assert "parwa_high" in PLAN_PRICE_IDS

        # Plan keys should NOT contain demo_pack or industry variants
        assert "demo_pack" not in PLAN_PRICE_IDS
        assert "returns_refunds" not in PLAN_PRICE_IDS

    def test_variant_price_ids_has_correct_industry_variants(self):
        """VARIANT_PRICE_IDS contains industry variants but not plan or demo_pack keys."""
        # Should contain known industry variants
        assert "order_management" in VARIANT_PRICE_IDS
        assert "returns_refunds" in VARIANT_PRICE_IDS
        assert "technical_support" in VARIANT_PRICE_IDS
        assert "shipment_tracking" in VARIANT_PRICE_IDS
        assert "appointment_scheduling" in VARIANT_PRICE_IDS

        # Should NOT contain plan keys or demo_pack
        assert "demo_pack" not in VARIANT_PRICE_IDS
        assert "mini_parwa" not in VARIANT_PRICE_IDS
        assert "parwa" not in VARIANT_PRICE_IDS
        assert "parwa_high" not in VARIANT_PRICE_IDS

    def test_variant_price_ids_count(self):
        """VARIANT_PRICE_IDS has all non-plan, non-demo_pack entries."""
        expected_count = len(_DEFAULT_PRICE_IDS) - 4  # minus demo_pack, mini_parwa, parwa, parwa_high
        assert len(VARIANT_PRICE_IDS) == expected_count

    def test_demo_pack_price_id_matches_default(self):
        """DEMO_PACK_PRICE_ID reflects the default or override."""
        # In test env with no PADDLE_PRICE_IDS override, should be default
        assert DEMO_PACK_PRICE_ID == _DEFAULT_PRICE_IDS["demo_pack"]


# ══════════════════════════════════════════════════════════════════════════
# 8. TestPaddleServiceErrorClasses
# ══════════════════════════════════════════════════════════════════════════

class TestPaddleServiceErrorClasses:
    """Tests for custom exception classes."""

    def test_paddle_service_error_with_message_and_code(self):
        """PaddleServiceError stores message and code."""
        err = PaddleServiceError("something went wrong", code="test_error")

        assert err.message == "something went wrong"
        assert err.code == "test_error"
        assert str(err) == "something went wrong"
        assert err.details is None

    def test_paddle_service_error_with_details(self):
        """PaddleServiceError stores optional details."""
        err = PaddleServiceError(
            "bad thing",
            code="err_01",
            details={"foo": "bar"},
        )

        assert err.details == {"foo": "bar"}

    def test_demo_pack_already_active_error(self):
        """DemoPackAlreadyActiveError has correct code and default message."""
        err = DemoPackAlreadyActiveError()

        assert "already active" in str(err).lower()
        assert err.code == "demo_pack_already_active"

    def test_demo_pack_already_active_error_custom_message(self):
        """DemoPackAlreadyActiveError accepts custom message."""
        err = DemoPackAlreadyActiveError("User already has an active demo")

        assert "User already has an active demo" in str(err)
        assert err.code == "demo_pack_already_active"

    def test_checkout_creation_error_with_details(self):
        """CheckoutCreationError stores details."""
        err = CheckoutCreationError("checkout failed", details={"paddle_error": "timeout"})

        assert err.message == "checkout failed"
        assert err.code == "checkout_creation_failed"
        assert err.details == {"paddle_error": "timeout"}

    def test_checkout_creation_error_default_message(self):
        """CheckoutCreationError has a sensible default message."""
        err = CheckoutCreationError()

        assert "Failed to create checkout" in str(err)

    def test_payment_not_found_error(self):
        """PaymentNotFoundError has correct code and default message."""
        err = PaymentNotFoundError()

        assert "Payment not found" in str(err)
        assert err.code == "payment_not_found"

    def test_payment_not_found_error_custom_message(self):
        """PaymentNotFoundError accepts custom message."""
        err = PaymentNotFoundError("No payment for session xyz")

        assert "No payment for session xyz" in str(err)

    def test_webhook_processing_error_with_details(self):
        """WebhookProcessingError stores details."""
        err = WebhookProcessingError(
            "missing session",
            details={"event_id": "evt_123"},
        )

        assert err.message == "missing session"
        assert err.code == "webhook_processing_failed"
        assert err.details == {"event_id": "evt_123"}

    def test_webhook_processing_error_default_message(self):
        """WebhookProcessingError has sensible default message."""
        err = WebhookProcessingError()

        assert "Webhook processing failed" in str(err)

    def test_error_inheritance(self):
        """All custom errors inherit from PaddleServiceError."""
        assert issubclass(DemoPackAlreadyActiveError, PaddleServiceError)
        assert issubclass(CheckoutCreationError, PaddleServiceError)
        assert issubclass(PaymentNotFoundError, PaddleServiceError)
        assert issubclass(WebhookProcessingError, PaddleServiceError)

    def test_error_inherits_from_exception(self):
        """PaddleServiceError inherits from Exception."""
        assert issubclass(PaddleServiceError, Exception)


# ══════════════════════════════════════════════════════════════════════════
# 9. TestPaddleServiceFactory
# ══════════════════════════════════════════════════════════════════════════

class TestPaddleServiceFactory:
    """Tests for get_paddle_service and PaddleService.client property."""

    def test_get_paddle_service_returns_singleton(self):
        """get_paddle_service returns the same instance on repeated calls."""
        # Reset the singleton for test isolation
        import app.services.paddle_service as ps_mod
        ps_mod._paddle_service = None

        svc1 = get_paddle_service()
        svc2 = get_paddle_service()

        assert svc1 is svc2

        # Clean up
        ps_mod._paddle_service = None

    def test_client_property_creates_paddle_client_lazily(self):
        """PaddleService.client creates a PaddleClient via get_paddle_client on first access."""
        svc = PaddleService(client=None)

        mock_client = MagicMock(spec=PaddleClient)

        with patch("app.services.paddle_service.get_paddle_client", return_value=mock_client) as mock_factory:
            # First access triggers lazy init
            client = svc.client
            assert client is mock_client
            mock_factory.assert_called_once()

            # Second access returns same client without new call
            client2 = svc.client
            assert client2 is mock_client
            assert mock_factory.call_count == 1

    def test_client_property_returns_injected_client(self):
        """If client is provided to __init__, it's returned directly."""
        mock_client = MagicMock(spec=PaddleClient)
        svc = PaddleService(client=mock_client)

        assert svc.client is mock_client

    def test_service_init_with_no_client(self):
        """PaddleService can be initialized without a client."""
        svc = PaddleService()
        assert svc._client is None

    def test_service_init_with_client(self):
        """PaddleService stores the provided client."""
        mock_client = MagicMock(spec=PaddleClient)
        svc = PaddleService(client=mock_client)
        assert svc._client is mock_client


# ══════════════════════════════════════════════════════════════════════════
# 10. TestConstants
# ══════════════════════════════════════════════════════════════════════════

class TestConstants:
    """Verify the module-level constants have expected values."""

    def test_demo_pack_amount(self):
        assert DEMO_PACK_AMOUNT == "1.00"

    def test_demo_pack_currency(self):
        assert DEMO_PACK_CURRENCY == "USD"

    def test_demo_pack_messages(self):
        assert DEMO_PACK_MESSAGES == 500

    def test_demo_pack_call_minutes(self):
        assert DEMO_PACK_CALL_MINUTES == 3

    def test_demo_pack_duration_hours(self):
        assert DEMO_PACK_DURATION_HOURS == 24
