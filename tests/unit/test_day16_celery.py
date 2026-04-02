"""
Day 16 Tests — Celery DLQ + Beat + Health Wire-up

Tests cover:
- Dead Letter Queue configuration (8 queues now)
- Beat scheduler with 3 periodic tasks
- Celery health check function
- Health endpoint includes celery subsystem
- Ready endpoint includes celery subsystem
- Periodic tasks are registered and callable
- Worker entry point scripts exist
- Task lifecycle DLQ logging on permanent failure
"""

import os

import pytest


class TestDeadLetterQueue:
    """Day 16: Dead Letter Queue configuration."""

    def test_dlq_queue_exists(self):
        """dead_letter queue is configured in QUEUE_NAMES."""
        from backend.app.tasks.celery_app import QUEUE_NAMES
        assert "dead_letter" in QUEUE_NAMES

    def test_total_queues_is_8(self):
        """Total queue count is now 8 (7 original + DLQ)."""
        from backend.app.tasks.celery_app import QUEUE_NAMES
        assert len(QUEUE_NAMES) == 8

    def test_dlq_queue_configured_in_app(self):
        """dead_letter queue exists in Celery app configuration."""
        from backend.app.tasks.celery_app import app
        configured = app.conf.task_queues
        assert "dead_letter" in configured

    def test_all_original_queues_still_present(self):
        """All 7 original queues still exist."""
        from backend.app.tasks.celery_app import QUEUE_NAMES
        original = [
            "default", "ai_heavy", "ai_light",
            "email", "webhook", "analytics", "training",
        ]
        for q in original:
            assert q in QUEUE_NAMES


class TestBeatScheduler:
    """Day 16: Celery Beat scheduler configuration."""

    def test_beat_schedule_exists(self):
        """Beat schedule is configured in Celery app."""
        from backend.app.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert schedule is not None
        assert isinstance(schedule, dict)

    def test_session_cleanup_scheduled(self):
        """Session cleanup task is scheduled."""
        from backend.app.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "cleanup-stale-sessions-daily" in schedule
        task_name = schedule[
            "cleanup-stale-sessions-daily"
        ]["task"]
        assert "cleanup_stale_sessions" in task_name

    def test_dlq_purge_scheduled(self):
        """DLQ purge task is scheduled."""
        from backend.app.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "purge-dead-letter-queue-hourly" in schedule

    def test_webhook_health_scheduled(self):
        """Webhook health check task is scheduled."""
        from backend.app.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert "check-webhook-health-every-5min" in schedule

    def test_three_scheduled_tasks(self):
        """Exactly 3 periodic tasks are scheduled."""
        from backend.app.tasks.celery_app import app
        schedule = app.conf.beat_schedule
        assert len(schedule) == 3

    def test_session_cleanup_interval(self):
        """Session cleanup runs every 24 hours."""
        from backend.app.tasks.celery_app import app
        interval = app.conf.beat_schedule[
            "cleanup-stale-sessions-daily"
        ]["schedule"]
        assert interval == 86400.0

    def test_webhook_health_interval(self):
        """Webhook health check runs every 5 minutes."""
        from backend.app.tasks.celery_app import app
        interval = app.conf.beat_schedule[
            "check-webhook-health-every-5min"
        ]["schedule"]
        assert interval == 300.0


class TestCeleryHealthCheck:
    """Day 16: Celery health check function."""

    def test_celery_health_check_importable(self):
        """celery_health_check function is importable."""
        from backend.app.tasks.celery_health import (
            celery_health_check,
        )
        assert callable(celery_health_check)

    def test_get_active_workers_importable(self):
        """get_active_workers function is importable."""
        from backend.app.tasks.celery_health import (
            get_active_workers,
        )
        assert callable(get_active_workers)


