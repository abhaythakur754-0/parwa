"""
PARWA Tests — F-099: Agent Provisioning Service

Tests the AgentProvisioningService covering:
- Constants validation
- _validate_specialty — specialty validation
- _validate_channels — channel validation
- _validate_agent_name — name validation
- _get_company_tier — tier lookup
- _check_agent_limit — limit enforcement
- get_agent_limit — tier info
- create_checkout — Paddle checkout creation
- process_webhook — webhook processing
- provision_agent — agent provisioning
- get_provisioning_status — status check
- cleanup_stale_pending — expired agent cleanup

Building Codes: BC-001, BC-002, BC-003, BC-004, BC-012
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import InternalError, NotFoundError, ValidationError
from app.services.agent_provisioning_service import (
    MAX_PROVISIONING_RETRIES,
    PAYMENT_TIMEOUT_HOURS,
    TIER_AGENT_LIMITS,
    VALID_CHANNELS,
    VALID_SPECIALTIES,
    AgentProvisioningService,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def company_id():
    return "comp-abc-123"


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    return AgentProvisioningService(mock_db)


def _make_pending_agent(
    pending_id="pending-1",
    company_id="comp-abc-123",
    agent_name="Support Bot",
    specialty="billing",
    channels='["chat", "email"]',
    payment_status="paid",
    provisioning_status="awaiting_payment",
    paddle_event_id=None,
    created_at=None,
    expires_at=None,
    provisioned_at=None,
    error_message=None,
):
    """Create a mock PendingAgent ORM object."""
    pending = MagicMock()
    pending.id = pending_id
    pending.company_id = company_id
    pending.agent_name = agent_name
    pending.specialty = specialty
    pending.channels = channels
    pending.payment_status = payment_status
    pending.provisioning_status = provisioning_status
    pending.paddle_event_id = paddle_event_id
    pending.paddle_checkout_id = None
    pending.paddle_transaction_id = None
    pending.created_at = created_at or datetime(2025, 1, 15, 12, 0, 0)
    pending.expires_at = expires_at or datetime(2025, 1, 16, 12, 0, 0)
    pending.provisioned_at = provisioned_at
    pending.error_message = error_message
    return pending


def _make_company(tier="mini_parwa"):
    """Create a mock Company object with subscription_tier."""
    company = MagicMock()
    company.id = "comp-abc-123"
    company.subscription_tier = tier
    return company


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════

class TestConstants:
    def test_valid_specialties(self):
        assert "billing" in VALID_SPECIALTIES
        assert "technical" in VALID_SPECIALTIES
        assert "general" in VALID_SPECIALTIES
        assert "custom" in VALID_SPECIALTIES
        assert len(VALID_SPECIALTIES) == 9

    def test_valid_channels(self):
        assert VALID_CHANNELS == {"chat", "email", "sms", "whatsapp", "voice"}

    def test_payment_timeout_hours(self):
        assert PAYMENT_TIMEOUT_HOURS == 24

    def test_max_provisioning_retries(self):
        assert MAX_PROVISIONING_RETRIES == 3

    def test_tier_agent_limits(self):
        assert TIER_AGENT_LIMITS["mini_parwa"] == 1
        assert TIER_AGENT_LIMITS["parwa"] == 3
        assert TIER_AGENT_LIMITS["parwa_high"] == 10


# ══════════════════════════════════════════════════════════════════
# VALIDATE_SPECIALTY TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidateSpecialty:
    def test_valid_specialty(self, service):
        service._validate_specialty("billing")  # Should not raise

    def test_all_valid_specialties(self, service):
        for s in VALID_SPECIALTIES:
            service._validate_specialty(s)  # Should not raise

    def test_invalid_specialty(self, service):
        with pytest.raises(ValidationError) as exc:
            service._validate_specialty("quantum_physics")
        assert "Invalid specialty" in exc.value.message

    def test_empty_specialty(self, service):
        with pytest.raises(ValidationError):
            service._validate_specialty("")

    def test_none_specialty(self, service):
        with pytest.raises(ValidationError):
            service._validate_specialty(None)


# ══════════════════════════════════════════════════════════════════
# VALIDATE_CHANNELS TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidateChannels:
    def test_valid_channels(self, service):
        service._validate_channels(["chat", "email"])  # Should not raise

    def test_single_channel(self, service):
        service._validate_channels(["sms"])  # Should not raise

    def test_invalid_channels(self, service):
        with pytest.raises(ValidationError) as exc:
            service._validate_channels(["chat", "fax"])
        assert "Invalid channels" in exc.value.message
        assert "fax" in str(exc.value.details.get("invalid_channels", []))

    def test_empty_channels(self, service):
        with pytest.raises(ValidationError) as exc:
            service._validate_channels([])
        assert "At least one channel" in exc.value.message

    def test_all_channels(self, service):
        service._validate_channels(list(VALID_CHANNELS))  # Should not raise


# ══════════════════════════════════════════════════════════════════
# VALIDATE_AGENT_NAME TESTS
# ══════════════════════════════════════════════════════════════════

class TestValidateAgentName:
    def test_valid_name(self, service):
        service._validate_agent_name("Support Bot")  # Should not raise

    def test_empty_name(self, service):
        with pytest.raises(ValidationError) as exc:
            service._validate_agent_name("")
        assert "Agent name is required" in exc.value.message

    def test_whitespace_only_name(self, service):
        with pytest.raises(ValidationError):
            service._validate_agent_name("   ")

    def test_none_name(self, service):
        with pytest.raises(ValidationError):
            service._validate_agent_name(None)

    def test_too_long_name(self, service):
        long_name = "A" * 201
        with pytest.raises(ValidationError) as exc:
            service._validate_agent_name(long_name)
        assert "200 characters" in exc.value.message

    def test_max_length_name(self, service):
        service._validate_agent_name("A" * 200)  # Should not raise

    def test_name_with_leading_trailing_whitespace(self, service):
        service._validate_agent_name("  Support Bot  ")  # Should not raise


# ══════════════════════════════════════════════════════════════════
# GET_COMPANY_TIER TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetCompanyTier:
    def test_with_tier_attribute(self, service, mock_db, company_id):
        company = _make_company(tier="parwa")
        mock_db.query.return_value.filter.return_value.first.return_value = company

        result = service._get_company_tier(company_id)

        assert result == "parwa"

    def test_without_tier_defaults(self, service, mock_db, company_id):
        company = MagicMock()
        company.subscription_tier = None
        mock_db.query.return_value.filter.return_value.first.return_value = company

        result = service._get_company_tier(company_id)

        assert result == "mini_parwa"

    def test_no_company_defaults(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service._get_company_tier(company_id)

        assert result == "mini_parwa"


# ══════════════════════════════════════════════════════════════════
# CHECK_AGENT_LIMIT TESTS
# ══════════════════════════════════════════════════════════════════

class TestCheckAgentLimit:
    def test_under_limit(self, service, mock_db, company_id):
        company = _make_company(tier="parwa")  # max 3
        mock_db.query.return_value.filter.return_value.first.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 1

        service._check_agent_limit(company_id)  # Should not raise

    def test_at_limit_raises(self, service, mock_db, company_id):
        company = _make_company(tier="mini_parwa")  # max 1
        mock_db.query.return_value.filter.return_value.first.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 1

        with pytest.raises(ValidationError) as exc:
            service._check_agent_limit(company_id)
        assert "Agent limit reached" in exc.value.message
        assert exc.value.details.get("upgrade_required") is True

    def test_over_limit_raises(self, service, mock_db, company_id):
        company = _make_company(tier="parwa")  # max 3
        mock_db.query.return_value.filter.return_value.first.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        with pytest.raises(ValidationError):
            service._check_agent_limit(company_id)


# ══════════════════════════════════════════════════════════════════
# GET_AGENT_LIMIT TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetAgentLimit:
    def test_mini_parwa_tier(self, service, mock_db, company_id):
        company = _make_company(tier="mini_parwa")
        mock_db.query.return_value.filter.return_value.first.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.get_agent_limit(company_id)

        assert result["tier"] == "mini_parwa"
        assert result["max_agents"] == 1
        assert result["current_agents"] == 0
        assert result["can_add"] is True

    def test_parwa_tier(self, service, mock_db, company_id):
        company = _make_company(tier="parwa")
        mock_db.query.return_value.filter.return_value.first.return_value = company
        mock_db.query.return_value.filter.return_value.count.return_value = 2

        result = service.get_agent_limit(company_id)

        assert result["tier"] == "parwa"
        assert result["max_agents"] == 3
        assert result["current_agents"] == 2
        assert result["can_add"] is True

    def test_default_tier(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.get_agent_limit(company_id)

        assert result["tier"] == "mini_parwa"
        assert result["max_agents"] == 1


# ══════════════════════════════════════════════════════════════════
# CREATE_CHECKOUT TESTS
# ══════════════════════════════════════════════════════════════════

class TestCreateCheckout:
    @patch.object(AgentProvisioningService, "_create_paddle_checkout")
    @patch.object(AgentProvisioningService, "_check_agent_limit")
    def test_valid_checkout(self, mock_check, mock_paddle, service, mock_db, company_id):
        mock_paddle.return_value = "https://checkout.paddle.com/agent/pending-1"

        result = service.create_checkout(
            company_id=company_id,
            agent_name="Support Bot",
            specialty="billing",
            channels=["chat", "email"],
            paddle_customer_id="cust-123",
        )

        assert "pending_agent_id" in result
        assert result["paddle_checkout_url"] == "https://checkout.paddle.com/agent/pending-1"
        assert result["payment_status"] == "pending"
        mock_db.add.assert_called()

    def test_invalid_specialty_raises(self, service, company_id):
        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="invalid_specialty",
                channels=["chat"],
            )

    def test_invalid_channels_raises(self, service, company_id):
        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["fax"],
            )

    def test_name_too_long_raises(self, service, company_id):
        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="A" * 201,
                specialty="billing",
                channels=["chat"],
            )

    @patch.object(AgentProvisioningService, "_check_agent_limit")
    def test_agent_limit_reached(self, mock_check, service, company_id):
        mock_check.side_effect = ValidationError(
            message="Agent limit reached",
            details={"tier": "mini_parwa"},
        )

        with pytest.raises(ValidationError):
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["chat"],
            )

    @patch.object(AgentProvisioningService, "_create_paddle_checkout")
    @patch.object(AgentProvisioningService, "_check_agent_limit")
    def test_paddle_failure_raises_internal(self, mock_check, mock_paddle, service, company_id):
        mock_paddle.side_effect = Exception("Paddle API error")

        with pytest.raises(InternalError) as exc:
            service.create_checkout(
                company_id=company_id,
                agent_name="Bot",
                specialty="billing",
                channels=["chat"],
            )
        assert "Failed to create payment checkout" in exc.value.message


# ══════════════════════════════════════════════════════════════════
# PROCESS_WEBHOOK TESTS
# ══════════════════════════════════════════════════════════════════

class TestProcessWebhook:
    def test_subscription_created(self, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="pending")
        # Query 1: idempotency → .filter().first() → None
        # Query 2: find pending → .filter().order_by().first() → pending
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.side_effect = [None, pending]
        mock_db.query.return_value = chain

        with patch.object(service, "_dispatch_provisioning_task"):
            result = service.process_webhook(
                company_id=company_id,
                event_type="subscription.created",
                event_data={"transaction_id": "txn-123"},
                event_id="evt-001",
            )

        assert result["status"] == "processed"
        assert "pending_agent_id" in result
        assert pending.payment_status == "paid"

    def test_transaction_completed(self, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="pending")
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.side_effect = [None, pending]
        mock_db.query.return_value = chain

        with patch.object(service, "_dispatch_provisioning_task"):
            result = service.process_webhook(
                company_id=company_id,
                event_type="transaction.completed",
                event_data={"transaction_id": "txn-456", "subscription_id": "sub-1"},
                event_id="evt-002",
            )

        assert result["status"] == "processed"
        assert pending.paddle_transaction_id == "txn-456"

    def test_idempotent_duplicate(self, service, mock_db, company_id):
        existing = _make_pending_agent(payment_status="paid")
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = service.process_webhook(
            company_id=company_id,
            event_type="subscription.created",
            event_data={},
            event_id="evt-001",
        )

        assert result["status"] == "already_processed"
        assert result["action"] == "duplicate"

    def test_unsupported_event(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.process_webhook(
            company_id=company_id,
            event_type="payment.refunded",
            event_data={},
            event_id="evt-003",
        )

        assert result["action"] == "unsupported_event_type"

    def test_no_pending_agent(self, service, mock_db, company_id):
        # Idempotency check passes (no duplicate), but no matching pending agent
        # Query 1: .filter().first() → None (idempotency)
        # Query 2: .filter().order_by().first() → None (no pending agent)
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.side_effect = [None, None]
        mock_db.query.return_value = chain

        result = service.process_webhook(
            company_id=company_id,
            event_type="subscription.created",
            event_data={},
            event_id="evt-004",
        )

        assert result["action"] == "no_pending_agent_found"

    def test_dispatch_failure_still_records(self, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="pending")
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.first.side_effect = [None, pending]
        mock_db.query.return_value = chain

        with patch.object(service, "_dispatch_provisioning_task", side_effect=Exception("Task error")):
            result = service.process_webhook(
                company_id=company_id,
                event_type="subscription.created",
                event_data={},
                event_id="evt-005",
            )

        # Payment should still be recorded even if dispatch fails
        assert result["status"] == "processed"
        assert "dispatch_failed" in result["action"]


# ══════════════════════════════════════════════════════════════════
# PROVISION_AGENT TESTS
# ══════════════════════════════════════════════════════════════════

class TestProvisionAgent:
    @patch.object(AgentProvisioningService, "_create_default_metric_threshold")
    def test_valid_flow(self, mock_threshold, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="paid", provisioning_status="awaiting_payment")

        mock_db.query.return_value.filter.return_value.first.return_value = pending

        result = service.provision_agent("pending-1", company_id)

        assert result["status"] == "training"
        assert "provisioned successfully" in result["message"].lower()
        assert pending.provisioning_status == "training"
        mock_db.add.assert_called()

    def test_not_found_raises(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc:
            service.provision_agent("nonexistent", company_id)
        assert "not found" in exc.value.message.lower()

    def test_not_paid_raises(self, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="pending")
        mock_db.query.return_value.filter.return_value.first.return_value = pending

        with pytest.raises(ValidationError) as exc:
            service.provision_agent("pending-1", company_id)
        assert "Payment must be completed" in exc.value.message

    def test_already_provisioned_returns(self, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="paid", provisioning_status="training")
        mock_db.query.return_value.filter.return_value.first.return_value = pending

        result = service.provision_agent("pending-1", company_id)

        assert result["status"] == "training"
        assert "already provisioned" in result["message"].lower()

    @patch.object(AgentProvisioningService, "_create_default_metric_threshold")
    def test_db_failure_marks_failed(self, mock_threshold, service, mock_db, company_id):
        pending = _make_pending_agent(payment_status="paid")
        mock_db.query.return_value.filter.return_value.first.return_value = pending
        mock_db.add.side_effect = Exception("DB constraint error")

        with pytest.raises(InternalError) as exc:
            service.provision_agent("pending-1", company_id)
        assert "failed" in exc.value.message.lower()
        assert pending.provisioning_status == "failed"
        assert pending.error_message is not None


# ══════════════════════════════════════════════════════════════════
# GET_PROVISIONING_STATUS TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetProvisioningStatus:
    def test_valid_status(self, service, mock_db, company_id):
        pending = _make_pending_agent(
            created_at=datetime(2025, 1, 15, 12, 0, 0),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = pending

        result = service.get_provisioning_status("pending-1", company_id)

        assert result["id"] == "pending-1"
        assert result["agent_name"] == "Support Bot"
        assert result["specialty"] == "billing"
        assert result["payment_status"] == "paid"
        assert result["provisioning_status"] == "awaiting_payment"
        assert result["created_at"] is not None

    def test_not_found_raises(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            service.get_provisioning_status("nonexistent", company_id)

    def test_includes_error_message(self, service, mock_db, company_id):
        pending = _make_pending_agent(
            error_message="Provisioning failed: DB error",
        )
        mock_db.query.return_value.filter.return_value.first.return_value = pending

        result = service.get_provisioning_status("pending-1", company_id)

        assert "DB error" in result["error_message"]


# ══════════════════════════════════════════════════════════════════
# CLEANUP_STALE_PENDING TESTS
# ══════════════════════════════════════════════════════════════════

class TestCleanupStalePending:
    def test_expired_agents(self, service, mock_db):
        stale1 = _make_pending_agent(pending_id="old-1", payment_status="pending")
        stale2 = _make_pending_agent(pending_id="old-2", payment_status="pending")
        mock_db.query.return_value.filter.return_value.all.return_value = [stale1, stale2]

        count = service.cleanup_stale_pending()

        assert count == 2
        assert stale1.payment_status == "expired"
        assert stale2.payment_status == "expired"
        mock_db.flush.assert_called_once()

    def test_no_stale_agents(self, service, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []

        count = service.cleanup_stale_pending()

        assert count == 0
        mock_db.flush.assert_not_called()
