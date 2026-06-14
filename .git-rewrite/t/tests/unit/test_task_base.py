"""
Tests for PARWA Task Base Classes (BC-004)

Tests verify base task classes, decorators, and example tasks
without requiring a running Celery worker or Redis broker.
"""

import logging

import pytest


class TestParwaTaskBaseClass:
    """Test that ParwaBaseTask can be inherited."""

    def test_parwa_task_base_class(self):
        """ParwaBaseTask is a valid base class for Celery tasks."""
        from backend.app.tasks.base import ParwaBaseTask

        # Create a concrete task class inheriting from ParwaBaseTask
        class TestTask(ParwaBaseTask):
            name = "test.task"

            def run(self, company_id: str):
                return {"company_id": company_id}

        task = TestTask()
        assert task.name == "test.task"
        assert task.queue == "default"


class TestTaskDefaultRetryConfig:
    """Test default retry configuration (BC-004)."""

    def test_task_default_retry_config(self):
        """ParwaBaseTask has correct default retry settings."""
        from backend.app.tasks.base import ParwaBaseTask

        assert ParwaBaseTask.autoretry_for == (Exception,)
        assert ParwaBaseTask.max_retries == 3
        assert ParwaBaseTask.retry_backoff is True
        assert ParwaBaseTask.retry_backoff_max == 300
        assert ParwaBaseTask.queue == "default"
        assert ParwaBaseTask.retry_jitter is True


class TestWithCompanyIdDecorator:
    """Test the @with_company_id decorator (BC-001)."""

    def test_with_company_id_decorator(self):
        """Decorator validates company_id and passes it through."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str, foo: str):
            return {"company_id": company_id, "foo": foo}

        result = my_task("comp_abc123", "bar")
        assert result == {"company_id": "comp_abc123", "foo": "bar"}

    def test_with_company_id_invalid_empty(self):
        """Decorator rejects empty company_id (BC-001)."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str):
            return {"ok": True}

        with pytest.raises(ValueError, match="non-empty string"):
            my_task("")

    def test_with_company_id_invalid_whitespace(self):
        """Decorator rejects whitespace-only company_id (BC-001)."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str):
            return {"ok": True}

        with pytest.raises(ValueError, match="non-empty string"):
            my_task("   ")

    def test_with_company_id_invalid_type(self):
        """Decorator rejects non-string company_id (BC-001)."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str):
            return {"ok": True}

        with pytest.raises(ValueError, match="non-empty string"):
            my_task(123)  # type: ignore[arg-type]

    def test_with_company_id_missing(self):
        """Decorator rejects missing company_id (BC-001)."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str):
            return {"ok": True}

        with pytest.raises(ValueError, match="required as the first"):
            my_task()

    def test_with_company_id_with_kwargs(self):
        """Decorator works when company_id is first positional arg."""
        from backend.app.tasks.base import with_company_id

        @with_company_id
        def my_task(company_id: str, extra: str = "default"):
            return {"company_id": company_id, "extra": extra}

        result = my_task("comp_xyz", extra="custom")
        assert result == {
            "company_id": "comp_xyz",
            "extra": "custom",
        }


class TestTaskLifecycleLogging:
    """Test task lifecycle logging (BC-012)."""

    def test_task_failure_logging(self, caplog):
        """on_failure logs error without stack traces (BC-012)."""
        from backend.app.tasks.base import ParwaBaseTask

        class FailTask(ParwaBaseTask):
            name = "test.fail_task"

        task = FailTask()
        exc = RuntimeError("test error")

        with caplog.at_level(logging.ERROR, logger="parwa.tasks"):
            task.on_failure(
                exc=exc,
                traceback=None,
                args=("comp_123",),
                kwargs={},
                einfo=None,
            )

        assert len(caplog.records) >= 1
        log_record = caplog.records[0]
        assert log_record.task_name == "test.fail_task"
        assert log_record.error_type == "RuntimeError"
        assert log_record.error_message == "test error"
        assert log_record.company_id == "comp_123"

    def test_task_success_logging(self, caplog):
        """on_success logs completion with company_id."""
        from backend.app.tasks.base import ParwaBaseTask

        class SuccessTask(ParwaBaseTask):
            name = "test.success_task"

        task = SuccessTask()

        with caplog.at_level(logging.INFO, logger="parwa.tasks"):
            task.on_success(
                retval={"status": "ok"},
                task_id="test-id-123",
                args=("comp_456",),
                kwargs={},
            )

        assert len(caplog.records) >= 1
        log_record = caplog.records[0]
        assert log_record.task_name == "test.success_task"
        assert log_record.company_id == "comp_456"

    def test_task_retry_logging(self, caplog):
        """on_retry logs retry with structured context."""
        from backend.app.tasks.base import ParwaBaseTask

        class RetryTask(ParwaBaseTask):
            name = "test.retry_task"

        task = RetryTask()
        exc = ConnectionError("retry me")

        with caplog.at_level(logging.WARNING, logger="parwa.tasks"):
            task.on_retry(
                exc=exc,
                traceback=None,
                eta=None,
            )

        assert len(caplog.records) >= 1
        log_record = caplog.records[0]
        assert log_record.task_name == "test.retry_task"
        assert log_record.error_type == "ConnectionError"


class TestExampleTasks:
    """Test that example tasks are registered and configured."""

    def test_example_tasks_defined(self):
        """Example tasks are defined and have correct names."""
        from backend.app.tasks.example_tasks import (
            calculate_analytics_task,
            process_webhook_task,
            send_welcome_email_task,
        )

        # Verify tasks are callable
        assert callable(send_welcome_email_task)
        assert callable(process_webhook_task)
        assert callable(calculate_analytics_task)

        # Verify they have the correct registered task names
        assert send_welcome_email_task.name == (
            "backend.app.tasks.email.send_welcome_email"
        )
        assert process_webhook_task.name == (
            "backend.app.tasks.webhook.process_webhook"
        )
        assert calculate_analytics_task.name == (
            "backend.app.tasks.analytics.calculate_analytics"
        )

    def test_email_task_queue(self):
        """send_welcome_email_task routes to 'email' queue."""
        from backend.app.tasks.example_tasks import (
            send_welcome_email_task,
        )
        assert send_welcome_email_task.queue == "email"

    def test_webhook_task_queue(self):
        """process_webhook_task routes to 'webhook' queue."""
        from backend.app.tasks.example_tasks import (
            process_webhook_task,
        )
        assert process_webhook_task.queue == "webhook"

    def test_analytics_task_queue(self):
        """calculate_analytics_task routes to 'analytics' queue."""
        from backend.app.tasks.example_tasks import (
            calculate_analytics_task,
        )
        assert calculate_analytics_task.queue == "analytics"
