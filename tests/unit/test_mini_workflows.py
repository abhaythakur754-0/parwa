"""
Unit tests for Mini PARWA workflows.

Tests cover:
- InquiryWorkflow: Handle customer inquiries
- TicketCreationWorkflow: Create support tickets
- EscalationWorkflow: Handle escalations to human support
- OrderStatusWorkflow: Check and report order status
- RefundVerificationWorkflow: Process refund requests

Critical tests:
- RefundVerificationWorkflow NEVER calls Paddle directly
- EscalationWorkflow triggers human handoff
- All workflows return appropriate status
"""
import pytest
from uuid import uuid4, UUID

from variants.mini.workflows.inquiry import InquiryWorkflow
from variants.mini.workflows.ticket_creation import TicketCreationWorkflow
from variants.mini.workflows.escalation import EscalationWorkflow
from variants.mini.workflows.order_status import OrderStatusWorkflow
from variants.mini.workflows.refund_verification import RefundVerificationWorkflow
from variants.mini.tools.faq_search import FAQSearchTool
from variants.mini.tools.order_lookup import OrderLookupTool
from variants.mini.tools.ticket_create import TicketCreateTool
from variants.mini.tools.notification import NotificationTool
from variants.mini.tools.refund_verification_tools import RefundVerificationTool
from variants.mini.config import MiniConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mini_config() -> MiniConfig:
    """Create a test MiniConfig."""
    return MiniConfig()


@pytest.fixture
def faq_tool() -> FAQSearchTool:
    """Create a FAQSearchTool for testing."""
    return FAQSearchTool()


@pytest.fixture
def order_tool() -> OrderLookupTool:
    """Create an OrderLookupTool for testing."""
    return OrderLookupTool()


@pytest.fixture
def ticket_tool() -> TicketCreateTool:
    """Create a TicketCreateTool for testing."""
    return TicketCreateTool()


@pytest.fixture
def notification_tool() -> NotificationTool:
    """Create a NotificationTool for testing."""
    return NotificationTool()


@pytest.fixture
def refund_tool() -> RefundVerificationTool:
    """Create a RefundVerificationTool for testing."""
    return RefundVerificationTool()


@pytest.fixture
def inquiry_workflow(mini_config: MiniConfig) -> InquiryWorkflow:
    """Create an InquiryWorkflow for testing."""
    return InquiryWorkflow(mini_config=mini_config)


@pytest.fixture
def ticket_workflow(mini_config: MiniConfig) -> TicketCreationWorkflow:
    """Create a TicketCreationWorkflow for testing."""
    return TicketCreationWorkflow(mini_config=mini_config)


@pytest.fixture
def escalation_workflow(mini_config: MiniConfig) -> EscalationWorkflow:
    """Create an EscalationWorkflow for testing."""
    return EscalationWorkflow(mini_config=mini_config)


@pytest.fixture
def order_status_workflow(mini_config: MiniConfig) -> OrderStatusWorkflow:
    """Create an OrderStatusWorkflow for testing."""
    return OrderStatusWorkflow(mini_config=mini_config)


@pytest.fixture
def refund_workflow(mini_config: MiniConfig) -> RefundVerificationWorkflow:
    """Create a RefundVerificationWorkflow for testing."""
    return RefundVerificationWorkflow(mini_config=mini_config)


# =============================================================================
# FAQSearchTool Tests
# =============================================================================

