"""
Unit tests for PARWA High Workflows.

Tests for PARWA High variant workflows:
- VideoSupportWorkflow
- AnalyticsWorkflow
- CoordinationWorkflow
- CustomerSuccessWorkflow

CRITICAL TESTS:
- Customer success workflow returns churn_risk with risk_score
- Customer success workflow returns churn_risk with factors
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from variants.parwa_high.tools.analytics_engine import (
    AnalyticsEngine,
    Insight,
    Trend,
    Anomaly,
)
from variants.parwa_high.tools.team_coordination import (
    TeamCoordinationTool,
    TeamTask,
    Team,
    TaskPriority,
    TaskStatus,
)
from variants.parwa_high.tools.customer_success_tools import (
    CustomerSuccessTools,
    HealthStatus,
    ChurnRiskLevel,
    ChurnPrediction,
    HealthScore,
)
from variants.parwa_high.workflows.video_support import (
    VideoSupportWorkflow,
    VideoSessionStatus,
    VideoResolution,
)
from variants.parwa_high.workflows.analytics import (
    AnalyticsWorkflow,
    AnalyticsWorkflowStatus,
)
from variants.parwa_high.workflows.coordination import (
    CoordinationWorkflow,
    CoordinationStatus,
    TaskComplexity,
)
from variants.parwa_high.workflows.customer_success import (
    CustomerSuccessWorkflow,
    CustomerSuccessStatus,
)


# ============================================================================
# Analytics Engine Tests
# ============================================================================

class TestAnalyticsEngine:
    """Tests for AnalyticsEngine."""

    @pytest.fixture
    def engine(self):
        """Create analytics engine instance."""
        return AnalyticsEngine(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_generate_insights_returns_insights(self, engine):
        """Test that generate_insights returns insights."""
        data = {
            "customer_metrics": {
                "csat_score": 4.2,
                "nps_score": 45,
                "feedback_count": 150,
            },
            "operational_metrics": {
                "avg_resolution_time_minutes": 12,
                "target_time_minutes": 15,
                "resolution_count": 100,
                "ticket_count": 120,
            },
            "time_period": "30d",
        }

        result = await engine.generate_insights(data)

        assert result["success"] is True
        assert "insights" in result
        assert "recommendations" in result
        assert isinstance(result["insights"], list)

    @pytest.mark.asyncio
    async def test_generate_insights_handles_low_csat(self, engine):
        """Test that low CSAT score generates appropriate insight."""
        data = {
            "customer_metrics": {
                "csat_score": 2.5,
                "nps_score": 20,
                "feedback_count": 50,
            },
            "operational_metrics": {},
            "time_period": "30d",
        }

        result = await engine.generate_insights(data)

        assert result["success"] is True
        # Should generate insight about low satisfaction
        assert len(result["insights"]) >= 1
        # Should have recommendations
        assert len(result["recommendations"]) >= 1

    @pytest.mark.asyncio
    async def test_calculate_trends_returns_trends(self, engine):
        """Test that calculate_trends returns trends."""
        historical_data = [
            {"timestamp": "2024-01-01T00:00:00Z", "metric_name": "tickets", "value": 100},
            {"timestamp": "2024-01-02T00:00:00Z", "metric_name": "tickets", "value": 105},
            {"timestamp": "2024-01-03T00:00:00Z", "metric_name": "tickets", "value": 110},
            {"timestamp": "2024-01-04T00:00:00Z", "metric_name": "tickets", "value": 115},
            {"timestamp": "2024-01-05T00:00:00Z", "metric_name": "tickets", "value": 120},
        ]

        result = await engine.calculate_trends(historical_data)

        assert result["success"] is True
        assert "trends" in result
        assert "forecast" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_calculate_trends_handles_insufficient_data(self, engine):
        """Test that calculate_trends handles insufficient data."""
        result = await engine.calculate_trends([])

        assert result["success"] is False
        assert result["trends"] == []

    @pytest.mark.asyncio
    async def test_identify_anomalies_detects_outliers(self, engine):
        """Test that identify_anomalies detects statistical outliers."""
        # Most values around 100, but some outliers
        data = [
            {"metric_name": "response_time", "value": 100},
            {"metric_name": "response_time", "value": 98},
            {"metric_name": "response_time", "value": 102},
            {"metric_name": "response_time", "value": 101},
            {"metric_name": "response_time", "value": 99},
            {"metric_name": "response_time", "value": 500},  # Anomaly
            {"metric_name": "response_time", "value": 103},
            {"metric_name": "response_time", "value": 97},
            {"metric_name": "response_time", "value": 600},  # Anomaly
            {"metric_name": "response_time", "value": 100},
        ]

        anomalies = await engine.identify_anomalies(data)

        assert isinstance(anomalies, list)
        # Should detect at least some anomalies
        assert len(anomalies) >= 1

    @pytest.mark.asyncio
    async def test_generate_report_returns_complete_report(self, engine):
        """Test that generate_report returns complete report."""
        company_id = str(uuid4())

        result = await engine.generate_report(company_id, "30d")

        assert result["success"] is True
        assert result["company_id"] == company_id
        assert result["period"] == "30d"
        assert "report_id" in result
        assert "summary" in result

    def test_engine_returns_correct_variant(self, engine):
        """Test that engine returns correct variant."""
        assert engine.get_variant() == "parwa_high"

    def test_engine_returns_correct_tier(self, engine):
        """Test that engine returns correct tier."""
        assert engine.get_tier() == "heavy"


# ============================================================================
# Team Coordination Tool Tests
# ============================================================================

class TestTeamCoordinationTool:
    """Tests for TeamCoordinationTool."""

    @pytest.fixture
    def tool(self):
        """Create team coordination tool instance."""
        return TeamCoordinationTool(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_assign_task_successfully(self, tool):
        """Test successful task assignment."""
        task = {
            "task_id": "task_001",
            "title": "Customer Issue",
            "description": "Billing problem",
            "priority": "high",
            "required_skills": ["billing"],
        }

        result = await tool.assign_task(task, "team_billing")

        assert result["success"] is True
        assert result["task_id"] == "task_001"
        assert result["team_id"] == "team_billing"
        assert "assigned_at" in result

    @pytest.mark.asyncio
    async def test_assign_task_to_nonexistent_team(self, tool):
        """Test assignment to non-existent team."""
        task = {
            "task_id": "task_002",
            "title": "Test Task",
            "priority": "medium",
        }

        result = await tool.assign_task(task, "nonexistent_team")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_team_load(self, tool):
        """Test getting team load information."""
        result = await tool.get_team_load("team_billing")

        assert result["success"] is True
        assert result["team_id"] == "team_billing"
        assert "load" in result
        assert "current" in result["load"]
        assert "capacity" in result["load"]

    @pytest.mark.asyncio
    async def test_balance_workload(self, tool):
        """Test workload balancing."""
        teams = ["team_billing", "team_support_t1", "team_support_t2"]

        result = await tool.balance_workload(teams)

        assert result["success"] is True
        assert result["teams_analyzed"] == 3
        assert "average_load" in result
        assert "is_balanced" in result

    @pytest.mark.asyncio
    async def test_escalate_to_manager(self, tool):
        """Test manager escalation."""
        # First assign a task
        task = {
            "task_id": "task_003",
            "title": "Critical Issue",
            "priority": "critical",
        }
        await tool.assign_task(task, "team_support_t2")

        # Then escalate
        result = await tool.escalate_to_manager("task_003", "Customer is very upset")

        assert result["success"] is True
        assert "escalation_id" in result
        assert result["status"] == "pending_review"

    def test_tool_max_teams(self, tool):
        """Test max concurrent teams constant."""
        assert tool.get_max_teams() == 5

    def test_tool_returns_correct_variant(self, tool):
        """Test that tool returns correct variant."""
        assert tool.get_variant() == "parwa_high"

    def test_tool_returns_correct_tier(self, tool):
        """Test that tool returns correct tier."""
        assert tool.get_tier() == "heavy"


# ============================================================================
# Customer Success Tools Tests
# ============================================================================

class TestCustomerSuccessTools:
    """Tests for CustomerSuccessTools."""

    @pytest.fixture
    def tools(self):
        """Create customer success tools instance."""
        return CustomerSuccessTools(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_calculate_health_score(self, tools):
        """Test health score calculation."""
        score = await tools.calculate_health_score("cust_001")

        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_predict_churn_risk_returns_risk_score(self, tools):
        """CRITICAL: Test that predict_churn_risk returns risk_score."""
        result = await tools.predict_churn_risk("cust_002")

        assert "risk_score" in result
        assert isinstance(result["risk_score"], float)
        assert 0.0 <= result["risk_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_predict_churn_risk_returns_factors(self, tools):
        """CRITICAL: Test that predict_churn_risk returns factors list."""
        result = await tools.predict_churn_risk("cust_003")

        assert "factors" in result
        assert isinstance(result["factors"], list)

    @pytest.mark.asyncio
    async def test_predict_churn_risk_returns_risk_level(self, tools):
        """Test that predict_churn_risk returns risk_level."""
        result = await tools.predict_churn_risk("cust_004")

        assert "risk_level" in result
        assert result["risk_level"] in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_predict_churn_risk_returns_recommendations(self, tools):
        """Test that predict_churn_risk returns recommendations."""
        result = await tools.predict_churn_risk("cust_005")

        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    @pytest.mark.asyncio
    async def test_get_retention_actions(self, tools):
        """Test getting retention actions."""
        actions = await tools.get_retention_actions("cust_006")

        assert isinstance(actions, list)
        for action in actions:
            assert "priority" in action
            assert "action" in action
            assert "timing" in action

    @pytest.mark.asyncio
    async def test_track_engagement(self, tools):
        """Test engagement tracking."""
        result = await tools.track_engagement("cust_007")

        assert result["customer_id"] == "cust_007"
        assert "metrics" in result
        assert "trends" in result
        assert "engagement_score" in result

    def test_tools_returns_correct_variant(self, tools):
        """Test that tools returns correct variant."""
        assert tools.get_variant() == "parwa_high"

    def test_tools_returns_correct_tier(self, tools):
        """Test that tools returns correct tier."""
        assert tools.get_tier() == "heavy"


# ============================================================================
# Video Support Workflow Tests
# ============================================================================

class TestVideoSupportWorkflow:
    """Tests for VideoSupportWorkflow."""

    @pytest.fixture
    def workflow(self):
        """Create video support workflow instance."""
        return VideoSupportWorkflow(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_execute_returns_session_id(self, workflow):
        """Test that execute returns session_id."""
        result = await workflow.execute("sess_001", "cust_001")

        assert result["session_id"] == "sess_001"
        assert result["customer_id"] == "cust_001"

    @pytest.mark.asyncio
    async def test_execute_returns_duration(self, workflow):
        """Test that execute returns duration."""
        result = await workflow.execute("sess_002", "cust_002")

        assert "duration" in result
        assert isinstance(result["duration"], int)
        assert result["duration"] >= 0

    @pytest.mark.asyncio
    async def test_execute_returns_resolution(self, workflow):
        """Test that execute returns resolution."""
        result = await workflow.execute("sess_003", "cust_003")

        assert "resolution" in result
        assert result["resolution"] in ["resolved", "partially_resolved", "escalated", "follow_up_required", "unresolved"]

    @pytest.mark.asyncio
    async def test_execute_returns_recording_url(self, workflow):
        """Test that execute returns recording_url."""
        result = await workflow.execute("sess_004", "cust_004")

        assert "recording_url" in result
        assert result["recording_url"] is not None

    @pytest.mark.asyncio
    async def test_execute_success(self, workflow):
        """Test successful workflow execution."""
        result = await workflow.execute("sess_005", "cust_005")

        assert result["success"] is True

    def test_workflow_returns_correct_variant(self, workflow):
        """Test that workflow returns correct variant."""
        assert workflow.get_variant() == "parwa_high"

    def test_workflow_returns_correct_tier(self, workflow):
        """Test that workflow returns correct tier."""
        assert workflow.get_tier() == "heavy"

    def test_workflow_returns_correct_name(self, workflow):
        """Test that workflow returns correct name."""
        assert workflow.get_workflow_name() == "VideoSupportWorkflow"


# ============================================================================
# Analytics Workflow Tests
# ============================================================================

class TestAnalyticsWorkflow:
    """Tests for AnalyticsWorkflow."""

    @pytest.fixture
    def workflow(self):
        """Create analytics workflow instance."""
        return AnalyticsWorkflow(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_execute_returns_insights(self, workflow):
        """Test that execute returns insights."""
        result = await workflow.execute(str(uuid4()), "30d")

        assert "insights" in result
        assert isinstance(result["insights"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_trends(self, workflow):
        """Test that execute returns trends."""
        result = await workflow.execute(str(uuid4()), "30d")

        assert "trends" in result
        assert isinstance(result["trends"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_anomalies(self, workflow):
        """Test that execute returns anomalies."""
        result = await workflow.execute(str(uuid4()), "30d")

        assert "anomalies" in result
        assert isinstance(result["anomalies"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_report_url(self, workflow):
        """Test that execute returns report_url."""
        result = await workflow.execute(str(uuid4()), "30d")

        assert "report_url" in result

    @pytest.mark.asyncio
    async def test_execute_with_different_periods(self, workflow):
        """Test execute with different period values."""
        for period in ["7d", "30d", "90d"]:
            result = await workflow.execute(str(uuid4()), period)
            assert result["period"] == period

    def test_workflow_returns_correct_variant(self, workflow):
        """Test that workflow returns correct variant."""
        assert workflow.get_variant() == "parwa_high"

    def test_workflow_returns_correct_tier(self, workflow):
        """Test that workflow returns correct tier."""
        assert workflow.get_tier() == "heavy"

    def test_workflow_returns_correct_name(self, workflow):
        """Test that workflow returns correct name."""
        assert workflow.get_workflow_name() == "AnalyticsWorkflow"


# ============================================================================
# Coordination Workflow Tests
# ============================================================================

class TestCoordinationWorkflow:
    """Tests for CoordinationWorkflow."""

    @pytest.fixture
    def workflow(self):
        """Create coordination workflow instance."""
        return CoordinationWorkflow(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_execute_returns_task_id(self, workflow):
        """Test that execute returns task_id."""
        task = {
            "task_id": "task_coord_001",
            "title": "Customer Issue",
            "priority": "high",
        }

        result = await workflow.execute(task)

        assert result["task_id"] == "task_coord_001"

    @pytest.mark.asyncio
    async def test_execute_assigns_teams(self, workflow):
        """Test that execute assigns teams."""
        task = {
            "task_id": "task_coord_002",
            "title": "Billing Dispute",
            "description": "Customer billing issue",
            "priority": "high",
            "required_skills": ["billing"],
        }

        result = await workflow.execute(task)

        assert "assigned_teams" in result
        assert isinstance(result["assigned_teams"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_status(self, workflow):
        """Test that execute returns status."""
        task = {
            "task_id": "task_coord_003",
            "title": "Support Request",
            "priority": "medium",
        }

        result = await workflow.execute(task)

        assert "status" in result
        assert result["status"] in ["pending", "analyzing", "assigning", "monitoring", "completed", "escalated", "error"]

    @pytest.mark.asyncio
    async def test_execute_returns_completion_time(self, workflow):
        """Test that execute returns completion_time."""
        task = {
            "task_id": "task_coord_004",
            "title": "Test Task",
            "priority": "low",
        }

        result = await workflow.execute(task)

        assert "completion_time" in result
        assert isinstance(result["completion_time"], float)

    @pytest.mark.asyncio
    async def test_execute_high_priority_task(self, workflow):
        """Test execute with high priority task."""
        task = {
            "task_id": "task_coord_005",
            "title": "Critical Issue",
            "description": "System is down",
            "priority": "critical",
        }

        result = await workflow.execute(task)

        assert result["task_id"] == "task_coord_005"

    def test_workflow_returns_correct_variant(self, workflow):
        """Test that workflow returns correct variant."""
        assert workflow.get_variant() == "parwa_high"

    def test_workflow_returns_correct_tier(self, workflow):
        """Test that workflow returns correct tier."""
        assert workflow.get_tier() == "heavy"

    def test_workflow_returns_correct_name(self, workflow):
        """Test that workflow returns correct name."""
        assert workflow.get_workflow_name() == "CoordinationWorkflow"


# ============================================================================
# Customer Success Workflow Tests
# ============================================================================

class TestCustomerSuccessWorkflow:
    """Tests for CustomerSuccessWorkflow."""

    @pytest.fixture
    def workflow(self):
        """Create customer success workflow instance."""
        return CustomerSuccessWorkflow(company_id=uuid4())

    @pytest.mark.asyncio
    async def test_execute_returns_health_score(self, workflow):
        """Test that execute returns health_score."""
        result = await workflow.execute("cust_cs_001")

        assert "health_score" in result
        assert isinstance(result["health_score"], float)
        assert 0.0 <= result["health_score"] <= 100.0

    @pytest.mark.asyncio
    async def test_execute_returns_churn_risk_with_risk_score(self, workflow):
        """CRITICAL: Test that execute returns churn_risk with risk_score."""
        result = await workflow.execute("cust_cs_002")

        assert "churn_risk" in result
        assert result["churn_risk"] is not None
        assert "risk_score" in result["churn_risk"]
        assert isinstance(result["churn_risk"]["risk_score"], float)
        assert 0.0 <= result["churn_risk"]["risk_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_execute_returns_churn_risk_with_factors(self, workflow):
        """CRITICAL: Test that execute returns churn_risk with factors."""
        result = await workflow.execute("cust_cs_003")

        assert "churn_risk" in result
        assert result["churn_risk"] is not None
        assert "factors" in result["churn_risk"]
        assert isinstance(result["churn_risk"]["factors"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_actions(self, workflow):
        """Test that execute returns actions."""
        result = await workflow.execute("cust_cs_004")

        assert "actions" in result
        assert isinstance(result["actions"], list)

    @pytest.mark.asyncio
    async def test_execute_returns_engagement(self, workflow):
        """Test that execute returns engagement."""
        result = await workflow.execute("cust_cs_005")

        assert "engagement" in result

    @pytest.mark.asyncio
    async def test_get_churn_prediction_returns_risk_score(self, workflow):
        """CRITICAL: Test that get_churn_prediction returns risk_score."""
        result = await workflow.get_churn_prediction("cust_cs_006")

        assert "risk_score" in result
        assert isinstance(result["risk_score"], float)

    @pytest.mark.asyncio
    async def test_get_health_assessment(self, workflow):
        """Test get_health_assessment method."""
        result = await workflow.get_health_assessment("cust_cs_007")

        assert "health_score" in result
        assert "status" in result
        assert result["status"] in ["healthy", "at_risk"]

    @pytest.mark.asyncio
    async def test_get_retention_plan(self, workflow):
        """Test get_retention_plan method."""
        result = await workflow.get_retention_plan("cust_cs_008")

        assert "health_score" in result
        assert "churn_risk" in result
        assert "priority_actions" in result
        assert "all_actions" in result

    def test_workflow_returns_correct_variant(self, workflow):
        """Test that workflow returns correct variant."""
        assert workflow.get_variant() == "parwa_high"

    def test_workflow_returns_correct_tier(self, workflow):
        """Test that workflow returns correct tier."""
        assert workflow.get_tier() == "heavy"

    def test_workflow_returns_correct_name(self, workflow):
        """Test that workflow returns correct name."""
        assert workflow.get_workflow_name() == "CustomerSuccessWorkflow"


# ============================================================================
# Integration Tests
# ============================================================================

class TestPARWAHighIntegration:
    """Integration tests for PARWA High workflows."""

    @pytest.mark.asyncio
    async def test_all_workflows_return_correct_variant_and_tier(self):
        """Test that all workflows return parwa_high variant and heavy tier."""
        company_id = uuid4()

        video = VideoSupportWorkflow(company_id=company_id)
        analytics = AnalyticsWorkflow(company_id=company_id)
        coordination = CoordinationWorkflow(company_id=company_id)
        customer_success = CustomerSuccessWorkflow(company_id=company_id)

        for workflow in [video, analytics, coordination, customer_success]:
            assert workflow.get_variant() == "parwa_high"
            assert workflow.get_tier() == "heavy"

    @pytest.mark.asyncio
    async def test_customer_success_full_flow(self):
        """Test complete customer success flow."""
        workflow = CustomerSuccessWorkflow(company_id=uuid4())
        customer_id = "cust_integration_001"

        # Execute full workflow
        result = await workflow.execute(customer_id)

        # Verify all expected outputs
        assert result["success"] is True
        assert "health_score" in result
        assert "churn_risk" in result
        assert "risk_score" in result["churn_risk"]
        assert "factors" in result["churn_risk"]
        assert "actions" in result
        assert "engagement" in result
        assert result["metadata"]["variant"] == "parwa_high"
        assert result["metadata"]["tier"] == "heavy"
