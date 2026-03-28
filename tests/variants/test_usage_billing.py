"""
Tests for Usage-Based Billing & Metering (Week 32, Builder 2).

Tests cover:
- UsageMeter: usage tracking, aggregation, limits
- BillingCalculator: tiered pricing, discounts, taxes
- OverageHandler: overage detection, grace periods
- UsageAlerts: threshold alerts, notifications
- InvoiceGenerator: invoice generation, PDF, Paddle integration
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from variants.saas.advanced.usage_meter import (
    UsageMeter,
    UsageRecord,
    UsageType,
    AggregationPeriod,
)
from variants.saas.advanced.billing_calculator import (
    BillingCalculator,
    BillingLineItem,
    BillingTier,
    Currency,
    TaxType,
)
from variants.saas.advanced.overage_handler import (
    OverageHandler,
    OverageRecord,
    OverageStatus,
    LimitType,
)
from variants.saas.advanced.usage_alerts import (
    UsageAlerts,
    UsageAlert,
    AlertThreshold,
    AlertSeverity,
    AlertChannel,
)
from variants.saas.advanced.invoice_generator import (
    InvoiceGenerator,
    Invoice,
    InvoiceStatus,
    PaymentTerms,
)


# =============================================================================
# UsageMeter Tests
# =============================================================================

class TestUsageMeter:
    """Tests for UsageMeter class."""

    @pytest.fixture
    def meter(self):
        """Create a usage meter instance."""
        return UsageMeter(client_id="test_client_001", tier="parwa")

    @pytest.mark.asyncio
    async def test_meter_initializes(self, meter):
        """Test that UsageMeter initializes correctly."""
        assert meter.client_id == "test_client_001"
        assert meter.tier == "parwa"
        assert meter._records == []

    @pytest.mark.asyncio
    async def test_track_usage(self, meter):
        """Test tracking usage."""
        record = await meter.track(UsageType.API_CALLS, quantity=100)

        assert record is not None
        assert record.usage_type == UsageType.API_CALLS
        assert record.quantity == 100

    @pytest.mark.asyncio
    async def test_track_api_call(self, meter):
        """Test tracking API call."""
        record = await meter.track_api_call(endpoint="/api/v1/tickets")

        assert record.usage_type == UsageType.API_CALLS
        assert record.quantity == 1
        assert record.metadata.get("endpoint") == "/api/v1/tickets"

    @pytest.mark.asyncio
    async def test_track_ai_interaction(self, meter):
        """Test tracking AI interaction."""
        record = await meter.track_ai_interaction(model="gpt-4", tokens=500)

        assert record.usage_type == UsageType.AI_INTERACTIONS
        assert record.metadata.get("model") == "gpt-4"
        assert record.metadata.get("tokens") == 500

    @pytest.mark.asyncio
    async def test_get_usage(self, meter):
        """Test getting usage summary."""
        await meter.track(UsageType.API_CALLS, quantity=100)
        await meter.track(UsageType.API_CALLS, quantity=50)
        await meter.track(UsageType.AI_INTERACTIONS, quantity=10)

        usage = await meter.get_usage()

        assert usage["usage"]["api_calls"] == 150
        assert usage["usage"]["ai_interactions"] == 10

    @pytest.mark.asyncio
    async def test_check_limit_within(self, meter):
        """Test checking limit when within bounds."""
        await meter.track(UsageType.TICKETS, quantity=100)

        status = await meter.check_limit(UsageType.TICKETS)

        assert status["at_limit"] is False
        assert status["over_limit"] is False
        assert status["remaining"] > 0

    @pytest.mark.asyncio
    async def test_check_limit_exceeded(self, meter):
        """Test checking limit when exceeded."""
        meter._limits[UsageType.TICKETS] = 100
        await meter.track(UsageType.TICKETS, quantity=150)

        status = await meter.check_limit(UsageType.TICKETS)

        assert status["over_limit"] is True

    @pytest.mark.asyncio
    async def test_get_usage_trend(self, meter):
        """Test getting usage trend."""
        await meter.track(UsageType.API_CALLS, quantity=50)
        await meter.track(UsageType.API_CALLS, quantity=30)

        trend = await meter.get_usage_trend(UsageType.API_CALLS, days=7)

        assert len(trend) == 7
        assert trend[-1]["usage"] == 80  # Today's usage

    @pytest.mark.asyncio
    async def test_update_tier(self, meter):
        """Test updating tier."""
        meter.update_tier("parwa_high")

        assert meter.tier == "parwa_high"


# =============================================================================
# BillingCalculator Tests
# =============================================================================

class TestBillingCalculator:
    """Tests for BillingCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create a billing calculator instance."""
        return BillingCalculator(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_calculator_initializes(self, calculator):
        """Test that BillingCalculator initializes correctly."""
        assert calculator.client_id == "test_client_001"
        assert calculator.currency == Currency.USD

    @pytest.mark.asyncio
    async def test_calculate_tiered_pricing(self, calculator):
        """Test tiered pricing calculation."""
        result = await calculator.calculate_tiered_pricing("api_calls", 5000)

        assert "total" in result
        assert "breakdown" in result
        assert len(result["breakdown"]) > 0

    @pytest.mark.asyncio
    async def test_apply_volume_discount(self, calculator):
        """Test volume discount application."""
        result = await calculator.apply_volume_discount(1000)

        assert result["discount_percent"] == 15
        assert result["discount_amount"] == 150

    @pytest.mark.asyncio
    async def test_apply_volume_discount_high(self, calculator):
        """Test high volume discount."""
        result = await calculator.apply_volume_discount(6000)

        assert result["discount_percent"] == 25
        assert result["discount_amount"] == 1500

    @pytest.mark.asyncio
    async def test_calculate_overage(self, calculator):
        """Test overage calculation."""
        result = await calculator.calculate_overage(
            "api_calls",
            included=1000,
            actual=1200
        )

        assert result["overage"] == 200
        assert result["overage_cost"] > 0

    @pytest.mark.asyncio
    async def test_calculate_overage_none(self, calculator):
        """Test no overage."""
        result = await calculator.calculate_overage(
            "api_calls",
            included=1000,
            actual=800
        )

        assert result["overage"] == 0
        assert result["overage_cost"] == 0

    @pytest.mark.asyncio
    async def test_calculate_proration(self, calculator):
        """Test proration calculation."""
        result = await calculator.calculate_proration(
            monthly_amount=149,
            days_in_period=30,
            days_used=15
        )

        assert result["credit"] == pytest.approx(74.50, rel=0.1)

    @pytest.mark.asyncio
    async def test_calculate_tax(self, calculator):
        """Test tax calculation."""
        result = await calculator.calculate_tax(100, region="EU")

        assert result["tax_rate"] == 0.20
        assert result["tax_amount"] == 20

    @pytest.mark.asyncio
    async def test_convert_currency(self, calculator):
        """Test currency conversion."""
        result = await calculator.convert_currency(
            100,
            Currency.USD,
            Currency.EUR
        )

        assert result["original_currency"] == "USD"
        assert result["converted_currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_generate_invoice_preview(self, calculator):
        """Test invoice preview generation."""
        preview = await calculator.generate_invoice_preview(
            subscription_tier="parwa",
            billing_cycle="monthly",
            usage_data={"api_calls": 1000, "ai_interactions": 100},
            region="US"
        )

        assert preview.subtotal > 0
        assert len(preview.line_items) > 0


# =============================================================================
# OverageHandler Tests
# =============================================================================

class TestOverageHandler:
    """Tests for OverageHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an overage handler instance."""
        return OverageHandler(client_id="test_client_001", tier="parwa")

    @pytest.mark.asyncio
    async def test_handler_initializes(self, handler):
        """Test that OverageHandler initializes correctly."""
        assert handler.client_id == "test_client_001"
        assert handler.tier == "parwa"

    @pytest.mark.asyncio
    async def test_check_no_overage(self, handler):
        """Test checking when no overage."""
        record = await handler.check_overage("api_calls", limit=1000, actual=800)

        assert record.status == OverageStatus.NONE
        assert record.overage == 0

    @pytest.mark.asyncio
    async def test_check_overage_soft_limit(self, handler):
        """Test soft limit overage."""
        record = await handler.check_overage("api_calls", limit=1000, actual=1200)

        assert record.overage == 200
        assert record.overage_cost > 0

    @pytest.mark.asyncio
    async def test_is_usage_allowed_soft(self, handler):
        """Test usage allowed with soft limit."""
        result = await handler.is_usage_allowed("api_calls", current=1100, limit=1000)

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_is_usage_allowed_hard(self, handler):
        """Test usage blocked with hard limit."""
        # Mini tier has hard limits for some things
        handler.update_tier("mini")
        result = await handler.is_usage_allowed("api_calls", current=11000, limit=10000)

        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_suggest_upgrade(self, handler):
        """Test upgrade suggestion."""
        overages = [
            {"usage_type": "api_calls", "overage_cost": 50},
            {"usage_type": "ai_interactions", "overage_cost": 30},
        ]

        suggestion = await handler.suggest_upgrade(overages)

        assert suggestion["suggested"] is True
        assert suggestion["suggested_tier"] in ["parwa_high", "enterprise"]


# =============================================================================
# UsageAlerts Tests
# =============================================================================

class TestUsageAlerts:
    """Tests for UsageAlerts class."""

    @pytest.fixture
    def alerts(self):
        """Create a usage alerts instance."""
        return UsageAlerts(
            client_id="test_client_001",
            email="test@example.com",
            phone="+1234567890"
        )

    @pytest.mark.asyncio
    async def test_alerts_initializes(self, alerts):
        """Test that UsageAlerts initializes correctly."""
        assert alerts.client_id == "test_client_001"
        assert alerts.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_check_and_alert_below_threshold(self, alerts):
        """Test no alert below threshold."""
        result = await alerts.check_and_alert("api_calls", current=500, limit=1000)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_and_alert_at_threshold(self, alerts):
        """Test alert at threshold."""
        result = await alerts.check_and_alert("api_calls", current=950, limit=1000)

        assert result is not None
        assert result.percentage >= 90

    @pytest.mark.asyncio
    async def test_send_predictive_alert(self, alerts):
        """Test predictive alert."""
        result = await alerts.send_predictive_alert(
            "api_calls",
            current=800,
            limit=1000,
            projected=1200,
            days_remaining=10
        )

        assert result is not None
        assert result.metadata["will_exceed"] is True

    @pytest.mark.asyncio
    async def test_set_preference(self, alerts):
        """Test setting alert preference."""
        pref = await alerts.set_preference(
            "api_calls",
            thresholds=[AlertThreshold.NINETY_PERCENT],
            channels=[AlertChannel.EMAIL],
            enabled=True
        )

        assert pref.thresholds == [AlertThreshold.NINETY_PERCENT]
        assert AlertChannel.EMAIL in pref.channels

    @pytest.mark.asyncio
    async def test_get_alert_history(self, alerts):
        """Test getting alert history."""
        await alerts.check_and_alert("api_calls", current=950, limit=1000)
        await alerts.check_and_alert("ai_interactions", current=4800, limit=5000)

        history = await alerts.get_alert_history()

        assert len(history) >= 2

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, alerts):
        """Test acknowledging alert."""
        alert = await alerts.check_and_alert("api_calls", current=950, limit=1000)

        result = await alerts.acknowledge_alert(alert.id)

        assert result["acknowledged"] is True


# =============================================================================
# InvoiceGenerator Tests
# =============================================================================

class TestInvoiceGenerator:
    """Tests for InvoiceGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create an invoice generator instance."""
        return InvoiceGenerator(
            client_id="test_client_001",
            company_name="Test Company",
            company_email="billing@test.com"
        )

    @pytest.mark.asyncio
    async def test_generator_initializes(self, generator):
        """Test that InvoiceGenerator initializes correctly."""
        assert generator.client_id == "test_client_001"
        assert generator.company_name == "Test Company"

    @pytest.mark.asyncio
    async def test_generate_invoice(self, generator):
        """Test generating an invoice."""
        invoice = await generator.generate_invoice(
            subscription_tier="parwa",
            billing_cycle="monthly",
            usage_data={"api_calls": 1000, "ai_interactions": 100},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        assert invoice is not None
        assert invoice.invoice_number.startswith("INV-")
        assert len(invoice.line_items) >= 2  # Subscription + usage

    @pytest.mark.asyncio
    async def test_generate_invoice_with_discount(self, generator):
        """Test generating invoice with discount."""
        invoice = await generator.generate_invoice(
            subscription_tier="parwa",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            discount_codes=["LAUNCH20"],
            tax_rate=0.0
        )

        assert invoice.discounts > 0

    @pytest.mark.asyncio
    async def test_generate_pdf(self, generator):
        """Test PDF generation."""
        invoice = await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        result = await generator.generate_pdf(invoice.id)

        assert result["pdf_generated"] is True

    @pytest.mark.asyncio
    async def test_send_invoice(self, generator):
        """Test sending invoice."""
        invoice = await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        result = await generator.send_invoice(invoice.id)

        assert result["sent"] is True
        assert invoice.status == InvoiceStatus.SENT

    @pytest.mark.asyncio
    async def test_mark_paid(self, generator):
        """Test marking invoice as paid."""
        invoice = await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        result = await generator.mark_paid(invoice.id, "pay_123456")

        assert result["paid"] is True
        assert invoice.status == InvoiceStatus.PAID

    @pytest.mark.asyncio
    async def test_get_invoice_history(self, generator):
        """Test getting invoice history."""
        await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        history = await generator.get_invoice_history()

        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_void_invoice(self, generator):
        """Test voiding invoice."""
        invoice = await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        result = await generator.void_invoice(invoice.id, "Customer request")

        assert result["voided"] is True
        assert invoice.status == InvoiceStatus.VOID

    @pytest.mark.asyncio
    async def test_create_paddle_checkout(self, generator):
        """Test creating Paddle checkout."""
        invoice = await generator.generate_invoice(
            subscription_tier="mini",
            billing_cycle="monthly",
            usage_data={},
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.0
        )

        result = await generator.create_paddle_checkout(invoice.id)

        assert result["checkout_url"] is not None
        assert "paddle.com" in result["checkout_url"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestUsageBillingIntegration:
    """Integration tests for usage billing."""

    @pytest.mark.asyncio
    async def test_full_billing_cycle(self):
        """Test complete billing cycle from usage to invoice."""
        client_id = "test_billing_001"

        # Track usage
        meter = UsageMeter(client_id=client_id, tier="parwa")
        await meter.track_api_call()
        await meter.track_ai_interaction("gpt-4", 500)
        await meter.track_voice_minutes(5.5)

        usage = await meter.get_usage()
        assert usage["record_count"] == 3

        # Check limits
        limit_check = await meter.check_all_limits()
        assert "limits" in limit_check

        # Generate invoice
        generator = InvoiceGenerator(
            client_id=client_id,
            company_name="Test Company",
            company_email="billing@test.com"
        )

        invoice = await generator.generate_invoice(
            subscription_tier="parwa",
            billing_cycle="monthly",
            usage_data=usage["usage"],
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc) + timedelta(days=30),
            tax_rate=0.08
        )

        assert invoice.total > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
