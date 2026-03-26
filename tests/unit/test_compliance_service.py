"""
Unit tests for Compliance Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.compliance_service import (
    ComplianceService,
    ComplianceStatus,
    ComplianceType,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def compliance_service(mock_db):
    """Compliance service instance with mocked DB."""
    company_id = uuid.uuid4()
    return ComplianceService(mock_db, company_id)


class TestComplianceServiceInit:
    """Tests for ComplianceService initialization."""

    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = ComplianceService(mock_db, company_id)

        assert service.db == mock_db
        assert service.company_id == company_id

    def test_gdpr_response_days_constant(self, compliance_service):
        """Test GDPR response days constant."""
        assert compliance_service.GDPR_RESPONSE_DAYS == 30

    def test_data_retention_years_constant(self, compliance_service):
        """Test data retention years constant."""
        assert compliance_service.DATA_RETENTION_YEARS == 7


class TestComplianceStatusEnum:
    """Tests for ComplianceStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert ComplianceStatus.PENDING.value == "pending"
        assert ComplianceStatus.IN_PROGRESS.value == "in_progress"
        assert ComplianceStatus.COMPLETED.value == "completed"
        assert ComplianceStatus.FAILED.value == "failed"
        assert ComplianceStatus.REJECTED.value == "rejected"


class TestComplianceTypeEnum:
    """Tests for ComplianceType enum."""

    def test_type_values(self):
        """Test type enum values."""
        assert ComplianceType.GDPR_ACCESS.value == "gdpr_access"
        assert ComplianceType.GDPR_DELETE.value == "gdpr_delete"
        assert ComplianceType.GDPR_PORTABILITY.value == "gdpr_portability"
        assert ComplianceType.DATA_CORRECTION.value == "data_correction"
        assert ComplianceType.CONSENT_WITHDRAWAL.value == "consent_withdrawal"
        assert ComplianceType.RETENTION_REVIEW.value == "retention_review"


class TestCreateRequest:
    """Tests for create_request method."""

    @pytest.mark.asyncio
    async def test_create_request_returns_dict(self, compliance_service, mock_db):
        """Test that create_request returns proper dict."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        requested_by = uuid.uuid4()
        subject_email = "subject@example.com"

        result = await compliance_service.create_request(
            request_type=ComplianceType.GDPR_ACCESS,
            requested_by=requested_by,
            subject_email=subject_email
        )

        assert result is not None
        assert "request_id" in result
        assert result["request_type"] == "gdpr_access"
        assert result["status"] == "pending"
        assert result["subject_email"] == subject_email

    @pytest.mark.asyncio
    async def test_create_request_with_description(self, compliance_service, mock_db):
        """Test create_request with description."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        requested_by = uuid.uuid4()
        subject_email = "subject@example.com"

        result = await compliance_service.create_request(
            request_type=ComplianceType.GDPR_ACCESS,
            requested_by=requested_by,
            subject_email=subject_email,
            description="Test description"
        )

        assert result["description"] == "Test description"

    @pytest.mark.asyncio
    async def test_create_request_calculates_deadline(self, compliance_service, mock_db):
        """Test that create_request calculates 30-day deadline."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        requested_by = uuid.uuid4()
        subject_email = "subject@example.com"

        result = await compliance_service.create_request(
            request_type=ComplianceType.GDPR_DELETE,
            requested_by=requested_by,
            subject_email=subject_email
        )

        assert "deadline" in result
        deadline = datetime.fromisoformat(result["deadline"])
        now = datetime.now(timezone.utc)
        days_until_deadline = (deadline - now).days

        # Should be approximately 30 days
        assert 29 <= days_until_deadline <= 31


class TestGetRequest:
    """Tests for get_request method."""

    @pytest.mark.asyncio
    async def test_get_request_returns_dict(self, compliance_service, mock_db):
        """Test that get_request returns dict."""
        request_id = uuid.uuid4()

        # Create a mock request
        mock_request = MagicMock()
        mock_request.id = request_id
        mock_request.company_id = compliance_service.company_id
        mock_request.request_type = MagicMock()
        mock_request.request_type.value = "gdpr_export"
        mock_request.status = MagicMock()
        mock_request.status.value = "pending"
        mock_request.customer_email = "test@example.com"
        mock_request.requested_at = datetime.now(timezone.utc)
        mock_request.completed_at = None
        mock_request.result_url = None
        mock_request.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_request
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.get_request(request_id)

        assert result is not None
        assert "request_id" in result

    @pytest.mark.asyncio
    async def test_get_request_returns_none_if_not_found(self, compliance_service, mock_db):
        """Test that get_request returns None if not found."""
        request_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.get_request(request_id)

        assert result is None


class TestListRequests:
    """Tests for list_requests method."""

    @pytest.mark.asyncio
    async def test_list_requests_returns_list(self, compliance_service, mock_db):
        """Test that list_requests returns list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.list_requests()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_requests_with_status_filter(self, compliance_service, mock_db):
        """Test list_requests with status filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await compliance_service.list_requests(status=ComplianceStatus.PENDING)

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_requests_with_type_filter(self, compliance_service, mock_db):
        """Test list_requests with type filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await compliance_service.list_requests(request_type=ComplianceType.GDPR_ACCESS)

        mock_db.execute.assert_called_once()


