"""
Day 25 Schema Tests - Comprehensive validation tests for all new Pydantic schemas.

Tests cover:
- Field validation
- Required/optional fields
- Default values
- Computed properties
- Edge cases
"""

import pytest
from datetime import datetime
from decimal import Decimal


# ═══════════════════════════════════════════════════════════════════
# TICKET SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestTicketCreate:
    """Tests for TicketCreate schema."""

    def test_create_with_required_fields(self):
        from backend.app.schemas.ticket import TicketCreate
        ticket = TicketCreate(customer_id="cust_123", channel="email")
        assert ticket.customer_id == "cust_123"
        assert ticket.channel == "email"
        assert ticket.priority == "medium"  # default
        assert ticket.tags == []  # default
        assert ticket.metadata_json == {}  # default

    def test_create_with_all_fields(self):
        from backend.app.schemas.ticket import TicketCreate
        ticket = TicketCreate(
            subject="Help needed",
            customer_id="cust_123",
            channel="chat",
            priority="high",
            category="tech_support",
            tags=["urgent", "vip"],
            metadata_json={"source": "widget"}
        )
        assert ticket.subject == "Help needed"
        assert ticket.priority == "high"
        assert ticket.category == "tech_support"
        assert ticket.tags == ["urgent", "vip"]

    def test_priority_validation(self):
        from backend.app.schemas.ticket import TicketCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TicketCreate(customer_id="cust_123", channel="email", priority="invalid")

    def test_category_validation(self):
        from backend.app.schemas.ticket import TicketCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TicketCreate(customer_id="cust_123", channel="email", category="invalid")


class TestTicketUpdate:
    """Tests for TicketUpdate schema."""

    def test_update_partial(self):
        from backend.app.schemas.ticket import TicketUpdate
        update = TicketUpdate(priority="critical")
        assert update.priority == "critical"
        assert update.status is None
        assert update.category is None

    def test_update_all_fields(self):
        from backend.app.schemas.ticket import TicketUpdate
        update = TicketUpdate(
            priority="low",
            category="billing",
            tags=["resolved"],
            status="in_progress",
            assigned_to="user_456",
            subject="Updated subject"
        )
        assert update.priority == "low"
        assert update.status == "in_progress"


class TestTicketFilter:
    """Tests for TicketFilter schema."""

    def test_empty_filter(self):
        from backend.app.schemas.ticket import TicketFilter
        f = TicketFilter()
        assert f.status is None
        assert f.priority is None
        assert f.search is None

    def test_filter_with_lists(self):
        from backend.app.schemas.ticket import TicketFilter
        f = TicketFilter(
            status=["open", "in_progress"],
            priority=["high", "critical"],
            tags=["vip"]
        )
        assert f.status == ["open", "in_progress"]
        assert f.priority == ["high", "critical"]


class TestTicketAssign:
    """Tests for TicketAssign schema."""

    def test_assign_to_human(self):
        from backend.app.schemas.ticket import TicketAssign
        assign = TicketAssign(assignee_id="user_123", assignee_type="human")
        assert assign.assignee_type == "human"
        assert assign.assignee_id == "user_123"

    def test_assign_to_ai(self):
        from backend.app.schemas.ticket import TicketAssign
        assign = TicketAssign(assignee_type="ai")
        assert assign.assignee_type == "ai"

    def test_assignee_type_validation(self):
        from backend.app.schemas.ticket import TicketAssign
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TicketAssign(assignee_type="invalid")


# ═══════════════════════════════════════════════════════════════════
# MESSAGE SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestMessageCreate:
    """Tests for MessageCreate schema."""

    def test_create_customer_message(self):
        from backend.app.schemas.ticket_message import MessageCreate
        msg = MessageCreate(
            content="I need help with my order",
            role="customer",
            channel="email"
        )
        assert msg.content == "I need help with my order"
        assert msg.role == "customer"
        assert msg.is_internal is False

    def test_create_internal_message(self):
        from backend.app.schemas.ticket_message import MessageCreate
        msg = MessageCreate(
            content="Internal note",
            role="agent",
            channel="web",
            is_internal=True
        )
        assert msg.is_internal is True

    def test_role_validation(self):
        from backend.app.schemas.ticket_message import MessageCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MessageCreate(content="Test", role="invalid", channel="email")

    def test_content_required(self):
        from backend.app.schemas.ticket_message import MessageCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MessageCreate(role="customer", channel="email")

    def test_empty_content_rejected(self):
        from backend.app.schemas.ticket_message import MessageCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MessageCreate(content="   ", role="customer", channel="email")


class TestAttachmentUpload:
    """Tests for AttachmentUpload schema."""

    def test_valid_attachment(self):
        from backend.app.schemas.ticket_message import AttachmentUpload
        att = AttachmentUpload(
            filename="document.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_url="https://example.com/files/doc.pdf"
        )
        assert att.filename == "document.pdf"
        assert att.file_size == 1024

    def test_file_size_must_be_positive(self):
        from backend.app.schemas.ticket_message import AttachmentUpload
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AttachmentUpload(
                filename="doc.pdf",
                file_size=0,
                mime_type="application/pdf",
                file_url="https://example.com/doc.pdf"
            )


