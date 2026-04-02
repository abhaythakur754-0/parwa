"""
Day 16 Loophole Tests — Celery Infrastructure Hardening

Tests for all Day 16 loophole fixes:
- L40: cleanup_stale_sessions cutoff must be 7 days ago (NOT now())
- L41: Worker script must include all 8 queues
- L42: No dead/unused variables in celery_health.py
- L43: on_retry truncates error message like on_failure
"""

import inspect
import os

import pytest


class TestL40SessionCleanupCutoff:
    """L40: cleanup_stale_sessions must delete old sessions only."""

    def test_cutoff_is_7_days_ago(self):
        """Source code uses timedelta(days=7), not datetime.now()."""
        from backend.app.tasks.periodic import cleanup_stale_sessions
        source = inspect.getsource(cleanup_stale_sessions)
        assert "timedelta" in source
        assert "days=7" in source

    def test_cutoff_uses_subtraction(self):
        """Cutoff uses subtraction (now - 7 days), not just now()."""
        from backend.app.tasks.periodic import cleanup_stale_sessions
        source = inspect.getsource(cleanup_stale_sessions)
        # Should be: datetime.now(timezone.utc) - timedelta(days=7)
        assert "- timedelta" in source


class TestL41WorkerScriptAllQueues:
    """L41: Worker script must include all 8 queues."""

    def test_worker_includes_all_queues(self):
        """run_worker.py includes all 8 queues."""
        with open("scripts/run_worker.py") as f:
            content = f.read()

        required_queues = [
            "default", "ai_heavy", "ai_light",
            "email", "webhook", "analytics",
            "training", "dead_letter",
        ]
        for q in required_queues:
            assert q in content, f"Missing queue '{q}' in run_worker.py"


class TestL42NoDeadVariables:
    """L42: No dead/unused variables in celery_health.py."""

    def test_no_unused_stats_variable(self):
        """get_active_workers should not have unused 'stats' variable."""
        from backend.app.tasks.celery_health import get_active_workers
        source = inspect.getsource(get_active_workers)
        # The old code had: stats = inspect.stats() but never used it
        assert "stats = inspect.stats()" not in source


class TestL43RetryErrorTruncation:
    """L43: on_retry must truncate error messages like on_failure."""

    def test_on_retry_truncates_error(self):
        """on_retry source truncates error_message to 500 chars."""
        from backend.app.tasks.base import ParwaTask
        source = inspect.getsource(ParwaTask.on_retry)
        assert "[:500]" in source

    def test_on_failure_truncates_error(self):
        """on_failure also truncates (for consistency)."""
        from backend.app.tasks.base import ParwaTask
        source = inspect.getsource(ParwaTask.on_failure)
        assert "[:500]" in source

    def test_both_truncate_consistently(self):
        """Both on_retry and on_failure use same truncation length."""
        from backend.app.tasks.base import ParwaTask
        retry_source = inspect.getsource(ParwaTask.on_retry)
        failure_source = inspect.getsource(ParwaTask.on_failure)
        assert "[:500]" in retry_source
        assert "[:500]" in failure_source
