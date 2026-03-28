"""
Integration Tests for SaaS Advanced Features (Week 32, Builder 5).

Tests full integration of SaaS Advanced components.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from variants.saas.advanced.subscription_manager import SubscriptionManager, SubscriptionTier
from variants.saas.advanced.plan_manager import PlanManager
from variants.saas.advanced.usage_meter import UsageMeter, UsageType
from variants.saas.advanced.billing_calculator import BillingCalculator
from variants.saas.advanced.churn_predictor import ChurnPredictor, CustomerFeatures
from variants.saas.advanced.health_score import HealthScoreCalculator
from variants.saas.advanced.saas_analytics import SaaSAnalytics


class TestSaaSAdvancedIntegration:
    """Integration tests for SaaS Advanced features."""

    @pytest.mark.asyncio
    async def test_full_subscription_lifecycle(self):
        """Test complete subscription lifecycle."""
        client_id = "test_full_lifecycle"
        company_id = uuid4()

        # Create subscription manager
        manager = SubscriptionManager(client_id=client_id, company_id=company_id)

        # Create subscription
        subscription = await manager.create_subscription(
            tier=SubscriptionTier.PARWA,
            trial_days=14
        )

        assert subscription.status.value == "trialing"
        assert subscription.tier == SubscriptionTier.PARWA

        # Track usage
        meter = UsageMeter(client_id=client_id, tier="parwa")
        await meter.track_api_call("/api/v1/tickets")
        await meter.track_ai_interaction("gpt-4", 500)

        usage = await meter.get_usage()
        assert usage["usage"]["api_calls"] == 1
        assert usage["usage"]["ai_interactions"] == 1

    @pytest.mark.asyncio
    async def test_billing_cycle(self):
        """Test complete billing cycle."""
        client_id = "test_billing_cycle"

        # Track usage
        meter = UsageMeter(client_id=client_id, tier="parwa_high")
        for _ in range(100):
            await meter.track(UsageType.API_CALLS, quantity=100)

        usage = await meter.get_usage()

        # Calculate billing
        calculator = BillingCalculator(client_id=client_id)
        pricing = await calculator.calculate_tiered_pricing(
            "api_calls",
            usage["usage"]["api_calls"]
        )

        assert pricing["total"] > 0

    @pytest.mark.asyncio
    async def test_churn_prediction_pipeline(self):
        """Test churn prediction pipeline."""
        client_id = "test_churn_pipeline"

        # Create customer features
        features = CustomerFeatures(
            client_id=client_id,
            days_since_signup=180,
            monthly_usage_trend=0.1,
            login_frequency_30d=20,
            feature_adoption_rate=0.7,
            support_tickets_30d=2,
            avg_ticket_sentiment=0.8,
            payment_failures_90d=0,
            nps_score=8,
        )

        # Predict churn
        predictor = ChurnPredictor()
        prediction = await predictor.predict(features)

        assert prediction.churn_probability >= 0
        assert prediction.churn_probability <= 1
        assert prediction.risk_level is not None

    @pytest.mark.asyncio
    async def test_health_score_integration(self):
        """Test health score calculation."""
        client_id = "test_health_integration"

        calculator = HealthScoreCalculator(client_id=client_id)

        health = await calculator.calculate_health_score(
            usage_data={
                "active_users": 8,
                "total_users": 10,
                "feature_utilization": 0.7,
                "usage_growth": 0.1,
            },
            engagement_data={
                "logins_30d": 25,
                "feature_adoption_rate": 0.6,
            },
            financial_data={
                "payment_failures_90d": 0,
                "overdue_days": 0,
            },
            support_data={
                "tickets_30d": 1,
                "avg_sentiment": 0.8,
            }
        )

        assert health.overall_score >= 0
        assert health.overall_score <= 100
        assert len(health.component_scores) == 4

    @pytest.mark.asyncio
    async def test_saas_analytics_integration(self):
        """Test SaaS analytics integration."""
        client_id = "test_analytics_integration"

        analytics = SaaSAnalytics(client_id=client_id)

        # Calculate MRR
        subscriptions = [
            {"status": "active", "amount": 499, "billing_cycle": "monthly"},
            {"status": "active", "amount": 1430, "billing_cycle": "annual"},
            {"status": "active", "amount": 149, "billing_cycle": "monthly"},
        ]

        metrics = await analytics.calculate_mrr(subscriptions)

        assert metrics.mrr > 0
        assert metrics.arr == metrics.mrr * 12

    @pytest.mark.asyncio
    async def test_plan_upgrade_flow(self):
        """Test plan upgrade flow."""
        client_id = "test_plan_upgrade"

        plan_manager = PlanManager(client_id=client_id)

        # Compare plans
        comparison = plan_manager.compare_plans("mini", "parwa")

        assert comparison["tier1_lower"] is True
        assert comparison["price_difference"]["monthly"] > 0

        # Get recommendation
        recommendation = plan_manager.recommend_plan({
            "current_tier": "mini",
            "monthly_tickets": 800,
            "voice_minutes": 200,
            "team_size": 5,
        })

        assert "recommended_tier" in recommendation


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_customer_journey_low_risk(self):
        """Test journey for low-risk customer."""
        client_id = "test_low_risk"

        # Step 1: Health check
        health_calc = HealthScoreCalculator(client_id=client_id)
        health = await health_calc.calculate_health_score(
            usage_data={"feature_utilization": 0.8, "usage_growth": 0.2},
            engagement_data={"logins_30d": 30, "feature_adoption_rate": 0.7},
            financial_data={"payment_failures_90d": 0},
            support_data={"tickets_30d": 0}
        )

        # Step 2: Churn prediction
        predictor = ChurnPredictor()
        features = CustomerFeatures(
            client_id=client_id,
            days_since_signup=365,
            monthly_usage_trend=0.2,
            login_frequency_30d=30,
            feature_adoption_rate=0.8,
            nps_score=9,
        )
        prediction = await predictor.predict(features)

        # Low-risk customers should have good health and low churn probability
        assert health.overall_score >= 70
        assert prediction.churn_probability < 0.3

    @pytest.mark.asyncio
    async def test_customer_journey_high_risk(self):
        """Test journey for high-risk customer."""
        client_id = "test_high_risk"

        # Step 1: Health check
        health_calc = HealthScoreCalculator(client_id=client_id)
        health = await health_calc.calculate_health_score(
            usage_data={"feature_utilization": 0.2, "usage_growth": -0.3},
            engagement_data={"logins_30d": 3, "feature_adoption_rate": 0.1},
            financial_data={"payment_failures_90d": 2, "overdue_days": 15},
            support_data={"tickets_30d": 8, "avg_sentiment": 0.3}
        )

        # Step 2: Churn prediction
        predictor = ChurnPredictor()
        features = CustomerFeatures(
            client_id=client_id,
            days_since_signup=30,
            monthly_usage_trend=-0.5,
            login_frequency_30d=2,
            feature_adoption_rate=0.1,
            support_tickets_30d=10,
            avg_ticket_sentiment=0.2,
            payment_failures_90d=2,
            nps_score=3,
        )
        prediction = await predictor.predict(features)

        # High-risk customers should have poor health and high churn probability
        assert health.overall_score < 60
        assert prediction.churn_probability > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
