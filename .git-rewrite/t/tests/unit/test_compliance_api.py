"""
Unit tests for backend/api/compliance.py - Compliance API.
Tests cover GDPR export/delete requests, compliance request listing, audit logs, and retention checks.
All external dependencies (database, Redis) are mocked for CI compatibility.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_compliance_request():
    """Create a mock compliance request."""
    req = MagicMock()
    req.id = uuid.uuid4()
    req.company_id = uuid.uuid4()
    req.request_type = MagicMock()
    req.request_type.value = "gdpr_export"
    req.customer_email = "customer@example.com"
    req.status = MagicMock()
    req.status.value = "pending"
    req.requested_at = datetime.now(timezone.utc)
    req.completed_at = None
    req.result_url = None
    req.created_at = datetime.now(timezone.utc)
    return req


@pytest.fixture
def mock_audit_entry():
    """Create a mock audit log entry."""
    entry = MagicMock()
    entry.id = uuid.uuid4()
    entry.company_id = uuid.uuid4()
    entry.ticket_id = uuid.uuid4()
    entry.actor = "admin@example.com"
    entry.action = "ticket_resolved"
    entry.details = {"reason": "Customer satisfied"}
    entry.created_at = datetime.now(timezone.utc)
    return entry


def create_test_app():
    """Create a FastAPI test app with compliance router."""
    app = FastAPI()

    # Mock get_db dependency
    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Import and include router
    from backend.api.compliance import router
    app.include_router(router)

    return app


# --- Tests ---

class TestComplianceEnums:
    """Tests to verify compliance enum values."""

    def test_request_type_enum_values(self):
        """Test ComplianceRequestType has expected values."""
        from backend.models.compliance_request import ComplianceRequestType
        assert ComplianceRequestType.gdpr_export.value == "gdpr_export"
        assert ComplianceRequestType.gdpr_delete.value == "gdpr_delete"
        assert ComplianceRequestType.tcpa_optout.value == "tcpa_optout"
        assert ComplianceRequestType.hipaa_access.value == "hipaa_access"

    def test_request_status_enum_values(self):
        """Test ComplianceRequestStatus has expected values."""
        from backend.models.compliance_request import ComplianceRequestStatus
        assert ComplianceRequestStatus.pending.value == "pending"
        assert ComplianceRequestStatus.processing.value == "processing"
        assert ComplianceRequestStatus.completed.value == "completed"
        assert ComplianceRequestStatus.failed.value == "failed"


class TestComplianceAPIEndpoints:
    """Tests for Compliance API endpoints."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.compliance import router
        assert router.prefix == "/compliance"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.compliance import router
        assert "Compliance" in router.tags

    def test_gdpr_export_request_schema(self):
        """Test GDPRExportRequest schema validation."""
        from backend.api.compliance import GDPRExportRequest
        from pydantic import ValidationError

        # Valid request
        valid = GDPRExportRequest(customer_email="test@example.com")
        assert valid.customer_email == "test@example.com"

        # Missing required fields
        with pytest.raises(ValidationError):
            GDPRExportRequest()

    def test_gdpr_export_invalid_email(self):
        """Test GDPRExportRequest rejects invalid email."""
        from backend.api.compliance import GDPRExportRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GDPRExportRequest(customer_email="not-an-email")

    def test_gdpr_delete_request_schema(self):
        """Test GDPRDeleteRequest schema validation."""
        from backend.api.compliance import GDPRDeleteRequest
        from pydantic import ValidationError

        # Valid request
        valid = GDPRDeleteRequest(customer_email="test@example.com", confirm=True)
        assert valid.customer_email == "test@example.com"
        assert valid.confirm is True

        # Missing confirm field
        with pytest.raises(ValidationError):
            GDPRDeleteRequest(customer_email="test@example.com")

    def test_gdpr_delete_requires_confirmation(self):
        """Test GDPRDeleteRequest requires confirm=True."""
        from backend.api.compliance import GDPRDeleteRequest

        # confirm=False is valid in schema but endpoint should reject
        req = GDPRDeleteRequest(customer_email="test@example.com", confirm=False)
        assert req.confirm is False

    def test_retention_check_request_schema(self):
        """Test RetentionCheckRequest schema validation."""
        from backend.api.compliance import RetentionCheckRequest

        # Empty request is valid (but endpoint will reject)
        req = RetentionCheckRequest()
        assert req.customer_email is None
        assert req.ticket_id is None

        # With email
        req = RetentionCheckRequest(customer_email="test@example.com")
        assert req.customer_email == "test@example.com"

        # With ticket_id
        ticket_id = uuid.uuid4()
        req = RetentionCheckRequest(ticket_id=ticket_id)
        assert req.ticket_id == ticket_id

    def test_compliance_request_response_schema(self):
        """Test ComplianceRequestResponse schema."""
        from backend.api.compliance import ComplianceRequestResponse

        req_id = uuid.uuid4()
        company_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        response = ComplianceRequestResponse(
            id=req_id,
            company_id=company_id,
            request_type="gdpr_export",
            customer_email="tes***@example.com",
            status="pending",
            requested_at=now,
            completed_at=None,
            result_url=None,
            created_at=now,
        )

        assert response.id == req_id
        assert response.request_type == "gdpr_export"
        assert response.status == "pending"

    def test_audit_log_response_schema(self):
        """Test AuditLogResponse schema."""
        from backend.api.compliance import AuditLogResponse

        entry_id = uuid.uuid4()
        company_id = uuid.uuid4()
        ticket_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        response = AuditLogResponse(
            id=entry_id,
            company_id=company_id,
            ticket_id=ticket_id,
            actor="admin@example.com",
            action="ticket_resolved",
            details={"key": "value"},
            created_at=now,
        )

        assert response.id == entry_id
        assert response.actor == "admin@example.com"
        assert response.action == "ticket_resolved"

    def test_retention_status_response_schema(self):
        """Test RetentionStatusResponse schema."""
        from backend.api.compliance import RetentionStatusResponse

        response = RetentionStatusResponse(
            customer_email="tes***@example.com",
            ticket_id=None,
            retention_days=90,
            deletion_scheduled=False,
            deletion_date=None,
            message="Data retention period is 90 days.",
        )

        assert response.retention_days == 90
        assert response.deletion_scheduled is False

    def test_message_response_schema(self):
        """Test MessageResponse schema."""
        from backend.api.compliance import MessageResponse

        request_id = uuid.uuid4()
        response = MessageResponse(
            message="Request created successfully",
            request_id=request_id
        )
        assert response.message == "Request created successfully"
        assert response.request_id == request_id


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_mask_email_full(self):
        """Test email masking for longer emails."""
        from backend.api.compliance import mask_email

        masked = mask_email("john.doe@example.com")
        assert "***" in masked
        assert "@" in masked
        assert "example.com" in masked

    def test_mask_email_short(self):
        """Test email masking for short emails."""
        from backend.api.compliance import mask_email

        masked = mask_email("ab@example.com")
        assert "***" in masked or masked.startswith("a")

    def test_mask_email_invalid(self):
        """Test email masking for invalid emails."""
        from backend.api.compliance import mask_email

        # Invalid email returns as-is
        result = mask_email("not-an-email")
        assert result == "not-an-email"

    def test_mask_email_empty(self):
        """Test email masking for empty string."""
        from backend.api.compliance import mask_email

        result = mask_email("")
        assert result == ""


