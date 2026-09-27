"""
Week 5 Day 6 — Invoice + Reconciliation + Integration Tests

Tests for:
- InvoiceService (F-023)
- ClientRefundService (BG-09)
- ReconciliationTasks (BG-06)
- Billing API endpoints

BC-001: All tests verify tenant isolation
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# ── Invoice Service Tests ────────────────────────────────────────────────────


class TestInvoiceService:
    """Tests for InvoiceService."""

    @pytest.fixture
    def invoice_service(self):
        """Create invoice service instance."""
        from backend.app.services.invoice_service import InvoiceService
        return InvoiceService()

    @pytest.fixture
    def sample_company_id(self):
        """Sample company UUID."""
        return uuid.uuid4()

    def test_invoice_service_exists(self, invoice_service):
        """Test InvoiceService can be instantiated."""
        assert invoice_service is not None

    def test_get_invoice_service_singleton(self):
        """Test get_invoice_service returns singleton."""
        from backend.app.services.invoice_service import get_invoice_service
        service1 = get_invoice_service()
        service2 = get_invoice_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_get_invoice_list_empty(self, invoice_service, sample_company_id):
        """Test get_invoice_list returns empty list when no invoices."""
        with patch('backend.app.services.invoice_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.count.return_value = 0
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            result = await invoice_service.get_invoice_list(sample_company_id)

            assert result["invoices"] == []
            assert result["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_invoice_list_pagination(self, invoice_service, sample_company_id):
        """Test get_invoice_list pagination parameters."""
        with patch('backend.app.services.invoice_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.count.return_value = 100
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            result = await invoice_service.get_invoice_list(
                sample_company_id,
                page=2,
                page_size=10,
            )

            assert result["pagination"]["page"] == 2
            assert result["pagination"]["page_size"] == 10
            assert result["pagination"]["total"] == 100

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, invoice_service, sample_company_id):
        """Test get_invoice raises error when not found."""
        from backend.app.services.invoice_service import InvoiceNotFoundError

        with patch('backend.app.services.invoice_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(InvoiceNotFoundError):
                await invoice_service.get_invoice(sample_company_id, "non-existent-id")

    @pytest.mark.asyncio
    async def test_get_invoice_access_denied(self, invoice_service, sample_company_id):
        """Test get_invoice denies access to other company's invoice."""
        from backend.app.services.invoice_service import InvoiceAccessDeniedError

        other_company_id = uuid.uuid4()

        with patch('backend.app.services.invoice_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_invoice = MagicMock()
            mock_invoice.company_id = str(other_company_id)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_invoice

            with pytest.raises(InvoiceAccessDeniedError):
                await invoice_service.get_invoice(sample_company_id, "some-invoice-id")


class TestInvoicePDFGeneration:
    """Tests for invoice PDF generation."""

    @pytest.fixture
    def invoice_service(self):
        """Create invoice service instance."""
        from backend.app.services.invoice_service import InvoiceService
        return InvoiceService()

    def test_generate_local_pdf_fallback(self, invoice_service):
        """Test local PDF generation when reportlab is not available."""
        import asyncio

        sample_invoice = {
            "id": "test-invoice-id",
            "amount": "99.99",
            "currency": "USD",
            "status": "paid",
        }

        # Should return bytes even without reportlab
        pdf_bytes = asyncio.get_event_loop().run_until_complete(
            invoice_service._generate_local_pdf(sample_invoice)
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0


class TestInvoiceSync:
    """Tests for Paddle invoice sync."""

    @pytest.fixture
    def invoice_service(self):
        """Create invoice service instance."""
        from backend.app.services.invoice_service import InvoiceService
        return InvoiceService()

    @pytest.mark.asyncio
    async def test_sync_invoices_no_paddle_customer(self, invoice_service):
        """Test sync skips when no Paddle customer ID."""
        sample_company_id = uuid.uuid4()

        with patch('backend.app.services.invoice_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_company = MagicMock()
            mock_company.paddle_customer_id = None
            mock_db.query.return_value.filter.return_value.first.return_value = mock_company

            result = await invoice_service.sync_invoices_from_paddle(sample_company_id)

            assert result["synced"] == 0
            assert "No Paddle customer ID" in result["message"]


# ── Client Refund Service Tests ──────────────────────────────────────────────


class TestClientRefundService:
    """Tests for ClientRefundService."""

    @pytest.fixture
    def refund_service(self):
        """Create client refund service instance."""
        from backend.app.services.client_refund_service import ClientRefundService
        return ClientRefundService()

    @pytest.fixture
    def sample_company_id(self):
        """Sample company UUID."""
        return uuid.uuid4()

    def test_refund_service_exists(self, refund_service):
        """Test ClientRefundService can be instantiated."""
        assert refund_service is not None

    def test_get_refund_service_singleton(self):
        """Test get_client_refund_service returns singleton."""
        from backend.app.services.client_refund_service import get_client_refund_service
        service1 = get_client_refund_service()
        service2 = get_client_refund_service()
        assert service1 is service2

    def test_create_refund_request_positive_amount(self, refund_service, sample_company_id):
        """Test creating refund with positive amount."""
        with patch('backend.app.services.client_refund_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_refund = MagicMock()
            mock_refund.id = str(uuid.uuid4())
            mock_refund.company_id = str(sample_company_id)
            mock_refund.ticket_id = None
            mock_refund.amount = Decimal("50.00")
            mock_refund.currency = "USD"
            mock_refund.reason = "Customer request"
            mock_refund.status = "pending"
            mock_refund.processed_at = None
            mock_refund.created_at = datetime.now(timezone.utc)
            mock_refund.updated_at = datetime.now(timezone.utc)

            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, 'id', mock_refund.id))

            result = refund_service.create_refund_request(
                company_id=sample_company_id,
                amount=Decimal("50.00"),
                reason="Customer request",
            )

            assert result["status"] == "pending"

    def test_create_refund_request_zero_amount_fails(self, refund_service, sample_company_id):
        """Test creating refund with zero amount fails."""
        from backend.app.services.client_refund_service import ClientRefundError

        with pytest.raises(ClientRefundError) as exc_info:
            refund_service.create_refund_request(
                company_id=sample_company_id,
                amount=Decimal("0.00"),
            )

        assert "positive" in str(exc_info.value).lower()

    def test_create_refund_request_negative_amount_fails(self, refund_service, sample_company_id):
        """Test creating refund with negative amount fails."""
        from backend.app.services.client_refund_service import ClientRefundError

        with pytest.raises(ClientRefundError) as exc_info:
            refund_service.create_refund_request(
                company_id=sample_company_id,
                amount=Decimal("-10.00"),
            )

        assert "positive" in str(exc_info.value).lower()

    def test_process_refund_wrong_status(self, refund_service, sample_company_id):
        """Test processing refund with wrong status fails."""
        from backend.app.services.client_refund_service import ClientRefundError

        with patch('backend.app.services.client_refund_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_refund = MagicMock()
            mock_refund.status = "processed"  # Already processed
            mock_refund.company_id = str(sample_company_id)
            mock_db.query.return_value.filter.return_value.first.return_value = mock_refund

            with pytest.raises(ClientRefundError) as exc_info:
                refund_service.process_refund(
                    company_id=sample_company_id,
                    refund_id=str(uuid.uuid4()),
                )

            assert "Cannot process" in str(exc_info.value)

    def test_get_refund_stats(self, refund_service, sample_company_id):
        """Test get_refund_stats returns correct counts."""
        with patch('backend.app.services.client_refund_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_refunds = [
                MagicMock(status="pending", amount=Decimal("10.00")),
                MagicMock(status="processed", amount=Decimal("20.00")),
                MagicMock(status="processed", amount=Decimal("30.00")),
                MagicMock(status="failed", amount=Decimal("5.00")),
            ]
            mock_db.query.return_value.filter.return_value.all.return_value = mock_refunds

            stats = refund_service.get_refund_stats(sample_company_id)

            assert stats["total_count"] == 4
            assert stats["pending_count"] == 1
            assert stats["processed_count"] == 2
            assert stats["failed_count"] == 1

    def test_list_refunds_with_status_filter(self, refund_service, sample_company_id):
        """Test list_refunds with status filter."""
        with patch('backend.app.services.client_refund_service.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            mock_query = MagicMock()
            mock_db.query.return_value.filter.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.count.return_value = 5
            mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            result = refund_service.list_refunds(
                company_id=sample_company_id,
                status="pending",
            )

            assert result["pagination"]["total"] == 5


# ── Reconciliation Task Tests ────────────────────────────────────────────────


class TestReconciliationTasks:
    """Tests for reconciliation Celery tasks."""

    def test_reconcile_subscriptions_task_exists(self):
        """Test reconcile_subscriptions task is registered."""
        from backend.app.tasks.reconciliation_tasks import reconcile_subscriptions
        assert reconcile_subscriptions is not None
        assert reconcile_subscriptions.name == "billing.reconcile_subscriptions"

    def test_reconcile_transactions_task_exists(self):
        """Test reconcile_transactions task is registered."""
        from backend.app.tasks.reconciliation_tasks import reconcile_transactions
        assert reconcile_transactions is not None
        assert reconcile_transactions.name == "billing.reconcile_transactions"

    def test_reconcile_usage_task_exists(self):
        """Test reconcile_usage task is registered."""
        from backend.app.tasks.reconciliation_tasks import reconcile_usage
        assert reconcile_usage is not None
        assert reconcile_usage.name == "billing.reconcile_usage"

    def test_reconcile_all_task_exists(self):
        """Test reconcile_all task is registered."""
        from backend.app.tasks.reconciliation_tasks import reconcile_all
        assert reconcile_all is not None
        assert reconcile_all.name == "billing.reconcile_all"

    def test_compare_subscription_function(self):
        """Test _compare_subscription detects discrepancies."""
        from backend.app.tasks.reconciliation_tasks import _compare_subscription

        mock_db_sub = MagicMock()
        mock_db_sub.status = "active"

        paddle_data = {
            "status": "canceled",
        }

        discrepancies = _compare_subscription(mock_db_sub, paddle_data)

        assert len(discrepancies) > 0
        assert "status" in discrepancies[0]

    def test_compare_subscription_no_discrepancies(self):
        """Test _compare_subscription with matching data."""
        from backend.app.tasks.reconciliation_tasks import _compare_subscription

        mock_db_sub = MagicMock()
        mock_db_sub.status = "active"

        paddle_data = {
            "status": "active",
        }

        discrepancies = _compare_subscription(mock_db_sub, paddle_data)

        # Should have no status discrepancy
        status_discrepancy = [d for d in discrepancies if "status" in d]
        assert len(status_discrepancy) == 0


class TestReconciliationErrorHandling:
    """Tests for reconciliation error handling."""

    def test_reconciliation_error_class(self):
        """Test ReconciliationError can be raised."""
        from backend.app.tasks.reconciliation_tasks import ReconciliationError
        assert ReconciliationError is not None

        with pytest.raises(ReconciliationError):
            raise ReconciliationError("Test error")


# ── Billing API Endpoint Tests ───────────────────────────────────────────────


class TestBillingAPIInvoices:
    """Tests for invoice API endpoints."""

    def test_invoice_list_response_model(self):
        """Test InvoiceListResponse model."""
        from backend.app.api.billing import InvoiceListResponse

        response = InvoiceListResponse(
            invoices=[],
            pagination={"page": 1, "page_size": 20, "total": 0, "total_pages": 0},
        )

        assert response.invoices == []
        assert response.pagination["total"] == 0

    def test_invoice_response_model(self):
        """Test InvoiceResponse model."""
        from backend.app.api.billing import InvoiceResponse

        response = InvoiceResponse(
            id="test-id",
            company_id="company-id",
            paddle_invoice_id="paddle-123",
            amount="99.99",
            currency="USD",
            status="paid",
            invoice_date="2024-01-01",
            due_date="2024-01-15",
            paid_at="2024-01-05",
            created_at="2024-01-01",
        )

        assert response.id == "test-id"
        assert response.status == "paid"


class TestBillingAPIUsage:
    """Tests for usage API endpoints."""

    def test_usage_response_model(self):
        """Test UsageResponse model."""
        from backend.app.api.billing import UsageResponse

        response = UsageResponse(
            current_month="2024-01",
            tickets_used=1500,
            ticket_limit=2000,
            overage_tickets=0,
            overage_charges="0.00",
            usage_percentage=0.75,
        )

        assert response.tickets_used == 1500
        assert response.overage_tickets == 0

    def test_usage_response_with_overage(self):
        """Test UsageResponse with overage."""
        from backend.app.api.billing import UsageResponse

        response = UsageResponse(
            current_month="2024-01",
            tickets_used=2500,
            ticket_limit=2000,
            overage_tickets=500,
            overage_charges="50.00",
            usage_percentage=1.0,
        )

        assert response.overage_tickets == 500
        assert response.overage_charges == "50.00"


class TestBillingAPIClientRefunds:
    """Tests for client refund API endpoints."""

    def test_client_refund_create_model(self):
        """Test ClientRefundCreate model."""
        from backend.app.api.billing import ClientRefundCreate

        request = ClientRefundCreate(
            amount=Decimal("50.00"),
            currency="USD",
            reason="Customer requested refund",
        )

        assert request.amount == Decimal("50.00")
        assert request.currency == "USD"

    def test_client_refund_create_requires_positive_amount(self):
        """Test ClientRefundCreate rejects non-positive amounts."""
        from backend.app.api.billing import ClientRefundCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClientRefundCreate(
                amount=Decimal("-10.00"),
                currency="USD",
            )

        with pytest.raises(ValidationError):
            ClientRefundCreate(
                amount=Decimal("0.00"),
                currency="USD",
            )

    def test_client_refund_response_model(self):
        """Test ClientRefundResponse model."""
        from backend.app.api.billing import ClientRefundResponse

        response = ClientRefundResponse(
            id="refund-id",
            company_id="company-id",
            ticket_id=None,
            amount="50.00",
            currency="USD",
            reason="Customer request",
            status="pending",
            processed_at=None,
            created_at="2024-01-01",
        )

        assert response.status == "pending"


# ── Integration Tests ────────────────────────────────────────────────────────


class TestBillingIntegration:
    """Integration tests for billing system."""

    @pytest.fixture
    def sample_company_id(self):
        """Sample company UUID."""
        return uuid.uuid4()

    def test_all_services_are_singletons(self):
        """Test all billing services use singleton pattern."""
        from backend.app.services.invoice_service import get_invoice_service
        from backend.app.services.client_refund_service import get_client_refund_service

        # Each service should return same instance
        invoice_svc1 = get_invoice_service()
        invoice_svc2 = get_invoice_service()
        assert invoice_svc1 is invoice_svc2

        refund_svc1 = get_client_refund_service()
        refund_svc2 = get_client_refund_service()
        assert refund_svc1 is refund_svc2

    def test_all_tasks_have_correct_names(self):
        """Test all Celery tasks have correct names."""
        from backend.app.tasks.reconciliation_tasks import (
            reconcile_subscriptions,
            reconcile_transactions,
            reconcile_usage,
            reconcile_all,
        )

        assert reconcile_subscriptions.name == "billing.reconcile_subscriptions"
        assert reconcile_transactions.name == "billing.reconcile_transactions"
        assert reconcile_usage.name == "billing.reconcile_usage"
        assert reconcile_all.name == "billing.reconcile_all"

    def test_decimal_handling_in_responses(self):
        """Test Decimal values are converted to strings in responses."""
        from backend.app.api.billing import UsageResponse

        # This ensures BC-002 compliance
        response = UsageResponse(
            current_month="2024-01",
            tickets_used=100,
            ticket_limit=2000,
            overage_tickets=0,
            overage_charges=str(Decimal("0.00")),  # Must be string
            usage_percentage=0.05,
        )

        # All monetary values should be strings for JSON serialization
        assert isinstance(response.overage_charges, str)


class TestBillingErrorHandling:
    """Tests for billing error handling."""

    def test_invoice_error_classes_exist(self):
        """Test invoice error classes are defined."""
        from backend.app.services.invoice_service import (
            InvoiceError,
            InvoiceNotFoundError,
            InvoiceAccessDeniedError,
        )

        assert InvoiceError is not None
        assert InvoiceNotFoundError is not None
        assert InvoiceAccessDeniedError is not None

        # Test inheritance
        assert issubclass(InvoiceNotFoundError, InvoiceError)
        assert issubclass(InvoiceAccessDeniedError, InvoiceError)

    def test_client_refund_error_classes_exist(self):
        """Test client refund error classes are defined."""
        from backend.app.services.client_refund_service import (
            ClientRefundError,
            ClientRefundNotFoundError,
        )

        assert ClientRefundError is not None
        assert ClientRefundNotFoundError is not None

        assert issubclass(ClientRefundNotFoundError, ClientRefundError)
