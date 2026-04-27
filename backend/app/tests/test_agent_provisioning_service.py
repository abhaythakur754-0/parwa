"""
PARWA Agent Provisioning Service Tests (F-099)

Comprehensive tests for the Paddle-triggered agent provisioning pipeline.
Follows test_custom_integration_service.py patterns.

Test classes:
- TestConstants: Validate constants and tier limits
- TestCreateCheckout: Valid creation, invalid inputs, limit enforcement
- TestProcessWebhook: Payment processing, idempotency, failures
- TestProvisionAgent: Full flow, edge cases, rollback on error
- TestGetProvisioningStatus: Found, not found
- TestCleanupStale: Expired cleanup, no expired records
- TestGetAgentLimit: Various tiers, at limit
- TestValidation: Specialty, channel, name validation
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.exceptions import (
    InternalError,
    NotFoundError,
    ValidationError,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy Session."""
    db = MagicMock()
    return db


@pytest.fixture
def company_id():
    return "company-uuid-001"


@pytest.fixture
def pending_agent_id():
    return "pending-agent-uuid-001"


@pytest.fixture
def service(mock_db):
    """Create AgentProvisioningService with mock DB."""
    from app.services.agent_provisioning_service import (
        AgentProvisioningService,
    )
    return AgentProvisioningService(mock_db)


# ══════════════════════════════════════════════════════════════════
# TEST CONSTANTS
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    """Validate module-level constants are correct."""

    def test_valid_specialties(self):
        from app.services.agent_provisioning_service import (
            VALID_SPECIALTIES,
        )
        assert isinstance(VALID_SPECIALTIES, set)
        assert "billing" in VALID_SPECIALTIES
        assert "returns" in VALID_SPECIALTIES
        assert "technical" in VALID_SPECIALTIES
        assert "general" in VALID_SPECIALTIES
        assert "sales" in VALID_SPECIALTIES
        assert "onboarding" in VALID_SPECIALTIES
        assert "vip" in VALID_SPECIALTIES
        assert "feedback" in VALID_SPECIALTIES
        assert "custom" in VALID_SPECIALTIES
        assert len(VALID_SPECIALTIES) == 9

    def test_valid_channels(self):
        from app.services.agent_provisioning_service import (
            VALID_CHANNELS,
        )
        assert isinstance(VALID_CHANNELS, set)
        assert "chat" in VALID_CHANNELS
        assert "email" in VALID_CHANNELS
        assert "sms" in VALID_CHANNELS
        assert "voice" in VALID_CHANNELS
        assert "slack" in VALID_CHANNELS
        assert "webchat" in VALID_CHANNELS
        assert len(VALID_CHANNELS) == 6

    def test_payment_timeout_hours(self):
        from app.services.agent_provisioning_service import (
            PAYMENT_TIMEOUT_HOURS,
        )
        assert PAYMENT_TIMEOUT_HOURS == 24

    def test_max_provisioning_retries(self):
        from app.services.agent_provisioning_service import (
            MAX_PROVISIONING_RETRIES,
        )
        assert MAX_PROVISIONING_RETRIES == 3

    def test_provisioning_statuses(self):
        from app.services.agent_provisioning_service import (
            PROVISIONING_STATUSES,
        )
        assert "awaiting_payment" in PROVISIONING_STATUSES
        assert "provisioning" in PROVISIONING_STATUSES
        assert "training" in PROVISIONING_STATUSES
        assert "active" in PROVISIONING_STATUSES
        assert "failed" in PROVISIONING_STATUSES

    def test_payment_statuses(self):
        from app.services.agent_provisioning_service import (
            PAYMENT_STATUSES,
        )
        assert "pending" in PAYMENT_STATUSES
        assert "paid" in PAYMENT_STATUSES
        assert "failed" in PAYMENT_STATUSES
        assert "refunded" in PAYMENT_STATUSES

    def test_tier_agent_limits(self):
        from app.services.agent_provisioning_service import (
            TIER_AGENT_LIMITS,
        )
        assert TIER_AGENT_LIMITS["mini_parwa"] == 1
        assert TIER_AGENT_LIMITS["parwa"] == 3
        assert TIER_AGENT_LIMITS["high_parwa"] == 10


