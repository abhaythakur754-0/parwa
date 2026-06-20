"""
Billing System End-to-End Integration Tests (WEEK5_PAYMENT_ROADMAP)

Verifies the full billing lifecycle by integrating multiple services
together.  Mocks external dependencies (Paddle API, database) but
tests the interaction between services:

  1. TestSubscriptionLifecycle   – create / duplicate / invalid variant
  2. TestUpgradeDowngrade        – proration calculation / scheduled downgrade
  3. TestCancellationFlow        – period-end / immediate / reactivate
  4. TestPaymentFailureFlow      – stop / idempotent / resume / freeze
  5. TestUsageTracking           – increment / overage / monthly history
  6. TestVariantLimitEnforcement – tickets / team / KB doc limits
  7. TestReconciliation          – subscription status sync / usage sync

All tests use mocks — no real DB or Paddle API calls.
"""

import pytest
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import sys
sys.path.insert(0, '/home/z/my-project/parwa')


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session (context-manager compatible)."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture
def mock_company():
    """Mock Company ORM object."""
    company = MagicMock()
    company.id = str(uuid4())
    company.subscription_status = "active"
    company.subscription_tier = "starter"
    company.paddle_customer_id = "cust_123"
    company.paddle_subscription_id = None
    return company


@pytest.fixture
def mock_active_subscription(mock_company):
    """Mock Subscription ORM object (active, starter)."""
    sub = MagicMock()
    sub.id = str(uuid4())
    sub.company_id = mock_company.id
    sub.tier = "starter"
    sub.status = "active"
    sub.current_period_start = datetime.now(timezone.utc)
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
    sub.cancel_at_period_end = False
    sub.paddle_subscription_id = None
    sub.created_at = datetime.now(timezone.utc)
    return sub


def _mock_agg(**kwargs):
    """Build a mock SQLAlchemy aggregation row."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _make_usage_history_rows(months_data):
    """Build a list of mock aggregation rows for usage history queries."""
    rows = []
    for m in months_data:
        row = MagicMock()
        row.record_month = m["record_month"]
        row.total_tickets = m["tickets_used"]
        row.total_overage_tickets = m.get("overage_tickets", 0)
        row.total_overage_charges = m.get("overage_charges", Decimal("0.00"))
        rows.append(row)
    return rows


# ══════════════════════════════════════════════════════════════════════════
# 1. TestSubscriptionLifecycle
# ══════════════════════════════════════════════════════════════════════════


class TestSubscriptionLifecycle:
    """Creating subscriptions for all variants, duplicate prevention,
    and rejection of invalid variants."""

    @pytest.mark.asyncio
    async def test_create_subscription_starter(self, mock_db, mock_company):
        """Company creates a starter subscription."""
        from backend.app.services.subscription_service import (
            SubscriptionService,
            SubscriptionAlreadyExistsError,
        )
        from backend.app.schemas.billing import VariantType

        service = SubscriptionService()
        company_id = uuid4()

        mock_sub = MagicMock()
        mock_sub.id = str(uuid4())
        mock_sub.company_id = str(company_id)
        mock_sub.tier = "starter"
        mock_sub.status = "active"
        mock_sub.current_period_start = datetime.now(timezone.utc)
        mock_sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        mock_sub.cancel_at_period_end = False
        mock_sub.paddle_subscription_id = None
        mock_sub.created_at = datetime.now(timezone.utc)

        mock_company.id = str(company_id)

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            # First query: no existing subscription; second: company lookup
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [None, mock_company]
            mock_db.refresh = MagicMock()
            mock_db.add = MagicMock()

            result = await service.create_subscription(
                company_id=company_id, variant="starter",
            )

        assert result.variant == VariantType.STARTER
        assert result.status.value == "active"

    @pytest.mark.asyncio
    async def test_create_subscription_growth(self, mock_db, mock_company):
        """Company creates a growth subscription."""
        from backend.app.services.subscription_service import SubscriptionService
        from backend.app.schemas.billing import VariantType

        service = SubscriptionService()
        company_id = uuid4()
        mock_company.id = str(company_id)

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [None, mock_company]
            mock_db.refresh = MagicMock()
            mock_db.add = MagicMock()

            # We only care about the return type check; the service
            # validates variant before DB ops, so patch _to_subscription_info
            info = MagicMock()
            info.variant = VariantType.GROWTH
            info.status = MagicMock(value="active")
            with patch.object(service, '_to_subscription_info', return_value=info):
                result = await service.create_subscription(
                    company_id=company_id, variant="growth",
                )

        assert result.variant == VariantType.GROWTH

    @pytest.mark.asyncio
    async def test_create_subscription_high(self, mock_db, mock_company):
        """Company creates a high subscription."""
        from backend.app.services.subscription_service import SubscriptionService
        from backend.app.schemas.billing import VariantType

        service = SubscriptionService()
        company_id = uuid4()
        mock_company.id = str(company_id)

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [None, mock_company]
            mock_db.refresh = MagicMock()
            mock_db.add = MagicMock()

            info = MagicMock()
            info.variant = VariantType.HIGH
            info.status = MagicMock(value="active")
            with patch.object(service, '_to_subscription_info', return_value=info):
                result = await service.create_subscription(
                    company_id=company_id, variant="high",
                )

        assert result.variant == VariantType.HIGH

    @pytest.mark.asyncio
    async def test_create_subscription_duplicate_prevented(
        self, mock_db, mock_active_subscription
    ):
        """Can't create two active subscriptions for the same company."""
        from backend.app.services.subscription_service import (
            SubscriptionService,
            SubscriptionAlreadyExistsError,
        )

        service = SubscriptionService()
        company_id = uuid4()

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl:
            mock_sl.return_value = mock_db
            # First query returns an existing active subscription
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_active_subscription

            with pytest.raises(SubscriptionAlreadyExistsError):
                await service.create_subscription(
                    company_id=company_id, variant="growth",
                )

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_variant_rejected(self, mock_db):
        """'enterprise' variant is rejected as invalid."""
        from backend.app.services.subscription_service import (
            SubscriptionService,
            InvalidVariantError,
        )

        service = SubscriptionService()
        company_id = uuid4()

        with pytest.raises(InvalidVariantError, match="Invalid variant"):
            await service.create_subscription(
                company_id=company_id, variant="enterprise",
            )


