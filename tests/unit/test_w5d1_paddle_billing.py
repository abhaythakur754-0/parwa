"""
Unit Tests for Week 5 Day 1: Paddle Client + Billing Tables + Schemas

Tests:
- PaddleClient initialization and configuration
- PaddleClient retry logic with exponential backoff
- PaddleClient rate limiting
- PaddleClient webhook signature verification
- Billing schema validation
- Billing extended models
- Overage calculation
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

# ── Paddle Client Tests ─────────────────────────────────────────────────────


class TestPaddleClientInit:
    """Tests for PaddleClient initialization."""

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="test_api_key_12345",
            sandbox=True,
        )

        assert client.api_key == "test_api_key_12345"
        assert client.sandbox is True
        assert "sandbox" in client.base_url

    def test_init_production_mode(self):
        """Test client initialization in production mode."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="live_api_key_12345",
            sandbox=False,
        )

        assert client.sandbox is False
        assert "sandbox" not in client.base_url
        assert "api.paddle.com" in client.base_url

    def test_init_with_webhook_secret(self):
        """Test client initialization with webhook secret."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="test_key",
            webhook_secret="whsec_test123",
        )

        assert client.webhook_secret == "whsec_test123"


class TestPaddleClientRetry:
    """Tests for PaddleClient retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_5xx_error(self):
        """Test that client retries on 5xx errors."""
        from backend.app.clients.paddle_client import PaddleClient, PaddleError

        client = PaddleClient(api_key="test_key", sandbox=True)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Server Error"}

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        client._client = mock_http_client

        with pytest.raises(PaddleError):
            await client._request("GET", "/subscriptions")

        # Should have retried MAX_RETRIES times
        assert mock_http_client.request.call_count >= 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_error(self):
        """Test that client does NOT retry on 4xx errors (except 429)."""
        from backend.app.clients.paddle_client import PaddleClient, PaddleNotFoundError

        client = PaddleClient(api_key="test_key", sandbox=True)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_http_client = AsyncMock()
        mock_http_client.request = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False

        client._client = mock_http_client

        with pytest.raises(PaddleNotFoundError):
            await client._request("GET", "/subscriptions/invalid")

        # Should NOT retry on 404
        assert mock_http_client.request.call_count == 1


class TestPaddleClientRateLimit:
    """Tests for PaddleClient rate limiting."""

    def test_rate_limit_tracking(self):
        """Test that rate limit tracking works."""
        from backend.app.clients.paddle_client import PaddleClient, RATE_LIMIT_REQUESTS

        client = PaddleClient(api_key="test_key", sandbox=True)

        # Simulate requests up to limit
        for _ in range(RATE_LIMIT_REQUESTS):
            client._check_rate_limit()

        assert len(client._request_times) >= RATE_LIMIT_REQUESTS

    def test_rate_limit_clears_old_requests(self):
        """Test that old requests are removed from tracking."""
        from backend.app.clients.paddle_client import PaddleClient, RATE_LIMIT_WINDOW

        client = PaddleClient(api_key="test_key", sandbox=True)

        # Add an old request
        import time
        old_time = time.time() - RATE_LIMIT_WINDOW - 10
        client._request_times.append(old_time)

        # Check rate limit (should clear old entry)
        client._check_rate_limit()

        assert old_time not in client._request_times


