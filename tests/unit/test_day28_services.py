"""
Day 28 Unit Tests - Ticket Search, Classification, Assignment Services

Tests for F-048, F-049, F-050:
- TicketSearchService: Full-text search, suggestions, recent searches
- ClassificationService: Intent/urgency classification, corrections
- AssignmentService: Auto-assignment, rules, manual assignment
"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.services.ticket_search_service import TicketSearchService
from backend.app.services.classification_service import (
    ClassificationService,
    IntentCategory,
    UrgencyLevel,
)
from backend.app.services.assignment_service import (
    AssignmentService,
    AssigneeType,
)
from backend.app.exceptions import NotFoundError, ValidationError
from database.base import Base
from database.models.tickets import (
    Ticket,
    TicketMessage,
    Customer,
    TicketIntent,
    ClassificationCorrection,
    TicketAssignment,
    AssignmentRule,
    TicketStatus,
    TicketPriority,
)
from database.models.core import User, Company


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def company_id():
    return str(uuid.uuid4())


@pytest.fixture
def user_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_company(db_session, company_id):
    """Create sample company."""
    company = Company(
        id=company_id,
        name="Test Company",
        industry="tech",
        subscription_tier="parwa",
        subscription_status="active",
    )
    db_session.add(company)
    db_session.commit()
    return company


@pytest.fixture
def sample_user(db_session, company_id, user_id):
    """Create sample user."""
    user = User(
        id=user_id,
        company_id=company_id,
        email="agent@test.com",
        full_name="Test Agent",
        role="agent",
        is_active=True,
        password_hash="hashed_password_123",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_customer(db_session, company_id):
    """Create sample customer."""
    customer = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        email="customer@test.com",
        name="Test Customer",
    )
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture
def sample_ticket(db_session, company_id, sample_customer):
    """Create sample ticket."""
    ticket = Ticket(
        id=str(uuid.uuid4()),
        company_id=company_id,
        customer_id=sample_customer.id,
        channel="email",
        status=TicketStatus.open.value,
        subject="Test ticket subject",
        priority=TicketPriority.medium.value,
        category="tech_support",
        tags=json.dumps(["test", "urgent"]),
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket


# ── TICKET SEARCH SERVICE TESTS ─────────────────────────────────────────────

class TestTicketSearchService:
    """Tests for TicketSearchService."""

    def test_search_basic(
        self, db_session, company_id, sample_ticket
    ):
        """Test basic search without query."""
        service = TicketSearchService(db_session, company_id)

        results, total, error = service.search()

        assert error is None
        assert total == 1
        assert len(results) == 1
        assert results[0]["id"] == sample_ticket.id

    def test_search_with_query(
        self, db_session, company_id, sample_ticket
    ):
        """Test search with query string."""
        service = TicketSearchService(db_session, company_id)

        results, total, error = service.search(query="Test")

        assert error is None
        assert total == 1
        assert len(results) == 1

    def test_search_with_filters(
        self, db_session, company_id, sample_ticket
    ):
        """Test search with filters."""
        service = TicketSearchService(db_session, company_id)

        # Filter by status
        results, total, error = service.search(
            status=[TicketStatus.open.value]
        )
        assert total == 1

        # Filter by priority
        results, total, error = service.search(
            priority=[TicketPriority.medium.value]
        )
        assert total == 1

        # Filter by non-matching status
        results, total, error = service.search(
            status=[TicketStatus.closed.value]
        )
        assert total == 0

    def test_search_tenant_isolation(
        self, db_session, company_id, sample_ticket
    ):
        """Test search respects tenant isolation."""
        other_company_id = str(uuid.uuid4())
        service = TicketSearchService(db_session, other_company_id)

        results, total, error = service.search()

        assert total == 0
        assert len(results) == 0

    def test_search_query_too_short(
        self, db_session, company_id
    ):
        """Test search rejects too short queries."""
        service = TicketSearchService(db_session, company_id)

        results, total, error = service.search(query="a")

        assert error is not None
        assert "at least" in error.lower()

    def test_search_query_sanitization(
        self, db_session, company_id, sample_ticket
    ):
        """Test search sanitizes query."""
        service = TicketSearchService(db_session, company_id)

        # Query with special characters should be sanitized
        results, total, error = service.search(query="Test; DROP TABLE tickets;")

        # Should not error, just sanitize (may not find results due to sanitization)
        assert error is None

    def test_search_pagination(
        self, db_session, company_id, sample_customer
    ):
        """Test search pagination."""
        # Create multiple tickets
        for i in range(25):
            ticket = Ticket(
                id=str(uuid.uuid4()),
                company_id=company_id,
                customer_id=sample_customer.id,
                channel="email",
                status=TicketStatus.open.value,
                subject=f"Test ticket {i}",
                priority=TicketPriority.medium.value,
            )
            db_session.add(ticket)
        db_session.commit()

        service = TicketSearchService(db_session, company_id)

        # Page 1
        results, total, error = service.search(page=1, page_size=10)
        assert total == 25
        assert len(results) == 10

        # Page 2
        results, total, error = service.search(page=2, page_size=10)
        assert len(results) == 10

        # Page 3
        results, total, error = service.search(page=3, page_size=10)
        assert len(results) == 5

    def test_search_sorting(
        self, db_session, company_id, sample_customer
    ):
        """Test search sorting."""
        # Create tickets with different priorities
        priorities = [
            TicketPriority.low.value,
            TicketPriority.critical.value,
            TicketPriority.high.value,
        ]
        for i, priority in enumerate(priorities):
            ticket = Ticket(
                id=str(uuid.uuid4()),
                company_id=company_id,
                customer_id=sample_customer.id,
                channel="email",
                status=TicketStatus.open.value,
                subject=f"Ticket {i}",
                priority=priority,
            )
            db_session.add(ticket)
        db_session.commit()

        service = TicketSearchService(db_session, company_id)

        # Sort by priority descending (critical first)
        results, total, error = service.search(
            sort_by="priority",
            sort_order="desc"
        )
        # Verify we have 3 results and priority sorting works
        assert total == 3
        # In descending order, critical should be first
        assert results[0]["priority"] == TicketPriority.critical.value

    def test_get_suggestions(
        self, db_session, company_id, sample_ticket
    ):
        """Test search suggestions."""
        service = TicketSearchService(db_session, company_id)

        suggestions = service.get_suggestions("test", limit=5)

        # Should find "Test" from ticket subject
        assert len(suggestions) >= 1

    def test_get_suggestions_too_short(
        self, db_session, company_id
    ):
        """Test suggestions reject short input."""
        service = TicketSearchService(db_session, company_id)

        suggestions = service.get_suggestions("a")

        assert len(suggestions) == 0

    def test_search_similarity(
        self, db_session, company_id, sample_ticket
    ):
        """Test similarity search."""
        service = TicketSearchService(db_session, company_id)

        similar = service.search_by_similarity(
            text="Test ticket subject",
            threshold=0.8,
            limit=5,
        )

        assert len(similar) >= 1
        assert similar[0]["similarity"] >= 0.8

    def test_calculate_similarity(
        self, db_session, company_id
    ):
        """Test similarity calculation."""
        service = TicketSearchService(db_session, company_id)

        # Identical strings
        assert service._calculate_similarity("test", "test") == 1.0

        # Completely different
        assert service._calculate_similarity("abc", "xyz") < 0.5

        # Similar
        assert service._calculate_similarity(
            "test ticket", "test tickets"
        ) > 0.8

    def test_highlight_match(
        self, db_session, company_id
    ):
        """Test match highlighting."""
        service = TicketSearchService(db_session, company_id)

        text = "This is a test message about tickets"
        highlighted = service._highlight_match(text, "test")

        assert "**test**" in highlighted

    def test_sanitize_query(
        self, db_session, company_id
    ):
        """Test query sanitization."""
        service = TicketSearchService(db_session, company_id)

        # Remove SQL injection attempts
        assert service._sanitize_query("test'; DROP TABLE;") == "test DROP TABLE"
        assert service._sanitize_query("test  \n  query") == "test query"


# ── CLASSIFICATION SERVICE TESTS ────────────────────────────────────────────

class TestClassificationService:
    """Tests for ClassificationService."""

    def test_classify_ticket(
        self, db_session, company_id, sample_ticket
    ):
        """Test ticket classification."""
        service = ClassificationService(db_session, company_id)

        result = service.classify(sample_ticket.id)

        assert "intent" in result
        assert "urgency" in result
        assert "confidence" in result
        assert result["intent"] in IntentCategory.ALL

    def test_classify_ticket_not_found(
        self, db_session, company_id
    ):
        """Test classification of non-existent ticket."""
        service = ClassificationService(db_session, company_id)

        with pytest.raises(NotFoundError):
            service.classify("non-existent-id")

    def test_classify_text_refund(
        self, db_session, company_id
    ):
        """Test classification of refund intent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="I want a refund for my purchase",
            message="Please return my money"
        )

        assert result["intent"] == IntentCategory.REFUND

    def test_classify_text_technical(
        self, db_session, company_id
    ):
        """Test classification of technical intent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Bug in the application",
            message="The system is not working, getting errors"
        )

        assert result["intent"] == IntentCategory.TECHNICAL

    def test_classify_text_billing(
        self, db_session, company_id
    ):
        """Test classification of billing intent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Invoice question",
            message="I have a billing issue with my subscription"
        )

        assert result["intent"] == IntentCategory.BILLING

    def test_classify_text_complaint(
        self, db_session, company_id
    ):
        """Test classification of complaint intent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Very unhappy with service",
            message="This is unacceptable! I want to speak to a manager!"
        )

        assert result["intent"] == IntentCategory.COMPLAINT

    def test_classify_text_feature_request(
        self, db_session, company_id
    ):
        """Test classification of feature request intent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Feature suggestion",
            message="It would be great if you could add dark mode"
        )

        assert result["intent"] == IntentCategory.FEATURE_REQUEST

    def test_classify_text_general(
        self, db_session, company_id
    ):
        """Test classification falls back to general."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Hello",
            message="Just saying hi"
        )

        assert result["intent"] == IntentCategory.GENERAL

    def test_classify_urgency_urgent(
        self, db_session, company_id
    ):
        """Test urgency classification for urgent."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="URGENT: Production down!",
            message="This is a critical emergency, need help ASAP"
        )

        assert result["urgency"] == UrgencyLevel.URGENT

    def test_classify_urgency_informational(
        self, db_session, company_id
    ):
        """Test urgency classification for informational."""
        service = ClassificationService(db_session, company_id)

        result = service.classify_text(
            subject="Question about pricing",
            message="I was wondering how the subscription works"
        )

        assert result["urgency"] == UrgencyLevel.INFORMATIONAL

    def test_suggest_priority(
        self, db_session, company_id
    ):
        """Test priority suggestion from classification."""
        service = ClassificationService(db_session, company_id)

        # Complaint should suggest higher priority
        priority = service._suggest_priority(
            IntentCategory.COMPLAINT,
            UrgencyLevel.URGENT
        )
        assert priority == TicketPriority.critical.value

        # Feature request should suggest lower priority
        priority = service._suggest_priority(
            IntentCategory.FEATURE_REQUEST,
            UrgencyLevel.INFORMATIONAL
        )
        assert priority == TicketPriority.low.value

    def test_record_correction(
        self, db_session, company_id, sample_ticket
    ):
        """Test recording classification correction."""
        service = ClassificationService(db_session, company_id)

        # First classify
        service.classify(sample_ticket.id)

        # Record correction
        correction = service.record_correction(
            ticket_id=sample_ticket.id,
            original_intent=IntentCategory.GENERAL,
            corrected_intent=IntentCategory.TECHNICAL,
            corrected_by="user-123",
            reason="More specific classification needed",
        )

        assert correction.original_intent == IntentCategory.GENERAL
        assert correction.corrected_intent == IntentCategory.TECHNICAL

    def test_get_corrections(
        self, db_session, company_id, sample_ticket
    ):
        """Test getting corrections list."""
        service = ClassificationService(db_session, company_id)

        # First classify the ticket
        service.classify(sample_ticket.id)

        # Add a correction
        service.record_correction(
            ticket_id=sample_ticket.id,
            original_intent=IntentCategory.GENERAL,
            corrected_intent=IntentCategory.TECHNICAL,
            corrected_by="test-user-id",
        )

        corrections, total = service.get_corrections()

        assert total >= 1
        assert len(corrections) >= 1

    def test_get_classification_stats(
        self, db_session, company_id, sample_ticket
    ):
        """Test getting classification statistics."""
        service = ClassificationService(db_session, company_id)

        # Classify ticket
        service.classify(sample_ticket.id)

        stats = service.get_classification_stats()

        assert "total_classifications" in stats
        assert "average_confidence" in stats
        assert stats["total_classifications"] >= 1

    def test_force_reclassify(
        self, db_session, company_id, sample_ticket
    ):
        """Test force reclassification."""
        service = ClassificationService(db_session, company_id)

        # Initial classification
        result1 = service.classify(sample_ticket.id)
        assert result1["already_classified"] == False

        # Without force, returns existing
        result2 = service.classify(sample_ticket.id)
        assert result2["already_classified"] == True

        # With force, reclassifies
        result3 = service.classify(sample_ticket.id, force_reclassify=True)
        assert result3["already_classified"] == False


