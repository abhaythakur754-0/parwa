"""Day 22 loophole tests (L65-L68)."""

import os


# ── L65: Company.is_active doesn't exist ──────────────────────────

class TestL65CompanyIsActive:
    def test_company_model_has_no_is_active(self):
        from database.models.core import Company
        assert not hasattr(Company, "is_active")

    def test_company_model_has_subscription_status(self):
        from database.models.core import Company
        assert hasattr(Company, "subscription_status")

    def test_periodic_uses_correct_import(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "backend", "app", "tasks", "periodic.py")
        with open(path) as f:
            content = f.read()
        assert "from database.models.companies" not in content
        assert "from database.models.core import Company" in content

    def test_periodic_uses_subscription_status(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, "backend", "app", "tasks", "periodic.py")
        with open(path) as f:
            content = f.read()
        assert 'subscription_status == "active"' in content

    def test_company_subscription_status_default_is_active(self):
        from database.models.core import Company
        default_val = Company.subscription_status.property.columns[0].default
        assert default_val.arg == "active"


# ── L66: Exponential backoff ──────────────────────────────────────

class TestL66ExponentialBackoff:
    def test_base_task_has_retry_backoff(self):
        from backend.app.tasks.base import ParwaBaseTask
        assert ParwaBaseTask.retry_backoff is True

    def test_base_task_has_jitter(self):
        from backend.app.tasks.base import ParwaBaseTask
        assert ParwaBaseTask.retry_jitter is True

    def test_base_task_has_max_backoff(self):
        from backend.app.tasks.base import ParwaBaseTask
        assert ParwaBaseTask.retry_backoff_max == 300

    def test_base_task_max_retries_is_3(self):
        from backend.app.tasks.base import ParwaBaseTask
        assert ParwaBaseTask.max_retries == 3


# ── L67: Time limits ──────────────────────────────────────────────

class TestL67TimeLimits:
    def test_all_tasks_have_time_limits(self):
        from tests.unit.test_day22_setup import setup_day22_tests
        setup_day22_tests()
        from backend.app.tasks.email_tasks import (
            send_email, render_template, send_bulk_notification,
        )
        from backend.app.tasks.analytics_tasks import (
            aggregate_metrics, calculate_roi, drift_detection,
        )
        from backend.app.tasks.ai_tasks import (
            classify_ticket, generate_response, score_confidence,
        )
        from backend.app.tasks.training_tasks import (
            prepare_dataset, check_mistake_threshold, schedule_training,
        )
        from backend.app.tasks.approval_tasks import (
            approval_timeout_check, approval_reminder, batch_process,
        )
        from backend.app.tasks.billing_tasks import (
            daily_overage_charge, invoice_sync, subscription_check,
        )
        tasks = [
            send_email, render_template, send_bulk_notification,
            aggregate_metrics, calculate_roi, drift_detection,
            classify_ticket, generate_response, score_confidence,
            prepare_dataset, check_mistake_threshold, schedule_training,
            approval_timeout_check, approval_reminder, batch_process,
            daily_overage_charge, invoice_sync, subscription_check,
        ]
        for task in tasks:
            assert task.soft_time_limit < task.time_limit, (
                f"{task.name}: soft={task.soft_time_limit} not < hard={task.time_limit}"
            )

    def test_heavy_tasks_have_higher_limits(self):
        from tests.unit.test_day22_setup import setup_day22_tests
        setup_day22_tests()
        from backend.app.tasks.email_tasks import send_email
        from backend.app.tasks.ai_tasks import generate_response
        assert generate_response.time_limit > send_email.time_limit

    def test_bulk_notification_has_highest_email_limit(self):
        from tests.unit.test_day22_setup import setup_day22_tests
        setup_day22_tests()
        from backend.app.tasks.email_tasks import (
            send_email, render_template, send_bulk_notification,
        )
        assert send_bulk_notification.time_limit > send_email.time_limit
        assert send_bulk_notification.time_limit > render_template.time_limit


# ── L68: No mutable state ─────────────────────────────────────────

class TestL68NoMutableState:
    def test_approval_constants_are_immutable(self):
        from backend.app.tasks.approval_tasks import (
            APPROVAL_TIMEOUT_HOURS,
            APPROVAL_REMINDER_INTERVAL_HOURS,
        )
        assert isinstance(APPROVAL_TIMEOUT_HOURS, int)
        assert isinstance(APPROVAL_REMINDER_INTERVAL_HOURS, int)

    def test_no_global_counters_in_tasks(self):
        import os
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        task_files = [
            "email_tasks.py",
            "analytics_tasks.py",
            "ai_tasks.py",
            "training_tasks.py",
            "approval_tasks.py",
            "billing_tasks.py",
        ]
        for fname in task_files:
            path = os.path.join(base, "backend", "app", "tasks", fname)
            with open(path) as f:
                content = f.read()
            assert "global " not in content, f"{fname} contains mutable global state"

    def test_no_module_level_lists_in_tasks(self):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        task_files = [
            "email_tasks.py",
            "analytics_tasks.py",
            "ai_tasks.py",
            "training_tasks.py",
            "approval_tasks.py",
            "billing_tasks.py",
        ]
        for fname in task_files:
            path = os.path.join(base, "backend", "app", "tasks", fname)
            with open(path) as f:
                content = f.read()
            lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith(("#", '"""', "'''", "import", "from"))]
            for line in lines:
                assert not line.startswith("results = ["), f"{fname} has mutable list: {line}"
                assert not line.startswith("cache = {"), f"{fname} has mutable dict: {line}"

    def test_constants_are_toplevel_integers(self):
        from backend.app.tasks.approval_tasks import (
            APPROVAL_TIMEOUT_HOURS,
            APPROVAL_REMINDER_INTERVAL_HOURS,
        )
        assert APPROVAL_TIMEOUT_HOURS > 0
        assert APPROVAL_REMINDER_INTERVAL_HOURS > 0
        assert APPROVAL_TIMEOUT_HOURS == 72
        assert APPROVAL_REMINDER_INTERVAL_HOURS == 24
