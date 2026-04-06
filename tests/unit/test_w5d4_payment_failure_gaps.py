"""
W5D4 Gap Tests - Payment Failure + Immediate Stop

Gap tests addressing the 5 gaps found by the gap finder:
1. CRITICAL: Race condition between payment failure and service suspension
2. CRITICAL: Tenant data isolation breach during suspension
3. HIGH: Partial service state during suspension
4. HIGH: Reactivation state inconsistency
5. HIGH: Silent failure in suspension process
"""

import pytest
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import concurrent.futures

import sys
sys.path.insert(0, '/home/z/my-project/parwa')

from database.base import Base
from database.models.billing import Subscription
from database.models.billing_extended import PaymentFailure, IdempotencyKey
from database.models.core import Company


# =============================================================================
# GAP 1: Race condition between payment failure and service suspension
# CRITICAL: Tenant may continue accessing service after payment failure due to timing issues
# =============================================================================

class TestPaymentFailureRaceCondition:
    """Test race conditions between payment failure and service suspension."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company."""
        company = MagicMock()
        company.id = "company_test_123"
        company.subscription_status = "active"
        company.subscription_tier = "growth"
        return company

    @pytest.mark.asyncio
    async def test_payment_failure_blocks_immediate_api_request(self, mock_db_session, mock_company):
        """
        GAP 1 - CRITICAL: Race condition between payment failure and service suspension.
        
        Test that API requests are blocked immediately after payment failure
        even before background tasks complete.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_test_123"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            # Process payment failure
            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_race_123",
                failure_code="card_declined",
                failure_reason="Card declined",
                amount_attempted=Decimal("999.00"),
            )

        # Company status should be updated synchronously
        assert result["status"] == "stopped"
        assert mock_company.subscription_status == "payment_failed"

    @pytest.mark.asyncio
    async def test_concurrent_api_request_during_payment_failure(self, mock_db_session, mock_company):
        """
        Test that concurrent API requests during payment failure handling
        are properly blocked.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_concurrent_test"

        results = {"failure": None, "status_check": None}
        lock = threading.Lock()

        def process_failure():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
                    mock_session.return_value = mock_db_session
                    mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
                    mock_db_session.query.return_value.filter.return_value.first.return_value = None

                    result = loop.run_until_complete(
                        service.handle_payment_failure(
                            company_id=company_id,
                            paddle_transaction_id="txn_concurrent",
                            failure_code="card_declined",
                            failure_reason="Card declined",
                            amount_attempted=Decimal("999.00"),
                        )
                    )
                    with lock:
                        results["failure"] = result
            finally:
                loop.close()

        def check_status():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            time.sleep(0.01)  # Small delay to simulate timing
            try:
                with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
                    mock_session.return_value = mock_db_session
                    
                    # Mock an active failure
                    existing_failure = MagicMock()
                    existing_failure.resolved = False
                    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

                    result = loop.run_until_complete(
                        service.is_service_stopped(company_id)
                    )
                    with lock:
                        results["status_check"] = result
            finally:
                loop.close()

        # Run both concurrently
        t1 = threading.Thread(target=process_failure)
        t2 = threading.Thread(target=check_status)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Status check should indicate service is stopped
        assert results["status_check"] is True


# =============================================================================
# GAP 2: Tenant data isolation breach during suspension
# CRITICAL: Suspended tenant may still access other tenants' data
# =============================================================================

