"""
Tests for Onboarding Analytics Services

Tests onboarding tracking, analytics, and milestone management.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from backend.services.client_success.onboarding_tracker import (
    OnboardingTracker,
    OnboardingStep,
    OnboardingStatus,
    StepProgress,
    ClientOnboardingProgress,
)
from backend.services.client_success.onboarding_analytics import (
    OnboardingAnalytics,
    OnboardingMetrics,
    BottleneckAnalysis,
    TrendData,
)
from backend.services.client_success.milestone_manager import (
    MilestoneManager,
    MilestoneType,
    MilestoneStatus,
    MilestoneDefinition,
    MilestoneProgress,
)


class TestOnboardingTracker:
    """Tests for OnboardingTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create onboarding tracker instance."""
        return OnboardingTracker()

    def test_initialize_clients(self, tracker):
        """Test that all 10 clients are initialized."""
        assert len(tracker._progress) == 10

        expected = [
            "client_001", "client_002", "client_003", "client_004", "client_005",
            "client_006", "client_007", "client_008", "client_009", "client_010"
        ]
        for client_id in expected:
            assert client_id in tracker._progress

    def test_start_onboarding(self, tracker):
        """Test starting onboarding for a client."""
        progress = tracker.start_onboarding(
            client_id="client_001",
            variant="parwa",
            industry="ecommerce"
        )

        assert progress.status == OnboardingStatus.IN_PROGRESS
        assert progress.variant == "parwa"
        assert progress.industry == "ecommerce"
        assert progress.started_at is not None
        assert progress.current_step == OnboardingStep.COMPANY_INFO

    def test_start_step(self, tracker):
        """Test starting an onboarding step."""
        tracker.start_onboarding("client_001")

        step_progress = tracker.start_step(
            client_id="client_001",
            step=OnboardingStep.INTEGRATIONS
        )

        assert step_progress.status == OnboardingStatus.IN_PROGRESS
        assert step_progress.started_at is not None
        assert step_progress.attempts == 1

    def test_complete_step(self, tracker):
        """Test completing an onboarding step."""
        tracker.start_onboarding("client_001")

        step_progress = tracker.complete_step(
            client_id="client_001",
            step=OnboardingStep.COMPANY_INFO,
            metadata={"company_name": "Test Company"}
        )

        assert step_progress.status == OnboardingStatus.COMPLETED
        assert step_progress.completed_at is not None
        assert step_progress.metadata["company_name"] == "Test Company"

    def test_completion_percentage(self, tracker):
        """Test completion percentage calculation."""
        tracker.start_onboarding("client_001")

        # Complete one step
        tracker.complete_step("client_001", OnboardingStep.COMPANY_INFO)

        progress = tracker.get_client_progress("client_001")
        assert progress.completion_percentage == 12.5  # 1/8 steps

    def test_detect_stuck_steps(self, tracker):
        """Test detection of stuck steps."""
        tracker.start_onboarding("client_001")
        tracker.start_step("client_001", OnboardingStep.INTEGRATIONS)

        # Manually set a step as stuck by manipulating the time
        progress = tracker._progress["client_001"]
        step = progress.steps[OnboardingStep.INTEGRATIONS]
        step.started_at = datetime.utcnow() - timedelta(hours=5)  # Very old start

        stuck = tracker.detect_stuck_steps("client_001")

        assert OnboardingStep.INTEGRATIONS in stuck.get("client_001", [])

    def test_get_time_to_complete(self, tracker):
        """Test time-to-complete metrics."""
        tracker.start_onboarding("client_001")
        tracker.complete_step("client_001", OnboardingStep.COMPANY_INFO)

        metrics = tracker.get_time_to_complete("client_001")

        assert "total_time_minutes" in metrics
        assert "completion_percentage" in metrics
        assert "steps" in metrics

    def test_get_completion_rate(self, tracker):
        """Test completion rate calculation."""
        # Setup some clients
        tracker.start_onboarding("client_001", variant="parwa")
        tracker.start_onboarding("client_002", variant="mini")

        # Complete one
        for step in OnboardingStep:
            tracker.complete_step("client_001", step)

        rate = tracker.get_completion_rate()

        assert rate["total_clients"] == 10
        assert rate["completed"] >= 1

    def test_invalid_client_raises_error(self, tracker):
        """Test that invalid client raises error."""
        with pytest.raises(ValueError, match="Unsupported client"):
            tracker.get_client_progress("invalid_client")


class TestOnboardingAnalytics:
    """Tests for OnboardingAnalytics class."""

    @pytest.fixture
    def tracker(self):
        """Create tracker with some data."""
        t = OnboardingTracker()
        t.start_onboarding("client_001", variant="parwa", industry="ecommerce")
        t.start_onboarding("client_002", variant="mini", industry="saas")
        return t

    @pytest.fixture
    def analytics(self, tracker):
        """Create analytics instance."""
        return OnboardingAnalytics(tracker)

    def test_calculate_average_time(self, analytics):
        """Test average time calculation."""
        result = analytics.calculate_average_time()

        assert "average_time_minutes" in result
        assert "median_time_minutes" in result
        assert "sample_size" in result

    def test_completion_rate_by_industry(self, analytics):
        """Test completion rate by industry."""
        result = analytics.completion_rate_by_industry()

        assert isinstance(result, dict)
        # Should have industry entries
        assert "ecommerce" in result or "saas" in result

    def test_completion_rate_by_variant(self, analytics):
        """Test completion rate by variant."""
        result = analytics.completion_rate_by_variant()

        assert isinstance(result, dict)
        assert "parwa" in result or "mini" in result

    def test_identify_bottlenecks(self, analytics):
        """Test bottleneck identification."""
        bottlenecks = analytics.identify_bottlenecks()

        assert isinstance(bottlenecks, list)
        # Each bottleneck should have required fields
        for b in bottlenecks:
            assert hasattr(b, "step")
            assert hasattr(b, "recommendation")

    def test_analyze_trends(self, analytics):
        """Test trend analysis."""
        trends = analytics.analyze_trends(days=7)

        assert isinstance(trends, list)
        assert len(trends) > 0

        for t in trends:
            assert isinstance(t, TrendData)
            assert t.completion_rate >= 0

    def test_get_analytics_summary(self, analytics):
        """Test analytics summary."""
        summary = analytics.get_analytics_summary()

        assert "average_time" in summary
        assert "completion_by_industry" in summary
        assert "completion_by_variant" in summary
        assert "bottlenecks" in summary
        assert "insights" in summary

    def test_compare_periods(self, analytics):
        """Test period comparison."""
        comparison = analytics.compare_periods(period1_days=7, period2_days=7)

        assert "period1" in comparison
        assert "period2" in comparison
        assert "change" in comparison

    def test_no_tracker_configured(self):
        """Test analytics without tracker."""
        analytics = OnboardingAnalytics()

        result = analytics.calculate_average_time()
        assert "error" in result


class TestMilestoneManager:
    """Tests for MilestoneManager class."""

    @pytest.fixture
    def manager(self):
        """Create milestone manager instance."""
        return MilestoneManager()

    def test_default_milestones_loaded(self, manager):
        """Test that default milestones are loaded."""
        assert len(manager._definitions) > 0
        assert "first_week_complete" in manager._definitions

    def test_define_milestone(self, manager):
        """Test defining a custom milestone."""
        milestone = manager.define_milestone(
            name="Custom Milestone",
            description="A custom milestone for testing",
            milestone_type=MilestoneType.CUSTOM,
            target_value=100,
            target_unit="items",
            due_days_from_start=14
        )

        assert milestone.milestone_id in manager._definitions
        assert milestone.name == "Custom Milestone"

    def test_start_tracking(self, manager):
        """Test starting milestone tracking."""
        start_date = datetime.utcnow()
        progress = manager.start_tracking("client_001", start_date)

        assert len(progress) > 0
        for p in progress.values():
            assert p.status == MilestoneStatus.PENDING
            assert p.started_at == start_date

    def test_update_progress(self, manager):
        """Test updating milestone progress."""
        start_date = datetime.utcnow()
        manager.start_tracking("client_001", start_date)

        result = manager.update_progress(
            client_id="client_001",
            milestone_type=MilestoneType.ACCURACY_THRESHOLD,
            current_value=70.0
        )

        assert result is not None
        assert result.current_value == 70.0

    def test_mark_achieved(self, manager):
        """Test marking milestone as achieved."""
        start_date = datetime.utcnow()
        manager.start_tracking("client_001", start_date)

        result = manager.mark_achieved("client_001", "first_week_complete")

        assert result is not None
        assert result.status == MilestoneStatus.ACHIEVED
        assert result.achieved_at is not None

    def test_check_overdue_milestones(self, manager):
        """Test checking for overdue milestones."""
        # Start tracking with old date
        old_date = datetime.utcnow() - timedelta(days=30)
        manager.start_tracking("client_001", old_date)

        overdue = manager.check_overdue_milestones()

        assert isinstance(overdue, dict)

    def test_get_upcoming_milestones(self, manager):
        """Test getting upcoming milestones."""
        start_date = datetime.utcnow()
        manager.start_tracking("client_001", start_date)

        upcoming = manager.get_upcoming_milestones("client_001", days_ahead=14)

        assert isinstance(upcoming, list)

    def test_get_milestone_summary(self, manager):
        """Test getting milestone summary."""
        start_date = datetime.utcnow()
        manager.start_tracking("client_001", start_date)

        summary = manager.get_milestone_summary("client_001")

        assert summary["client_id"] == "client_001"
        assert summary["total_milestones"] > 0
        assert "completion_rate" in summary

    def test_notifications_created(self, manager):
        """Test that notifications are created for milestones."""
        start_date = datetime.utcnow()
        manager.start_tracking("client_001", start_date)
        manager.mark_achieved("client_001", "first_week_complete")

        notifications = manager.get_pending_notifications("client_001")

        assert len(notifications) > 0
        assert notifications[0].notification_type == "achieved"

    def test_get_overall_summary(self, manager):
        """Test getting overall summary."""
        summary = manager.get_overall_summary()

        assert "clients_tracked" in summary
        assert "total_milestones" in summary
        assert "overall_completion_rate" in summary

    def test_invalid_client_raises_error(self, manager):
        """Test that invalid client raises error."""
        with pytest.raises(ValueError):
            manager.start_tracking("invalid_client", datetime.utcnow())


class TestIntegration:
    """Integration tests for onboarding services."""

    def test_full_onboarding_workflow(self):
        """Test complete onboarding workflow."""
        # Setup
        tracker = OnboardingTracker()
        analytics = OnboardingAnalytics(tracker)
        milestones = MilestoneManager()

        # Start onboarding
        progress = tracker.start_onboarding(
            client_id="client_001",
            variant="parwa",
            industry="ecommerce"
        )

        assert progress.status == OnboardingStatus.IN_PROGRESS

        # Start milestone tracking
        start_date = datetime.utcnow()
        milestones.start_tracking("client_001", start_date)

        # Complete steps
        for step in OnboardingStep:
            tracker.complete_step("client_001", step)

        # Check completion
        progress = tracker.get_client_progress("client_001")
        assert progress.status == OnboardingStatus.COMPLETED
        assert progress.completion_percentage == 100.0

        # Check analytics
        summary = analytics.get_analytics_summary()
        assert summary is not None

        # Check milestones
        milestone_summary = milestones.get_milestone_summary("client_001")
        assert milestone_summary["total_milestones"] > 0

    def test_all_clients_tracking(self):
        """Test that all 10 clients can be tracked."""
        tracker = OnboardingTracker()
        milestones = MilestoneManager()

        all_clients = [
            "client_001", "client_002", "client_003", "client_004", "client_005",
            "client_006", "client_007", "client_008", "client_009", "client_010"
        ]

        for client_id in all_clients:
            tracker.start_onboarding(client_id, variant="mini")
            milestones.start_tracking(client_id, datetime.utcnow())

        # Verify all tracked
        assert len(tracker.get_all_progress()) == 10

        # Get overall summaries
        completion_rate = tracker.get_completion_rate()
        assert completion_rate["total_clients"] == 10

        milestone_summary = milestones.get_overall_summary()
        assert milestone_summary["clients_tracked"] == 10
