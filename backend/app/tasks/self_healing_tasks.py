"""
Self-Healing Periodic Tasks (Phase 6: Production Hardening)

Scheduled tasks executed by Celery Beat:
- run_self_healing_check: Every 5 minutes — detect anomalies and auto-heal
- run_anomaly_detection: Every 1 minute — detect and log anomalies
- run_circuit_breaker_health: Every 10 minutes — check and reset stale breakers

BC-001: These are system-level tasks (no company_id required).
BC-004: All tasks use ParwaBaseTask with retry config.
BC-008: Never crash — all tasks return gracefully on failure.
BC-012: All timestamps UTC.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.base import ParwaBaseTask
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.self_healing_tasks")


def _run_async(coro):
    """Run an async coroutine from a sync Celery task.

    Handles both cases: already in an event loop (use nest_asyncio)
    or not in an event loop (use asyncio.run).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're already in an event loop — create a new one
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════
# TASK: Self-Healing Check (Every 5 minutes)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.self_healing_tasks.run_self_healing_check",
    max_retries=1,
)
def run_self_healing_check(self):
    """Run periodic self-healing check.

    Detects system anomalies and applies automatic remediation:
    - LLM provider failover
    - Redis reconnection
    - DB pool reset
    - Stale lock cleanup
    - Circuit breaker reset
    - Queue drain monitoring

    Runs every 5 minutes via Celery Beat.
    Safe to run when system is healthy (no-op).
    """
    try:
        from app.services.self_healing_service import get_self_healing_service

        service = get_self_healing_service()
        result = _run_async(service.run_health_check())

        status = result.get("status", "unknown")
        anomalies = result.get("anomalies_found", 0)
        actions = len(result.get("healing_actions", []))

        if anomalies > 0:
            logger.info(
                "self_healing_check completed status=%s anomalies=%d actions=%d",
                status, anomalies, actions,
            )
        else:
            logger.debug(
                "self_healing_check healthy status=%s", status,
            )

        return {
            "status": status,
            "anomalies_found": anomalies,
            "healing_actions_taken": actions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning(
            "self_healing_check failed error=%s",
            str(exc)[:200],
        )
        return {
            "status": "failed",
            "error": str(exc)[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# TASK: Anomaly Detection (Every 1 minute)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.self_healing_tasks.run_anomaly_detection",
    max_retries=1,
)
def run_anomaly_detection(self):
    """Run anomaly detection and log results.

    Lightweight check that only detects and logs anomalies
    without taking corrective action. The full self-healing
    check (run_self_healing_check) handles remediation.

    Runs every 1 minute via Celery Beat.
    """
    try:
        from app.services.self_healing_service import get_self_healing_service

        service = get_self_healing_service()
        anomalies = service.detector.detect_all()

        if anomalies:
            for anomaly in anomalies:
                logger.warning(
                    "anomaly_detected service=%s type=%s severity=%s msg=%s",
                    anomaly.service,
                    anomaly.anomaly_type,
                    anomaly.severity,
                    anomaly.message[:200],
                )
        else:
            logger.debug("anomaly_detection no_anomalies")

        return {
            "status": "ok",
            "anomalies_found": len(anomalies),
            "anomalies": [
                {
                    "service": a.service,
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "message": a.message[:200],
                }
                for a in anomalies
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning(
            "anomaly_detection failed error=%s",
            str(exc)[:200],
        )
        return {
            "status": "failed",
            "error": str(exc)[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# TASK: Circuit Breaker Health (Every 10 minutes)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.self_healing_tasks.run_circuit_breaker_health",
    max_retries=1,
)
def run_circuit_breaker_health(self):
    """Check circuit breaker states and reset stale ones.

    Finds circuit breakers that have been in OPEN state for too
    long (default: 10 minutes) and resets them to CLOSED state
    to allow recovery testing.

    Runs every 10 minutes via Celery Beat.
    """
    try:
        from app.core.circuit_breaker_manager import (
            CircuitState,
            get_circuit_breaker_manager,
        )

        manager = get_circuit_breaker_manager()
        states = manager.get_all_states()

        open_circuits = []
        reset_circuits = []

        for name, status in states.items():
            if status["state"] == "open":
                open_circuits.append(name)

                # Check how long it's been open
                last_change = status.get("last_state_change")
                if last_change:
                    try:
                        change_time = datetime.fromisoformat(last_change)
                        if change_time.tzinfo is None:
                            change_time = change_time.replace(
                                tzinfo=timezone.utc,
                            )
                        elapsed = (
                            datetime.now(timezone.utc) - change_time
                        ).total_seconds()

                        # Reset if open for more than 10 minutes
                        if elapsed > 600:
                            manager.force_close(name)
                            reset_circuits.append(name)
                            logger.info(
                                "circuit_breaker_reset name=%s "
                                "open_duration=%ds",
                                name, round(elapsed),
                            )
                    except (ValueError, TypeError):
                        pass

        result = {
            "status": "ok",
            "total_circuits": len(states),
            "open_circuits": open_circuits,
            "reset_circuits": reset_circuits,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if open_circuits:
            logger.info(
                "circuit_breaker_health open=%d reset=%d",
                len(open_circuits), len(reset_circuits),
            )
        else:
            logger.debug("circuit_breaker_health all_closed")

        return result
    except Exception as exc:
        logger.warning(
            "circuit_breaker_health failed error=%s",
            str(exc)[:200],
        )
        return {
            "status": "failed",
            "error": str(exc)[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# TASK: Stale Lock Cleanup (Every 15 minutes)
# ══════════════════════════════════════════════════════════════════


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.self_healing_tasks.run_stale_lock_cleanup",
    max_retries=1,
)
def run_stale_lock_cleanup(self):
    """Clean up stale Redis locks.

    Finds Redis lock keys that have no TTL (potential stale locks)
    and removes them. Runs every 15 minutes via Celery Beat.
    """
    try:
        from app.services.self_healing_service import get_self_healing_service

        service = get_self_healing_service()
        result = _run_async(service.heal_stale_lock_cleanup())

        logger.info(
            "stale_lock_cleanup success=%s message=%s",
            result.success, result.message[:200],
        )

        return {
            "status": "ok" if result.success else "partial",
            "action": result.action.value,
            "message": result.message[:200],
            "details": result.details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning(
            "stale_lock_cleanup failed error=%s",
            str(exc)[:200],
        )
        return {
            "status": "failed",
            "error": str(exc)[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