class TestFAQSearchTool:
    """Tests for FAQSearchTool."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, faq_tool: FAQSearchTool):
        """Test search returns results."""
        results = await faq_tool.search("password reset")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_finds_match(self, faq_tool: FAQSearchTool):
        """Test search finds matching FAQ."""
        results = await faq_tool.search("password")
        assert len(results) > 0
        assert "password" in results[0].get("question", "").lower()

    @pytest.mark.asyncio
    async def test_get_by_id(self, faq_tool: FAQSearchTool):
        """Test get FAQ by ID."""
        faq = await faq_tool.get_by_id("FAQ-001")
        assert faq is not None
        assert faq.get("id") == "FAQ-001"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, faq_tool: FAQSearchTool):
        """Test get FAQ by ID not found."""
        faq = await faq_tool.get_by_id("NONEXISTENT")
        assert faq is None

    @pytest.mark.asyncio
    async def test_get_categories(self, faq_tool: FAQSearchTool):
        """Test get categories."""
        categories = await faq_tool.get_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0


# =============================================================================
# OrderLookupTool Tests
# =============================================================================

class TestOrderLookupTool:
    """Tests for OrderLookupTool."""

    @pytest.mark.asyncio
    async def test_lookup_order(self, order_tool: OrderLookupTool):
        """Test lookup order by ID."""
        order = await order_tool.lookup("ORD-12345")
        assert order is not None
        assert order.get("order_id") == "ORD-12345"

    @pytest.mark.asyncio
    async def test_lookup_order_not_found(self, order_tool: OrderLookupTool):
        """Test lookup order not found."""
        order = await order_tool.lookup("NONEXISTENT")
        assert order is None

    @pytest.mark.asyncio
    async def test_lookup_by_customer(self, order_tool: OrderLookupTool):
        """Test lookup orders by customer."""
        orders = await order_tool.lookup_by_customer("CUST-001")
        assert isinstance(orders, list)

    @pytest.mark.asyncio
    async def test_check_status(self, order_tool: OrderLookupTool):
        """Test check order status."""
        status = await order_tool.check_status("ORD-12345")
        assert status is not None

    @pytest.mark.asyncio
    async def test_is_refundable(self, order_tool: OrderLookupTool):
        """Test is order refundable."""
        result = await order_tool.is_refundable("ORD-12345")
        assert "refundable" in result


# =============================================================================
# TicketCreateTool Tests
# =============================================================================

class TestTicketCreateTool:
    """Tests for TicketCreateTool."""

    @pytest.mark.asyncio
    async def test_create_ticket(self, ticket_tool: TicketCreateTool):
        """Test create ticket."""
        ticket = await ticket_tool.create(
            subject="Test ticket",
            description="This is a test ticket description"
        )
        assert ticket.get("ticket_id") is not None
        assert ticket.get("status") == "open"

    @pytest.mark.asyncio
    async def test_validate_ticket_data(self, ticket_tool: TicketCreateTool):
        """Test validate ticket data."""
        result = ticket_tool.validate_ticket_data("Subject", "Description here", "normal")
        assert result.get("valid") is True

    @pytest.mark.asyncio
    async def test_validate_ticket_data_invalid(self, ticket_tool: TicketCreateTool):
        """Test validate ticket data invalid."""
        result = ticket_tool.validate_ticket_data("Ab", "Short", "invalid")
        assert result.get("valid") is False

    @pytest.mark.asyncio
    async def test_add_comment(self, ticket_tool: TicketCreateTool):
        """Test add comment to ticket."""
        ticket = await ticket_tool.create(
            subject="Test",
            description="Test description"
        )
        updated = await ticket_tool.add_comment(
            ticket_id=ticket["ticket_id"],
            comment="Test comment",
            author="Test User"
        )
        assert updated is not None
        assert len(updated.get("comments", [])) == 1


# =============================================================================
# NotificationTool Tests
# =============================================================================

class TestNotificationTool:
    """Tests for NotificationTool."""

    @pytest.mark.asyncio
    async def test_send_sms(self, notification_tool: NotificationTool):
        """Test send SMS."""
        result = await notification_tool.send_sms(
            to="+1234567890",
            message="Test message"
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_send_sms_invalid_phone(self, notification_tool: NotificationTool):
        """Test send SMS with invalid phone."""
        result = await notification_tool.send_sms(
            to="123",
            message="Test message"
        )
        assert result.get("success") is False

    @pytest.mark.asyncio
    async def test_send_email(self, notification_tool: NotificationTool):
        """Test send email."""
        result = await notification_tool.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body content"
        )
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_send_email_invalid_email(self, notification_tool: NotificationTool):
        """Test send email with invalid email."""
        result = await notification_tool.send_email(
            to="invalid-email",
            subject="Test Subject",
            body="Test body"
        )
        assert result.get("success") is False


# =============================================================================
# RefundVerificationTool Tests
# =============================================================================

class TestRefundVerificationTool:
    """Tests for RefundVerificationTool."""

    @pytest.mark.asyncio
    async def test_verify_eligibility(self, refund_tool: RefundVerificationTool):
        """Test verify refund eligibility."""
        result = await refund_tool.verify_eligibility("ORD-12345")
        assert "eligible" in result

    @pytest.mark.asyncio
    async def test_create_approval_request(self, refund_tool: RefundVerificationTool):
        """Test create approval request."""
        result = await refund_tool.create_approval_request({
            "order_id": "ORD-12345",
            "amount": 30.0,
            "reason": "Customer request"
        })
        assert result.get("approval_id") is not None
        assert result.get("status") == "pending"

    def test_get_recommendation_approve(self, refund_tool: RefundVerificationTool):
        """Test get recommendation approve."""
        recommendation = refund_tool.get_recommendation({
            "amount": 20.0,
            "is_first_refund": True,
            "fraud_indicators": False
        })
        assert recommendation == "APPROVE"

    def test_get_recommendation_deny(self, refund_tool: RefundVerificationTool):
        """Test get recommendation deny for fraud."""
        recommendation = refund_tool.get_recommendation({
            "amount": 20.0,
            "fraud_indicators": True
        })
        assert recommendation == "DENY"

    def test_validate_refund_amount_within_limit(self, refund_tool: RefundVerificationTool):
        """Test validate refund amount within limit."""
        result = refund_tool.validate_refund_amount(30.0)
        assert result.get("valid") is True
        assert result.get("within_mini_limit") is True

    def test_validate_refund_amount_over_limit(self, refund_tool: RefundVerificationTool):
        """Test validate refund amount over limit."""
        result = refund_tool.validate_refund_amount(100.0)
        assert result.get("valid") is True
        assert result.get("within_mini_limit") is False


class TestRefundToolGate:
    """CRITICAL: Tests verifying refund gate is enforced."""

    @pytest.mark.asyncio
    async def test_payment_processor_not_called(self, refund_tool: RefundVerificationTool):
        """CRITICAL: Payment processor must NOT be called when creating approval."""
        result = await refund_tool.create_approval_request({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        # CRITICAL: Verify payment processor was NOT called
        assert result.get("payment_processor_called") is False


# =============================================================================
# InquiryWorkflow Tests
# =============================================================================

class TestInquiryWorkflow:
    """Tests for InquiryWorkflow."""

    @pytest.mark.asyncio
    async def test_execute_faq_inquiry(self, inquiry_workflow: InquiryWorkflow):
        """Test execute FAQ inquiry."""
        result = await inquiry_workflow.execute({
            "query": "How do I reset my password?"
        })
        assert result.get("status") in ["resolved", "escalated", "no_match"]

    @pytest.mark.asyncio
    async def test_classify_inquiry_order_status(self, inquiry_workflow: InquiryWorkflow):
        """Test classify order status inquiry."""
        inquiry_type = await inquiry_workflow._classify_inquiry(
            "Where is my order?"
        )
        assert inquiry_type == "order_status"

    @pytest.mark.asyncio
    async def test_classify_inquiry_refund(self, inquiry_workflow: InquiryWorkflow):
        """Test classify refund inquiry."""
        inquiry_type = await inquiry_workflow._classify_inquiry(
            "I want a refund"
        )
        assert inquiry_type == "refund"

    def test_get_workflow_name(self, inquiry_workflow: InquiryWorkflow):
        """Test get workflow name."""
        assert inquiry_workflow.get_workflow_name() == "InquiryWorkflow"

    def test_get_variant(self, inquiry_workflow: InquiryWorkflow):
        """Test get variant."""
        assert inquiry_workflow.get_variant() == "mini"


# =============================================================================
# TicketCreationWorkflow Tests
# =============================================================================

class TestTicketCreationWorkflow:
    """Tests for TicketCreationWorkflow."""

    @pytest.mark.asyncio
    async def test_execute_create_ticket(self, ticket_workflow: TicketCreationWorkflow):
        """Test execute create ticket."""
        result = await ticket_workflow.execute({
            "subject": "Test Subject",
            "description": "This is a test ticket description",
            "priority": "normal"
        })
        assert result.get("status") == "created"
        assert result.get("ticket_id") is not None

    @pytest.mark.asyncio
    async def test_execute_validation_failed(self, ticket_workflow: TicketCreationWorkflow):
        """Test execute with validation failure."""
        result = await ticket_workflow.execute({
            "subject": "Ab",  # Too short
            "description": "Short"  # Too short
        })
        assert result.get("status") == "validation_failed"

    @pytest.mark.asyncio
    async def test_execute_with_notification(
        self,
        ticket_workflow: TicketCreationWorkflow
    ):
        """Test execute with customer notification."""
        result = await ticket_workflow.execute({
            "subject": "Test Subject",
            "description": "This is a test ticket description",
            "customer_email": "test@example.com",
            "notify_customer": True
        })
        assert result.get("status") == "created"
        # Notification may or may not be sent depending on email

    def test_get_workflow_name(self, ticket_workflow: TicketCreationWorkflow):
        """Test get workflow name."""
        assert ticket_workflow.get_workflow_name() == "TicketCreationWorkflow"


# =============================================================================
# EscalationWorkflow Tests
# =============================================================================

class TestEscalationWorkflow:
    """Tests for EscalationWorkflow."""

    @pytest.mark.asyncio
    async def test_execute_escalation(self, escalation_workflow: EscalationWorkflow):
        """Test execute escalation."""
        result = await escalation_workflow.execute({
            "ticket_id": "TKT-12345",
            "reason": "low_confidence",
            "confidence": 0.5
        })
        assert result.get("status") == "escalated"
        assert result.get("escalation_id") is not None

    @pytest.mark.asyncio
    async def test_escalation_triggers_human_handoff(
        self,
        escalation_workflow: EscalationWorkflow
    ):
        """CRITICAL: Test escalation triggers human handoff."""
        result = await escalation_workflow.execute({
            "ticket_id": "TKT-12345",
            "reason": "low_confidence",
            "confidence": 0.3
        })
        assert result.get("human_handoff") is True

    @pytest.mark.asyncio
    async def test_acknowledge_escalation(self, escalation_workflow: EscalationWorkflow):
        """Test acknowledge escalation."""
        # Create escalation first
        created = await escalation_workflow.execute({
            "ticket_id": "TKT-12345",
            "reason": "test"
        })

        # Acknowledge it
        result = await escalation_workflow.acknowledge(
            escalation_id=created.get("escalation_id"),
            handler="Agent John"
        )
        assert result.get("status") == "acknowledged"

    @pytest.mark.asyncio
    async def test_resolve_escalation(self, escalation_workflow: EscalationWorkflow):
        """Test resolve escalation."""
        # Create escalation first
        created = await escalation_workflow.execute({
            "ticket_id": "TKT-12345",
            "reason": "test"
        })

        # Resolve it
        result = await escalation_workflow.resolve(
            escalation_id=created.get("escalation_id"),
            resolution="Issue resolved"
        )
        assert result.get("status") == "resolved"


# =============================================================================
# OrderStatusWorkflow Tests
# =============================================================================

class TestOrderStatusWorkflow:
    """Tests for OrderStatusWorkflow."""

    @pytest.mark.asyncio
    async def test_execute_order_found(
        self,
        order_status_workflow: OrderStatusWorkflow
    ):
        """Test execute order found."""
        result = await order_status_workflow.execute("ORD-12345")
        assert result.get("status") == "found"
        assert result.get("order_status") is not None

    @pytest.mark.asyncio
    async def test_execute_order_not_found(
        self,
        order_status_workflow: OrderStatusWorkflow
    ):
        """Test execute order not found."""
        result = await order_status_workflow.execute("NONEXISTENT")
        assert result.get("status") == "not_found"

    @pytest.mark.asyncio
    async def test_execute_by_customer(
        self,
        order_status_workflow: OrderStatusWorkflow
    ):
        """Test execute by customer."""
        result = await order_status_workflow.execute_by_customer("CUST-001")
        assert result.get("status") == "found"
        assert result.get("total_orders", 0) >= 1

    @pytest.mark.asyncio
    async def test_execute_by_email(
        self,
        order_status_workflow: OrderStatusWorkflow
    ):
        """Test execute by email."""
        result = await order_status_workflow.execute_by_email("customer@example.com")
        assert result.get("status") == "found"

    def test_get_workflow_name(self, order_status_workflow: OrderStatusWorkflow):
        """Test get workflow name."""
        assert order_status_workflow.get_workflow_name() == "OrderStatusWorkflow"


# =============================================================================
# RefundVerificationWorkflow Tests - CRITICAL
# =============================================================================

class TestRefundVerificationWorkflow:
    """Tests for RefundVerificationWorkflow."""

    @pytest.mark.asyncio
    async def test_execute_refund_within_limit(
        self,
        refund_workflow: RefundVerificationWorkflow
    ):
        """Test execute refund within limit."""
        result = await refund_workflow.execute({
            "order_id": "ORD-12345",
            "amount": 30.0,
            "reason": "Customer request"
        })
        assert result.get("status") == "pending_approval"
        assert result.get("approval_id") is not None

    @pytest.mark.asyncio
    async def test_execute_refund_over_limit(
        self,
        refund_workflow: RefundVerificationWorkflow
    ):
        """Test execute refund over $50 limit."""
        result = await refund_workflow.execute({
            "order_id": "ORD-12345",
            "amount": 100.0,
            "reason": "Customer request"
        })
        assert result.get("status") == "pending_approval"
        assert result.get("within_mini_limit") is False
        assert result.get("escalated") is True

    @pytest.mark.asyncio
    async def test_check_approval_status(
        self,
        refund_workflow: RefundVerificationWorkflow
    ):
        """Test check approval status."""
        # Create approval first
        created = await refund_workflow.execute({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        # Check status
        result = await refund_workflow.check_status(created.get("approval_id"))
        assert result.get("status") == "pending"


class TestRefundWorkflowGate:
    """CRITICAL: Tests verifying the refund gate is enforced."""

    @pytest.mark.asyncio
    async def test_paddle_not_called_directly(
        self,
        refund_workflow: RefundVerificationWorkflow
    ):
        """CRITICAL: Paddle must NOT be called when creating approval."""
        result = await refund_workflow.execute({
            "order_id": "ORD-12345",
            "amount": 30.0
        })

        # CRITICAL: Verify payment processor was NOT called
        assert result.get("payment_processor_called") is False

    @pytest.mark.asyncio
    async def test_refund_workflow_never_calls_paddle(
        self,
        refund_workflow: RefundVerificationWorkflow
    ):
        """CRITICAL: Verify no direct Paddle calls in RefundVerificationWorkflow."""
        # Test various refund amounts
        amounts = [10.0, 30.0, 50.0, 100.0]

        for amount in amounts:
            result = await refund_workflow.execute({
                "order_id": "ORD-12345",
                "amount": amount
            })
            assert result.get("payment_processor_called") is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestWorkflowIntegration:
    """Integration tests for workflows."""

    @pytest.mark.asyncio
    async def test_inquiry_to_ticket_flow(
        self,
        inquiry_workflow: InquiryWorkflow,
        ticket_workflow: TicketCreationWorkflow
    ):
        """Test inquiry flow that results in ticket creation."""
        # Inquire about something complex
        inquiry_result = await inquiry_workflow.execute({
            "query": "I have a complex billing issue that needs review"
        })

        # If escalated, create ticket
        if inquiry_result.get("status") in ["escalated", "no_match"]:
            ticket_result = await ticket_workflow.execute({
                "subject": "Complex billing inquiry",
                "description": "Customer needs billing review"
            })
            assert ticket_result.get("status") == "created"

    @pytest.mark.asyncio
    async def test_refund_to_escalation_flow(
        self,
        refund_workflow: RefundVerificationWorkflow,
        escalation_workflow: EscalationWorkflow
    ):
        """Test refund over limit triggers escalation flow."""
        # Request refund over limit
        refund_result = await refund_workflow.execute({
            "order_id": "ORD-12345",
            "amount": 100.0,  # Over $50 limit
            "customer_id": "CUST-001"
        })

        assert refund_result.get("escalated") is True

        # Would trigger escalation
        escalation_result = await escalation_workflow.execute({
            "ticket_id": refund_result.get("approval_id"),
            "reason": "refund_over_limit",
            "confidence": 0.0
        })

        assert escalation_result.get("human_handoff") is True

    @pytest.mark.asyncio
    async def test_all_workflows_return_variant_mini(
        self,
        inquiry_workflow: InquiryWorkflow,
        ticket_workflow: TicketCreationWorkflow,
        escalation_workflow: EscalationWorkflow,
        order_status_workflow: OrderStatusWorkflow,
        refund_workflow: RefundVerificationWorkflow
    ):
        """Test all workflows return 'mini' variant."""
        assert inquiry_workflow.get_variant() == "mini"
        assert ticket_workflow.get_variant() == "mini"
        assert escalation_workflow.get_variant() == "mini"
        assert order_status_workflow.get_variant() == "mini"
        assert refund_workflow.get_variant() == "mini"
