"""Tests for Day 22 billing tasks."""

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.billing_tasks import (  # noqa: E402
    daily_overage_charge,
    invoice_sync,
    subscription_check,
)


class TestDailyOverageCharge:
    def test_returns_dict_on_success(self):
        result = daily_overage_charge("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_checked(self):
        result = daily_overage_charge("company-123")
        assert result["status"] == "checked"

    def test_return_has_company_id(self):
        result = daily_overage_charge("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_date(self):
        result = daily_overage_charge("company-123")
        assert "date" in result

    def test_date_format_is_iso(self):
        result = daily_overage_charge("company-123")
        date_str = result["date"]
        assert len(date_str) == 10
        assert date_str[4] == "-"
        assert date_str[7] == "-"

    def test_return_has_overage_amount(self):
        result = daily_overage_charge("company-123")
        assert "overage_amount" in result

    def test_return_has_charged(self):
        result = daily_overage_charge("company-123")
        assert "charged" in result

    def test_charged_is_bool(self):
        result = daily_overage_charge("company-123")
        assert isinstance(result["charged"], bool)

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
    def test_returns_dict_on_success(self):
        result = invoice_sync("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_synced(self):
        result = invoice_sync("company-123")
        assert result["status"] == "synced"

    def test_return_has_company_id(self):
        result = invoice_sync("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_invoices_synced(self):
        result = invoice_sync("company-123")
        assert "invoices_synced" in result

    def test_return_has_new_invoices(self):
        result = invoice_sync("company-123")
        assert "new_invoices" in result

    def test_invoices_synced_is_int(self):
        result = invoice_sync("company-123")
        assert isinstance(result["invoices_synced"], int)

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
    def test_returns_dict_on_success(self):
        result = subscription_check("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_active(self):
        result = subscription_check("company-123")
        assert result["status"] == "active"

    def test_return_has_company_id(self):
        result = subscription_check("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_plan(self):
        result = subscription_check("company-123")
        assert "plan" in result

    def test_return_has_valid_until(self):
        result = subscription_check("company-123")
        assert "valid_until" in result

    def test_default_plan_is_free(self):
        result = subscription_check("company-123")
        assert result["plan"] == "free"

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
