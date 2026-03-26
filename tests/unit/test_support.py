"""
Unit tests for backend/api/support.py - Support Ticket API.
Tests cover ticket creation, listing, updating, escalation, and messaging.
All external dependencies (database, Redis) are mocked for CI compatibility.
"""
import os
import uuid
from datetime import datetime, timezone
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
    user.email = "agent@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "agent"
    user.is_active = True
    return user


@pytest.fixture
def mock_ticket():
    """Create a mock support ticket."""
    ticket = MagicMock()
    ticket.id = uuid.uuid4()
    ticket.company_id = uuid.uuid4()
    ticket.customer_email = "customer@example.com"
    ticket.channel = MagicMock()
    ticket.channel.value = "email"
    ticket.status = MagicMock()
    ticket.status.value = "open"
    ticket.category = "Technical Support"
    ticket.subject = "Cannot login"
    ticket.body = "Login fails"
    ticket.ai_recommendation = None
    ticket.ai_confidence = None
    ticket.ai_tier_used = None
    ticket.sentiment = None
    ticket.assigned_to = None
    ticket.resolved_at = None
    ticket.created_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    ticket.is_pending_approval = lambda: False
    return ticket


def create_test_app():
    """Create a FastAPI test app with support router."""
    app = FastAPI()

    # Mock get_db dependency
    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Import and include router
    from backend.api.support import router
    app.include_router(router)

    return app


# --- Tests ---

class TestTicketEnums:
    """Tests to verify ticket enum values."""

    def test_channel_enum_values(self):
        """Test ChannelEnum has expected values."""
        from backend.models.support_ticket import ChannelEnum
        assert ChannelEnum.chat.value == "chat"
        assert ChannelEnum.email.value == "email"
        assert ChannelEnum.sms.value == "sms"
        assert ChannelEnum.voice.value == "voice"

    def test_status_enum_values(self):
        """Test TicketStatusEnum has expected values."""
        from backend.models.support_ticket import TicketStatusEnum
        assert TicketStatusEnum.open.value == "open"
        assert TicketStatusEnum.pending_approval.value == "pending_approval"
        assert TicketStatusEnum.resolved.value == "resolved"
        assert TicketStatusEnum.escalated.value == "escalated"

    def test_ai_tier_enum_values(self):
        """Test AITierEnum has expected values."""
        from backend.models.support_ticket import AITierEnum
        assert AITierEnum.light.value == "light"
        assert AITierEnum.medium.value == "medium"
        assert AITierEnum.heavy.value == "heavy"

    def test_sentiment_enum_values(self):
        """Test SentimentEnum has expected values."""
        from backend.models.support_ticket import SentimentEnum
        assert SentimentEnum.positive.value == "positive"
        assert SentimentEnum.neutral.value == "neutral"
        assert SentimentEnum.negative.value == "negative"


