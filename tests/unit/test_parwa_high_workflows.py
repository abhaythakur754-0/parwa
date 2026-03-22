"""
Unit tests for PARWA High Workflows.

Tests for PARWA High workflows and tasks:
- VideoCallTask
- GenerateInsightsTask
- CoordinateTeamsTask
- CustomerSuccessTask

CRITICAL TESTS:
- Customer success returns churn_risk with risk_score
- All tasks return variant="parwa_high", tier="heavy"
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from variants.parwa_high.tasks.video_call import VideoCallTask, VideoCallStatus
from variants.parwa_high.tasks.generate_insights import GenerateInsightsTask
from variants.parwa_high.tasks.coordinate_teams import CoordinateTeamsTask
from variants.parwa_high.tasks.customer_success import (
    CustomerSuccessTask,
    CustomerSuccessResult,
    ChurnRisk,
)


# =============================================================================
# VideoCallTask Tests
# =============================================================================

class TestVideoCallTask:
    """Tests for VideoCallTask."""

    @pytest.fixture
    def task(self):
        """Create video call task instance."""
        return VideoCallTask()

    def test_task_metadata(self, task):
        """Test task metadata."""
        assert task.get_task_name() == "video_call"
        assert task.get_variant() == "parwa_high"
        assert task.get_tier() == "heavy"

    @pytest.mark.asyncio
    async def test_start_video(self, task):
        """Test starting video call."""
        result = await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="start",
        )

        assert result.success is True
        assert result.session_id == "sess_123"
        assert result.status == VideoCallStatus.STARTED

    @pytest.mark.asyncio
    async def test_share_screen(self, task):
        """Test screen sharing."""
        # Start session first
        await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="start",
        )

        result = await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="share_screen",
            enabled=True,
        )

        assert result.success is True
        assert result.status == VideoCallStatus.SCREEN_SHARING

    @pytest.mark.asyncio
    async def test_end_video(self, task):
        """Test ending video call."""
        # Start session first
        await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="start",
        )

        result = await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="end",
        )

        assert result.success is True
        assert result.status == VideoCallStatus.ENDED

    @pytest.mark.asyncio
    async def test_unknown_action(self, task):
        """Test unknown action handling."""
        result = await task.execute(
            session_id="sess_123",
            customer_id="cust_456",
            action="invalid",
        )

        assert result.success is False
        assert result.status == VideoCallStatus.FAILED


# =============================================================================
# GenerateInsightsTask Tests
# =============================================================================

class TestGenerateInsightsTask:
    """Tests for GenerateInsightsTask."""

    @pytest.fixture
    def task(self):
        """Create generate insights task instance."""
        return GenerateInsightsTask()

    def test_task_metadata(self, task):
        """Test task metadata."""
        assert task.get_task_name() == "generate_insights"
        assert task.get_variant() == "parwa_high"
        assert task.get_tier() == "heavy"

    @pytest.mark.asyncio
    async def test_execute_returns_insights(self, task):
        """Test execute returns insights.

        CRITICAL: Returns {insights, risk_score, trends}
        """
        result = await task.execute(
            company_id="company_123",
            period="last_30_days",
        )

        assert result.success is True
        assert result.company_id == "company_123"
        assert result.period == "last_30_days"

        # CRITICAL: Check required fields
        assert hasattr(result, "insights")
        assert hasattr(result, "risk_score")
        assert hasattr(result, "trends")

    @pytest.mark.asyncio
    async def test_risk_score_calculation(self, task):
        """Test risk score is calculated."""
        result = await task.execute(
            company_id="company_456",
            period="last_7_days",
        )

        assert result.success is True
        assert 0.0 <= result.risk_score <= 1.0


# =============================================================================
# CoordinateTeamsTask Tests
# =============================================================================

class TestCoordinateTeamsTask:
    """Tests for CoordinateTeamsTask."""

    @pytest.fixture
    def task(self):
        """Create coordinate teams task instance."""
        return CoordinateTeamsTask()

    def test_task_metadata(self, task):
        """Test task metadata."""
        assert task.get_task_name() == "coordinate_teams"
        assert task.get_variant() == "parwa_high"
        assert task.get_tier() == "heavy"

    @pytest.mark.asyncio
    async def test_coordinate_teams(self, task):
        """Test coordinating teams."""
        result = await task.execute({
            "description": "Handle VIP customer issue",
            "priority": 1,
            "required_skills": ["vip_support"],
        })

        assert result.success is True
        assert result.task_id is not None
        assert result.status == "assigned"
        assert result.max_teams == 5

    @pytest.mark.asyncio
    async def test_assign_to_specific_team(self, task):
        """Test assigning to specific team."""
        result = await task.execute({
            "description": "Technical issue",
            "priority": 2,
            "team_id": "team_tech",
        })

        assert result.success is True
        assert "team_tech" in result.assigned_teams

    @pytest.mark.asyncio
    async def test_monitor_progress(self, task):
        """Test monitoring progress."""
        # Create task first
        coord_result = await task.execute({
            "description": "Test task",
            "priority": 3,
        })

        result = await task.monitor_progress(coord_result.task_id)
        assert result.success is True


# =============================================================================
# CustomerSuccessTask Tests (CRITICAL)
# =============================================================================

class TestCustomerSuccessTask:
    """Tests for CustomerSuccessTask.

    CRITICAL: Returns {health_score, churn_risk, recommendations}
    """

    @pytest.fixture
    def task(self):
        """Create customer success task instance."""
        return CustomerSuccessTask()

    def test_task_metadata(self, task):
        """Test task metadata."""
        assert task.get_task_name() == "customer_success"
        assert task.get_variant() == "parwa_high"
        assert task.get_tier() == "heavy"

    @pytest.mark.asyncio
    async def test_execute_returns_required_fields(self, task):
        """Test execute returns all required fields.

        CRITICAL: Returns {health_score, churn_risk, recommendations}
        """
        result = await task.execute(customer_id="cust_123")

        assert result.success is True
        assert result.customer_id == "cust_123"

        # CRITICAL: Check required fields
        assert hasattr(result, "health_score")
        assert hasattr(result, "churn_risk")
        assert hasattr(result, "recommendations")

    @pytest.mark.asyncio
    async def test_health_score_range(self, task):
        """Test health score is in valid range."""
        result = await task.execute(customer_id="cust_456")

        assert result.success is True
        assert 0.0 <= result.health_score <= 1.0

    @pytest.mark.asyncio
    async def test_churn_risk_has_risk_score(self, task):
        """Test churn risk includes risk_score.

        CRITICAL: churn_risk must contain risk_score.
        """
        result = await task.execute(customer_id="cust_789")

        assert result.success is True
        assert result.churn_risk is not None
        assert isinstance(result.churn_risk, ChurnRisk)

        # CRITICAL: Check risk score
        assert hasattr(result.churn_risk, "risk_score")
        assert 0.0 <= result.churn_risk.risk_score <= 1.0

    @pytest.mark.asyncio
    async def test_churn_risk_has_risk_factors(self, task):
        """Test churn risk includes risk_factors."""
        result = await task.execute(customer_id="cust_abc")

        assert result.success is True
        assert result.churn_risk is not None
        assert hasattr(result.churn_risk, "risk_factors")
        assert isinstance(result.churn_risk.risk_factors, list)

    @pytest.mark.asyncio
    async def test_churn_risk_has_risk_level(self, task):
        """Test churn risk includes risk_level."""
        result = await task.execute(customer_id="cust_def")

        assert result.success is True
        assert result.churn_risk is not None
        assert hasattr(result.churn_risk, "risk_level")
        assert result.churn_risk.risk_level in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_recommendations_generated(self, task):
        """Test recommendations are generated."""
        result = await task.execute(customer_id="cust_xyz")

        assert result.success is True
        assert isinstance(result.recommendations, list)

    @pytest.mark.asyncio
    async def test_empty_customer_id_fails(self, task):
        """Test empty customer ID fails."""
        result = await task.execute(customer_id="")

        assert result.success is False
        assert "required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_engagement_score_included(self, task):
        """Test engagement score is included."""
        result = await task.execute(customer_id="cust_123")

        assert result.success is True
        assert hasattr(result, "engagement_score")
        assert 0.0 <= result.engagement_score <= 1.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestParwaHighTasksIntegration:
    """Integration tests for PARWA High tasks."""

    def test_all_tasks_return_heavy_tier(self):
        """Test all tasks return tier='heavy'."""
        tasks = [
            VideoCallTask(),
            GenerateInsightsTask(),
            CoordinateTeamsTask(),
            CustomerSuccessTask(),
        ]

        for task in tasks:
            assert task.get_tier() == "heavy"
            assert task.get_variant() == "parwa_high"

    @pytest.mark.asyncio
    async def test_full_customer_success_flow(self):
        """Test complete customer success workflow."""
        task = CustomerSuccessTask()

        result = await task.execute(customer_id="test_customer")

        # Verify all required fields present
        assert result.success is True
        assert result.health_score is not None
        assert result.churn_risk is not None
        assert result.churn_risk.risk_score is not None
        assert len(result.recommendations) >= 0

    @pytest.mark.asyncio
    async def test_video_to_coordination_flow(self):
        """Test video session to team coordination flow."""
        video_task = VideoCallTask()
        coord_task = CoordinateTeamsTask()

        # Start video session
        video_result = await video_task.execute(
            session_id="sess_vip",
            customer_id="cust_vip",
            action="start",
        )
        assert video_result.success is True

        # Coordinate team for support
        coord_result = await coord_task.execute({
            "description": "VIP customer video support",
            "priority": 1,
            "required_skills": ["vip", "video_support"],
        })
        assert coord_result.success is True
        assert coord_result.max_teams == 5
