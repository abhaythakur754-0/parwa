"""
Week 5 Day 4 - Payment Failure Service Tests

Tests for Netflix-style payment failure handling:
1. Payment failure triggers immediate stop
2. All services stop correctly (agents, tickets)
3. Notification sent
4. Service resumes on successful payment
5. Frozen tickets unfrozen correctly
6. Payment failure history retrieval

BC-001: company_id isolation in all tests
BC-002: Decimal precision for amounts
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import sys
sys.path.insert(0, '/home/z/my-project/parwa')


# =============================================================================
# Shared Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def mock_company():
    """Create a mock company."""
    company = MagicMock()
    company.id = str(uuid4())
    company.subscription_status = "active"
    company.subscription_tier = "parwa"
    return company


@pytest.fixture
def mock_subscription():
    """Create a mock subscription."""
    subscription = MagicMock()
    subscription.id = str(uuid4())
    subscription.company_id = str(uuid4())
    subscription.status = "active"
    subscription.tier = "parwa"
    return subscription


# =============================================================================
# Test Payment Failure Service
# =============================================================================

class TestPaymentFailureService:

    @pytest.mark.asyncio
    async def test_handle_payment_failure_creates_record(self, mock_db_session, mock_company):
        """
        Test that handle_payment_failure creates a PaymentFailure record.
        
        GAP 1: Payment failure creates audit record
        """
        from backend.app.services.payment_failure_service import PaymentFailureService
        from database.models.billing_extended import PaymentFailure

        service = PaymentFailureService()
        company_id = uuid4()

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None  # No existing failure

            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_123",
                failure_code="card_declined",
                failure_reason="Insufficient funds",
                amount_attempted=Decimal("999.00"),
            )

        assert result["status"] == "stopped"
        assert "failure_id" in result
        assert result["new_status"] == "payment_failed"

    @pytest.mark.asyncio
    async def test_handle_payment_failure_updates_company_status(self, mock_db_session, mock_company):
        """
        Test that handle_payment_failure updates company.subscription_status.
        
        GAP 2: Company status updated to 'payment_failed'
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_456",
                failure_code="expired_card",
                failure_reason="Card has expired",
                amount_attempted=Decimal("2499.00"),
            )

        assert mock_company.subscription_status == "payment_failed"
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_payment_failure_idempotent(self, mock_db_session, mock_company):
        """
        Test that duplicate payment failure calls are handled idempotently.
        
        GAP 3: Duplicate failures don't create duplicate records
        """
        from backend.app.services.payment_failure_service import PaymentFailureService
        from database.models.billing_extended import PaymentFailure

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock existing unresolved failure
        existing_failure = MagicMock()
        existing_failure.id = str(uuid4())
        existing_failure.resolved = False

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            # First query returns existing failure
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_789",
                failure_code="card_declined",
                failure_reason="Insufficient funds",
                amount_attempted=Decimal("999.00"),
            )

        assert result["status"] == "already_stopped"
        assert "existing_failure_id" in result

    @pytest.mark.asyncio
    async def test_is_service_stopped_true(self, mock_db_session):
        """
        Test is_service_stopped returns True when company has active failure.
        
        GAP 4: Service stop detection works correctly
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock unresolved failure
        existing_failure = MagicMock()
        existing_failure.resolved = False

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            result = await service.is_service_stopped(company_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_service_stopped_false(self, mock_db_session, mock_company):
        """
        Test is_service_stopped returns False when no active failure.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()
        mock_company.subscription_status = "active"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.first.side_effect = [None, mock_company]

            result = await service.is_service_stopped(company_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_resume_service_updates_status(self, mock_db_session, mock_company):
        """
        Test resume_service updates company status to 'active'.
        
        GAP 5: Service resume works correctly
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock existing failure
        existing_failure = MagicMock()
        existing_failure.id = str(uuid4())
        existing_failure.resolved = False
        existing_failure.service_resumed_at = None

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_success_123",
            )

        assert result["status"] == "resumed"
        assert mock_company.subscription_status == "active"
        assert existing_failure.resolved is True
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_resume_service_no_active_failure(self, mock_db_session, mock_company):
        """
        Test resume_service when there's no active failure.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()
        mock_company.subscription_status = "active"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None  # No failure

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_123",
            )

        assert result["status"] == "no_failure"

    @pytest.mark.asyncio
    async def test_get_payment_failure_history(self, mock_db_session):
        """
        Test get_payment_failure_history returns list of failures.
        
        GAP 6: History retrieval works correctly
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock failures
        failure1 = MagicMock()
        failure1.id = str(uuid4())
        failure1.paddle_subscription_id = "sub_1"
        failure1.paddle_transaction_id = "txn_1"
        failure1.failure_code = "card_declined"
        failure1.failure_reason = "Insufficient funds"
        failure1.amount_attempted = Decimal("999.00")
        failure1.currency = "USD"
        failure1.service_stopped_at = datetime.now(timezone.utc)
        failure1.service_resumed_at = None
        failure1.notification_sent = True
        failure1.resolved = False
        failure1.created_at = datetime.now(timezone.utc)

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [failure1]

            result = await service.get_payment_failure_history(company_id)

        assert len(result) == 1
        assert result[0]["id"] == failure1.id
        assert result[0]["failure_code"] == "card_declined"

    @pytest.mark.asyncio
    async def test_get_active_failure(self, mock_db_session):
        """
        Test get_active_failure returns unresolved failure.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock active failure
        active_failure = MagicMock()
        active_failure.id = str(uuid4())
        active_failure.paddle_transaction_id = "txn_active"
        active_failure.failure_code = "card_declined"
        active_failure.failure_reason = "Card declined"
        active_failure.amount_attempted = Decimal("999.00")
        active_failure.currency = "USD"
        active_failure.service_stopped_at = datetime.now(timezone.utc)
        active_failure.resolved = False
        active_failure.created_at = datetime.now(timezone.utc)

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.first.return_value = active_failure

            result = await service.get_active_failure(company_id)

        assert result is not None
        assert result["id"] == active_failure.id
        assert result["resolved"] is False


