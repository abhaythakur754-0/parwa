"""
Tests for Health Monitor Service

Tests health monitoring functionality including:
- Health monitoring for all 10 clients
- Health score calculation
- Trend detection
- Alert triggering
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.client_success.health_monitor import (
    HealthMonitor,
    HealthStatus,
    HealthMetric,
    ClientHealthSnapshot,
)
from backend.services.client_success.health_scorer import (
    HealthScorer,
    ScoreFactor,
    TrendDirection,
    HealthScoreResult,
)
from backend.services.client_success.alert_manager import (
    AlertManager,
    AlertSeverity,
    AlertType,
    HealthAlert,
)


class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    @pytest.fixture
    def monitor(self):
        """Create health monitor instance."""
        return HealthMonitor()

    @pytest.mark.asyncio
    async def test_monitor_all_clients(self, monitor):
        """Test monitoring all 10 clients."""
        snapshots = await monitor.monitor_all_clients()

        # Should have exactly 10 clients
        assert len(snapshots) == 10

        # All clients should have snapshots
        expected_clients = [
            "client_001", "client_002", "client_003", "client_004", "client_005",
            "client_006", "client_007", "client_008", "client_009", "client_010"
        ]
        for client_id in expected_clients:
            assert client_id in snapshots
            assert isinstance(snapshots[client_id], ClientHealthSnapshot)

    @pytest.mark.asyncio
    async def test_monitor_single_client(self, monitor):
        """Test monitoring a single client."""
        snapshot = await monitor.monitor_client("client_001")

        assert snapshot.client_id == "client_001"
        assert 0 <= snapshot.overall_health <= 100
        assert snapshot.status in HealthStatus
        assert isinstance(snapshot.timestamp, datetime)
        assert len(snapshot.metrics) > 0

    @pytest.mark.asyncio
    async def test_invalid_client_raises_error(self, monitor):
        """Test that invalid client raises error."""
        with pytest.raises(ValueError, match="Unsupported client"):
            await monitor.monitor_client("invalid_client")

    @pytest.mark.asyncio
    async def test_health_score_in_valid_range(self, monitor):
        """Test that health scores are in valid range."""
        snapshots = await monitor.monitor_all_clients()

        for client_id, snapshot in snapshots.items():
            assert 0 <= snapshot.overall_health <= 100, \
                f"{client_id} health score {snapshot.overall_health} out of range"
            assert 0 <= snapshot.activity_level <= 100
            assert 0 <= snapshot.accuracy_rate <= 100
            assert snapshot.avg_response_time >= 0
            assert 0 <= snapshot.resolution_rate <= 100
            assert 0 <= snapshot.engagement_score <= 100

    @pytest.mark.asyncio
    async def test_health_status_thresholds(self, monitor):
        """Test health status is correctly determined."""
        # Monitor clients
        await monitor.monitor_all_clients()

        # Check status is determined correctly
        for client_id, snapshot in monitor._snapshots.items():
            if snapshot.overall_health >= 90:
                assert snapshot.status == HealthStatus.EXCELLENT
            elif snapshot.overall_health >= 75:
                assert snapshot.status == HealthStatus.GOOD
            elif snapshot.overall_health >= 60:
                assert snapshot.status == HealthStatus.FAIR
            elif snapshot.overall_health >= 40:
                assert snapshot.status == HealthStatus.POOR
            else:
                assert snapshot.status == HealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_get_client_history(self, monitor):
        """Test getting client history."""
        # Monitor multiple times to create history
        for _ in range(3):
            await monitor.monitor_client("client_001")

        history = monitor.get_client_history("client_001", days=7)

        assert len(history) >= 1
        assert all(isinstance(s, ClientHealthSnapshot) for s in history)

    @pytest.mark.asyncio
    async def test_get_health_summary(self, monitor):
        """Test health summary generation."""
        await monitor.monitor_all_clients()

        summary = monitor.get_health_summary()

        assert summary["clients_monitored"] == 10
        assert "average_health" in summary
        assert "status_distribution" in summary
        assert 0 <= summary["average_health"] <= 100

    @pytest.mark.asyncio
    async def test_get_clients_by_status(self, monitor):
        """Test filtering clients by status."""
        await monitor.monitor_all_clients()

        for status in HealthStatus:
            clients = monitor.get_clients_by_status(status)
            assert isinstance(clients, list)
            # All returned clients should have the requested status
            for client_id in clients:
                snapshot = monitor.get_client_snapshot(client_id)
                assert snapshot.status == status


class TestHealthScorer:
    """Tests for HealthScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create health scorer instance."""
        return HealthScorer()

    def test_calculate_score(self, scorer):
        """Test health score calculation."""
        result = scorer.calculate_score(
            client_id="client_001",
            activity_level=80.0,
            accuracy=90.0,
            response_time=2.0,
            ticket_resolution=85.0,
            engagement=75.0
        )

        assert isinstance(result, HealthScoreResult)
        assert result.client_id == "client_001"
        assert 0 <= result.overall_score <= 100
        assert result.grade in ["A", "B", "C", "D", "F"]
        assert len(result.factor_scores) == 5

    def test_score_with_low_response_time(self, scorer):
        """Test that low response time boosts score."""
        # Low response time should give high score
        result_low = scorer.calculate_score(
            client_id="client_001",
            activity_level=80.0,
            accuracy=85.0,
            response_time=1.0,  # Fast response
            ticket_resolution=80.0,
            engagement=70.0
        )

        result_high = scorer.calculate_score(
            client_id="client_002",
            activity_level=80.0,
            accuracy=85.0,
            response_time=6.0,  # Slow response
            ticket_resolution=80.0,
            engagement=70.0
        )

        # Low response time should result in higher score
        assert result_low.overall_score > result_high.overall_score

    def test_weighted_scoring(self, scorer):
        """Test that weights are applied correctly."""
        result = scorer.calculate_score(
            client_id="client_001",
            activity_level=100.0,
            accuracy=100.0,
            response_time=0.0,
            ticket_resolution=100.0,
            engagement=100.0
        )

        # With all perfect scores, should get close to 100
        assert result.overall_score >= 95

    def test_grade_thresholds(self, scorer):
        """Test grade assignment based on score."""
        # Test A grade (90-100)
        result_a = scorer.calculate_score(
            client_id="client_001",
            activity_level=95.0,
            accuracy=95.0,
            response_time=1.0,
            ticket_resolution=95.0,
            engagement=95.0
        )
        # High scores should result in A or B grade
        assert result_a.grade in ["A", "B"]

    def test_recommendations_generated(self, scorer):
        """Test that recommendations are generated for low scores."""
        result = scorer.calculate_score(
            client_id="client_001",
            activity_level=50.0,  # Low activity
            accuracy=60.0,  # Low accuracy
            response_time=5.0,  # High response time
            ticket_resolution=50.0,  # Low resolution
            engagement=40.0  # Low engagement
        )

        # Should have recommendations
        assert len(result.recommendations) > 0

    def test_risk_flags_identified(self, scorer):
        """Test that risk flags are identified."""
        result = scorer.calculate_score(
            client_id="client_001",
            activity_level=30.0,  # Very low
            accuracy=60.0,  # Below threshold
            response_time=8.0,  # Very high
            ticket_resolution=50.0,
            engagement=30.0
        )

        # Should have risk flags
        assert len(result.risk_flags) > 0

    def test_trend_analysis(self, scorer):
        """Test trend analysis over time."""
        # Create history with improving scores
        for i, score in enumerate([60, 65, 70, 75, 80]):
            scorer.calculate_score(
                client_id="client_001",
                activity_level=score,
                accuracy=score,
                response_time=3.0,
                ticket_resolution=score,
                engagement=score
            )

        # Get trend analysis
        analysis = scorer.get_score_trend_analysis("client_001")

        assert analysis["trend_direction"] in ["improving", "stable", "declining"]
        assert analysis["improvement"] > 0  # Should show improvement

    def test_batch_calculate_scores(self, scorer):
        """Test batch score calculation."""
        clients_data = [
            {"client_id": "client_001", "accuracy": 85, "response_time": 2.0},
            {"client_id": "client_002", "accuracy": 75, "response_time": 3.0},
            {"client_id": "client_003", "accuracy": 90, "response_time": 1.5},
        ]

        results = scorer.batch_calculate_scores(clients_data)

        assert len(results) == 3
        assert all(isinstance(r, HealthScoreResult) for r in results)


class TestAlertManager:
    """Tests for AlertManager class."""

    @pytest.fixture
    def alert_manager(self):
        """Create alert manager instance."""
        return AlertManager()

    def test_check_health_alerts_below_threshold(self, alert_manager):
        """Test health alerts when score is below threshold."""
        alerts = alert_manager.check_health_alerts(
            client_id="client_001",
            health_score=35.0  # Below critical threshold
        )

        assert len(alerts) > 0
        assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)

    def test_check_health_alerts_score_drop(self, alert_manager):
        """Test alerts on significant score drop."""
        alerts = alert_manager.check_health_alerts(
            client_id="client_001",
            health_score=60.0,
            previous_score=80.0  # 20 point drop
        )

        # Should have drop alert
        drop_alerts = [a for a in alerts if "drop" in a.title.lower()]
        assert len(drop_alerts) > 0
        assert any(a.severity == AlertSeverity.CRITICAL for a in drop_alerts)

    def test_check_inactivity_alert(self, alert_manager):
        """Test inactivity alert."""
        last_activity = datetime.utcnow() - timedelta(days=5)

        alert = alert_manager.check_inactivity_alert(
            client_id="client_001",
            last_activity=last_activity
        )

        assert alert is not None
        assert alert.alert_type == AlertType.INACTIVITY
        assert alert.severity in [AlertSeverity.WARNING, AlertSeverity.ERROR]

    def test_check_accuracy_alert(self, alert_manager):
        """Test accuracy drop alert."""
        alerts = alert_manager.check_accuracy_alert(
            client_id="client_001",
            accuracy=55.0,  # Below critical threshold
            previous_accuracy=75.0
        )

        assert len(alerts) > 0
        assert any(a.alert_type == AlertType.ACCURACY_DROP for a in alerts)

    def test_check_response_time_alert(self, alert_manager):
        """Test response time alert."""
        alert = alert_manager.check_response_time_alert(
            client_id="client_001",
            avg_response_time=6.0  # Above threshold
        )

        assert alert is not None
        assert alert.alert_type == AlertType.RESPONSE_TIME_HIGH

    def test_check_all_alerts(self, alert_manager):
        """Test checking all alert conditions."""
        health_data = {
            "health_score": 35.0,
            "accuracy": 55.0,
            "avg_response_time": 6.0,
            "last_activity": datetime.utcnow() - timedelta(days=5)
        }

        alerts = alert_manager.check_all_alerts(
            client_id="client_001",
            health_data=health_data
        )

        assert len(alerts) > 0

    @pytest.mark.asyncio
    async def test_send_notifications(self, alert_manager):
        """Test sending notifications."""
        alert = alert_manager.check_health_alerts(
            client_id="client_001",
            health_score=30.0
        )[0]

        results = await alert_manager.send_notifications(alert)

        assert isinstance(results, dict)
        assert "email" in results
        assert "in_app" in results

    def test_acknowledge_alert(self, alert_manager):
        """Test acknowledging an alert."""
        # Create an alert
        alerts = alert_manager.check_health_alerts(
            client_id="client_001",
            health_score=30.0
        )

        alert_id = alerts[0].alert_id

        # Acknowledge it
        acknowledged = alert_manager.acknowledge_alert(
            alert_id=alert_id,
            acknowledged_by="test_user"
        )

        assert acknowledged is not None
        assert acknowledged.acknowledged is True
        assert acknowledged.acknowledged_by == "test_user"

    def test_get_active_alerts(self, alert_manager):
        """Test getting active alerts."""
        # Create some alerts
        alert_manager.check_health_alerts("client_001", 30.0)
        alert_manager.check_health_alerts("client_002", 35.0)

        active = alert_manager.get_active_alerts()

        assert len(active) >= 2
        assert all(not a.acknowledged for a in active)

    def test_get_alert_summary(self, alert_manager):
        """Test getting alert summary."""
        # Create some alerts
        alert_manager.check_health_alerts("client_001", 30.0)
        alert_manager.check_health_alerts("client_002", 55.0)

        summary = alert_manager.get_alert_summary()

        assert summary["total_alerts"] >= 2
        assert "active_alerts" in summary
        assert "by_severity" in summary


class TestIntegration:
    """Integration tests for health monitoring workflow."""

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        monitor = HealthMonitor()
        scorer = HealthScorer()
        alert_manager = AlertManager()

        # Monitor all clients
        snapshots = await monitor.monitor_all_clients()
        assert len(snapshots) == 10

        # Score each client
        results = []
        for client_id, snapshot in snapshots.items():
            result = scorer.calculate_score(
                client_id=client_id,
                activity_level=snapshot.activity_level,
                accuracy=snapshot.accuracy_rate,
                response_time=snapshot.avg_response_time,
                ticket_resolution=snapshot.resolution_rate,
                engagement=snapshot.engagement_score
            )
            results.append(result)

            # Check for alerts
            health_data = {
                "health_score": result.overall_score,
                "accuracy": snapshot.accuracy_rate,
                "avg_response_time": snapshot.avg_response_time,
            }
            alerts = alert_manager.check_all_alerts(client_id, health_data)

        # Verify all clients scored
        assert len(results) == 10
        assert all(0 <= r.overall_score <= 100 for r in results)

    @pytest.mark.asyncio
    async def test_all_10_clients_tracked(self):
        """Test that all 10 clients are tracked."""
        monitor = HealthMonitor()

        # Run monitoring
        await monitor.monitor_all_clients()

        # Verify all 10 clients have snapshots
        expected = [
            "client_001", "client_002", "client_003", "client_004", "client_005",
            "client_006", "client_007", "client_008", "client_009", "client_010"
        ]

        for client_id in expected:
            snapshot = monitor.get_client_snapshot(client_id)
            assert snapshot is not None, f"No snapshot for {client_id}"
            assert snapshot.overall_health >= 0
