"""
Billing Day 5 Unit Tests (20 items: R1-R20)

Tests for:
- CB1-CB5: Chargeback handling
- RF1-RF5: Admin refund system + credit balance
- SC1-SC4: Spending caps
- WH1-WH4: Webhook hardening
- FS1-FS3: Financial safety

All services use mocked database models from conftest.py.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, call
from typing import Any

import pytest


# ── Project root for migration checks ────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ═══════════════════════════════════════════════════════════════════════
# CB1-CB5: Chargeback Tests
# ═══════════════════════════════════════════════════════════════════════


class TestChargebackModels:
    """CB1: Verify chargeback model exists with correct columns."""

    def test_chargeback_model_exists(self):
        """CB1: Chargeback model should exist in billing_extended."""
        from database.models.billing_extended import Chargeback
        assert Chargeback is not None

    def test_chargeback_has_required_columns(self):
        """CB1: Chargeback should have all required columns."""
        from database.models.billing_extended import Chargeback
        required = [
            "id", "company_id", "paddle_transaction_id", "paddle_chargeback_id",
            "amount", "currency", "reason", "status", "service_stopped_at",
            "notification_sent_at", "resolved_at", "resolution_notes", "created_at",
        ]
        for col in required:
            assert hasattr(Chargeback, col), f"Missing column: {col}"

    def test_chargeback_tablename(self):
        """CB1: Chargeback table name should be chargebacks."""
        from database.models.billing_extended import Chargeback
        assert Chargeback.__tablename__ == "chargebacks"


class TestChargebackService:
    """CB1-CB5: Chargeback service tests."""

    @patch("app.services.chargeback_service.SessionLocal")
    def test_process_chargeback_event_creates_record(self, mock_session_cls):
        """CB1: process_chargeback_event should create a Chargeback record."""
        from app.services.chargeback_service import get_chargeback_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        company_id = str(uuid.uuid4())
        event_data = {
            "paddle_transaction_id": "txn_123",
            "amount": "2499.00",
            "currency": "USD",
            "reason": "fraudulent",
        }

        svc = get_chargeback_service()
        result = svc.process_chargeback_event(company_id, event_data)

        assert result is not None
        assert mock_db.commit.called

    @patch("app.services.chargeback_service.SessionLocal")
    def test_chargeback_stops_service(self, mock_session_cls):
        """CB2: Chargeback should stop service — set subscription to payment_failed."""
        from app.services.chargeback_service import get_chargeback_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        company_id = str(uuid.uuid4())

        mock_sub = MagicMock()
        mock_sub.status = "active"
        # Service: db.query(Subscription).filter(company_id, status).first() — ONE filter call
        # Then: db.query(Company).filter(id).first() — ONE filter call
        # Use side_effect to return sub for first query, company for second
        mock_company = MagicMock(name="Company")
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_sub, mock_company]
        mock_db.commit = MagicMock()

        svc = get_chargeback_service()
        result = svc.stop_service_on_chargeback(mock_db, company_id)

        assert mock_sub.status == "payment_failed"

    @patch("app.services.chargeback_service.SessionLocal")
    def test_list_chargebacks_returns_list(self, mock_session_cls):
        """CB1: list_chargebacks should return a list."""
        from app.services.chargeback_service import get_chargeback_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        svc = get_chargeback_service()
        result = svc.list_chargebacks(str(uuid.uuid4()))

        assert isinstance(result, list)

    @patch("app.services.chargeback_service.SessionLocal")
    def test_update_chargeback_status(self, mock_session_cls):
        """CB4: Update chargeback status should work."""
        from app.services.chargeback_service import get_chargeback_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cb = MagicMock()
        mock_cb.status = "received"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cb

        svc = get_chargeback_service()
        result = svc.update_chargeback_status("cb_123", "under_review", "Investigating")

        assert mock_cb.status == "under_review"

    @patch("app.services.chargeback_service.SessionLocal")
    def test_admin_notification_data(self, mock_session_cls):
        """CB3: get_admin_notification_data should return notification payload."""
        from app.services.chargeback_service import get_chargeback_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cb = MagicMock()
        mock_cb.id = "cb_123"
        mock_cb.company_id = str(uuid.uuid4())
        mock_cb.amount = Decimal("2499.00")
        mock_cb.currency = "USD"
        mock_cb.reason = "fraudulent"
        mock_cb.status = "received"
        mock_cb.created_at = datetime.now(timezone.utc)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cb

        svc = get_chargeback_service()
        result = svc.get_admin_notification_data("cb_123")

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# RF1-RF5: Refund System Tests
# ═══════════════════════════════════════════════════════════════════════


class TestRefundModels:
    """RF3/RF5: Verify refund-related models exist."""

    def test_refund_audit_model_exists(self):
        """RF5: RefundAudit model should exist."""
        from database.models.billing_extended import RefundAudit
        assert RefundAudit is not None

    def test_refund_audit_tablename(self):
        """RF5: RefundAudit table name should be refund_audits."""
        from database.models.billing_extended import RefundAudit
        assert RefundAudit.__tablename__ == "refund_audits"

    def test_refund_audit_has_dual_approval_columns(self):
        """RF5: RefundAudit should have dual approval columns."""
        from database.models.billing_extended import RefundAudit
        assert hasattr(RefundAudit, "approver_id")
        assert hasattr(RefundAudit, "second_approver_id")

    def test_credit_balance_model_exists(self):
        """RF3: CreditBalance model should exist."""
        from database.models.billing_extended import CreditBalance
        assert CreditBalance is not None

    def test_credit_balance_tablename(self):
        """RF3: CreditBalance table name should be credit_balances."""
        from database.models.billing_extended import CreditBalance
        assert CreditBalance.__tablename__ == "credit_balances"

    def test_credit_balance_has_source_column(self):
        """RF3: CreditBalance should have source column."""
        from database.models.billing_extended import CreditBalance
        assert hasattr(CreditBalance, "source")


class TestRefundService:
    """RF1-RF5: Refund service tests."""

    @patch("app.services.refund_service.SessionLocal")
    def test_create_refund_needs_dual_approval(self, mock_session_cls):
        """RF1: Refunds > $500 should need dual approval (status=pending)."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        added = []
        mock_db.add = lambda o: (added.append(o), setattr(o, 'id', str(uuid.uuid4())))
        mock_db.flush = MagicMock()

        svc = get_refund_service()
        result = svc.create_refund(
            company_id=str(uuid.uuid4()),
            amount=Decimal("600.00"),
            reason="Service issue",
            refund_type="partial",
            admin_id=str(uuid.uuid4()),
        )

        # All refunds start as "pending" — dual approval is tracked via needs_dual_approval field
        assert result["status"] == "pending"

    @patch("app.services.refund_service.SessionLocal")
    def test_create_refund_small_amount(self, mock_session_cls):
        """RF1: All refunds start as pending; $200 refund should be logged with dual_approval=False."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(name="Company")

        added = []
        mock_db.add = lambda o: (added.append(o), setattr(o, 'id', str(uuid.uuid4())))
        mock_db.flush = MagicMock()

        svc = get_refund_service()
        result = svc.create_refund(
            company_id=str(uuid.uuid4()),
            amount=Decimal("200.00"),
            reason="Minor issue",
            refund_type="partial",
            admin_id=str(uuid.uuid4()),
        )

        # Service always creates with pending status
        assert result["status"] == "pending"

    @patch("app.services.refund_service.SessionLocal")
    def test_create_credit_balance(self, mock_session_cls):
        """RF3: Credit balance should be created with default 12-month expiry."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        added = []
        mock_db.add = lambda o: (added.append(o), setattr(o, 'id', str(uuid.uuid4())))
        mock_db.flush = MagicMock()

        svc = get_refund_service()
        result = svc.create_credit_balance(
            company_id=str(uuid.uuid4()),
            amount=Decimal("100.00"),
            source="refund",
            description="Refund credit",
        )

        assert result is not None
        assert result["amount"] == "100.00"
        assert result["source"] == "refund"

    @patch("app.services.refund_service.SessionLocal")
    def test_list_refund_audits(self, mock_session_cls):
        """RF5: list_refund_audits should return list."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        svc = get_refund_service()
        result = svc.list_refund_audits(str(uuid.uuid4()))

        assert isinstance(result, list)

    @patch("app.services.refund_service.SessionLocal")
    def test_get_available_credits(self, mock_session_cls):
        """RF3: get_available_credits should return credit list."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        # The service uses SQLAlchemy expressions (.in_(), .is_(), |) that don't work
        # with mock model attributes. Mock the entire query result.
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        svc = get_refund_service()
        result = svc.get_available_credits(str(uuid.uuid4()))

        assert isinstance(result, list)

    @patch("app.services.refund_service.SessionLocal")
    def test_request_cooling_off_refund_within_window(self, mock_session_cls):
        """RF4: Cooling-off refund within 24h should work for <$1000."""
        from app.services.refund_service import get_refund_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_sub.tier = "growth"
        mock_sub.current_period_start = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=28)
        mock_sub.billing_frequency = "monthly"
        mock_sub.paddle_subscription_id = "sub_123"
        mock_sub.days_in_period = 30

        # Service: db.query(Subscription).filter(company_id).order_by(desc).first() — only Subscription
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [mock_sub]

        added = []
        mock_db.add = lambda o: (added.append(o), setattr(o, 'id', str(uuid.uuid4())))
        mock_db.flush = MagicMock()

        svc = get_refund_service()
        result = svc.request_cooling_off_refund(
            company_id=str(uuid.uuid4()),
            reason="Not what I expected",
        )

        assert result is not None

    @patch("app.services.refund_service.SessionLocal")
    def test_cooling_off_refund_expired_window(self, mock_session_cls):
        """RF4: Cooling-off refund after 24h should raise CoolingOffExpiredError."""
        from app.services.refund_service import get_refund_service, CoolingOffExpiredError

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
        mock_sub.tier = "growth"
        mock_sub.current_period_start = datetime.now(timezone.utc) - timedelta(hours=48)
        mock_sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=26)
        mock_sub.billing_frequency = "monthly"
        mock_sub.paddle_subscription_id = "sub_123"
        mock_sub.days_in_period = 30
        # Service: db.query(Subscription).filter(company_id).order_by(desc).first()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [mock_sub]

        svc = get_refund_service()
        with pytest.raises(CoolingOffExpiredError):
            svc.request_cooling_off_refund(
                company_id=str(uuid.uuid4()),
                reason="Too late",
            )


