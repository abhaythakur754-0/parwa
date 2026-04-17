"""
Unit Tests for PARWA Assignment Scoring Service

Tests the 5-factor AI scoring algorithm:
1. Expertise Match (40 pts)
2. Workload Balance (30 pts)
3. Performance History (20 pts)
4. Response Time History (15 pts)
5. Availability (10 pts)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Import the service
from app.services.assignment_scoring_service import (
    AssignmentScoringService,
    get_assignment_scoring_service,
    FACTOR_WEIGHTS,
    MAX_SCORE,
)


class TestAssignmentScoringService:
    """Test suite for AssignmentScoringService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def mock_company_id(self):
        """Test company ID."""
        return "test-company-123"
    
    @pytest.fixture
    def scoring_service(self, mock_db, mock_company_id):
        """Create a scoring service instance."""
        return AssignmentScoringService(mock_db, mock_company_id)
    
    @pytest.fixture
    def mock_ticket(self):
        """Create a mock ticket."""
        ticket = Mock()
        ticket.id = "ticket-123"
        ticket.company_id = "test-company-123"
        ticket.category = "billing"
        ticket.priority = "high"
        ticket.status = "open"
        return ticket
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent with good metrics."""
        agent = Mock()
        agent.id = "agent-123"
        agent.email = "agent@example.com"
        agent.full_name = "Test Agent"
        agent.is_active = True
        agent.status = "active"
        agent.specialty = "billing"
        return agent
    
    # ── Expertise Scoring Tests ─────────────────────────────────────
    
    def test_expertise_score_direct_match(self, scoring_service, mock_agent, mock_ticket):
        """Test that direct specialty match gives maximum expertise score."""
        mock_ticket.category = "billing"
        mock_agent.specialty = "billing"
        
        metrics = {}
        score, explanation = scoring_service._score_expertise(mock_agent, mock_ticket, metrics)
        
        assert score == FACTOR_WEIGHTS["expertise"]  # 40 points
        assert "Direct specialty match" in explanation
    
    def test_expertise_score_partial_match(self, scoring_service, mock_agent, mock_ticket):
        """Test partial specialty match gives reduced score."""
        mock_ticket.category = "billing"
        mock_agent.specialty = "billing-support"
        
        metrics = {}
        score, explanation = scoring_service._score_expertise(mock_agent, mock_ticket, metrics)
        
        # Should be 70% of max for partial match
        expected = FACTOR_WEIGHTS["expertise"] * 0.7
        assert score == expected
        assert "Partial specialty match" in explanation
    
    def test_expertise_score_no_match(self, scoring_service, mock_agent, mock_ticket):
        """Test no specialty match gives base score."""
        mock_ticket.category = "technical"
        mock_agent.specialty = "billing"
        
        metrics = {}
        score, explanation = scoring_service._score_expertise(mock_agent, mock_ticket, metrics)
        
        # Should be 20% of max for no match
        expected = FACTOR_WEIGHTS["expertise"] * 0.2
        assert score == expected
        assert "No specialty match" in explanation
    
    def test_expertise_score_with_category_performance(self, scoring_service, mock_agent, mock_ticket):
        """Test that historical category performance boosts score."""
        mock_ticket.category = "billing"
        mock_agent.specialty = None
        
        metrics = {
            "category_performance": {
                "billing": {"resolution_rate": 95.0}
            }
        }
        
        score, explanation = scoring_service._score_expertise(mock_agent, mock_ticket, metrics)
        
        # Should include bonus for excellent category performance
        assert score > FACTOR_WEIGHTS["expertise"] * 0.3
        assert "Excellent history" in explanation
    
    # ── Workload Scoring Tests ─────────────────────────────────────
    
    def test_workload_score_optimal(self, scoring_service):
        """Test optimal workload gives maximum score."""
        score, explanation = scoring_service._score_workload(3)
        
        assert score == FACTOR_WEIGHTS["workload"]  # 30 points
        assert "Optimal workload" in explanation
    
    def test_workload_score_at_capacity(self, scoring_service):
        """Test at capacity gives zero score."""
        score, explanation = scoring_service._score_workload(20)
        
        assert score == 0.0
        assert "At capacity" in explanation
    
    def test_workload_score_moderate(self, scoring_service):
        """Test moderate workload gives reduced score."""
        score, explanation = scoring_service._score_workload(10)
        
        # Should be roughly 50% of max (between optimal=5 and max=20)
        assert 0 < score < FACTOR_WEIGHTS["workload"]
        assert "Moderate workload" in explanation
    
    def test_workload_score_zero_tickets(self, scoring_service):
        """Test zero tickets gives full score."""
        score, explanation = scoring_service._score_workload(0)
        
        assert score == FACTOR_WEIGHTS["workload"]
    
    # ── Performance Scoring Tests ─────────────────────────────────────
    
    def test_performance_score_excellent(self, scoring_service):
        """Test excellent performance metrics."""
        metrics = {
            "resolution_rate": 95.0,
            "avg_csat": 4.8,
            "avg_confidence": 92.0,
        }
        
        score, explanation = scoring_service._score_performance(metrics)
        
        # Should be near maximum
        assert score >= FACTOR_WEIGHTS["performance"] * 0.9
        assert "Excellent resolution rate" in explanation
        assert "Excellent CSAT" in explanation
    
    def test_performance_score_poor(self, scoring_service):
        """Test poor performance metrics."""
        metrics = {
            "resolution_rate": 40.0,
            "avg_csat": 2.5,
            "avg_confidence": 50.0,
        }
        
        score, explanation = scoring_service._score_performance(metrics)
        
        # Should be low
        assert score < FACTOR_WEIGHTS["performance"] * 0.5
        assert "Below average" in explanation
    
    def test_performance_score_no_data(self, scoring_service):
        """Test with no performance data."""
        metrics = {}
        
        score, explanation = scoring_service._score_performance(metrics)
        
        # Should get default score
        assert score > 0
        assert "No" in explanation
    
    # ── Response Time Scoring Tests ─────────────────────────────────────
    
    def test_response_time_score_excellent(self, scoring_service):
        """Test excellent SLA compliance and response time."""
        metrics = {
            "sla_compliance_rate": 98.0,
            "avg_response_time_minutes": 3.0,
        }
        
        score, explanation = scoring_service._score_response_time(metrics)
        
        assert score == FACTOR_WEIGHTS["response_time"]  # 15 points
        assert "Excellent SLA compliance" in explanation
        assert "Excellent response time" in explanation
    
    def test_response_time_score_poor(self, scoring_service):
        """Test poor SLA compliance."""
        metrics = {
            "sla_compliance_rate": 50.0,
            "avg_response_time_minutes": 90.0,
        }
        
        score, explanation = scoring_service._score_response_time(metrics)
        
        assert score < FACTOR_WEIGHTS["response_time"] * 0.5
        assert "Below average" in explanation or "Slow" in explanation
    
    # ── Availability Scoring Tests ─────────────────────────────────────
    
    def test_availability_score_active(self, scoring_service, mock_agent):
        """Test active agent gets full availability score."""
        mock_agent.status = "active"
        mock_agent.is_active = True
        
        score, explanation = scoring_service._score_availability(mock_agent)
        
        assert score == FACTOR_WEIGHTS["availability"]  # 10 points
        assert "active and available" in explanation
    
    def test_availability_score_paused(self, scoring_service, mock_agent):
        """Test paused agent gets reduced score."""
        mock_agent.status = "paused"
        
        score, explanation = scoring_service._score_availability(mock_agent)
        
        assert score == FACTOR_WEIGHTS["availability"] * 0.3
        assert "paused" in explanation
    
    def test_availability_score_inactive(self, scoring_service, mock_agent):
        """Test inactive agent gets zero score."""
        mock_agent.is_active = False
        
        score, explanation = scoring_service._score_availability(mock_agent)
        
        assert score == 0.0
        assert "not active" in explanation
    
    # ── Full Score Calculation Tests ─────────────────────────────────────
    
    def test_full_score_calculation(self, scoring_service, mock_agent, mock_ticket):
        """Test complete score calculation with all factors."""
        # Mock database queries
        scoring_service.db.query.return_value.filter.return_value.first.return_value = mock_ticket
        scoring_service.db.query.return_value.filter.return_value.all.return_value = [mock_agent]
        
        # Mock internal methods
        with patch.object(scoring_service, '_get_agent_metrics') as mock_metrics, \
             patch.object(scoring_service, '_get_agent_workload') as mock_workload:
            
            mock_metrics.return_value = {
                "resolution_rate": 90.0,
                "avg_csat": 4.5,
                "avg_confidence": 85.0,
                "sla_compliance_rate": 95.0,
                "avg_response_time_minutes": 5.0,
                "category_performance": {},
            }
            mock_workload.return_value = 5
            
            result = scoring_service._score_agent(mock_agent, mock_ticket)
            
            assert "total_score" in result
            assert "normalized_score" in result
            assert "score_breakdown" in result
            assert 0 <= result["normalized_score"] <= 1.0
            
            # Verify all factors are present
            breakdown = result["score_breakdown"]
            assert "expertise" in breakdown
            assert "workload" in breakdown
            assert "performance" in breakdown
            assert "response_time" in breakdown
            assert "availability" in breakdown
    
    def test_explain_score(self, scoring_service, mock_agent, mock_ticket):
        """Test that explain_score includes detailed explanations."""
        with patch.object(scoring_service, '_get_agent_metrics') as mock_metrics, \
             patch.object(scoring_service, '_get_agent_workload') as mock_workload:
            
            mock_metrics.return_value = {
                "resolution_rate": 85.0,
                "avg_csat": 4.2,
                "avg_confidence": 80.0,
                "sla_compliance_rate": 90.0,
                "avg_response_time_minutes": 8.0,
                "category_performance": {},
            }
            mock_workload.return_value = 7
            
            result = scoring_service._score_agent(mock_agent, mock_ticket, include_explanation=True)
            
            assert "explanations" in result
            assert "expertise" in result["explanations"]
            assert "workload" in result["explanations"]
            assert "performance" in result["explanations"]
            assert "response_time" in result["explanations"]
            assert "availability" in result["explanations"]
    
    # ── Integration Tests ─────────────────────────────────────────
    
    def test_calculate_scores_returns_candidates(self, scoring_service, mock_ticket, mock_agent):
        """Test that calculate_scores returns proper structure."""
        # Mock database queries
        mock_query = Mock()
        mock_filter = Mock()
        mock_first = Mock()
        
        scoring_service.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = mock_ticket
        mock_filter.all.return_value = [mock_agent]
        
        with patch.object(scoring_service, '_get_available_agents') as mock_agents, \
             patch.object(scoring_service, '_score_agent') as mock_score:
            
            mock_agents.return_value = [mock_agent]
            mock_score.return_value = {
                "agent_id": mock_agent.id,
                "agent_name": mock_agent.full_name,
                "total_score": 0.85,
                "normalized_score": 0.85,
                "raw_score": 97.75,
                "score_breakdown": {},
            }
            
            result = scoring_service.calculate_scores("ticket-123")
            
            assert "ticket_id" in result
            assert "candidates" in result
            assert "recommended_assignee" in result
            assert result["scoring_method"] == "5-factor-ai"
    
    def test_get_best_assignee_with_threshold(self, scoring_service):
        """Test that get_best_assignee respects minimum score threshold."""
        with patch.object(scoring_service, 'calculate_scores') as mock_calc:
            mock_calc.return_value = {
                "recommended_assignee": {
                    "normalized_score": 0.25,  # Below threshold
                    "agent_id": "agent-123",
                }
            }
            
            result = scoring_service.get_best_assignee("ticket-123", min_score=0.3)
            
            # Should return None because score is below threshold
            assert result is None
    
    # ── Service Factory Tests ─────────────────────────────────────
    
    def test_get_assignment_scoring_service_caches(self, mock_db, mock_company_id):
        """Test that service factory caches instances."""
        service1 = get_assignment_scoring_service(mock_db, mock_company_id)
        service2 = get_assignment_scoring_service(mock_db, mock_company_id)
        
        # Should return same cached instance
        assert service1 is service2
    
    # ── Edge Cases ─────────────────────────────────────────
    
    def test_score_agent_with_no_metrics(self, scoring_service, mock_agent, mock_ticket):
        """Test scoring when agent has no historical metrics."""
        with patch.object(scoring_service, '_get_agent_metrics') as mock_metrics, \
             patch.object(scoring_service, '_get_agent_workload') as mock_workload:
            
            mock_metrics.return_value = {
                "resolution_rate": None,
                "avg_csat": None,
                "avg_confidence": None,
                "sla_compliance_rate": None,
                "avg_response_time_minutes": None,
                "category_performance": {},
            }
            mock_workload.return_value = 0
            
            result = scoring_service._score_agent(mock_agent, mock_ticket)
            
            # Should still produce a valid score with defaults
            assert result["normalized_score"] > 0
            assert result["normalized_score"] <= 1.0


class TestScoringWeights:
    """Test that scoring weights are correctly configured."""
    
    def test_max_score_is_sum_of_weights(self):
        """Verify MAX_SCORE equals sum of factor weights."""
        assert MAX_SCORE == sum(FACTOR_WEIGHTS.values())
    
    def test_weights_are_reasonable(self):
        """Verify weights follow expected distribution."""
        # Expertise should be highest weight
        assert FACTOR_WEIGHTS["expertise"] >= FACTOR_WEIGHTS["workload"]
        assert FACTOR_WEIGHTS["workload"] >= FACTOR_WEIGHTS["performance"]
        assert FACTOR_WEIGHTS["performance"] >= FACTOR_WEIGHTS["response_time"]
        assert FACTOR_WEIGHTS["response_time"] >= FACTOR_WEIGHTS["availability"]
        
        # Total should be 115 points
        assert MAX_SCORE == 115


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