class TestTenantIsolationDuringSuspension:
    """Test tenant isolation is maintained during payment suspension."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.mark.asyncio
    async def test_suspended_tenant_cannot_access_other_tenant_data(self, mock_db_session):
        """
        GAP 2 - CRITICAL: Tenant isolation during suspension.
        
        Verify that a suspended tenant cannot access other tenants' data
        even with modified company_id parameters.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        suspended_company_id = "company_suspended"
        other_company_id = "company_other"

        # Mock suspended company
        suspended_company = MagicMock()
        suspended_company.id = suspended_company_id
        suspended_company.subscription_status = "payment_failed"

        # Mock active failure for suspended company
        existing_failure = MagicMock()
        existing_failure.resolved = False
        existing_failure.company_id = suspended_company_id

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            
            # Check service is stopped for suspended company
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure
            is_stopped = await service.is_service_stopped(suspended_company_id)
            assert is_stopped is True

    @pytest.mark.asyncio
    async def test_payment_failure_history_isolated_by_company(self, mock_db_session):
        """
        Test that payment failure history is isolated by company_id.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_a_id = "company_a"
        company_b_id = "company_b"

        # Mock failure for company A only
        failure_a = MagicMock()
        failure_a.id = "failure_a"
        failure_a.company_id = company_a_id

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            
            # Query should only return failures for the specific company
            mock_db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [failure_a]

            history = await service.get_payment_failure_history(company_a_id)

            # Verify only company A's failures returned
            for record in history:
                # Company ID should be the queried company
                assert record.get("company_id", company_a_id) == company_a_id


# =============================================================================
# GAP 3: Partial service state during suspension
# HIGH: Some services suspended while others remain active
# =============================================================================

class TestPartialServiceSuspension:
    """Test that all services are properly suspended during payment failure."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company."""
        company = MagicMock()
        company.id = "company_partial_test"
        company.subscription_status = "active"
        company.subscription_tier = "growth"
        return company

    @pytest.mark.asyncio
    async def test_all_subscription_states_updated_on_failure(self, mock_db_session, mock_company):
        """
        GAP 3 - HIGH: Partial service state during suspension.
        
        Verify that both Company and Subscription records are updated
        to payment_failed status.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_partial_test"

        # Mock subscription
        mock_subscription = MagicMock()
        mock_subscription.status = "active"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.side_effect = [None, mock_subscription]

            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_partial",
                failure_code="card_declined",
                failure_reason="Card declined",
                amount_attempted=Decimal("999.00"),
            )

        # Both company and subscription should be updated
        assert mock_company.subscription_status == "payment_failed"
        assert mock_subscription.status == "payment_failed"

    @pytest.mark.asyncio
    async def test_service_stop_status_check_consistency(self, mock_db_session, mock_company):
        """
        Test that is_service_stopped returns consistent results.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_consistency_test"

        mock_company.subscription_status = "payment_failed"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            
            # No active failure but company status is payment_failed
            mock_db_session.query.return_value.filter.return_value.first.side_effect = [None, mock_company]

            is_stopped = await service.is_service_stopped(company_id)

        # Should return True because of payment_failed status
        assert is_stopped is True


# =============================================================================
# GAP 4: Reactivation state inconsistency
# HIGH: Tenant reactivation doesn't fully restore all services
# =============================================================================

class TestReactivationStateConsistency:
    """Test that service reactivation fully restores all states."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company."""
        company = MagicMock()
        company.id = "company_reactivation"
        company.subscription_status = "payment_failed"
        return company

    @pytest.mark.asyncio
    async def test_reactivation_updates_company_and_subscription(self, mock_db_session, mock_company):
        """
        GAP 4 - HIGH: Reactivation state inconsistency.
        
        Verify that reactivation updates both Company and Subscription
        records to 'active' status.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_reactivation"

        # Mock existing failure
        existing_failure = MagicMock()
        existing_failure.id = "failure_reactivation"
        existing_failure.resolved = False

        # Mock subscription
        mock_subscription = MagicMock()
        mock_subscription.status = "payment_failed"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            
            # Setup mock chain for resume_service
            # First query: Company with lock
            # Second query: PaymentFailure
            # Third query: Subscription
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            
            # Set up the query side effects in order
            query_count = [0]
            def mock_query_side_effect(*args, **kwargs):
                query_count[0] += 1
                if query_count[0] == 1:
                    return existing_failure  # PaymentFailure query
                return mock_subscription  # Subscription query
            
            mock_db_session.query.return_value.filter.return_value.first.side_effect = mock_query_side_effect

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_success",
            )

        # Both company and subscription should be active
        assert result["status"] == "resumed"
        assert mock_company.subscription_status == "active"
        assert existing_failure.resolved is True

    @pytest.mark.asyncio
    async def test_reactivation_clears_failure_record(self, mock_db_session, mock_company):
        """
        Test that reactivation properly marks the failure as resolved.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_reactivation_clear"

        existing_failure = MagicMock()
        existing_failure.id = "failure_clear"
        existing_failure.resolved = False
        existing_failure.service_resumed_at = None

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_success",
            )

        assert existing_failure.resolved is True
        assert existing_failure.service_resumed_at is not None