class TestPaddleClientWebhookSignature:
    """Tests for Paddle webhook signature verification."""

    def test_verify_valid_signature(self):
        """Test verification of valid webhook signature."""
        from backend.app.clients.paddle_client import PaddleClient

        webhook_secret = "test_webhook_secret"
        client = PaddleClient(
            api_key="test_key",
            webhook_secret=webhook_secret,
        )

        # Create a test payload
        payload = b'{"event_type": "subscription.created", "data": {}}'

        # Generate valid signature
        expected_sig = hmac.new(
            webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        assert client.verify_webhook_signature(payload, expected_sig) is True

    def test_verify_invalid_signature(self):
        """Test verification of invalid webhook signature."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(
            api_key="test_key",
            webhook_secret="test_webhook_secret",
        )

        payload = b'{"event_type": "subscription.created"}'
        invalid_sig = "invalid_signature_12345"

        assert client.verify_webhook_signature(payload, invalid_sig) is False

    def test_verify_without_secret(self):
        """Test that verification fails without webhook secret."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key")

        payload = b'{"event_type": "subscription.created"}'
        sig = "any_signature"

        assert client.verify_webhook_signature(payload, sig) is False

    def test_parse_webhook_event(self):
        """Test parsing webhook event payload."""
        from backend.app.clients.paddle_client import PaddleClient

        client = PaddleClient(api_key="test_key")

        payload = json.dumps({
            "event_type": "subscription.created",
            "event_id": "evt_123456",
            "occurred_at": "2024-01-15T10:30:00Z",
            "data": {
                "id": "sub_789",
                "status": "active",
            },
        }).encode()

        event = client.parse_webhook_event(payload)

        assert event["event_type"] == "subscription.created"
        assert event["event_id"] == "evt_123456"
        assert event["data"]["id"] == "sub_789"


# ── Billing Schema Tests ─────────────────────────────────────────────────────


class TestBillingSchemas:
    """Tests for billing Pydantic schemas."""

    def test_variant_type_enum(self):
        """Test VariantType enum values."""
        from backend.app.schemas.billing import VariantType

        assert VariantType.STARTER.value == "mini_parwa"
        assert VariantType.GROWTH.value == "parwa"
        assert VariantType.HIGH.value == "high"

    def test_subscription_status_enum(self):
        """Test SubscriptionStatus enum values."""
        from backend.app.schemas.billing import SubscriptionStatus

        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.PAST_DUE.value == "past_due"
        assert SubscriptionStatus.CANCELED.value == "canceled"
        assert SubscriptionStatus.PAYMENT_FAILED.value == "payment_failed"

    def test_variant_limits_schema(self):
        """Test VariantLimits schema."""
        from backend.app.schemas.billing import VariantLimits, VariantType

        limits = VariantLimits(
            variant=VariantType.STARTER,
            monthly_tickets=2000,
            ai_agents=1,
            team_members=3,
            voice_slots=0,
            kb_docs=100,
            price=Decimal("999.00"),
        )

        assert limits.variant == VariantType.STARTER
        assert limits.monthly_tickets == 2000
        assert limits.price == Decimal("999.00")

    def test_subscription_create_schema(self):
        """Test SubscriptionCreate schema."""
        from backend.app.schemas.billing import SubscriptionCreate, VariantType

        sub = SubscriptionCreate(
            variant=VariantType.GROWTH,
            payment_method_id="pm_12345",
        )

        assert sub.variant == VariantType.GROWTH
        assert sub.payment_method_id == "pm_12345"

    def test_subscription_cancel_schema(self):
        """Test SubscriptionCancel schema."""
        from backend.app.schemas.billing import SubscriptionCancel

        cancel = SubscriptionCancel(
            reason="Too expensive",
            effective_immediately=False,
        )

        assert cancel.reason == "Too expensive"
        assert cancel.effective_immediately is False

    def test_client_refund_create_validation(self):
        """Test ClientRefundCreate validation."""
        from backend.app.schemas.billing import ClientRefundCreate

        # Valid refund
        refund = ClientRefundCreate(
            amount=Decimal("29.99"),
            reason="Customer request",
        )
        assert refund.amount == Decimal("29.99")

        # Invalid: negative amount
        with pytest.raises(ValidationError):
            ClientRefundCreate(
                amount=Decimal("-10.00"),
                reason="Invalid",
            )

        # Invalid: zero amount
        with pytest.raises(ValidationError):
            ClientRefundCreate(
                amount=Decimal("0.00"),
                reason="Invalid",
            )

    def test_usage_info_schema(self):
        """Test UsageInfo schema."""
        from backend.app.schemas.billing import UsageInfo
        from uuid import uuid4

        company_id = uuid4()
        usage = UsageInfo(
            company_id=company_id,
            record_month="2024-01",
            tickets_used=1500,
            ticket_limit=2000,
            usage_percentage=0.75,
        )

        assert usage.tickets_used == 1500
        assert usage.ticket_limit == 2000
        assert usage.usage_percentage == 0.75
        assert usage.limit_exceeded is False

    def test_proration_result_schema(self):
        """Test ProrationResult schema."""
        from backend.app.schemas.billing import ProrationResult, VariantType

        proration = ProrationResult(
            old_variant=VariantType.STARTER,
            new_variant=VariantType.GROWTH,
            old_price=Decimal("999.00"),
            new_price=Decimal("2499.00"),
            days_remaining=15,
            days_in_period=30,
            unused_amount=Decimal("499.50"),
            proration_credit=Decimal("499.50"),
            new_charge=Decimal("1249.50"),
            net_charge=Decimal("750.00"),
            billing_cycle_start=date(2024, 1, 1),
            billing_cycle_end=date(2024, 1, 31),
        )

        assert proration.net_charge == Decimal("750.00")
        assert proration.days_remaining == 15