# ── ASSIGNMENT SERVICE TESTS ────────────────────────────────────────────────

class TestAssignmentService:
    """Tests for AssignmentService."""

    def test_auto_assign(
        self, db_session, company_id, sample_ticket, sample_user
    ):
        """Test auto assignment."""
        service = AssignmentService(db_session, company_id)

        result = service.auto_assign(sample_ticket.id)

        assert result["assigned"] == True
        assert "assignee_id" in result
        assert "rule_name" in result

    def test_auto_assign_ticket_not_found(
        self, db_session, company_id
    ):
        """Test auto assign with non-existent ticket."""
        service = AssignmentService(db_session, company_id)

        with pytest.raises(NotFoundError):
            service.auto_assign("non-existent-id")

    def test_get_assignment_scores(
        self, db_session, company_id, sample_ticket, sample_user
    ):
        """Test getting assignment scores."""
        service = AssignmentService(db_session, company_id)

        result = service.get_assignment_scores(sample_ticket.id)

        assert "candidates" in result
        assert "recommended_assignee" in result
        assert result["scoring_method"] == "rule-based"

    def test_create_rule(
        self, db_session, company_id
    ):
        """Test creating assignment rule."""
        service = AssignmentService(db_session, company_id)

        rule = service.create_rule(
            name="Test Rule",
            conditions={"priority": ["critical"]},
            action={"assign_to_pool": "senior", "assignee_type": "human"},
            priority_order=1,
        )

        assert rule.name == "Test Rule"
        assert rule.priority_order == 1

    def test_create_rule_max_exceeded(
        self, db_session, company_id
    ):
        """Test max rules per company."""
        service = AssignmentService(db_session, company_id)

        # Create max rules
        for i in range(service.MAX_RULES_PER_COMPANY):
            service.create_rule(
                name=f"Rule {i}",
                conditions={},
                action={"assign_to_pool": "default"},
            )

        # Should fail on next
        with pytest.raises(ValidationError):
            service.create_rule(
                name="Extra Rule",
                conditions={},
                action={"assign_to_pool": "default"},
            )

    def test_create_rule_invalid_conditions(
        self, db_session, company_id
    ):
        """Test creating rule with invalid conditions."""
        service = AssignmentService(db_session, company_id)

        with pytest.raises(ValidationError):
            service.create_rule(
                name="Bad Rule",
                conditions={"invalid_key": ["value"]},
                action={"assign_to_pool": "default"},
            )

    def test_create_rule_invalid_action(
        self, db_session, company_id
    ):
        """Test creating rule with invalid action."""
        service = AssignmentService(db_session, company_id)

        with pytest.raises(ValidationError):
            service.create_rule(
                name="Bad Rule",
                conditions={},
                action={"invalid_action": "value"},
            )

    def test_update_rule(
        self, db_session, company_id
    ):
        """Test updating assignment rule."""
        service = AssignmentService(db_session, company_id)

        rule = service.create_rule(
            name="Test Rule",
            conditions={},
            action={"assign_to_pool": "default"},
        )

        updated = service.update_rule(
            rule_id=rule.id,
            name="Updated Rule",
            is_active=False,
        )

        assert updated.name == "Updated Rule"
        assert updated.is_active == False

    def test_update_rule_not_found(
        self, db_session, company_id
    ):
        """Test updating non-existent rule."""
        service = AssignmentService(db_session, company_id)

        with pytest.raises(NotFoundError):
            service.update_rule("non-existent-id", name="Test")

    def test_delete_rule(
        self, db_session, company_id
    ):
        """Test deleting assignment rule."""
        service = AssignmentService(db_session, company_id)

        rule = service.create_rule(
            name="Test Rule",
            conditions={},
            action={"assign_to_pool": "default"},
        )

        deleted = service.delete_rule(rule.id)
        assert deleted == True

        # Should not find deleted rule
        with pytest.raises(NotFoundError):
            service.delete_rule(rule.id)

    def test_list_rules(
        self, db_session, company_id
    ):
        """Test listing assignment rules."""
        service = AssignmentService(db_session, company_id)

        # Create rules
        for i in range(3):
            service.create_rule(
                name=f"Rule {i}",
                conditions={},
                action={"assign_to_pool": "default"},
                priority_order=i,
            )

        rules = service.list_rules()

        assert len(rules) >= 3

    def test_list_rules_include_inactive(
        self, db_session, company_id
    ):
        """Test listing rules including inactive."""
        service = AssignmentService(db_session, company_id)

        rule = service.create_rule(
            name="Inactive Rule",
            conditions={},
            action={"assign_to_pool": "default"},
            is_active=False,
        )

        # Without inactive
        active_rules = service.list_rules(include_inactive=False)
        assert not any(r["id"] == rule.id for r in active_rules)

        # With inactive
        all_rules = service.list_rules(include_inactive=True)
        assert any(r["id"] == rule.id for r in all_rules)

    def test_assign_to_user(
        self, db_session, company_id, sample_ticket, sample_user
    ):
        """Test manual assignment to user."""
        service = AssignmentService(db_session, company_id)

        result = service.assign_to_user(
            ticket_id=sample_ticket.id,
            assignee_id=sample_user.id,
            reason="Manual assignment for testing",
        )

        assert result["new_assignee"] == sample_user.id

    def test_assign_to_user_not_found(
        self, db_session, company_id, sample_ticket
    ):
        """Test assigning to non-existent user."""
        service = AssignmentService(db_session, company_id)

        with pytest.raises(NotFoundError):
            service.assign_to_user(
                ticket_id=sample_ticket.id,
                assignee_id="non-existent-user",
            )

    def test_assign_cross_tenant_user(
        self, db_session, company_id, sample_ticket
    ):
        """Test cannot assign to user from different company."""
        # Create user in different company
        other_company_id = str(uuid.uuid4())
        other_company = Company(
            id=other_company_id,
            name="Other Company",
            industry="tech",
            subscription_tier="mini_parwa",
            subscription_status="active",
        )
        db_session.add(other_company)
        db_session.flush()  # Ensure company exists

        other_user = User(
            id=str(uuid.uuid4()),
            company_id=other_company_id,
            email="other@user.com",
            is_active=True,
            password_hash="hashed_password_123",
            role="agent",
        )
        db_session.add(other_user)
        db_session.commit()

        service = AssignmentService(db_session, company_id)

        # This should raise NotFoundError because user is from different company
        with pytest.raises(NotFoundError):
            service.assign_to_user(
                ticket_id=sample_ticket.id,
                assignee_id=other_user.id,
            )

    def test_unassign(
        self, db_session, company_id, sample_ticket, sample_user
    ):
        """Test unassigning a ticket."""
        service = AssignmentService(db_session, company_id)

        # First assign
        service.assign_to_user(
            ticket_id=sample_ticket.id,
            assignee_id=sample_user.id,
        )

        # Then unassign
        result = service.unassign(sample_ticket.id)

        assert result["unassigned"] == True
        assert result["previous_assignee"] == sample_user.id

    def test_get_assignment_history(
        self, db_session, company_id, sample_ticket, sample_user
    ):
        """Test getting assignment history."""
        service = AssignmentService(db_session, company_id)

        # Make some assignments
        service.assign_to_user(
            ticket_id=sample_ticket.id,
            assignee_id=sample_user.id,
        )
        service.unassign(sample_ticket.id)
        service.auto_assign(sample_ticket.id)

        history = service.get_assignment_history(sample_ticket.id)

        assert len(history) >= 3

    def test_rule_matches_priority(
        self, db_session, company_id, sample_customer
    ):
        """Test rule matching by priority."""
        service = AssignmentService(db_session, company_id)

        # Create ticket with critical priority
        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=sample_customer.id,
            channel="email",
            status=TicketStatus.open.value,
            subject="Critical issue",
            priority=TicketPriority.critical.value,
        )
        db_session.add(ticket)
        db_session.commit()

        rule = service.create_rule(
            name="Critical Rule",
            conditions={"priority": ["critical"]},
            action={"assign_to_pool": "senior"},
            priority_order=1,
        )

        assert service._rule_matches(rule, ticket) == True

    def test_rule_matches_category(
        self, db_session, company_id, sample_customer
    ):
        """Test rule matching by category."""
        service = AssignmentService(db_session, company_id)

        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=sample_customer.id,
            channel="email",
            status=TicketStatus.open.value,
            subject="Billing question",
            priority=TicketPriority.medium.value,
            category="billing",
        )
        db_session.add(ticket)
        db_session.commit()

        rule = service.create_rule(
            name="Billing Rule",
            conditions={"category": ["billing"]},
            action={"assign_to_pool": "billing"},
            priority_order=10,
        )

        assert service._rule_matches(rule, ticket) == True

    def test_rule_no_match(
        self, db_session, company_id, sample_customer
    ):
        """Test rule not matching."""
        service = AssignmentService(db_session, company_id)

        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=sample_customer.id,
            channel="email",
            status=TicketStatus.open.value,
            subject="General question",
            priority=TicketPriority.low.value,
            category="general",
        )
        db_session.add(ticket)
        db_session.commit()

        rule = service.create_rule(
            name="Critical Only",
            conditions={"priority": ["critical"]},
            action={"assign_to_pool": "senior"},
        )

        assert service._rule_matches(rule, ticket) == False

    def test_rule_empty_conditions_matches_all(
        self, db_session, company_id, sample_ticket
    ):
        """Test rule with empty conditions matches all tickets."""
        service = AssignmentService(db_session, company_id)

        rule = service.create_rule(
            name="Catch-all",
            conditions={},
            action={"assign_to_pool": "default"},
        )

        assert service._rule_matches(rule, sample_ticket) == True

    def test_get_agent_ticket_count(
        self, db_session, company_id, sample_customer, sample_user
    ):
        """Test getting agent's current ticket count."""
        service = AssignmentService(db_session, company_id)

        # Create assigned tickets
        for i in range(3):
            ticket = Ticket(
                id=str(uuid.uuid4()),
                company_id=company_id,
                customer_id=sample_customer.id,
                channel="email",
                status=TicketStatus.open.value,
                subject=f"Ticket {i}",
                priority=TicketPriority.medium.value,
                assigned_to=sample_user.id,
            )
            db_session.add(ticket)
        db_session.commit()

        count = service._get_agent_ticket_count(sample_user.id)

        assert count == 3

    def test_default_rules_created(
        self, db_session, company_id
    ):
        """Test default rules are created when none exist."""
        service = AssignmentService(db_session, company_id)

        # Should have no rules initially
        rules = service.list_rules()
        assert len(rules) == 0

        # Trigger default rule creation
        default_rules = service._create_default_rules()

        assert len(default_rules) >= 4
        assert any(r.name == "Default to AI Agent" for r in default_rules)


