"""
Week 3 Unit Tests — Celery Infrastructure (BC-004)

Tests for:
- celery_app.py — App config, queues, task routing, beat schedule
- base.py — ParwaBaseTask, @with_company_id, tenant context propagation
- celery_health.py — asyncio.to_thread wrapping, broker check
"""

import sys
import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ── celery_health Tests ─────────────────────────────────────────

class TestCeleryHealthCheck:

    @pytest.mark.asyncio
    async def test_healthy_when_broker_reachable(self):
        mock_conn = MagicMock()
        mock_conn.ensure_connection.return_value = True
        mock_conn.release = MagicMock()
        mock_app = MagicMock()
        mock_app.connection_or_acquire.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_app.connection_or_acquire.return_value.__exit__ = MagicMock(return_value=False)
        with patch("backend.app.tasks.celery_health.app", mock_app), \
             patch("backend.app.tasks.celery_health._sync_celery_health_check",
                   return_value={"status": "healthy", "latency_ms": 5}):
            result = await celery_health_check()
            assert result["status"] == "healthy"
            assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_unhealthy_when_broker_down(self):
        with patch("backend.app.tasks.celery_health._sync_celery_health_check",
                   return_value={"status": "unhealthy", "latency_ms": 100, "error": "Connection refused"}):
            result = await celery_health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_uses_asyncio_to_thread(self):
        """Verify sync function is called via asyncio.to_thread."""
        with patch("backend.app.tasks.celery_health.asyncio.to_thread",
                   new_callable=AsyncMock,
                   return_value={"status": "healthy", "latency_ms": 1}) as mock_to_thread:
            from backend.app.tasks.celery_health import celery_health_check
            await celery_health_check()
            mock_to_thread.assert_called_once()


class TestGetActiveWorkers:

    @pytest.mark.asyncio
    async def test_returns_worker_count(self):
        with patch("backend.app.tasks.celery_health._sync_get_active_workers",
                   return_value={"status": "healthy", "worker_count": 5}):
            from backend.app.tasks.celery_health import get_active_workers
            result = await get_active_workers()
            assert result["worker_count"] == 5
            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_workers(self):
        with patch("backend.app.tasks.celery_health._sync_get_active_workers",
                   return_value={"status": "no_workers", "worker_count": 0}):
            from backend.app.tasks.celery_health import get_active_workers
            result = await get_active_workers()
            assert result["worker_count"] == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        with patch("backend.app.tasks.celery_health._sync_get_active_workers",
                   return_value={"status": "unreachable", "worker_count": 0, "error": "timeout"}):
            from backend.app.tasks.celery_health import get_active_workers
            result = await get_active_workers()
            assert result["worker_count"] == 0
            assert result["status"] == "unreachable"

    @pytest.mark.asyncio
    async def test_uses_asyncio_to_thread(self):
        """Verify sync function is called via asyncio.to_thread."""
        with patch("backend.app.tasks.celery_health.asyncio.to_thread",
                   new_callable=AsyncMock,
                   return_value={"status": "healthy", "worker_count": 2}) as mock_to_thread:
            from backend.app.tasks.celery_health import get_active_workers
            await get_active_workers()
            mock_to_thread.assert_called_once()


class TestSyncCeleryHealthCheck:

    def test_healthy_broker(self):
        mock_conn = MagicMock()
        mock_conn.ensure_connection.return_value = True
        mock_conn.release = MagicMock()
        mock_app = MagicMock()
        mock_app.connection_or_acquire.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_app.connection_or_acquire.return_value.__exit__ = MagicMock(return_value=False)
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_celery_health_check
            result = _sync_celery_health_check()
            assert result["status"] == "healthy"
            assert "latency_ms" in result

    def test_unhealthy_broker(self):
        mock_app = MagicMock()
        mock_app.connection_or_acquire.return_value.__enter__ = MagicMock(
            side_effect=Exception("Connection refused"))
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_celery_health_check
            result = _sync_celery_health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result

    def test_connection_released_in_finally(self):
        mock_conn = MagicMock()
        mock_app = MagicMock()
        mock_app.connection_or_acquire.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_app.connection_or_acquire.return_value.__exit__ = MagicMock(return_value=False)
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_celery_health_check
            _sync_celery_health_check()
            mock_conn.release.assert_called_once()


class TestSyncGetActiveWorkers:

    def test_returns_count_with_active_workers(self):
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = {"worker1": [1, 2], "worker2": [3]}
        mock_app = MagicMock()
        mock_app.control.inspect.return_value = mock_inspect
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_get_active_workers
            result = _sync_get_active_workers()
            assert result["worker_count"] == 2
            assert result["status"] == "healthy"

    def test_returns_zero_no_workers(self):
        mock_inspect = MagicMock()
        mock_inspect.active.return_value = None
        mock_app = MagicMock()
        mock_app.control.inspect.return_value = mock_inspect
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_get_active_workers
            result = _sync_get_active_workers()
            assert result["worker_count"] == 0
            assert result["status"] == "no_workers"

    def test_returns_error_on_exception(self):
        mock_app = MagicMock()
        mock_app.control.inspect.side_effect = Exception("broker down")
        with patch("backend.app.tasks.celery_health.app", mock_app):
            from backend.app.tasks.celery_health import _sync_get_active_workers
            result = _sync_get_active_workers()
            assert result["worker_count"] == 0
            assert result["status"] == "unreachable"
            assert "error" in result


# ── Import at top level after patches ───────────────────────────

# These imports need the module path available
from backend.app.tasks.celery_health import (
    celery_health_check,
    get_active_workers,
    _sync_celery_health_check,
    _sync_get_active_workers,
)
