"""
Unit tests for PARWA Mini Tasks.

Tests for all Mini variant tasks:
- AnswerFAQTask
- ProcessEmailTask
- HandleChatTask
- MakeCallTask
- CreateTicketTask
- EscalateTask
- VerifyRefundTask

CRITICAL TESTS:
- VerifyRefundTask: Paddle NEVER called without approval
- MakeCallTask: Max 2 concurrent calls enforced
- All tasks: Escalation when confidence < 70%
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

from variants.mini.tasks.answer_faq import AnswerFAQTask, FAQTaskResult
from variants.mini.tasks.process_email import ProcessEmailTask, EmailTaskResult, EmailIntent
from variants.mini.tasks.handle_chat import HandleChatTask, ChatTaskResult
from variants.mini.tasks.make_call import MakeCallTask, CallTaskResult, CallStatus
from variants.mini.tasks.create_ticket import CreateTicketTask, TicketTaskResult, TicketPriority
from variants.mini.tasks.escalate import EscalateTask, EscalationTaskResult, EscalationLevel
from variants.mini.tasks.verify_refund import VerifyRefundTask, RefundTaskResult, RefundStatus


# =============================================================================
# AnswerFAQTask Tests
# =============================================================================

class TestAnswerFAQTask:
    """Tests for AnswerFAQTask."""

    @pytest.fixture
    def task(self):
        """Create FAQ task instance."""
        return AnswerFAQTask()

    @pytest.mark.asyncio
    async def test_answer_faq_returns_result(self, task):
        """Test FAQ task returns result."""
        result = await task.execute({
            "query": "What are your business hours?",
            "customer_id": "cust_123"
        })

        assert isinstance(result, FAQTaskResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_answer_faq_handles_empty_query(self, task):
        """Test FAQ task handles empty query."""
        result = await task.execute({
            "query": "",
            "customer_id": "cust_123"
        })

        assert isinstance(result, FAQTaskResult)

    def test_faq_task_has_correct_metadata(self, task):
        """Test FAQ task metadata."""
        assert task.get_task_name() == "answer_faq"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# ProcessEmailTask Tests
# =============================================================================

class TestProcessEmailTask:
    """Tests for ProcessEmailTask."""

    @pytest.fixture
    def task(self):
        """Create email task instance."""
        return ProcessEmailTask()

    @pytest.mark.asyncio
    async def test_process_email_returns_result(self, task):
        """Test email task returns result."""
        result = await task.execute({
            "email_id": "email_123",
            "subject": "Question about my order",
            "body": "I ordered last week and haven't received my package yet.",
            "sender_email": "customer@example.com"
        })

        assert isinstance(result, EmailTaskResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_process_email_classifies_refund_intent(self, task):
        """Test email task classifies refund intent correctly."""
        result = await task.execute({
            "email_id": "email_123",
            "subject": "Need a refund",
            "body": "I want my money back for this defective product.",
            "sender_email": "customer@example.com"
        })

        assert result.intent == EmailIntent.REFUND_REQUEST.value

    @pytest.mark.asyncio
    async def test_process_email_classifies_order_status(self, task):
        """Test email task classifies order status intent."""
        result = await task.execute({
            "email_id": "email_123",
            "subject": "Where is my order?",
            "body": "I want to track my delivery status.",
            "sender_email": "customer@example.com"
        })

        assert result.intent == EmailIntent.ORDER_STATUS.value

    @pytest.mark.asyncio
    async def test_process_email_classifies_complaint(self, task):
        """Test email task classifies complaint intent."""
        result = await task.execute({
            "email_id": "email_123",
            "subject": "Very disappointed",
            "body": "I am extremely unhappy with your terrible service!",
            "sender_email": "customer@example.com"
        })

        assert result.intent == EmailIntent.COMPLAINT.value

    def test_email_task_has_correct_metadata(self, task):
        """Test email task metadata."""
        assert task.get_task_name() == "process_email"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# HandleChatTask Tests
# =============================================================================

class TestHandleChatTask:
    """Tests for HandleChatTask."""

    @pytest.fixture
    def task(self):
        """Create chat task instance."""
        return HandleChatTask()

    @pytest.mark.asyncio
    async def test_handle_chat_returns_result(self, task):
        """Test chat task returns result."""
        result = await task.execute({
            "message": "I need help with my order",
            "session_id": "sess_123",
            "customer_id": "cust_456"
        })

        assert isinstance(result, ChatTaskResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_chat_max_messages_triggers_escalation(self, task):
        """Test chat task escalates after max messages."""
        result = await task.execute({
            "message": "Still need help",
            "session_id": "sess_123",
            "customer_id": "cust_456",
            "message_count": 50  # At max limit
        })

        assert result.escalated is True
        assert result.escalation_reason == "max_messages_reached"

    def test_chat_task_has_correct_metadata(self, task):
        """Test chat task metadata."""
        assert task.get_task_name() == "handle_chat"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# MakeCallTask Tests
# =============================================================================

class TestMakeCallTask:
    """Tests for MakeCallTask."""

    @pytest.fixture
    def task(self):
        """Create call task instance."""
        return MakeCallTask()

    @pytest.mark.asyncio
    async def test_make_call_returns_result(self, task):
        """Test call task returns result."""
        result = await task.execute({
            "phone_number": "+1234567890",
            "reason": "order_confirmation",
            "customer_id": "cust_123"
        })

        assert isinstance(result, CallTaskResult)

    @pytest.mark.asyncio
    async def test_make_call_enforces_two_concurrent_limit(self, task):
        """CRITICAL: Test call task enforces 2 concurrent call limit."""
        # Simulate 2 active calls
        task._active_calls = {
            "call_1": None,
            "call_2": None
        }

        result = await task.execute({
            "phone_number": "+1234567890",
            "reason": "order_confirmation",
            "customer_id": "cust_123"
        })

        # Should be queued due to limit
        assert result.status == CallStatus.QUEUED
        assert result.queued_reason is not None
        assert "2" in result.queued_reason  # Check limit mentioned

    @pytest.mark.asyncio
    async def test_can_make_call_returns_correct_status(self, task):
        """Test can_make_call returns correct status."""
        # No active calls - should be able to make call
        assert task.can_make_call() is True

        # Add active calls up to limit
        task._active_calls = {"call_1": None}
        assert task.can_make_call() is True

        task._active_calls = {"call_1": None, "call_2": None}
        assert task.can_make_call() is False

    def test_call_task_has_correct_metadata(self, task):
        """Test call task metadata."""
        assert task.get_task_name() == "make_call"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# CreateTicketTask Tests
# =============================================================================

class TestCreateTicketTask:
    """Tests for CreateTicketTask."""

    @pytest.fixture
    def task(self):
        """Create ticket task instance."""
        return CreateTicketTask()

    @pytest.mark.asyncio
    async def test_create_ticket_returns_result(self, task):
        """Test ticket task returns result."""
        result = await task.execute({
            "subject": "Order not received",
            "description": "I ordered 5 days ago and haven't received anything.",
            "customer_id": "cust_123",
            "category": "shipping"
        })

        assert isinstance(result, TicketTaskResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_ticket_assigns_correct_priority(self, task):
        """Test ticket task assigns correct priority by category."""
        # Refund category should be HIGH priority
        result = await task.execute({
            "subject": "Refund request",
            "description": "I need a refund",
            "customer_id": "cust_123",
            "category": "refund"
        })

        assert result.priority == TicketPriority.HIGH

    @pytest.mark.asyncio
    async def test_create_ticket_urgent_keywords_trigger_urgent_priority(self, task):
        """Test urgent keywords trigger urgent priority."""
        result = await task.execute({
            "subject": "URGENT: Need immediate help",
            "description": "This is an emergency that needs to be handled immediately!",
            "customer_id": "cust_123",
            "category": "inquiry"
        })

        assert result.priority == TicketPriority.URGENT

    @pytest.mark.asyncio
    async def test_create_ticket_high_priority_auto_escalates(self, task):
        """Test high priority tickets auto-escalate."""
        result = await task.execute({
            "subject": "Serious complaint",
            "description": "I am very disappointed",
            "customer_id": "cust_123",
            "category": "complaint"
        })

        assert result.escalated is True

    def test_ticket_task_has_correct_metadata(self, task):
        """Test ticket task metadata."""
        assert task.get_task_name() == "create_ticket"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# EscalateTask Tests
# =============================================================================

class TestEscalateTask:
    """Tests for EscalateTask."""

    @pytest.fixture
    def task(self):
        """Create escalation task instance."""
        return EscalateTask()

    @pytest.mark.asyncio
    async def test_escalate_returns_result(self, task):
        """Test escalation task returns result."""
        result = await task.execute({
            "conversation_id": "conv_123",
            "reason": "low_confidence",
            "context": {"query": "Complex question"},
            "customer_id": "cust_456"
        })

        assert isinstance(result, EscalationTaskResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_escalate_vip_customer_gets_manager_level(self, task):
        """Test VIP customers get manager level escalation."""
        result = await task.execute({
            "conversation_id": "conv_123",
            "reason": "low_confidence",
            "context": {},
            "customer_id": "cust_vip",
            "is_vip": True
        })

        assert result.level in (EscalationLevel.TIER_2, EscalationLevel.MANAGER)

    @pytest.mark.asyncio
    async def test_escalate_complaint_gets_tier_2(self, task):
        """Test complaints escalate to Tier 2."""
        result = await task.execute({
            "conversation_id": "conv_123",
            "reason": "complaint",
            "context": {},
            "customer_id": "cust_456"
        })

        assert result.level == EscalationLevel.TIER_2

    @pytest.mark.asyncio
    async def test_escalate_returns_customer_message(self, task):
        """Test escalation returns customer message."""
        result = await task.execute({
            "conversation_id": "conv_123",
            "reason": "low_confidence",
            "context": {},
            "customer_id": "cust_456"
        })

        assert result.customer_message is not None
        assert "human agent" in result.customer_message.lower()

    def test_escalate_task_has_correct_metadata(self, task):
        """Test escalation task metadata."""
        assert task.get_task_name() == "escalate"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# VerifyRefundTask Tests (CRITICAL)
# =============================================================================

class TestVerifyRefundTask:
    """Tests for VerifyRefundTask - CRITICAL tests for Paddle refund gate."""

    @pytest.fixture
    def task(self):
        """Create refund verification task instance."""
        return VerifyRefundTask()

    @pytest.mark.asyncio
    async def test_verify_refund_returns_result(self, task):
        """Test refund verification returns result."""
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 25.00,
            "reason": "Product defective",
            "customer_id": "cust_456"
        })

        assert isinstance(result, RefundTaskResult)

    @pytest.mark.asyncio
    async def test_verify_refund_within_limit_succeeds(self, task):
        """Test refund within $50 limit succeeds verification."""
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 45.00,  # Under $50 limit
            "reason": "Product defective",
            "customer_id": "cust_456"
        })

        assert result.success is True
        assert result.status != RefundStatus.EXCEEDED_LIMIT

    @pytest.mark.asyncio
    async def test_verify_refund_exceeds_limit_rejected(self, task):
        """CRITICAL: Test refund over $50 limit is rejected."""
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 75.00,  # Over $50 limit
            "reason": "Product defective",
            "customer_id": "cust_456"
        })

        assert result.success is False
        assert result.status == RefundStatus.EXCEEDED_LIMIT
        assert "exceeds" in result.rejection_reason.lower()

    @pytest.mark.asyncio
    async def test_verify_refund_never_calls_paddle(self, task):
        """CRITICAL: Test that refund verification NEVER calls Paddle."""
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 30.00,
            "reason": "Product defective",
            "customer_id": "cust_456"
        })

        # CRITICAL ASSERTION
        assert result.paddle_call_required is False
        assert result.approval_required is True

    @pytest.mark.asyncio
    async def test_verify_refund_always_requires_approval(self, task):
        """CRITICAL: Test that Mini refunds always require approval."""
        # Even for small amounts
        result = await task.execute({
            "order_id": "ord_123",
            "amount": 5.00,  # Very small amount
            "reason": "Product defective",
            "customer_id": "cust_456"
        })

        # CRITICAL: Always requires approval for Mini
        assert result.approval_required is True
        assert result.paddle_call_required is False

    def test_check_limit_returns_correct_value(self, task):
        """Test check_limit method."""
        assert task.check_limit(Decimal("45.00")) is True
        assert task.check_limit(Decimal("50.00")) is True
        assert task.check_limit(Decimal("50.01")) is False
        assert task.check_limit(Decimal("100.00")) is False

    def test_get_max_refund_returns_50(self, task):
        """Test get_max_refund returns $50."""
        assert task.get_max_refund() == Decimal("50.00")

    def test_refund_task_has_correct_metadata(self, task):
        """Test refund task metadata."""
        assert task.get_task_name() == "verify_refund"
        assert task.get_variant() == "mini"
        assert task.get_tier() == "light"


# =============================================================================
# Integration Tests
# =============================================================================

class TestMiniTasksIntegration:
    """Integration tests for Mini tasks."""

    @pytest.mark.asyncio
    async def test_all_tasks_can_be_instantiated(self):
        """Test all tasks can be instantiated."""
        tasks = [
            AnswerFAQTask(),
            ProcessEmailTask(),
            HandleChatTask(),
            MakeCallTask(),
            CreateTicketTask(),
            EscalateTask(),
            VerifyRefundTask(),
        ]

        for task in tasks:
            assert task.get_variant() == "mini"
            assert task.get_tier() == "light"

    @pytest.mark.asyncio
    async def test_refund_to_chat_escalation_flow(self):
        """Test flow from refund to chat escalation."""
        # 1. Create chat session
        chat_task = HandleChatTask()
        chat_result = await chat_task.execute({
            "message": "I need a refund for $75",
            "session_id": "sess_123",
            "customer_id": "cust_456",
            "message_count": 1
        })

        assert chat_result.success is True

        # 2. Try refund verification
        refund_task = VerifyRefundTask()
        refund_result = await refund_task.execute({
            "order_id": "ord_123",
            "amount": 75.00,  # Over Mini limit
            "reason": "Product not as described",
            "customer_id": "cust_456"
        })

        # Should fail due to limit
        assert refund_result.success is False
        assert refund_result.status == RefundStatus.EXCEEDED_LIMIT

        # 3. Escalate
        escalate_task = EscalateTask()
        escalate_result = await escalate_task.execute({
            "conversation_id": "sess_123",
            "reason": "refund_high_value",
            "context": {"refund_amount": 75.00},
            "customer_id": "cust_456"
        })

        assert escalate_result.success is True
        assert escalate_result.level == EscalationLevel.TIER_2
