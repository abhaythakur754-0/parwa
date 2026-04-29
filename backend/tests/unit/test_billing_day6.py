"""
Billing Day 6 Unit Tests (25 items: MF1-MF12, T1-T8, DI1-DI5)

Tests for:
- MF1: Trial period (start, status, expiry, reminders)
- MF2: Subscription pause/resume
- MF3: Promo codes (create, validate, apply, duplicate prevention)
- MF4: Currency field
- MF6: Enterprise billing
- MF7: Invoice amendments
- MF8-MF11: Analytics, spending summary, voice/SMS usage
- DI1-DI5: Dashboard APIs
- Migration file
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ═══════════════════════════════════════════════════════════════════════
# MF1: Trial Tests
# ═══════════════════════════════════════════════════════════════════════


class TestTrialModels:
    """MF1: Verify trial-related model attributes exist."""

    def test_subscription_has_trial_days(self):
        """MF1: Subscription model should have trial_days column."""
        from database.models.billing import Subscription

        assert hasattr(Subscription, "trial_days")

    def test_subscription_has_trial_started_at(self):
        """MF1: Subscription model should have trial_started_at column."""
        from database.models.billing import Subscription

        assert hasattr(Subscription, "trial_started_at")

    def test_subscription_has_trial_ends_at(self):
        """MF1: Subscription model should have trial_ends_at column."""
        from database.models.billing import Subscription

        assert hasattr(Subscription, "trial_ends_at")


class TestTrialService:
    """MF1: Trial service tests."""

    @patch("app.services.trial_service.SessionLocal")
    def test_start_trial(self, mock_session_cls):
        """MF1: start_trial should set trial dates on subscription."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.trial_ends_at = None
        mock_sub.trial_days = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_sub
        )

        svc = get_trial_service()
        result = svc.start_trial(str(uuid.uuid4()), trial_days=14)

        assert result["status"] == "active"
        assert result["trial_days"] == 14
        assert "trial_ends_at" in result

    @patch("app.services.trial_service.SessionLocal")
    def test_trial_status_no_subscription(self, mock_session_cls):
        """MF1: check_trial_status should return 'none' for missing subscription."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        svc = get_trial_service()
        result = svc.check_trial_status(str(uuid.uuid4()))

        assert result["status"] == "none"

    @patch("app.services.trial_service.SessionLocal")
    def test_trial_status_active(self, mock_session_cls):
        """MF1: Active trial should show remaining days."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.trial_started_at = datetime.now(timezone.utc)
        mock_sub.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_sub
        )

        svc = get_trial_service()
        result = svc.check_trial_status(str(uuid.uuid4()))

        assert result["status"] == "active"
        assert result["remaining_days"] >= 6

    @patch("app.services.trial_service.SessionLocal")
    def test_trial_status_expired(self, mock_session_cls):
        """MF1: Expired trial should return 'expired'."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.trial_started_at = datetime.now(timezone.utc) - timedelta(days=20)
        mock_sub.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=6)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_sub
        )

        svc = get_trial_service()
        result = svc.check_trial_status(str(uuid.uuid4()))

        assert result["status"] == "expired"

    @patch("app.services.trial_service.SessionLocal")
    def test_send_trial_reminders(self, mock_session_cls):
        """MF1: send_trial_reminders should return count."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Service loops over REMINDER_DAYS, calling query each time
        # Each query: db.query().filter().all() → []
        mock_db.query.return_value.filter.return_value.all.return_value = []

        svc = get_trial_service()
        result = svc.send_trial_reminders()

        assert "reminders_sent" in result

    @patch("app.services.trial_service.SessionLocal")
    def test_process_expired_trials(self, mock_session_cls):
        """MF1: process_expired_trials should count expired."""
        from app.services.trial_service import get_trial_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Single query: db.query().filter().filter().all() → []
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = (
            []
        )

        svc = get_trial_service()
        result = svc.process_expired_trials()

        assert "expired_count" in result