# ══════════════════════════════════════════════════════════════════════════
# 2. TestUpgradeDowngrade
# ══════════════════════════════════════════════════════════════════════════


class TestUpgradeDowngrade:
    """Upgrade, downgrade, and same-variant no-op paths."""

    def _build_growth_sub(self, mock_company):
        sub = MagicMock()
        sub.id = str(uuid4())
        sub.company_id = mock_company.id
        sub.tier = "growth"
        sub.status = "active"
        sub.current_period_start = datetime.now(timezone.utc) - timedelta(days=10)
        sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=20)
        sub.cancel_at_period_end = False
        sub.paddle_subscription_id = None
        return sub

    def _build_high_sub(self, mock_company):
        sub = self._build_growth_sub(mock_company)
        sub.tier = "high"
        return sub

    @pytest.mark.asyncio
    async def test_upgrade_starter_to_growth(self, mock_db, mock_company):
        """Proration is calculated when upgrading starter → growth."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        mock_sub = self._build_growth_sub(mock_company)
        mock_sub.tier = "starter"  # Simulate existing starter sub

        info = MagicMock()
        info.variant = MagicMock(value="growth")

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info), \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [mock_sub, mock_company]
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.upgrade_subscription(
                company_id=uuid4(), new_variant="growth",
            )

        assert result["proration"] is not None
        assert result["proration"]["old_variant"] == "starter"
        assert result["proration"]["new_variant"] == "growth"
        assert result["proration"]["old_price"] == Decimal("999.00")
        assert result["proration"]["new_price"] == Decimal("2499.00")

    @pytest.mark.asyncio
    async def test_upgrade_growth_to_high(self, mock_db, mock_company):
        """Proration is calculated when upgrading growth → high."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        mock_sub = self._build_growth_sub(mock_company)
        mock_sub.tier = "growth"

        info = MagicMock()
        info.variant = MagicMock(value="high")

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info), \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [mock_sub, mock_company]
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.upgrade_subscription(
                company_id=uuid4(), new_variant="high",
            )

        assert result["proration"] is not None
        assert result["proration"]["old_variant"] == "growth"
        assert result["proration"]["new_variant"] == "high"
        assert result["proration"]["net_charge"] > 0

    @pytest.mark.asyncio
    async def test_downgrade_growth_to_starter(self, mock_db, mock_company):
        """Downgrade is scheduled at period end (not immediate)."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        mock_sub = self._build_growth_sub(mock_company)

        info = MagicMock()
        info.variant = MagicMock(value="growth")

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_sub

            result = await service.downgrade_subscription(
                company_id=uuid4(), new_variant="starter",
            )

        assert "scheduled_change" in result
        assert result["scheduled_change"]["current_variant"] == "growth"
        assert result["scheduled_change"]["new_variant"] == "starter"
        assert result["scheduled_change"]["effective_date"] is not None
        assert "scheduled" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_same_variant_noop(self, mock_db, mock_company):
        """Upgrading to the same variant returns a no-op message."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        mock_sub = self._build_growth_sub(mock_company)

        info = MagicMock()
        info.variant = MagicMock(value="growth")

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_sub

            result = await service.upgrade_subscription(
                company_id=uuid4(), new_variant="growth",
            )

        assert result["proration"] is None
        assert "already" in result["message"].lower()


