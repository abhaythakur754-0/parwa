"""
Week 41 Builder 5 - Enterprise Support Portal Tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestTicketManager:
    """Test ticket manager"""

    def test_manager_exists(self):
        """Test ticket manager exists"""
        from enterprise.support.ticket_manager import TicketManager
        assert TicketManager is not None

    def test_create_ticket(self):
        """Test creating ticket"""
        from enterprise.support.ticket_manager import TicketManager, TicketPriority, TicketStatus

        manager = TicketManager()
        ticket = manager.create_ticket(
            client_id="client_001",
            title="Test Issue",
            description="This is a test issue",
            priority=TicketPriority.HIGH
        )

        assert ticket.client_id == "client_001"
        assert ticket.title == "Test Issue"
        assert ticket.status == TicketStatus.OPEN

    def test_resolve_ticket(self):
        """Test resolving ticket"""
        from enterprise.support.ticket_manager import TicketManager, TicketStatus

        manager = TicketManager()
        ticket = manager.create_ticket("client_001", "Test", "Test")
        manager.resolve_ticket(ticket.ticket_id, "Resolved")

        assert ticket.status == TicketStatus.RESOLVED


class TestSLATracker:
    """Test SLA tracker"""

    def test_tracker_exists(self):
        """Test SLA tracker exists"""
        from enterprise.support.sla_tracker import SLATracker
        assert SLATracker is not None

    def test_set_client_sla(self):
        """Test setting client SLA"""
        from enterprise.support.sla_tracker import SLATracker, SLALevel

        tracker = SLATracker()
        tracker.set_client_sla("client_001", SLALevel.PREMIUM)

        target = tracker.get_sla_target("client_001")
        assert target.level == SLALevel.PREMIUM

    def test_check_sla(self):
        """Test checking SLA"""
        from enterprise.support.sla_tracker import SLATracker, SLALevel
        from datetime import datetime, timedelta

        tracker = SLATracker()
        tracker.set_client_sla("client_001", SLALevel.STANDARD)

        created = datetime.utcnow() - timedelta(hours=2)
        responded = datetime.utcnow()

        result = tracker.check_response_sla("client_001", created, responded)
        assert result is True


class TestEscalationManager:
    """Test escalation manager"""

    def test_manager_exists(self):
        """Test escalation manager exists"""
        from enterprise.support.escalation_manager import EscalationManager
        assert EscalationManager is not None

    def test_escalate(self):
        """Test escalation"""
        from enterprise.support.escalation_manager import EscalationManager, EscalationReason, EscalationLevel

        manager = EscalationManager()
        escalation = manager.escalate(
            ticket_id="tkt_001",
            client_id="client_001",
            reason=EscalationReason.PRIORITY
        )

        assert escalation.from_level == EscalationLevel.L1
        assert escalation.to_level == EscalationLevel.L2


class TestKnowledgeBase:
    """Test knowledge base"""

    def test_kb_exists(self):
        """Test knowledge base exists"""
        from enterprise.support.knowledge_base import KnowledgeBase
        assert KnowledgeBase is not None

    def test_create_article(self):
        """Test creating article"""
        from enterprise.support.knowledge_base import KnowledgeBase, ArticleType, ArticleStatus

        kb = KnowledgeBase()
        article = kb.create_article(
            title="How to reset password",
            content="Click on forgot password...",
            article_type=ArticleType.HOW_TO,
            category="account"
        )

        assert article.title == "How to reset password"
        assert article.status == ArticleStatus.DRAFT

    def test_search_articles(self):
        """Test searching articles"""
        from enterprise.support.knowledge_base import KnowledgeBase

        kb = KnowledgeBase()
        kb.create_article("Test Article", "This is test content")
        kb.publish_article(list(kb.articles.keys())[0])

        results = kb.search("test")
        assert len(results) > 0


class TestFeedbackCollector:
    """Test feedback collector"""

    def test_collector_exists(self):
        """Test feedback collector exists"""
        from enterprise.support.feedback_collector import FeedbackCollector
        assert FeedbackCollector is not None

    def test_submit_feedback(self):
        """Test submitting feedback"""
        from enterprise.support.feedback_collector import FeedbackCollector, FeedbackType, FeedbackRating

        collector = FeedbackCollector()
        feedback = collector.submit_feedback(
            client_id="client_001",
            title="Great service!",
            content="Very happy with the support",
            feedback_type=FeedbackType.GENERAL,
            rating=FeedbackRating.VERY_SATISFIED
        )

        assert feedback.client_id == "client_001"
        assert feedback.rating == FeedbackRating.VERY_SATISFIED

    def test_get_stats(self):
        """Test getting stats"""
        from enterprise.support.feedback_collector import FeedbackCollector
        from datetime import datetime, timedelta

        collector = FeedbackCollector()
        collector.submit_feedback("client_001", "Test", "Test")

        stats = collector.get_stats(
            "client_001",
            datetime.utcnow() - timedelta(days=1),
            datetime.utcnow() + timedelta(days=1)
        )

        assert stats.total_feedback == 1
