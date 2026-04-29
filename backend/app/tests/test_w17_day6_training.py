"""
Integration Tests for Week 17 Day 6 — F-106 & F-107

Tests for:
- F-106: Fallback Training Service (Bi-weekly scheduled retraining)
- F-107: Cold Start Service (New agent cold start + Industry templates)

Building Codes tested:
- BC-001: Multi-tenant isolation
- BC-007: Training threshold is LOCKED at 50
- BC-012: Error handling
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# F-106: Fallback Training Service Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFallbackTrainingService:
    """Tests for F-106 Fallback Training Service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create FallbackTrainingService instance."""
        from app.services.fallback_training_service import FallbackTrainingService
        return FallbackTrainingService(mock_db)

    def test_retraining_interval_is_14_days(self):
        """Test that retraining interval is correctly set to 14 days."""
        from app.services.fallback_training_service import RETRAINING_INTERVAL_DAYS
        assert RETRAINING_INTERVAL_DAYS == 14

    def test_get_agents_due_for_retraining_no_agent(self, service, mock_db):
        """Test getting agents due for retraining when no agents exist."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = service.get_agents_due_for_retraining("company-123")
        assert result == []

    def test_get_agents_due_for_retraining_never_trained(
            self, service, mock_db):
        """Test that never-trained agents are not marked for retraining (cold start instead)."""
        # Mock agent
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.get_agents_due_for_retraining("company-123")

        assert len(result) == 1
        assert result[0]["agent_id"] == "agent-123"
        assert result[0]["is_due_for_retraining"] == False
        assert "cold_start" in result[0]["reason"]

    def test_get_agents_due_for_retraining_recently_trained(
            self, service, mock_db):
        """Test that recently trained agents are not due."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.now(timezone.utc)

        # Mock recent training run
        mock_run = Mock()
        mock_run.id = "run-123"
        mock_run.completed_at = datetime.now(timezone.utc) - timedelta(days=5)
        mock_run.status = "completed"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_run
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.get_agents_due_for_retraining("company-123")

        assert len(result) == 1
        assert result[0]["is_due_for_retraining"] == False
        assert "recently_trained" in result[0]["reason"] or "not_due" in result[0]["reason"]

    def test_get_agents_due_for_retraining_biweekly_due(
            self, service, mock_db):
        """Test that agents with 14+ days since training are due."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"
        mock_agent.created_at = datetime.now(timezone.utc)

        # Mock old training run (15 days ago)
        mock_run = Mock()
        mock_run.id = "run-123"
        mock_run.completed_at = datetime.now(timezone.utc) - timedelta(days=15)
        mock_run.status = "completed"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_run
        mock_db.query.return_value.filter.return_value.count.return_value = 15  # 15 new mistakes

        result = service.get_agents_due_for_retraining("company-123")

        assert len(result) == 1
        assert result[0]["is_due_for_retraining"]
        assert result[0]["days_since_training"] >= 14

    def test_schedule_retraining_agent_not_found(self, service, mock_db):
        """Test scheduling retraining for non-existent agent."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service.schedule_retraining("company-123", "non-existent")

        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_schedule_retraining_agent_already_training(
            self, service, mock_db):
        """Test that retraining is skipped if agent is already training."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"

        mock_run = Mock()
        mock_run.id = "run-active"
        mock_run.status = "running"

        # Mock the queries
        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_run

        result = service.schedule_retraining(
            "company-123", "agent-123", force=True)

        assert result["status"] == "skipped"
        assert result["reason"] == "already_training"

    def test_get_retraining_schedule(self, service, mock_db):
        """Test getting the retraining schedule."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.status = "active"

        mock_run = Mock()
        mock_run.completed_at = datetime.now(timezone.utc) - timedelta(days=10)
        mock_run.status = "completed"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent]
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_run

        result = service.get_retraining_schedule("company-123", days_ahead=30)

        assert "schedule" in result
        assert result["interval_days"] == 14
        assert result["company_id"] == "company-123"

    def test_get_training_effectiveness(self, service, mock_db):
        """Test getting training effectiveness metrics."""
        mock_run = Mock()
        mock_run.id = "run-123"
        mock_run.agent_id = "agent-123"
        mock_run.completed_at = datetime.now(timezone.utc)
        mock_run.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_run.trigger = "scheduled"
        mock_run.metrics = {"final_accuracy": 0.85, "quality_score": 0.9}
        mock_run.cost_usd = 5.50

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_run]
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = service.get_training_effectiveness("company-123")

        assert result["company_id"] == "company-123"
        assert result["runs_analyzed"] == 1
        assert "average_improvement_pct" in result
        assert "total_cost_usd" in result


# ─────────────────────────────────────────────────────────────────────────────
# F-107: Cold Start Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestColdStartService:
    """Tests for F-107 Cold Start Service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create ColdStartService instance."""
        from app.services.cold_start_service import ColdStartService
        return ColdStartService(mock_db)

    def test_industry_templates_exist(self):
        """Test that industry templates are defined."""
        from app.services.cold_start_service import INDUSTRY_TEMPLATES

        # Check key industries exist
        assert "ecommerce" in INDUSTRY_TEMPLATES
        assert "saas" in INDUSTRY_TEMPLATES
        assert "healthcare" in INDUSTRY_TEMPLATES
        assert "finance" in INDUSTRY_TEMPLATES
        assert "generic" in INDUSTRY_TEMPLATES

    def test_industry_template_has_required_fields(self):
        """Test that industry templates have all required fields."""
        from app.services.cold_start_service import INDUSTRY_TEMPLATES

        for industry, template in INDUSTRY_TEMPLATES.items():
            assert "name" in template, f"Missing name for {industry}"
            assert "description" in template, f"Missing description for {industry}"
            assert "common_queries" in template, f"Missing common_queries for {industry}"
            assert "responses" in template, f"Missing responses for {industry}"
            assert "knowledge_topics" in template, f"Missing knowledge_topics for {industry}"

    def test_get_cold_start_status_agent_not_found(self, service, mock_db):
        """Test cold start status for non-existent agent."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_cold_start_status("company-123", "non-existent")

        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_get_cold_start_status_needs_cold_start(self, service, mock_db):
        """Test that new agents need cold start."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "New Agent"
        mock_agent.status = "active"
        mock_agent.industry = "ecommerce"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.query.return_value.filter.return_value.count.return_value = 0  # No training runs

        result = service.get_cold_start_status("company-123", "agent-123")

        assert result["needs_cold_start"]
        assert result["has_training_history"] == False
        assert result["suggested_industry"] == "ecommerce"

    def test_get_cold_start_status_has_training(self, service, mock_db):
        """Test that trained agents don't need cold start."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Trained Agent"
        mock_agent.status = "active"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.query.return_value.filter.return_value.count.return_value = 1  # Has training run

        result = service.get_cold_start_status("company-123", "agent-123")

        assert result["needs_cold_start"] == False
        assert result["has_training_history"]

    def test_get_agents_needing_cold_start(self, service, mock_db):
        """Test getting list of agents needing cold start."""
        # Mock agents
        mock_agent1 = Mock()
        mock_agent1.id = "agent-1"
        mock_agent1.name = "New Agent"
        mock_agent1.status = "active"
        mock_agent1.created_at = datetime.now(timezone.utc)
        mock_agent1.industry = "saas"

        mock_agent2 = Mock()
        mock_agent2.id = "agent-2"
        mock_agent2.name = "Trained Agent"
        mock_agent2.status = "active"
        mock_agent2.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_agent1, mock_agent2]
        # No training for agent1
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # For agent 1
        first_call_count = 0

        def side_effect_first(*args, **kwargs):
            nonlocal first_call_count
            first_call_count += 1
            if first_call_count <= 2:  # First two calls for agent 1
                return None
            return Mock()  # Return something for agent 2

        mock_db.query.return_value.filter.return_value.first.side_effect = side_effect_first
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.get_agents_needing_cold_start("company-123")

        assert isinstance(result, list)

    def test_get_industry_template(self, service):
        """Test getting a specific industry template."""
        result = service.get_industry_template("ecommerce")

        assert result["industry"] == "ecommerce"
        assert "template" in result
        assert result["template"]["name"] == "E-Commerce"

    def test_get_industry_template_unknown(self, service):
        """Test getting template for unknown industry returns generic."""
        result = service.get_industry_template("unknown_industry")

        assert result["industry"] == "unknown_industry"
        assert result["template"]["name"] == "General Purpose"

    def test_list_industry_templates(self, service):
        """Test listing all industry templates."""
        result = service.list_industry_templates()

        assert isinstance(result, list)
        assert len(result) >= 9  # At least 9 industries

        # Check structure
        for template in result:
            assert "industry_key" in template
            assert "name" in template
            assert "description" in template
            assert "query_categories" in template
            assert "knowledge_topics" in template

    def test_get_template_training_data(self, service):
        """Test getting training data from template."""
        result = service.get_template_training_data("ecommerce")

        assert isinstance(result, list)
        assert len(result) > 0

        # Each item should have query and category
        for item in result:
            assert "query" in item
            assert "category" in item

    def test_get_template_training_data_min_samples(self, service):
        """Test that templates have minimum required samples."""
        from app.services.cold_start_service import MIN_TEMPLATE_SAMPLES

        for industry in [
            "ecommerce",
            "saas",
            "healthcare",
            "finance",
                "generic"]:
            data = service.get_template_training_data(industry)
            assert len(data) >= MIN_TEMPLATE_SAMPLES, f"Template {industry} has only {
                len(data)} samples, minimum is {MIN_TEMPLATE_SAMPLES}"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests for API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingEndpointsIntegration:
    """Integration tests for Day 6 API endpoints."""

    def test_cold_start_endpoints_exist(self):
        """Test that cold start related constants are accessible."""
        from app.services.cold_start_service import (
            INDUSTRY_ECOMMERCE,
            INDUSTRY_SAAS,
            INDUSTRY_GENERIC,
        )

        assert INDUSTRY_ECOMMERCE == "ecommerce"
        assert INDUSTRY_SAAS == "saas"
        assert INDUSTRY_GENERIC == "generic"

    def test_fallback_training_constants(self):
        """Test fallback training constants."""
        from app.services.fallback_training_service import (
            RETRAINING_INTERVAL_DAYS,
            MIN_NEW_MISTAKES_FOR_RETRAINING,
            MIN_DAYS_SINCE_TRAINING,
        )

        assert RETRAINING_INTERVAL_DAYS == 14
        assert MIN_NEW_MISTAKES_FOR_RETRAINING == 10
        assert MIN_DAYS_SINCE_TRAINING == 7