class TestHealthEndpointCelery:
    """Day 16: /health endpoint includes celery subsystem."""

    def test_health_includes_celery(self, client):
        """Health endpoint response includes celery subsystem."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "subsystems" in data
        assert "celery" in data["subsystems"]

    def test_health_celery_has_status(self, client):
        """Celery subsystem has a status field."""
        resp = client.get("/health")
        data = resp.json()
        celery = data["subsystems"]["celery"]
        assert "status" in celery

    def test_ready_includes_celery(self, client):
        """Readiness endpoint includes celery subsystem."""
        resp = client.get("/ready")
        data = resp.json()
        assert "subsystems" in data
        assert "celery" in data["subsystems"]


class TestPeriodicTasks:
    """Day 16: Periodic tasks are registered."""

    def test_periodic_module_importable(self):
        """Periodic tasks module is importable."""
        from backend.app.tasks import periodic
        assert periodic is not None

    def test_cleanup_stale_sessions_callable(self):
        """cleanup_stale_sessions task is callable."""
        from backend.app.tasks.periodic import (
            cleanup_stale_sessions,
        )
        assert callable(cleanup_stale_sessions)

    def test_purge_dlq_callable(self):
        """purge_dead_letter_queue task is callable."""
        from backend.app.tasks.periodic import (
            purge_dead_letter_queue,
        )
        assert callable(purge_dead_letter_queue)

    def test_webhook_health_callable(self):
        """check_webhook_health task is callable."""
        from backend.app.tasks.periodic import (
            check_webhook_health,
        )
        assert callable(check_webhook_health)

    def test_cleanup_stale_sessions_name(self):
        """cleanup_stale_sessions has correct registered name."""
        from backend.app.tasks.periodic import (
            cleanup_stale_sessions,
        )
        assert "cleanup_stale_sessions" in cleanup_stale_sessions.name

    def test_periodic_tasks_in_imports(self):
        """Periodic tasks module is in Celery imports."""
        from backend.app.tasks.celery_app import app
        assert "backend.app.tasks.periodic" in app.conf.imports


class TestWorkerEntryPoints:
    """Day 16: Worker and Beat entry point scripts exist."""

    def test_worker_script_exists(self):
        """run_worker.py script exists."""
        assert os.path.isfile(
            "scripts/run_worker.py",
        )

    def test_beat_script_exists(self):
        """run_beat.py script exists."""
        assert os.path.isfile(
            "scripts/run_beat.py",
        )


class TestTaskEventsEnabled:
    """Day 16: Task send events and tracking enabled."""

    def test_task_send_sent_event(self):
        """task_send_sent_event is enabled for monitoring."""
        from backend.app.tasks.celery_app import app
        assert app.conf.task_send_sent_event is True

    def test_task_track_started(self):
        """task_track_started is enabled for monitoring."""
        from backend.app.tasks.celery_app import app
        assert app.conf.task_track_started is True


class TestTaskDLQLogging:
    """Day 16: Task base logs DLQ routing on permanent failure."""

    def test_on_failure_logs_error(self, caplog):
        """on_failure logs task_failure for normal failures."""
        import logging
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

    def test_on_failure_logs_error_message(self, caplog):
        """on_failure includes error_message in log."""
        import logging
        from backend.app.tasks.base import ParwaBaseTask

        class FailTask(ParwaBaseTask):
            name = "test.error_msg"

        task = FailTask()
        exc = RuntimeError("some error")

        with caplog.at_level(logging.ERROR, logger="parwa.tasks"):
            task.on_failure(
                exc=exc,
                traceback=None,
                args=("comp_456",),
                kwargs={},
                einfo=None,
            )

        assert len(caplog.records) >= 1
        log_record = caplog.records[0]
        assert log_record.error_message == "some error"

    def test_on_failure_includes_company_id(self, caplog):
        """on_failure includes company_id from args."""
        import logging
        from backend.app.tasks.base import ParwaBaseTask

        class FailTask(ParwaBaseTask):
            name = "test.company"

        task = FailTask()

        with caplog.at_level(logging.ERROR, logger="parwa.tasks"):
            task.on_failure(
                exc=RuntimeError("err"),
                traceback=None,
                args=("comp_789", "extra"),
                kwargs={},
                einfo=None,
            )

        assert len(caplog.records) >= 1
        assert caplog.records[0].company_id == "comp_789"
