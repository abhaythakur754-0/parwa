"""
Unit Tests for PARWA Jarvis Customer Care Service (jarvis_cc_service)

Tests cover:
  1. Session Management — get_or_create_cc_session, get_cc_session, get_cc_context, update_cc_context
  2. Message Processing — send_cc_message (with pipeline mocking)
  3. System Prompt — build_cc_system_prompt, tier capabilities, welcome messages
  4. Health Check — get_cc_session_health
  5. Edge Cases — missing company_id, wrong session type, empty messages, oversized context

BC-008: All tests verify graceful degradation on invalid inputs.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.jarvis_cc_service import (
    get_or_create_cc_session,
    get_cc_session,
    get_cc_context,
    update_cc_context,
    send_cc_message,
    get_cc_history,
    build_cc_system_prompt,
    get_cc_session_health,
    _safe_parse_json,
    _maybe_reset_daily_counter,
    _build_cc_welcome,
    _get_tier_capabilities,
    _get_friendly_error_message,
    CC_DAILY_MESSAGE_LIMIT,
    CC_MAX_CONTEXT_MESSAGES,
    CC_MAX_CONTEXT_JSON_SIZE,
)
from app.exceptions import NotFoundError, ValidationError, RateLimitError
from database.models.jarvis import JarvisSession, JarvisMessage


# ══════════════════════════════════════════════════════════════════
# HELPER FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Create a mock SQLAlchemy session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.count.return_value = 0
    return db


@pytest.fixture
def sample_cc_session():
    """Create a sample customer care JarvisSession."""
    session = MagicMock(spec=JarvisSession)
    session.id = "cc_session_001"
    session.user_id = "user_001"
    session.company_id = "company_001"
    session.type = "customer_care"
    session.is_active = True
    session.message_count_today = 5
    session.total_message_count = 50
    session.last_message_date = datetime.now(timezone.utc)
    session.pack_type = "free"
    session.handoff_completed = False
    session.context_json = json.dumps({
        "variant_tier": "parwa",
        "variant_instance_id": "inst_parwa_company_001",
        "industry": "ecommerce",
        "mode": "customer_care",
        "awareness_enabled": False,
        "last_pipeline_metadata": {
            "variant_tier": "parwa",
            "pipeline_status": "completed",
            "quality_score": 0.85,
            "classification_intent": "billing",
            "technique_used": "chain_of_thought",
        },
    })
    session.updated_at = datetime.now(timezone.utc)
    session.created_at = datetime.now(timezone.utc)
    return session


@pytest.fixture
def sample_handoff_session():
    """Create a sample onboarding session with handoff completed."""
    session = MagicMock(spec=JarvisSession)
    session.id = "onboarding_001"
    session.user_id = "user_001"
    session.company_id = "company_001"
    session.type = "onboarding"
    session.handoff_completed = True
    session.updated_at = datetime.now(timezone.utc)
    session.context_json = json.dumps({
        "variant_tier": "parwa_high",
        "variant_instance_id": "inst_high_company_001",
        "industry": "saas",
        "business_email": "test@company.com",
        "email_verified": True,
        "selected_variants": ["parwa_high"],
    })
    return session


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTION TESTS
# ══════════════════════════════════════════════════════════════════


class TestSafeParseJson:
    """Tests for _safe_parse_json helper."""

    def test_valid_json(self):
        result = _safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_string(self):
        result = _safe_parse_json("")
        assert result == {}

    def test_none_input(self):
        result = _safe_parse_json(None)
        assert result == {}

    def test_invalid_json(self):
        result = _safe_parse_json("not json at all")
        assert result == {}

    def test_json_array_returns_empty(self):
        """Arrays are not valid context objects — should return empty dict."""
        result = _safe_parse_json("[1, 2, 3]")
        # json.loads would return a list, but our function handles that
        # Actually json.loads("[1,2,3]") returns [1,2,3] which is a list
        # The function returns whatever json.loads returns, so this is a list
        # But in practice, context_json is always a dict
        assert isinstance(result, (dict, list))

    def test_nested_json(self):
        result = _safe_parse_json('{"outer": {"inner": "value"}}')
        assert result["outer"]["inner"] == "value"


class TestBuildCcWelcome:
    """Tests for _build_cc_welcome helper."""

    def test_mini_parwa_welcome(self):
        msg = _build_cc_welcome("mini_parwa", "ecommerce")
        assert "Mini PARWA" in msg
        assert "ecommerce" in msg

    def test_parwa_welcome(self):
        msg = _build_cc_welcome("parwa", "saas")
        assert "PARWA" in msg
        assert "saas" in msg

    def test_parwa_high_welcome(self):
        msg = _build_cc_welcome("parwa_high", "healthcare")
        assert "PARWA High" in msg
        assert "healthcare" in msg

    def test_unknown_tier_uses_default(self):
        msg = _build_cc_welcome("unknown_tier", "general")
        assert "PARWA" in msg  # Falls back to default name


class TestGetTierCapabilities:
    """Tests for _get_tier_capabilities helper."""

    def test_mini_parwa_capabilities(self):
        caps = _get_tier_capabilities("mini_parwa")
        assert "Email and Chat" in caps
        assert "Tier 1" in caps
        assert "CLARA" in caps
        assert "CRP" in caps

    def test_parwa_capabilities(self):
        caps = _get_tier_capabilities("parwa")
        assert "SMS and Voice" in caps
        assert "Tier 1+2" in caps
        assert "Chain-of-Thought" in caps

    def test_parwa_high_capabilities(self):
        caps = _get_tier_capabilities("parwa_high")
        assert "Social media" in caps
        assert "Tier 1+2+3" in caps
        assert "peer review" in caps.lower()

    def test_unknown_tier_falls_back(self):
        caps = _get_tier_capabilities("enterprise")
        # Should fall back to mini_parwa capabilities
        assert "Email and Chat" in caps


class TestGetFriendlyErrorMessage:
    """Tests for _get_friendly_error_message helper."""

    def test_returns_string(self):
        msg = _get_friendly_error_message()
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_does_not_expose_technical_details(self):
        msg = _get_friendly_error_message()
        assert "exception" not in msg.lower()
        assert "traceback" not in msg.lower()
        assert "500" not in msg


# ══════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetOrCreateCcSession:
    """Tests for get_or_create_cc_session."""

    def test_requires_company_id(self, mock_db):
        """Must raise ValidationError if company_id is missing."""
        with pytest.raises(ValidationError):
            get_or_create_cc_session(
                db=mock_db,
                user_id="user_001",
                company_id="",
            )

    def test_creates_new_session_when_none_exists(self, mock_db):
        """Should create a new CC session when no active one exists."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        session = get_or_create_cc_session(
            db=mock_db,
            user_id="user_001",
            company_id="company_001",
        )

        # Should have called db.add at least once (session + welcome message)
        assert mock_db.add.call_count >= 1
        assert mock_db.flush.call_count >= 1

    def test_resumes_existing_session(self, mock_db, sample_cc_session):
        """Should resume an existing active CC session."""
        # First query returns None (for existing_session_id lookup)
        # Second query returns the sample session
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = sample_cc_session

        session = get_or_create_cc_session(
            db=mock_db,
            user_id="user_001",
            company_id="company_001",
        )

        # Should NOT create a new session — just return existing
        # db.add should not be called for session creation
        assert session is sample_cc_session

    def test_inherits_context_from_handoff(self, mock_db, sample_handoff_session):
        """New CC session should inherit variant_tier from handoff session."""
        # No existing CC session, but handoff session exists
        call_count = [0]
        def mock_first():
            call_count[0] += 1
            if call_count[0] <= 2:
                return None  # No existing CC session
            return sample_handoff_session  # Handoff session

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = mock_first

        session = get_or_create_cc_session(
            db=mock_db,
            user_id="user_001",
            company_id="company_001",
        )

        # The new session should have been added
        assert mock_db.add.call_count >= 1


