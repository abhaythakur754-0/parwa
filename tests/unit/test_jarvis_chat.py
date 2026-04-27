"""
PARWA Jarvis Chat Tests (Week 6 Day 8-9)

Tests for jarvis_service.py — helper functions, pricing storage,
payment updates, and session management.

Uses MagicMock for database sessions.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

from backend.app.services import jarvis_service
from backend.app.exceptions import ValidationError


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def sample_user_id():
    return "user-uuid-001"


@pytest.fixture
def sample_company_id():
    return "company-uuid-001"


@pytest.fixture
def sample_session_id():
    return "session-uuid-001"


@pytest.fixture
def mock_session(sample_user_id, sample_company_id, sample_session_id):
    session = MagicMock()
    session.id = sample_session_id
    session.user_id = sample_user_id
    session.company_id = sample_company_id
    session.status = "active"
    session.current_step = "greeting"
    session.message_count = 0
    session.selected_plan = None
    session.selected_industry = None
    session.pricing_selection = None
    session.payment_status = None
    session.paddle_session_id = None
    session.payment_amount = None
    session.last_message_at = None
    session.created_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    session.completed_at = None
    session.messages = []
    return session


# ── Session Tests ────────────────────────────────────────────────


class TestGetOrCreateSession:
    """Tests for get_or_create_session."""

    def test_create_new_session(self, sample_user_id, sample_company_id):
        """Test creating a new session when none exists."""
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        db.query.return_value.filter.return_value.first.return_value = None

        session = jarvis_service.get_or_create_session(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
        )

        assert db.add.called
        assert db.commit.called
        assert session.status == "active"

    def test_return_existing_active_session(self, mock_session):
        """Test returning existing active session."""
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        session = jarvis_service.get_or_create_session(
            db=db,
            user_id=mock_session.user_id,
            company_id=mock_session.company_id,
        )

        assert session.id == mock_session.id


# ── Helper Function Tests ───────────────────────────────────────


class TestHelperFunctions:
    """Tests for internal helper functions — these work reliably with mocks."""

    def test_get_greeting_message_with_name(self):
        msg = jarvis_service._get_greeting_message("John Doe", "Acme Corp")
        assert "John Doe" in msg
        assert "Acme Corp" in msg
        assert "PARWA" in msg
        assert "Jarvis" in msg

    def test_get_greeting_message_without_name(self):
        msg = jarvis_service._get_greeting_message(None, None)
        assert "Welcome" in msg
        assert "Jarvis" in msg

    def test_get_greeting_message_with_name_only(self):
        msg = jarvis_service._get_greeting_message("Jane", None)
        assert "Jane" in msg

    def test_get_pricing_review_message(self):
        pricing = {
            "plan": "parwa",
            "industry": "saas",
            "variants": [
                {"name": "Technical Support", "quantity": 2, "ticketsPerMonth": 800}
            ],
            "totalTickets": 1600,
            "totalMonthly": 258,
        }
        msg = jarvis_service._get_pricing_review_message(pricing)
        assert "parwa" in msg
        assert "Technical Support" in msg
        assert "1,600" in msg.replace(",", "")

    def test_get_pricing_review_empty_variants(self):
        pricing = {
            "plan": "mini-parwa",
            "industry": "ecommerce",
            "variants": [],
            "totalTickets": 0,
            "totalMonthly": 0,
        }
        msg = jarvis_service._get_pricing_review_message(pricing)
        assert "mini parwa" in msg

    def test_get_completion_message(self):
        msg = jarvis_service._get_completion_message("Jarvis")
        assert "Jarvis" in msg
        assert "ready" in msg.lower()
        assert "dashboard" in msg.lower()

    def test_get_completion_message_custom_name(self):
        msg = jarvis_service._get_completion_message("Buddy")
        assert "Buddy" in msg

    def test_get_otp_step_message(self):
        msg = jarvis_service._get_otp_step_message()
        assert "email" in msg.lower()
        assert "verif" in msg.lower()
        assert "6-digit" in msg or "code" in msg.lower()

    def test_get_payment_step_message(self):
        msg = jarvis_service._get_payment_step_message(999, "parwa")
        assert "999" in msg
        assert "Payment" in msg
        assert "Paddle" in msg

    def test_get_details_step_message_no_details(self):
        msg = jarvis_service._get_details_step_message(None)
        assert "Full Name" in msg
        assert "Company Name" in msg

    def test_get_details_step_message_with_partial_details(self):
        details = {"full_name": "John"}
        msg = jarvis_service._get_details_step_message(details)
        assert "missing" in msg.lower()

    def test_get_details_step_message_complete_details(self):
        details = {
            "full_name": "John",
            "company_name": "Acme",
            "work_email": "john@acme.com",
            "work_email_verified": True,
            "industry": "saas",
        }
        msg = jarvis_service._get_details_step_message(details)
        assert "pre-filled" in msg.lower() or "review" in msg.lower()

    def test_get_integration_step_message(self):
        msg = jarvis_service._get_integration_step_message()
        assert "Connect" in msg
        assert "skip" in msg.lower()
        assert "Email" in msg or "SMS" in msg

    def test_get_kb_step_message(self):
        msg = jarvis_service._get_kb_step_message()
        assert "Knowledge" in msg or "documentation" in msg.lower()
        assert "skip" in msg.lower()
        assert "PDF" in msg or "upload" in msg.lower()

    def test_get_ai_config_step_message(self):
        msg = jarvis_service._get_ai_config_step_message()
        assert "AI" in msg
        assert "Tone" in msg or "style" in msg.lower()


# ── Response Conversion Tests ─────────────────────────────────


class TestResponseConversion:
    """Tests for _session_to_response and _message_to_response."""

    def test_session_to_response(self, mock_session):
        response = jarvis_service._session_to_response(mock_session)
        assert response.id == mock_session.id
        assert response.status == "active"
        assert response.current_step == "greeting"
        assert response.message_count == 0

    def test_session_to_response_with_pricing(self, mock_session):
        mock_session.selected_plan = "parwa"
        mock_session.selected_industry = "saas"
        mock_session.payment_status = "completed"
        response = jarvis_service._session_to_response(mock_session)
        assert response.selected_plan == "parwa"
        assert response.selected_industry == "saas"
        assert response.payment_status == "completed"

    def test_session_to_response_completed(self, mock_session):
        mock_session.status = "completed"
        mock_session.completed_at = datetime.utcnow()
        response = jarvis_service._session_to_response(mock_session)
        assert response.status == "completed"
        assert response.completed_at is not None

    def test_message_to_response_user(self):
        msg = MagicMock()
        msg.id = "msg-1"
        msg.session_id = "ses-1"
        msg.role = "user"
        msg.content = "Hello Jarvis"
        msg.message_type = "text"
        msg.metadata_json = None
        msg.step = "greeting"
        msg.created_at = datetime.utcnow()

        response = jarvis_service._message_to_response(msg)
        assert response.id == "msg-1"
        assert response.role == "user"
        assert response.content == "Hello Jarvis"

    def test_message_to_response_assistant(self):
        msg = MagicMock()
        msg.id = "msg-2"
        msg.session_id = "ses-1"
        msg.role = "assistant"
        msg.content = "Welcome!"
        msg.message_type = "text"
        msg.metadata_json = None
        msg.step = "greeting"
        msg.created_at = datetime.utcnow()

        response = jarvis_service._message_to_response(msg)
        assert response.id == "msg-2"
        assert response.role == "assistant"
        assert response.message_type == "text"

    def test_message_to_response_with_metadata(self):
        msg = MagicMock()
        msg.id = "msg-3"
        msg.session_id = "ses-1"
        msg.role = "assistant"
        msg.content = "Summary"
        msg.message_type = "bill_summary"
        msg.metadata_json = '{"card_type": "pricing_review", "total": 999}'
        msg.step = "pricing"
        msg.created_at = datetime.utcnow()

        response = jarvis_service._message_to_response(msg)
        assert response.metadata_json is not None
        assert response.metadata_json["card_type"] == "pricing_review"

    def test_message_to_response_with_invalid_metadata(self):
        msg = MagicMock()
        msg.id = "msg-4"
        msg.session_id = "ses-1"
        msg.role = "assistant"
        msg.content = "Test"
        msg.message_type = "text"
        msg.metadata_json = "not-valid-json"
        msg.step = None
        msg.created_at = datetime.utcnow()

        response = jarvis_service._message_to_response(msg)
        assert response.metadata_json is None

    def test_message_to_response_no_metadata(self):
        msg = MagicMock()
        msg.id = "msg-5"
        msg.session_id = "ses-1"
        msg.role = "assistant"
        msg.content = "Test"
        msg.message_type = "text"
        msg.metadata_json = None
        msg.step = None
        msg.created_at = datetime.utcnow()

        response = jarvis_service._message_to_response(msg)
        assert response.metadata_json is None


# ── Advance Step Tests ──────────────────────────────────────────


class TestAdvanceStep:
    """Tests for advance_step."""

    def test_advance_to_valid_step(self, sample_user_id, sample_company_id, mock_session):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        result = jarvis_service.advance_step(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            step="integration",
        )

        assert mock_session.current_step == "integration"
        assert db.commit.called

    def test_advance_to_done_completes_session(self, sample_user_id, sample_company_id, mock_session):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        jarvis_service.advance_step(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            step="done",
        )

        assert mock_session.status == "completed"
        assert mock_session.completed_at is not None

    def test_advance_to_invalid_step_raises(self, sample_user_id, sample_company_id, mock_session):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        with pytest.raises(ValidationError) as exc_info:
            jarvis_service.advance_step(
                db=db,
                user_id=sample_user_id,
                company_id=sample_company_id,
                step="nonexistent_step",
            )

        assert "invalid step" in str(exc_info.value.message).lower()


# ── Store Pricing Tests ──────────────────────────────────────────


class TestStorePricing:
    """Tests for store_pricing_selection."""

    def test_store_pricing_updates_session_fields(self, sample_user_id, sample_company_id):
        db = MagicMock()
        new_session = MagicMock()
        new_session.id = "new-sid"
        new_session.message_count = 0
        new_session.current_step = "greeting"
        db.execute.return_value.scalar_one_or_none.side_effect = [None, None]
        db.add = MagicMock()
        db.refresh = MagicMock()

        pricing = {
            "plan": "parwa",
            "industry": "saas",
            "variants": [{"id": "saas-tech", "name": "Technical Support", "quantity": 2}],
            "totalTickets": 800,
            "totalMonthly": 258,
        }

        result = jarvis_service.store_pricing_selection(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            selected_plan="parwa",
            selected_industry="saas",
            pricing_selection=pricing,
            total_monthly=258,
        )

        assert db.commit.called

    def test_store_pricing_mini_parwa(self, sample_user_id, sample_company_id):
        db = MagicMock()
        new_session = MagicMock()
        new_session.id = "new-sid"
        db.execute.return_value.scalar_one_or_none.side_effect = [None, None]
        db.add = MagicMock()

        result = jarvis_service.store_pricing_selection(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            selected_plan="mini-parwa",
            selected_industry="ecommerce",
            pricing_selection={"plan": "mini-parwa"},
            total_monthly=499,
        )

        assert db.commit.called


# ── Payment Tests ───────────────────────────────────────────────


class TestUpdatePayment:
    """Tests for update_payment_status."""

    def test_payment_completed_advances_to_details(self, sample_user_id, sample_company_id, mock_session):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        result = jarvis_service.update_payment_status(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            payment_status="completed",
            paddle_session_id="paddle-ses-123",
            payment_amount=99900,
        )

        assert mock_session.payment_status == "completed"
        assert mock_session.current_step == "details"
        assert mock_session.paddle_session_id == "paddle-ses-123"

    def test_payment_pending_does_not_advance(self, sample_user_id, sample_company_id, mock_session):
        mock_session.current_step = "payment"
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        jarvis_service.update_payment_status(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            payment_status="pending",
        )

        assert mock_session.current_step == "payment"

    def test_payment_failed_does_not_advance(self, sample_user_id, sample_company_id, mock_session):
        mock_session.current_step = "payment"
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session

        jarvis_service.update_payment_status(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            payment_status="failed",
        )

        assert mock_session.current_step == "payment"


# ── Validation Tests ───────────────────────────────────────────


class TestValidation:
    """Tests for input validation."""

    def test_empty_message_raises_validation(self):
        db = MagicMock()
        with pytest.raises(ValidationError) as exc_info:
            jarvis_service.send_message(
                db=db,
                user_id="u1",
                company_id="c1",
                content="   ",
            )
        assert "empty" in str(exc_info.value.message).lower()

    def test_none_session_id_raises_validation(self, sample_user_id, sample_company_id):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValidationError) as exc_info:
            jarvis_service.send_message(
                db=db,
                user_id=sample_user_id,
                company_id=sample_company_id,
                content="test",
                session_id="nonexistent-id",
            )
        assert "not found" in str(exc_info.value.message).lower()


# ── Chat History Tests ──────────────────────────────────────────


class TestGetChatHistory:
    """Tests for get_chat_history."""

    def test_get_history_with_messages(self, sample_user_id, sample_company_id, mock_session):
        msg1 = MagicMock()
        msg1.id = "msg-1"
        msg1.session_id = mock_session.id
        msg1.role = "assistant"
        msg1.content = "Welcome!"
        msg1.message_type = "text"
        msg1.metadata_json = None
        msg1.step = "greeting"
        msg1.created_at = datetime.utcnow()

        msg2 = MagicMock()
        msg2.id = "msg-2"
        msg2.session_id = mock_session.id
        msg2.role = "user"
        msg2.content = "Start"
        msg2.message_type = "text"
        msg2.metadata_json = None
        msg2.step = "greeting"
        msg2.created_at = datetime.utcnow()

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session
        db.execute.return_value.scalars.return_value.all.return_value = [msg1, msg2]

        result = jarvis_service.get_chat_history(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            limit=50,
            offset=0,
        )

        assert len(result.messages) == 2
        assert result.session.id == mock_session.id

    def test_get_history_pagination_has_more(self, sample_user_id, sample_company_id, mock_session):
        messages = [MagicMock(id=f"msg-{i}") for i in range(51)]
        for i, m in enumerate(messages):
            m.session_id = mock_session.id
            m.role = "assistant"
            m.content = f"Message {i}"
            m.message_type = "text"
            m.metadata_json = None
            m.step = "greeting"
            m.created_at = datetime.utcnow()

        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session
        db.execute.return_value.scalars.return_value.all.return_value = messages

        result = jarvis_service.get_chat_history(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            limit=50,
            offset=0,
        )

        assert len(result.messages) == 50
        assert result.has_more is True

    def test_get_history_empty_session(self, sample_user_id, sample_company_id, mock_session):
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = mock_session
        db.execute.return_value.scalars.return_value.all.return_value = []

        result = jarvis_service.get_chat_history(
            db=db,
            user_id=sample_user_id,
            company_id=sample_company_id,
            limit=50,
            offset=0,
        )

        assert len(result.messages) == 0
        assert result.has_more is False
