"""
Tests for Churn Prediction & Retention (Week 32, Builder 3).

Tests cover:
- ChurnPredictor: prediction, features, signals
- RiskScorer: multi-factor scoring, decline detection
- RetentionCampaign: workflows, messages, offers
- WinBack: churned customers, reactivation
- HealthScore: components, trends, dashboard
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from variants.saas.advanced.churn_predictor import (
    ChurnPredictor,
    ChurnPrediction,
    CustomerFeatures,
    ChurnRisk,
    ChurnSignal,
)
from variants.saas.advanced.risk_scorer import (
    RiskScorer,
    RiskScore,
    RiskFactor,
)
from variants.saas.advanced.retention_campaign import (
    RetentionCampaignManager,
    RetentionCampaign,
    CampaignType,
    CampaignStatus,
    MessageChannel,
)
from variants.saas.advanced.win_back import (
    WinBackManager,
    WinBackCampaign,
    ChurnedCustomer,
    WinBackStatus,
    OfferType,
)
from variants.saas.advanced.health_score import (
    HealthScoreCalculator,
    HealthScore,
    HealthLevel,
    HealthComponent,
)


# =============================================================================
# ChurnPredictor Tests
# =============================================================================

class TestChurnPredictor:
    """Tests for ChurnPredictor class."""

    @pytest.fixture
    def predictor(self):
        """Create a churn predictor instance."""
        return ChurnPredictor()

    @pytest.fixture
    def sample_features(self):
        """Create sample customer features."""
        return CustomerFeatures(
            client_id="test_client_001",
            days_since_signup=180,
            monthly_usage_trend=0.1,
            login_frequency_30d=20,
            feature_adoption_rate=0.6,
            support_tickets_30d=2,
            avg_ticket_sentiment=0.7,
            payment_failures_90d=0,
            days_since_last_payment=15,
            subscription_changes_90d=0,
            nps_score=8,
            last_feature_used_days=2,
            team_member_count=5,
            active_team_members=4,
        )

    @pytest.mark.asyncio
    async def test_predictor_initializes(self, predictor):
        """Test that ChurnPredictor initializes correctly."""
        assert predictor.model_version == "1.0.0"
        assert predictor._predictions == {}

    @pytest.mark.asyncio
    async def test_predict_churn_low_risk(self, predictor, sample_features):
        """Test prediction for low-risk customer."""
        prediction = await predictor.predict(sample_features)

        assert prediction is not None
        assert prediction.churn_probability < 0.5
        assert prediction.risk_level == ChurnRisk.LOW

    @pytest.mark.asyncio
    async def test_predict_churn_high_risk(self, predictor):
        """Test prediction for high-risk customer."""
        features = CustomerFeatures(
            client_id="test_client_002",
            days_since_signup=30,
            monthly_usage_trend=-0.5,
            login_frequency_30d=2,
            feature_adoption_rate=0.1,
            support_tickets_30d=10,
            avg_ticket_sentiment=0.2,
            payment_failures_90d=2,
            days_since_last_payment=45,
            subscription_changes_90d=3,
            nps_score=2,
            last_feature_used_days=20,
        )

        prediction = await predictor.predict(features)

        assert prediction.churn_probability > 0.5
        assert prediction.risk_level in [ChurnRisk.HIGH, ChurnRisk.CRITICAL]

    @pytest.mark.asyncio
    async def test_extract_features(self, predictor):
        """Test feature extraction."""
        features = await predictor.extract_features(
            client_id="test_client_001",
            usage_data={"days_since_signup": 100, "monthly_usage_trend": 0.05},
            support_data={"tickets_30d": 3, "avg_sentiment": 0.8},
            payment_data={"failures_90d": 0, "days_since_last": 10},
            engagement_data={"logins_30d": 15, "nps_score": 9}
        )

        assert features.client_id == "test_client_001"
        assert features.days_since_signup == 100
        assert features.support_tickets_30d == 3

    @pytest.mark.asyncio
    async def test_identify_signals(self, predictor):
        """Test churn signal identification."""
        features = CustomerFeatures(
            client_id="test_client_003",
            monthly_usage_trend=-0.4,
            payment_failures_90d=1,
            login_frequency_30d=2,
            feature_adoption_rate=0.2,
            avg_ticket_sentiment=0.2,
            last_feature_used_days=20,
        )

        signals = await predictor._identify_signals(features)

        assert ChurnSignal.USAGE_DECLINE in signals
        assert ChurnSignal.ENGAGEMENT_DROP in signals

    @pytest.mark.asyncio
    async def test_get_at_risk_customers(self, predictor, sample_features):
        """Test getting at-risk customers."""
        await predictor.predict(sample_features)

        high_risk = await predictor.get_at_risk_customers(ChurnRisk.HIGH)
        medium_risk = await predictor.get_at_risk_customers(ChurnRisk.MEDIUM)

        assert len(medium_risk) >= len(high_risk)


# =============================================================================
# RiskScorer Tests
# =============================================================================

class TestRiskScorer:
    """Tests for RiskScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a risk scorer instance."""
        return RiskScorer(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_scorer_initializes(self, scorer):
        """Test that RiskScorer initializes correctly."""
        assert scorer.client_id == "test_client_001"

    @pytest.mark.asyncio
    async def test_calculate_score(self, scorer):
        """Test calculating comprehensive risk score."""
        score = await scorer.calculate_score(
            usage_data={"current_usage": 100, "previous_usage": 120, "last_usage_days": 0},
            engagement_data={"logins_7d": 5, "feature_adoption": 0.5},
            financial_data={"payment_failures_90d": 0, "overdue_days": 0},
            support_data={"tickets_30d": 1, "avg_sentiment": 0.8}
        )

        assert score is not None
        assert 0 <= score.overall_score <= 10
        assert len(score.factor_scores) == 4

    @pytest.mark.asyncio
    async def test_detect_usage_decline(self, scorer):
        """Test usage decline detection."""
        result = await scorer.detect_usage_decline(
            current_usage=70,
            previous_usage=100,
            threshold=0.20
        )

        assert result["decline_detected"] is True
        assert result["decline_percentage"] == 30.0

    @pytest.mark.asyncio
    async def test_track_login_frequency(self, scorer):
        """Test login frequency tracking."""
        result = await scorer.track_login_frequency(
            logins_7d=5,
            logins_30d=20
        )

        assert result["engagement_level"] in ["high", "moderate", "low", "inactive"]
        assert result["daily_average"] == pytest.approx(20/30, rel=0.1)

    @pytest.mark.asyncio
    async def test_score_feature_adoption(self, scorer):
        """Test feature adoption scoring."""
        result = await scorer.score_feature_adoption(
            available_features=10,
            used_features=7,
            feature_depth={"feature1": 15, "feature2": 5, "feature3": 1}
        )

        assert result["adoption_rate"] == 0.7
        assert result["level"] in ["high", "moderate", "low"]

    @pytest.mark.asyncio
    async def test_analyze_payment_failures(self, scorer):
        """Test payment failure analysis."""
        result = await scorer.analyze_payment_failures(
            failures_90d=2,
            last_failure_days=5,
            payment_method_age=180
        )

        assert result["risk_level"] == "high"
        assert "recurring_failures" in result["risk_factors"]


# =============================================================================
# RetentionCampaign Tests
# =============================================================================

class TestRetentionCampaign:
    """Tests for RetentionCampaign class."""

    @pytest.fixture
    def manager(self):
        """Create a retention campaign manager instance."""
        return RetentionCampaignManager(
            client_id="test_client_001",
            company_name="Test Company",
            email="test@example.com"
        )

    @pytest.mark.asyncio
    async def test_manager_initializes(self, manager):
        """Test that RetentionCampaignManager initializes correctly."""
        assert manager.client_id == "test_client_001"

    @pytest.mark.asyncio
    async def test_create_campaign(self, manager):
        """Test creating a campaign."""
        campaign = await manager.create_campaign(
            campaign_type=CampaignType.ENGAGEMENT
        )

        assert campaign is not None
        assert campaign.campaign_type == CampaignType.ENGAGEMENT
        assert campaign.status == CampaignStatus.DRAFT

    @pytest.mark.asyncio
    async def test_send_personalized_message(self, manager):
        """Test sending personalized message."""
        message = await manager.send_personalized_message(
            message_type="check_in",
            template_vars={"name": "Test", "product_name": "PARWA"},
            channel=MessageChannel.EMAIL
        )

        assert message is not None
        assert message.channel == MessageChannel.EMAIL
        assert message.sent_at is not None

    @pytest.mark.asyncio
    async def test_offer_discount(self, manager):
        """Test offering discount."""
        discount = await manager.offer_discount(
            discount_percent=20,
            validity_days=30,
            reason="retention"
        )

        assert discount["percent"] == 20
        assert discount["code"].startswith("RETAIN")

    @pytest.mark.asyncio
    async def test_assign_success_manager(self, manager):
        """Test assigning success manager."""
        result = await manager.assign_success_manager()

        assert result["assigned"] is True
        assert result["manager_id"] is not None


# =============================================================================
# WinBack Tests
# =============================================================================

class TestWinBack:
    """Tests for WinBack class."""

    @pytest.fixture
    def manager(self):
        """Create a win-back manager instance."""
        return WinBackManager()

    @pytest.mark.asyncio
    async def test_manager_initializes(self, manager):
        """Test that WinBackManager initializes correctly."""
        assert manager._churned_customers == {}
        assert manager._campaigns == {}

    @pytest.mark.asyncio
    async def test_identify_churned_customers(self, manager):
        """Test identifying churned customers."""
        # Add a churned customer
        customer = manager.add_churned_customer(
            client_id="churned_001",
            company_name="Churned Corp",
            email="churned@example.com",
            previous_tier="parwa",
            previous_mrr=149.0,
            churn_reason="too_expensive",
            tenure_days=180
        )

        customers = await manager.identify_churned_customers(days_since_churn=90)

        assert len(customers) >= 1

    @pytest.mark.asyncio
    async def test_create_win_back_campaign(self, manager):
        """Test creating win-back campaign."""
        customer = manager.add_churned_customer(
            client_id="churned_002",
            company_name="Test Corp",
            email="test@example.com",
            previous_tier="parwa",
            previous_mrr=149.0
        )

        campaign = await manager.create_win_back_campaign(customer)

        assert campaign is not None
        assert campaign.status == WinBackStatus.PENDING

    @pytest.mark.asyncio
    async def test_collect_feedback(self, manager):
        """Test collecting feedback."""
        customer = manager.add_churned_customer(
            client_id="churned_003",
            company_name="Test Corp",
            email="test@example.com",
            previous_tier="mini",
            previous_mrr=49.0
        )

        result = await manager.collect_feedback(
            churned_customer_id=customer.id,
            feedback_score=6,
            feedback_text="Product was too complex",
            competitor="Competitor A"
        )

        assert result["collected"] is True

    @pytest.mark.asyncio
    async def test_get_competitive_analysis(self, manager):
        """Test competitive analysis."""
        # Add customers with competitors
        for i, comp in enumerate(["CompA", "CompB", "CompA", None]):
            customer = manager.add_churned_customer(
                client_id=f"churned_{i}",
                company_name=f"Company {i}",
                email=f"company{i}@example.com",
                previous_tier="parwa",
                previous_mrr=149.0
            )
            if comp:
                await manager.collect_feedback(customer.id, 5, "Test", comp)

        analysis = await manager.get_competitive_analysis()

        assert "competitor_mentions" in analysis
        assert analysis["top_competitor"] == "CompA"


# =============================================================================
# HealthScore Tests
# =============================================================================

class TestHealthScore:
    """Tests for HealthScore class."""

    @pytest.fixture
    def calculator(self):
        """Create a health score calculator instance."""
        return HealthScoreCalculator(client_id="test_client_001")

    @pytest.mark.asyncio
    async def test_calculator_initializes(self, calculator):
        """Test that HealthScoreCalculator initializes correctly."""
        assert calculator.client_id == "test_client_001"

    @pytest.mark.asyncio
    async def test_calculate_health_score(self, calculator):
        """Test calculating health score."""
        score = await calculator.calculate_health_score(
            usage_data={
                "active_users": 8,
                "total_users": 10,
                "feature_utilization": 0.7,
                "usage_growth": 0.1,
                "api_calls_30d": 5000,
            },
            engagement_data={
                "logins_30d": 30,
                "feature_adoption_rate": 0.6,
                "avg_session_minutes": 12,
                "team_engagement_rate": 0.8,
            },
            financial_data={
                "payment_failures_90d": 0,
                "overdue_days": 0,
                "is_annual_contract": True,
                "downgrade_requests_90d": 0,
            },
            support_data={
                "tickets_30d": 1,
                "avg_resolution_hours": 2,
                "avg_sentiment": 0.8,
                "escalations_30d": 0,
            }
        )

        assert score is not None
        assert 0 <= score.overall_score <= 100
        assert score.health_level in [HealthLevel.EXCELLENT, HealthLevel.GOOD, HealthLevel.FAIR, HealthLevel.POOR, HealthLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_get_component_health(self, calculator):
        """Test getting component health."""
        await calculator.calculate_health_score(
            usage_data={"active_users": 5, "total_users": 10, "feature_utilization": 0.5},
            engagement_data={"logins_30d": 15, "feature_adoption_rate": 0.5},
            financial_data={"payment_failures_90d": 0},
            support_data={"tickets_30d": 2, "avg_sentiment": 0.7}
        )

        usage = await calculator.get_usage_health()
        engagement = await calculator.get_engagement_health()

        assert usage is not None
        assert engagement is not None

    @pytest.mark.asyncio
    async def test_get_health_dashboard(self, calculator):
        """Test getting health dashboard."""
        await calculator.calculate_health_score(
            usage_data={"feature_utilization": 0.5},
            engagement_data={"logins_30d": 15},
            financial_data={},
            support_data={}
        )

        dashboard = await calculator.get_health_dashboard()

        assert "current_score" in dashboard
        assert "trends" in dashboard

    @pytest.mark.asyncio
    async def test_analyze_trends(self, calculator):
        """Test trend analysis."""
        # Create multiple scores
        for _ in range(5):
            await calculator.calculate_health_score(
                usage_data={"feature_utilization": 0.5},
                engagement_data={"logins_30d": 15},
                financial_data={},
                support_data={}
            )

        trends = await calculator.analyze_trends(days=30)

        assert trends["analyzed"] is True
        assert trends["data_points"] >= 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestChurnRetentionIntegration:
    """Integration tests for churn prediction and retention."""

    @pytest.mark.asyncio
    async def test_full_retention_workflow(self):
        """Test complete retention workflow."""
        client_id = "test_retention_001"

        # Calculate health score
        health_calc = HealthScoreCalculator(client_id=client_id)
        health = await health_calc.calculate_health_score(
            usage_data={"feature_utilization": 0.3, "usage_growth": -0.2},
            engagement_data={"logins_30d": 3, "feature_adoption_rate": 0.2},
            financial_data={"payment_failures_90d": 0},
            support_data={"tickets_30d": 5, "avg_sentiment": 0.4}
        )

        # Predict churn
        predictor = ChurnPredictor()
        features = CustomerFeatures(
            client_id=client_id,
            monthly_usage_trend=-0.2,
            login_frequency_30d=3,
            feature_adoption_rate=0.2,
            support_tickets_30d=5,
            avg_ticket_sentiment=0.4,
        )
        prediction = await predictor.predict(features)

        # If at risk, trigger retention campaign
        if prediction.risk_level in [ChurnRisk.HIGH, ChurnRisk.CRITICAL]:
            manager = RetentionCampaignManager(
                client_id=client_id,
                company_name="Test Company",
                email="test@example.com"
            )
            campaign = await manager.create_campaign(CampaignType.ENGAGEMENT)

            assert campaign is not None
            assert campaign.campaign_type == CampaignType.ENGAGEMENT

        assert health.overall_score >= 0
        assert prediction.churn_probability >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