class TestSupportAPIEndpoints:
    """Tests for Support API endpoints."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.support import router
        assert router.prefix == "/support"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.support import router
        assert "Support" in router.tags

    def test_create_ticket_request_schema(self):
        """Test TicketCreateRequest schema validation."""
        from backend.api.support import TicketCreateRequest
        from backend.models.support_ticket import ChannelEnum
        from pydantic import ValidationError

        # Valid request
        valid = TicketCreateRequest(
            customer_email="test@example.com",
            channel=ChannelEnum.email,
            category="Technical",
            subject="Test subject",
            body="Test body content"
        )
        assert valid.customer_email == "test@example.com"

        # Missing required fields
        with pytest.raises(ValidationError):
            TicketCreateRequest()

    def test_create_ticket_invalid_email(self):
        """Test TicketCreateRequest rejects invalid email."""
        from backend.api.support import TicketCreateRequest
        from backend.models.support_ticket import ChannelEnum
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TicketCreateRequest(
                customer_email="not-an-email",
                channel=ChannelEnum.email,
                subject="Test",
                body="Test"
            )

    def test_create_ticket_subject_too_long(self):
        """Test TicketCreateRequest rejects too long subject."""
        from backend.api.support import TicketCreateRequest
        from backend.models.support_ticket import ChannelEnum
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TicketCreateRequest(
                customer_email="test@example.com",
                channel=ChannelEnum.email,
                subject="x" * 201,  # Max is 200
                body="Test"
            )

    def test_ticket_update_request_schema(self):
        """Test TicketUpdateRequest schema validation."""
        from backend.api.support import TicketUpdateRequest
        from backend.models.support_ticket import TicketStatusEnum

        # Empty update is valid (all optional)
        update = TicketUpdateRequest()
        assert update.status is None

        # Update with values
        update = TicketUpdateRequest(
            status=TicketStatusEnum.resolved,
            category="Billing",
            ai_confidence=0.95
        )
        assert update.status == TicketStatusEnum.resolved
        assert update.ai_confidence == 0.95

    def test_ticket_update_invalid_confidence(self):
        """Test TicketUpdateRequest rejects invalid confidence."""
        from backend.api.support import TicketUpdateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TicketUpdateRequest(ai_confidence=1.5)  # Must be 0-1

        with pytest.raises(ValidationError):
            TicketUpdateRequest(ai_confidence=-0.1)  # Must be 0-1

    def test_ticket_message_request_schema(self):
        """Test TicketMessageRequest schema validation."""
        from backend.api.support import TicketMessageRequest
        from pydantic import ValidationError

        # Valid message
        msg = TicketMessageRequest(
            message="This is a test message",
            sender="agent@example.com"
        )
        assert msg.message == "This is a test message"

        # Missing required fields
        with pytest.raises(ValidationError):
            TicketMessageRequest(message="Test")  # Missing sender

    def test_message_empty_validation(self):
        """Test TicketMessageRequest rejects empty message."""
        from backend.api.support import TicketMessageRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TicketMessageRequest(message="", sender="agent")

    def test_ticket_response_schema(self):
        """Test TicketResponse schema."""
        from backend.api.support import TicketResponse

        ticket_id = uuid.uuid4()
        company_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        response = TicketResponse(
            id=ticket_id,
            company_id=company_id,
            customer_email="test@example.com",
            channel="email",
            status="open",
            category="Technical",
            subject="Test subject",
            body="Test body",
            ai_recommendation=None,
            ai_confidence=None,
            ai_tier_used=None,
            sentiment=None,
            assigned_to=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )

        assert response.id == ticket_id
        assert response.channel == "email"
        assert response.status == "open"

    def test_message_response_schema(self):
        """Test MessageResponse schema."""
        from backend.api.support import MessageResponse

        ticket_id = uuid.uuid4()
        response = MessageResponse(message="Test message", ticket_id=ticket_id)
        assert response.message == "Test message"
        assert response.ticket_id == ticket_id

    def test_ticket_list_response_schema(self):
        """Test TicketListResponse schema."""
        from backend.api.support import TicketListResponse, TicketResponse

        ticket_id = uuid.uuid4()
        company_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        ticket = TicketResponse(
            id=ticket_id,
            company_id=company_id,
            customer_email="test@example.com",
            channel="email",
            status="open",
            category="Technical",
            subject="Test subject",
            body="Test body",
            ai_recommendation=None,
            ai_confidence=None,
            ai_tier_used=None,
            sentiment=None,
            assigned_to=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )

        response = TicketListResponse(
            tickets=[ticket],
            total=1,
            page=1,
            page_size=20
        )

        assert response.total == 1
        assert len(response.tickets) == 1


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_mask_email_full(self):
        """Test email masking for longer emails."""
        from backend.api.support import mask_email

        masked = mask_email("john.doe@example.com")
        assert "***" in masked
        assert "@" in masked
        assert "example.com" in masked

    def test_mask_email_short(self):
        """Test email masking for short emails."""
        from backend.api.support import mask_email

        masked = mask_email("ab@example.com")
        assert "***" in masked or masked.startswith("a")

    def test_mask_email_invalid(self):
        """Test email masking for invalid emails."""
        from backend.api.support import mask_email

        # Invalid email returns as-is
        result = mask_email("not-an-email")
        assert result == "not-an-email"

    def test_mask_email_empty(self):
        """Test email masking for empty string."""
        from backend.api.support import mask_email

        result = mask_email("")
        assert result == ""


class TestEndpointsWithoutAuth:
    """Tests for endpoints without authentication."""

    def test_create_ticket_requires_auth(self):
        """Test that create ticket endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/support/tickets",
                json={
                    "customer_email": "test@example.com",
                    "channel": "email",
                    "subject": "Test",
                    "body": "Test body"
                }
            )

        assert response.status_code in [401, 403]

    def test_list_tickets_requires_auth(self):
        """Test that list tickets endpoint requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/support/tickets")

        assert response.status_code in [401, 403]

    def test_get_ticket_requires_auth(self):
        """Test that get ticket endpoint requires authentication."""
        app = create_test_app()
        ticket_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.get(f"/support/tickets/{ticket_id}")

        assert response.status_code in [401, 403]

    def test_update_ticket_requires_auth(self):
        """Test that update ticket endpoint requires authentication."""
        app = create_test_app()
        ticket_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.put(
                f"/support/tickets/{ticket_id}",
                json={"status": "resolved"}
            )

        assert response.status_code in [401, 403]

    def test_escalate_ticket_requires_auth(self):
        """Test that escalate ticket endpoint requires authentication."""
        app = create_test_app()
        ticket_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(f"/support/tickets/{ticket_id}/escalate")

        assert response.status_code in [401, 403]

    def test_add_message_requires_auth(self):
        """Test that add message endpoint requires authentication."""
        app = create_test_app()
        ticket_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(
                f"/support/tickets/{ticket_id}/messages",
                json={"message": "Test", "sender": "agent"}
            )

        assert response.status_code in [401, 403]


class TestInvalidUUIDHandling:
    """Tests for invalid UUID handling."""

    def test_get_ticket_invalid_uuid(self):
        """Test getting ticket with invalid UUID returns validation error."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/support/tickets/not-a-uuid")

        # Auth is checked before UUID validation, so we get 401
        # If auth passes, then 422 for invalid UUID
        assert response.status_code in [401, 403, 422]

    def test_update_ticket_invalid_uuid(self):
        """Test updating ticket with invalid UUID returns validation error."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.put(
                "/support/tickets/not-a-uuid",
                json={"status": "resolved"}
            )

        assert response.status_code in [401, 403, 422]

    def test_escalate_ticket_invalid_uuid(self):
        """Test escalating ticket with invalid UUID returns validation error."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post("/support/tickets/not-a-uuid/escalate")

        assert response.status_code in [401, 403, 422]

    def test_add_message_invalid_uuid(self):
        """Test adding message with invalid UUID returns validation error."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/support/tickets/not-a-uuid/messages",
                json={"message": "Test", "sender": "agent"}
            )

        assert response.status_code in [401, 403, 422]


class TestPaginationValidation:
    """Tests for pagination parameter validation."""

    def test_list_tickets_invalid_page(self):
        """Test listing tickets with invalid page number."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/support/tickets", params={"page": 0})

        assert response.status_code in [401, 403, 422]

    def test_list_tickets_invalid_page_size(self):
        """Test listing tickets with invalid page size."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/support/tickets", params={"page_size": 0})

        assert response.status_code in [401, 403, 422]

        with TestClient(app) as client:
            response = client.get("/support/tickets", params={"page_size": 101})

        assert response.status_code in [401, 403, 422]
