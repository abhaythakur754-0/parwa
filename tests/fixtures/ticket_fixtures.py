"""
PARWA Shared Test Fixtures (Day 35)

Comprehensive fixtures for ticket system testing.
These fixtures are shared across all test files to ensure consistency.

Usage:
    from tests.fixtures.ticket_fixtures import *
"""

import json
import uuid
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any, Optional

# Models
from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketAssignment,
    TicketStatusChange,
    TicketAttachment,
    TicketIntent,
    TicketMerge,
    TicketInternalNote,
    TicketFeedback,
    Customer,
    CustomerChannel,
    IdentityMatchLog,
    SLAPolicy,
    SLATimer,
    AssignmentRule,
    BulkActionFailure,
    BulkActionLog,
    NotificationTemplate,
    TicketTrigger,
    CustomField,
    TicketStatus,
    TicketPriority,
    TicketCategory,
)
from database.models.core import User, Company


# ── DATABASE FIXTURES ────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """
    Mock database session with common methods.
    Each test gets a fresh mock to avoid state leakage.
    """
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    db.flush = MagicMock()

    # Create a chain-able query mock
    def create_query_mock(*args, **kwargs):
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.filter_by = MagicMock(return_value=mock_query)
        mock_query.join = MagicMock(return_value=mock_query)
        mock_query.outerjoin = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.offset = MagicMock(return_value=mock_query)
        mock_query.group_by = MagicMock(return_value=mock_query)
        mock_query.having = MagicMock(return_value=mock_query)
        mock_query.distinct = MagicMock(return_value=mock_query)
        return mock_query

    db.query = MagicMock(side_effect=create_query_mock)
    return db


@pytest.fixture
def mock_db_session(mock_db):
    """Alias for mock_db for clarity."""
    return mock_db


# ── COMPANY FIXTURES ─────────────────────────────────────────────────────────

@pytest.fixture
def company_id():
    """Standard test company ID."""
    return "test-company-123"


@pytest.fixture
def other_company_id():
    """Different company ID for isolation tests."""
    return "other-company-456"


@pytest.fixture
def mock_company():
    """Mock company object."""
    company = Company()
    company.id = "test-company-123"
    company.name = "Test Company"
    company.plan_tier = "growth"
    company.is_suspended = False
    company.created_at = datetime.utcnow()
    return company


# ── USER FIXTURES ────────────────────────────────────────────────────────────

@pytest.fixture
def user_id():
    """Standard test user ID."""
    return "user-123"


@pytest.fixture
def agent_id():
    """Standard test agent ID."""
    return "agent-456"


@pytest.fixture
def customer_user_id():
    """Standard test customer user ID."""
    return "customer-user-789"


@pytest.fixture
def mock_user():
    """Mock user object."""
    user = User()
    user.id = "user-123"
    user.company_id = "test-company-123"
    user.email = "user@example.com"
    user.name = "Test User"
    user.role = "agent"
    user.is_active = True
    user.created_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_agent():
    """Mock agent user object."""
    agent = User()
    agent.id = "agent-456"
    agent.company_id = "test-company-123"
    agent.email = "agent@example.com"
    agent.name = "Test Agent"
    agent.role = "agent"
    agent.is_active = True
    agent.created_at = datetime.utcnow()
    return agent


# ── CUSTOMER FIXTURES ────────────────────────────────────────────────────────

@pytest.fixture
def customer_id():
    """Standard test customer ID."""
    return "customer-789"


@pytest.fixture
def mock_customer():
    """Mock customer object."""
    customer = Customer()
    customer.id = "customer-789"
    customer.company_id = "test-company-123"
    customer.email = "customer@example.com"
    customer.name = "Test Customer"
    customer.phone = "+1234567890"
    customer.external_id = "ext-123"
    customer.metadata_json = "{}"
    customer.created_at = datetime.utcnow()
    customer.updated_at = datetime.utcnow()
    return customer


@pytest.fixture
def mock_customer_channel(mock_customer):
    """Mock customer channel object."""
    channel = CustomerChannel()
    channel.id = "channel-123"
    channel.customer_id = mock_customer.id
    channel.company_id = mock_customer.company_id
    channel.channel_type = "email"
    channel.external_id = "customer@example.com"
    channel.is_primary = True
    channel.created_at = datetime.utcnow()
    return channel


# ── TICKET FIXTURES ──────────────────────────────────────────────────────────

@pytest.fixture
def ticket_id():
    """Standard test ticket ID."""
    return "ticket-123"


@pytest.fixture
def mock_ticket(company_id, customer_id):
    """Mock ticket object with default values."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = company_id
    ticket.customer_id = customer_id
    ticket.channel = "email"
    ticket.status = TicketStatus.open.value
    ticket.subject = "Test ticket subject"
    ticket.priority = TicketPriority.medium.value
    ticket.category = TicketCategory.tech_support.value
    ticket.tags = "[]"
    ticket.assigned_to = None
    ticket.reopen_count = 0
    ticket.frozen = False
    ticket.is_spam = False
    ticket.awaiting_human = False
    ticket.awaiting_client = False
    ticket.escalation_level = 1
    ticket.sla_breached = False
    ticket.parent_ticket_id = None
    ticket.duplicate_of_id = None
    ticket.metadata_json = "{}"
    ticket.plan_snapshot = "growth"
    ticket.variant_version = "v1"
    ticket.client_timezone = "UTC"
    ticket.created_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    ticket.first_response_at = None
    ticket.resolution_target_at = None
    ticket.closed_at = None
    return ticket


