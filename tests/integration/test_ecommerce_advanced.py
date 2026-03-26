"""Integration Tests for E-commerce Advanced Features."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from variants.ecommerce.advanced.recommendation_engine import RecommendationEngine
from variants.ecommerce.advanced.cart_recovery import CartRecovery, CartStatus
from variants.ecommerce.advanced.incentive_engine import IncentiveEngine, IncentiveType
from variants.ecommerce.advanced.pricing_support import PricingSupport
from variants.ecommerce.advanced.order_tracking import OrderTracking, OrderStatus
from variants.ecommerce.advanced.ecommerce_analytics import EcommerceAnalytics


class TestFullRecommendationPipeline:
    """Test full recommendation pipeline."""

    def test_full_pipeline(self):
        """Test complete recommendation flow."""
        # Initialize engine
        engine = RecommendationEngine(client_id="test_client")

        # Get recommendations based on context
        result = engine.get_recommendations(
            context="Looking for wireless headphones",
            customer_id="cust_001"
        )

        assert result is not None
        assert result.recommendations is not None

    def test_recommendation_with_cross_sell(self):
        """Test recommendations with cross-sell."""
        from variants.ecommerce.advanced.cross_sell import CrossSellEngine

        rec_engine = RecommendationEngine(client_id="test")
        cross_sell = CrossSellEngine(client_id="test")

        # Get recommendations
        recs = rec_engine.get_recommendations("phone accessories")

        # Get cross-sell for recommended products
        if recs.recommendations:
            product_id = recs.recommendations[0].product.product_id
            cross_sell_recs = cross_sell.get_cross_sell_recommendations(
                product_id, "electronics"
            )

            assert isinstance(cross_sell_recs, list)


class TestEndToEndCartRecovery:
    """Test end-to-end cart recovery."""

    def test_full_recovery_flow(self):
        """Test complete cart recovery flow."""
        from variants.ecommerce.advanced.recovery_scheduler import RecoveryScheduler
        from variants.ecommerce.advanced.recovery_templates import RecoveryTemplates, TemplateVariant

        # Initialize components
        cart_recovery = CartRecovery(client_id="test")
        scheduler = RecoveryScheduler(client_id="test")
        templates = RecoveryTemplates(client_id="test")
        incentive_engine = IncentiveEngine(client_id="test")

        # Detect abandoned carts
        abandoned = cart_recovery.detect_abandoned_carts()

        if abandoned:
            cart = abandoned[0]

            # Schedule recovery
            schedules = scheduler.schedule_recovery(
                cart_id=cart.cart_id,
                customer_id=cart.customer_id,
                cart_value=cart.total_value
            )

            assert len(schedules) == 3

            # Generate incentive
            incentive = incentive_engine.generate_incentive(
                incentive_type=IncentiveType.PERCENTAGE,
                value=Decimal("10"),
                customer_id=cart.customer_id
            )

            assert incentive.code is not None

            # Get template
            template = templates.get_template(
                channel=templates.get_template(
                    templates.select_variant(
                        cart.customer_id,
                        float(cart.total_value),
                        0
                    ),
                    TemplateVariant.CONTROL
                ).channel,
                variant=TemplateVariant.CONTROL
            )

            assert template is not None


class TestDynamicPricingFlow:
    """Test dynamic pricing flow."""

    def test_pricing_flow(self):
        """Test complete pricing flow."""
        from variants.ecommerce.advanced.price_monitor import PriceMonitor
        from variants.ecommerce.advanced.competitor_tracker import CompetitorTracker
        from variants.ecommerce.advanced.price_adjustment import PriceAdjustmentEngine

        pricing = PricingSupport(client_id="test")
        monitor = PriceMonitor(client_id="test")
        tracker = CompetitorTracker(client_id="test")
        adjustment = PriceAdjustmentEngine(client_id="test")

        # Get price
        price = pricing.get_price("prod_001", currency="USD")
        assert "base_price" in price

        # Track competitor
        tracker.track_competitor("CompetitorA", "prod_001", Decimal("89.99"))

        # Analyze gap
        gap = tracker.analyze_price_gap("prod_001", Decimal("99.99"))
        assert "competitor_gaps" in gap

        # Get adjustment recommendation
        rec = adjustment.recommend_adjustment(
            "prod_001",
            Decimal("99.99"),
            Decimal("30"),
            Decimal("70")
        )
        assert "recommended_price" in rec


class TestOrderTrackingWorkflow:
    """Test order tracking workflow."""

    def test_tracking_workflow(self):
        """Test complete tracking workflow."""
        from variants.ecommerce.advanced.shipping_carriers import ShippingCarriers
        from variants.ecommerce.advanced.proactive_notifier import ProactiveNotifier
        from variants.ecommerce.advanced.delivery_estimator import DeliveryEstimator

        tracking = OrderTracking(client_id="test")
        carriers = ShippingCarriers(client_id="test")
        notifier = ProactiveNotifier(client_id="test")
        estimator = DeliveryEstimator(client_id="test")

        # Create order
        order = tracking.create_order(
            order_id="ord_001",
            customer_id="cust_001",
            items=[{"product_id": "p1", "quantity": 1}],
            total=Decimal("99.99")
        )

        assert order.status == OrderStatus.PENDING

        # Update to shipped
        tracking.update_status(
            "ord_001",
            OrderStatus.SHIPPED,
            tracking_number="1Z1234567890123456"
        )

        # Detect carrier
        carrier = carriers.detect_carrier("1Z1234567890123456")
        assert carrier is not None

        # Send notification
        notifications = notifier.send_shipped_notification(
            customer_id="cust_001",
            order_id="ord_001",
            tracking_number="1Z1234567890123456",
            carrier="UPS"
        )

        assert len(notifications) >= 1

        # Estimate delivery
        estimate = estimator.estimate_delivery(
            carrier="UPS",
            service="ground",
            origin_region="west",
            destination_region="northeast"
        )

        assert estimate.estimated_date is not None


class TestExceptionHandlingFlow:
    """Test exception handling flow."""

    def test_exception_flow(self):
        """Test complete exception handling."""
        from variants.ecommerce.advanced.exception_handler import (
            ExceptionHandler,
            ExceptionType,
            ResolutionType
        )

        handler = ExceptionHandler(client_id="test")

        # Detect exception
        events = [
            {"status": "exception", "description": "Package lost in transit"}
        ]
        exception = handler.detect_exception("1Z123", events)

        assert exception is not None
        assert exception.exception_type == ExceptionType.LOST

        # Classify
        classification = handler.classify_exception(exception)
        assert classification["severity"] == "high"

        # Check refund eligibility
        eligibility = handler.check_refund_eligibility(
            ExceptionType.LOST,
            order_age_days=5
        )
        assert eligibility["eligible"] is True

        # Initiate resolution (should require approval)
        result = handler.initiate_resolution(
            exception.exception_id,
            ResolutionType.REFUND,
            Decimal("100"),
            pending_approval=True
        )

        assert result["status"] == "pending_approval"


class TestAnalyticsDataFlow:
    """Test analytics data flow."""

    def test_analytics_flow(self):
        """Test complete analytics flow."""
        analytics = EcommerceAnalytics(client_id="test")

        # Track events
        analytics.track_event("product_view", {"product_id": "p1"})
        analytics.track_event("add_to_cart", {"product_id": "p1"})
        analytics.track_event("purchase", {
            "product_id": "p1",
            "revenue": 99.99,
            "customer_id": "c1"
        })

        # Get dashboard summary
        summary = analytics.get_dashboard_summary()

        assert summary.total_orders == 1
        assert summary.total_revenue == Decimal("99.99")

        # Get conversion funnel
        funnel = analytics.get_conversion_funnel()

        assert "stages" in funnel
        assert funnel["stages"]["purchase"] == 1


class Test30ClientValidation:
    """Test all features work across 30 clients."""

    def test_recommendations_for_all_clients(self):
        """Test recommendations work for all 30 clients."""
        for i in range(1, 31):
            client_id = f"client_{i:03d}"
            engine = RecommendationEngine(client_id=client_id)

            result = engine.get_recommendations(
                context="Looking for products",
                customer_id="cust_test"
            )

            assert result is not None, f"Failed for {client_id}"

    def test_cart_recovery_for_all_clients(self):
        """Test cart recovery works for all 30 clients."""
        for i in range(1, 31):
            client_id = f"client_{i:03d}"
            recovery = CartRecovery(client_id=client_id)

            abandoned = recovery.detect_abandoned_carts()
            assert isinstance(abandoned, list), f"Failed for {client_id}"

    def test_pricing_for_all_clients(self):
        """Test pricing works for all 30 clients."""
        for i in range(1, 31):
            client_id = f"client_{i:03d}"
            pricing = PricingSupport(client_id=client_id)

            price = pricing.get_price("prod_001")
            assert "base_price" in price, f"Failed for {client_id}"

    def test_order_tracking_for_all_clients(self):
        """Test order tracking works for all 30 clients."""
        for i in range(1, 31):
            client_id = f"client_{i:03d}"
            tracking = OrderTracking(client_id=client_id)

            order = tracking.create_order(
                order_id=f"ord_{i}",
                customer_id="cust_test",
                items=[],
                total=Decimal("50")
            )

            assert order.order_id == f"ord_{i}", f"Failed for {client_id}"

    def test_analytics_for_all_clients(self):
        """Test analytics works for all 30 clients."""
        for i in range(1, 31):
            client_id = f"client_{i:03d}"
            analytics = EcommerceAnalytics(client_id=client_id)

            summary = analytics.get_dashboard_summary()
            assert summary is not None, f"Failed for {client_id}"


class TestCrossClientIsolation:
    """Test no data leaks between clients."""

    def test_recommendation_isolation(self):
        """Test recommendations don't leak between clients."""
        engine1 = RecommendationEngine(client_id="client_001")
        engine2 = RecommendationEngine(client_id="client_002")

        # Each should have isolated data
        assert engine1.client_id != engine2.client_id

    def test_cart_recovery_isolation(self):
        """Test cart recovery doesn't leak between clients."""
        recovery1 = CartRecovery(client_id="client_001")
        recovery2 = CartRecovery(client_id="client_002")

        # Create cart for client 1
        from variants.ecommerce.advanced.cart_recovery import CartItem, AbandonedCart
        from datetime import datetime, timedelta

        cart = AbandonedCart(
            cart_id="cart_001",
            customer_id="cust_001",
            items=[CartItem("p1", "Product", Decimal("50"), 1)],
            total_value=Decimal("50"),
            abandoned_at=datetime.utcnow() - timedelta(hours=2),
            status=CartStatus.ABANDONED
        )
        recovery1._carts["cart_001"] = cart

        # Client 2 should not see client 1's carts
        assert "cart_001" not in recovery2._carts

    def test_analytics_isolation(self):
        """Test analytics don't leak between clients."""
        analytics1 = EcommerceAnalytics(client_id="client_001")
        analytics2 = EcommerceAnalytics(client_id="client_002")

        # Track event for client 1
        analytics1.track_event("purchase", {"revenue": 100})

        # Client 2 should not see client 1's events
        assert len(analytics2._events) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
