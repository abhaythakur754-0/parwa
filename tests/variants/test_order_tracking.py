"""Tests for Order Tracking System."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from variants.ecommerce.advanced.order_tracking import (
    OrderTracking,
    OrderStatus
)
from variants.ecommerce.advanced.shipping_carriers import (
    ShippingCarriers,
    Carrier
)
from variants.ecommerce.advanced.proactive_notifier import (
    ProactiveNotifier,
    NotificationType,
    NotificationChannel
)
from variants.ecommerce.advanced.delivery_estimator import (
    DeliveryEstimator,
    DeliveryConfidence
)
from variants.ecommerce.advanced.exception_handler import (
    ExceptionHandler,
    ExceptionType,
    ResolutionType
)


class TestOrderTracking:
    """Tests for OrderTracking."""

    def test_order_tracking_initializes(self):
        """Test initialization."""
        ot = OrderTracking(client_id="test")
        assert ot.client_id == "test"

    def test_create_order(self):
        """Test order creation."""
        ot = OrderTracking(client_id="test")
        order = ot.create_order(
            order_id="ord_001",
            customer_id="cust_001",
            items=[{"product_id": "p1", "quantity": 2}],
            total=Decimal("99.99")
        )

        assert order.order_id == "ord_001"
        assert order.status == OrderStatus.PENDING

    def test_get_order_status(self):
        """Test get order status."""
        ot = OrderTracking(client_id="test")
        ot.create_order("ord_001", "cust_001", [], Decimal("50"))

        status = ot.get_order_status("ord_001")

        assert status is not None
        assert status["status"] == "pending"

    def test_update_status(self):
        """Test status update."""
        ot = OrderTracking(client_id="test")
        ot.create_order("ord_001", "cust_001", [], Decimal("50"))

        updated = ot.update_status("ord_001", OrderStatus.SHIPPED, "1Z1234567890")

        assert updated.status == OrderStatus.SHIPPED
        assert updated.tracking_number == "1Z1234567890"

    def test_validate_tracking_number(self):
        """Test tracking validation."""
        ot = OrderTracking(client_id="test")
        result = ot.validate_tracking_number("1Z1234567890123456")

        assert result["valid"] is True
        assert result["carrier"] == "UPS"

    def test_detect_carrier(self):
        """Test carrier detection."""
        ot = OrderTracking(client_id="test")

        assert ot.detect_carrier("1Z1234567890123456") == "UPS"

    def test_get_order_history(self):
        """Test order history."""
        ot = OrderTracking(client_id="test")
        ot.create_order("ord_001", "cust_001", [], Decimal("50"))
        ot.create_order("ord_002", "cust_001", [], Decimal("75"))

        history = ot.get_order_history("cust_001")

        assert len(history) == 2


class TestShippingCarriers:
    """Tests for ShippingCarriers."""

    def test_carriers_initializes(self):
        """Test initialization."""
        sc = ShippingCarriers(client_id="test")
        assert sc.client_id == "test"

    def test_detect_carrier(self):
        """Test carrier detection."""
        sc = ShippingCarriers(client_id="test")

        assert sc.detect_carrier("1Z1234567890123456") == Carrier.UPS
        assert sc.detect_carrier("123456789012") == Carrier.FEDEX

    def test_map_status(self):
        """Test status mapping."""
        sc = ShippingCarriers(client_id="test")

        status = sc.map_status(Carrier.UPS, "I")
        assert status == "in_transit"

    def test_get_tracking_url(self):
        """Test tracking URL generation."""
        sc = ShippingCarriers(client_id="test")

        url = sc.get_tracking_url(Carrier.UPS, "1Z1234567890123456")
        assert "ups.com" in url

    def test_get_rate_estimate(self):
        """Test rate estimate."""
        sc = ShippingCarriers(client_id="test")

        rates = sc.get_rate_estimate("10001", "90210", Decimal("2"))

        assert len(rates) == 4
        assert all("rate" in r for r in rates)


class TestProactiveNotifier:
    """Tests for ProactiveNotifier."""

    def test_notifier_initializes(self):
        """Test initialization."""
        pn = ProactiveNotifier(client_id="test")
        assert pn.client_id == "test"

    def test_send_shipped_notification(self):
        """Test shipped notification."""
        pn = ProactiveNotifier(client_id="test")

        notifications = pn.send_shipped_notification(
            customer_id="cust_001",
            order_id="ord_001",
            tracking_number="1Z123",
            carrier="UPS"
        )

        assert len(notifications) == 1
        assert notifications[0].notification_type == NotificationType.SHIPPED

    def test_send_out_for_delivery_notification(self):
        """Test out for delivery notification."""
        pn = ProactiveNotifier(client_id="test")

        notifications = pn.send_out_for_delivery_notification(
            customer_id="cust_001",
            order_id="ord_001",
            estimated_time="2:00 PM"
        )

        assert len(notifications) == 2  # SMS and Push

    def test_send_delivered_notification(self):
        """Test delivered notification."""
        pn = ProactiveNotifier(client_id="test")

        notifications = pn.send_delivered_notification(
            customer_id="cust_001",
            order_id="ord_001"
        )

        assert len(notifications) == 2

    def test_send_exception_notification(self):
        """Test exception notification."""
        pn = ProactiveNotifier(client_id="test")

        notifications = pn.send_exception_notification(
            customer_id="cust_001",
            order_id="ord_001",
            exception_type="Delayed due to weather",
            resolution="We're monitoring and will update you"
        )

        assert len(notifications) == 1


class TestDeliveryEstimator:
    """Tests for DeliveryEstimator."""

    def test_estimator_initializes(self):
        """Test initialization."""
        de = DeliveryEstimator(client_id="test")
        assert de.client_id == "test"

    def test_estimate_delivery(self):
        """Test delivery estimation."""
        de = DeliveryEstimator(client_id="test")

        estimate = de.estimate_delivery(
            carrier="UPS",
            service="ground",
            origin_region="west",
            destination_region="northeast"
        )

        assert estimate.estimated_date is not None
        assert estimate.confidence in DeliveryConfidence

    def test_apply_weather_delay(self):
        """Test weather delay application."""
        de = DeliveryEstimator(client_id="test")

        base = de.estimate_delivery("UPS", "ground", "west", "east")
        weather_affected = de.apply_weather_delay(base, 0.7)

        assert weather_affected.estimated_date > base.estimated_date
        assert weather_affected.confidence == DeliveryConfidence.LOW

    def test_get_delivery_window(self):
        """Test delivery window."""
        de = DeliveryEstimator(client_id="test")

        estimate = de.estimate_delivery("UPS", "ground", "west", "east")
        window = de.get_delivery_window(estimate)

        assert "earliest" in window
        assert "estimated" in window
        assert "latest" in window


class TestExceptionHandler:
    """Tests for ExceptionHandler."""

    def test_handler_initializes(self):
        """Test initialization."""
        eh = ExceptionHandler(client_id="test")
        assert eh.client_id == "test"

    def test_detect_exception(self):
        """Test exception detection."""
        eh = ExceptionHandler(client_id="test")

        events = [{"status": "exception", "description": "Package lost"}]
        exception = eh.detect_exception("1Z123", events)

        assert exception is not None
        assert exception.exception_type == ExceptionType.LOST

    def test_classify_exception(self):
        """Test exception classification."""
        eh = ExceptionHandler(client_id="test")

        events = [{"status": "exception", "description": "Package lost"}]
        exception = eh.detect_exception("1Z123", events)

        classification = eh.classify_exception(exception)

        assert classification["severity"] == "high"
        assert classification["recommended_resolution"] == "refund"

    def test_initiate_resolution_reship(self):
        """Test reship resolution."""
        eh = ExceptionHandler(client_id="test")

        events = [{"status": "exception", "description": "Package damaged"}]
        exception = eh.detect_exception("1Z123", events)

        result = eh.initiate_resolution(
            exception.exception_id,
            ResolutionType.RESHIP,
            Decimal("100"),
            pending_approval=False
        )

        assert result["success"] is True

    def test_initiate_refund_requires_approval(self):
        """Test refund requires approval (Paddle gate)."""
        eh = ExceptionHandler(client_id="test")

        events = [{"status": "exception", "description": "Package lost"}]
        exception = eh.detect_exception("1Z123", events)

        result = eh.initiate_resolution(
            exception.exception_id,
            ResolutionType.REFUND,
            Decimal("100"),
            pending_approval=True
        )

        assert result["status"] == "pending_approval"
        assert "Paddle gate" in result["message"]

    def test_check_refund_eligibility(self):
        """Test refund eligibility check."""
        eh = ExceptionHandler(client_id="test")

        eligible = eh.check_refund_eligibility(ExceptionType.LOST, 5)
        assert eligible["eligible"] is True

        not_eligible = eh.check_refund_eligibility(ExceptionType.DELAYED, 5)
        assert not_eligible["eligible"] is False

    def test_escalate_to_human(self):
        """Test escalation."""
        eh = ExceptionHandler(client_id="test")

        events = [{"status": "exception", "description": "Package lost"}]
        exception = eh.detect_exception("1Z123", events)

        result = eh.escalate_to_human(exception.exception_id, "Customer complaint")

        assert result["success"] is True
        assert result["escalated_to"] == "human_agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