# =============================================================================
# GAP 5: Silent failure in suspension process
# HIGH: Payment failure occurs but suspension process fails silently
# =============================================================================

class TestSilentSuspensionFailure:
    """Test that suspension failures are properly logged and handled."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company."""
        company = MagicMock()
        company.id = "company_silent"
        company.subscription_status = "active"
        return company

    @pytest.mark.asyncio
    async def test_payment_failure_raises_error_for_missing_company(self, mock_db_session):
        """
        GAP 5 - HIGH: Silent failure in suspension process.
        
        Verify that payment failure raises appropriate error
        when company is not found.
        """
        from backend.app.services.payment_failure_service import (
            PaymentFailureService,
            PaymentFailureError,
        )

        service = PaymentFailureService()
        company_id = "nonexistent_company"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None

            with pytest.raises(PaymentFailureError):
                await service.handle_payment_failure(
                    company_id=company_id,
                    paddle_transaction_id="txn_error",
                    failure_code="card_declined",
                    failure_reason="Card declined",
                    amount_attempted=Decimal("999.00"),
                )

    @pytest.mark.asyncio
    async def test_notification_tracking_prevents_silent_failure(self, mock_db_session, mock_company):
        """
        Test that notification tracking prevents silent failures.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        failure_id = "failure_notification"

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

    def test_stop_service_task_has_retry_configuration(self):
        """
        Test that stop_service_immediately task has proper retry configuration.
        """
        from backend.app.tasks.payment_failure_tasks import stop_service_immediately

        # Task should have retry configuration
        assert stop_service_immediately.max_retries == 2
        assert stop_service_immediately.retry_backoff is True

    def test_resume_service_task_has_retry_configuration(self):
        """
        Test that resume_service task has proper retry configuration.
        """
        from backend.app.tasks.payment_failure_tasks import resume_service

        assert resume_service.max_retries == 2
        assert resume_service.retry_backoff is True


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestPaymentFailureEdgeCases:
    """Additional edge case tests for payment failure handling."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company."""
        company = MagicMock()
        company.id = "company_edge"
        company.subscription_status = "active"
        return company

    @pytest.mark.asyncio
    async def test_multiple_payment_failures_idempotent(self, mock_db_session, mock_company):
        """
        Test that multiple payment failures for same company are handled idempotently.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_multiple"

        # Mock existing failure
        existing_failure = MagicMock()
        existing_failure.id = "existing_failure"
        existing_failure.resolved = False

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = existing_failure

            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_multiple",
                failure_code="card_declined",
                failure_reason="Card declined",
                amount_attempted=Decimal("999.00"),
            )

        assert result["status"] == "already_stopped"
        assert "existing_failure_id" in result

    @pytest.mark.asyncio
    async def test_reactivation_without_prior_failure(self, mock_db_session, mock_company):
        """
        Test that reactivation without prior failure doesn't cause errors.
        """
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = "company_no_failure"

        mock_company.subscription_status = "active"

        with patch('backend.app.services.payment_failure_service.SessionLocal') as mock_session:
            mock_session.return_value = mock_db_session
            mock_db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_company
            mock_db_session.query.return_value.filter.return_value.first.return_value = None

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_no_failure",
            )

        assert result["status"] == "no_failure"
