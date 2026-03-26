"""
Unit Tests for Quality Coach Module.

Tests for:
- QualityAnalyzer: Scores accuracy/empathy/efficiency
- QualityReporter: Weekly reports and trends
- QualityNotifier: Real-time alerts

CRITICAL Tests:
- Scores accuracy/empathy/efficiency (0-100)
- Weekly report generated
- Real-time alert fires on low quality
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch


# Import quality coach modules
from backend.quality_coach.analyzer import (
    QualityAnalyzer,
    QualityScores,
    QualityLevel,
    QualityAnalysisResult,
    get_quality_analyzer
)
from backend.quality_coach.reporter import (
    QualityReporter,
    QualityTrend,
    WeeklyReport,
    get_quality_reporter
)
from backend.quality_coach.notifier import (
    QualityNotifier,
    QualityAlert,
    AlertThresholds,
    AlertType,
    AlertSeverity,
    get_quality_notifier
)


class TestQualityAnalyzer:
    """Tests for Quality Analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer without LLM for testing."""
        return QualityAnalyzer(use_llm=False)

    @pytest.mark.asyncio
    async def test_analyze_conversation(self, analyzer):
        """Test analyzing a conversation."""
        analyzer.register_interaction(
            interaction_id="int_001",
            company_id="comp_001",
            messages=[
                {"role": "agent", "content": "How can I help you?"},
                {"role": "customer", "content": "I have a question."}
            ]
        )

        result = await analyzer.analyze_conversation("int_001")

        assert result["success"] is True
        assert "accuracy_score" in result
        assert "empathy_score" in result
        assert "efficiency_score" in result
        assert "overall_score" in result

    @pytest.mark.asyncio
    async def test_scores_accuracy(self, analyzer):
        """CRITICAL: Test that accuracy is scored 0-100."""
        analyzer.register_interaction(
            interaction_id="int_002",
            company_id="comp_001",
            messages=[{"role": "agent", "content": "Test"}],
            resolved=True
        )

        result = await analyzer.analyze_conversation("int_002")

        assert 0 <= result["accuracy_score"] <= 100

    @pytest.mark.asyncio
    async def test_scores_empathy(self, analyzer):
        """CRITICAL: Test that empathy is scored 0-100."""
        analyzer.register_interaction(
            interaction_id="int_003",
            company_id="comp_001",
            messages=[{"role": "agent", "content": "I understand your frustration."}],
            sentiment="positive"
        )

        result = await analyzer.analyze_conversation("int_003")

        assert 0 <= result["empathy_score"] <= 100

    @pytest.mark.asyncio
    async def test_scores_efficiency(self, analyzer):
        """CRITICAL: Test that efficiency is scored 0-100."""
        analyzer.register_interaction(
            interaction_id="int_004",
            company_id="comp_001",
            messages=[{"role": "agent", "content": "Quick response"}],
            resolution_time_minutes=5,
            first_contact_resolution=True
        )

        result = await analyzer.analyze_conversation("int_004")

        assert 0 <= result["efficiency_score"] <= 100

    @pytest.mark.asyncio
    async def test_overall_score_calculation(self, analyzer):
        """Test that overall score is calculated correctly."""
        analyzer.register_interaction(
            interaction_id="int_005",
            company_id="comp_001",
            messages=[],
            resolved=True
        )

        result = await analyzer.analyze_conversation("int_005")

        # Overall should be weighted average of accuracy, empathy, efficiency
        expected = (
            result["accuracy_score"] * 0.4 +
            result["empathy_score"] * 0.3 +
            result["efficiency_score"] * 0.3
        )

        assert abs(result["overall_score"] - expected) < 0.1

    @pytest.mark.asyncio
    async def test_quality_level_classification(self, analyzer):
        """Test quality level classification."""
        # Test different score ranges
        assert analyzer._get_quality_level(95) == QualityLevel.EXCELLENT
        assert analyzer._get_quality_level(80) == QualityLevel.GOOD
        assert analyzer._get_quality_level(60) == QualityLevel.ACCEPTABLE
        assert analyzer._get_quality_level(30) == QualityLevel.POOR
        assert analyzer._get_quality_level(15) == QualityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_recommendations_generated(self, analyzer):
        """Test that recommendations are generated."""
        analyzer.register_interaction(
            interaction_id="int_006",
            company_id="comp_001",
            messages=[]
        )

        result = await analyzer.analyze_conversation("int_006")

        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    @pytest.mark.asyncio
    async def test_low_quality_detection(self, analyzer):
        """Test detection of low quality interactions."""
        # Register multiple interactions
        for i in range(5):
            analyzer.register_interaction(
                interaction_id=f"int_low_{i}",
                company_id="comp_001",
                messages=[],
                resolved=False,
                sentiment="negative"
            )
            await analyzer.analyze_conversation(f"int_low_{i}")

        # Check for low quality
        low_quality = analyzer.get_low_quality_interactions("comp_001")

        # Should have some low quality
        assert isinstance(low_quality, list)

    def test_get_status(self, analyzer):
        """Test getting analyzer status."""
        status = analyzer.get_status()

        assert "use_llm" in status
        assert "total_interactions" in status


class TestQualityReporter:
    """Tests for Quality Reporter."""

    @pytest.fixture
    def reporter(self):
        """Create a quality reporter."""
        return QualityReporter()

    @pytest.mark.asyncio
    async def test_generate_weekly_report(self, reporter):
        """CRITICAL: Test that weekly report is generated."""
        result = await reporter.generate_weekly_report("comp_001")

        assert result["success"] is True
        assert "report_id" in result
        assert "average_scores" in result
        assert "total_interactions" in result

    @pytest.mark.asyncio
    async def test_weekly_report_includes_scores(self, reporter):
        """Test that report includes all score averages."""
        result = await reporter.generate_weekly_report("comp_001")

        scores = result["average_scores"]

        assert "accuracy" in scores
        assert "empathy" in scores
        assert "efficiency" in scores
        assert "overall" in scores

    @pytest.mark.asyncio
    async def test_get_trends(self, reporter):
        """Test getting quality trends."""
        result = await reporter.get_trends("comp_001", days=30)

        assert "days_analyzed" in result
        assert "trend_direction" in result
        assert result["trend_direction"] in ["improving", "declining", "stable"]

    @pytest.mark.asyncio
    async def test_compare_periods(self, reporter):
        """Test comparing different periods."""
        now = datetime.now(timezone.utc)

        result = await reporter.compare_periods(
            company_id="comp_001",
            period1={
                "start": (now - timedelta(days=14)).isoformat(),
                "end": (now - timedelta(days=7)).isoformat()
            },
            period2={
                "start": (now - timedelta(days=7)).isoformat(),
                "end": now.isoformat()
            }
        )

        assert result["success"] is True
        assert "deltas" in result
        assert "period1" in result
        assert "period2" in result

    @pytest.mark.asyncio
    async def test_quality_distribution(self, reporter):
        """Test quality distribution in report."""
        result = await reporter.generate_weekly_report("comp_001")

        distribution = result["quality_distribution"]

        assert "excellent" in distribution
        assert "good" in distribution
        assert "acceptable" in distribution
        assert "poor" in distribution
        assert "critical" in distribution

    def test_get_status(self, reporter):
        """Test getting reporter status."""
        status = reporter.get_status()

        assert "total_reports" in status
        assert "companies_tracked" in status


class TestQualityNotifier:
    """Tests for Quality Notifier."""

    @pytest.fixture
    def notifier(self):
        """Create a quality notifier."""
        return QualityNotifier()

    @pytest.mark.asyncio
    async def test_alert_low_quality(self, notifier):
        """CRITICAL: Test that real-time alert fires on low quality."""
        result = await notifier.alert_low_quality(
            interaction_id="int_001",
            score=35.0,  # Below default 50 threshold
            company_id="comp_001"
        )

        assert result["alert_fired"] is True
        assert result["alert_type"] in ["low_quality", "critical_quality"]

    @pytest.mark.asyncio
    async def test_no_alert_high_quality(self, notifier):
        """Test no alert for high quality scores."""
        result = await notifier.alert_low_quality(
            interaction_id="int_002",
            score=85.0,  # Above threshold
            company_id="comp_001"
        )

        assert result["alert_fired"] is False

    @pytest.mark.asyncio
    async def test_critical_quality_alert(self, notifier):
        """Test critical quality alert."""
        result = await notifier.alert_low_quality(
            interaction_id="int_003",
            score=15.0,  # Critical threshold
            company_id="comp_001"
        )

        assert result["alert_fired"] is True
        assert result["severity"] == AlertSeverity.CRITICAL.value

    @pytest.mark.asyncio
    async def test_notify_manager(self, notifier):
        """Test notifying manager."""
        notifier.add_manager("comp_001", "manager_001")

        result = await notifier.notify_manager(
            company_id="comp_001",
            issue={
                "alert_type": "low_quality",
                "message": "Test alert"
            }
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_setup_alerts(self, notifier):
        """Test setting up custom alert thresholds."""
        result = await notifier.setup_alerts(
            company_id="comp_002",
            thresholds={
                "low_quality": 60.0,
                "critical_quality": 30.0
            }
        )

        assert result["success"] is True
        assert result["thresholds"]["low_quality"] == 60.0

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, notifier):
        """Test acknowledging an alert."""
        # Create alert first
        alert_result = await notifier.alert_low_quality(
            interaction_id="int_004",
            score=30.0,
            company_id="comp_001"
        )

        if alert_result["alert_fired"]:
            result = await notifier.acknowledge_alert(
                alert_id=alert_result["alert_id"],
                acknowledged_by="manager_001"
            )

            assert result["success"] is True
            assert result["acknowledged"] is True

    def test_get_alerts(self, notifier):
        """Test getting alerts."""
        alerts = notifier.get_alerts()

        assert isinstance(alerts, list)

    def test_get_status(self, notifier):
        """Test getting notifier status."""
        status = notifier.get_status()

        assert "total_alerts" in status
        assert "unacknowledged_count" in status


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_quality_analyzer(self):
        """Test analyzer factory."""
        analyzer = get_quality_analyzer(use_llm=False)
        assert isinstance(analyzer, QualityAnalyzer)

    def test_get_quality_reporter(self):
        """Test reporter factory."""
        reporter = get_quality_reporter()
        assert isinstance(reporter, QualityReporter)

    def test_get_quality_notifier(self):
        """Test notifier factory."""
        notifier = get_quality_notifier()
        assert isinstance(notifier, QualityNotifier)


class TestIntegration:
    """Integration tests for Quality Coach."""

    @pytest.mark.asyncio
    async def test_full_analysis_to_alert_flow(self):
        """Test flow from analysis to alert."""
        analyzer = QualityAnalyzer(use_llm=False)
        notifier = QualityNotifier()

        # Analyze conversation
        analyzer.register_interaction(
            interaction_id="int_integration",
            company_id="comp_integration",
            messages=[],
            resolved=False,
            sentiment="negative"
        )

        analysis = await analyzer.analyze_conversation("int_integration")

        # Check if alert should fire
        alert = await notifier.alert_low_quality(
            interaction_id="int_integration",
            score=analysis["overall_score"],
            company_id="comp_integration"
        )

        # Verify integration
        assert analysis["success"] is True
        assert "alert_fired" in alert

    @pytest.mark.asyncio
    async def test_full_analysis_to_report_flow(self):
        """Test flow from analysis to weekly report."""
        analyzer = QualityAnalyzer(use_llm=False)
        reporter = QualityReporter()

        # Perform analyses
        for i in range(5):
            analyzer.register_interaction(
                interaction_id=f"int_report_{i}",
                company_id="comp_report",
                messages=[]
            )
            result = await analyzer.analyze_conversation(f"int_report_{i}")
            reporter.add_analysis("comp_report", result)

        # Generate report
        report = await reporter.generate_weekly_report("comp_report")

        assert report["success"] is True
        assert report["total_interactions"] >= 0