class TestProcessGDPRAccessRequest:
    """Tests for process_gdpr_access_request method."""

    @pytest.mark.asyncio
    async def test_process_access_returns_dict(self, compliance_service, mock_db):
        """Test that process_gdpr_access_request returns dict."""
        request_id = uuid.uuid4()

        # Mock the get_request method to return a request
        mock_request = MagicMock()
        mock_request.id = request_id
        mock_request.company_id = compliance_service.company_id
        mock_request.request_type = MagicMock()
        mock_request.request_type.value = "gdpr_export"
        mock_request.status = MagicMock()
        mock_request.status.value = "pending"
        mock_request.customer_email = "test@example.com"
        mock_request.requested_at = datetime.now(timezone.utc)
        mock_request.completed_at = None
        mock_request.result_url = None
        mock_request.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_request
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await compliance_service.process_gdpr_access_request(request_id)

        assert result["status"] == "completed"
        assert "data_collected" in result

    @pytest.mark.asyncio
    async def test_process_access_raises_if_not_found(self, compliance_service, mock_db):
        """Test that process_gdpr_access_request raises if not found."""
        request_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError):
            await compliance_service.process_gdpr_access_request(request_id)


class TestProcessGDPRDeleteRequest:
    """Tests for process_gdpr_delete_request method."""

    @pytest.mark.asyncio
    async def test_process_delete_returns_dict(self, compliance_service, mock_db):
        """Test that process_gdpr_delete_request returns dict."""
        request_id = uuid.uuid4()

        # Mock the get_request method to return a request
        mock_request = MagicMock()
        mock_request.id = request_id
        mock_request.company_id = compliance_service.company_id
        mock_request.request_type = MagicMock()
        mock_request.request_type.value = "gdpr_delete"
        mock_request.status = MagicMock()
        mock_request.status.value = "pending"
        mock_request.customer_email = "test@example.com"
        mock_request.requested_at = datetime.now(timezone.utc)
        mock_request.completed_at = None
        mock_request.result_url = None
        mock_request.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_request
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        result = await compliance_service.process_gdpr_delete_request(request_id)

        assert result["status"] == "completed"
        assert "deleted_at" in result
        assert "note" in result
        assert "soft-delete" in result["note"].lower() or "soft deleted" in result["note"].lower()

    @pytest.mark.asyncio
    async def test_process_delete_raises_if_not_found(self, compliance_service, mock_db):
        """Test that process_gdpr_delete_request raises if not found."""
        request_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError):
            await compliance_service.process_gdpr_delete_request(request_id)


class TestCheckDeadlines:
    """Tests for check_deadlines method."""

    @pytest.mark.asyncio
    async def test_check_deadlines_returns_list(self, compliance_service, mock_db):
        """Test that check_deadlines returns list."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.check_deadlines()

        assert isinstance(result, list)


class TestGenerateComplianceReport:
    """Tests for generate_compliance_report method."""

    @pytest.mark.asyncio
    async def test_generate_report_returns_dict(self, compliance_service, mock_db):
        """Test that generate_compliance_report returns dict."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.generate_compliance_report()

        assert "company_id" in result
        assert "metrics" in result
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_generate_report_with_date_filters(self, compliance_service, mock_db):
        """Test generate_compliance_report with date filters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        result = await compliance_service.generate_compliance_report(
            start_date=start_date,
            end_date=end_date
        )

        assert "report_period" in result
        assert result["report_period"]["start"] is not None
        assert result["report_period"]["end"] is not None

    @pytest.mark.asyncio
    async def test_generate_report_metrics_structure(self, compliance_service, mock_db):
        """Test that report metrics have correct structure."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await compliance_service.generate_compliance_report()

        metrics = result["metrics"]
        assert "total_requests" in metrics
        assert "completed" in metrics
        assert "pending" in metrics
        assert "failed" in metrics
        assert "overdue" in metrics
        assert "average_resolution_days" in metrics
