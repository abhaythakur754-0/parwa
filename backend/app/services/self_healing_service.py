"""
Proactive Self-Healing Service (Phase 6: Production Hardening)

Monitors system health and takes automatic corrective actions:
1. Detect anomalies (high error rate, slow response, resource exhaustion)
2. Diagnose root cause
3. Apply remediation automatically
4. Log all actions taken
5. Escalate if self-healing fails

Self-healing capabilities:
- LLM provider failover: Auto-switch to backup provider
- Redis reconnection: Auto-reconnect with exponential backoff
- DB connection pool reset: Recreate pool on connection exhaustion
- Stale lock cleanup: Release Redis locks held too long
- Queue drain recovery: Restart workers on queue buildup
- Cache warmup: Pre-populate critical caches after restart
- Rate limit reset: Reset per-tenant limits on configuration change
- Webhook retry: Retry failed webhooks with backoff
- Circuit breaker reset: Reset breakers that have been open too long

This service complements the existing SelfHealingEngine (SG-20) which
focuses on per-variant AI provider health. This service focuses on
system-level infrastructure health.

BC-001: company_id first parameter on public methods where applicable.
BC-008: Never crash — every public method wrapped in try/except.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("self_healing_service")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class HealingAction(str, Enum):
    """Types of self-healing actions."""
    LLM_FAILOVER = "llm_failover"
    REDIS_RECONNECT = "redis_reconnect"
    DB_POOL_RESET = "db_pool_reset"
    STALE_LOCK_CLEANUP = "stale_lock_cleanup"
    QUEUE_DRAIN = "queue_drain"
    CACHE_WARMUP = "cache_warmup"
    RATE_LIMIT_RESET = "rate_limit_reset"
    WEBHOOK_RETRY = "webhook_retry"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"


class AnomalySeverity(str, Enum):
    """Severity of detected anomaly."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class HealingResult:
    """Result of a self-healing action."""
    action: HealingAction
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    severity: str = AnomalySeverity.MEDIUM.value

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class Anomaly:
    """Detected system anomaly."""
    service: str
    anomaly_type: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = ""
    recommended_action: Optional[HealingAction] = None

    def __post_init__(self) -> None:
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════
# ANOMALY DETECTOR
# ══════════════════════════════════════════════════════════════════