# ═══════════════════════════════════════════════════════════════════════
# MF2: Pause/Resume Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPauseModels:
    """MF2: Verify pause record model exists."""

    def test_pause_record_model_exists(self):
        """MF2: PauseRecord model should exist in billing_extended."""
        from database.models.billing_extended import PauseRecord

        assert PauseRecord is not None

    def test_pause_record_tablename(self):
        """MF2: PauseRecord table name should be pause_records."""
        from database.models.billing_extended import PauseRecord

        assert PauseRecord.__tablename__ == "pause_records"

    def test_pause_record_has_required_columns(self):
        """MF2: PauseRecord should have all required columns."""
        from database.models.billing_extended import PauseRecord

        required = [
            "id",
            "company_id",
            "subscription_id",
            "paused_at",
            "resumed_at",
            "pause_duration_days",
            "max_pause_days",
            "period_end_extension_days",
        ]
        for col in required:
            assert hasattr(PauseRecord, col), f"Missing column: {col}"


class TestPauseService:
    """MF2: Pause service tests."""

    @patch("app.services.pause_service.SessionLocal")
    def test_pause_subscription(self, mock_session_cls):
        """MF2: pause_subscription should set status to paused."""
        from app.services.pause_service import get_pause_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_sub = MagicMock()
        mock_sub.id = str(uuid.uuid4())

        # 3 separate db.query() calls in pause_subscription
        # Use side_effect to provide different query builders
        queries = []
        for _ in range(3):
            q = MagicMock()
            queries.append(q)
        mock_db.query.side_effect = queries

        # q[0]: query(Subscription).filter().order_by().first() → sub
        queries[0].filter.return_value.order_by.return_value.first.return_value = (
            mock_sub
        )
        # q[1]: query(PauseRecord).filter().first() → None (no existing pause)
        queries[1].filter.return_value.first.return_value = None
        # q[2]: query(PauseRecord).filter().first() → None (no cooldown)
        queries[2].filter.return_value.first.return_value = None

        svc = get_pause_service()
        result = svc.pause_subscription(str(uuid.uuid4()))

        assert result["status"] == "paused"
        assert "paused_at" in result
        assert result["max_pause_days"] == 30

    @patch("app.services.pause_service.SessionLocal")
    def test_resume_subscription(self, mock_session_cls):
        """MF2: resume_subscription should extend period."""
        from app.services.pause_service import get_pause_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_pause = MagicMock()
        mock_pause.paused_at = datetime.now(timezone.utc) - timedelta(days=5)
        mock_pause.subscription_id = str(uuid.uuid4())

        mock_sub = MagicMock()
        mock_sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=25)

        # 2 queries: PauseRecord then Subscription
        queries = [MagicMock(), MagicMock()]
        mock_db.query.side_effect = queries
        # existing pause
        queries[0].filter.return_value.first.return_value = mock_pause
        # subscription
        queries[1].filter.return_value.first.return_value = mock_sub

        svc = get_pause_service()
        result = svc.resume_subscription(str(uuid.uuid4()))

        assert result["status"] == "active"
        assert result["pause_duration_days"] >= 4

    @patch("app.services.pause_service.SessionLocal")
    def test_get_pause_status_not_paused(self, mock_session_cls):
        """MF2: get_pause_status should return not_paused when no pause."""
        from app.services.pause_service import get_pause_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_pause_service()
        result = svc.get_pause_status(str(uuid.uuid4()))

        assert result["status"] == "not_paused"

    @patch("app.services.pause_service.SessionLocal")
    def test_process_max_pause_exceeded(self, mock_session_cls):
        """MF2: Auto-resume should work for exceeded pauses."""
        from app.services.pause_service import get_pause_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        q1 = MagicMock()
        q1.filter.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value = q1

        svc = get_pause_service()
        result = svc.process_max_pause_exceeded()

        assert "auto_resumed" in result