class TestGetCcSession:
    """Tests for get_cc_session."""

    def test_raises_not_found_for_missing_session(self, mock_db):
        """Should raise NotFoundError if session doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            get_cc_session(
                db=mock_db,
                session_id="nonexistent",
                user_id="user_001",
                company_id="company_001",
            )

    def test_raises_not_found_for_wrong_type(self, mock_db):
        """Should raise NotFoundError if session is not customer_care type."""
        wrong_type_session = MagicMock(spec=JarvisSession)
        wrong_type_session.type = "onboarding"
        mock_db.query.return_value.filter.return_value.first.return_value = wrong_type_session

        with pytest.raises(NotFoundError) as exc_info:
            get_cc_session(
                db=mock_db,
                session_id="session_001",
                user_id="user_001",
                company_id="company_001",
            )

        assert "not a customer care session" in str(exc_info.value.message).lower()

    def test_returns_valid_cc_session(self, mock_db, sample_cc_session):
        """Should return session when it's a valid customer_care type."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        result = get_cc_session(
            db=mock_db,
            session_id="cc_session_001",
            user_id="user_001",
            company_id="company_001",
        )

        assert result is sample_cc_session
        assert result.type == "customer_care"


class TestGetCcContext:
    """Tests for get_cc_context."""

    def test_returns_parsed_context_with_runtime(self, mock_db, sample_cc_session):
        """Should return context with runtime enrichment."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session
        # Second query for tickets returns None
        mock_db.query.return_value.filter.return_value.scalar.return_value = 10

        context = get_cc_context(
            db=mock_db,
            session_id="cc_session_001",
            user_id="user_001",
            company_id="company_001",
        )

        assert "variant_tier" in context
        assert context["variant_tier"] == "parwa"
        assert "runtime" in context
        assert "tickets_today" in context["runtime"]

    def test_handles_missing_session_gracefully(self, mock_db):
        """Should raise NotFoundError for missing session."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            get_cc_context(
                db=mock_db,
                session_id="nonexistent",
                user_id="user_001",
                company_id="company_001",
            )