@pytest.fixture
def mock_ticket_assigned(mock_ticket, agent_id):
    """Mock ticket in assigned status."""
    mock_ticket.status = TicketStatus.assigned.value
    mock_ticket.assigned_to = agent_id
    return mock_ticket


@pytest.fixture
def mock_ticket_in_progress(mock_ticket_assigned):
    """Mock ticket in progress."""
    mock_ticket_assigned.status = TicketStatus.in_progress.value
    return mock_ticket_assigned


@pytest.fixture
def mock_ticket_resolved(mock_ticket):
    """Mock resolved ticket."""
    mock_ticket.status = TicketStatus.resolved.value
    mock_ticket.resolved_at = datetime.utcnow()
    return mock_ticket


@pytest.fixture
def mock_ticket_closed(mock_ticket_resolved):
    """Mock closed ticket."""
    mock_ticket_resolved.status = TicketStatus.closed.value
    mock_ticket_resolved.closed_at = datetime.utcnow()
    return mock_ticket_resolved


@pytest.fixture
def mock_ticket_reopened(mock_ticket_closed):
    """Mock reopened ticket."""
    mock_ticket_closed.status = TicketStatus.reopened.value
    mock_ticket_closed.reopen_count = 1
    return mock_ticket_closed


@pytest.fixture
def mock_ticket_frozen(mock_ticket):
    """Mock frozen ticket."""
    mock_ticket.status = TicketStatus.frozen.value
    mock_ticket.frozen = True
    return mock_ticket


@pytest.fixture
def mock_ticket_awaiting_client(mock_ticket):
    """Mock ticket awaiting client response."""
    mock_ticket.status = TicketStatus.awaiting_client.value
    mock_ticket.awaiting_client = True
    return mock_ticket


@pytest.fixture
def mock_ticket_awaiting_human(mock_ticket):
    """Mock ticket awaiting human agent."""
    mock_ticket.status = TicketStatus.awaiting_human.value
    mock_ticket.awaiting_human = True
    return mock_ticket


@pytest.fixture
def mock_ticket_spam(mock_ticket):
    """Mock ticket marked as spam."""
    mock_ticket.is_spam = True
    mock_ticket.status = TicketStatus.closed.value
    return mock_ticket