class TestPaddleSchemas:
    """Tests for Paddle webhook event schemas."""

    def test_event_type_enum_count(self):
        """Test that we have 25+ event types defined."""
        from backend.app.schemas.paddle import PaddleEventType, SUPPORTED_EVENT_TYPES

        # Should have at least 25 event types
        assert len(SUPPORTED_EVENT_TYPES) >= 25

    def test_subscription_event_types(self):
        """Test subscription event types exist."""
        from backend.app.schemas.paddle import PaddleEventType

        assert PaddleEventType.SUBSCRIPTION_CREATED
        assert PaddleEventType.SUBSCRIPTION_UPDATED
        assert PaddleEventType.SUBSCRIPTION_CANCELED
        assert PaddleEventType.SUBSCRIPTION_PAST_DUE
        assert PaddleEventType.SUBSCRIPTION_PAUSED
        assert PaddleEventType.SUBSCRIPTION_RESUMED

    def test_transaction_event_types(self):
        """Test transaction event types exist."""
        from backend.app.schemas.paddle import PaddleEventType

        assert PaddleEventType.TRANSACTION_COMPLETED
        assert PaddleEventType.TRANSACTION_PAID
        assert PaddleEventType.TRANSACTION_PAYMENT_FAILED
        assert PaddleEventType.TRANSACTION_CANCELED

    def test_paddle_subscription_data(self):
        """Test PaddleSubscriptionData schema."""
        from backend.app.schemas.paddle import PaddleSubscriptionData

        data = PaddleSubscriptionData(
            id="sub_123456",
            status="active",
            customer_id="cus_789",
            items=[{
                "price_id": "pri_abc",
                "quantity": 1,
            }],
        )

        assert data.id == "sub_123456"
        assert data.status == "active"

    def test_paddle_transaction_data(self):
        """Test PaddleTransactionData schema."""
        from backend.app.schemas.paddle import PaddleTransactionData

        data = PaddleTransactionData(
            id="txn_123456",
            status="completed",
            customer_id="cus_789",
        )

        assert data.id == "txn_123456"
        assert data.status == "completed"


# ── Billing Extended Models Tests ────────────────────────────────────────────


class TestBillingExtendedModels:
    """Tests for billing extended database models."""

    def test_get_variant_limits_starter(self):
        """Test getting starter variant limits."""
        from database.models.billing_extended import get_variant_limits

        limits = get_variant_limits("mini_parwa")

        assert limits is not None
        assert limits["monthly_tickets"] == 2000
        assert limits["ai_agents"] == 1
        assert limits["team_members"] == 3
        assert limits["voice_slots"] == 0
        assert limits["kb_docs"] == 100
        assert limits["price_monthly"] == Decimal("999.00")

    def test_get_variant_limits_growth(self):
        """Test getting growth variant limits."""
        from database.models.billing_extended import get_variant_limits

        limits = get_variant_limits("parwa")

        assert limits is not None
        assert limits["monthly_tickets"] == 5000
        assert limits["ai_agents"] == 3
        assert limits["price_monthly"] == Decimal("2499.00")

    def test_get_variant_limits_high(self):
        """Test getting high variant limits."""
        from database.models.billing_extended import get_variant_limits

        limits = get_variant_limits("high")

        assert limits is not None
        assert limits["monthly_tickets"] == 15000
        assert limits["ai_agents"] == 5
        assert limits["price_monthly"] == Decimal("3999.00")

    def test_get_variant_limits_invalid(self):
        """Test getting invalid variant limits."""
        from database.models.billing_extended import get_variant_limits

        limits = get_variant_limits("invalid_variant")

        assert limits is None

    def test_get_variant_limits_case_insensitive(self):
        """Test that variant name is case insensitive."""
        from database.models.billing_extended import get_variant_limits

        limits1 = get_variant_limits("STARTER")
        limits2 = get_variant_limits("Starter")
        limits3 = get_variant_limits("mini_parwa")

        assert limits1 == limits2 == limits3


