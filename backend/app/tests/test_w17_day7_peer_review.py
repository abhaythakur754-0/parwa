"""
Integration Tests for Week 17 Day 7 — F-108 Peer Review + Pipeline Test

Tests for:
- F-108: Peer Review Service (Junior-to-senior escalation)
- Full Training Pipeline Integration Test

Building Codes tested:
- BC-001: Multi-tenant isolation
- BC-007: AI Model Interaction
- BC-012: Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# F-108: Peer Review Service Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPeerReviewService:
    """Tests for F-108 Peer Review Service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create PeerReviewService instance."""
        from app.services.peer_review_service import PeerReviewService
        return PeerReviewService(mock_db)

    def test_escalation_constants_exist(self):
        """Test that escalation constants are properly defined."""
        from app.services.peer_review_service import (
            ESCALATION_LOW_CONFIDENCE,
            ESCALATION_COMPLEX_QUERY,
            ESCALATION_CONFIDENCE_THRESHOLD,
        )

        assert ESCALATION_LOW_CONFIDENCE == "low_confidence"
        assert ESCALATION_COMPLEX_QUERY == "complex_query"
        assert ESCALATION_CONFIDENCE_THRESHOLD == 0.65

    def test_create_escalation_agent_not_found(self, service, mock_db):
        """Test creating escalation when junior agent not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.create_escalation(
            company_id="company-123",
            junior_agent_id="non-existent",
            ticket_id="ticket-123",
            reason="low_confidence",
        )

        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    def test_create_escalation_no_senior_agents(self, service, mock_db):
        """Test creating escalation when no senior agents available."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Junior Agent"
        mock_agent.tier = "junior"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = service.create_escalation(
            company_id="company-123",
            junior_agent_id="agent-123",
            ticket_id="ticket-123",
            reason="low_confidence",
        )

        assert result["status"] == "error"
        assert "no senior agents" in result["error"].lower()

    def test_auto_escalate_agent_not_found(self, service, mock_db):
        """Test auto-escalation when agent not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.auto_escalate_if_needed(
            company_id="company-123",
            agent_id="non-existent",
            ticket_id="ticket-123",
            confidence_score=0.5,
            response_draft="Test response",
        )

        assert result["escalated"] == False
        assert result["reason"] == "agent_not_found"

    def test_auto_escalate_not_junior_tier(self, service, mock_db):
        """Test auto-escalation for senior agent (should not escalate)."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.tier = "senior"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        result = service.auto_escalate_if_needed(
            company_id="company-123",
            agent_id="agent-123",
            ticket_id="ticket-123",
            confidence_score=0.3,
            response_draft="Test response",
        )

        assert result["escalated"] == False
        assert result["reason"] == "not_junior_tier"

    def test_auto_escalate_confidence_above_threshold(self, service, mock_db):
        """Test that no escalation when confidence is high enough."""
        mock_agent = Mock()
        mock_agent.id = "agent-123"
        mock_agent.tier = "junior"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        result = service.auto_escalate_if_needed(
            company_id="company-123",
            agent_id="agent-123",
            ticket_id="ticket-123",
            confidence_score=0.8,  # Above 0.65 threshold
            response_draft="Test response",
        )

        assert result["escalated"] == False
        assert result["reason"] == "confidence_above_threshold"

    def test_get_review_queue(self, service, mock_db):
        """Test getting review queue for senior agent."""
        result = service.get_review_queue(
            company_id="company-123",
            senior_agent_id="senior-123",
        )

        assert "queue" in result
        assert "total" in result
        assert result["senior_agent_id"] == "senior-123"

    def test_get_escalation_analytics(self, service, mock_db):
        """Test getting escalation analytics."""
        result = service.get_escalation_analytics(
            company_id="company-123",
            days=30,
        )

        assert result["company_id"] == "company-123"
        assert result["period_days"] == 30
        assert "by_reason" in result
        assert "by_priority" in result

    def test_get_senior_workload(self, service, mock_db):
        """Test getting senior workload distribution."""
        mock_senior = Mock()
        mock_senior.id = "senior-123"
        mock_senior.name = "Senior Agent"
        mock_senior.tier = "senior"
        mock_senior.status = "active"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_senior]

        result = service.get_senior_workload("company-123")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["agent_id"] == "senior-123"

    def test_get_learning_progress(self, service, mock_db):
        """Test getting learning progress for junior agent."""
        result = service.get_learning_progress(
            company_id="company-123",
            junior_agent_id="junior-123",
            days=30,
        )

        assert result["agent_id"] == "junior-123"
        assert result["period_days"] == 30
        assert "improvement_areas" in result


# ─────────────────────────────────────────────────────────────────────────────
# Training Pipeline Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFullTrainingPipeline:
    """Tests for the full training pipeline integration."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_pipeline_test_all_services_exist(self):
        """Test that all pipeline services can be imported."""
        # Cold Start
        from app.services.cold_start_service import INDUSTRY_TEMPLATES

        # Mistake Threshold
        from app.services.mistake_threshold_service import MISTAKE_THRESHOLD

        # Training

        # Dataset

        # GPU Provider

        # Model Validation

        # Model Deployment

        # Fallback Training
        from app.services.fallback_training_service import RETRAINING_INTERVAL_DAYS

        # Peer Review

        # Verify key constants
        assert MISTAKE_THRESHOLD == 50
        assert RETRAINING_INTERVAL_DAYS == 14
        assert len(INDUSTRY_TEMPLATES) >= 9

    def test_pipeline_test_function(self, mock_db):
        """Test the pipeline test function runs without errors."""
        from app.services.peer_review_service import run_full_training_pipeline_test

        result = run_full_training_pipeline_test("test-company", mock_db)

        assert "company_id" in result
        assert "tests" in result
        assert "passed" in result
        assert "failed" in result
        assert result["company_id"] == "test-company"

    def test_industry_templates_complete(self):
        """Test all industry templates have complete data."""
        from app.services.cold_start_service import INDUSTRY_TEMPLATES

        required_fields = [
            "name",
            "description",
            "common_queries",
            "responses",
            "knowledge_topics"]

        for industry, template in INDUSTRY_TEMPLATES.items():
            for field in required_fields:
                assert field in template, f"Missing {field} in {industry}"

            # Check minimum samples
            query_count = len(template.get("common_queries", []))
            assert query_count >= 5, f"{industry} has only {query_count} queries"

    def test_escalation_reasons_complete(self):
        """Test escalation reasons are complete."""
        from app.services.peer_review_service import (
            ESCALATION_LOW_CONFIDENCE,
            ESCALATION_COMPLEX_QUERY,
            ESCALATION_POLICY_VIOLATION_RISK,
            ESCALATION_CUSTOMER_ESCALATION,
            ESCALATION_UNCERTAINTY,
            ESCALATION_KNOWLEDGE_GAP,
        )

        reasons = [
            ESCALATION_LOW_CONFIDENCE,
            ESCALATION_COMPLEX_QUERY,
            ESCALATION_POLICY_VIOLATION_RISK,
            ESCALATION_CUSTOMER_ESCALATION,
            ESCALATION_UNCERTAINTY,
            ESCALATION_KNOWLEDGE_GAP,
        ]

        assert len(reasons) == 6
        assert len(set(reasons)) == 6  # All unique

    def test_agent_tiers_complete(self):
        """Test agent tiers are complete."""
        from app.services.peer_review_service import (
            TIER_JUNIOR,
            TIER_MID,
            TIER_SENIOR,
            TIER_EXPERT,
        )

        assert TIER_JUNIOR == "junior"
        assert TIER_MID == "mid"
        assert TIER_SENIOR == "senior"
        assert TIER_EXPERT == "expert"


