"""
Day 26 Unit Tests - Ticket API

Tests for F-046: Ticket CRUD API endpoints.
Uses FastAPI dependency_overrides for proper mocking.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.tickets import router
from app.api.deps import get_current_user, get_db


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_current_user():
    """Mock current user as dict (as expected by tickets API)."""
    return {
        "user_id": "user-123",
        "company_id": "company-123",
        "plan_tier": "starter",
    }


@pytest.fixture
def app(mock_db, mock_current_user):
    """FastAPI app with dependency overrides."""
    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    def override_get_db():
        yield mock_db

    def override_get_current_user():
        return mock_current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.fixture
def client(app):
    """Test client."""
    return TestClient(app)


@pytest.fixture
def sample_ticket_data():
    """Sample ticket response data."""
    return {
        "id": "ticket-123",
        "company_id": "company-123",
        "customer_id": "customer-456",
        "channel": "email",
        "status": "open",
        "subject": "Test ticket",
        "priority": "medium",
        "category": None,
        "tags": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def create_mock_ticket():
    """Create a mock ticket object with all required attributes."""
    now = datetime.now(timezone.utc)
    mock_ticket = MagicMock()
    mock_ticket.id = "ticket-123"
    mock_ticket.company_id = "company-123"
    mock_ticket.customer_id = "customer-456"
    mock_ticket.channel = "email"
    mock_ticket.status = "open"
    mock_ticket.subject = "Test"
    mock_ticket.priority = "medium"
    mock_ticket.category = None
    mock_ticket.tags = "[]"
    mock_ticket.metadata_json = "{}"
    mock_ticket.created_at = now
    mock_ticket.updated_at = now
    mock_ticket.agent_id = None
    mock_ticket.assigned_to = None
    mock_ticket.classification_intent = None
    mock_ticket.classification_type = None
    mock_ticket.reopen_count = 0
    mock_ticket.frozen = False
    mock_ticket.parent_ticket_id = None
    mock_ticket.duplicate_of_id = None
    mock_ticket.is_spam = False
    mock_ticket.awaiting_human = False
    mock_ticket.awaiting_client = False
    mock_ticket.escalation_level = 1
    mock_ticket.sla_breached = False
    mock_ticket.first_response_at = None
    mock_ticket.resolution_target_at = None
    mock_ticket.client_timezone = None
    mock_ticket.plan_snapshot = "{}"
    mock_ticket.variant_version = None
    mock_ticket.closed_at = None
    return mock_ticket


# ── CREATE TICKET API TESTS ─────────────────────────────────────────────────

class TestCreateTicketAPI:
    """Tests for POST /tickets endpoint."""

    def test_create_ticket_success(self, client, mock_db):
        """Test successful ticket creation via API."""
        mock_ticket = create_mock_ticket()

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.create_ticket.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.post(
                "/tickets",
                json={
                    "customer_id": "customer-456",
                    "channel": "email",
                    "subject": "Test ticket",
                    "priority": "medium",
                }
            )

            assert response.status_code == 201


# ── LIST TICKETS API TESTS ──────────────────────────────────────────────────

class TestListTicketsAPI:
    """Tests for GET /tickets endpoint."""

    def test_list_tickets_success(self, client, mock_db):
        """Test successful ticket listing via API."""
        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.list_tickets.return_value = ([], 0)
            MockService.return_value = mock_service

            response = client.get("/tickets")

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data

    def test_list_tickets_with_filters(self, client, mock_db):
        """Test ticket listing with filters."""
        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.list_tickets.return_value = ([], 0)
            MockService.return_value = mock_service

            response = client.get(
                "/tickets",
                params={
                    "status": ["open", "assigned"],
                    "priority": ["high"],
                    "page": 1,
                    "page_size": 10,
                }
            )

            assert response.status_code == 200


# ── GET TICKET API TESTS ────────────────────────────────────────────────────

class TestGetTicketAPI:
    """Tests for GET /tickets/{ticket_id} endpoint."""

    def test_get_ticket_success(self, client, mock_db):
        """Test successful ticket retrieval via API."""
        mock_ticket = create_mock_ticket()

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.get_ticket.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.get("/tickets/ticket-123")

            assert response.status_code == 200

    def test_get_ticket_not_found(self, client, mock_db):
        """Test get ticket returns 404 when not found."""
        with patch("app.api.tickets.TicketService") as MockService:
            from app.exceptions import NotFoundError
            mock_service = MagicMock()
            mock_service.get_ticket.side_effect = NotFoundError("Not found")
            MockService.return_value = mock_service

            response = client.get("/tickets/nonexistent")

            assert response.status_code == 404


# ── UPDATE TICKET API TESTS ─────────────────────────────────────────────────

class TestUpdateTicketAPI:
    """Tests for PUT /tickets/{ticket_id} endpoint."""

    def test_update_ticket_success(self, client, mock_db):
        """Test successful ticket update via API."""
        mock_ticket = create_mock_ticket()
        mock_ticket.subject = "Updated"
        mock_ticket.priority = "high"

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.update_ticket.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.put(
                "/tickets/ticket-123",
                json={"priority": "high"}
            )

            assert response.status_code == 200


# ── DELETE TICKET API TESTS ─────────────────────────────────────────────────

class TestDeleteTicketAPI:
    """Tests for DELETE /tickets/{ticket_id} endpoint."""

    def test_delete_ticket_success(self, client, mock_db):
        """Test successful ticket deletion via API."""
        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.delete_ticket.return_value = True
            MockService.return_value = mock_service

            response = client.delete("/tickets/ticket-123")

            assert response.status_code == 200


# ── STATUS UPDATE API TESTS ─────────────────────────────────────────────────

class TestStatusUpdateAPI:
    """Tests for PATCH /tickets/{ticket_id}/status endpoint."""

    def test_update_status_success(self, client, mock_db):
        """Test successful status update via API."""
        mock_ticket = create_mock_ticket()
        mock_ticket.status = "assigned"

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.get_ticket.return_value = mock_ticket
            mock_service.update_ticket.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.patch(
                "/tickets/ticket-123/status",
                json={"status": "assigned", "reason": "Taking ownership"}
            )

            assert response.status_code == 200


# ── ASSIGNMENT API TESTS ────────────────────────────────────────────────────

class TestAssignAPI:
    """Tests for POST /tickets/{ticket_id}/assign endpoint."""

    def test_assign_ticket_success(self, client, mock_db):
        """Test successful ticket assignment via API."""
        # First call gets old ticket, second call gets new ticket after assign
        old_ticket = create_mock_ticket()
        old_ticket.assigned_to = None  # No previous assignee

        new_ticket = create_mock_ticket()
        new_ticket.assigned_to = "agent-789"

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            # First get_ticket for previous_assignee, second for response
            mock_service.get_ticket.return_value = old_ticket
            mock_service.assign_ticket.return_value = new_ticket
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/ticket-123/assign",
                json={
                    "assignee_id": "agent-789",
                    "assignee_type": "human",
                    "reason": "Expert in this area"
                }
            )

            assert response.status_code == 200


# ── TAGS API TESTS ──────────────────────────────────────────────────────────

class TestTagsAPI:
    """Tests for ticket tags endpoints."""

    def test_add_tags_success(self, client, mock_db):
        """Test successful tag addition via API."""
        mock_ticket = create_mock_ticket()
        mock_ticket.tags = json.dumps(["urgent", "api"])

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.add_tags.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/ticket-123/tags",
                json=["urgent", "api"]
            )

            assert response.status_code == 200

    def test_remove_tag_success(self, client, mock_db):
        """Test successful tag removal via API."""
        mock_ticket = create_mock_ticket()
        mock_ticket.tags = json.dumps(["api"])

        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.remove_tag.return_value = mock_ticket
            MockService.return_value = mock_service

            response = client.delete("/tickets/ticket-123/tags/urgent")

            assert response.status_code == 200


# ── BULK OPERATIONS API TESTS ───────────────────────────────────────────────

class TestBulkOperationsAPI:
    """Tests for bulk operation endpoints."""

    def test_bulk_status_update(self, client, mock_db):
        """Test bulk status update via API."""
        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.bulk_update_status.return_value = (2, [])
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/bulk/status",
                json={
                    "ticket_ids": ["ticket-1", "ticket-2"],
                    "status": "closed",
                    "reason": "Resolved"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success_count"] == 2
            assert data["failure_count"] == 0

    def test_bulk_assign(self, client, mock_db):
        """Test bulk assignment via API."""
        with patch("app.api.tickets.TicketService") as MockService:
            mock_service = MagicMock()
            mock_service.bulk_assign.return_value = (2, [])
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/bulk/assign",
                json={
                    "ticket_ids": ["ticket-1", "ticket-2"],
                    "assignee_id": "agent-789",
                    "assignee_type": "human"
                }
            )

            assert response.status_code == 200


# ── PRIORITY DETECTION API TESTS ────────────────────────────────────────────

class TestPriorityDetectionAPI:
    """Tests for priority detection endpoint."""

    def test_detect_priority(self, client, mock_db):
        """Test priority detection via API."""
        with patch("app.api.tickets.PriorityService") as MockService:
            mock_service = MagicMock()
            mock_service.detect_priority.return_value = ("critical", 0.85)
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/detect-priority",
                json={"text": "URGENT: production is down"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["priority"] == "critical"


# ── CATEGORY DETECTION API TESTS ────────────────────────────────────────────

class TestCategoryDetectionAPI:
    """Tests for category detection endpoint."""

    def test_detect_category(self, client, mock_db):
        """Test category detection via API."""
        with patch("app.api.tickets.CategoryService") as MockService:
            mock_service = MagicMock()
            mock_service.detect_category_advanced.return_value = (
                "tech_support",
                0.75,
                {"tech_support": 0.75, "billing": 0.1}
            )
            mock_service.get_department.return_value = "technical_support"
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/detect-category",
                json={
                    "subject": "API error",
                    "message": "Getting errors when calling the API"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "tech_support"


# ── PII SCAN API TESTS ──────────────────────────────────────────────────────

class TestPIIScanAPI:
    """Tests for PII scan endpoint."""

    def test_scan_pii(self, client, mock_db):
        """Test PII scan via API."""
        with patch("app.api.tickets.PIIScanService") as MockService:
            mock_service = MagicMock()
            mock_service.scan_and_redact.return_value = {
                "original_text": "Card: 4532015112830366",
                "redacted_text": "Card: [CREDIT_CARD_abc123]",
                "redaction_map": {},
                "redaction_count": 1,
                "pii_types": ["credit_card"]
            }
            MockService.return_value = mock_service

            response = client.post(
                "/tickets/scan-pii",
                json={"text": "Card: 4532015112830366"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["redaction_count"] == 1