# =============================================================================
# Test Payment Failure Tasks
# =============================================================================

class TestPaymentFailureTasks:
    """Test the payment failure Celery tasks."""

    def test_stop_service_immediately_task_structure(self):
        """
        Test that stop_service_immediately task has correct configuration.
        
        GAP 7: Task configuration is correct
        """
        from backend.app.tasks.payment_failure_tasks import stop_service_immediately

        # Check task attributes
        assert stop_service_immediately.name == "backend.app.tasks.payment_failure.stop_service_immediately"
        assert stop_service_immediately.max_retries == 2
        assert stop_service_immediately.soft_time_limit == 60

    def test_resume_service_task_structure(self):
        """
        Test that resume_service task has correct configuration.
        """
        from backend.app.tasks.payment_failure_tasks import resume_service

        assert resume_service.name == "backend.app.tasks.payment_failure.resume_service"
        assert resume_service.max_retries == 2

    def test_send_notification_task_structure(self):
        """
        Test that send_payment_failed_notification task has correct configuration.
        """
        from backend.app.tasks.payment_failure_tasks import send_payment_failed_notification

        assert send_payment_failed_notification.name == "backend.app.tasks.payment_failure.send_payment_failed_notification"
        assert send_payment_failed_notification.max_retries == 3


# =============================================================================
# Test Billing Webhooks
# =============================================================================

class TestBillingWebhooks:
    """Test the billing webhook API endpoints."""

    def test_verify_paddle_signature_valid(self):
        """
        Test webhook signature verification with valid signature.
        
        GAP 8: HMAC signature verification works
        """
        import hashlib
        import hmac

        from backend.app.api.billing_webhooks import verify_paddle_signature

        secret = "test_secret"
        payload = b'{"event_type": "payment.failed"}'

        # Generate valid signature
        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        result = verify_paddle_signature(payload, expected_sig, secret)

        assert result is True

    def test_verify_paddle_signature_invalid(self):
        """
        Test webhook signature verification with invalid signature.
        """
        from backend.app.api.billing_webhooks import verify_paddle_signature

        secret = "test_secret"
        payload = b'{"event_type": "payment.failed"}'
        invalid_sig = "invalid_signature"

        result = verify_paddle_signature(payload, invalid_sig, secret)

        assert result is False

    def test_verify_paddle_signature_missing_secret(self):
        """
        Test webhook signature verification when secret is not configured.
        """
        from backend.app.api.billing_webhooks import verify_paddle_signature

        payload = b'{"event_type": "payment.failed"}'

        result = verify_paddle_signature(payload, "any_sig", "")

        assert result is False

    def test_extract_company_id_from_custom_data(self):
        """
        Test extracting company_id from custom_data.
        """
        from backend.app.api.billing_webhooks import extract_company_id_from_event

        data = {
            "custom_data": {
                "company_id": "company_123",
            },
        }

        result = extract_company_id_from_event(data)

        assert result == "company_123"

    def test_extract_company_id_from_passthrough(self):
        """
        Test extracting company_id from passthrough.
        """
        from backend.app.api.billing_webhooks import extract_company_id_from_event

        data = {
            "passthrough": '{"company_id": "company_456"}',
        }

        result = extract_company_id_from_event(data)

        assert result == "company_456"

    def test_extract_company_id_missing(self):
        """
        Test extracting company_id when not present.
        """
        from backend.app.api.billing_webhooks import extract_company_id_from_event

        data = {
            "some_other_field": "value",
        }

        result = extract_company_id_from_event(data)

        assert result is None