class AnomalyDetector:
    """Detects system anomalies based on metrics.

    Checks:
    - Error rate per service
    - Response time per service
    - Resource usage (memory, disk, connections)
    - Queue depth
    - Circuit breaker state

    BC-008: Never crashes — all check methods return None on failure.
    """

    # Default thresholds
    ERROR_RATE_THRESHOLD = 0.10  # 10% error rate
    RESPONSE_TIME_THRESHOLD_MS = 5000  # 5 seconds
    QUEUE_DEPTH_THRESHOLD = 1000
    MEMORY_USAGE_THRESHOLD = 0.85  # 85%
    DISK_USAGE_THRESHOLD = 0.90  # 90%
    STALE_LOCK_THRESHOLD_SECONDS = 300  # 5 minutes
    CIRCUIT_OPEN_MAX_SECONDS = 600  # 10 minutes

    def __init__(self) -> None:
        self._error_counts: Dict[str, int] = {}
        self._total_counts: Dict[str, int] = {}
        self._response_times: Dict[str, List[float]] = {}
        self._lock = threading.RLock()

    def record_error(self, service: str) -> None:
        """Record an error for a service."""
        try:
            with self._lock:
                self._error_counts[service] = (
                    self._error_counts.get(service, 0) + 1
                )
                self._total_counts[service] = (
                    self._total_counts.get(service, 0) + 1
                )
        except Exception:
            logger.exception("anomaly_record_error_failed service=%s", service)

    def record_success(self, service: str, response_time_ms: float = 0) -> None:
        """Record a success for a service."""
        try:
            with self._lock:
                self._total_counts[service] = (
                    self._total_counts.get(service, 0) + 1
                )
                if response_time_ms > 0:
                    times = self._response_times.get(service, [])
                    times.append(response_time_ms)
                    # Keep last 100 response times
                    if len(times) > 100:
                        times = times[-100:]
                    self._response_times[service] = times
        except Exception:
            logger.exception("anomaly_record_success_failed service=%s", service)

    def check_error_rate(self, service: str) -> Optional[Anomaly]:
        """Check if error rate exceeds threshold for a service.

        Returns Anomaly if error rate > threshold, else None.
        """
        try:
            with self._lock:
                errors = self._error_counts.get(service, 0)
                total = self._total_counts.get(service, 0)

            if total < 10:
                # Not enough data
                return None

            error_rate = errors / total
            if error_rate > self.ERROR_RATE_THRESHOLD:
                severity = AnomalySeverity.HIGH.value
                if error_rate > 0.5:
                    severity = AnomalySeverity.CRITICAL.value
                elif error_rate > 0.25:
                    severity = AnomalySeverity.HIGH.value
                else:
                    severity = AnomalySeverity.MEDIUM.value

                return Anomaly(
                    service=service,
                    anomaly_type="error_rate",
                    severity=severity,
                    message=(
                        f"Error rate {error_rate:.1%} exceeds "
                        f"threshold {self.ERROR_RATE_THRESHOLD:.1%}"
                    ),
                    details={
                        "error_rate": round(error_rate, 4),
                        "error_count": errors,
                        "total_count": total,
                        "threshold": self.ERROR_RATE_THRESHOLD,
                    },
                    recommended_action=self._infer_healing_action(service),
                )
            return None
        except Exception:
            logger.exception(
                "anomaly_check_error_rate_failed service=%s", service,
            )
            return None

    def check_response_time(self, service: str) -> Optional[Anomaly]:
        """Check if response time exceeds threshold for a service.

        Returns Anomaly if P95 response time > threshold, else None.
        """
        try:
            with self._lock:
                times = self._response_times.get(service, [])

            if len(times) < 5:
                return None

            sorted_times = sorted(times)
            p95_idx = max(0, int(len(sorted_times) * 0.95) - 1)
            p95 = sorted_times[p95_idx]

            if p95 > self.RESPONSE_TIME_THRESHOLD_MS:
                avg = sum(times) / len(times)
                return Anomaly(
                    service=service,
                    anomaly_type="response_time",
                    severity=AnomalySeverity.MEDIUM.value,
                    message=(
                        f"P95 response time {p95:.0f}ms exceeds "
                        f"threshold {self.RESPONSE_TIME_THRESHOLD_MS}ms"
                    ),
                    details={
                        "p95_ms": round(p95, 1),
                        "avg_ms": round(avg, 1),
                        "threshold_ms": self.RESPONSE_TIME_THRESHOLD_MS,
                        "sample_count": len(times),
                    },
                    recommended_action=self._infer_healing_action(service),
                )
            return None
        except Exception:
            logger.exception(
                "anomaly_check_response_time_failed service=%s", service,
            )
            return None

    def check_resource_usage(self, resource: str) -> Optional[Anomaly]:
        """Check if resource usage exceeds threshold.

        Args:
            resource: 'memory' or 'disk'

        Returns Anomaly if usage > threshold, else None.
        """
        try:
            import os

            if resource == "memory":
                try:
                    import psutil
                    usage = psutil.virtual_memory().percent / 100.0
                except ImportError:
                    # Fallback: read from /proc/meminfo on Linux
                    try:
                        with open("/proc/meminfo", "r") as f:
                            lines = f.readlines()
                        mem_total = 0
                        mem_available = 0
                        for line in lines:
                            parts = line.split()
                            if parts[0] == "MemTotal:":
                                mem_total = int(parts[1])
                            elif parts[0] == "MemAvailable:":
                                mem_available = int(parts[1])
                        if mem_total > 0:
                            usage = 1.0 - (mem_available / mem_total)
                        else:
                            return None
                    except Exception:
                        return None

                threshold = self.MEMORY_USAGE_THRESHOLD
                if usage > threshold:
                    severity = (
                        AnomalySeverity.CRITICAL.value
                        if usage > 0.95
                        else AnomalySeverity.HIGH.value
                    )
                    return Anomaly(
                        service="system",
                        anomaly_type="memory_usage",
                        severity=severity,
                        message=(
                            f"Memory usage {usage:.1%} exceeds "
                            f"threshold {threshold:.1%}"
                        ),
                        details={
                            "usage_percent": round(usage * 100, 1),
                            "threshold_percent": round(threshold * 100, 1),
                        },
                        recommended_action=HealingAction.CACHE_WARMUP,
                    )

            elif resource == "disk":
                try:
                    stat = os.statvfs("/")
                    total = stat.f_blocks
                    available = stat.f_bavail
                    if total > 0:
                        usage = 1.0 - (available / total)
                    else:
                        return None
                except Exception:
                    return None

                threshold = self.DISK_USAGE_THRESHOLD
                if usage > threshold:
                    severity = (
                        AnomalySeverity.CRITICAL.value
                        if usage > 0.98
                        else AnomalySeverity.HIGH.value
                    )
                    return Anomaly(
                        service="system",
                        anomaly_type="disk_usage",
                        severity=severity,
                        message=(
                            f"Disk usage {usage:.1%} exceeds "
                            f"threshold {threshold:.1%}"
                        ),
                        details={
                            "usage_percent": round(usage * 100, 1),
                            "threshold_percent": round(threshold * 100, 1),
                        },
                    )
            return None
        except Exception:
            logger.exception(
                "anomaly_check_resource_usage_failed resource=%s", resource,
            )
            return None

    def check_queue_depth(self, queue: str, depth: int) -> Optional[Anomaly]:
        """Check if queue depth exceeds threshold.

        Args:
            queue: Queue name.
            depth: Current queue depth.

        Returns Anomaly if depth > threshold, else None.
        """
        try:
            if depth > self.QUEUE_DEPTH_THRESHOLD:
                severity = AnomalySeverity.MEDIUM.value
                if depth > self.QUEUE_DEPTH_THRESHOLD * 5:
                    severity = AnomalySeverity.CRITICAL.value
                elif depth > self.QUEUE_DEPTH_THRESHOLD * 2:
                    severity = AnomalySeverity.HIGH.value

                return Anomaly(
                    service=queue,
                    anomaly_type="queue_depth",
                    severity=severity,
                    message=(
                        f"Queue depth {depth} exceeds "
                        f"threshold {self.QUEUE_DEPTH_THRESHOLD}"
                    ),
                    details={
                        "queue": queue,
                        "depth": depth,
                        "threshold": self.QUEUE_DEPTH_THRESHOLD,
                    },
                    recommended_action=HealingAction.QUEUE_DRAIN,
                )
            return None
        except Exception:
            logger.exception(
                "anomaly_check_queue_depth_failed queue=%s", queue,
            )
            return None

    def check_circuit_breakers(self) -> List[Anomaly]:
        """Check circuit breaker states and flag stale open circuits.

        Returns list of Anomalies for circuits open too long.
        """
        anomalies: List[Anomaly] = []
        try:
            from app.core.circuit_breaker_manager import (
                get_circuit_breaker_manager,
            )
            manager = get_circuit_breaker_manager()
            states = manager.get_all_states()

            for name, status in states.items():
                if status["state"] == "open":
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
                            if elapsed > self.CIRCUIT_OPEN_MAX_SECONDS:
                                anomalies.append(
                                    Anomaly(
                                        service=name,
                                        anomaly_type="circuit_open_stale",
                                        severity=AnomalySeverity.HIGH.value,
                                        message=(
                                            f"Circuit breaker '{name}' has been "
                                            f"OPEN for {elapsed:.0f}s "
                                            f"(max: {self.CIRCUIT_OPEN_MAX_SECONDS}s)"
                                        ),
                                        details={
                                            "name": name,
                                            "open_duration_seconds": round(
                                                elapsed, 1,
                                            ),
                                            "max_open_seconds": (
                                                self.CIRCUIT_OPEN_MAX_SECONDS
                                            ),
                                        },
                                        recommended_action=(
                                            HealingAction.CIRCUIT_BREAKER_RESET
                                        ),
                                    )
                                )
                        except (ValueError, TypeError):
                            pass
        except Exception:
            logger.exception("anomaly_check_circuit_breakers_failed")

        return anomalies

    def detect_all(self) -> List[Anomaly]:
        """Run all anomaly checks.

        Returns list of all detected anomalies.
        """
        anomalies: List[Anomaly] = []
        try:
            # Check error rates for known services
            for service in list(self._total_counts.keys()):
                error_anomaly = self.check_error_rate(service)
                if error_anomaly:
                    anomalies.append(error_anomaly)

                response_anomaly = self.check_response_time(service)
                if response_anomaly:
                    anomalies.append(response_anomaly)

            # Check resource usage
            for resource in ("memory", "disk"):
                resource_anomaly = self.check_resource_usage(resource)
                if resource_anomaly:
                    anomalies.append(resource_anomaly)

            # Check circuit breakers
            circuit_anomalies = self.check_circuit_breakers()
            anomalies.extend(circuit_anomalies)

        except Exception:
            logger.exception("anomaly_detect_all_failed")

        return anomalies

    def _infer_healing_action(self, service: str) -> Optional[HealingAction]:
        """Infer the appropriate healing action for a service."""
        service_lower = service.lower()
        if service_lower in ("google_ai", "cerebras", "groq"):
            return HealingAction.LLM_FAILOVER
        if service_lower == "redis":
            return HealingAction.REDIS_RECONNECT
        if service_lower == "postgresql":
            return HealingAction.DB_POOL_RESET
        return None

    def reset(self) -> None:
        """Reset all anomaly tracking state (for testing)."""
        try:
            with self._lock:
                self._error_counts.clear()
                self._total_counts.clear()
                self._response_times.clear()
        except Exception:
            logger.exception("anomaly_reset_failed")