# ══════════════════════════════════════════════════════════════════
# TEST CREATE CHECKOUT
# ══════════════════════════════════════════════════════════════════


class TestCreateCheckout:
    """Tests for create_checkout method."""

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._create_paddle_checkout",
        return_value="https://checkout.paddle.com/test",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=1,
    )
    def test_valid_checkout_creation(
        self, mock_count, mock_tier, mock_paddle,
        service, mock_db, company_id,
    ):
        """Valid checkout creation returns expected fields."""
        result = service.create_checkout(
            company_id=company_id,
            agent_name="Support Bot",
            specialty="billing",
            channels=["chat", "email"],
        )

        assert "pending_agent_id" in result
        assert result["payment_status"] == "pending"
        assert result["paddle_checkout_url"] == (
            "https://checkout.paddle.com/test"
        )
        assert "expires_at" in result
        # PendingAgent was added to session
        mock_db.add.assert_called_once()

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_invalid_specialty(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Invalid specialty raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="nonexistent",
                channels=["chat"],
            )
        assert "Invalid specialty" in str(exc_info.value)

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_invalid_channels(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Invalid channel raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["chat", "tiktok"],
            )
        assert "Invalid channels" in str(exc_info.value)
        assert "tiktok" in str(exc_info.value.details.get(
            "invalid_channels", [],
        ))

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=3,
    )
    def test_agent_limit_exceeded(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Agent limit exceeded raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["chat"],
            )
        assert "limit reached" in str(exc_info.value).lower()
        assert exc_info.value.details["current_agents"] == 3
        assert exc_info.value.details["max_agents"] == 3
        assert exc_info.value.details["upgrade_required"] is True

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_validates_name_length(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Agent name exceeding 200 chars raises ValidationError."""
        long_name = "A" * 201
        with pytest.raises(ValidationError) as exc_info:
            service.create_checkout(
                company_id=company_id,
                agent_name=long_name,
                specialty="billing",
                channels=["chat"],
            )
        assert "200 characters" in str(exc_info.value)

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_empty_name_raises(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Empty agent name raises ValidationError."""
        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="",
                specialty="billing",
                channels=["chat"],
            )

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_empty_channels_raises(
        self, mock_count, mock_tier,
        service, company_id,
    ):
        """Empty channels list raises ValidationError."""
        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=[],
            )

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._create_paddle_checkout",
        side_effect=Exception("Paddle API down"),
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_paddle_failure_raises_internal_error(
        self, mock_count, mock_tier, mock_paddle,
        service, mock_db, company_id,
    ):
        """Paddle API failure raises InternalError."""
        with pytest.raises(InternalError) as exc_info:
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["chat"],
            )
        assert "checkout" in str(exc_info.value).lower()

    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._create_paddle_checkout",
        return_value="https://checkout.paddle.com/test",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._get_company_tier",
        return_value="parwa",
    )
    @patch(
        "app.services.agent_provisioning_service"
        ".AgentProvisioningService._count_active_agents",
        return_value=0,
    )
    def test_sets_expires_at_24h(
        self, mock_count, mock_tier, mock_paddle,
        service, mock_db, company_id,
    ):
        """Checkout sets expires_at to 24 hours from now."""
        before = datetime.utcnow()
        result = service.create_checkout(
            company_id=company_id,
            agent_name="Bot",
            specialty="billing",
            channels=["chat"],
        )
        after = datetime.utcnow()

        expires_at = datetime.fromisoformat(result["expires_at"])
        expected_min = before + timedelta(hours=23)
        expected_max = after + timedelta(hours=25)
        assert expected_min <= expires_at <= expected_max


# ══════════════════════════════════════════════════════════════════
# TEST PROCESS WEBHOOK
# ══════════════════════════════════════════════════════════════════