@pytest.fixture
def mock_ticket_escalated(mock_ticket):
    """Mock escalated ticket."""
    mock_ticket.escalation_level = 2
    return mock_ticket


@pytest.fixture
def mock_ticket_sla_breached(mock_ticket):
    """Mock ticket with SLA breach."""
    mock_ticket.sla_breached = True
    return mock_ticket


# ── TICKET MESSAGE FIXTURES ──────────────────────────────────────────────────

@pytest.fixture
def message_id():
    """Standard test message ID."""
    return "message-123"


@pytest.fixture
def mock_ticket_message(ticket_id, customer_id):
    """Mock ticket message."""
    message = TicketMessage()
    message.id = "message-123"
    message.ticket_id = ticket_id
    message.company_id = "test-company-123"
    message.content = "This is a test message"
    message.role = "customer"
    message.channel = "email"
    message.is_internal = False
    message.is_edited = False
    message.edited_at = None
    message.created_at = datetime.utcnow()
    message.sender_id = customer_id
    return message


@pytest.fixture
def mock_agent_message(ticket_id, agent_id):
    """Mock agent message."""
    message = TicketMessage()
    message.id = "agent-message-123"
    message.ticket_id = ticket_id
    message.company_id = "test-company-123"
    message.content = "This is an agent response"
    message.role = "agent"
    message.channel = "email"
    message.is_internal = False
    message.is_edited = False
    message.created_at = datetime.utcnow()
    message.sender_id = agent_id
    return message


@pytest.fixture
def mock_internal_note(ticket_id, agent_id):
    """Mock internal note."""
    note = TicketMessage()
    note.id = "note-123"
    note.ticket_id = ticket_id
    note.company_id = "test-company-123"
    note.content = "This is an internal note"
    note.role = "agent"
    note.channel = "internal"
    note.is_internal = True
    note.is_edited = False
    note.created_at = datetime.utcnow()
    note.sender_id = agent_id
    return note


# ── SLA FIXTURES ──────────────────────────────────────────────────────────────

@pytest.fixture
def sla_policy_id():
    """Standard test SLA policy ID."""
    return "sla-policy-123"


@pytest.fixture
def mock_sla_policy(company_id):
    """Mock SLA policy."""
    policy = SLAPolicy()
    policy.id = "sla-policy-123"
    policy.company_id = company_id
    policy.plan_tier = "growth"
    policy.priority = TicketPriority.medium.value
    policy.first_response_minutes = 240  # 4 hours
    policy.resolution_minutes = 1440  # 24 hours
    policy.update_frequency_minutes = 480  # 8 hours
    policy.is_active = True
    policy.created_at = datetime.utcnow()
    return policy


@pytest.fixture
def mock_sla_timer(ticket_id, sla_policy_id):
    """Mock SLA timer."""
    timer = SLATimer()
    timer.id = "timer-123"
    timer.ticket_id = ticket_id
    timer.policy_id = sla_policy_id
    timer.company_id = "test-company-123"
    timer.first_response_at = None
    timer.first_response_target = datetime.utcnow() + timedelta(hours=4)
    timer.resolution_target = datetime.utcnow() + timedelta(hours=24)
    timer.is_breached = False
    timer.breached_at = None
    timer.resolved_at = None
    timer.created_at = datetime.utcnow()
    return timer


@pytest.fixture
def mock_sla_timer_breached(mock_sla_timer):
    """Mock breached SLA timer."""
    mock_sla_timer.is_breached = True
    mock_sla_timer.breached_at = datetime.utcnow() - timedelta(hours=1)
    return mock_sla_timer


@pytest.fixture
def mock_sla_timer_approaching(mock_sla_timer):
    """Mock SLA timer approaching breach (75% elapsed)."""
    mock_sla_timer.resolution_target = datetime.utcnow() + timedelta(hours=6)
    return mock_sla_timer


