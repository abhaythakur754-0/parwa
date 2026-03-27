"""
Tests for Subscription Lifecycle Management (Week 32, Builder 1).

Tests cover:
- SubscriptionManager: subscription tracking, renewals, Paddle integration
- PlanManager: plan comparison, pricing, recommendations
- UpgradeDowngradeHandler: proration, data preservation, feature updates
- TrialHandler: trial periods, expiration alerts, conversions
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from variants.saas.advanced.subscription_manager import (
    SubscriptionManager,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    BillingCycle,
)
from variants.saas.advanced.plan_manager import (
    PlanManager,
    PlanTier,
    BillingFrequency,
)
from variants.saas.advanced.upgrade_downgrade import (
    UpgradeDowngradeHandler,
    ChangeType,
    ChangeTiming,
)
from variants.saas.advanced.trial_handler import (
    TrialHandler,
    TrialStatus,
    DEFAULT_TRIAL_DAYS,
)


# =============================================================================
# SubscriptionManager Tests
# =============================================================================

class TestSubscriptionManager:
    """Tests for SubscriptionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a subscription manager instance."""
        return SubscriptionManager(client_id="test_client_001", company_id=uuid4())

    @pytest.mark.asyncio
    async def test_manager_initializes(self, manager):
        """Test that SubscriptionManager initializes correctly."""
        assert manager.client_id == "test_client_001"
        assert manager.company_id is not None
        assert manager._subscriptions == {}

    @pytest.mark.asyncio
    async def test_create_subscription(self, manager):
        """Test creating a new subscription."""
        subscription = await manager.create_subscription(
            tier=SubscriptionTier.PARWA,
            billing_cycle=BillingCycle.MONTHLY,
        )

        assert subscription is not None
        assert subscription.client_id == "test_client_001"
        assert subscription.tier == SubscriptionTier.PARWA
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.billing_cycle == BillingCycle.MONTHLY

    @pytest.mark.asyncio
    async def test_create_subscription_with_trial(self, manager):
        """Test creating a subscription with trial period."""
        subscription = await manager.create_subscription(
            tier=SubscriptionTier.MINI,
            trial_days=14,
        )

        assert subscription.status == SubscriptionStatus.TRIALING
        assert subscription.trial_ends is not None
        assert subscription.trial_ends > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_get_subscription(self, manager):
        """Test retrieving a subscription."""
        # Create subscription first
        created = await manager.create_subscription(tier=SubscriptionTier.MINI)

        # Get subscription
        retrieved = await manager.get_subscription()

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_update_status(self, manager):
        """Test updating subscription status."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.PARWA)

        updated = await manager.update_status(
            subscription,
            SubscriptionStatus.PAST_DUE,
            reason="Payment failed"
        )

        assert updated.status == SubscriptionStatus.PAST_DUE
        assert updated.grace_period_ends is not None

    @pytest.mark.asyncio
    async def test_pause_subscription(self, manager):
        """Test pausing a subscription."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.PARWA)

        paused = await manager.pause_subscription(subscription, reason="User request")

        assert paused.status == SubscriptionStatus.PAUSED
        assert paused.paused_at is not None

    @pytest.mark.asyncio
    async def test_resume_subscription(self, manager):
        """Test resuming a paused subscription."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.PARWA)
        await manager.pause_subscription(subscription)

        resumed = await manager.resume_subscription(subscription)

        assert resumed.status == SubscriptionStatus.ACTIVE
        assert resumed.paused_at is None

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediate(self, manager):
        """Test immediate cancellation."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.MINI)

        canceled = await manager.cancel_subscription(
            subscription,
            immediate=True,
            reason="User request"
        )

        assert canceled.status == SubscriptionStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(self, manager):
        """Test cancellation at period end."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.MINI)

        canceled = await manager.cancel_subscription(
            subscription,
            immediate=False,
            reason="User request"
        )

        assert canceled.cancel_at_period_end is True
        assert canceled.status == SubscriptionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_check_renewal_status(self, manager):
        """Test checking renewal status."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.PARWA)

        status = await manager.check_renewal_status(subscription)

        assert "days_until_renewal" in status
        assert "will_renew" in status
        assert status["will_renew"] is True

    @pytest.mark.asyncio
    async def test_get_subscription_metrics(self, manager):
        """Test getting subscription metrics."""
        await manager.create_subscription(tier=SubscriptionTier.MINI)
        await manager.create_subscription(
            tier=SubscriptionTier.PARWA,
            client_id="test_client_002"
        )

        metrics = await manager.get_subscription_metrics()

        assert metrics["total_subscriptions"] == 2
        assert "by_status" in metrics
        assert "by_tier" in metrics

    @pytest.mark.asyncio
    async def test_get_subscription_events(self, manager):
        """Test retrieving subscription events."""
        subscription = await manager.create_subscription(tier=SubscriptionTier.MINI)
        await manager.pause_subscription(subscription)

        events = await manager.get_subscription_events()

        assert len(events) >= 2  # Created and paused events

    @pytest.mark.asyncio
    async def test_process_paddle_webhook(self, manager):
        """Test processing Paddle webhook."""
        subscription = await manager.create_subscription(
            tier=SubscriptionTier.PARWA,
            paddle_subscription_id="paddle_sub_123"
        )

        result = await manager.process_paddle_webhook({
            "alert_type": "subscription_payment_failed",
            "subscription_id": "paddle_sub_123",
        })

        assert result["processed"] is True
        assert subscription.status == SubscriptionStatus.PAST_DUE


# =============================================================================
# PlanManager Tests
# =============================================================================

class TestPlanManager:
    """Tests for PlanManager class."""

    @pytest.fixture
    def manager(self):
        """Create a plan manager instance."""
        return PlanManager(client_id="test_client_001")

    def test_manager_initializes(self, manager):
        """Test that PlanManager initializes correctly."""
        assert manager.client_id == "test_client_001"

    def test_get_plan(self, manager):
        """Test getting a plan by tier."""
        plan = manager.get_plan(PlanTier.MINI)

        assert plan is not None
        assert plan.tier == PlanTier.MINI
        assert plan.monthly_price == 49.0

    def test_get_all_plans(self, manager):
        """Test getting all plans."""
        plans = manager.get_all_plans()

        assert len(plans) == 4
        tiers = [p.tier for p in plans]
        assert PlanTier.MINI in tiers
        assert PlanTier.PARWA in tiers
        assert PlanTier.PARWA_HIGH in tiers
        assert PlanTier.ENTERPRISE in tiers

    def test_compare_plans(self, manager):
        """Test comparing two plans."""
        comparison = manager.compare_plans(PlanTier.MINI, PlanTier.PARWA)

        assert comparison["plan1"]["tier"] == "mini"
        assert comparison["plan2"]["tier"] == "parwa"
        assert comparison["tier1_lower"] is True
        assert comparison["price_difference"]["monthly"] == 100.0  # 149 - 49

    def test_calculate_price_monthly(self, manager):
        """Test calculating monthly price."""
        pricing = manager.calculate_price(
            tier=PlanTier.PARWA,
            billing_frequency=BillingFrequency.MONTHLY,
            seats=10,
        )

        assert pricing["base_price"] == 149.0
        assert pricing["seats"] == 10
        assert pricing["total"] == 149.0

    def test_calculate_price_annual(self, manager):
        """Test calculating annual price."""
        pricing = manager.calculate_price(
            tier=PlanTier.PARWA,
            billing_frequency=BillingFrequency.ANNUAL,
        )

        assert pricing["base_price"] == 1430.0
        assert pricing["effective_monthly"] < 149.0  # Discount applied

    def test_calculate_price_with_discount(self, manager):
        """Test calculating price with discount code."""
        pricing = manager.calculate_price(
            tier=PlanTier.PARWA,
            billing_frequency=BillingFrequency.MONTHLY,
            discount_code="LAUNCH20",
        )

        assert pricing["discount_percent"] == 20
        assert pricing["discount_amount"] > 0
        assert pricing["total"] < pricing["subtotal"]

    def test_recommend_plan_basic(self, manager):
        """Test plan recommendation for basic usage."""
        recommendation = manager.recommend_plan({
            "current_tier": "mini",
            "monthly_tickets": 100,
            "voice_minutes": 30,
            "ai_interactions": 200,
            "concurrent_calls": 1,
            "team_size": 3,
        })

        assert "recommended_tier" in recommendation
        assert "scores" in recommendation
        assert "reasoning" in recommendation

    def test_recommend_plan_high_usage(self, manager):
        """Test plan recommendation for high usage."""
        recommendation = manager.recommend_plan({
            "current_tier": "parwa",
            "monthly_tickets": 5000,
            "voice_minutes": 1500,
            "ai_interactions": 20000,
            "concurrent_calls": 5,
            "needs_video": True,
            "team_size": 20,
        })

        assert recommendation["recommended_tier"] in ["parwa_high", "enterprise"]
        assert recommendation["upgrade_recommended"] is True

    def test_get_feature_matrix(self, manager):
        """Test getting feature matrix."""
        matrix = manager.get_feature_matrix()

        assert "features" in matrix
        assert "plans" in matrix
        assert len(matrix["plans"]) == 4

    def test_create_custom_plan(self, manager):
        """Test creating a custom plan."""
        custom = manager.create_custom_plan(
            base_tier=PlanTier.PARWA_HIGH,
            custom_features=[
                {"name": "Custom Reports", "included": True},
                {"name": "API Rate Limit Override", "included": True, "limit": 10000},
            ],
            custom_price=599.0,
        )

        assert custom["custom_plan"]["is_custom"] is True
        assert custom["custom_plan"]["monthly_price"] == 599.0


# =============================================================================
# UpgradeDowngradeHandler Tests
# =============================================================================

class TestUpgradeDowngradeHandler:
    """Tests for UpgradeDowngradeHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an upgrade/downgrade handler instance."""
        return UpgradeDowngradeHandler(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_handler_initializes(self, handler):
        """Test that handler initializes correctly."""
        assert handler.client_id == "test_client_001"
        assert handler._pending_changes == {}

    @pytest.mark.asyncio
    async def test_initiate_upgrade(self, handler):
        """Test initiating an upgrade."""
        change = await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
        )

        assert change.change_type == ChangeType.UPGRADE
        assert change.from_tier == "mini"
        assert change.to_tier == "parwa"

    @pytest.mark.asyncio
    async def test_initiate_downgrade(self, handler):
        """Test initiating a downgrade."""
        change = await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="parwa_high",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
        )

        assert change.change_type == ChangeType.DOWNGRADE

    @pytest.mark.asyncio
    async def test_calculate_proration(self, handler):
        """Test proration calculation."""
        proration = await handler.calculate_proration(
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
            days_remaining=15,
        )

        assert "proration_amount" in proration
        assert "charge_amount" in proration
        assert "credit_amount" in proration

    @pytest.mark.asyncio
    async def test_validate_upgrade(self, handler):
        """Test validating an upgrade."""
        validation = await handler.validate_change(
            from_tier="mini",
            to_tier="parwa",
            change_type=ChangeType.UPGRADE,
        )

        assert validation["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_downgrade_with_limitations(self, handler):
        """Test validating a downgrade with limitations."""
        validation = await handler.validate_change(
            from_tier="parwa_high",
            to_tier="mini",
            change_type=ChangeType.DOWNGRADE,
        )

        assert validation["valid"] is True
        assert len(validation["limitations"]) > 0  # Features will be lost

    @pytest.mark.asyncio
    async def test_apply_change_immediate(self, handler):
        """Test applying an immediate change."""
        change = await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
            timing=ChangeTiming.IMMEDIATE,
        )

        result = await handler.apply_change(change.id)

        assert result["applied"] is True
        assert result["timing"] == "immediate"

    @pytest.mark.asyncio
    async def test_apply_change_end_of_cycle(self, handler):
        """Test scheduling an end-of-cycle change."""
        change = await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="parwa",
            to_tier="mini",
            from_billing="monthly",
            to_billing="monthly",
            timing=ChangeTiming.END_OF_CYCLE,
        )

        result = await handler.apply_change(change.id)

        assert result["applied"] is False
        assert result["scheduled"] is True

    @pytest.mark.asyncio
    async def test_cancel_change(self, handler):
        """Test canceling a pending change."""
        change = await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
            timing=ChangeTiming.END_OF_CYCLE,
        )

        result = await handler.cancel_change(change.id, reason="User changed mind")

        assert result["canceled"] is True

    @pytest.mark.asyncio
    async def test_get_upgrade_incentives(self, handler):
        """Test getting upgrade incentives."""
        incentives = await handler.get_upgrade_incentives("mini", "parwa_high")

        assert incentives["available"] is True
        assert len(incentives["discounts"]) > 0
        assert incentives["trial_extension"] > 0

    @pytest.mark.asyncio
    async def test_get_pending_changes(self, handler):
        """Test getting pending changes."""
        await handler.initiate_change(
            subscription_id=uuid4(),
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
        )

        pending = await handler.get_pending_changes()

        assert len(pending) == 1


# =============================================================================
# TrialHandler Tests
# =============================================================================

class TestTrialHandler:
    """Tests for TrialHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a trial handler instance."""
        return TrialHandler(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_handler_initializes(self, handler):
        """Test that handler initializes correctly."""
        assert handler.client_id == "test_client_001"
        assert handler._trials == {}

    @pytest.mark.asyncio
    async def test_start_trial(self, handler):
        """Test starting a trial."""
        trial = await handler.start_trial(tier="parwa", days=14)

        assert trial is not None
        assert trial.client_id == "test_client_001"
        assert trial.tier == "parwa"
        assert trial.status == TrialStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_trial(self, handler):
        """Test retrieving a trial."""
        created = await handler.start_trial()
        retrieved = await handler.get_trial()

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_check_trial_status(self, handler):
        """Test checking trial status."""
        await handler.start_trial()

        status = await handler.check_trial_status()

        assert status["has_trial"] is True
        assert "days_remaining" in status
        assert status["is_expired"] is False

    @pytest.mark.asyncio
    async def test_extend_trial(self, handler):
        """Test extending a trial."""
        await handler.start_trial()

        result = await handler.extend_trial(days=7, reason="Customer request")

        assert result["extended"] is True
        assert result["days_extended"] == 7

    @pytest.mark.asyncio
    async def test_extend_trial_max_reached(self, handler):
        """Test extending trial when max is reached."""
        await handler.start_trial()
        await handler.extend_trial(days=7)

        result = await handler.extend_trial(days=5)

        assert result["extended"] is False

    @pytest.mark.asyncio
    async def test_convert_to_paid(self, handler):
        """Test converting trial to paid."""
        await handler.start_trial()

        result = await handler.convert_to_paid(
            tier="parwa",
            billing_frequency="monthly"
        )

        assert result["converted"] is True
        trial = await handler.get_trial()
        assert trial.status == TrialStatus.CONVERTED

    @pytest.mark.asyncio
    async def test_cancel_trial(self, handler):
        """Test canceling a trial."""
        await handler.start_trial()

        result = await handler.cancel_trial(reason="Not interested")

        assert result["canceled"] is True
        trial = await handler.get_trial()
        assert trial.status == TrialStatus.CANCELED

    @pytest.mark.asyncio
    async def test_track_feature_usage(self, handler):
        """Test tracking feature usage."""
        await handler.start_trial(tier="parwa")

        result = await handler.track_feature_usage("tickets", amount=5)

        assert result["tracked"] is True
        assert result["current_usage"] == 5

    @pytest.mark.asyncio
    async def test_check_feature_limit(self, handler):
        """Test checking feature limit."""
        await handler.start_trial(tier="mini")

        limit_status = await handler.check_feature_limit("tickets")

        assert "allowed" in limit_status
        assert "limit" in limit_status

    @pytest.mark.asyncio
    async def test_get_trial_analytics(self, handler):
        """Test getting trial analytics."""
        await handler.start_trial()
        await handler.track_feature_usage("tickets", amount=10)
        await handler.track_feature_usage("ai_interactions", amount=50)

        analytics = await handler.get_trial_analytics()

        assert analytics["has_trial"] is True
        assert "engagement" in analytics
        assert analytics["engagement"]["feature_adoption"] > 0

    @pytest.mark.asyncio
    async def test_get_conversion_suggestions(self, handler):
        """Test getting conversion suggestions."""
        await handler.start_trial()

        suggestions = await handler.get_conversion_suggestions()

        assert "suggestions" in suggestions
        assert "engagement_score" in suggestions


# =============================================================================
# Integration Tests
# =============================================================================

class TestSubscriptionLifecycleIntegration:
    """Integration tests for subscription lifecycle."""

    @pytest.mark.asyncio
    async def test_full_subscription_lifecycle(self):
        """Test complete subscription lifecycle from trial to paid."""
        client_id = "test_lifecycle_001"

        # Start with trial
        trial_handler = TrialHandler(client_id=client_id)
        trial = await trial_handler.start_trial(tier="parwa", days=14)

        assert trial.status == TrialStatus.ACTIVE

        # Track usage
        await trial_handler.track_feature_usage("tickets", amount=50)
        await trial_handler.track_feature_usage("ai_interactions", amount=200)

        # Get conversion suggestions
        suggestions = await trial_handler.get_conversion_suggestions()
        assert len(suggestions["suggestions"]) >= 0

        # Convert to paid
        conversion = await trial_handler.convert_to_paid(
            tier="parwa",
            billing_frequency="annual"
        )

        assert conversion["converted"] is True

        # Create subscription
        sub_manager = SubscriptionManager(client_id=client_id, company_id=uuid4())
        subscription = await sub_manager.create_subscription(
            tier=SubscriptionTier.PARWA,
            billing_cycle=BillingCycle.ANNUAL,
        )

        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.tier == SubscriptionTier.PARWA

    @pytest.mark.asyncio
    async def test_plan_change_workflow(self):
        """Test plan upgrade workflow."""
        client_id = "test_upgrade_001"

        # Create initial subscription
        sub_manager = SubscriptionManager(client_id=client_id, company_id=uuid4())
        subscription = await sub_manager.create_subscription(
            tier=SubscriptionTier.MINI,
            billing_cycle=BillingCycle.MONTHLY,
        )

        # Initiate upgrade
        upgrade_handler = UpgradeDowngradeHandler(client_id=client_id)
        change = await upgrade_handler.initiate_change(
            subscription_id=subscription.id,
            from_tier="mini",
            to_tier="parwa",
            from_billing="monthly",
            to_billing="monthly",
            timing=ChangeTiming.IMMEDIATE,
        )

        assert change.change_type == ChangeType.UPGRADE

        # Apply change
        result = await upgrade_handler.apply_change(change.id)
        assert result["applied"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