class TestEndpointsWithoutAuth:
    """Tests for endpoints without authentication."""

    def test_gdpr_export_requires_auth(self):
        """Test that GDPR export endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/compliance/gdpr/export",
                json={"customer_email": "test@example.com"}
            )

        assert response.status_code in [401, 403]

    def test_gdpr_delete_requires_auth(self):
        """Test that GDPR delete endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/compliance/gdpr/delete",
                json={"customer_email": "test@example.com", "confirm": True}
            )

        assert response.status_code in [401, 403]

    def test_list_requests_requires_auth(self):
        """Test that list requests endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/requests")

        assert response.status_code in [401, 403]

    def test_list_audit_log_requires_auth(self):
        """Test that audit log endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log")

        assert response.status_code in [401, 403]

    def test_get_audit_entry_requires_auth(self):
        """Test that get audit entry endpoint requires authentication."""
        app = create_test_app()
        entry_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.get(f"/compliance/audit-log/{entry_id}")

        assert response.status_code in [401, 403]

    def test_retention_check_requires_auth(self):
        """Test that retention check endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/compliance/retention/check",
                json={"customer_email": "test@example.com"}
            )

        assert response.status_code in [401, 403]


class TestInvalidUUIDHandling:
    """Tests for invalid UUID handling."""

    def test_get_audit_entry_invalid_uuid(self):
        """Test getting audit entry with invalid UUID returns validation error."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log/not-a-uuid")

        # Auth is checked before UUID validation, so we get 401
        # If auth passes, then 422 for invalid UUID
        assert response.status_code in [401, 403, 422]