# ── INTEGRATION TESTS ──────────────────────────────────────────────────────

class TestDay28Integration:
    """Integration tests for Day 28 services."""

    def test_search_classify_assign_flow(
        self, db_session, company_id, sample_customer
    ):
        """Test full flow: create -> search -> classify -> assign."""
        # Create a user first
        user = User(
            id=str(uuid.uuid4()),
            company_id=company_id,
            email="agent@test.com",
            full_name="Test Agent",
            role="agent",
            is_active=True,
            password_hash="hashed_password_123",
        )
        db_session.add(user)
        db_session.flush()

        # Create ticket
        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=sample_customer.id,
            channel="email",
            status=TicketStatus.open.value,
            subject="I want a refund for my broken product",
            priority=TicketPriority.medium.value,
        )
        db_session.add(ticket)
        db_session.commit()

        # Search
        search_service = TicketSearchService(db_session, company_id)
        results, total, _ = search_service.search(query="refund")
        assert total >= 1

        # Classify
        classify_service = ClassificationService(db_session, company_id)
        classification = classify_service.classify(ticket.id)
        assert classification["intent"] == IntentCategory.REFUND

        # Assign
        assign_service = AssignmentService(db_session, company_id)
        assignment = assign_service.auto_assign(ticket.id)
        assert assignment["assigned"] == True

    def test_tenant_isolation_all_services(
        self, db_session, company_id, sample_ticket
    ):
        """Test tenant isolation across all services."""
        other_company_id = str(uuid.uuid4())

        # Search
        search_service = TicketSearchService(db_session, other_company_id)
        results, total, _ = search_service.search()
        assert total == 0

        # Classification
        classify_service = ClassificationService(db_session, other_company_id)
        with pytest.raises(NotFoundError):
            classify_service.classify(sample_ticket.id)

        # Assignment
        assign_service = AssignmentService(db_session, other_company_id)
        with pytest.raises(NotFoundError):
            assign_service.auto_assign(sample_ticket.id)

    def test_classification_affects_assignment(
        self, db_session, company_id, sample_customer
    ):
        """Test classification affects assignment rules."""
        # Create complaint ticket
        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=sample_customer.id,
            channel="email",
            status=TicketStatus.open.value,
            subject="Terrible service, very disappointed!",
            priority=TicketPriority.medium.value,
        )
        db_session.add(ticket)
        db_session.commit()

        # Classify
        classify_service = ClassificationService(db_session, company_id)
        classification = classify_service.classify(ticket.id)
        assert classification["intent"] == IntentCategory.COMPLAINT

        # Complaints should get higher priority suggestion
        assert classification["suggested_priority"] in [
            TicketPriority.critical.value,
            TicketPriority.high.value,
        ]