class TestOverageCalculation:
    """Tests for overage calculation."""

    def test_no_overage(self):
        """Test calculation when under limit."""
        from database.models.billing_extended import calculate_overage

        result = calculate_overage(tickets_used=1500, ticket_limit=2000)

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_exact_limit(self):
        """Test calculation at exact limit."""
        from database.models.billing_extended import calculate_overage

        result = calculate_overage(tickets_used=2000, ticket_limit=2000)

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_small_overage(self):
        """Test calculation with small overage."""
        from database.models.billing_extended import calculate_overage

        # 100 tickets over limit = $10.00
        result = calculate_overage(tickets_used=2100, ticket_limit=2000)

        assert result["overage_tickets"] == 100
        assert result["overage_charges"] == Decimal("10.00")
        assert result["overage_rate"] == Decimal("0.10")

    def test_large_overage(self):
        """Test calculation with large overage."""
        from database.models.billing_extended import calculate_overage

        # 5000 tickets over limit = $500.00
        result = calculate_overage(tickets_used=7000, ticket_limit=2000)

        assert result["overage_tickets"] == 5000
        assert result["overage_charges"] == Decimal("500.00")


# ── Limit Check Tests ────────────────────────────────────────────────────────


class TestLimitCheckResult:
    """Tests for limit check result schema."""

    def test_allowed_result(self):
        """Test allowed limit check result."""
        from backend.app.schemas.billing import LimitCheckResult

        result = LimitCheckResult(
            allowed=True,
            limit_type="tickets",
            current_usage=1500,
            limit=2000,
            remaining=500,
        )

        assert result.allowed is True
        assert result.remaining == 500

    def test_exceeded_result(self):
        """Test exceeded limit check result."""
        from backend.app.schemas.billing import LimitCheckResult

        result = LimitCheckResult(
            allowed=False,
            limit_type="tickets",
            current_usage=2500,
            limit=2000,
            remaining=0,
            message="Monthly ticket limit exceeded",
        )

        assert result.allowed is False
        assert result.remaining == 0
        assert "exceeded" in result.message


# ── Constants Validation Tests ───────────────────────────────────────────────


class TestVariantLimitsConstants:
    """Tests that VARIANT_LIMITS constant matches expectations."""

    def test_variant_limits_completeness(self):
        """Test that all variants have all required fields."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        required_fields = [
            "monthly_tickets",
            "ai_agents",
            "team_members",
            "voice_slots",
            "kb_docs",
            "price",
        ]

        for variant in [VariantType.STARTER, VariantType.GROWTH, VariantType.HIGH]:
            limits = VARIANT_LIMITS[variant]
            for field in required_fields:
                assert field in limits, f"Missing {field} for {variant}"

    def test_variant_prices_are_decimal(self):
        """Test that all prices are Decimal type."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        for variant in [VariantType.STARTER, VariantType.GROWTH, VariantType.HIGH]:
            price = VARIANT_LIMITS[variant]["price"]
            assert isinstance(price, Decimal), f"Price for {variant} should be Decimal"

    def test_variant_tickets_increase(self):
        """Test that ticket limits increase with variant tier."""
        from backend.app.schemas.billing import VARIANT_LIMITS, VariantType

        starter_tickets = VARIANT_LIMITS[VariantType.STARTER]["monthly_tickets"]
        growth_tickets = VARIANT_LIMITS[VariantType.GROWTH]["monthly_tickets"]
        high_tickets = VARIANT_LIMITS[VariantType.HIGH]["monthly_tickets"]

        assert starter_tickets < growth_tickets < high_tickets