# ── ASSIGNMENT FIXTURES ───────────────────────────────────────────────────────

@pytest.fixture
def assignment_rule_id():
    """Standard test assignment rule ID."""
    return "rule-123"


@pytest.fixture
def mock_assignment_rule(company_id):
    """Mock assignment rule."""
    rule = AssignmentRule()
    rule.id = "rule-123"
    rule.company_id = company_id
    rule.name = "Billing to billing team"
    rule.description = "Route billing tickets to billing team"
    rule.conditions = json.dumps({
        "category": "billing",
        "priority": ["high", "critical"]
    })
    rule.action = json.dumps({
        "type": "assign_to_team",
        "team": "billing"
    })
    rule.priority_order = 1
    rule.is_active = True
    rule.created_at = datetime.utcnow()
    return rule


@pytest.fixture
def mock_ticket_assignment(ticket_id, agent_id):
    """Mock ticket assignment record."""
    assignment = TicketAssignment()
    assignment.id = "assignment-123"
    assignment.ticket_id = ticket_id
    assignment.company_id = "test-company-123"
    assignment.assigned_to = agent_id
    assignment.assigned_by = "system"
    assignment.assignment_type = "auto"
    assignment.rule_id = None
    assignment.score = 0.85
    assignment.assigned_at = datetime.utcnow()
    assignment.unassigned_at = None
    return assignment


# ── NOTIFICATION FIXTURES ─────────────────────────────────────────────────────

@pytest.fixture
def notification_id():
    """Standard test notification ID."""
    return "notification-123"


@pytest.fixture
def mock_notification(user_id):
    """Mock notification (using MagicMock since Notification model doesn't exist yet)."""
    notification = MagicMock()
    notification.id = "notification-123"
    notification.company_id = "test-company-123"
    notification.user_id = user_id
    notification.notification_type = "ticket_assigned"
    notification.title = "Ticket assigned to you"
    notification.message = "You have been assigned a new ticket"
    notification.channel = "in_app"
    notification.data = json.dumps({"ticket_id": "ticket-123"})
    notification.is_read = False
    notification.read_at = None
    notification.created_at = datetime.utcnow()
    return notification


@pytest.fixture
def mock_notification_template():
    """Mock notification template."""
    template = NotificationTemplate()
    template.id = "template-123"
    template.company_id = "test-company-123"
    template.event_type = "ticket_created"
    template.channel = "email"
    template.subject_template = "New ticket: {{ticket.subject}}"
    template.body_template = "A new ticket has been created by {{customer.name}}"
    template.is_active = True
    template.created_at = datetime.utcnow()
    return template


@pytest.fixture
def mock_notification_preference(user_id):
    """Mock notification preference (using MagicMock since model doesn't exist yet)."""
    pref = MagicMock()
    pref.id = "pref-123"
    pref.company_id = "test-company-123"
    pref.user_id = user_id
    pref.event_type = "ticket_assigned"
    pref.channels = json.dumps(["email", "in_app"])
    pref.enabled = True
    pref.digest_mode = "instant"
    return pref


# ── TEMPLATE & TRIGGER FIXTURES ───────────────────────────────────────────────

@pytest.fixture
def template_id():
    """Standard test template ID."""
    return "template-123"


@pytest.fixture
def mock_template(company_id):
    """Mock response template (using MagicMock since Template model doesn't exist yet)."""
    template = MagicMock()
    template.id = "template-123"
    template.company_id = company_id
    template.name = "Billing Refund"
    template.content = "Hello {{customer.name}}, we have processed your refund."
    template.category = "billing"
    template.variables = json.dumps(["customer.name"])
    template.is_active = True
    template.use_count = 0
    template.created_at = datetime.utcnow()
    return template


@pytest.fixture
def trigger_id():
    """Standard test trigger ID."""
    return "trigger-123"


