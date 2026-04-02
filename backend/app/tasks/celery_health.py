"""
PARWA Celery Health Check (Day 16, BC-004, BC-012)

Provides Celery broker connectivity check and worker status
for the /health and /ready endpoints.
"""

import logging
import time

logger = logging.getLogger("parwa.celery_health")


async def celery_health_check() -> dict:
    """Check Celery broker (Redis) connectivity and responsiveness.

    Returns:
        Dict with 'status' ('healthy' or 'unhealthy'), 'latency_ms',
        and optional 'error'.
    """
    start = time.monotonic()
    try:
        from backend.app.tasks.celery_app import app

        # Check broker connectivity
        conn = app.connection_or_acquire()
        try:
            conn.ensure_connection(max_retries=3, timeout=2)
            latency = round((time.monotonic() - start) * 1000, 2)
            return {
                "status": "healthy",
                "latency_ms": latency,
            }
        finally:
            conn.release()
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        logger.warning(
            "celery_health_check failed latency_ms=%s error=%s",
            latency, exc,
        )
        return {
            "status": "unhealthy",
            "latency_ms": latency,
            "error": str(exc),
        }


async def get_active_workers() -> dict:
    """Get active Celery worker count and queue stats.

    Returns:
        Dict with 'worker_count' and 'queue_lengths'.
    """
    try:
        from backend.app.tasks.celery_app import app

        inspect = app.control.inspect(timeout=3)
        active_workers = inspect.active()

        worker_count = 0
        if active_workers:
            worker_count = len(active_workers)

        return {
            "status": "healthy" if worker_count > 0 else "no_workers",
            "worker_count": worker_count,
        }
    except Exception as exc:
        logger.warning(
            "get_active_workers failed error=%s",
            exc,
        )
        return {
            "status": "unreachable",
            "worker_count": 0,
            "error": str(exc),
        }