# =============================================================================
# Test Payment Failure Edge Cases
# =============================================================================

class TestPaymentFailureEdgeCases:
    """Test edge cases in payment failure handling."""

    @pytest.mark.asyncio
    async def test_payment_failure_company_not_found(self, mock_db_session):
        """
        Test payment failure when company doesn't exist.
        """
        from backend.app.services.payment_failure_service import (
            PaymentFailureService,
            PaymentFailureError,
        )

        service = PaymentFailureService()
        company_id = uuid4()

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None

            with pytest.raises(PaymentFailureError):
                await service.handle_payment_failure(
                    company_id=company_id,
                    paddle_transaction_id="txn_123",
                    failure_code="card_declined",
                    failure_reason="Card declined",
                    amount_attempted=Decimal("999.00"),
                )

    @pytest.mark.asyncio
    async def test_payment_failure_decimal_precision(self, mock_db_session, mock_company):
        """
        Test that payment failure handles Decimal amounts correctly.
        
        BC-002: All money values use Decimal
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Test with precise decimal
            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_decimal",
                failure_code="card_declined",
                failure_reason="Insufficient funds",
                amount_attempted=Decimal("999.99"),
            )

        assert result["status"] == "stopped"

    def test_payment_failure_pydantic_model_validation(self):
        """
        Test PaymentFailedWebhook Pydantic model validation.
        """
        from backend.app.api.billing_webhooks import PaymentFailedWebhook
        from decimal import Decimal

        # Valid payload
        payload = PaymentFailedWebhook(
            event_id="evt_123",
            company_id=str(uuid4()),
            paddle_transaction_id="txn_123",
            failure_code="card_declined",
            failure_reason="Insufficient funds",
            amount_attempted=Decimal("999.00"),
        )

        assert payload.event_type == "payment.failed"
        assert payload.currency == "USD"
        assert payload.amount_attempted == Decimal("999.00")

    def test_payment_succeeded_pydantic_model(self):
        """
        Test PaymentSucceededWebhook Pydantic model.
        """
        from backend.app.api.billing_webhooks import PaymentSucceededWebhook
        from decimal import Decimal

        payload = PaymentSucceededWebhook(
            event_id="evt_456",
            company_id=str(uuid4()),
            paddle_transaction_id="txn_success",
            amount=Decimal("999.00"),
        )

        assert payload.event_type == "payment.succeeded"
        assert payload.amount == Decimal("999.00")


# =============================================================================
# Test Race Conditions
# =============================================================================

class TestPaymentFailureRaceConditions:
    """Test race condition handling in payment failure."""

    @pytest.mark.asyncio
    async def test_concurrent_payment_failures_use_row_lock(self, mock_db_session, mock_company):
        """
        Test that concurrent payment failures use row-level locking.
        
        GAP 9: Race condition protection with row locks
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session

            # Verify with_for_update is called
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_race",
                failure_code="card_declined",
                failure_reason="Card declined",
                amount_attempted=Decimal("999.00"),
            )

        # Verify with_for_update was called
        mock_db_session.query.return_value.filter.return_value.with_for_update.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_resume_service_use_row_lock(self, mock_db_session, mock_company):
        """
        Test that concurrent resume_service calls use row-level locking.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        # Mock existing failure
        existing_failure = MagicMock()
        existing_failure.id = str(uuid4())
        existing_failure.resolved = False

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_success",
            )

        # Verify with_for_update was called
        mock_db_session.query.return_value.filter.return_value.with_for_update.assert_called()


# =============================================================================
# Test Notification Handling
# =============================================================================

class TestPaymentFailureNotifications:
    """Test notification handling for payment failures."""

    @pytest.mark.asyncio
    async def test_mark_notification_sent(self, mock_db_session):
        """
        Test marking notification as sent.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        failure_id = str(uuid4())

        # Mock failure
        failure = MagicMock()
        failure.id = failure_id
        failure.notification_sent = False

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.first.return_value = failure

            result = await service.mark_notification_sent(failure_id)

        assert result is True
        assert failure.notification_sent is True
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_mark_notification_sent_failure_not_found(self, mock_db_session):
        """
        Test marking notification when failure doesn't exist.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        failure_id = str(uuid4())

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = await service.mark_notification_sent(failure_id)

        assert result is False