@pytest.fixture
def mock_trigger(company_id):
    """Mock automation trigger using TicketTrigger model."""
    trigger = TicketTrigger()
    trigger.id = "trigger-123"
    trigger.company_id = company_id
    trigger.name = "Auto-close resolved tickets"
    trigger.description = "Auto-close tickets after 7 days resolved"
    trigger.conditions = json.dumps({
        "events": ["ticket_resolved"],
        "status": "resolved",
        "days_since_resolved": 7
    })
    trigger.action = json.dumps({
        "change_status": "closed"
    })
    trigger.is_active = True
    trigger.priority_order = 10
    trigger.created_at = datetime.utcnow()
    return trigger


# ── CUSTOM FIELD FIXTURES ────────────────────────────────────────────────────

@pytest.fixture
def custom_field_id():
    """Standard test custom field ID."""
    return "field-123"


@pytest.fixture
def mock_custom_field(company_id):
    """Mock custom field definition."""
    field = CustomField()
    field.id = "field-123"
    field.company_id = company_id
    field.name = "Invoice Number"
    field.field_key = "invoice_number"
    field.field_type = "text"
    field.config = json.dumps({"category": "billing"})
    field.applicable_categories = json.dumps(["billing"])
    field.is_required = False
    field.is_active = True
    field.sort_order = 0
    field.created_at = datetime.utcnow()
    return field


# ── BULK ACTION FIXTURES ─────────────────────────────────────────────────────

@pytest.fixture
def bulk_action_id():
    """Standard test bulk action ID."""
    return "bulk-123"


@pytest.fixture
def mock_bulk_action(company_id, user_id):
    """Mock bulk action using BulkActionLog model."""
    action = BulkActionLog()
    action.id = "bulk-123"
    action.company_id = company_id
    action.action_type = "status_change"
    action.ticket_ids = json.dumps(["ticket-1", "ticket-2", "ticket-3"])
    action.performed_by = user_id
    action.result_summary = json.dumps({"status": "completed", "success_count": 3, "failure_count": 0})
    action.undo_token = "undo-token-abc"
    action.undone = False
    action.created_at = datetime.utcnow()
    return action


@pytest.fixture
def mock_bulk_action_failure(bulk_action_id):
    """Mock bulk action failure."""
    failure = BulkActionFailure()
    failure.id = "failure-123"
    failure.bulk_action_id = bulk_action_id
    failure.ticket_id = "ticket-failed"
    failure.error_message = "Ticket not found"
    failure.created_at = datetime.utcnow()
    return failure


# ── TICKET MERGE FIXTURES ────────────────────────────────────────────────────

@pytest.fixture
def merge_id():
    """Standard test merge ID."""
    return "merge-123"


@pytest.fixture
def mock_ticket_merge(company_id, ticket_id, user_id):
    """Mock ticket merge record."""
    merge = TicketMerge()
    merge.id = "merge-123"
    merge.company_id = company_id
    merge.primary_ticket_id = ticket_id
    merge.merged_ticket_ids = json.dumps(["ticket-2", "ticket-3"])
    merge.merged_by = user_id
    merge.merge_reason = "Duplicate tickets"
    merge.undo_token = "undo-merge-abc"
    merge.undo_expires_at = datetime.utcnow() + timedelta(hours=24)
    merge.unmerged_at = None
    merge.created_at = datetime.utcnow()
    return merge


# ── ATTACHMENT FIXTURES ──────────────────────────────────────────────────────

@pytest.fixture
def attachment_id():
    """Standard test attachment ID."""
    return "attachment-123"


@pytest.fixture
def mock_attachment(ticket_id, message_id):
    """Mock ticket attachment."""
    attachment = TicketAttachment()
    attachment.id = "attachment-123"
    attachment.ticket_id = ticket_id
    attachment.message_id = message_id
    attachment.company_id = "test-company-123"
    attachment.filename = "document.pdf"
    attachment.file_url = "https://storage.example.com/document.pdf"
    attachment.file_size = 1024 * 100  # 100KB
    attachment.mime_type = "application/pdf"
    attachment.created_at = datetime.utcnow()
    return attachment


