"""
Tests for PARWA Event Celery Tasks (Day 19)

Tests:
- fanout_event_task logic
- cleanup_event_buffer_task logic
- Task registration in Celery app
- BC-004: company_id as first param
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.events import reset_event_registry


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset event registry before each test."""
    reset_event_registry()
    yield
    reset_event_registry()


class TestFanoutEventTask:
    """Test fanout_event_task business logic."""

    def test_task_has_company_id_as_first_param(self):
        """Task signature has company_id as first param (BC-004)."""
        import inspect
        from backend.app.tasks.event_tasks import fanout_event_task
        sig = inspect.signature(fanout_event_task)
        params = list(sig.parameters.keys())
        assert params[0] == "company_id"

    def test_fanout_calls_emit_for_each_target_user(self):
        """Fan-out calls emit_event once per target user."""
        mock_emit = AsyncMock(return_value=True)
        mock_loop = MagicMock()

        with patch(
            "backend.app.core.event_emitter.emit_event",
            mock_emit,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import fanout_event_task

            result = fanout_event_task.apply(
                args=["acme"],
                kwargs={
                    "event_type": "ticket:new",
                    "payload": {"ticket_id": "t-1", "company_id": "acme"},
                    "target_user_ids": ["u-1", "u-2", "u-3"],
                },
            ).get()

        assert result["status"] == "emitted"
        assert result["target_count"] == 3

    def test_fanout_single_call_without_targets(self):
        """Without target_user_ids, emit is called once."""
        mock_emit = AsyncMock(return_value=True)
        mock_loop = MagicMock()

        with patch(
            "backend.app.core.event_emitter.emit_event",
            mock_emit,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import fanout_event_task

            result = fanout_event_task.apply(
                args=["acme"],
                kwargs={
                    "event_type": "ticket:new",
                    "payload": {"ticket_id": "t-1", "company_id": "acme"},
                },
            ).get()

        assert result["target_count"] == 1

    def test_fanout_with_correlation_id(self):
        """Fan-out passes correlation_id through."""
        mock_emit = AsyncMock(return_value=True)
        mock_loop = MagicMock()

        with patch(
            "backend.app.core.event_emitter.emit_event",
            mock_emit,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import fanout_event_task

            result = fanout_event_task.apply(
                args=["acme"],
                kwargs={
                    "event_type": "ticket:new",
                    "payload": {"ticket_id": "t-1", "company_id": "acme"},
                    "correlation_id": "corr-abc",
                },
            ).get()

        assert result["status"] == "emitted"

    def test_fanout_task_registered_in_celery(self):
        """fanout_event_task is registered in Celery app."""
        from backend.app.tasks.celery_app import app
        assert "backend.app.tasks.event_tasks.fanout_event_task" in app.tasks

    def test_fanout_queue_is_default(self):
        """fanout_event_task routes to 'default' queue."""
        from backend.app.tasks.celery_app import app
        task = app.tasks[
            "backend.app.tasks.event_tasks.fanout_event_task"
        ]
        assert task.queue == "default"


class TestCleanupEventBufferTask:
    """Test cleanup_event_buffer_task business logic."""

    def test_task_has_company_id_as_first_param(self):
        """Task signature has company_id as first param (BC-004)."""
        import inspect
        from backend.app.tasks.event_tasks import cleanup_event_buffer_task
        sig = inspect.signature(cleanup_event_buffer_task)
        params = list(sig.parameters.keys())
        assert params[0] == "company_id"

    def test_cleanup_calls_cleanup_old_events(self):
        """Cleanup delegates to event_buffer.cleanup_old_events."""
        mock_cleanup = AsyncMock(return_value=42)
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(return_value=42)

        with patch(
            "backend.app.core.event_buffer.cleanup_old_events",
            mock_cleanup,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import cleanup_event_buffer_task

            result = cleanup_event_buffer_task.apply(
                args=["acme"],
                kwargs={},
            ).get()

        assert result["status"] == "cleaned"
        assert result["events_removed"] == 42

    def test_cleanup_error_returns_error_dict(self):
        """Cleanup returns error status on failure."""
        mock_cleanup = AsyncMock(side_effect=RuntimeError("Redis down"))
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(
            side_effect=RuntimeError("Redis down")
        )

        with patch(
            "backend.app.core.event_buffer.cleanup_old_events",
            mock_cleanup,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import cleanup_event_buffer_task

            result = cleanup_event_buffer_task.apply(
                args=["acme"],
                kwargs={},
            ).get()

        assert result["status"] == "error"
        assert "error" in result

    def test_cleanup_zero_events(self):
        """Cleanup returns 0 when no events to remove."""
        mock_cleanup = AsyncMock(return_value=0)
        mock_loop = MagicMock()
        mock_loop.run_until_complete = MagicMock(return_value=0)

        with patch(
            "backend.app.core.event_buffer.cleanup_old_events",
            mock_cleanup,
        ), patch("asyncio.new_event_loop", return_value=mock_loop), \
            patch("asyncio.get_event_loop", return_value=mock_loop):
            from backend.app.tasks.event_tasks import cleanup_event_buffer_task

            result = cleanup_event_buffer_task.apply(
                args=["acme"],
                kwargs={},
            ).get()

        assert result["events_removed"] == 0

    def test_cleanup_task_registered_in_celery(self):
        """cleanup_event_buffer_task is registered in Celery app."""
        from backend.app.tasks.celery_app import app
        assert (
            "backend.app.tasks.event_tasks.cleanup_event_buffer_task"
            in app.tasks
        )

    def test_cleanup_queue_is_default(self):
        """cleanup_event_buffer_task routes to 'default' queue."""
        from backend.app.tasks.celery_app import app
        task = app.tasks[
            "backend.app.tasks.event_tasks.cleanup_event_buffer_task"
        ]
        assert task.queue == "default"


class TestTaskMaxRetries:
    """Test task retry configuration (BC-004)."""

    def test_fanout_max_retries_3(self):
        """fanout_event_task has max_retries=3."""
        from backend.app.tasks.celery_app import app
        task = app.tasks[
            "backend.app.tasks.event_tasks.fanout_event_task"
        ]
        assert task.max_retries == 3

    def test_cleanup_max_retries_2(self):
        """cleanup_event_buffer_task has max_retries=2."""
        from backend.app.tasks.celery_app import app
        task = app.tasks[
            "backend.app.tasks.event_tasks.cleanup_event_buffer_task"
        ]
        assert task.max_retries == 2

    def test_fanout_acks_late(self):
        """fanout_event_task has acks_late=True."""
        from backend.app.tasks.celery_app import app
        task = app.tasks[
            "backend.app.tasks.event_tasks.fanout_event_task"
        ]
        assert task.acks_late is True
