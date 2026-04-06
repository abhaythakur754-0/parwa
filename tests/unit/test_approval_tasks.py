"""Tests for Day 22 approval tasks."""

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.approval_tasks import (  # noqa: E402
    approval_timeout_check,
    approval_reminder,
    batch_process,
    APPROVAL_TIMEOUT_HOURS,
    APPROVAL_REMINDER_INTERVAL_HOURS,
)


class TestApprovalTimeoutCheck:
    def test_returns_dict_on_success(self):
        result = approval_timeout_check("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_checked(self):
        result = approval_timeout_check("company-123")
        assert result["status"] == "checked"

    def test_return_has_company_id(self):
        result = approval_timeout_check("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_timed_out_count(self):
        result = approval_timeout_check("company-123")
        assert "timed_out_count" in result

    def test_return_has_auto_rejected(self):
        result = approval_timeout_check("company-123")
        assert "auto_rejected" in result

    def test_queue_is_default(self):
        assert approval_timeout_check.queue == "default"

    def test_max_retries_is_3(self):
        assert approval_timeout_check.max_retries == 3

    def test_soft_time_limit(self):
        assert approval_timeout_check.soft_time_limit == 60

    def test_time_limit(self):
        assert approval_timeout_check.time_limit == 120

    def test_task_name_registered(self):
        assert "approval.timeout_check" in approval_timeout_check.name

    def test_auto_rejected_is_int(self):
        result = approval_timeout_check("c1")
        assert isinstance(result["auto_rejected"], int)


class TestApprovalReminder:
    def test_returns_dict_on_success(self):
        result = approval_reminder("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_completed(self):
        result = approval_reminder("company-123")
        assert result["status"] == "completed"

    def test_return_has_company_id(self):
        result = approval_reminder("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_reminders_sent(self):
        result = approval_reminder("company-123")
        assert "reminders_sent" in result

    def test_reminders_sent_is_int(self):
        result = approval_reminder("company-123")
        assert isinstance(result["reminders_sent"], int)

    def test_queue_is_default(self):
        assert approval_reminder.queue == "default"

    def test_max_retries_is_3(self):
        assert approval_reminder.max_retries == 3

    def test_soft_time_limit(self):
        assert approval_reminder.soft_time_limit == 60

    def test_time_limit(self):
        assert approval_reminder.time_limit == 120

    def test_task_name_registered(self):
        assert "approval.reminder" in approval_reminder.name


class TestBatchProcess:
    def test_returns_dict_on_success(self):
        result = batch_process("company-123", ["apr-1", "apr-2"])
        assert isinstance(result, dict)

    def test_return_has_status_completed(self):
        result = batch_process("company-123", ["apr-1"])
        assert result["status"] == "completed"

    def test_return_has_action(self):
        result = batch_process("company-123", ["apr-1"], action="reject")
        assert result["action"] == "reject"

    def test_return_has_total(self):
        result = batch_process("company-123", ["a", "b", "c"])
        assert result["total"] == 3

    def test_return_has_processed(self):
        result = batch_process("company-123", ["a", "b"])
        assert result["processed"] == 2

    def test_return_has_skipped(self):
        result = batch_process("company-123", ["a"])
        assert "skipped" in result

    def test_default_action_is_approve(self):
        result = batch_process("company-123", ["a"])
        assert result["action"] == "approve"

    def test_queue_is_default(self):
        assert batch_process.queue == "default"

    def test_max_retries_is_2(self):
        assert batch_process.max_retries == 2

    def test_soft_time_limit(self):
        assert batch_process.soft_time_limit == 120

    def test_time_limit(self):
        assert batch_process.time_limit == 300

    def test_task_name_registered(self):
        assert "approval.batch_process" in batch_process.name

    def test_empty_list(self):
        result = batch_process("c1", [])
        assert result["total"] == 0


class TestApprovalConstants:
    def test_timeout_hours_is_72(self):
        assert APPROVAL_TIMEOUT_HOURS == 72

    def test_reminder_interval_is_24(self):
        assert APPROVAL_REMINDER_INTERVAL_HOURS == 24