# ─────────────────────────────────────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingModels:
    """Tests for Training models."""

    def test_training_run_has_required_fields(self):
        """Test TrainingRun model has all required fields."""
        from database.models.analytics import TrainingRun

        # Check columns exist
        assert hasattr(TrainingRun, 'company_id')
        assert hasattr(TrainingRun, 'agent_id')
        assert hasattr(TrainingRun, 'dataset_id')
        assert hasattr(TrainingRun, 'trigger')
        assert hasattr(TrainingRun, 'status')
        assert hasattr(TrainingRun, 'progress_pct')
        assert hasattr(TrainingRun, 'current_epoch')
        assert hasattr(TrainingRun, 'total_epochs')
        assert hasattr(TrainingRun, 'cost_usd')
        assert hasattr(TrainingRun, 'provider')
        assert hasattr(TrainingRun, 'gpu_type')

    def test_training_dataset_has_required_fields(self):
        """Test TrainingDataset model has all required fields."""
        from database.models.training import TrainingDataset

        assert hasattr(TrainingDataset, 'company_id')
        assert hasattr(TrainingDataset, 'agent_id')
        assert hasattr(TrainingDataset, 'name')
        assert hasattr(TrainingDataset, 'record_count')
        assert hasattr(TrainingDataset, 'source')
        assert hasattr(TrainingDataset, 'status')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