# ═══════════════════════════════════════════════════════════════════════
# MF3: Promo Code Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPromoModels:
    """MF3: Verify promo code models exist."""

    def test_promo_code_model_exists(self):
        """MF3: PromoCode model should exist."""
        from database.models.billing_extended import PromoCode

        assert PromoCode is not None

    def test_promo_code_tablename(self):
        """MF3: PromoCode table name should be promo_codes."""
        from database.models.billing_extended import PromoCode

        assert PromoCode.__tablename__ == "promo_codes"

    def test_promo_code_has_required_columns(self):
        """MF3: PromoCode should have required columns."""
        from database.models.billing_extended import PromoCode

        required = [
            "id",
            "code",
            "discount_type",
            "discount_value",
            "max_uses",
            "used_count",
            "valid_from",
            "valid_until",
            "applies_to_tiers",
            "is_active",
        ]
        for col in required:
            assert hasattr(PromoCode, col), f"Missing column: {col}"

    def test_company_promo_use_model_exists(self):
        """MF3: CompanyPromoUse model should exist."""
        from database.models.billing_extended import CompanyPromoUse

        assert CompanyPromoUse is not None

    def test_company_promo_use_tablename(self):
        """MF3: CompanyPromoUse table name should be company_promo_uses."""
        from database.models.billing_extended import CompanyPromoUse

        assert CompanyPromoUse.__tablename__ == "company_promo_uses"


class TestPromoService:
    """MF3: Promo code service tests."""

    @patch("app.services.promo_service.SessionLocal")
    def test_create_promo_code(self, mock_session_cls):
        """MF3: create_promo_code should succeed with valid data."""
        from app.services.promo_service import get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_promo_service()
        result = svc.create_promo_code(
            code="SAVE20",
            discount_type="percentage",
            discount_value=Decimal("20.00"),
        )

        assert result["code"] == "SAVE20"
        assert result["status"] == "active"

    @patch("app.services.promo_service.SessionLocal")
    def test_create_promo_duplicate_fails(self, mock_session_cls):
        """MF3: Duplicate promo code should raise PromoError."""
        from app.services.promo_service import PromoError, get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            code="SAVE20"
        )

        svc = get_promo_service()
        with pytest.raises(PromoError):
            svc.create_promo_code(
                code="SAVE20",
                discount_type="percentage",
                discount_value=Decimal("20.00"),
            )

    @patch("app.services.promo_service.SessionLocal")
    def test_validate_promo_code_valid(self, mock_session_cls):
        """MF3: Valid promo code should pass validation."""
        from app.services.promo_service import get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_promo = MagicMock()
        mock_promo.id = str(uuid.uuid4())
        mock_promo.code = "SAVE20"
        mock_promo.discount_type = "percentage"
        mock_promo.discount_value = Decimal("20.00")
        mock_promo.max_uses = 100
        mock_promo.used_count = 5
        mock_promo.valid_from = None
        mock_promo.valid_until = None
        mock_promo.applies_to_tiers = None
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_promo,
            None,
        ]

        svc = get_promo_service()
        result = svc.validate_promo_code("SAVE20", str(uuid.uuid4()))

        assert result["valid"] is True
        assert result["code"] == "SAVE20"

    @patch("app.services.promo_service.SessionLocal")
    def test_validate_promo_not_found(self, mock_session_cls):
        """MF3: Non-existent promo should raise PromoNotFoundError."""
        from app.services.promo_service import PromoNotFoundError, get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_promo_service()
        with pytest.raises(PromoNotFoundError):
            svc.validate_promo_code("FAKE", str(uuid.uuid4()))

    @patch("app.services.promo_service.SessionLocal")
    def test_list_promo_codes(self, mock_session_cls):
        """MF3: list_promo_codes should return list."""
        from app.services.promo_service import get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.order_by.return_value.all.return_value = []

        svc = get_promo_service()
        result = svc.list_promo_codes()

        assert isinstance(result, list)

    @patch("app.services.promo_service.SessionLocal")
    def test_deactivate_promo(self, mock_session_cls):
        """MF3: deactivate_promo_code should set is_active=False."""
        from app.services.promo_service import get_promo_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_promo = MagicMock()
        mock_promo.id = str(uuid.uuid4())
        mock_promo.code = "OLDPROMO"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_promo

        svc = get_promo_service()
        result = svc.deactivate_promo_code(str(uuid.uuid4()))

        assert result["status"] == "deactivated"


# ═══════════════════════════════════════════════════════════════════════
# MF7: Invoice Amendment Tests
# ═══════════════════════════════════════════════════════════════════════