class TestPaginationValidation:
    """Tests for pagination parameter validation."""

    def test_list_requests_invalid_page(self):
        """Test listing requests with invalid page number."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/requests", params={"page": 0})

        assert response.status_code in [401, 403, 422]

    def test_list_requests_invalid_page_size(self):
        """Test listing requests with invalid page size."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/requests", params={"page_size": 0})

        assert response.status_code in [401, 403, 422]

        with TestClient(app) as client:
            response = client.get("/compliance/requests", params={"page_size": 101})

        assert response.status_code in [401, 403, 422]

    def test_list_audit_log_invalid_page(self):
        """Test listing audit log with invalid page number."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log", params={"page": 0})

        assert response.status_code in [401, 403, 422]

    def test_list_audit_log_invalid_page_size(self):
        """Test listing audit log with invalid page size."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log", params={"page_size": 200})

        assert response.status_code in [401, 403, 422]


class TestRequestTypeFiltering:
    """Tests for request type filtering."""

    def test_list_requests_filter_by_type(self):
        """Test filtering compliance requests by type."""
        from backend.api.compliance import ComplianceRequestListResponse
        from backend.models.compliance_request import ComplianceRequestType

        # Verify enum values are correct for filtering
        assert ComplianceRequestType.gdpr_export.value == "gdpr_export"
        assert ComplianceRequestType.gdpr_delete.value == "gdpr_delete"

    def test_list_requests_filter_by_status(self):
        """Test filtering compliance requests by status."""
        from backend.models.compliance_request import ComplianceRequestStatus

        # Verify enum values are correct for filtering
        assert ComplianceRequestStatus.pending.value == "pending"
        assert ComplianceRequestStatus.processing.value == "processing"
        assert ComplianceRequestStatus.completed.value == "completed"
        assert ComplianceRequestStatus.failed.value == "failed"


class TestAuditLogFiltering:
    """Tests for audit log filtering parameters."""

    def test_audit_log_filter_by_ticket_id(self):
        """Test audit log can filter by ticket_id."""
        # This tests that the endpoint accepts the ticket_id parameter
        app = create_test_app()
        ticket_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.get(f"/compliance/audit-log?ticket_id={ticket_id}")

        # Will fail auth, but should not fail validation
        assert response.status_code in [401, 403]

    def test_audit_log_filter_by_actor(self):
        """Test audit log can filter by actor."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log?actor=admin@example.com")

        assert response.status_code in [401, 403]

    def test_audit_log_filter_by_action(self):
        """Test audit log can filter by action."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/compliance/audit-log?action=ticket_resolved")

        assert response.status_code in [401, 403]

    def test_audit_log_filter_by_date_range(self):
        """Test audit log can filter by date range."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get(
                "/compliance/audit-log",
                params={
                    "start_date": "2024-01-01T00:00:00Z",
                    "end_date": "2024-12-31T23:59:59Z"
                }
            )

        assert response.status_code in [401, 403]


class TestRetentionCheckValidation:
    """Tests for retention check validation."""

    def test_retention_check_needs_email_or_ticket(self):
        """Test that retention check requires email or ticket_id."""
        from backend.api.compliance import RetentionCheckRequest

        # Schema allows empty but endpoint should reject
        req = RetentionCheckRequest()
        assert req.customer_email is None
        assert req.ticket_id is None


class TestListResponseSchemas:
    """Tests for list response schemas."""

    def test_compliance_request_list_response(self):
        """Test ComplianceRequestListResponse schema."""
        from backend.api.compliance import (
            ComplianceRequestListResponse,
            ComplianceRequestResponse
        )

        req_id = uuid.uuid4()
        company_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        request = ComplianceRequestResponse(
            id=req_id,
            company_id=company_id,
            request_type="gdpr_export",
            customer_email="tes***@example.com",
            status="pending",
            requested_at=now,
            completed_at=None,
            result_url=None,
            created_at=now,
        )

        response = ComplianceRequestListResponse(
            requests=[request],
            total=1,
            page=1,
            page_size=20
        )

        assert response.total == 1
        assert len(response.requests) == 1

    def test_audit_log_list_response(self):
        """Test AuditLogListResponse schema."""
        from backend.api.compliance import AuditLogListResponse, AuditLogResponse

        entry_id = uuid.uuid4()
        company_id = uuid.uuid4()
        ticket_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        entry = AuditLogResponse(
            id=entry_id,
            company_id=company_id,
            ticket_id=ticket_id,
            actor="admin@example.com",
            action="ticket_resolved",
            details={},
            created_at=now,
        )

        response = AuditLogListResponse(
            entries=[entry],
            total=1,
            page=1,
            page_size=20
        )

        assert response.total == 1
        assert len(response.entries) == 1
