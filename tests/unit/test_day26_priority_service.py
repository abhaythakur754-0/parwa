"""
Day 26 Unit Tests - Priority Service

Tests for MF01: Priority auto-assignment with:
- Priority detection from keywords
- SLA target calculation
- Priority score calculation
- Escalation logic
"""

import pytest
from unittest.mock import MagicMock

from backend.app.services.priority_service import PriorityService
from database.models.tickets import Ticket, TicketPriority


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def priority_service(mock_db, mock_company_id):
    """Priority service instance."""
    return PriorityService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.reopen_count = 0
    ticket.sla_breached = False
    ticket.awaiting_human = False
    ticket.escalation_level = 1
    return ticket


# ── PRIORITY DETECTION TESTS ────────────────────────────────────────────────

class TestDetectPriority:
    """Tests for priority detection from text."""

    def test_detect_critical_keywords(self, priority_service):
        """Test detection of critical priority keywords."""
        priority, confidence = priority_service.detect_priority(
            "URGENT: Production is down and we need help immediately"
        )
        assert priority == TicketPriority.critical.value
        assert confidence > 0.7

    def test_detect_critical_outage(self, priority_service):
        """Test detection of critical outage keywords."""
        priority, confidence = priority_service.detect_priority(
            "System outage affecting all users"
        )
        assert priority == TicketPriority.critical.value

    def test_detect_critical_security_breach(self, priority_service):
        """Test detection of security breach keywords."""
        priority, confidence = priority_service.detect_priority(
            "We have a security breach in the system"
        )
        assert priority == TicketPriority.critical.value

    def test_detect_high_keywords(self, priority_service):
        """Test detection of high priority keywords."""
        priority, confidence = priority_service.detect_priority(
            "This is important and blocking our work"
        )
        assert priority == TicketPriority.high.value
        assert confidence > 0.6

    def test_detect_high_error(self, priority_service):
        """Test detection of error keywords."""
        priority, confidence = priority_service.detect_priority(
            "Getting an error when trying to save"
        )
        assert priority == TicketPriority.high.value

    def test_detect_low_keywords(self, priority_service):
        """Test detection of low priority keywords."""
        priority, confidence = priority_service.detect_priority(
            "No rush, just wondering about this feature"
        )
        assert priority == TicketPriority.low.value

    def test_detect_medium_default(self, priority_service):
        """Test default to medium priority."""
        priority, confidence = priority_service.detect_priority(
            "Hello I would like to know something"
        )
        # Default should be medium (no keywords matched)
        assert priority in [TicketPriority.medium.value, TicketPriority.low.value]

    def test_detect_priority_empty_text(self, priority_service):
        """Test detection with empty text."""
        priority, confidence = priority_service.detect_priority("")
        assert priority == TicketPriority.medium.value
        assert confidence == 0.5

    def test_detect_priority_none_text(self, priority_service):
        """Test detection with None text."""
        priority, confidence = priority_service.detect_priority(None)
        assert priority == TicketPriority.medium.value

    def test_detect_priority_multiple_critical_keywords(self, priority_service):
        """Test confidence increases with multiple keywords."""
        priority1, conf1 = priority_service.detect_priority("urgent")
        priority2, conf2 = priority_service.detect_priority(
            "urgent critical emergency immediately"
        )
        assert conf2 > conf1


# ── SLA TARGET TESTS ────────────────────────────────────────────────────────

class TestGetSLATarget:
    """Tests for SLA target calculation."""

    def test_sla_target_critical(self, priority_service):
        """Test SLA targets for critical priority."""
        targets = priority_service.get_sla_target(TicketPriority.critical.value)
        assert "first_response_minutes" in targets
        assert "resolution_minutes" in targets
        assert targets["first_response_minutes"] == 60

    def test_sla_target_high(self, priority_service):
        """Test SLA targets for high priority."""
        targets = priority_service.get_sla_target(TicketPriority.high.value)
        assert targets["first_response_minutes"] == 240
        assert targets["resolution_minutes"] == 1440

    def test_sla_target_medium(self, priority_service):
        """Test SLA targets for medium priority."""
        targets = priority_service.get_sla_target(TicketPriority.medium.value)
        assert targets["first_response_minutes"] == 720
        assert targets["resolution_minutes"] == 2880

    def test_sla_target_low(self, priority_service):
        """Test SLA targets for low priority."""
        targets = priority_service.get_sla_target(TicketPriority.low.value)
        assert targets["first_response_minutes"] == 1440
        assert targets["resolution_minutes"] == 4320

    def test_sla_target_growth_plan(self, priority_service):
        """Test SLA targets improve for growth plan."""
        starter_targets = priority_service.get_sla_target(
            TicketPriority.high.value, "starter"
        )
        growth_targets = priority_service.get_sla_target(
            TicketPriority.high.value, "growth"
        )
        assert growth_targets["first_response_minutes"] < starter_targets["first_response_minutes"]

    def test_sla_target_enterprise_plan(self, priority_service):
        """Test SLA targets are best for enterprise plan."""
        enterprise_targets = priority_service.get_sla_target(
            TicketPriority.critical.value, "enterprise"
        )
        assert enterprise_targets["first_response_minutes"] == 24  # 60 * 0.4

    def test_sla_target_unknown_plan(self, priority_service):
        """Test SLA targets for unknown plan defaults to starter."""
        targets = priority_service.get_sla_target(
            TicketPriority.medium.value, "unknown_plan"
        )
        assert targets["first_response_minutes"] == 720