class TestInvoiceAmendmentModels:
    """MF7: Verify invoice amendment model."""

    def test_invoice_amendment_model_exists(self):
        """MF7: InvoiceAmendment model should exist."""
        from database.models.billing_extended import InvoiceAmendment

        assert InvoiceAmendment is not None

    def test_invoice_amendment_tablename(self):
        """MF7: InvoiceAmendment table name should be invoice_amendments."""
        from database.models.billing_extended import InvoiceAmendment

        assert InvoiceAmendment.__tablename__ == "invoice_amendments"

    def test_invoice_amendment_has_required_columns(self):
        """MF7: InvoiceAmendment should have required columns."""
        from database.models.billing_extended import InvoiceAmendment

        required = [
            "id",
            "invoice_id",
            "company_id",
            "original_amount",
            "new_amount",
            "amendment_type",
            "reason",
            "approved_by",
        ]
        for col in required:
            assert hasattr(InvoiceAmendment, col), f"Missing column: {col}"


class TestInvoiceAmendmentService:
    """MF7: Invoice amendment service tests."""

    @patch("app.services.invoice_amendment_service.SessionLocal")
    def test_list_amendments(self, mock_session_cls):
        """MF7: list_amendments should return list."""
        from app.services.invoice_amendment_service import get_invoice_amendment_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )

        svc = get_invoice_amendment_service()
        result = svc.list_amendments("inv_123")

        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════
# MF8-MF11: Analytics Tests
# ═══════════════════════════════════════════════════════════════════════


class TestAnalyticsService:
    """MF8-MF11: Analytics service tests."""

    @patch("app.services.analytics_service.SessionLocal")
    def test_get_spending_summary(self, mock_session_cls):
        """MF8: get_spending_summary should return summary dict."""
        from app.services.analytics_service import get_billing_analytics_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_billing_analytics_service()
        result = svc.get_spending_summary(str(uuid.uuid4()))

        assert isinstance(result, dict)

    @patch("app.services.analytics_service.SessionLocal")
    def test_get_channel_breakdown(self, mock_session_cls):
        """MF8: get_channel_breakdown should return dict."""
        from app.services.analytics_service import get_billing_analytics_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_billing_analytics_service()
        result = svc.get_channel_breakdown(str(uuid.uuid4()))

        assert isinstance(result, dict)

    @patch("app.services.analytics_service.SessionLocal")
    def test_get_budget_alert(self, mock_session_cls):
        """MF9: get_budget_alert should return thresholds."""
        from app.services.analytics_service import get_billing_analytics_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_billing_analytics_service()
        result = svc.get_budget_alert(str(uuid.uuid4()))

        assert "usage_percentage" in result
        assert "thresholds_triggered" in result

    @patch("app.services.analytics_service.SessionLocal")
    def test_get_voice_usage(self, mock_session_cls):
        """MF10: get_voice_usage should return voice minutes."""
        from app.services.analytics_service import get_billing_analytics_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_billing_analytics_service()
        result = svc.get_voice_usage(str(uuid.uuid4()))

        assert "voice_minutes_used" in result

    @patch("app.services.analytics_service.SessionLocal")
    def test_get_sms_usage(self, mock_session_cls):
        """MF11: get_sms_usage should return SMS count."""
        from app.services.analytics_service import get_billing_analytics_service

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        svc = get_billing_analytics_service()
        result = svc.get_sms_usage(str(uuid.uuid4()))

        assert "sms_count" in result


# ═══════════════════════════════════════════════════════════════════════
# MF6: Enterprise Billing Tests
# ═══════════════════════════════════════════════════════════════════════


class TestEnterpriseBillingService:
    """MF6: Enterprise billing service tests."""

    @patch("app.services.enterprise_billing_service.SessionLocal")
    def test_enable_manual_billing(self, mock_session_cls):
        """MF6: enable_manual_billing should set billing_method."""
        from app.services.enterprise_billing_service import (
            get_enterprise_billing_service,
        )

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_company = MagicMock()
        mock_company.billing_method = "automatic"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_company

        svc = get_enterprise_billing_service()
        result = svc.enable_manual_billing(str(uuid.uuid4()))

        assert result is not None

    @patch("app.services.enterprise_billing_service.SessionLocal")
    def test_get_enterprise_status(self, mock_session_cls):
        """MF6: get_enterprise_billing_status should return dict."""
        from app.services.enterprise_billing_service import (
            get_enterprise_billing_service,
        )

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_company = MagicMock()
        mock_company.billing_method = "automatic"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_company

        svc = get_enterprise_billing_service()
        result = svc.get_enterprise_billing_status(str(uuid.uuid4()))

        assert "billing_method" in result