# ─────────────────────────────────────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPeerReviewModel:
    """Tests for PeerReview model."""

    def test_peer_review_model_has_required_fields(self):
        """Test PeerReview model has all required fields."""
        from database.models.training import PeerReview

        assert hasattr(PeerReview, 'company_id')
        assert hasattr(PeerReview, 'junior_agent_id')
        assert hasattr(PeerReview, 'senior_agent_id')
        assert hasattr(PeerReview, 'ticket_id')
        assert hasattr(PeerReview, 'reason')
        assert hasattr(PeerReview, 'status')
        assert hasattr(PeerReview, 'priority')
        assert hasattr(PeerReview, 'original_response')
        assert hasattr(PeerReview, 'reviewed_response')
        assert hasattr(PeerReview, 'feedback')
        assert hasattr(PeerReview, 'confidence_score')
        assert hasattr(PeerReview, 'approved')
        assert hasattr(PeerReview, 'used_for_training')

    def test_peer_review_model_table_name(self):
        """Test PeerReview model table name."""
        from database.models.training import PeerReview

        assert PeerReview.__tablename__ == "peer_reviews"


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPeerReviewAPIEndpoints:
    """Tests for Peer Review API endpoints."""

    def test_escalation_request_schema(self):
        """Test EscalationRequest schema validation."""
        from backend.app.api.peer_review import EscalationRequest

        # Valid request
        req = EscalationRequest(
            junior_agent_id="junior-123",
            ticket_id="ticket-123",
            reason="low_confidence",
            original_response="Test response",
            confidence_score=0.5,
            priority="normal",
        )

        assert req.junior_agent_id == "junior-123"
        assert req.confidence_score == 0.5

    def test_review_submit_request_schema(self):
        """Test ReviewSubmitRequest schema validation."""
        from backend.app.api.peer_review import ReviewSubmitRequest

        req = ReviewSubmitRequest(
            senior_agent_id="senior-123",
            reviewed_response="Corrected response",
            feedback="Good effort, but need to check policy",
            approved=False,
            use_for_training=True,
        )

        assert req.senior_agent_id == "senior-123"
        assert req.approved == False
        assert req.use_for_training


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
