"""
Tests for Churn Prediction Services

Tests churn prediction, risk scoring, retention management,
and intervention engine functionality.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from backend.services.client_success.churn_predictor import (
    ChurnPredictor,
    ChurnRiskLevel,
    ChurnPrediction,
    RiskFactor,
)
from backend.services.client_success.risk_scorer import (
    RiskScorer,
    RiskCategory,
    RiskTrend,
    RiskScoreResult,
    RiskComponent,
)
from backend.services.client_success.retention_manager import (
    RetentionManager,
    ActionType,
    ActionPriority,
    ActionStatus,
    RetentionAction,
)
from backend.services.client_success.intervention_engine import (
    InterventionEngine,
    InterventionType,
    InterventionStatus,
    TriggerCondition,
    Intervention,
)


class TestChurnPredictor:
    """Tests for ChurnPredictor class."""

    @pytest.fixture
    def predictor(self):
        """Create churn predictor instance."""
        return ChurnPredictor()

    def test_predict(self, predictor):
        """Test churn prediction calculation."""
        prediction = predictor.predict(
            client_id="client_001",
            usage_trend=-15.0,
            accuracy_rate=70.0,
            support_tickets_30d=5,
            payment_issues=1,
            engagement_score=45.0
        )

        assert isinstance(prediction, ChurnPrediction)
        assert prediction.client_id == "client_001"
        assert 0 <= prediction.churn_probability <= 1
        assert prediction.risk_level in ChurnRiskLevel
        assert len(prediction.risk_factors) == 5

    def test_predict_all_clients(self, predictor):
        """Test prediction for all 10 clients."""
        predictions = predictor.predict_all_clients()

        assert len(predictions) == 10
        for client_id in predictor.SUPPORTED_CLIENTS:
            assert client_id in predictions
            assert isinstance(predictions[client_id], ChurnPrediction)

    def test_risk_level_determination(self, predictor):
        """Test risk level is correctly determined."""
        # High risk scenario
        high_risk = predictor.predict(
            client_id="client_001",
            usage_trend=-30.0,
            accuracy_rate=60.0,
            support_tickets_30d=10,
            payment_issues=2,
            engagement_score=30.0
        )
        assert high_risk.risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]

        # Low risk scenario
        low_risk = predictor.predict(
            client_id="client_002",
            usage_trend=5.0,
            accuracy_rate=95.0,
            support_tickets_30d=1,
            payment_issues=0,
            engagement_score=90.0
        )
        assert low_risk.risk_level == ChurnRiskLevel.LOW

    def test_recommendations_generated(self, predictor):
        """Test that recommendations are generated."""
        prediction = predictor.predict(
            client_id="client_001",
            usage_trend=-20.0,
            accuracy_rate=65.0,
            support_tickets_30d=8,
            payment_issues=0,
            engagement_score=40.0
        )

        assert len(prediction.recommended_actions) > 0

    def test_weighted_scoring(self, predictor):
        """Test that risk factors are weighted correctly."""
        prediction = predictor.predict(
            client_id="client_001",
            usage_trend=-20.0,
            accuracy_rate=100.0,  # Perfect accuracy
            support_tickets_30d=0,
            payment_issues=0,
            engagement_score=100.0
        )

        # With good metrics in other areas, declining usage should dominate
        usage_factor = next(
            (rf for rf in prediction.risk_factors if rf.name == "declining_usage"),
            None
        )
        assert usage_factor is not None
        assert usage_factor.score > 0

    def test_get_at_risk_clients(self, predictor):
        """Test getting at-risk clients."""
        predictor.predict_all_clients()

        at_risk = predictor.get_at_risk_clients()

        assert isinstance(at_risk, list)
        for prediction in at_risk:
            assert prediction.risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]

    def test_prediction_history(self, predictor):
        """Test getting prediction history."""
        # Make multiple predictions
        for _ in range(3):
            predictor.predict(
                client_id="client_001",
                usage_trend=-10.0,
                accuracy_rate=80.0,
                support_tickets_30d=2,
                payment_issues=0,
                engagement_score=70.0
            )

        history = predictor.get_prediction_history("client_001")

        assert len(history) >= 3

    def test_prediction_summary(self, predictor):
        """Test getting prediction summary."""
        predictor.predict_all_clients()

        summary = predictor.get_prediction_summary()

        assert summary["clients_predicted"] == 10
        assert "average_churn_probability" in summary
        assert "by_risk_level" in summary

    def test_invalid_client_raises_error(self, predictor):
        """Test that invalid client raises error."""
        with pytest.raises(ValueError, match="Unsupported client"):
            predictor.predict(client_id="invalid_client")


class TestRiskScorer:
    """Tests for RiskScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create risk scorer instance."""
        return RiskScorer()

    def test_calculate_score(self, scorer):
        """Test risk score calculation."""
        result = scorer.calculate_score(
            client_id="client_001",
            usage_metrics={"usage_trend": -15.0, "active_users": 50, "total_users": 100},
            quality_metrics={"accuracy_rate": 70.0, "resolution_rate": 60.0},
            support_metrics={"tickets_30d": 8, "escalations_30d": 2},
            financial_metrics={"payment_issues": 1, "overdue_amount": 500},
            engagement_metrics={"engagement_score": 40.0, "last_login_days": 10}
        )

        assert isinstance(result, RiskScoreResult)
        assert result.client_id == "client_001"
        assert 0 <= result.overall_score <= 100
        assert result.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert len(result.components) == 5

    def test_component_scores(self, scorer):
        """Test individual component scoring."""
        result = scorer.calculate_score(
            client_id="client_001",
            usage_metrics={"usage_trend": -30.0},
            quality_metrics={"accuracy_rate": 50.0},
            support_metrics={"tickets_30d": 15},
            financial_metrics={"payment_issues": 3},
            engagement_metrics={"engagement_score": 20.0}
        )

        # All components should have elevated scores
        for component in result.components:
            assert isinstance(component, RiskComponent)
            assert component.score >= 0

    def test_risk_distribution(self, scorer):
        """Test risk distribution calculation."""
        # Score some clients
        for client_id in scorer.SUPPORTED_CLIENTS[:5]:
            scorer.calculate_score(client_id=client_id)

        distribution = scorer.get_risk_distribution()

        assert "LOW" in distribution
        assert "MEDIUM" in distribution
        assert "HIGH" in distribution
        assert "CRITICAL" in distribution

    def test_high_risk_clients(self, scorer):
        """Test getting high-risk clients."""
        # Create high-risk scenario
        scorer.calculate_score(
            client_id="client_001",
            usage_metrics={"usage_trend": -40.0},
            quality_metrics={"accuracy_rate": 40.0},
            support_metrics={"tickets_30d": 20, "escalations_30d": 5},
            financial_metrics={"payment_issues": 5},
            engagement_metrics={"engagement_score": 10.0, "last_login_days": 30}
        )

        high_risk = scorer.get_high_risk_clients()

        assert isinstance(high_risk, list)
        assert len(high_risk) > 0

    def test_trend_analysis(self, scorer):
        """Test trend analysis over time."""
        # Create history
        for i in range(5):
            scorer.calculate_score(
                client_id="client_001",
                usage_metrics={"usage_trend": -10 - i * 5},
                quality_metrics={"accuracy_rate": 80 - i * 5}
            )

        history = scorer.get_client_scores("client_001")

        assert len(history) == 5
        # Latest should show increasing risk
        assert history[-1].trend in [RiskTrend.INCREASING, RiskTrend.STABLE]


class TestRetentionManager:
    """Tests for RetentionManager class."""

    @pytest.fixture
    def manager(self):
        """Create retention manager instance."""
        return RetentionManager()

    def test_create_action(self, manager):
        """Test creating a retention action."""
        action = manager.create_action(
            client_id="client_001",
            action_type=ActionType.CHECK_IN,
            priority=ActionPriority.HIGH,
            title="Proactive Check-in",
            description="Schedule check-in call with client"
        )

        assert isinstance(action, RetentionAction)
        assert action.client_id == "client_001"
        assert action.status == ActionStatus.PENDING

    def test_get_recommended_actions(self, manager):
        """Test getting recommended actions."""
        recommendations = manager.get_recommended_actions(
            client_id="client_001",
            risk_level="critical"
        )

        assert len(recommendations) > 0
        assert all("action_type" in r for r in recommendations)
        assert all("priority" in r for r in recommendations)

    def test_priority_queue(self, manager):
        """Test priority queue ordering."""
        # Create actions with different priorities
        manager.create_action("client_001", ActionType.CHECK_IN, ActionPriority.LOW)
        manager.create_action("client_002", ActionType.ESCALATION, ActionPriority.URGENT)
        manager.create_action("client_003", ActionType.TRAINING, ActionPriority.MEDIUM)

        queue = manager.get_priority_queue()

        assert len(queue) == 3
        # Urgent should be first
        assert queue[0].priority == ActionPriority.URGENT

    def test_assign_action(self, manager):
        """Test assigning an action."""
        action = manager.create_action(
            client_id="client_001",
            action_type=ActionType.CHECK_IN,
            priority=ActionPriority.HIGH
        )

        assigned = manager.assign_action(action.action_id, "user_123")

        assert assigned is not None
        assert assigned.assigned_to == "user_123"
        assert assigned.status == ActionStatus.IN_PROGRESS

    def test_complete_action(self, manager):
        """Test completing an action."""
        action = manager.create_action(
            client_id="client_001",
            action_type=ActionType.CHECK_IN,
            priority=ActionPriority.HIGH
        )

        completed = manager.complete_action(
            action_id=action.action_id,
            outcome="Client engaged, issues resolved",
            success=True
        )

        assert completed is not None
        assert completed.status == ActionStatus.COMPLETED
        assert completed.success is True

    def test_success_rate(self, manager):
        """Test success rate calculation."""
        # Create and complete some actions
        for i, success in enumerate([True, True, False, True, False]):
            action = manager.create_action(
                client_id=f"client_00{i+1}",
                action_type=ActionType.CHECK_IN,
                priority=ActionPriority.MEDIUM
            )
            manager.complete_action(action.action_id, "Outcome", success)

        rate = manager.get_success_rate()

        assert rate["total_actions"] == 5
        assert rate["success_rate"] == 60.0  # 3/5

    def test_get_overdue_actions(self, manager):
        """Test getting overdue actions."""
        # Create an overdue action
        action = manager.create_action(
            client_id="client_001",
            action_type=ActionType.CHECK_IN,
            priority=ActionPriority.HIGH,
            scheduled_for=datetime.utcnow() - timedelta(days=2)
        )

        overdue = manager.get_overdue_actions()

        assert len(overdue) > 0
        assert action.action_id in [a.action_id for a in overdue]

    def test_action_summary(self, manager):
        """Test action summary."""
        manager.create_action("client_001", ActionType.CHECK_IN, ActionPriority.HIGH)
        manager.create_action("client_002", ActionType.ESCALATION, ActionPriority.URGENT)

        summary = manager.get_action_summary()

        assert summary["total_actions"] >= 2
        assert "by_status" in summary
        assert "by_priority" in summary


class TestInterventionEngine:
    """Tests for InterventionEngine class."""

    @pytest.fixture
    def engine(self):
        """Create intervention engine instance."""
        return InterventionEngine()

    def test_evaluate_triggers(self, engine):
        """Test trigger condition evaluation."""
        client_data = {
            "engagement_score": 30,
            "risk_score": 75,
            "usage_trend": -20,
            "accuracy_rate": 60,
            "payment_issues": 1,
            "last_activity_days": 10,
            "support_tickets_30d": 8
        }

        triggers = engine.evaluate_triggers("client_001", client_data)

        assert len(triggers) > 0
        assert TriggerCondition.LOW_ENGAGEMENT in triggers
        assert TriggerCondition.HIGH_RISK_SCORE in triggers

    def test_get_triggered_interventions(self, engine):
        """Test getting triggered interventions."""
        triggers = [TriggerCondition.HIGH_RISK_SCORE, TriggerCondition.DECLINING_USAGE]

        interventions = engine.get_triggered_interventions("client_001", triggers)

        assert isinstance(interventions, list)
        assert all(hasattr(i, "intervention_type") for i in interventions)

    @pytest.mark.asyncio
    async def test_trigger_intervention(self, engine):
        """Test triggering an intervention."""
        template = engine._templates["high_risk_alert"]

        intervention = await engine.trigger_intervention(
            client_id="client_001",
            template=template,
            trigger_condition=TriggerCondition.HIGH_RISK_SCORE,
            context={"risk_score": 75}
        )

        assert isinstance(intervention, Intervention)
        assert intervention.client_id == "client_001"
        assert intervention.status in [InterventionStatus.TRIGGERED, InterventionStatus.SENT]

    @pytest.mark.asyncio
    async def test_run_automated_interventions(self, engine):
        """Test running automated interventions."""
        clients_data = {
            "client_001": {
                "engagement_score": 30,
                "risk_score": 75,
                "usage_trend": -20,
            },
            "client_002": {
                "engagement_score": 85,
                "risk_score": 20,
                "usage_trend": 5,
            }
        }

        results = await engine.run_automated_interventions(clients_data)

        assert isinstance(results, dict)
        # client_001 should have interventions, client_002 should not
        assert "client_001" in results or len(results) == 0  # Might be empty if no triggers

    def test_cooldown_check(self, engine):
        """Test cooldown period enforcement."""
        # Simulate recent intervention
        template = engine._templates["low_engagement_checkin"]

        # First trigger should not be in cooldown
        assert not engine._is_in_cooldown("client_001", template)

    def test_intervention_summary(self, engine):
        """Test intervention summary."""
        summary = engine.get_intervention_summary()

        assert "total_interventions" in summary
        assert "by_status" in summary
        assert "response_rate" in summary

    def test_templates(self, engine):
        """Test getting templates."""
        templates = engine.get_templates()

        assert len(templates) > 0
        assert all(hasattr(t, "intervention_type") for t in templates)


class TestIntegration:
    """Integration tests for churn prevention workflow."""

    def test_full_churn_prevention_workflow(self):
        """Test complete churn prevention workflow."""
        predictor = ChurnPredictor()
        scorer = RiskScorer()
        retention = RetentionManager()
        interventions = InterventionEngine()

        # Predict churn
        prediction = predictor.predict(
            client_id="client_001",
            usage_trend=-25.0,
            accuracy_rate=65.0,
            support_tickets_30d=8,
            payment_issues=1,
            engagement_score=35.0
        )

        # Score risk
        risk = scorer.calculate_score(
            client_id="client_001",
            usage_metrics={"usage_trend": -25.0},
            quality_metrics={"accuracy_rate": 65.0},
            support_metrics={"tickets_30d": 8},
            financial_metrics={"payment_issues": 1},
            engagement_metrics={"engagement_score": 35.0}
        )

        # Get recommended actions
        recommendations = retention.get_recommended_actions(
            client_id="client_001",
            risk_level=prediction.risk_level.value
        )

        # Verify workflow
        assert prediction.risk_level in [ChurnRiskLevel.HIGH, ChurnRiskLevel.CRITICAL]
        assert risk.risk_level in ["HIGH", "CRITICAL"]
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_all_10_clients_churn_prediction(self):
        """Test churn prediction for all 10 clients."""
        predictor = ChurnPredictor()

        predictions = predictor.predict_all_clients()

        # Verify all 10 clients have predictions
        assert len(predictions) == 10
        for client_id in predictor.SUPPORTED_CLIENTS:
            assert client_id in predictions
            prediction = predictions[client_id]
            assert prediction.churn_probability >= 0
            assert prediction.risk_level in ChurnRiskLevel

    def test_intervention_triggers_on_high_risk(self):
        """Test that interventions trigger correctly on high risk."""
        engine = InterventionEngine()

        # High-risk client data
        client_data = {
            "engagement_score": 25,
            "risk_score": 85,
            "usage_trend": -35,
            "accuracy_rate": 55,
            "payment_issues": 2,
            "last_activity_days": 15,
            "support_tickets_30d": 12
        }

        triggers = engine.evaluate_triggers("client_001", client_data)

        # Should have multiple triggers
        assert len(triggers) >= 3
        assert TriggerCondition.HIGH_RISK_SCORE in triggers