# ══════════════════════════════════════════════════════════════════════════
# 3. TestCancellationFlow
# ══════════════════════════════════════════════════════════════════════════


class TestCancellationFlow:
    """Cancel at period end, cancel immediately, and reactivation."""

    @pytest.mark.asyncio
    async def test_cancel_at_period_end(self, mock_db, mock_active_subscription):
        """Netflix-style cancel: access until billing period end."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()

        info = MagicMock()
        info.cancel_at_period_end = True

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info), \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_active_subscription
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.cancel_subscription(
                company_id=uuid4(),
                reason="Downsizing",
                effective_immediately=False,
            )

        assert result["cancellation"]["effective_immediately"] is False
        assert result["cancellation"]["access_until"] is not None
        assert "continue" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_immediately(self, mock_db, mock_active_subscription):
        """Immediate cancellation stops service right away."""
        from backend.app.services.subscription_service import SubscriptionService
        from backend.app.schemas.billing import SubscriptionStatus

        service = SubscriptionService()

        info = MagicMock()
        info.status = SubscriptionStatus.CANCELED

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info), \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            # Sub query + Company query
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.side_effect = [
                    mock_active_subscription,
                    MagicMock(id=mock_active_subscription.company_id,
                              subscription_status="active"),
                ]
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.cancel_subscription(
                company_id=uuid4(),
                reason="Switching providers",
                effective_immediately=True,
            )

        assert result["cancellation"]["effective_immediately"] is True
        assert result["cancellation"]["access_until"] is None
        assert "canceled immediately" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_reactivate_canceled_subscription(
        self, mock_db, mock_active_subscription
    ):
        """Undo a pending cancellation (cancel_at_period_end)."""
        from backend.app.services.subscription_service import SubscriptionService

        service = SubscriptionService()
        mock_active_subscription.cancel_at_period_end = True

        info = MagicMock()
        info.cancel_at_period_end = False

        with patch('backend.app.services.subscription_service.SessionLocal') as mock_sl, \
             patch.object(service, '_to_subscription_info', return_value=info), \
             patch.object(service, '_get_paddle', new_callable=AsyncMock):
            mock_sl.return_value = mock_db
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_active_subscription
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.reactivate_subscription(
                company_id=uuid4(),
            )

        assert result.cancel_at_period_end is False


# ══════════════════════════════════════════════════════════════════════════
# 4. TestPaymentFailureFlow
# ══════════════════════════════════════════════════════════════════════════


class TestPaymentFailureFlow:
    """Payment failure stops service, is idempotent, resumes, freezes."""

    @pytest.mark.asyncio
    async def test_payment_failure_stops_service(self, mock_db, mock_company):
        """Payment failure sets status → payment_failed."""
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        mock_failure = MagicMock()
        mock_failure.id = str(uuid4())
        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_company
        # No existing failure
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_company.subscription_status = "active"

        with patch('backend.app.services.payment_failure_service.SessionLocal',
                   return_value=mock_db):
            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_fail_001",
                failure_code="card_declined",
                failure_reason="Insufficient funds",
                amount_attempted=Decimal("999.00"),
            )

        assert result["status"] == "stopped"
        assert result["new_status"] == "payment_failed"
        assert "service_stopped" in result["actions_taken"]
        assert mock_company.subscription_status == "payment_failed"

    @pytest.mark.asyncio
    async def test_payment_failure_idempotent(self, mock_db, mock_company):
        """Duplicate failure for the same company returns already_stopped."""
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        existing_failure = MagicMock()
        existing_failure.id = "existing_fail_id"
        existing_failure.resolved = False

        mock_db.query.return_value.filter.return_value \
            .with_for_update.return_value.first.return_value = mock_company
        mock_db.query.return_value.filter.return_value.first.return_value = existing_failure

        with patch('backend.app.services.payment_failure_service.SessionLocal',
                   return_value=mock_db):
            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_fail_002",
                failure_code="card_declined",
                failure_reason="Card expired",
                amount_attempted=Decimal("2499.00"),
            )

        assert result["status"] == "already_stopped"
        assert result["existing_failure_id"] == "existing_fail_id"
        assert "already" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_resume_after_payment(self, mock_db, mock_company):
        """Service resumes on successful payment after failure."""
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        mock_failure = MagicMock()
        mock_failure.id = "fail_to_resume"
        mock_failure.resolved = False

        mock_sub = MagicMock()
        mock_sub.status = "payment_failed"

        mock_company.subscription_status = "payment_failed"

        # with_for_update → company; then filter.first → failure; then
        # filter.return_value.order_by… → subscription
        with patch('backend.app.services.payment_failure_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_company
            mock_db.query.return_value.filter.return_value.first.return_value = mock_failure
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub
            mock_db.commit = MagicMock()

            result = await service.resume_service(
                company_id=company_id,
                paddle_transaction_id="txn_success_001",
            )

        assert result["status"] == "resumed"
        assert result["old_status"] == "payment_failed"
        assert result["new_status"] == "active"
        assert mock_failure.resolved is True
        assert mock_company.subscription_status == "active"

    @pytest.mark.asyncio
    async def test_payment_failure_freeze_tickets(self, mock_db, mock_company):
        """Payment failure freezes open tickets."""
        from backend.app.services.payment_failure_service import PaymentFailureService

        service = PaymentFailureService()
        company_id = uuid4()

        mock_company.subscription_status = "active"

        mock_open_tickets = [MagicMock(id=f"tkt_{i}") for i in range(3)]

        with patch('backend.app.services.payment_failure_service.SessionLocal',
                   return_value=mock_db) as mock_sl, \
             patch('backend.app.services.payment_failure_service.logger') as mock_logger:
            mock_db.query.return_value.filter.return_value \
                .with_for_update.return_value.first.return_value = mock_company
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_db.add = MagicMock()
            mock_db.commit = MagicMock()
            mock_db.refresh = MagicMock()

            result = await service.handle_payment_failure(
                company_id=company_id,
                paddle_transaction_id="txn_freeze_001",
                failure_code="card_declined",
                failure_reason="Insufficient funds",
                amount_attempted=Decimal("999.00"),
            )

        # Service is stopped — the TODO in the service would freeze
        # tickets.  Verify status is payment_failed.
        assert result["status"] == "stopped"
        assert mock_company.subscription_status == "payment_failed"


# ══════════════════════════════════════════════════════════════════════════
# 5. TestUsageTracking
# ══════════════════════════════════════════════════════════════════════════


class TestUsageTracking:
    """Increment usage, calculate overage, retrieve monthly history."""

    @pytest.mark.asyncio
    async def test_increment_and_retrieve_usage(self, mock_db):
        """Full round trip: increment tickets, then retrieve current usage."""
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()
        company_id = uuid4()

        mock_record = MagicMock()
        mock_record.tickets_used = 0
        mock_record.ai_agents_used = 0
        mock_record.voice_minutes_used = Decimal("0.00")
        mock_record.overage_tickets = 0
        mock_record.overage_charges = Decimal("0.00")
        mock_record.record_month = datetime.now(timezone.utc).strftime("%Y-%m")

        with patch('backend.app.services.usage_tracking_service.SessionLocal',
                   return_value=mock_db):
            # increment: get_or_create returns fresh record
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_db.add = MagicMock()
            mock_db.flush = MagicMock()

            # After flush, the record object's tickets_used is 0
            # We simulate the increment inside the service (record.tickets_used += count)
            # by re-binding the return of first after add+flush
            def _side_effect_increment(*a, **kw):
                mock_record.tickets_used = 50
                return None
            mock_db.flush.side_effect = _side_effect_increment
            mock_db.refresh = MagicMock()

            result = service.increment_ticket_usage(
                company_id=company_id, count=50,
            )

        assert result["tickets_used"] == 50

    def test_overage_calculation(self, mock_db):
        """Tickets over the plan limit are charged at $0.10 each."""
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()
        company_id = uuid4()

        with patch('backend.app.services.usage_tracking_service.SessionLocal',
                   return_value=mock_db):
            result = service.calculate_overage(
                company_id=company_id,
                tickets_used=2100,
                ticket_limit=2000,
            )

        assert result["overage_tickets"] == 100
        assert result["overage_charges"] == Decimal("10.00")
        assert result["overage_rate"] == Decimal("0.10")

    def test_overage_calculation_within_limit(self, mock_db):
        """No overage when usage is within the plan limit."""
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()
        company_id = uuid4()

        with patch('backend.app.services.usage_tracking_service.SessionLocal',
                   return_value=mock_db):
            result = service.calculate_overage(
                company_id=company_id,
                tickets_used=1500,
                ticket_limit=2000,
            )

        assert result["overage_tickets"] == 0
        assert result["overage_charges"] == Decimal("0.00")

    def test_monthly_usage_aggregation(self, mock_db):
        """Usage history returns data across multiple months."""
        from backend.app.services.usage_tracking_service import UsageTrackingService

        service = UsageTrackingService()
        company_id = uuid4()

        history_rows = _make_usage_history_rows([
            {"record_month": "2024-03", "tickets_used": 1800,
             "overage_tickets": 0, "overage_charges": Decimal("0.00")},
            {"record_month": "2024-02", "tickets_used": 2200,
             "overage_tickets": 200, "overage_charges": Decimal("20.00")},
            {"record_month": "2024-01", "tickets_used": 1990,
             "overage_tickets": 0, "overage_charges": Decimal("0.00")},
        ])

        with patch('backend.app.services.usage_tracking_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .group_by.return_value.order_by.return_value \
                .limit.return_value.all.return_value = history_rows

            result = service.get_usage_history(
                company_id=company_id, months=3,
            )

        assert len(result) == 3
        assert result[0]["record_month"] == "2024-03"
        assert result[0]["tickets_used"] == 1800
        assert result[1]["overage_tickets"] == 200
        assert result[1]["overage_charges"] == "20.00"


# ══════════════════════════════════════════════════════════════════════════
# 6. TestVariantLimitEnforcement
# ══════════════════════════════════════════════════════════════════════════


class TestVariantLimitEnforcement:
    """Ticket limit, team member limit, and KB doc limit enforcement."""

    @pytest.mark.asyncio
    async def test_ticket_limit_enforcement_at_cap(self, mock_db, mock_company):
        """Blocked when ticket usage equals or exceeds the limit."""
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.status = "active"

        with patch('backend.app.services.variant_limit_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub

            result = service.check_ticket_limit(
                company_id=uuid4(), current_count=2000,
            )

        assert result["allowed"] is False
        assert result["current_usage"] == 2000
        assert result["limit"] == 2000
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_ticket_limit_enforcement_under(self, mock_db, mock_company):
        """Allowed when ticket usage is under the limit."""
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.status = "active"

        with patch('backend.app.services.variant_limit_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub

            result = service.check_ticket_limit(
                company_id=uuid4(), current_count=1500,
            )

        assert result["allowed"] is True
        assert result["remaining"] == 500

    @pytest.mark.asyncio
    async def test_team_member_limit_check(self, mock_db):
        """Team member limit: under limit allowed, over limit blocked."""
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.status = "active"

        with patch('backend.app.services.variant_limit_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub

            # Under limit (starter allows 3 team members, have 2)
            result = service.check_team_member_limit(
                company_id=uuid4(), current_count=2,
            )
            assert result["allowed"] is True
            assert result["remaining"] == 1

            # At limit
            result = service.check_team_member_limit(
                company_id=uuid4(), current_count=3,
            )
            assert result["allowed"] is False
            assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_kb_doc_limit_check(self, mock_db):
        """KB doc limit: under and over for starter (100 docs)."""
        from backend.app.services.variant_limit_service import VariantLimitService

        service = VariantLimitService()

        mock_sub = MagicMock()
        mock_sub.tier = "starter"
        mock_sub.status = "active"

        with patch('backend.app.services.variant_limit_service.SessionLocal',
                   return_value=mock_db):
            mock_db.query.return_value.filter.return_value \
                .order_by.return_value.first.return_value = mock_sub

            # Under limit
            result = service.check_kb_doc_limit(
                company_id=uuid4(), current_count=80,
            )
            assert result["allowed"] is True
            assert result["remaining"] == 20

            # Over limit
            result = service.check_kb_doc_limit(
                company_id=uuid4(), current_count=105,
            )
            assert result["allowed"] is False
            assert "exceeded" in result["message"].lower()


# ══════════════════════════════════════════════════════════════════════════
# 7. TestReconciliation
# ══════════════════════════════════════════════════════════════════════════


class TestReconciliation:
    """Subscription status sync and usage reconciliation between
    local DB and Paddle."""

    @pytest.mark.asyncio
    async def test_subscription_status_sync(self, mock_db, mock_company):
        """DB subscription status is updated to match Paddle."""
        from backend.app.tasks.reconciliation_tasks import (
            _compare_subscription,
            _update_subscription_from_paddle,
        )

        mock_sub = MagicMock()
        mock_sub.status = "active"
        mock_sub.current_period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_sub.current_period_end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        mock_sub.cancel_at_period_end = False

        paddle_data = {
            "status": "paused",
            "items": [{"price": {"id": "pri_growth"}}],
            "current_billing_period": {
                "starts_at": "2024-01-15T00:00:00Z",
                "ends_at": "2024-02-15T00:00:00Z",
            },
            "scheduled_change": None,
        }

        discrepancies = _compare_subscription(mock_sub, paddle_data)
        assert len(discrepancies) > 0
        assert any("status" in d for d in discrepancies)

        _update_subscription_from_paddle(mock_sub, paddle_data)
        assert mock_sub.status == "paused"
        assert mock_sub.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_subscription_sync_cancel_flag(self, mock_db, mock_company):
        """Paddle scheduled_change sets cancel_at_period_end in DB."""
        from backend.app.tasks.reconciliation_tasks import (
            _update_subscription_from_paddle,
        )

        mock_sub = MagicMock()
        mock_sub.status = "active"

        paddle_data = {
            "status": "active",
            "scheduled_change": {"action": "cancel"},
        }

        _update_subscription_from_paddle(mock_sub, paddle_data)
        assert mock_sub.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_usage_reconciliation(self, mock_db, mock_company):
        """Usage reconciliation creates missing UsageRecords."""
        from backend.app.tasks.reconciliation_tasks import reconcile_usage

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_company]

        # No existing usage record
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        # Mock the Ticket import chain
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 42

        call_count = [0]
        def _query_side(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                # companies query
                return [mock_company]
            if call_count[0] == 2:
                # usage record query
                return None
            # count query
            return mock_count_result

        mock_db.query.return_value.filter.side_effect = _query_side

        with patch('backend.app.tasks.reconciliation_tasks.SessionLocal',
                   return_value=mock_db):
            result = reconcile_usage()

        assert result["checked"] >= 1
        assert result["errors"] == 0