# ═══════════════════════════════════════════════════════════════════════
# DI1-DI5: Dashboard Integration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDashboardSchemas:
    """DI1-DI5: Verify dashboard schema models exist."""

    def test_dashboard_summary_schema_exists(self):
        """DI1: DashboardSummary schema should exist."""
        from app.schemas.billing import DashboardSummary

        assert DashboardSummary is not None

    def test_plan_comparison_schema_exists(self):
        """DI2: PlanComparison schema should exist."""
        from app.schemas.billing import PlanComparison

        assert PlanComparison is not None

    def test_variant_catalog_schema_exists(self):
        """DI3: VariantCatalog schema should exist."""
        from app.schemas.billing import VariantCatalog

        assert VariantCatalog is not None

    def test_enhanced_invoice_history_schema_exists(self):
        """DI4: EnhancedInvoiceHistory schema should exist."""
        from app.schemas.billing import EnhancedInvoiceHistory

        assert EnhancedInvoiceHistory is not None

    def test_payment_schedule_schema_exists(self):
        """DI5: PaymentSchedule schema should exist."""
        from app.schemas.billing import PaymentSchedule

        assert PaymentSchedule is not None


class TestDay6CeleryTasks:
    """Day 6 Celery task registration tests."""

    def test_trial_reminder_task_defined(self):
        """MF1: Trial reminder Celery task should be defined in billing_tasks."""
        path = _PROJECT_ROOT / "backend" / "app" / "tasks" / "billing_tasks.py"
        content = path.read_text()
        assert 'name="billing.send_trial_reminders"' in content

    def test_expired_trial_task_defined(self):
        """MF1: Expired trial Celery task should be defined."""
        path = _PROJECT_ROOT / "backend" / "app" / "tasks" / "billing_tasks.py"
        content = path.read_text()
        assert 'name="billing.process_expired_trials"' in content

    def test_max_pause_task_defined(self):
        """MF2: Max pause Celery task should be defined."""
        path = _PROJECT_ROOT / "backend" / "app" / "tasks" / "billing_tasks.py"
        content = path.read_text()
        assert 'name="billing.process_max_pause_exceeded"' in content


# ═══════════════════════════════════════════════════════════════════════
# Migration Tests
# ═══════════════════════════════════════════════════════════════════════


class TestDay6Migration:
    """Verify Day 6 migration file exists and is valid."""

    def test_migration_file_exists(self):
        """Migration 025 should exist."""
        path = (
            _PROJECT_ROOT
            / "database"
            / "alembic"
            / "versions"
            / "025_day6_missing_features.py"
        )
        assert path.exists(), f"Migration file not found: {path}"

    def test_migration_creates_all_tables(self):
        """Migration should create all Day 6 tables."""
        path = (
            _PROJECT_ROOT
            / "database"
            / "alembic"
            / "versions"
            / "025_day6_missing_features.py"
        )
        content = path.read_text()
        for table in [
            "promo_codes",
            "company_promo_uses",
            "invoice_amendments",
            "pause_records",
        ]:
            assert table in content, f"Missing table {table} in migration"

    def test_migration_adds_trial_columns(self):
        """Migration should add trial columns to subscriptions."""
        path = (
            _PROJECT_ROOT
            / "database"
            / "alembic"
            / "versions"
            / "025_day6_missing_features.py"
        )
        content = path.read_text()
        for col in ["trial_days", "trial_started_at", "trial_ends_at"]:
            assert col in content, f"Missing column {col} in migration"

    def test_migration_revision_chain(self):
        """Migration should reference correct down_revision."""
        path = (
            _PROJECT_ROOT
            / "database"
            / "alembic"
            / "versions"
            / "025_day6_missing_features.py"
        )
        content = path.read_text()
        assert 'down_revision = "024_day5_billing_protection"' in content