# ── PRIORITY SCORE TESTS ────────────────────────────────────────────────────

class TestCalculatePriorityScore:
    """Tests for priority score calculation."""

    def test_priority_score_base_critical(self, priority_service):
        """Test base score for critical priority."""
        score = priority_service.calculate_priority_score(
            TicketPriority.critical.value
        )
        assert score == 100

    def test_priority_score_base_high(self, priority_service):
        """Test base score for high priority."""
        score = priority_service.calculate_priority_score(
            TicketPriority.high.value
        )
        assert score == 75

    def test_priority_score_base_medium(self, priority_service):
        """Test base score for medium priority."""
        score = priority_service.calculate_priority_score(
            TicketPriority.medium.value
        )
        assert score == 50

    def test_priority_score_base_low(self, priority_service):
        """Test base score for low priority."""
        score = priority_service.calculate_priority_score(
            TicketPriority.low.value
        )
        assert score == 25

    def test_priority_score_age_boost(self, priority_service):
        """Test score increases with age."""
        fresh_score = priority_service.calculate_priority_score(
            TicketPriority.medium.value, age_hours=0
        )
        old_score = priority_service.calculate_priority_score(
            TicketPriority.medium.value, age_hours=24
        )
        assert old_score > fresh_score

    def test_priority_score_reopen_boost(self, priority_service):
        """Test score increases with reopen count."""
        normal_score = priority_service.calculate_priority_score(
            TicketPriority.medium.value, reopen_count=0
        )
        reopened_score = priority_service.calculate_priority_score(
            TicketPriority.medium.value, reopen_count=2
        )
        assert reopened_score > normal_score

    def test_priority_score_capped(self, priority_service):
        """Test score is capped at 200."""
        score = priority_service.calculate_priority_score(
            TicketPriority.critical.value,
            age_hours=100,
            reopen_count=5
        )
        assert score <= 200


# ── ESCALATION TESTS ────────────────────────────────────────────────────────

class TestShouldEscalate:
    """Tests for escalation logic."""

    def test_should_escalate_multiple_reopens(self, priority_service, sample_ticket):
        """Test escalation due to multiple reopens."""
        sample_ticket.reopen_count = 2
        should, reason = priority_service.should_escalate(
            sample_ticket, TicketPriority.medium.value
        )
        assert should is True
        assert "reopened" in reason.lower()

    def test_should_escalate_sla_breached(self, priority_service, sample_ticket):
        """Test escalation due to SLA breach."""
        sample_ticket.sla_breached = True
        should, reason = priority_service.should_escalate(
            sample_ticket, TicketPriority.low.value
        )
        assert should is True
        assert "sla" in reason.lower()

    def test_should_escalate_awaiting_human(self, priority_service, sample_ticket):
        """Test escalation for awaiting human too long."""
        sample_ticket.awaiting_human = True
        sample_ticket.escalation_level = 1
        should, reason = priority_service.should_escalate(
            sample_ticket, TicketPriority.high.value
        )
        assert should is True

    def test_should_not_escalate_critical(self, priority_service, sample_ticket):
        """Test no escalation needed for critical priority."""
        sample_ticket.reopen_count = 0
        sample_ticket.sla_breached = False
        should, reason = priority_service.should_escalate(
            sample_ticket, TicketPriority.critical.value
        )
        assert should is False

    def test_should_not_escalate_max_level(self, priority_service, sample_ticket):
        """Test no escalation beyond max level."""
        sample_ticket.awaiting_human = True
        sample_ticket.escalation_level = 3  # Max level
        should, reason = priority_service.should_escalate(
            sample_ticket, TicketPriority.medium.value
        )
        assert should is False


# ── NEXT PRIORITY TESTS ──────────────────────────────────────────────────────

class TestGetNextPriority:
    """Tests for getting next priority level."""

    def test_next_priority_from_low(self, priority_service):
        """Test getting next priority from low."""
        next_priority = priority_service.get_next_priority(
            TicketPriority.low.value
        )
        assert next_priority == TicketPriority.medium.value

    def test_next_priority_from_medium(self, priority_service):
        """Test getting next priority from medium."""
        next_priority = priority_service.get_next_priority(
            TicketPriority.medium.value
        )
        assert next_priority == TicketPriority.high.value

    def test_next_priority_from_high(self, priority_service):
        """Test getting next priority from high."""
        next_priority = priority_service.get_next_priority(
            TicketPriority.high.value
        )
        assert next_priority == TicketPriority.critical.value

    def test_next_priority_from_critical(self, priority_service):
        """Test no next priority from critical."""
        next_priority = priority_service.get_next_priority(
            TicketPriority.critical.value
        )
        assert next_priority is None

    def test_next_priority_unknown(self, priority_service):
        """Test next priority for unknown value."""
        next_priority = priority_service.get_next_priority("unknown")
        assert next_priority is None