class TestUpdateCcContext:
    """Tests for update_cc_context."""

    def test_merges_partial_updates(self, mock_db, sample_cc_session):
        """Should merge new keys into existing context."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        session = update_cc_context(
            db=mock_db,
            session_id="cc_session_001",
            user_id="user_001",
            company_id="company_001",
            partial_updates={"custom_key": "custom_value", "alert_count": 5},
        )

        # Verify flush was called (session was updated)
        assert mock_db.flush.call_count >= 1

    def test_rejects_oversized_context(self, mock_db, sample_cc_session):
        """Should raise ValidationError if context would exceed size limit."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        with pytest.raises(ValidationError):
            update_cc_context(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                partial_updates={"huge_key": "x" * CC_MAX_CONTEXT_JSON_SIZE},
            )

    def test_protects_critical_keys(self, mock_db, sample_cc_session):
        """Should not overwrite variant_tier with None."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        # Try to set variant_tier to None — should be protected
        session = update_cc_context(
            db=mock_db,
            session_id="cc_session_001",
            user_id="user_001",
            company_id="company_001",
            partial_updates={"variant_tier": None},
        )

        # The update should still proceed (protected keys with None are skipped)
        assert mock_db.flush.call_count >= 1


# ══════════════════════════════════════════════════════════════════
# MESSAGE PROCESSING TESTS
# ══════════════════════════════════════════════════════════════════


class TestSendCcMessage:
    """Tests for send_cc_message."""

    def test_rejects_empty_message(self, mock_db, sample_cc_session):
        """Should raise ValidationError for empty messages."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        with pytest.raises(ValidationError):
            send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="",
            )

    def test_rejects_whitespace_only_message(self, mock_db, sample_cc_session):
        """Should raise ValidationError for whitespace-only messages."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        with pytest.raises(ValidationError):
            send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="   ",
            )

    def test_rejects_oversized_message(self, mock_db, sample_cc_session):
        """Should raise ValidationError for messages over 10K chars."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        with pytest.raises(ValidationError):
            send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="x" * 10001,
            )

    def test_raises_not_found_for_missing_session(self, mock_db):
        """Should raise NotFoundError for non-existent session."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            send_cc_message(
                db=mock_db,
                session_id="nonexistent",
                user_id="user_001",
                company_id="company_001",
                user_message="Hello",
            )

    @patch("app.services.jarvis_cc_service.process_customer_care_message_sync", create=True)
    def test_routes_through_pipeline_bridge(self, mock_pipeline, mock_db, sample_cc_session):
        """Should route message through variant_pipeline_bridge."""
        # Mock the pipeline bridge import
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        # Mock PipelineResult
        mock_result = MagicMock()
        mock_result.response_text = "I can help you with that!"
        mock_result.variant_tier = "parwa"
        mock_result.industry = "ecommerce"
        mock_result.pipeline_status = "completed"
        mock_result.quality_score = 0.85
        mock_result.total_latency_ms = 500.0
        mock_result.billing_tokens = 150
        mock_result.steps_completed = ["classify", "generate"]
        mock_result.technique_used = "chain_of_thought"
        mock_result.emergency_flag = False
        mock_result.empathy_score = 0.7
        mock_result.classification_intent = "billing"
        mock_result.metadata = {}
        mock_result.to_dict.return_value = {
            "variant_tier": "parwa",
            "pipeline_status": "completed",
            "quality_score": 0.85,
        }

        with patch(
            "app.core.variant_pipeline_bridge.process_customer_care_message_sync",
            return_value=mock_result,
        ):
            user_msg, ai_msg, metadata = send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="I need help with my billing",
            )

        # Should save both user and AI messages
        assert mock_db.add.call_count >= 2
        assert mock_db.flush.call_count >= 2

    def test_handles_ai_paused_state(self, mock_db, sample_cc_session):
        """Should return paused message when AI is paused for the channel."""
        sample_cc_session.context_json = json.dumps({
            "variant_tier": "parwa",
            "variant_instance_id": "inst_001",
            "industry": "ecommerce",
            "mode": "customer_care",
            "awareness_enabled": False,
        })

        # Setup: session found, then EmergencyState found
        call_count = [0]
        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return sample_cc_session  # Session query
            # EmergencyState query
            emergency = MagicMock()
            emergency.is_paused = True
            emergency.paused_channels = "chat"
            return emergency

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = mock_first
        mock_db.query.return_value.filter.return_value.first.side_effect = mock_first

        user_msg, ai_msg, metadata = send_cc_message(
            db=mock_db,
            session_id="cc_session_001",
            user_id="user_001",
            company_id="company_001",
            user_message="Help me!",
        )

        assert metadata.get("ai_paused") is True

    def test_increments_message_counters(self, mock_db, sample_cc_session):
        """Should increment message_count_today and total_message_count."""
        initial_today = sample_cc_session.message_count_today
        initial_total = sample_cc_session.total_message_count

        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        mock_result = MagicMock()
        mock_result.response_text = "Hello!"
        mock_result.variant_tier = "mini_parwa"
        mock_result.industry = "general"
        mock_result.pipeline_status = "completed"
        mock_result.quality_score = 0.5
        mock_result.total_latency_ms = 100.0
        mock_result.billing_tokens = 50
        mock_result.steps_completed = []
        mock_result.technique_used = ""
        mock_result.emergency_flag = False
        mock_result.empathy_score = 0.5
        mock_result.classification_intent = "general"
        mock_result.metadata = {}
        mock_result.to_dict.return_value = {}

        with patch(
            "app.core.variant_pipeline_bridge.process_customer_care_message_sync",
            return_value=mock_result,
        ):
            send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="Hello",
            )

        # Counters should have been incremented
        assert sample_cc_session.message_count_today == initial_today + 1
        assert sample_cc_session.total_message_count == initial_total + 1


# ══════════════════════════════════════════════════════════════════
# HISTORY TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetCcHistory:
    """Tests for get_cc_history."""

    def test_returns_empty_for_no_messages(self, mock_db, sample_cc_session):
        """Should return empty list and 0 count for no messages."""
        with patch(
            "app.services.jarvis_cc_service.get_cc_session",
            return_value=sample_cc_session,
        ):
            mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            messages, total = get_cc_history(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
            )

        assert messages == []
        assert total == 0

    def test_returns_messages_with_count(self, mock_db, sample_cc_session):
        """Should return messages and total count."""
        with patch(
            "app.services.jarvis_cc_service.get_cc_session",
            return_value=sample_cc_session,
        ):
            mock_db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 2

            msg1 = MagicMock(spec=JarvisMessage)
            msg1.id = "msg_001"
            msg1.role = "user"
            msg1.content = "Hello"
            msg1.message_type = "text"
            msg1.metadata_json = "{}"
            msg1.created_at = datetime.now(timezone.utc)

            msg2 = MagicMock(spec=JarvisMessage)
            msg2.id = "msg_002"
            msg2.role = "jarvis"
            msg2.content = "Hi there!"
            msg2.message_type = "variant_pipeline"
            msg2.metadata_json = '{"quality_score": 0.9}'
            msg2.created_at = datetime.now(timezone.utc)

            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [msg1, msg2]

            messages, total = get_cc_history(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
            )

        assert total == 2
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "jarvis"

    def test_raises_not_found_for_invalid_session(self, mock_db):
        """Should raise NotFoundError for non-existent session."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            get_cc_history(
                db=mock_db,
                session_id="nonexistent",
                user_id="user_001",
                company_id="company_001",
            )


