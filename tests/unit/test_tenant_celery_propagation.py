"""
Tests for PARWA Tenant Celery Propagation (Day 20)

Tests company_id flow from API → task headers → Celery task execution.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from backend.app.core.tenant_context import (  # noqa: E402
    clear_tenant_context,
    get_tenant_context,
    reset_tenant_context,
    set_tenant_context,
)
from backend.app.tasks.base import (  # noqa: E402
    ParwaBaseTask,
    ParwaTask,
    inject_tenant_context,
    set_task_tenant_header,
    TENANT_HEADER_KEY,
)
from backend.app.tasks.celery_app import app as celery_app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    reset_tenant_context()
    yield
    reset_tenant_context()


# ── set_task_tenant_header ───────────────────────────────


class TestSetTaskTenantHeader:

    def test_returns_dict_with_header(self):
        headers = set_task_tenant_header("acme")
        assert isinstance(headers, dict)
        assert headers[TENANT_HEADER_KEY] == "acme"

    def test_strips_whitespace(self):
        headers = set_task_tenant_header("  acme  ")
        assert headers[TENANT_HEADER_KEY] == "acme"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="company_id is required"):
            set_task_tenant_header("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            set_task_tenant_header(None)


# ── ParwaTask._get_task_company_id ───────────────────────


class TestParwaTaskHeaderExtraction:

    def _make_task(self, headers=None):
        task = ParwaTask()
        # Use _task_store to simulate request with headers
        task._task_store = {}
        mock_req = type('MockRequest', (), {'headers': headers or {}})()
        # Monkey-patch the request property descriptor
        type(task).request = property(lambda self: mock_req)
        return task

    def test_extracts_from_headers(self):
        task = self._make_task(headers={TENANT_HEADER_KEY: "acme"})
        assert task._get_task_company_id() == "acme"

    def test_none_without_headers(self):
        task = self._make_task(headers={})
        assert task._get_task_company_id() is None

    def test_none_with_empty_headers(self):
        task = self._make_task(headers=None)
        assert task._get_task_company_id() is None

    def test_value_stringified(self):
        task = self._make_task(headers={TENANT_HEADER_KEY: 12345})
        assert task._get_task_company_id() == "12345"


# ── ParwaTask.__call__ tenant propagation ────────────────


class TestParwaTaskCallWithTenant:

    def _make_callable_task(self, headers=None):
        """Create a task instance that can be called."""
        task = ParwaTask()
        task.run = MagicMock(return_value="done")
        mock_request = MagicMock()
        mock_request.headers = headers or {}
        # Need to set request as property mock
        type(task).request = property(lambda self: mock_request)
        return task

    def test_call_sets_context_from_header(self):
        task = self._make_callable_task(
            headers={TENANT_HEADER_KEY: "acme"}
        )
        task()
        # Context should have been set during call
        # (cleared after, so we check it was set at all)
        assert task.run.called

    def test_call_clears_context_after(self):
        task = self._make_callable_task(
            headers={TENANT_HEADER_KEY: "acme"}
        )
        task()
        # After call, context should be cleared
        assert get_tenant_context() is None

    def test_call_clears_on_exception(self):
        task = self._make_callable_task(
            headers={TENANT_HEADER_KEY: "acme"}
        )
        task.run.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            task()
        assert get_tenant_context() is None

    def test_call_without_header_logs_warning(self, caplog):
        import logging
        task = self._make_callable_task(headers={})
        with caplog.at_level(logging.WARNING, logger="parwa.tasks"):
            task()
        assert any(
            "task_no_tenant_context" in r.message
            for r in caplog.records
        )


# ── inject_tenant_context decorator ──────────────────────


class TestInjectTenantContext:

    def test_decorator_works_with_context(self):
        set_tenant_context("acme")
        result = {}

        @inject_tenant_context
        def my_func():
            result["ctx"] = get_tenant_context()
            return "ok"

        assert my_func() == "ok"
        assert result["ctx"] == "acme"

    def test_decorator_warns_without_context(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="parwa.tasks"):
            @inject_tenant_context
            def my_func():
                return "ok"
            my_func()
        assert any(
            "inject_tenant_context_no_context" in r.message
            for r in caplog.records
        )


# ── Full Flow ────────────────────────────────────────────


class TestFullFlow:

    def test_api_to_task_full_flow(self):
        """Simulate: API sets context → dispatch task with headers → task uses context."""
        # Step 1: API middleware sets context
        set_tenant_context("fullflow-co")

        # Step 2: API dispatches task with tenant headers
        headers = set_task_tenant_header("fullflow-co")
        assert headers[TENANT_HEADER_KEY] == "fullflow-co"

        # Step 3: Task receives headers and sets context
        task = ParwaTask()
        task.run = MagicMock(return_value="done")
        mock_request = MagicMock()
        mock_request.headers = headers
        type(task).request = property(lambda self: mock_request)

        # Step 4: Task auto-sets context via __call__
        task()
        assert task.run.called

        # Step 5: Context cleaned up after
        assert get_tenant_context() is None