# ═══════════════════════════════════════════════════════════════════
# SLA SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestSLAPolicyCreate:
    """Tests for SLAPolicyCreate schema."""

    def test_create_policy(self):
        from backend.app.schemas.sla import SLAPolicyCreate
        policy = SLAPolicyCreate(
            plan_tier="mini_parwa",
            priority="high",
            first_response_minutes=240,
            resolution_minutes=1440,
            update_frequency_minutes=60
        )
        assert policy.plan_tier == "mini_parwa"
        assert policy.priority == "high"
        assert policy.first_response_minutes == 240

    def test_minutes_must_be_positive(self):
        from backend.app.schemas.sla import SLAPolicyCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SLAPolicyCreate(
                plan_tier="mini_parwa",
                priority="high",
                first_response_minutes=0,
                resolution_minutes=1440,
                update_frequency_minutes=60
            )

    def test_priority_validation(self):
        from backend.app.schemas.sla import SLAPolicyCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SLAPolicyCreate(
                plan_tier="mini_parwa",
                priority="urgent",
                first_response_minutes=60,
                resolution_minutes=240,
                update_frequency_minutes=30
            )


# ═══════════════════════════════════════════════════════════════════
# ASSIGNMENT SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestAssignmentRuleCreate:
    """Tests for AssignmentRuleCreate schema."""

    def test_create_rule(self):
        from backend.app.schemas.assignment import AssignmentRuleCreate
        rule = AssignmentRuleCreate(
            name="Route billing to finance",
            conditions={"category": "billing"},
            action={"assign_to_team": "finance"}
        )
        assert rule.name == "Route billing to finance"
        assert rule.priority_order == 0  # default
        assert rule.is_active is True  # default

    def test_rule_with_priority(self):
        from backend.app.schemas.assignment import AssignmentRuleCreate
        rule = AssignmentRuleCreate(
            name="VIP routing",
            conditions={"tags": ["vip"]},
            action={"assign_to": "senior_agent"},
            priority_order=10
        )
        assert rule.priority_order == 10


class TestAssignmentScore:
    """Tests for AssignmentScore schema."""

    def test_score_result(self):
        from backend.app.schemas.assignment import AssignmentScore
        score = AssignmentScore(
            ticket_id="ticket_123",
            candidate_scores={"user_1": 0.85, "user_2": 0.72},
            final_assignee_id="user_1",
            final_assignee_type="human",
            reason="Best match based on skills"
        )
        assert score.final_assignee_id == "user_1"
        assert score.candidate_scores["user_1"] == 0.85


# ═══════════════════════════════════════════════════════════════════
# BULK ACTION SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestBulkActionRequest:
    """Tests for BulkActionRequest schema."""

    def test_bulk_status_change(self):
        from backend.app.schemas.bulk_action import BulkActionRequest
        req = BulkActionRequest(
            action_type="status_change",
            ticket_ids=["t1", "t2", "t3"],
            params={"new_status": "resolved"}
        )
        assert req.action_type == "status_change"
        assert len(req.ticket_ids) == 3

    def test_max_tickets_validation(self):
        from backend.app.schemas.bulk_action import BulkActionRequest
        from pydantic import ValidationError
        # More than 500 tickets should fail
        with pytest.raises(ValidationError):
            BulkActionRequest(
                action_type="status_change",
                ticket_ids=[f"t{i}" for i in range(501)],
                params={"new_status": "resolved"}
            )


class TestTicketMergeRequest:
    """Tests for TicketMergeRequest schema."""

    def test_merge_request(self):
        from backend.app.schemas.bulk_action import TicketMergeRequest
        req = TicketMergeRequest(
            primary_ticket_id="ticket_1",
            merged_ticket_ids=["ticket_2", "ticket_3"],
            reason="Duplicate tickets"
        )
        assert req.primary_ticket_id == "ticket_1"
        assert len(req.merged_ticket_ids) == 2


# ═══════════════════════════════════════════════════════════════════
# NOTIFICATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestNotificationTemplateCreate:
    """Tests for NotificationTemplateCreate schema."""

    def test_create_email_template(self):
        from backend.app.schemas.notification import NotificationTemplateCreate
        template = NotificationTemplateCreate(
            event_type="ticket.created",
            channel="email",
            subject_template="New ticket: {{ticket.subject}}",
            body_template="A new ticket has been created..."
        )
        assert template.event_type == "ticket.created"
        assert template.channel == "email"
        assert template.is_active is True

    def test_channel_validation(self):
        from backend.app.schemas.notification import NotificationTemplateCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NotificationTemplateCreate(
                event_type="ticket.created",
                channel="invalid",
                body_template="Test"
            )


# ═══════════════════════════════════════════════════════════════════
# CUSTOMER SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class TestCustomerCreate:
    """Tests for CustomerCreate schema."""

    def test_create_with_email(self):
        from backend.app.schemas.customer import CustomerCreate
        customer = CustomerCreate(
            email="john@example.com",
            name="John Doe"
        )
        assert customer.email == "john@example.com"
        assert customer.name == "John Doe"

    def test_create_with_phone(self):
        from backend.app.schemas.customer import CustomerCreate
        customer = CustomerCreate(
            phone="+1234567890",
            name="Jane Doe"
        )
        assert customer.phone == "+1234567890"


class TestIdentityMatchRequest:
    """Tests for IdentityMatchRequest schema."""

    def test_match_with_email(self):
        from backend.app.schemas.customer import IdentityMatchRequest
        req = IdentityMatchRequest(email="test@example.com")
        assert req.email == "test@example.com"

    def test_at_least_one_field_required(self):
        from backend.app.schemas.customer import IdentityMatchRequest
        from pydantic import ValidationError
        # All empty should fail
        with pytest.raises(ValidationError):
            IdentityMatchRequest()


class TestCustomerChannelCreate:
    """Tests for CustomerChannelCreate schema."""

    def test_create_channel_link(self):
        from backend.app.schemas.customer import CustomerChannelCreate
        link = CustomerChannelCreate(
            customer_id="cust_123",
            channel_type="whatsapp",
            external_id="+1234567890"
        )
        assert link.channel_type == "whatsapp"
        assert link.is_verified is False  # default