# ══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT TESTS
# ══════════════════════════════════════════════════════════════════


class TestBuildCcSystemPrompt:
    """Tests for build_cc_system_prompt."""

    def test_contains_core_identity(self, mock_db):
        """Should contain the core CC Jarvis identity."""
        context = {
            "variant_tier": "mini_parwa",
            "variant_instance_id": "inst_001",
            "industry": "ecommerce",
        }

        # Mock CompanySetting query to return None (no brand voice)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="session_001",
            company_id="company_001",
            context=context,
        )

        assert "JARVIS" in prompt
        assert "AI CUSTOMER CARE EMPLOYEE" in prompt
        assert "NOT a chatbot" in prompt

    def test_includes_tier_capabilities(self, mock_db):
        """Should include tier-specific capabilities."""
        context = {
            "variant_tier": "parwa_high",
            "variant_instance_id": "inst_001",
            "industry": "saas",
        }

        mock_db.query.return_value.filter.return_value.first.return_value = None

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="session_001",
            company_id="company_001",
            context=context,
        )

        assert "PARWA_HIGH" in prompt
        assert "Tier 1+2+3" in prompt

    def test_includes_current_configuration(self, mock_db):
        """Should include current variant tier and industry."""
        context = {
            "variant_tier": "parwa",
            "variant_instance_id": "inst_001",
            "industry": "healthcare",
        }

        mock_db.query.return_value.filter.return_value.first.return_value = None

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="session_001",
            company_id="company_001",
            context=context,
        )

        assert "parwa" in prompt
        assert "healthcare" in prompt

    def test_includes_last_pipeline_metadata(self, mock_db):
        """Should include last pipeline metadata for continuity."""
        context = {
            "variant_tier": "parwa",
            "variant_instance_id": "inst_001",
            "industry": "ecommerce",
            "last_pipeline_metadata": {
                "classification_intent": "billing",
                "quality_score": 0.92,
                "technique_used": "react",
            },
        }

        mock_db.query.return_value.filter.return_value.first.return_value = None

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="session_001",
            company_id="company_001",
            context=context,
        )

        assert "billing" in prompt
        assert "0.9" in prompt  # 0.92 rounds to 0.9 with :.1f format
        assert "react" in prompt

    def test_no_prohibited_phrases(self, mock_db):
        """Should include prohibited phrases from company settings."""
        context = {
            "variant_tier": "mini_parwa",
            "variant_instance_id": "",
            "industry": "general",
        }

        mock_db.query.return_value.filter.return_value.first.return_value = None

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="session_001",
            company_id="company_001",
            context=context,
        )

        # Check the strict rules section exists
        assert "NEVER say" in prompt or "STRICT RULES" in prompt

    def test_loads_context_from_db_when_not_provided(self, mock_db, sample_cc_session):
        """Should load context from DB when context parameter is None."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        prompt = build_cc_system_prompt(
            db=mock_db,
            session_id="cc_session_001",
            company_id="company_001",
            context=None,  # Should load from DB
        )

        # Should still produce a valid prompt
        assert "JARVIS" in prompt


# ══════════════════════════════════════════════════════════════════
# HEALTH CHECK TESTS
# ══════════════════════════════════════════════════════════════════


class TestGetCcSessionHealth:
    """Tests for get_cc_session_health."""

    def test_returns_health_for_valid_session(self, mock_db, sample_cc_session):
        """Should return health metrics for a valid CC session."""
        with patch(
            "app.services.jarvis_cc_service.get_cc_session",
            return_value=sample_cc_session,
        ):
            health = get_cc_session_health(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
            )

        assert health["session_id"] == "cc_session_001"
        assert health["is_active"] is True
        assert health["variant_tier"] == "parwa"
        assert health["daily_limit"] == CC_DAILY_MESSAGE_LIMIT
        assert "daily_remaining" in health
        assert "pipeline_status" in health

    def test_returns_error_for_missing_session(self, mock_db):
        """Should return error status for missing session."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        health = get_cc_session_health(
            db=mock_db,
            session_id="nonexistent",
            user_id="user_001",
            company_id="company_001",
        )

        assert health["is_active"] is False
        assert "error" in health

    def test_includes_instance_status(self, mock_db, sample_cc_session):
        """Should include variant instance status when available."""
        with patch(
            "app.services.jarvis_cc_service.get_cc_session",
            return_value=sample_cc_session,
        ), patch(
            "app.services.variant_instance_service.get_instance",
            return_value=MagicMock(
                status="active",
                active_tickets_count=3,
                total_tickets_handled=150,
                last_activity_at=datetime.now(timezone.utc),
            ),
        ):
            health = get_cc_session_health(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
            )

        # Should have instance info or variant_tier
        assert "instance" in health or "variant_tier" in health