class TestProcessWebhook:
    """Tests for process_webhook method."""

    def test_successful_payment(
        self, service, mock_db, company_id,
    ):
        """Successful payment webhook updates pending agent."""
        # Mock: no existing event
        mock_db.query.return_value.filter.return_value \
            .first.return_value = None

        # Mock: find pending agent
        pending = MagicMock()
        pending.payment_status = "pending"
        pending.paddle_event_id = None
        pending.paddle_transaction_id = None
        pending.id = "pa-001"

        # Chain: first filter call returns mock for event check,
        # second filter call returns mock for pending agent lookup
        filter_mock = MagicMock()

        def filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if args and hasattr(args[0], '_order_by'):
                # Second call (pending agent lookup)
                m.order_by.return_value.first.return_value = pending
                return m
            else:
                # First call (event check)
                m.first.return_value = None
                return m
            return MagicMock()

        # Simplified: just use two separate return values
        call_count = [0]

        original_filter = mock_db.query.return_value.filter

        def filter_fn(*args, **kwargs):
            call_count[0] += 1
            m = MagicMock()
            if call_count[0] == 1:
                # Event idempotency check
                m.first.return_value = None
            else:
                # Pending agent lookup
                m.order_by.return_value.first.return_value = pending
            return m

        mock_db.query.return_value.filter = filter_fn

        with patch.object(
            service, "_dispatch_provisioning_task",
        ):
            result = service.process_webhook(
                company_id=company_id,
                event_type="transaction.completed",
                event_data={
                    "transaction_id": "txn_123",
                    "subscription_id": "sub_456",
                },
                event_id="evt_001",
            )

        assert result["status"] == "processed"
        assert result["pending_agent_id"] == "pa-001"
        assert pending.payment_status == "paid"
        assert pending.paddle_event_id == "evt_001"
        assert pending.paddle_transaction_id == "txn_123"

    def test_idempotent_duplicate(
        self, service, mock_db, company_id,
    ):
        """Duplicate event_id returns already_processed."""
        existing = MagicMock()
        existing.id = "existing-pa-001"

        filter_mock = MagicMock()
        filter_mock.first.return_value = existing
        mock_db.query.return_value.filter.return_value = filter_mock

        result = service.process_webhook(
            company_id=company_id,
            event_type="transaction.completed",
            event_data={},
            event_id="evt_duplicate",
        )

        assert result["status"] == "already_processed"
        assert result["action"] == "duplicate"
        assert result["pending_agent_id"] == "existing-pa-001"

    def test_unsupported_event_type(
        self, service, mock_db, company_id,
    ):
        """Unsupported event type returns ignored."""
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        mock_db.query.return_value.filter.return_value = filter_mock

        result = service.process_webhook(
            company_id=company_id,
            event_type="customer.updated",
            event_data={},
            event_id="evt_002",
        )

        assert result["status"] == "ignored"
        assert result["action"] == "unsupported_event_type"

    def test_no_matching_pending_agent(
        self, service, mock_db, company_id,
    ):
        """No pending agent found returns no_matching_pending."""
        call_count = [0]

        def filter_fn(*args, **kwargs):
            call_count[0] += 1
            m = MagicMock()
            if call_count[0] == 1:
                m.first.return_value = None
            else:
                # No pending agent
                m.order_by.return_value.first.return_value = None
            return m

        mock_db.query.return_value.filter = filter_fn

        result = service.process_webhook(
            company_id=company_id,
            event_type="transaction.completed",
            event_data={},
            event_id="evt_003",
        )

        assert result["status"] == "no_matching_pending"


# ══════════════════════════════════════════════════════════════════
# TEST PROVISION AGENT
# ══════════════════════════════════════════════════════════════════


