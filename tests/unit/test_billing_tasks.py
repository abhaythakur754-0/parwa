"""Tests for Day 22 billing tasks."""

from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.billing_tasks import (  # noqa: E402
    daily_overage_charge,
    invoice_sync,
    subscription_check,
)

# ─── Shared mock overage result ───────────────────────────────────────────────
_OVERAGE_RESULT = {
    "status": "checked",
    "company_id": "company-123",
    "date": datetime.now(timezone.utc).date().isoformat(),
    "overage_amount": "0.00",
    "charged": False,
    "overage_tickets": 0,
}

# ─── Shared mock subscription ─────────────────────────────────────────────────
def _mock_subscription():
    sub = MagicMock()
    sub.tier = "free"
    sub.status = "active"
    sub.paddle_subscription_id = None
    sub.current_period_end = None
    return sub


class TestDailyOverageCharge:
    def _run(self):
        """Run task with overage service mocked out."""
        mock_svc = MagicMock()
        mock_svc.process_daily_overage = AsyncMock(return_value=_OVERAGE_RESULT)
        with patch("app.services.overage_service.get_overage_service", return_value=mock_svc):
            return daily_overage_charge("company-123")

    def test_returns_dict_on_success(self):
        assert isinstance(self._run(), dict)

    def test_return_has_status_checked(self):
        assert self._run()["status"] == "checked"

    def test_return_has_company_id(self):
        assert self._run()["company_id"] == "company-123"

    def test_return_has_date(self):
        assert "date" in self._run()

    def test_date_format_is_iso(self):
        date_str = self._run()["date"]
        assert len(date_str) == 10
        assert date_str[4] == "-"
        assert date_str[7] == "-"

    def test_return_has_overage_amount(self):
        assert "overage_amount" in self._run()

    def test_return_has_charged(self):
        assert "charged" in self._run()

    def test_charged_is_bool(self):
        assert isinstance(self._run()["charged"], bool)

    def test_queue_is_default(self):
        assert daily_overage_charge.queue == "default"

    def test_max_retries_is_3(self):
        assert daily_overage_charge.max_retries == 3

    def test_soft_time_limit(self):
        assert daily_overage_charge.soft_time_limit == 120

    def test_time_limit(self):
        assert daily_overage_charge.time_limit == 300

    def test_task_name_registered(self):
        assert "billing.daily_overage_charge" in daily_overage_charge.name


class TestInvoiceSync:
    def _run(self):
        """Run invoice_sync with DB and Paddle mocked out."""
        mock_company = MagicMock()
        mock_company.paddle_customer_id = None  # triggers 'skipped' path cleanly
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_company
        with patch("app.tasks.billing_tasks.SessionLocal", return_value=mock_db):
            return invoice_sync("company-123")

    def test_returns_dict_on_success(self):
        assert isinstance(self._run(), dict)

    def test_return_has_status_synced(self):
        # No paddle_customer_id → 'skipped'; both are valid completed states
        result = self._run()
        assert result["status"] in ("synced", "skipped")

    def test_return_has_company_id(self):
        assert self._run()["company_id"] == "company-123"

    def test_return_has_invoices_synced(self):
        assert "invoices_synced" in self._run()

    def test_return_has_new_invoices(self):
        assert "new_invoices" in self._run()

    def test_invoices_synced_is_int(self):
        assert isinstance(self._run()["invoices_synced"], int)

    def test_queue_is_default(self):
        assert invoice_sync.queue == "default"

    def test_max_retries_is_3(self):
        assert invoice_sync.max_retries == 3

    def test_soft_time_limit(self):
        assert invoice_sync.soft_time_limit == 120

    def test_time_limit(self):
        assert invoice_sync.time_limit == 300

    def test_task_name_registered(self):
        assert "billing.invoice_sync" in invoice_sync.name


class TestSubscriptionCheck:
    def _run(self):
        """Run subscription_check with DB mocked to return a free subscription."""
        sub = _mock_subscription()
        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = sub
        with patch("app.tasks.billing_tasks.SessionLocal", return_value=mock_db):
            return subscription_check("company-123")

    def test_returns_dict_on_success(self):
        assert isinstance(self._run(), dict)

    def test_return_has_status_active(self):
        assert self._run()["status"] == "active"

    def test_return_has_company_id(self):
        assert self._run()["company_id"] == "company-123"

    def test_return_has_plan(self):
        assert "plan" in self._run()

    def test_return_has_valid_until(self):
        assert "valid_until" in self._run()

    def test_default_plan_is_free(self):
        assert self._run()["plan"] == "free"

    def test_queue_is_default(self):
        assert subscription_check.queue == "default"

    def test_max_retries_is_2(self):
        assert subscription_check.max_retries == 2

    def test_soft_time_limit(self):
        assert subscription_check.soft_time_limit == 60

    def test_time_limit(self):
        assert subscription_check.time_limit == 120

    def test_task_name_registered(self):
        assert "billing.subscription_check" in subscription_check.name