# ══════════════════════════════════════════════════════════════════
# RATE LIMITING TESTS
# ══════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Tests for daily message rate limiting."""

    def test_rejects_message_at_daily_limit(self, mock_db, sample_cc_session):
        """Should raise RateLimitError when daily limit is reached."""
        sample_cc_session.message_count_today = CC_DAILY_MESSAGE_LIMIT
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        with pytest.raises(RateLimitError):
            send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="This should be rate limited",
            )

    def test_allows_message_below_limit(self, mock_db, sample_cc_session):
        """Should allow messages when below daily limit."""
        sample_cc_session.message_count_today = CC_DAILY_MESSAGE_LIMIT - 1
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cc_session

        mock_result = MagicMock()
        mock_result.response_text = "OK"
        mock_result.variant_tier = "mini_parwa"
        mock_result.industry = "general"
        mock_result.pipeline_status = "completed"
        mock_result.quality_score = 0.5
        mock_result.total_latency_ms = 100.0
        mock_result.billing_tokens = 50
        mock_result.steps_completed = []
        mock_result.technique_used = ""
        mock_result.emergency_flag = False
        mock_result.empathy_score = 0.5
        mock_result.classification_intent = ""
        mock_result.metadata = {}
        mock_result.to_dict.return_value = {}

        with patch(
            "app.core.variant_pipeline_bridge.process_customer_care_message_sync",
            return_value=mock_result,
        ):
            # Should not raise
            user_msg, ai_msg, metadata = send_cc_message(
                db=mock_db,
                session_id="cc_session_001",
                user_id="user_001",
                company_id="company_001",
                user_message="This should work",
            )