class TestProvisionAgent:
    """Tests for provision_agent method."""

    def test_full_provisioning_flow(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Full provisioning creates Agent and updates status."""
        pending = MagicMock()
        pending.id = pending_agent_id
        pending.payment_status = "paid"
        pending.provisioning_status = "awaiting_payment"
        pending.agent_name = "Support Bot"
        pending.specialty = "billing"
        pending.channels = '["chat", "email"]'
        pending.error_message = None

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        # Mock Agent model
        mock_agent = MagicMock()
        mock_agent.id = "new-agent-id"

        with patch(
            "app.services.agent_provisioning_service"
            ".AgentProvisioningService._create_default_metric_threshold",
        ), patch(
            "database.models.agent.Agent", return_value=mock_agent,
        ):
            result = service.provision_agent(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

        assert result["agent_id"] == "new-agent-id"
        assert result["status"] == "training"
        assert "provisioned" in result["message"].lower()
        assert pending.provisioning_status == "training"
        mock_db.add.assert_called()

    def test_already_provisioned(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Already provisioned agent returns early."""
        pending = MagicMock()
        pending.payment_status = "paid"
        pending.provisioning_status = "active"

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        result = service.provision_agent(
            pending_agent_id=pending_agent_id,
            company_id=company_id,
        )

        assert result["status"] == "active"
        assert "already" in result["message"].lower()

    def test_not_found_raises(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Non-existent pending agent raises NotFoundError."""
        mock_db.query.return_value.filter.return_value \
            .first.return_value = None

        with pytest.raises(NotFoundError):
            service.provision_agent(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

    def test_unpaid_raises_validation_error(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Unpaid pending agent raises ValidationError."""
        pending = MagicMock()
        pending.payment_status = "pending"
        pending.provisioning_status = "awaiting_payment"

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        with pytest.raises(ValidationError) as exc_info:
            service.provision_agent(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

        assert "payment must be completed" in str(exc_info.value).lower()

    def test_db_error_rollback(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """DB error during provisioning sets status to failed (BC-002)."""
        pending = MagicMock()
        pending.id = pending_agent_id
        pending.payment_status = "paid"
        pending.provisioning_status = "awaiting_payment"
        pending.agent_name = "Bot"
        pending.specialty = "billing"
        pending.channels = '["chat"]'
        pending.error_message = None

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending
        mock_db.add.side_effect = Exception("DB failure")

        with pytest.raises(InternalError):
            service.provision_agent(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

        assert pending.provisioning_status == "failed"
        assert "DB failure" in pending.error_message

    def test_invalid_json_channels_fallback(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Invalid JSON in channels falls back to ['chat']."""
        pending = MagicMock()
        pending.payment_status = "paid"
        pending.provisioning_status = "awaiting_payment"
        pending.channels = "not-json"

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        mock_agent = MagicMock()
        mock_agent.id = "agent-001"

        with patch(
            "app.services.agent_provisioning_service"
            ".AgentProvisioningService._create_default_metric_threshold",
        ), patch(
            "database.models.agent.Agent", return_value=mock_agent,
        ):
            result = service.provision_agent(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

        assert result["status"] == "training"


# ══════════════════════════════════════════════════════════════════
# TEST GET PROVISIONING STATUS
# ══════════════════════════════════════════════════════════════════


class TestGetProvisioningStatus:
    """Tests for get_provisioning_status method."""

    def test_found(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Returns status when pending agent found."""
        pending = MagicMock()
        pending.id = pending_agent_id
        pending.agent_name = "Bot"
        pending.specialty = "billing"
        pending.channels = '["chat"]'
        pending.payment_status = "paid"
        pending.provisioning_status = "training"
        pending.created_at = datetime.utcnow()
        pending.provisioned_at = datetime.utcnow()
        pending.error_message = None

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        result = service.get_provisioning_status(
            pending_agent_id=pending_agent_id,
            company_id=company_id,
        )

        assert result["id"] == pending_agent_id
        assert result["payment_status"] == "paid"
        assert result["provisioning_status"] == "training"
        assert result["error_message"] is None

    def test_not_found_raises(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Raises NotFoundError when pending agent not found."""
        mock_db.query.return_value.filter.return_value \
            .first.return_value = None

        with pytest.raises(NotFoundError):
            service.get_provisioning_status(
                pending_agent_id=pending_agent_id,
                company_id=company_id,
            )

    def test_with_error_message(
        self, service, mock_db, company_id, pending_agent_id,
    ):
        """Returns error_message when provisioning failed."""
        pending = MagicMock()
        pending.id = pending_agent_id
        pending.agent_name = "Bot"
        pending.specialty = "billing"
        pending.channels = "[]"
        pending.payment_status = "paid"
        pending.provisioning_status = "failed"
        pending.created_at = None
        pending.provisioned_at = None
        pending.error_message = "Provisioning failed: DB error"

        mock_db.query.return_value.filter.return_value \
            .first.return_value = pending

        result = service.get_provisioning_status(
            pending_agent_id=pending_agent_id,
            company_id=company_id,
        )

        assert result["error_message"] == "Provisioning failed: DB error"


# ══════════════════════════════════════════════════════════════════
# TEST CLEANUP STALE
# ══════════════════════════════════════════════════════════════════


class TestCleanupStale:
    """Tests for cleanup_stale_pending method."""

    def test_cleanup_expired(
        self, service, mock_db,
    ):
        """Expired pending agents get payment_status='expired'."""
        stale_1 = MagicMock()
        stale_2 = MagicMock()

        mock_db.query.return_value.filter.return_value \
            .all.return_value = [stale_1, stale_2]

        count = service.cleanup_stale_pending()

        assert count == 2
        assert stale_1.payment_status == "expired"
        assert stale_2.payment_status == "expired"
        mock_db.flush.assert_called_once()

    def test_no_expired_records(
        self, service, mock_db,
    ):
        """No expired records returns 0."""
        mock_db.query.return_value.filter.return_value \
            .all.return_value = []

        count = service.cleanup_stale_pending()

        assert count == 0
        mock_db.flush.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# TEST GET AGENT LIMIT
# ══════════════════════════════════════════════════════════════════


class TestGetAgentLimit:
    """Tests for get_agent_limit method."""

    def test_parwa_tier(
        self, service, company_id,
    ):
        """Parwa tier returns correct limits."""
        with patch.object(
            service, "_get_company_tier", return_value="parwa",
        ), patch.object(
            service, "_count_active_agents", return_value=2,
        ):
            result = service.get_agent_limit(company_id)

        assert result["tier"] == "parwa"
        assert result["current_agents"] == 2
        assert result["max_agents"] == 3
        assert result["can_add"] is True

    def test_at_limit(
        self, service, company_id,
    ):
        """At limit returns can_add=False."""
        with patch.object(
            service, "_get_company_tier", return_value="mini_parwa",
        ), patch.object(
            service, "_count_active_agents", return_value=1,
        ):
            result = service.get_agent_limit(company_id)

        assert result["current_agents"] == 1
        assert result["max_agents"] == 1
        assert result["can_add"] is False

    def test_unknown_tier_defaults(
        self, service, company_id,
    ):
        """Unknown tier defaults to mini_parwa limit."""
        with patch.object(
            service, "_get_company_tier", return_value="unknown_tier",
        ), patch.object(
            service, "_count_active_agents", return_value=0,
        ):
            result = service.get_agent_limit(company_id)

        assert result["max_agents"] == 1  # default fallback
        assert result["can_add"] is True

    def test_high_parwa_tier(
        self, service, company_id,
    ):
        """Parwa High tier returns 10 max agents."""
        with patch.object(
            service, "_get_company_tier", return_value="high_parwa",
        ), patch.object(
            service, "_count_active_agents", return_value=5,
        ):
            result = service.get_agent_limit(company_id)

        assert result["max_agents"] == 10
        assert result["can_add"] is True


# ══════════════════════════════════════════════════════════════════
# TEST VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════


class TestValidation:
    """Tests for private validation helpers."""

    def test_validate_specialty_valid(self, service):
        """Valid specialty does not raise."""
        service._validate_specialty("billing")  # no exception

    def test_validate_specialty_invalid(self, service):
        """Invalid specialty raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_specialty("invalid_specialty")

    def test_validate_specialty_none(self, service):
        """None specialty raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_specialty(None)

    def test_validate_specialty_empty(self, service):
        """Empty specialty raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_specialty("")

    def test_validate_channels_valid(self, service):
        """Valid channels do not raise."""
        service._validate_channels(["chat", "email", "sms"])

    def test_validate_channels_invalid(self, service):
        """Invalid channel raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service._validate_channels(["chat", "slack"])
        assert "slack" in str(exc_info.value)

    def test_validate_channels_empty_list(self, service):
        """Empty channels list raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_channels([])

    def test_validate_agent_name_valid(self, service):
        """Valid name does not raise."""
        service._validate_agent_name("Support Bot")

    def test_validate_agent_name_empty(self, service):
        """Empty name raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_agent_name("")

    def test_validate_agent_name_whitespace(self, service):
        """Whitespace-only name raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_agent_name("   ")

    def test_validate_agent_name_too_long(self, service):
        """Name over 200 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            service._validate_agent_name("A" * 201)

    def test_validate_agent_name_at_limit(self, service):
        """Name at exactly 200 chars does not raise."""
        service._validate_agent_name("A" * 200)  # no exception