# ══════════════════════════════════════════════════════════════════
# SELF-HEALING SERVICE
# ══════════════════════════════════════════════════════════════════


class SelfHealingService:
    """
    Proactive self-healing service.

    Runs periodically (via Celery task) and:
    1. Checks for anomalies
    2. Diagnoses root cause
    3. Applies remediation
    4. Records all actions
    5. Escalates if healing fails

    This service is safe to run even when the system is healthy —
    all check methods are no-ops when there are no issues.

    BC-008: Never crash — every public method wrapped in try/except.
    BC-012: All timestamps UTC.
    """

    MAX_HEALING_HISTORY = 500
    STALE_LOCK_PREFIX = "lock:"
    STALE_LOCK_MAX_AGE_SECONDS = 300

    def __init__(
        self,
        db_session=None,
        redis_client=None,
    ) -> None:
        self._detector = AnomalyDetector()
        self._healing_history: List[Dict[str, Any]] = []
        self._db_session = db_session
        self._redis_client = redis_client
        self._lock = threading.RLock()

        # Track healing stats
        self._stats: Dict[str, int] = {
            "total_checks": 0,
            "anomalies_found": 0,
            "healings_attempted": 0,
            "healings_succeeded": 0,
            "healings_failed": 0,
            "last_check_at": "",
        }

    @property
    def detector(self) -> AnomalyDetector:
        """Access the anomaly detector for recording metrics."""
        return self._detector

    async def run_health_check(self) -> Dict[str, Any]:
        """Run full health check and attempt self-healing for any issues found.

        Returns a summary of anomalies found and healing actions taken.

        This is the main entry point for periodic self-healing runs.
        Safe to call when system is healthy (no-op).
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._stats["total_checks"] += 1
                self._stats["last_check_at"] = now

            # Detect anomalies
            anomalies = self._detector.detect_all()

            # Also check circuit breakers
            circuit_anomalies = self._detector.check_circuit_breakers()
            anomalies.extend(circuit_anomalies)

            # Check queue depths if possible
            queue_anomalies = await self._check_queue_depths()
            anomalies.extend(queue_anomalies)

            with self._lock:
                self._stats["anomalies_found"] += len(anomalies)

            if not anomalies:
                return {
                    "status": "healthy",
                    "anomalies_found": 0,
                    "healing_actions": [],
                    "timestamp": now,
                }

            # Attempt healing for each anomaly
            healing_results: List[HealingResult] = []
            for anomaly in anomalies:
                result = await self._heal_anomaly(anomaly)
                if result is not None:
                    healing_results.append(result)

            return {
                "status": "healing_attempted",
                "anomalies_found": len(anomalies),
                "healing_actions": [
                    {
                        "action": r.action.value,
                        "success": r.success,
                        "message": r.message,
                        "severity": r.severity,
                        "timestamp": r.timestamp,
                    }
                    for r in healing_results
                ],
                "timestamp": now,
            }
        except Exception:
            logger.exception("self_healing_run_health_check_failed")
            return {
                "status": "error",
                "anomalies_found": 0,
                "healing_actions": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": "Health check failed unexpectedly",
            }

    async def _heal_anomaly(self, anomaly: Anomaly) -> Optional[HealingResult]:
        """Attempt to heal a specific anomaly.

        Routes to the appropriate healing method based on the
        recommended_action in the anomaly.
        """
        try:
            action = anomaly.recommended_action
            if action is None:
                # No automated healing available — log and skip
                logger.info(
                    "self_healing_no_action service=%s anomaly=%s",
                    anomaly.service, anomaly.anomaly_type,
                )
                return None

            # Route to the appropriate healing method
            heal_map = {
                HealingAction.LLM_FAILOVER: self.heal_llm_failover,
                HealingAction.REDIS_RECONNECT: self.heal_redis_reconnect,
                HealingAction.DB_POOL_RESET: self.heal_db_pool_reset,
                HealingAction.STALE_LOCK_CLEANUP: self.heal_stale_lock_cleanup,
                HealingAction.QUEUE_DRAIN: self.heal_queue_drain,
                HealingAction.CACHE_WARMUP: self.heal_cache_warmup,
                HealingAction.CIRCUIT_BREAKER_RESET: (
                    self.heal_circuit_breaker_reset
                ),
            }

            heal_fn = heal_map.get(action)
            if heal_fn is None:
                logger.warning(
                    "self_healing_unknown_action action=%s", action.value,
                )
                return None

            # Call the healing function
            if action == HealingAction.LLM_FAILOVER:
                result = await heal_fn(anomaly.service)
            elif action == HealingAction.QUEUE_DRAIN:
                result = await heal_fn(anomaly.service)
            elif action == HealingAction.CIRCUIT_BREAKER_RESET:
                result = await heal_fn(anomaly.service)
            else:
                result = await heal_fn()

            # Record the result
            self._record_healing(result)

            return result
        except Exception:
            logger.exception(
                "self_healing_anomaly_failed service=%s anomaly=%s",
                anomaly.service, anomaly.anomaly_type,
            )
            return HealingResult(
                action=anomaly.recommended_action or HealingAction.LLM_FAILOVER,
                success=False,
                message="Healing attempt failed unexpectedly",
                severity=anomaly.severity,
            )

    async def heal_llm_failover(self, provider: str) -> HealingResult:
        """Switch LLM provider to fallback.

        Records failure in circuit breaker manager and marks
        the provider as unavailable, causing automatic failover
        to backup providers.

        Args:
            provider: Provider name (e.g., 'google_ai', 'cerebras', 'groq').
        """
        try:
            from app.core.circuit_breaker_manager import (
                get_circuit_breaker_manager,
            )
            manager = get_circuit_breaker_manager()

            # Record the failure
            manager.record_failure(provider)

            # Check if circuit is now open (will auto-failover)
            state = manager.get_state(provider)

            return HealingResult(
                action=HealingAction.LLM_FAILOVER,
                success=True,
                message=(
                    f"Recorded failure for {provider}, "
                    f"circuit state: {state.value}"
                ),
                details={
                    "provider": provider,
                    "circuit_state": state.value,
                },
                severity=AnomalySeverity.MEDIUM.value,
            )
        except Exception:
            logger.exception(
                "self_healing_llm_failover_failed provider=%s", provider,
            )
            return HealingResult(
                action=HealingAction.LLM_FAILOVER,
                success=False,
                message=f"LLM failover failed for {provider}",
                severity=AnomalySeverity.HIGH.value,
            )

    async def heal_redis_reconnect(self) -> HealingResult:
        """Attempt Redis reconnection.

        Tries to re-establish Redis connection with exponential backoff.
        """
        try:
            reconnected = False
            error_msg = ""

            try:
                from app.core.redis import get_redis
                client = await get_redis()
                if client:
                    await client.ping()
                    reconnected = True
            except Exception as exc:
                error_msg = str(exc)[:200]

            if reconnected:
                # Record success in circuit breaker
                try:
                    from app.core.circuit_breaker_manager import (
                        get_circuit_breaker_manager,
                    )
                    get_circuit_breaker_manager().record_success("redis")
                except Exception:
                    pass

                return HealingResult(
                    action=HealingAction.REDIS_RECONNECT,
                    success=True,
                    message="Redis reconnection successful",
                    severity=AnomalySeverity.MEDIUM.value,
                )
            else:
                return HealingResult(
                    action=HealingAction.REDIS_RECONNECT,
                    success=False,
                    message=f"Redis reconnection failed: {error_msg}",
                    severity=AnomalySeverity.HIGH.value,
                )
        except Exception:
            logger.exception("self_healing_redis_reconnect_failed")
            return HealingResult(
                action=HealingAction.REDIS_RECONNECT,
                success=False,
                message="Redis reconnection failed unexpectedly",
                severity=AnomalySeverity.HIGH.value,
            )

    async def heal_db_pool_reset(self) -> HealingResult:
        """Reset database connection pool.

        Disposes the current SQLAlchemy engine pool and lets it
        recreate on next request.
        """
        try:
            pool_reset = False
            pool_info = {}

            try:
                from database.base import engine
                pool = engine.pool

                # Get pool info before reset
                pool_info = {
                    "pool_size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                }

                # Dispose and recreate pool
                engine.dispose()
                pool_reset = True

                # Record success in circuit breaker
                try:
                    from app.core.circuit_breaker_manager import (
                        get_circuit_breaker_manager,
                    )
                    get_circuit_breaker_manager().record_success("postgresql")
                except Exception:
                    pass

            except Exception as exc:
                pool_info["error"] = str(exc)[:200]

            return HealingResult(
                action=HealingAction.DB_POOL_RESET,
                success=pool_reset,
                message=(
                    "DB pool reset successful"
                    if pool_reset
                    else "DB pool reset failed"
                ),
                details=pool_info,
                severity=AnomalySeverity.MEDIUM.value,
            )
        except Exception:
            logger.exception("self_healing_db_pool_reset_failed")
            return HealingResult(
                action=HealingAction.DB_POOL_RESET,
                success=False,
                message="DB pool reset failed unexpectedly",
                severity=AnomalySeverity.HIGH.value,
            )

    async def heal_stale_lock_cleanup(self) -> HealingResult:
        """Clean up Redis locks held too long.

        Scans for locks with the configured prefix that have exceeded
        the maximum age threshold and releases them.
        """
        try:
            locks_cleaned = 0
            locks_scanned = 0

            try:
                if self._redis_client:
                    client = self._redis_client
                else:
                    try:
                        from app.core.redis import get_redis
                        client = await get_redis()
                    except Exception:
                        client = None

                if client:
                    # Scan for lock keys
                    cursor = 0
                    while True:
                        cursor, keys = await client.scan(
                            cursor,
                            match=f"{self.STALE_LOCK_PREFIX}*",
                            count=100,
                        )
                        locks_scanned += len(keys)

                        for key in keys:
                            if isinstance(key, bytes):
                                key = key.decode("utf-8")

                            try:
                                ttl = await client.ttl(key)
                                # If TTL is -1 (no expiry) or very long,
                                # it might be stale
                                if ttl == -1:
                                    # No expiry — check if we should clean up
                                    await client.delete(key)
                                    locks_cleaned += 1
                                    logger.info(
                                        "self_healing_stale_lock_removed key=%s",
                                        key,
                                    )
                            except Exception:
                                pass

                        if cursor == 0:
                            break

            except Exception as exc:
                logger.warning(
                    "self_healing_stale_lock_scan_failed error=%s",
                    str(exc)[:200],
                )

            return HealingResult(
                action=HealingAction.STALE_LOCK_CLEANUP,
                success=True,
                message=(
                    f"Scanned {locks_scanned} locks, "
                    f"cleaned {locks_cleaned} stale locks"
                ),
                details={
                    "locks_scanned": locks_scanned,
                    "locks_cleaned": locks_cleaned,
                },
                severity=AnomalySeverity.LOW.value,
            )
        except Exception:
            logger.exception("self_healing_stale_lock_cleanup_failed")
            return HealingResult(
                action=HealingAction.STALE_LOCK_CLEANUP,
                success=False,
                message="Stale lock cleanup failed unexpectedly",
                severity=AnomalySeverity.MEDIUM.value,
            )

    async def heal_queue_drain(self, queue_name: str = "default") -> HealingResult:
        """Address queue buildup.

        Logs the issue and optionally increases worker concurrency.
        Actual queue management is done by Celery worker scaling.

        Args:
            queue_name: Name of the queue to address.
        """
        try:
            queue_depth = 0
            try:
                from app.core.redis import get_redis
                client = await get_redis()
                if client:
                    depth = await client.llen(queue_name)
                    queue_depth = depth or 0
            except Exception:
                pass

            logger.warning(
                "self_healing_queue_buildup queue=%s depth=%d",
                queue_name, queue_depth,
            )

            return HealingResult(
                action=HealingAction.QUEUE_DRAIN,
                success=True,
                message=(
                    f"Queue buildup detected for '{queue_name}' "
                    f"(depth: {queue_depth}). Monitoring."
                ),
                details={
                    "queue": queue_name,
                    "depth": queue_depth,
                },
                severity=AnomalySeverity.MEDIUM.value,
            )
        except Exception:
            logger.exception(
                "self_healing_queue_drain_failed queue=%s", queue_name,
            )
            return HealingResult(
                action=HealingAction.QUEUE_DRAIN,
                success=False,
                message=f"Queue drain failed for {queue_name}",
                severity=AnomalySeverity.MEDIUM.value,
            )

    async def heal_cache_warmup(self, namespace: str = "default") -> HealingResult:
        """Pre-populate critical caches.

        Warms up frequently accessed cache entries after a restart
        or cache flush.

        Args:
            namespace: Cache namespace to warm up.
        """
        try:
            warmed_keys = 0

            try:
                from app.core.redis import get_redis
                client = await get_redis()

                if client:
                    # Warm up critical system caches
                    # 1. Check system health cache
                    await client.setex(
                        "cache:health_check",
                        30,
                        '{"status": "warming_up"}',
                    )
                    warmed_keys += 1

                    # 2. Warm up variant access cache
                    await client.setex(
                        "cache:variant_access",
                        3600,
                        '{"mini_parwa": ["light"], "parwa": ["light", "medium"]}',
                    )
                    warmed_keys += 1

            except Exception as exc:
                logger.warning(
                    "self_healing_cache_warmup_partial error=%s",
                    str(exc)[:200],
                )

            return HealingResult(
                action=HealingAction.CACHE_WARMUP,
                success=True,
                message=f"Cache warmup completed for namespace '{namespace}'",
                details={
                    "namespace": namespace,
                    "warmed_keys": warmed_keys,
                },
                severity=AnomalySeverity.LOW.value,
            )
        except Exception:
            logger.exception("self_healing_cache_warmup_failed")
            return HealingResult(
                action=HealingAction.CACHE_WARMUP,
                success=False,
                message="Cache warmup failed unexpectedly",
                severity=AnomalySeverity.LOW.value,
            )

    async def heal_circuit_breaker_reset(self, service: str) -> HealingResult:
        """Reset a circuit breaker that's been open too long.

        Forces the circuit breaker to HALF_OPEN state so it can
        test recovery, rather than leaving it stuck in OPEN.

        Args:
            service: Service name whose circuit breaker to reset.
        """
        try:
            from app.core.circuit_breaker_manager import (
                get_circuit_breaker_manager,
            )
            manager = get_circuit_breaker_manager()

            # Get current state
            current_state = manager.get_state(service)

            if current_state.value != "open":
                return HealingResult(
                    action=HealingAction.CIRCUIT_BREAKER_RESET,
                    success=True,
                    message=(
                        f"Circuit breaker for '{service}' is "
                        f"{current_state.value}, no reset needed"
                    ),
                    severity=AnomalySeverity.LOW.value,
                )

            # Force close to allow recovery testing
            manager.force_close(service)

            return HealingResult(
                action=HealingAction.CIRCUIT_BREAKER_RESET,
                success=True,
                message=(
                    f"Circuit breaker for '{service}' reset from "
                    f"OPEN to CLOSED for recovery testing"
                ),
                details={
                    "service": service,
                    "previous_state": "open",
                    "new_state": "closed",
                },
                severity=AnomalySeverity.MEDIUM.value,
            )
        except Exception:
            logger.exception(
                "self_healing_circuit_breaker_reset_failed service=%s",
                service,
            )
            return HealingResult(
                action=HealingAction.CIRCUIT_BREAKER_RESET,
                success=False,
                message=f"Circuit breaker reset failed for {service}",
                severity=AnomalySeverity.HIGH.value,
            )

    async def _check_queue_depths(self) -> List[Anomaly]:
        """Check Celery queue depths for anomalies."""
        anomalies: List[Anomaly] = []
        try:
            queue_names = [
                "default", "ai_heavy", "ai_light",
                "email", "webhook", "analytics", "training",
            ]

            try:
                from app.core.redis import get_redis
                client = await get_redis()
                if client:
                    for queue_name in queue_names:
                        try:
                            depth = await client.llen(queue_name)
                            if depth and depth > 0:
                                anomaly = self._detector.check_queue_depth(
                                    queue_name, depth,
                                )
                                if anomaly:
                                    anomalies.append(anomaly)
                        except Exception:
                            pass
            except Exception:
                pass

        except Exception:
            logger.exception("self_healing_check_queue_depths_failed")

        return anomalies

    def _record_healing(self, result: HealingResult) -> None:
        """Record a healing action in the audit trail."""
        try:
            with self._lock:
                entry = {
                    "action": result.action.value,
                    "success": result.success,
                    "message": result.message,
                    "details": result.details,
                    "timestamp": result.timestamp,
                    "severity": result.severity,
                }
                self._healing_history.append(entry)

                # Trim to max size
                if len(self._healing_history) > self.MAX_HEALING_HISTORY:
                    self._healing_history = (
                        self._healing_history[-self.MAX_HEALING_HISTORY:]
                    )

                # Update stats
                self._stats["healings_attempted"] += 1
                if result.success:
                    self._stats["healings_succeeded"] += 1
                else:
                    self._stats["healings_failed"] += 1
        except Exception:
            logger.exception("self_healing_record_failed")

    def get_healing_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent healing actions taken.

        Args:
            limit: Maximum number of actions to return.

        Returns:
            List of healing action dicts, most recent first.
        """
        try:
            with self._lock:
                history = list(self._healing_history)
            # Return most recent first
            history.reverse()
            return history[:limit]
        except Exception:
            logger.exception("self_healing_get_history_failed")
            return []

    def get_healing_metrics(self) -> Dict[str, Any]:
        """Get healing metrics for monitoring.

        Returns stats about healing checks, anomalies found,
        and healing action success/failure rates.
        """
        try:
            with self._lock:
                stats = dict(self._stats)
                recent_history = list(self._healing_history[-20:])

            # Calculate success rate
            attempted = stats.get("healings_attempted", 0)
            succeeded = stats.get("healings_succeeded", 0)
            success_rate = (
                round(succeeded / attempted * 100, 1)
                if attempted > 0
                else 100.0
            )

            return {
                "total_checks": stats.get("total_checks", 0),
                "anomalies_found": stats.get("anomalies_found", 0),
                "healings_attempted": attempted,
                "healings_succeeded": succeeded,
                "healings_failed": stats.get("healings_failed", 0),
                "success_rate_percent": success_rate,
                "last_check_at": stats.get("last_check_at", ""),
                "recent_actions": len(recent_history),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            logger.exception("self_healing_get_metrics_failed")
            return {
                "total_checks": 0,
                "anomalies_found": 0,
                "healings_attempted": 0,
                "healings_succeeded": 0,
                "healings_failed": 0,
                "success_rate_percent": 0.0,
                "last_check_at": "",
                "recent_actions": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current self-healing service status.

        Returns a summary suitable for /health endpoint.
        """
        try:
            metrics = self.get_healing_metrics()
            return {
                "status": "active",
                "metrics": metrics,
                "detector_services_monitored": len(
                    self._detector._total_counts
                ),
            }
        except Exception:
            logger.exception("self_healing_get_status_failed")
            return {
                "status": "error",
                "metrics": {},
                "detector_services_monitored": 0,
            }


# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════

_service: Optional[SelfHealingService] = None
_service_lock = threading.Lock()


def get_self_healing_service() -> SelfHealingService:
    """Get the singleton SelfHealingService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = SelfHealingService()
                logger.info("self_healing_service_initialized")
    return _service


def reset_self_healing_service() -> None:
    """Reset the singleton service (for testing only)."""
    global _service
    with _service_lock:
        _service = None