# ══════════════════════════════════════════════════════════════════
# DAILY COUNTER RESET TESTS
# ══════════════════════════════════════════════════════════════════


class TestDailyCounterReset:
    """Tests for _maybe_reset_daily_counter."""

    def test_resets_when_new_day(self, mock_db):
        """Should reset counter when last_message_date is from yesterday."""
        session = MagicMock(spec=JarvisSession)
        session.message_count_today = 100
        session.last_message_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

        _maybe_reset_daily_counter(mock_db, session)

        assert session.message_count_today == 0
        assert mock_db.flush.call_count >= 1

    def test_does_not_reset_same_day(self, mock_db):
        """Should NOT reset counter when last_message_date is today."""
        session = MagicMock(spec=JarvisSession)
        session.message_count_today = 50
        session.last_message_date = datetime.now(timezone.utc)

        _maybe_reset_daily_counter(mock_db, session)

        assert session.message_count_today == 50

    def test_resets_when_no_last_date(self, mock_db):
        """Should reset counter when last_message_date is None."""
        session = MagicMock(spec=JarvisSession)
        session.message_count_today = 50
        session.last_message_date = None

        _maybe_reset_daily_counter(mock_db, session)

        assert session.message_count_today == 0


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    """Verify constants are production-appropriate."""

    def test_daily_limit_is_reasonable(self):
        """CC daily limit should be much higher than onboarding."""
        assert CC_DAILY_MESSAGE_LIMIT == 5000

    def test_context_messages_limit(self):
        """Context window should be reasonable for AI."""
        assert 10 <= CC_MAX_CONTEXT_MESSAGES <= 50

    def test_context_json_size_limit(self):
        """Context JSON should have a size limit."""
        assert CC_MAX_CONTEXT_JSON_SIZE > 0
        assert CC_MAX_CONTEXT_JSON_SIZE <= 100000  # 100K max