# ── FEEDBACK FIXTURES ────────────────────────────────────────────────────────

@pytest.fixture
def feedback_id():
    """Standard test feedback ID."""
    return "feedback-123"


@pytest.fixture
def mock_ticket_feedback(ticket_id, customer_id):
    """Mock ticket feedback/CSAT."""
    feedback = TicketFeedback()
    feedback.id = "feedback-123"
    feedback.ticket_id = ticket_id
    feedback.company_id = "test-company-123"
    feedback.customer_id = customer_id
    feedback.rating = 5
    feedback.comment = "Great service!"
    feedback.created_at = datetime.utcnow()
    return feedback


@pytest.fixture
def mock_ticket_feedback_bad(ticket_id, customer_id):
    """Mock bad ticket feedback (1-star)."""
    feedback = TicketFeedback()
    feedback.id = "feedback-bad"
    feedback.ticket_id = ticket_id
    feedback.company_id = "test-company-123"
    feedback.customer_id = customer_id
    feedback.rating = 1
    feedback.comment = "Not helpful"
    feedback.created_at = datetime.utcnow()
    return feedback


# ── IDENTITY RESOLUTION FIXTURES ─────────────────────────────────────────────

@pytest.fixture
def identity_match_id():
    """Standard test identity match ID."""
    return "match-123"


@pytest.fixture
def mock_identity_match_log(company_id, customer_id):
    """Mock identity match log."""
    log = IdentityMatchLog()
    log.id = "match-123"
    log.company_id = company_id
    log.matched_customer_id = customer_id
    log.match_method = "email"
    log.confidence = 0.95
    log.input_email = "customer@example.com"
    log.input_phone = None
    log.input_social_id = None
    log.created_at = datetime.utcnow()
    return log


# ── INTENT/CLASSIFICATION FIXTURES ───────────────────────────────────────────

@pytest.fixture
def intent_id():
    """Standard test intent ID."""
    return "intent-123"


@pytest.fixture
def mock_ticket_intent(ticket_id):
    """Mock ticket intent/classification."""
    intent = TicketIntent()
    intent.id = "intent-123"
    intent.ticket_id = ticket_id
    intent.company_id = "test-company-123"
    intent.intent = "refund_request"
    intent.urgency = "high"
    intent.confidence = 0.92
    intent.classification_method = "rule_based"
    intent.is_corrected = False
    intent.corrected_by = None
    intent.corrected_at = None
    intent.created_at = datetime.utcnow()
    return intent


# ── FACTORY FIXTURES ─────────────────────────────────────────────────────────

@pytest.fixture
def ticket_factory(company_id):
    """Factory for creating tickets with custom attributes."""
    def create_ticket(**kwargs):
        ticket = Ticket()
        ticket.id = kwargs.get('id', f"ticket-{uuid.uuid4().hex[:8]}")
        ticket.company_id = kwargs.get('company_id', company_id)
        ticket.customer_id = kwargs.get('customer_id', "customer-789")
        ticket.channel = kwargs.get('channel', "email")
        ticket.status = kwargs.get('status', TicketStatus.open.value)
        ticket.subject = kwargs.get('subject', "Test ticket")
        ticket.priority = kwargs.get('priority', TicketPriority.medium.value)
        ticket.category = kwargs.get('category', None)
        ticket.tags = json.dumps(kwargs.get('tags', []))
        ticket.assigned_to = kwargs.get('assigned_to', None)
        ticket.reopen_count = kwargs.get('reopen_count', 0)
        ticket.frozen = kwargs.get('frozen', False)
        ticket.is_spam = kwargs.get('is_spam', False)
        ticket.awaiting_human = kwargs.get('awaiting_human', False)
        ticket.awaiting_client = kwargs.get('awaiting_client', False)
        ticket.escalation_level = kwargs.get('escalation_level', 1)
        ticket.sla_breached = kwargs.get('sla_breached', False)
        ticket.created_at = kwargs.get('created_at', datetime.utcnow())
        ticket.updated_at = kwargs.get('updated_at', datetime.utcnow())
        return ticket
    return create_ticket


