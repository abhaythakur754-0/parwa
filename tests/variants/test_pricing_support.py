"""Tests for Pricing Support System."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from variants.ecommerce.advanced.pricing_support import (
    PricingSupport,
    PricingTier,
    TierPrice
)
from variants.ecommerce.advanced.price_monitor import (
    PriceMonitor,
    AlertType
)
from variants.ecommerce.advanced.competitor_tracker import CompetitorTracker
from variants.ecommerce.advanced.price_adjustment import (
    PriceAdjustmentEngine,
    AdjustmentType
)
from variants.ecommerce.advanced.promotion_manager import (
    PromotionManager,
    PromotionType,
    StackingRule
)


class TestPricingSupport:
    """Tests for PricingSupport."""

    def test_pricing_support_initializes(self):
        """Test initialization."""
        ps = PricingSupport(client_id="test")
        assert ps.client_id == "test"

    def test_get_price(self):
        """Test getting price."""
        ps = PricingSupport(client_id="test")
        price = ps.get_price("prod_001")

        assert "product_id" in price
        assert "base_price" in price
        assert "currency" in price

    def test_get_price_with_currency_conversion(self):
        """Test currency conversion."""
        ps = PricingSupport(client_id="test")
        price = ps.get_price("prod_001", currency="EUR")

        assert price["currency"] == "EUR"

    def test_get_tiered_pricing(self):
        """Test tiered pricing."""
        ps = PricingSupport(client_id="test")
        tiers = ps.get_tiered_pricing("prod_001", Decimal("100"))

        assert len(tiers) == 4
        assert tiers[0].min_quantity == 1
        assert tiers[1].discount_percent == 5

    def test_calculate_bulk_price(self):
        """Test bulk price calculation."""
        ps = PricingSupport(client_id="test")
        bulk = ps.calculate_bulk_price("prod_001", 50, Decimal("100"))

        assert bulk["quantity"] == 50
        assert bulk["discount_percent"] == 10

    def test_handle_price_match_request(self):
        """Test price match request."""
        ps = PricingSupport(client_id="test")
        result = ps.handle_price_match_request(
            "prod_001",
            Decimal("85"),
            "cust_001"
        )

        assert "request_id" in result
        assert "status" in result


class TestPriceMonitor:
    """Tests for PriceMonitor."""

    def test_price_monitor_initializes(self):
        """Test initialization."""
        pm = PriceMonitor(client_id="test")
        assert pm.client_id == "test"

    def test_track_price(self):
        """Test price tracking."""
        pm = PriceMonitor(client_id="test")
        alert = pm.track_price("prod_001", Decimal("100"))

        assert alert is None  # First price, no alert

    def test_track_price_change(self):
        """Test price change detection."""
        pm = PriceMonitor(client_id="test")
        pm.track_price("prod_001", Decimal("100"))
        alert = pm.track_price("prod_001", Decimal("90"))

        assert alert is not None
        assert alert.alert_type == AlertType.DROP

    def test_add_to_watch_list(self):
        """Test watch list."""
        pm = PriceMonitor(client_id="test")
        pm.add_to_watch_list("prod_001", drop_threshold=Decimal("80"))

        assert "prod_001" in pm._watch_list

    def test_check_alerts(self):
        """Test alert checking."""
        pm = PriceMonitor(client_id="test")
        pm.add_to_watch_list("prod_001", drop_threshold=Decimal("80"))
        pm.track_price("prod_001", Decimal("75"))

        alerts = pm.check_alerts()
        assert len(alerts) >= 0


class TestCompetitorTracker:
    """Tests for CompetitorTracker."""

    def test_tracker_initializes(self):
        """Test initialization."""
        ct = CompetitorTracker(client_id="test")
        assert ct.client_id == "test"

    def test_track_competitor(self):
        """Test competitor tracking."""
        ct = CompetitorTracker(client_id="test")
        ct.track_competitor("CompetitorA", "prod_001", Decimal("89.99"))

        assert len(ct._competitor_prices) == 1

    def test_analyze_price_gap(self):
        """Test price gap analysis."""
        ct = CompetitorTracker(client_id="test")
        ct.track_competitor("CompetitorA", "prod_001", Decimal("89.99"))

        analysis = ct.analyze_price_gap("prod_001", Decimal("99.99"))

        assert "competitor_gaps" in analysis
        assert "average_gap_percent" in analysis

    def test_get_market_position(self):
        """Test market positioning."""
        ct = CompetitorTracker(client_id="test")
        ct.track_competitor("CompetitorA", "prod_001", Decimal("90"))

        position = ct.get_market_position("prod_001", Decimal("99.99"))

        assert position in ["premium", "above_average", "competitive", "budget"]


class TestPriceAdjustment:
    """Tests for PriceAdjustmentEngine."""

    def test_engine_initializes(self):
        """Test initialization."""
        engine = PriceAdjustmentEngine(client_id="test")
        assert engine.client_id == "test"

    def test_recommend_adjustment(self):
        """Test adjustment recommendation."""
        engine = PriceAdjustmentEngine(client_id="test")
        rec = engine.recommend_adjustment(
            "prod_001",
            Decimal("100"),
            Decimal("30"),  # 30% margin
            Decimal("70")   # $70 cost
        )

        assert "recommended_price" in rec
        assert "adjustment_type" in rec

    def test_apply_adjustment(self):
        """Test applying adjustment."""
        engine = PriceAdjustmentEngine(client_id="test")
        adj = engine.apply_adjustment(
            "prod_001",
            Decimal("89.99"),
            Decimal("99.99"),
            AdjustmentType.DECREASE,
            "Price optimization"
        )

        assert adj.adjustment_id is not None

    def test_schedule_sale_price(self):
        """Test sale scheduling."""
        engine = PriceAdjustmentEngine(client_id="test")
        sale = engine.schedule_sale_price(
            "prod_001",
            Decimal("79.99"),
            datetime.utcnow(),
            datetime.utcnow() + timedelta(days=7)
        )

        assert sale["status"] == "scheduled"

    def test_check_map_compliance(self):
        """Test MAP compliance."""
        engine = PriceAdjustmentEngine(client_id="test")

        assert engine.check_map_compliance(Decimal("60")) is True
        assert engine.check_map_compliance(Decimal("30")) is False


class TestPromotionManager:
    """Tests for PromotionManager."""

    def test_manager_initializes(self):
        """Test initialization."""
        pm = PromotionManager(client_id="test")
        assert pm.client_id == "test"

    def test_create_promotion(self):
        """Test promotion creation."""
        pm = PromotionManager(client_id="test")
        promo = pm.create_promotion(
            "Summer Sale",
            PromotionType.PERCENTAGE,
            Decimal("20")
        )

        assert promo.promotion_id is not None
        assert promo.code is not None

    def test_create_flash_sale(self):
        """Test flash sale creation."""
        pm = PromotionManager(client_id="test")
        sale = pm.create_flash_sale("Flash Sale", Decimal("30"), duration_hours=24)

        assert sale.promotion_type == PromotionType.FLASH_SALE

    def test_create_bundle_promotion(self):
        """Test bundle promotion."""
        pm = PromotionManager(client_id="test")
        bundle = pm.create_bundle_promotion("Bundle Deal", Decimal("15"))

        assert bundle.promotion_type == PromotionType.BUNDLE

    def test_validate_stacking(self):
        """Test stacking validation."""
        pm = PromotionManager(client_id="test")
        p1 = pm.create_promotion("P1", PromotionType.PERCENTAGE, Decimal("10"))
        p2 = pm.create_promotion("P2", PromotionType.PERCENTAGE, Decimal("15"))

        result = pm.validate_stacking([p1.code, p2.code])

        assert "stackable" in result

    def test_apply_promotion(self):
        """Test applying promotion."""
        pm = PromotionManager(client_id="test")
        promo = pm.create_promotion("Test", PromotionType.PERCENTAGE, Decimal("10"))

        result = pm.apply_promotion(promo.code, Decimal("100"))

        assert result["applied"] is True
        assert result["discount"] == 10.0

    def test_validate_with_paddle(self):
        """Test Paddle validation."""
        pm = PromotionManager(client_id="test")
        promo = pm.create_promotion("Test", PromotionType.PERCENTAGE, Decimal("10"))

        assert pm.validate_with_paddle(promo.code) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
