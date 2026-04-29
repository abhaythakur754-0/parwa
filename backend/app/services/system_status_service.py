"""
PARWA System Status Service (F-088) — Real-time Health Dashboard

Provides real-time health dashboard data for all PARWA subsystems.
Aggregates status from LLM providers, Redis, PostgreSQL, Celery queues,
and external integrations into a unified response.

Features:
- Check health of all PARWA subsystems
- Aggregate status into unified response
- Store health snapshots in Redis with TTL
- Track system incidents (state transitions: healthy→degraded→down)
- Support historical status queries for charting

Methods:
- get_system_status() — Full system health snapshot
- get_status_history() — Historical data for charting
- get_active_incidents() — Unresolved system incidents
- record_incident() — Track state transitions

Building Codes: BC-001 (tenant isolation), BC-005 (real-time),
               BC-008 (graceful degradation), BC-012 (resilience)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.logger import get_logger

logger = get_logger("system_status_service")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Redis TTL for health snapshots (5 minutes)
SNAPSHOT_TTL_SECONDS = 300

# Redis TTL for history entries (24 hours)
HISTORY_TTL_SECONDS = 86400

# Maximum history points to keep per company
MAX_HISTORY_POINTS = 288  # 24h * 12 (every 5 minutes)

# Incident resolution threshold (seconds)
INCIDENT_AUTO_RESOLVE_SECONDS = 3600  # 1 hour

# History collection interval (seconds) — used for gap detection
HISTORY_INTERVAL_SECONDS = 300  # 5 minutes


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class SystemStatusService:
    """System Status Service (F-088) — Real-time Health Dashboard.

    Provides aggregated health status for all PARWA subsystems.
    Health snapshots are cached in Redis with TTL for performance.
    State transitions (healthy→degraded→unhealthy) are tracked as
    system incidents for alerting and analysis.

    BC-001: All methods scoped by company_id.
    BC-005: Real-time health checks.
    BC-008: Graceful degradation — Redis failure does not block.
    BC-012: Structured error responses, UTC timestamps.
    """

    def __init__(self, company_id: str):
        """Initialize the service for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        self.company_id = company_id
        self._redis = None

    # ── Lazy Redis Loading ──────────────────────────────────────

    async def _get_redis(self):
        """Get Redis connection (lazy, with graceful fallback).

        BC-008: Returns None on failure — callers must handle.
        """
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis
            self._redis = await get_redis()
            return self._redis
        except Exception as exc:
            logger.warning(
                "system_status_redis_unavailable",
                company_id=self.company_id,
                error=str(exc),
            )
            return None

    # ── Core Methods ────────────────────────────────────────────

    async def get_system_status(self) -> Dict[str, Any]:
        """Get the full system health status for this tenant.

        Checks all subsystems:
        - LLM providers (via smart_router health tracker)
        - Redis (via redis_health_check)
        - PostgreSQL (via health orchestrator)
        - Celery queues (via celery_health)
        - External integrations

        Results are cached in Redis with 5-minute TTL.

        Returns:
            Dictionary with overall_status, subsystems, timestamps.
        """
        # Try to read from cache first
        cached = await self._get_cached_snapshot()
        if cached is not None:
            return cached

        # Collect fresh health data
        subsystems = {}
        now = datetime.now(timezone.utc)

        # Check LLM providers
        llm_status = await self._check_llm_providers()
        subsystems.update(llm_status)

        # Check Redis
        redis_status = await self._check_redis()
        subsystems["redis"] = redis_status

        # Check PostgreSQL
        pg_status = await self._check_postgresql()
        subsystems["postgresql"] = pg_status

        # Check Celery
        celery_status = await self._check_celery()
        subsystems["celery"] = celery_status

        # Check Celery queues
        queue_status = await self._check_celery_queues()
        subsystems["celery_queues"] = queue_status

        # Check external integrations
        integration_status = await self._check_integrations()
        subsystems.update(integration_status)

        # Calculate aggregate status
        overall = self._calculate_overall_status(subsystems)

        # Build response
        response = {
            "overall_status": overall,
            "subsystems": subsystems,
            "checked_at": now.isoformat(),
            "cached": False,
            "checks_total": len(subsystems),
            "checks_healthy": sum(
                1 for s in subsystems.values()
                if s.get("status") == "healthy"
            ),
            "checks_degraded": sum(
                1 for s in subsystems.values()
                if s.get("status") == "degraded"
            ),
            "checks_unhealthy": sum(
                1 for s in subsystems.values()
                if s.get("status") == "unhealthy"
            ),
        }

        # Cache the snapshot
        await self._cache_snapshot(response)

        # Record status transition (incident detection)
        await self._detect_and_record_incidents(response)

        # Append to history
        await self._append_history_point(response)

        return response

    async def get_status_history(
        self,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Get historical system status data for charting.

        Args:
            from_timestamp: ISO 8601 start time (optional).
            to_timestamp: ISO 8601 end time (optional).
            limit: Maximum number of data points to return.

        Returns:
            Dictionary with points list and metadata.
        """
        redis = await self._get_redis()
        points = []

        if redis is None:
            return self._empty_history_response(from_timestamp, to_timestamp)

        try:
            from app.core.redis import make_key

            history_key = make_key(
                self.company_id, "system_status", "history",
            )

            # Get all history entries
            raw_history = await redis.lrange(history_key, 0, -1)

            for entry in raw_history:
                try:
                    point = json.loads(entry)
                    if point.get("company_id") != self.company_id:
                        continue

                    # Apply time filters
                    if from_timestamp:
                        if point.get("timestamp", "") < from_timestamp:
                            continue
                    if to_timestamp:
                        if point.get("timestamp", "") > to_timestamp:
                            continue

                    points.append({
                        "timestamp": point.get("timestamp", ""),
                        "overall_status": point.get("overall_status", "unknown"),
                        "subsystems_summary": point.get(
                            "subsystems_summary", {},
                        ),
                    })
                except (json.JSONDecodeError, TypeError):
                    continue

            # Sort by timestamp descending
            points.sort(key=lambda x: x["timestamp"], reverse=True)
            points = points[:limit]

        except Exception as exc:
            logger.warning(
                "system_status_history_failed",
                company_id=self.company_id,
                error=str(exc),
            )

        return {
            "company_id": self.company_id,
            "points": points,
            "total_points": len(points),
            "from_timestamp": from_timestamp,
            "to_timestamp": to_timestamp,
        }

    async def get_active_incidents(self) -> Dict[str, Any]:
        """Get all unresolved system incidents.

        Returns:
            Dictionary with incidents list and count.
        """
        redis = await self._get_redis()
        incidents = []

        if redis is None:
            return {"incidents": [], "total": 0}

        try:
            from app.core.redis import make_key

            incidents_key = make_key(
                self.company_id, "system_status", "incidents",
            )
            raw_incidents = await redis.lrange(incidents_key, 0, -1)

            for entry in raw_incidents:
                try:
                    incident = json.loads(entry)
                    # Filter to unresolved
                    if incident.get("resolved_at") is None:
                        incidents.append({
                            "incident_id": incident.get("incident_id", ""),
                            "subsystem": incident.get("subsystem", ""),
                            "previous_status": incident.get(
                                "previous_status", "",
                            ),
                            "current_status": incident.get(
                                "current_status", "",
                            ),
                            "severity": incident.get("severity", "medium"),
                            "description": incident.get("description"),
                            "detected_at": incident.get("detected_at", ""),
                            "resolved_at": None,
                            "metadata": incident.get("metadata", {}),
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

        except Exception as exc:
            logger.warning(
                "system_status_incidents_failed",
                company_id=self.company_id,
                error=str(exc),
            )

        return {"incidents": incidents, "total": len(incidents)}

    async def record_incident(
        self,
        subsystem: str,
        previous_status: str,
        current_status: str,
        severity: str = "medium",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a system incident (state transition).

        Args:
            subsystem: Affected subsystem name.
            previous_status: Status before the transition.
            current_status: Status after the transition.
            severity: Incident severity (low, medium, high, critical).
            description: Optional description.
            metadata: Optional additional context.

        Returns:
            Created incident record.
        """
        now = datetime.now(timezone.utc)
        incident = {
            "incident_id": f"INC-{uuid4().hex[:8].upper()}",
            "company_id": self.company_id,
            "subsystem": subsystem,
            "previous_status": previous_status,
            "current_status": current_status,
            "severity": severity,
            "description": description or (
                f"{subsystem} transitioned from {previous_status} "
                f"to {current_status}"
            ),
            "detected_at": now.isoformat(),
            "resolved_at": None,
            "metadata": metadata or {},
        }

        redis = await self._get_redis()
        if redis is not None:
            try:
                from app.core.redis import make_key

                incidents_key = make_key(
                    self.company_id, "system_status", "incidents",
                )
                await redis.lpush(
                    incidents_key, json.dumps(incident),
                )
                # Keep max 100 incidents
                await redis.ltrim(incidents_key, 0, 99)
                # Auto-resolve previous incidents for this subsystem
                await self._auto_resolve_subsystem_incidents(
                    redis, subsystem,
                )
            except Exception as exc:
                logger.warning(
                    "system_status_record_incident_failed",
                    company_id=self.company_id,
                    error=str(exc),
                )

        logger.info(
            "system_status_incident_recorded",
            company_id=self.company_id,
            incident_id=incident["incident_id"],
            subsystem=subsystem,
            previous_status=previous_status,
            current_status=current_status,
            severity=severity,
        )

        return incident

    # ── Subsystem Health Checks ─────────────────────────────────

    async def _check_llm_providers(self) -> Dict[str, Any]:
        """Check health of all LLM providers via Smart Router."""
        result = {}

        try:
            from app.core.smart_router import SmartRouter

            router = SmartRouter()
            provider_status = router.get_provider_status()

            for registry_key, info in provider_status.items():
                status = "healthy"
                if not info.get("is_healthy", True):
                    status = "unhealthy"
                elif info.get("rate_limited", False):
                    status = "degraded"

                result[registry_key] = {
                    "name": registry_key,
                    "status": status,
                    "latency_ms": 0.0,
                    "details": {
                        "provider": info.get("provider", ""),
                        "daily_count": info.get("daily_count", 0),
                        "daily_limit": info.get("daily_limit", 0),
                        "daily_remaining": info.get("daily_remaining", 0),
                        "consecutive_failures": info.get(
                            "consecutive_failures", 0,
                        ),
                        "last_error": info.get("last_error", ""),
                        "rate_limited": info.get("rate_limited", False),
                    },
                    "is_critical": False,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as exc:
            logger.warning(
                "system_status_llm_check_failed",
                company_id=self.company_id,
                error=str(exc),
            )
            result["llm_providers"] = {
                "name": "llm_providers",
                "status": "unknown",
                "error": str(exc)[:200],
                "is_critical": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        return result

    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health via the core health module."""
        try:
            from app.core.redis import redis_health_check

            health = await redis_health_check()
            return {
                "name": "redis",
                "status": health.get("status", "unknown"),
                "latency_ms": health.get("latency_ms", 0.0),
                "error": health.get("error"),
                "is_critical": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "name": "redis",
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": str(exc)[:200],
                "is_critical": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _check_postgresql(self) -> Dict[str, Any]:
        """Check PostgreSQL health via the core health module."""
        try:
            from app.core.health import check_postgresql

            sub = await check_postgresql()
            return {
                "name": sub.name,
                "status": sub.status,
                "latency_ms": sub.latency_ms,
                "details": sub.details,
                "error": sub.error,
                "is_critical": sub.is_critical,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "name": "postgresql",
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": str(exc)[:200],
                "is_critical": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _check_celery(self) -> Dict[str, Any]:
        """Check Celery health via the core health module."""
        try:
            from app.core.health import check_celery

            sub = await check_celery()
            return {
                "name": sub.name,
                "status": sub.status,
                "latency_ms": sub.latency_ms,
                "details": sub.details,
                "error": sub.error,
                "is_critical": sub.is_critical,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "name": "celery",
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": str(exc)[:200],
                "is_critical": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _check_celery_queues(self) -> Dict[str, Any]:
        """Check Celery queue depths via the core health module."""
        try:
            from app.core.health import check_celery_queues

            sub = await check_celery_queues()
            return {
                "name": sub.name,
                "status": sub.status,
                "latency_ms": sub.latency_ms,
                "details": sub.details,
                "error": sub.error,
                "is_critical": sub.is_critical,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "name": "celery_queues",
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": str(exc)[:200],
                "is_critical": False,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _check_integrations(self) -> Dict[str, Any]:
        """Check external integration health."""
        result = {}

        integrations = [
            ("paddle", "https://vendors.paddle.com"),
            ("brevo", "https://api.brevo.com"),
            ("twilio", "https://api.twilio.com"),
        ]

        for name, url in integrations:
            try:
                from app.core.health import check_external_service

                sub = await check_external_service(
                    f"integration_{name}", url,
                )
                result[f"integration_{name}"] = {
                    "name": f"integration_{name}",
                    "status": sub.status,
                    "latency_ms": sub.latency_ms,
                    "error": sub.error,
                    "is_critical": False,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                result[f"integration_{name}"] = {
                    "name": f"integration_{name}",
                    "status": "unknown",
                    "error": str(exc)[:200],
                    "is_critical": False,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

        return result

    # ── Aggregation & Caching ────────────────────────────────────

    @staticmethod
    def _calculate_overall_status(subsystems: Dict[str, Any]) -> str:
        """Calculate aggregate status from subsystem statuses.

        Rules:
        - If any critical subsystem is unhealthy → unhealthy
        - If any non-critical is unhealthy → degraded
        - If any subsystem is degraded → degraded
        - Otherwise → healthy
        """
        has_critical_unhealthy = False
        has_non_critical_unhealthy = False
        has_degraded = False

        for info in subsystems.values():
            status = info.get("status", "unknown")
            is_critical = info.get("is_critical", False)

            if status == "unhealthy" and is_critical:
                has_critical_unhealthy = True
            elif status == "unhealthy":
                has_non_critical_unhealthy = True
            elif status == "degraded":
                has_degraded = True

        if has_critical_unhealthy:
            return "unhealthy"
        if has_non_critical_unhealthy or has_degraded:
            return "degraded"
        return "healthy"

    async def _get_cached_snapshot(self) -> Optional[Dict[str, Any]]:
        """Try to read the last health snapshot from Redis cache."""
        redis = await self._get_redis()
        if redis is None:
            return None

        try:
            from app.core.redis import make_key

            key = make_key(self.company_id, "system_status", "snapshot")
            raw = await redis.get(key)
            if raw:
                data = json.loads(raw)
                data["cached"] = True
                return data
        except Exception:
            pass

        return None

    async def _cache_snapshot(self, response: Dict[str, Any]) -> None:
        """Store health snapshot in Redis with TTL."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            key = make_key(self.company_id, "system_status", "snapshot")
            await redis.set(
                key, json.dumps(response), ex=SNAPSHOT_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "system_status_cache_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    async def _append_history_point(self, response: Dict[str, Any]) -> None:
        """Append a status data point to the history timeline."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            history_key = make_key(
                self.company_id, "system_status", "history",
            )

            # Build subsystems summary
            subsystems_summary = {}
            for name, info in response.get("subsystems", {}).items():
                subsystems_summary[name] = info.get("status", "unknown")

            point = {
                "company_id": self.company_id,
                "timestamp": response.get("checked_at", ""),
                "overall_status": response.get("overall_status", "unknown"),
                "subsystems_summary": subsystems_summary,
            }

            await redis.lpush(
                history_key, json.dumps(point),
            )
            # Trim to max history points
            await redis.ltrim(history_key, 0, MAX_HISTORY_POINTS - 1)
            # Set TTL on the key
            await redis.expire(history_key, HISTORY_TTL_SECONDS)

        except Exception as exc:
            logger.warning(
                "system_status_history_append_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    # ── Incident Detection ──────────────────────────────────────

    async def _detect_and_record_incidents(
        self, response: Dict[str, Any],
    ) -> None:
        """Detect state transitions and record incidents."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            prev_key = make_key(
                self.company_id, "system_status", "prev_snapshot",
            )
            raw_prev = await redis.get(prev_key)

            if raw_prev is None:
                # First check — no previous state to compare
                await redis.set(
                    prev_key,
                    json.dumps(response.get("subsystems", {})),
                    ex=SNAPSHOT_TTL_SECONDS,
                )
                return

            prev_subsystems = json.loads(raw_prev)
            current_subsystems = response.get("subsystems", {})

            # Detect transitions
            all_names = set(prev_subsystems.keys()) | set(
                current_subsystems.keys(),
            )
            for name in all_names:
                prev_status = prev_subsystems.get(name, {}).get(
                    "status", "unknown",
                )
                curr_status = current_subsystems.get(name, {}).get(
                    "status", "unknown",
                )

                # Skip if no change
                if prev_status == curr_status:
                    continue

                # Skip if transitioning to "healthy" (resolve)
                if curr_status == "healthy":
                    await self._resolve_subsystem_incident(
                        redis, name,
                    )
                    continue

                # Determine severity
                severity = "medium"
                if curr_status == "unhealthy":
                    is_critical = current_subsystems.get(name, {}).get(
                        "is_critical", False,
                    )
                    severity = "critical" if is_critical else "high"
                elif curr_status == "degraded":
                    severity = "low"

                await self.record_incident(
                    subsystem=name,
                    previous_status=prev_status,
                    current_status=curr_status,
                    severity=severity,
                )

            # Update previous snapshot
            await redis.set(
                prev_key,
                json.dumps(current_subsystems),
                ex=SNAPSHOT_TTL_SECONDS,
            )

        except Exception as exc:
            logger.warning(
                "system_status_incident_detection_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    async def _auto_resolve_subsystem_incidents(
        self, redis, subsystem: str,
    ) -> None:
        """Auto-resolve previous incidents for a subsystem."""
        try:
            from app.core.redis import make_key

            incidents_key = make_key(
                self.company_id, "system_status", "incidents",
            )
            raw_incidents = await redis.lrange(incidents_key, 0, -1)

            updated = []
            for entry in raw_incidents:
                try:
                    incident = json.loads(entry)
                    if (
                        incident.get("subsystem") == subsystem
                        and incident.get("resolved_at") is None
                    ):
                        incident["resolved_at"] = datetime.now(
                            timezone.utc,
                        ).isoformat()
                    updated.append(json.dumps(incident))
                except (json.JSONDecodeError, TypeError):
                    updated.append(entry)

            if updated:
                await redis.delete(incidents_key)
                if updated:
                    await redis.rpush(incidents_key, *updated)

        except Exception as exc:
            logger.warning(
                "system_status_auto_resolve_failed",
                company_id=self.company_id,
                subsystem=subsystem,
                error=str(exc),
            )

    async def _resolve_subsystem_incident(
        self, redis, subsystem: str,
    ) -> None:
        """Mark incidents for a subsystem as resolved."""
        await self._auto_resolve_subsystem_incidents(redis, subsystem)

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _empty_history_response(
        from_ts: Optional[str], to_ts: Optional[str],
    ) -> Dict[str, Any]:
        """Return an empty history response."""
        return {
            "company_id": "",
            "points": [],
            "total_points": 0,
            "from_timestamp": from_ts,
            "to_timestamp": to_ts,
        }


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_service_cache: Dict[str, SystemStatusService] = {}


def get_system_status_service(company_id: str) -> SystemStatusService:
    """Get or create a SystemStatusService for a tenant.

    Uses lazy loading pattern per jarvis_service.py.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        SystemStatusService instance.
    """
    if company_id not in _service_cache:
        _service_cache[company_id] = SystemStatusService(company_id)
    return _service_cache[company_id]


__all__ = [
    "SystemStatusService",
    "get_system_status_service",
]
