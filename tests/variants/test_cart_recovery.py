"""Tests for Cart Recovery System."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from variants.ecommerce.advanced.cart_recovery import (
    CartRecovery,
    CartStatus,
    RecoveryChannel,
    AbandonedCart,
    CartItem
)
from variants.ecommerce.advanced.recovery_scheduler import (
    RecoveryScheduler,
    SchedulePriority,
    ScheduledRecovery
)
from variants.ecommerce.advanced.recovery_templates import (
    RecoveryTemplates,
    TemplateVariant
)
from variants.ecommerce.advanced.incentive_engine import (
    IncentiveEngine,
    IncentiveType,
    IncentiveStatus
)
from variants.ecommerce.advanced.recovery_analytics import (
    RecoveryAnalytics,
    MetricPeriod
)


class TestCartRecovery:
    """Tests for CartRecovery."""

    def test_cart_recovery_initializes(self):
        """Test CartRecovery initializes correctly."""
        recovery = CartRecovery(client_id="test_client")
        assert recovery.client_id == "test_client"
        assert recovery.abandonment_threshold_minutes == 30

    def test_detect_abandoned_carts(self):
        """Test abandoned cart detection."""
        recovery = CartRecovery(client_id="test_client")
        abandoned = recovery.detect_abandoned_carts(threshold_minutes=60)

        assert isinstance(abandoned, list)

    def test_generate_recovery_message_email(self):
        """Test email recovery message generation."""
        recovery = CartRecovery(client_id="test_client")

        cart = AbandonedCart(
            cart_id="cart_001",
            customer_id="cust_001",
            items=[
                CartItem("prod_001", "Headphones", Decimal("99.99"), 1)
            ],
            total_value=Decimal("99.99"),
            abandoned_at=datetime.utcnow() - timedelta(hours=1),
            status=CartStatus.ABANDONED
        )

        message = recovery.generate_recovery_message(
            cart, RecoveryChannel.EMAIL
        )

        assert message.channel == RecoveryChannel.EMAIL
        assert message.cart_id == "cart_001"
        assert "Complete your purchase" in message.subject

    def test_generate_recovery_message_sms(self):
        """Test SMS recovery message generation."""
        recovery = CartRecovery(client_id="test_client")

        cart = AbandonedCart(
            cart_id="cart_002",
            customer_id="cust_002",
            items=[
                CartItem("prod_002", "Phone Case", Decimal("29.99"), 2)
            ],
            total_value=Decimal("59.98"),
            abandoned_at=datetime.utcnow() - timedelta(hours=2),
            status=CartStatus.ABANDONED
        )

        message = recovery.generate_recovery_message(
            cart, RecoveryChannel.SMS
        )

        assert message.channel == RecoveryChannel.SMS
        assert "59.98" in message.body

    def test_analyze_cart_content(self):
        """Test cart content analysis."""
        recovery = CartRecovery(client_id="test_client")

        cart = AbandonedCart(
            cart_id="cart_003",
            customer_id="cust_003",
            items=[
                CartItem("electronics_001", "Headphones", Decimal("199.99"), 1),
                CartItem("electronics_002", "Cable", Decimal("19.99"), 2)
            ],
            total_value=Decimal("239.97"),
            abandoned_at=datetime.utcnow(),
            status=CartStatus.ABANDONED
        )

        analysis = recovery.analyze_cart_content(cart)

        assert analysis["cart_type"] == "high_value"
        assert analysis["total_items"] == 2
        assert analysis["total_quantity"] == 3

    def test_check_opt_out(self):
        """Test opt-out check."""
        recovery = CartRecovery(client_id="test_client")
        opted_out = recovery.check_opt_out("cust_001")

        assert isinstance(opted_out, bool)

    def test_record_conversion(self):
        """Test recording a conversion."""
        recovery = CartRecovery(client_id="test_client")

        # Create a cart first
        cart = AbandonedCart(
            cart_id="cart_test",
            customer_id="cust_test",
            items=[CartItem("p1", "Product", Decimal("50"), 1)],
            total_value=Decimal("50"),
            abandoned_at=datetime.utcnow(),
            status=CartStatus.ABANDONED
        )
        recovery._carts["cart_test"] = cart

        result = recovery.record_conversion("cart_test", Decimal("50"))
        assert result is True
        assert cart.status == CartStatus.RECOVERED


class TestRecoveryScheduler:
    """Tests for RecoveryScheduler."""

    def test_scheduler_initializes(self):
        """Test scheduler initializes correctly."""
        scheduler = RecoveryScheduler(client_id="test_client")
        assert scheduler.client_id == "test_client"
        assert scheduler.default_timezone == "America/New_York"

    def test_schedule_recovery(self):
        """Test recovery scheduling."""
        scheduler = RecoveryScheduler(client_id="test_client")

        schedules = scheduler.schedule_recovery(
            cart_id="cart_001",
            customer_id="cust_001",
            cart_value=Decimal("150")
        )

        assert len(schedules) == 3  # 3 touches
        assert schedules[0].attempt_number == 1
        assert schedules[1].attempt_number == 2
        assert schedules[2].attempt_number == 3

    def test_determine_priority(self):
        """Test priority determination."""
        scheduler = RecoveryScheduler(client_id="test_client")

        high = scheduler._determine_priority(Decimal("300"))
        medium = scheduler._determine_priority(Decimal("100"))
        low = scheduler._determine_priority(Decimal("25"))

        assert high == SchedulePriority.HIGH
        assert medium == SchedulePriority.MEDIUM
        assert low == SchedulePriority.LOW

    def test_calculate_backoff(self):
        """Test backoff calculation."""
        scheduler = RecoveryScheduler(client_id="test_client")

        first = scheduler.calculate_backoff(1, 24)
        second = scheduler.calculate_backoff(2, 24)
        third = scheduler.calculate_backoff(3, 24)

        assert first == 24
        assert second == 48
        assert third == 96

    def test_is_within_business_hours(self):
        """Test business hours check."""
        scheduler = RecoveryScheduler(client_id="test_client")

        # Create datetime within business hours
        within = datetime(2026, 3, 26, 14, 0)  # Thursday 2pm
        outside = datetime(2026, 3, 26, 23, 0)  # Thursday 11pm

        assert scheduler.is_within_business_hours(within) is True
        assert scheduler.is_within_business_hours(outside) is False

    def test_mark_sent(self):
        """Test marking schedule as sent."""
        scheduler = RecoveryScheduler(client_id="test_client")

        # Create a schedule first
        schedules = scheduler.schedule_recovery("cart_test", "cust_test")
        schedule_id = schedules[0].schedule_id

        result = scheduler.mark_sent(schedule_id)
        assert result is True
        assert scheduler._schedules[schedule_id].status == "sent"


class TestRecoveryTemplates:
    """Tests for RecoveryTemplates."""

    def test_templates_initializes(self):
        """Test templates initialize correctly."""
        templates = RecoveryTemplates(client_id="test_client")
        assert templates.client_id == "test_client"
        assert templates.brand_name == "Our Store"

    def test_get_template_control(self):
        """Test getting control template."""
        templates = RecoveryTemplates(client_id="test_client")

        template = templates.get_template(
            RecoveryChannel.EMAIL,
            TemplateVariant.CONTROL
        )

        assert template.variant == TemplateVariant.CONTROL
        assert "cart" in template.subject_template.lower()

    def test_get_template_sms(self):
        """Test getting SMS template."""
        templates = RecoveryTemplates(client_id="test_client")

        template = templates.get_template(
            RecoveryChannel.SMS,
            TemplateVariant.URGENCY
        )

        assert template.channel == RecoveryChannel.SMS

    def test_render_template(self):
        """Test template rendering."""
        templates = RecoveryTemplates(client_id="test_client")
        template = templates.get_template(
            RecoveryChannel.EMAIL,
            TemplateVariant.CONTROL
        )

        context = {
            "customer_name": "John",
            "item_count": 3,
            "items_list": "Headphones, Cable, Case",
            "cart_total": "$149.99",
            "checkout_url": "https://example.com/checkout"
        }

        subject, body = templates.render_template(template, context)

        assert "John" in body
        assert "149.99" in body

    def test_select_variant(self):
        """Test variant selection."""
        templates = RecoveryTemplates(client_id="test_client")

        variant = templates.select_variant(
            customer_id="cust_001",
            cart_value=100,
            attempt=0
        )

        assert isinstance(variant, TemplateVariant)

    def test_select_variant_discount_for_later_attempts(self):
        """Test discount variant for later attempts."""
        templates = RecoveryTemplates(client_id="test_client")

        variant = templates.select_variant(
            customer_id="cust_001",
            cart_value=100,
            attempt=2
        )

        assert variant == TemplateVariant.DISCOUNT


class TestIncentiveEngine:
    """Tests for IncentiveEngine."""

    def test_engine_initializes(self):
        """Test engine initializes correctly."""
        engine = IncentiveEngine(client_id="test_client")
        assert engine.client_id == "test_client"
        assert engine.default_expiry_hours == 72

    def test_generate_percentage_incentive(self):
        """Test generating percentage discount."""
        engine = IncentiveEngine(client_id="test_client")

        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.PERCENTAGE,
            value=Decimal("10"),
            customer_id="cust_001"
        )

        assert incentive.incentive_type == IncentiveType.PERCENTAGE
        assert incentive.value == Decimal("10")
        assert len(incentive.code) == 8

    def test_generate_fixed_incentive(self):
        """Test generating fixed discount."""
        engine = IncentiveEngine(client_id="test_client")

        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.FIXED,
            value=Decimal("25"),
            customer_id="cust_001"
        )

        assert incentive.incentive_type == IncentiveType.FIXED
        assert incentive.value == Decimal("25")

    def test_check_eligibility_valid(self):
        """Test eligibility check for valid code."""
        engine = IncentiveEngine(client_id="test_client")

        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.PERCENTAGE,
            value=Decimal("10"),
            min_cart_value=Decimal("50")
        )

        result = engine.check_eligibility(
            code=incentive.code,
            customer_id="cust_001",
            cart_value=Decimal("100")
        )

        assert result.eligible is True

    def test_check_eligibility_invalid_code(self):
        """Test eligibility check for invalid code."""
        engine = IncentiveEngine(client_id="test_client")

        result = engine.check_eligibility(
            code="INVALID",
            customer_id="cust_001",
            cart_value=Decimal("100")
        )

        assert result.eligible is False
        assert "Invalid" in result.reason

    def test_margin_protection(self):
        """Test margin protection caps discount."""
        engine = IncentiveEngine(client_id="test_client")

        # Try to create 50% discount (exceeds max)
        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.PERCENTAGE,
            value=Decimal("50"),
            customer_segment="regular"
        )

        # Should be capped at 20% for regular segment
        assert incentive.value == Decimal("20")

    def test_apply_incentive(self):
        """Test applying incentive."""
        engine = IncentiveEngine(client_id="test_client")

        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.PERCENTAGE,
            value=Decimal("10")
        )

        discount, success = engine.apply_incentive(
            code=incentive.code,
            order_value=Decimal("100")
        )

        assert success is True
        assert discount == Decimal("10")

    def test_validate_with_paddle(self):
        """Test Paddle validation."""
        engine = IncentiveEngine(client_id="test_client")

        incentive = engine.generate_incentive(
            incentive_type=IncentiveType.PERCENTAGE,
            value=Decimal("10")
        )

        result = engine.validate_with_paddle(incentive.code)
        assert result is True


class TestRecoveryAnalytics:
    """Tests for RecoveryAnalytics."""

    def test_analytics_initializes(self):
        """Test analytics initializes correctly."""
        analytics = RecoveryAnalytics(client_id="test_client")
        assert analytics.client_id == "test_client"

    def test_track_event(self):
        """Test event tracking."""
        analytics = RecoveryAnalytics(client_id="test_client")

        analytics.track_event(
            event_type="abandoned",
            cart_id="cart_001",
            value=Decimal("100")
        )

        assert len(analytics._events) == 1

    def test_get_recovery_metrics(self):
        """Test recovery metrics."""
        analytics = RecoveryAnalytics(client_id="test_client")

        # Track some events
        analytics.track_event("abandoned", "cart_1", value=Decimal("100"))
        analytics.track_event("abandoned", "cart_2", value=Decimal("200"))
        analytics.track_event("recovered", "cart_1", value=Decimal("100"))

        metrics = analytics.get_recovery_metrics(MetricPeriod.WEEK)

        assert metrics.total_abandoned == 2
        assert metrics.total_recovered == 1
        assert metrics.recovery_rate == 0.5

    def test_get_channel_performance(self):
        """Test channel performance."""
        analytics = RecoveryAnalytics(client_id="test_client")

        # Track events
        analytics.track_event("message_sent", "cart_1", channel="email")
        analytics.track_event("opened", "cart_1", channel="email")
        analytics.track_event("clicked", "cart_1", channel="email")
        analytics.track_event("recovered", "cart_1", channel="email", value=Decimal("100"))

        perf = analytics.get_channel_performance("email")

        assert perf.messages_sent == 1
        assert perf.open_rate == 1.0

    def test_calculate_roi(self):
        """Test ROI calculation."""
        analytics = RecoveryAnalytics(client_id="test_client")

        analytics.track_event("abandoned", "cart_1", value=Decimal("100"))
        analytics.track_event("message_sent", "cart_1")
        analytics.track_event("recovered", "cart_1", value=Decimal("100"))

        roi = analytics.calculate_roi(MetricPeriod.WEEK)

        assert "roi_percent" in roi
        assert "revenue_recovered" in roi

    def test_export_analytics(self):
        """Test analytics export."""
        analytics = RecoveryAnalytics(client_id="test_client")

        analytics.track_event("abandoned", "cart_1", value=Decimal("100"))

        exported = analytics.export_analytics(MetricPeriod.WEEK)

        assert "client_id" in exported
        assert "period" in exported


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