@pytest.fixture
def customer_factory(company_id):
    """Factory for creating customers with custom attributes."""
    def create_customer(**kwargs):
        customer = Customer()
        customer.id = kwargs.get('id', f"customer-{uuid.uuid4().hex[:8]}")
        customer.company_id = kwargs.get('company_id', company_id)
        customer.email = kwargs.get('email', "test@example.com")
        customer.name = kwargs.get('name', "Test Customer")
        customer.phone = kwargs.get('phone', None)
        customer.external_id = kwargs.get('external_id', None)
        customer.metadata_json = json.dumps(kwargs.get('metadata', {}))
        customer.created_at = kwargs.get('created_at', datetime.utcnow())
        return customer
    return create_customer


# ── QUERY MOCK HELPERS ───────────────────────────────────────────────────────

@pytest.fixture
def mock_query_result():
    """Helper to create mock query results."""
    def create_result(items: List[Any], total: Optional[int] = None):
        mock_query = MagicMock()
        mock_query.all.return_value = items
        mock_query.count.return_value = total if total is not None else len(items)
        mock_query.first.return_value = items[0] if items else None
        return mock_query
    return create_result


@pytest.fixture
def mock_empty_query():
    """Helper to create empty query result."""
    mock_query = MagicMock()
    mock_query.all.return_value = []
    mock_query.count.return_value = 0
    mock_query.first.return_value = None
    return mock_query


# ── SERVICE FIXTURES ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get = MagicMock(return_value=None)
    redis_mock.set = MagicMock(return_value=True)
    redis_mock.delete = MagicMock(return_value=1)
    redis_mock.exists = MagicMock(return_value=0)
    redis_mock.expire = MagicMock(return_value=True)
    redis_mock.ttl = MagicMock(return_value=-1)
    redis_mock.incr = MagicMock(return_value=1)
    redis_mock.sadd = MagicMock(return_value=1)
    redis_mock.srem = MagicMock(return_value=1)
    redis_mock.smembers = MagicMock(return_value=set())
    return redis_mock


@pytest.fixture
def mock_socketio():
    """Mock Socket.io emitter."""
    socketio_mock = MagicMock()
    socketio_mock.emit = MagicMock(return_value=True)
    return socketio_mock


# ── DATE/TIME FIXTURES ───────────────────────────────────────────────────────

@pytest.fixture
def now():
    """Current UTC datetime."""
    return datetime.utcnow()


@pytest.fixture
def one_hour_ago():
    """Datetime one hour ago."""
    return datetime.utcnow() - timedelta(hours=1)


@pytest.fixture
def one_day_ago():
    """Datetime one day ago."""
    return datetime.utcnow() - timedelta(days=1)


@pytest.fixture
def one_week_ago():
    """Datetime one week ago."""
    return datetime.utcnow() - timedelta(weeks=1)


# ── TEST DATA CONSTANTS ──────────────────────────────────────────────────────

@pytest.fixture
def valid_statuses():
    """All valid ticket statuses."""
    return [s.value for s in TicketStatus]


@pytest.fixture
def valid_priorities():
    """All valid ticket priorities."""
    return [p.value for p in TicketPriority]


@pytest.fixture
def valid_categories():
    """All valid ticket categories."""
    return [c.value for c in TicketCategory]


@pytest.fixture
def valid_channels():
    """Valid channel types."""
    return ["email", "chat", "sms", "voice", "twitter", "instagram", "facebook"]