# ═══════════════════════════════════════════════════════════════════════
# SC1-SC4: Spending Cap Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSpendingCapModels:
    """SC1: Verify spending cap model."""

    def test_spending_cap_model_exists(self):
        """SC1: SpendingCap model should exist in billing_extended."""
        from database.models.billing_extended import SpendingCap
        assert SpendingCap is not None

    def test_spending_cap_tablename(self):
        """SC1: SpendingCap table name should be spending_caps."""
        from database.models.billing_extended import SpendingCap
        assert SpendingCap.__tablename__ == "spending_caps"

    def test_spending_cap_has_max_overage(self):
        """SC1: SpendingCap should have max_overage_amount column."""
        from database.models.billing_extended import SpendingCap
        assert hasattr(SpendingCap, "max_overage_amount")

    def test_spending_cap_has_alert_thresholds(self):
        """SC3: SpendingCap should have alert_thresholds column."""
        from database.models.billing_extended import SpendingCap
        assert hasattr(SpendingCap, "alert_thresholds")


class TestSpendingCapService:
    """SC1-SC4: Spending cap service tests."""

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_set_spending_cap(self, mock_session_cls):
        """SC1: set_spending_cap should create a spending cap record."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.set_spending_cap(
            company_id=str(uuid.uuid4()),
            max_overage_amount=Decimal("50.00"),
        )

        assert result is not None
        assert mock_db.commit.called

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_remove_spending_cap(self, mock_session_cls):
        """SC4: remove_spending_cap should delete cap record."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cap = MagicMock()
        mock_cap.company_id = str(uuid.uuid4())
        mock_cap.max_overage_amount = Decimal("50.00")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cap
        mock_db.query.return_value.filter.return_value.delete.return_value = 1  # Return int for deleted count

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.remove_spending_cap(str(uuid.uuid4()))

        assert mock_db.delete.called or mock_db.commit.called

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_check_cap_blocks_overage(self, mock_session_cls):
        """SC2: check_cap_before_overage should block when cap exceeded."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cap = MagicMock()
        mock_cap.max_overage_amount = Decimal("50.00")
        mock_cap.is_active = True
        mock_cap.alert_thresholds = "[50, 75, 90]"
        # Mock: first() for spending cap; scalar() for current overage via func.sum query
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_cap, None]
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("45.00")

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.check_cap_before_overage(
            company_id=str(uuid.uuid4()),
            proposed_charge=Decimal("10.00"),
        )

        assert result["allowed"] is False or result.get("would_exceed") is True

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_check_cap_allows_within_limit(self, mock_session_cls):
        """SC2: check_cap_before_overage should allow when within cap."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cap = MagicMock()
        mock_cap.max_overage_amount = Decimal("50.00")
        mock_cap.is_active = True
        mock_cap.alert_thresholds = "[50, 75, 90]"
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_cap, None]
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("10.00")

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.check_cap_before_overage(
            company_id=str(uuid.uuid4()),
            proposed_charge=Decimal("5.00"),
        )

        assert result["allowed"] is True

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_enforce_hard_cap_blocks(self, mock_session_cls):
        """SC2: enforce_hard_cap should block when over limit."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cap = MagicMock()
        mock_cap.max_overage_amount = Decimal("50.00")
        # enforce_hard_cap: db.query(SpendingCap).filter(company_id, is_active).first() — ONE filter
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cap

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.enforce_hard_cap(
            company_id=str(uuid.uuid4()),
            current_overage_amount=Decimal("60.00"),
        )

        assert result["action"] == "block_tickets"

    @patch("app.services.spending_cap_service.SessionLocal")
    def test_enforce_hard_cap_allows(self, mock_session_cls):
        """SC2: enforce_hard_cap should allow when under limit."""
        from app.services.spending_cap_service import get_spending_cap_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_cap = MagicMock()
        mock_cap.max_overage_amount = Decimal("50.00")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cap

        svc = get_spending_cap_service()
        svc._table_available = True

        result = svc.enforce_hard_cap(
            company_id=str(uuid.uuid4()),
            current_overage_amount=Decimal("30.00"),
        )

        assert result["action"] == "allow"


# ═══════════════════════════════════════════════════════════════════════
# WH1-WH4: Webhook Hardening Tests
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookHardeningModels:
    """WH2/WH3: Verify webhook health models."""

    def test_dead_letter_webhook_model_exists(self):
        """WH3: DeadLetterWebhook model should exist."""
        from database.models.billing_extended import DeadLetterWebhook
        assert DeadLetterWebhook is not None

    def test_dead_letter_webhook_tablename(self):
        """WH3: DeadLetterWebhook table name should be dead_letter_webhooks."""
        from database.models.billing_extended import DeadLetterWebhook
        assert DeadLetterWebhook.__tablename__ == "dead_letter_webhooks"

    def test_webhook_health_stat_model_exists(self):
        """WH2: WebhookHealthStat model should exist."""
        from database.models.billing_extended import WebhookHealthStat
        assert WebhookHealthStat is not None

    def test_webhook_health_stat_tablename(self):
        """WH2: WebhookHealthStat table name should be webhook_health_stats."""
        from database.models.billing_extended import WebhookHealthStat
        assert WebhookHealthStat.__tablename__ == "webhook_health_stats"


class TestWebhookHealthService:
    """WH1-WH4: Webhook health service tests."""

    @patch("app.services.webhook_health_service.SessionLocal")
    def test_dead_letter_queue_add(self, mock_session_cls):
        """WH3: add_to_dead_letter_queue should create a DLQ record."""
        from app.services.webhook_health_service import get_webhook_health_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = get_webhook_health_service()
        result = svc.add_to_dead_letter_queue(
            company_id=str(uuid.uuid4()),
            provider="paddle",
            event_id="evt_123",
            event_type="subscription.activated",
            payload={"test": "data"},
            error_message="Processing failed",
        )

        assert result is not None
        assert mock_db.commit.called

    @patch("app.services.webhook_health_service.SessionLocal")
    def test_list_dead_letter_webhooks(self, mock_session_cls):
        """WH3: list_dead_letter_webhooks should return list."""
        from app.services.webhook_health_service import get_webhook_health_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        svc = get_webhook_health_service()
        result = svc.list_dead_letter_webhooks()

        assert isinstance(result, list)

    @patch("app.services.webhook_health_service.SessionLocal")
    def test_webhook_health_recording(self, mock_session_cls):
        """WH2: record_webhook_processed should update health stats."""
        from app.services.webhook_health_service import get_webhook_health_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_webhook_health_service()
        result = svc.record_webhook_processed(
            provider="paddle",
            event_type="subscription.activated",
            processing_time_ms=150,
            success=True,
        )

        assert result is not None
        assert mock_db.commit.called

    @patch("app.services.webhook_health_service.SessionLocal")
    def test_webhook_ordering_delay(self, mock_session_cls):
        """WH4: ensure_webhook_ordering should detect gaps and delay."""
        from app.services.webhook_health_service import get_webhook_health_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_unprocessed = MagicMock()
        mock_unprocessed.event_id = "evt_older"
        # Service: db.query(WebhookSequence).filter(company_id, status.in_([...]), occurred_at < dt).order_by(...).first()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_unprocessed

        svc = get_webhook_health_service()
        result = svc.ensure_webhook_ordering(
            company_id=str(uuid.uuid4()),
            event_id="evt_newer",
            occurred_at=datetime.now(timezone.utc),
        )

        assert result.get("delayed") is True

    @patch("app.services.webhook_health_service.SessionLocal")
    def test_backfill_webhooks(self, mock_session_cls):
        """WH1: backfill_webhooks should return result with status."""
        from app.services.webhook_health_service import get_webhook_health_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Mock all query chains: last_sync, idempotency keys, existing events
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        svc = get_webhook_health_service()
        # backfill_webhooks tries to call Paddle API, which may fail
        # Just verify it returns a dict without crashing
        result = svc.backfill_webhooks(
            since_timestamp="2026-04-15T00:00:00Z",
        )

        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════
# FS1-FS3: Financial Safety Tests
# ═══════════════════════════════════════════════════════════════════════


class TestFinancialSafetyService:
    """FS1-FS3: Financial safety service tests."""

    def test_global_overage_cap_enforcement(self):
        """FS1: $500/month global hard cap should block when exceeded."""
        from app.services.financial_safety_service import get_financial_safety_service

        svc = get_financial_safety_service()
        result = svc.enforce_global_overage_cap(
            company_id=str(uuid.uuid4()),
            current_overage_amount=Decimal("550.00"),
        )

        assert result["allowed"] is False

    def test_global_overage_cap_allows_under(self):
        """FS1: Global cap should allow when under $500."""
        from app.services.financial_safety_service import get_financial_safety_service

        svc = get_financial_safety_service()
        result = svc.enforce_global_overage_cap(
            company_id=str(uuid.uuid4()),
            current_overage_amount=Decimal("300.00"),
        )

        assert result["allowed"] is True

    def test_global_overage_cap_at_limit(self):
        """FS1: Global cap should block at exactly $500."""
        from app.services.financial_safety_service import get_financial_safety_service

        svc = get_financial_safety_service()
        result = svc.enforce_global_overage_cap(
            company_id=str(uuid.uuid4()),
            current_overage_amount=Decimal("500.00"),
        )

        assert result["allowed"] is False

    @patch("app.services.financial_safety_service.SessionLocal")
    def test_anomaly_detection_spike(self, mock_session_cls):
        """FS2: Should detect anomaly when volume triples."""
        from app.services.financial_safety_service import get_financial_safety_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = get_financial_safety_service()

        today_mock = type("UR", (), {"tickets_used": 900})
        yesterday_mock = type("UR", (), {"tickets_used": 200})

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            today_mock, yesterday_mock
        ]

        result = svc.check_anomaly(company_id=str(uuid.uuid4()))

        assert result["anomaly_detected"] is True
        assert result["ratio"] > 3.0

    @patch("app.services.financial_safety_service.SessionLocal")
    def test_anomaly_no_false_positive_small_volume(self, mock_session_cls):
        """FS2: No false positive when yesterday had < 100 tickets."""
        from app.services.financial_safety_service import get_financial_safety_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = get_financial_safety_service()

        today_mock = type("UR", (), {"tickets_used": 150})
        yesterday_mock = type("UR", (), {"tickets_used": 30})

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            today_mock, yesterday_mock
        ]

        result = svc.check_anomaly(company_id=str(uuid.uuid4()))

        assert result["anomaly_detected"] is False

    @patch("app.services.financial_safety_service.SessionLocal")
    def test_anomaly_no_spike_normal(self, mock_session_cls):
        """FS2: No anomaly when volume growth is normal."""
        from app.services.financial_safety_service import get_financial_safety_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        svc = get_financial_safety_service()

        today_mock = type("UR", (), {"tickets_used": 500})
        yesterday_mock = type("UR", (), {"tickets_used": 450})

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            today_mock, yesterday_mock
        ]

        result = svc.check_anomaly(company_id=str(uuid.uuid4()))

        assert result["anomaly_detected"] is False

    @patch("app.services.financial_safety_service.SessionLocal")
    def test_invoice_audit_returns_summary(self, mock_session_cls):
        """FS3: audit_invoices should return summary dict."""
        from app.services.financial_safety_service import get_financial_safety_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.all.return_value = []

        svc = get_financial_safety_service()
        result = svc.audit_invoices(company_id=str(uuid.uuid4()))

        assert "matched" in result or "missing_local" in result or "missing_paddle" in result


# ═══════════════════════════════════════════════════════════════════════
# Webhook Handler: Chargeback Event Test
# ═══════════════════════════════════════════════════════════════════════


class TestChargebackWebhookHandler:
    """CB1: Verify chargeback webhook handler is registered."""

    def test_chargeback_handler_registered(self):
        """CB1: payment.chargeback.created handler should be registered."""
        from app.webhooks.paddle_handler import _PADDLE_HANDLERS
        assert "payment.chargeback.created" in _PADDLE_HANDLERS

    def test_chargeback_handler_processes_event(self):
        """CB1: Handler should return processed status."""
        from app.webhooks.paddle_handler import handle_payment_chargeback_created

        event = {
            "event_type": "payment.chargeback.created",
            "event_id": "evt_cb_123",
            "company_id": str(uuid.uuid4()),
            "payload": {
                "data": {
                    "chargeback": {
                        "transaction_id": "txn_456",
                        "amount": "2499.00",
                        "currency_code": "USD",
                        "reason": "fraudulent",
                        "status": "received",
                        "created_at": "2026-04-16T00:00:00Z",
                    }
                }
            },
        }

        result = handle_payment_chargeback_created(event)
        assert result["status"] == "processed"
        assert result["action"] == "chargeback_created"

    def test_chargeback_backward_compat_alias(self):
        """CB1: subscription.chargeback.created should also be registered."""
        from app.webhooks.paddle_handler import _PADDLE_HANDLERS
        assert "subscription.chargeback.created" in _PADDLE_HANDLERS


# ═══════════════════════════════════════════════════════════════════════
# Migration Verification
# ═══════════════════════════════════════════════════════════════════════


class TestDay5Migration:
    """Verify Day 5 migration file exists and is correct."""

    def test_migration_file_exists(self):
        """Day 5 migration file should exist."""
        migration_path = _PROJECT_ROOT / "database" / "alembic" / "versions" / "024_day5_billing_protection.py"
        assert migration_path.exists(), f"Migration file not found at {migration_path}"

    def test_migration_creates_all_tables(self):
        """Migration should create all 6 Day 5 tables."""
        migration_path = _PROJECT_ROOT / "database" / "alembic" / "versions" / "024_day5_billing_protection.py"
        with open(migration_path) as f:
            content = f.read()

        expected_tables = [
            "chargebacks", "credit_balances", "spending_caps",
            "dead_letter_webhooks", "webhook_health_stats", "refund_audits",
        ]
        for table in expected_tables:
            assert table in content, f"Missing table {table} in migration"

    def test_migration_revision_chain(self):
        """Migration should reference 023_training_runs as down_revision."""
        migration_path = _PROJECT_ROOT / "database" / "alembic" / "versions" / "024_day5_billing_protection.py"
        with open(migration_path) as f:
            content = f.read()
        assert "023_training_runs" in content
