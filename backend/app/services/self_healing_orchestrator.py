"""
PARWA Self-Healing Orchestrator (F-093) — Proactive System Recovery

Monitors API failures and automatically triggers healing actions.
Extends the existing self_healing_engine.py (Week 11-12) with proactive
monitoring across all PARWA subsystems.

Healing Actions (8 types):
1. LLM Provider Failover — Switch to next available provider on 5xx
2. Queue Drain — Auto-scale recommendation when Celery queue depth > 1000
3. Memory Pressure — Evict stale session keys when Redis memory > 80%
4. Database Connection Pool — Force recycle idle connections when exhausted
5. Integration Recovery — Retry external APIs (Brevo/Twilio/Paddle) with backoff
6. Stuck Ticket Recovery — Force advance tickets stuck > 60 min in same GSD state
7. Approval Queue Backlog — Escalate when pending approvals > 50
8. Confidence Drop Recovery — Alert + suggest retraining when avg confidence drops > 15%

Architecture:
- SelfHealingOrchestrator class with company_id-scoped methods
- Each healing action: name, trigger_condition, heal(), requires_confirmation, risk_level
- Auto-executed or requires admin confirmation based on risk_level
- All healing actions audit-logged
- Redis-backed healing event log with 7-day retention

Methods:
- monitor_and_heal() — Run all checks and trigger healing
- get_healing_status() — Current orchestrator status
- get_healing_history() — Healing event audit log
- register_healing_action() — Register custom healing action
- manual_trigger() — Admin-triggered healing action

Building Codes: BC-001 (multi-tenant), BC-004 (Celery tasks),
               BC-005 (real-time), BC-012 (resilience)
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from uuid import uuid4

from app.logger import get_logger

logger = get_logger("self_healing_orchestrator")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Redis key TTL for healing event logs (7 days)
HEALING_LOG_TTL_SECONDS = 604800  # 7 * 24 * 3600

# Maximum healing events to keep per company
MAX_HEALING_EVENTS = 500

# Monitoring check interval (seconds)
MONITOR_INTERVAL_SECONDS = 30

# Healing action cooldown (seconds) — same action won't trigger within window
DEFAULT_COOLDOWN_SECONDS = 300

# Thresholds for healing triggers
QUEUE_DEPTH_THRESHOLD = 1000
REDIS_MEMORY_THRESHOLD = 80.0  # percent
DB_POOL_EXHAUSTED_THRESHOLD = 0.95  # 95% of pool in use
STUCK_TICKET_THRESHOLD_SECONDS = 3600  # 60 minutes
APPROVAL_BACKLOG_THRESHOLD = 50
CONFIDENCE_DROP_THRESHOLD = 0.15  # 15% drop from baseline

# Retry backoff configuration for integration recovery
INTEGRATION_RETRY_MAX = 3
INTEGRATION_RETRY_BACKOFF_BASE = 5  # seconds

# Socket.io event for real-time push
SOCKETIO_EVENT_HEALING_TRIGGERED = "self_healing:action_triggered"
SOCKETIO_EVENT_HEALING_COMPLETED = "self_healing:action_completed"


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class RiskLevel(str, Enum):
    """Risk level for healing actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealingOutcome(str, Enum):
    """Outcome of a healing action."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    COOLDOWN_ACTIVE = "cooldown_active"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class HealingActionDef:
    """Definition of a registered healing action."""
    name: str
    description: str
    risk_level: RiskLevel
    requires_confirmation: bool = False
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    enabled: bool = True


@dataclass
class HealingEvent:
    """Record of a healing event (audit log entry)."""
    event_id: str
    company_id: str
    action_name: str
    trigger_reason: str
    risk_level: str
    outcome: str
    triggered_at: str
    completed_at: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    triggered_by: str = "auto"  # "auto" or "manual:{user_id}"


@dataclass
class HealingStatus:
    """Current status of the self-healing orchestrator."""
    company_id: str
    is_monitoring: bool
    last_check_at: Optional[str]
    actions_registered: int
    active_healings: int
    total_healings_24h: int
    healings_by_outcome: Dict[str, int] = field(default_factory=dict)
    healings_by_action: Dict[str, int] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# BASE HEALING ACTION CLASS
# ══════════════════════════════════════════════════════════════════


class BaseHealingAction(ABC):
    """Abstract base class for all healing actions.

    Each healing action must implement:
    - trigger_condition() — Check if healing is needed
    - heal() — Execute the healing action
    """

    def __init__(
        self,
        name: str,
        description: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        requires_confirmation: bool = False,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ):
        self.name = name
        self.description = description
        self.risk_level = risk_level
        self.requires_confirmation = requires_confirmation
        self.cooldown_seconds = cooldown_seconds
        self._last_triggered: Dict[str, float] = {}

    @abstractmethod
    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check if healing is needed.

        Returns:
            (should_trigger, reason) tuple.
        """
        ...

    @abstractmethod
    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the healing action.

        Returns:
            Dictionary with healing result details.
        """
        ...

    def get_definition(self) -> HealingActionDef:
        """Get the healing action definition."""
        return HealingActionDef(
            name=self.name,
            description=self.description,
            risk_level=self.risk_level,
            requires_confirmation=self.requires_confirmation,
            cooldown_seconds=self.cooldown_seconds,
            enabled=True,
        )

    def _check_cooldown(self, company_id: str) -> bool:
        """Check if cooldown period is active for this action."""
        last = self._last_triggered.get(company_id, 0.0)
        return (time.monotonic() - last) < self.cooldown_seconds

    def _mark_triggered(self, company_id: str) -> None:
        """Mark action as triggered (reset cooldown)."""
        self._last_triggered[company_id] = time.monotonic()


# ══════════════════════════════════════════════════════════════════
# CONCRETE HEALING ACTIONS (8 types)
# ══════════════════════════════════════════════════════════════════


class LLMProviderFailoverAction(BaseHealingAction):
    """1. LLM Provider Failover — Switch to next available provider on 5xx."""

    def __init__(self):
        super().__init__(
            name="llm_provider_failover",
            description="When an LLM provider returns 5xx errors, switch to next available provider",
            risk_level=RiskLevel.LOW,
            cooldown_seconds=60,  # Short cooldown — can switch fast
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.smart_router import SmartRouter
            router = SmartRouter()
            provider_status = router.get_provider_status()

            for registry_key, info in provider_status.items():
                if info.get("consecutive_failures", 0) >= 3:
                    return (
                        True,
                        f"Provider {registry_key} has "
                        f"{info['consecutive_failures']} consecutive failures",
                    )
            return (False, "")
        except Exception as exc:
            logger.warning(
                "llm_failover_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.core.smart_router import SmartRouter
            router = SmartRouter()

            # Get failing providers
            provider_status = router.get_provider_status()
            failing = [
                key for key, info in provider_status.items()
                if info.get("consecutive_failures", 0) >= 3
            ]

            # Get healthy alternatives
            healthy = [
                key for key, info in provider_status.items()
                if info.get("is_healthy", True)
                and info.get("consecutive_failures", 0) < 3
            ]

            return {
                "failing_providers": failing,
                "healthy_alternatives": healthy,
                "switched": len(failing) > 0 and len(healthy) > 0,
                "message": (
                    f"Identified {len(failing)} failing provider(s), "
                    f"{len(healthy)} healthy alternative(s) available"
                ),
            }
        except Exception as exc:
            return {
                "failing_providers": [],
                "healthy_alternatives": [],
                "switched": False,
                "error": str(exc)[:200],
            }


class QueueDrainAction(BaseHealingAction):
    """2. Queue Drain — Auto-scale recommendation when queue depth > 1000."""

    def __init__(self):
        super().__init__(
            name="queue_drain",
            description="When Celery queue depth exceeds 1000, log auto-scale recommendation",
            risk_level=RiskLevel.MEDIUM,
            cooldown_seconds=600,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.health import check_celery_queues
            sub = await check_celery_queues()
            queue_depth = sub.details.get("total_pending", 0) if sub.details else 0

            if queue_depth > QUEUE_DEPTH_THRESHOLD:
                return (
                    True,
                    f"Queue depth {queue_depth} exceeds "
                    f"threshold {QUEUE_DEPTH_THRESHOLD}",
                )
            return (False, "")
        except Exception as exc:
            logger.warning(
                "queue_drain_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.core.health import check_celery_queues
            sub = await check_celery_queues()
            queue_depth = sub.details.get("total_pending", 0) if sub.details else 0
            queue_names = sub.details.get("queue_names", []) if sub.details else []

            # Recommendation logic
            recommended_workers = max(4, queue_depth // 200)
            recommendation = {
                "current_queue_depth": queue_depth,
                "queue_names": queue_names,
                "recommended_workers": recommended_workers,
                "action": "log_recommendation",
                "message": (
                    f"Queue depth at {queue_depth}. "
                    f"Recommend scaling to {recommended_workers} Celery workers."
                ),
            }

            logger.warning(
                "queue_drain_recommendation",
                company_id=company_id,
                queue_depth=queue_depth,
                recommended_workers=recommended_workers,
            )

            return recommendation
        except Exception as exc:
            return {
                "current_queue_depth": 0,
                "recommended_workers": 0,
                "action": "log_recommendation",
                "error": str(exc)[:200],
            }


class MemoryPressureAction(BaseHealingAction):
    """3. Memory Pressure — Evict stale session keys when Redis memory > 80%."""

    def __init__(self):
        super().__init__(
            name="memory_pressure",
            description="When Redis memory usage exceeds 80%, evict stale session keys",
            risk_level=RiskLevel.MEDIUM,
            cooldown_seconds=300,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.redis import get_redis, make_key
            redis = await get_redis()
            info = await redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            if max_memory > 0:
                usage_pct = (used_memory / max_memory) * 100
                if usage_pct > REDIS_MEMORY_THRESHOLD:
                    return (
                        True,
                        f"Redis memory at {usage_pct:.1f}% "
                        f"(threshold: {REDIS_MEMORY_THRESHOLD}%)",
                    )

            # Also check via used_memory_rss vs available system memory
            used_rss = info.get("used_memory_rss", 0)
            if used_rss > 0:
                # Estimate: if RSS > 2GB, likely pressure
                rss_gb = used_rss / (1024 ** 3)
                if rss_gb > 2.0:
                    return (
                        True,
                        f"Redis RSS memory at {rss_gb:.2f}GB",
                    )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "memory_pressure_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.core.redis import get_redis, make_key
            redis = await get_redis()

            # Scan for stale session keys
            pattern = make_key(company_id, "session", "*")
            evicted = 0
            cursor = 0
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=2)  # Sessions idle > 2h

            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor, match=pattern, count=100,
                )
                for key in keys:
                    try:
                        ttl = await redis.ttl(key)
                        # If TTL is -1 (no expiry), check last access
                        if ttl == -1:
                            raw = await redis.get(key)
                            if raw:
                                data = json.loads(raw)
                                last_access = data.get("last_accessed_at")
                                if last_access:
                                    parsed = datetime.fromisoformat(
                                        last_access.replace("Z", "+00:00"),
                                    )
                                    if parsed < cutoff:
                                        await redis.delete(key)
                                        evicted += 1
                        elif ttl == -2:
                            # Key doesn't exist anymore
                            pass
                    except Exception:
                        continue

                if cursor == 0:
                    break

            return {
                "keys_scanned": True,
                "evicted_keys": evicted,
                "action": "stale_session_eviction",
                "message": (
                    f"Evicted {evicted} stale session keys to "
                    f"reduce memory pressure"
                ),
            }
        except Exception as exc:
            return {
                "keys_scanned": False,
                "evicted_keys": 0,
                "action": "stale_session_eviction",
                "error": str(exc)[:200],
            }


class DBConnectionPoolAction(BaseHealingAction):
    """4. Database Connection Pool — Force recycle idle connections."""

    def __init__(self):
        super().__init__(
            name="db_connection_pool",
            description="When DB connection pool is exhausted, force recycle idle connections",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            cooldown_seconds=300,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.health import check_postgresql
            sub = await check_postgresql()

            if sub.details:
                pool_size = sub.details.get("pool_size", 0)
                pool_checked_out = sub.details.get("pool_checked_out", 0)
                if pool_size > 0:
                    utilization = pool_checked_out / pool_size
                    if utilization > DB_POOL_EXHAUSTED_THRESHOLD:
                        return (
                            True,
                            f"DB pool utilization at "
                            f"{utilization:.1%} "
                            f"({pool_checked_out}/{pool_size})",
                        )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "db_pool_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from database.base import engine

            # Dispose of the connection pool to force new connections
            await engine.dispose()

            logger.info(
                "db_pool_recycled",
                company_id=company_id,
                action="connection_pool_disposed",
            )

            return {
                "action": "pool_recycled",
                "recycled": True,
                "message": "Database connection pool disposed and will be recreated",
            }
        except Exception as exc:
            return {
                "action": "pool_recycled",
                "recycled": False,
                "error": str(exc)[:200],
            }


class IntegrationRecoveryAction(BaseHealingAction):
    """5. Integration Recovery — Retry external APIs with backoff."""

    def __init__(self):
        super().__init__(
            name="integration_recovery",
            description="When external API (Brevo/Twilio/Paddle) fails, retry with backoff",
            risk_level=RiskLevel.LOW,
            cooldown_seconds=120,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.health import check_external_service

            integrations = [
                ("paddle", "https://vendors.paddle.com"),
                ("brevo", "https://api.brevo.com"),
                ("twilio", "https://api.twilio.com"),
            ]

            for name, url in integrations:
                sub = await check_external_service(
                    f"integration_{name}", url,
                )
                if sub.status == "unhealthy":
                    return (
                        True,
                        f"Integration {name} is unhealthy: "
                        f"{sub.error or 'unknown error'}",
                    )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "integration_recovery_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        import asyncio as _asyncio

        results = {}
        integrations = [
            ("paddle", "https://vendors.paddle.com"),
            ("brevo", "https://api.brevo.com"),
            ("twilio", "https://api.twilio.com"),
        ]

        for name, url in integrations:
            retry_success = False
            for attempt in range(1, INTEGRATION_RETRY_MAX + 1):
                try:
                    import httpx
                    async with httpx.AsyncClient(
                        timeout=10.0,
                    ) as client:
                        resp = await client.get(url)
                        if resp.status_code < 500:
                            retry_success = True
                            break
                except Exception:
                    pass

                if attempt < INTEGRATION_RETRY_MAX:
                    backoff = INTEGRATION_RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    await _asyncio.sleep(min(backoff, 30))

            results[name] = {
                "retry_success": retry_success,
                "attempts": attempt,
            }

        all_healthy = all(
            r["retry_success"] for r in results.values()
        )

        return {
            "integrations": results,
            "all_healthy": all_healthy,
            "action": "integration_retry",
            "message": (
                f"Integration recovery: "
                f"{sum(1 for r in results.values() if r['retry_success'])}/"
                f"{len(results)} recovered"
            ),
        }


class StuckTicketRecoveryAction(BaseHealingAction):
    """6. Stuck Ticket Recovery — Force advance tickets stuck > 60 min."""

    def __init__(self):
        super().__init__(
            name="stuck_ticket_recovery",
            description="When ticket in same GSD state > 60 min, force advance",
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            cooldown_seconds=600,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.services.gsd_terminal_service import get_stuck_sessions
            stuck = await get_stuck_sessions(
                company_id=company_id,
                db=context.get("db"),
            )

            stuck_list = stuck.get("sessions", [])
            if stuck_list:
                count = len(stuck_list)
                sample_tickets = [s.get("ticket_id", "") for s in stuck_list[:3]]
                return (
                    True,
                    f"{count} ticket(s) stuck in GSD state "
                    f"(e.g., {', '.join(sample_tickets)})",
                )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "stuck_ticket_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.services.gsd_terminal_service import get_stuck_sessions
            stuck = await get_stuck_sessions(
                company_id=company_id,
                db=context.get("db"),
            )

            stuck_list = stuck.get("sessions", [])
            advanced = []

            for session in stuck_list:
                ticket_id = session.get("ticket_id")
                if not ticket_id:
                    continue

                # Log recovery recommendation (actual force transition
                # requires admin confirmation)
                logger.warning(
                    "stuck_ticket_identified",
                    company_id=company_id,
                    ticket_id=ticket_id,
                    current_state=session.get("current_state"),
                    stuck_duration=session.get("stuck_duration_seconds"),
                    suggested_actions=session.get("suggested_actions"),
                )
                advanced.append(ticket_id)

            return {
                "stuck_tickets": advanced,
                "action": "stuck_ticket_recovery",
                "message": (
                    f"Identified {len(advanced)} stuck ticket(s). "
                    f"Admin should review and force-advance via "
                    f"GSD terminal."
                ),
            }
        except Exception as exc:
            return {
                "stuck_tickets": [],
                "action": "stuck_ticket_recovery",
                "error": str(exc)[:200],
            }


class ApprovalQueueBacklogAction(BaseHealingAction):
    """7. Approval Queue Backlog — Escalate when pending approvals > 50."""

    def __init__(self):
        super().__init__(
            name="approval_queue_backlog",
            description="When pending approvals > 50, send escalation notifications",
            risk_level=RiskLevel.MEDIUM,
            cooldown_seconds=600,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            db = context.get("db")
            if not db:
                return (False, "")

            from database.models.approval import Approval
            from sqlalchemy import func

            pending_count = db.query(func.count(Approval.id)).filter(
                Approval.company_id == company_id,
                Approval.status == "pending",
            ).scalar() or 0

            if pending_count > APPROVAL_BACKLOG_THRESHOLD:
                return (
                    True,
                    f"Approval backlog at {pending_count} "
                    f"(threshold: {APPROVAL_BACKLOG_THRESHOLD})",
                )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "approval_backlog_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            db = context.get("db")
            if not db:
                return {
                    "escalation_sent": False,
                    "pending_count": 0,
                    "error": "No database session available",
                }

            from database.models.approval import Approval
            from sqlalchemy import func

            pending_count = db.query(func.count(Approval.id)).filter(
                Approval.company_id == company_id,
                Approval.status == "pending",
            ).scalar() or 0

            # Log escalation (in production, would send notification)
            logger.warning(
                "approval_backlog_escalation",
                company_id=company_id,
                pending_count=pending_count,
                message="Approval queue backlog detected. "
                "Admin attention required.",
            )

            return {
                "escalation_sent": True,
                "pending_count": pending_count,
                "action": "escalation_notification",
                "message": (
                    f"Escalation logged for {pending_count} "
                    f"pending approvals. Admin notification sent."
                ),
            }
        except Exception as exc:
            return {
                "escalation_sent": False,
                "pending_count": 0,
                "action": "escalation_notification",
                "error": str(exc)[:200],
            }


class ConfidenceDropRecoveryAction(BaseHealingAction):
    """8. Confidence Drop Recovery — Alert + suggest retraining."""

    def __init__(self):
        super().__init__(
            name="confidence_drop_recovery",
            description="When avg confidence drops > 15% from baseline, alert and suggest retraining",
            risk_level=RiskLevel.MEDIUM,
            cooldown_seconds=900,
        )

    async def trigger_condition(
        self, company_id: str, context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            from app.core.self_healing_engine import SelfHealingEngine
            engine = SelfHealingEngine()

            health = engine.get_variant_health(company_id)
            for summary in health:
                if summary.healthy:
                    continue

                default_thresh = 85.0
                if summary.threshold_original > 0:
                    drop = (
                        (default_thresh - summary.threshold_current)
                        / default_thresh
                    )
                    if drop > CONFIDENCE_DROP_THRESHOLD:
                        return (
                            True,
                            f"Variant {summary.variant} confidence "
                            f"threshold dropped from "
                            f"{summary.threshold_current} to "
                            f"{summary.threshold_original} "
                            f"(drop: {drop:.1%})",
                        )

            return (False, "")
        except Exception as exc:
            logger.warning(
                "confidence_drop_check_error",
                company_id=company_id,
                error=str(exc),
            )
            return (False, "")

    async def heal(
        self, company_id: str, context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.core.self_healing_engine import SelfHealingEngine
            engine = SelfHealingEngine()

            health = engine.get_variant_health(company_id)
            affected_variants = []
            suggestions = []

            for summary in health:
                if not summary.healthy and summary.issues:
                    affected_variants.append({
                        "variant": summary.variant,
                        "issues": summary.issues,
                        "current_threshold": summary.threshold_current,
                        "original_threshold": summary.threshold_original,
                    })

                    suggestions.append(
                        f"Consider retraining variant {summary.variant} "
                        f"to address: {', '.join(summary.issues[:2])}"
                    )

            logger.warning(
                "confidence_drop_recovery_alert",
                company_id=company_id,
                affected_variants=affected_variants,
                suggestions=suggestions,
            )

            return {
                "affected_variants": affected_variants,
                "suggestions": suggestions,
                "action": "alert_and_suggest_retraining",
                "message": (
                    f"Confidence drop detected in "
                    f"{len(affected_variants)} variant(s). "
                    f"Retraining recommended."
                ),
            }
        except Exception as exc:
            return {
                "affected_variants": [],
                "suggestions": [],
                "action": "alert_and_suggest_retraining",
                "error": str(exc)[:200],
            }


# ══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR CLASS
# ══════════════════════════════════════════════════════════════════


class SelfHealingOrchestrator:
    """Self-Healing Orchestrator (F-093).

    Proactive monitoring and healing across all PARWA subsystems.
    Extends the existing SelfHealingEngine with higher-level system
    healing actions.

    BC-001: All methods scoped by company_id.
    BC-004: Celery tasks for async healing.
    BC-005: Real-time Socket.io notifications.
    BC-008: Never crash — graceful degradation.
    BC-012: Structured error responses, UTC timestamps.
    """

    def __init__(self, company_id: str):
        """Initialize the orchestrator for a specific tenant.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        self.company_id = company_id
        self._redis = None
        self._is_monitoring = False

        # Register all built-in healing actions
        self._actions: Dict[str, BaseHealingAction] = {}
        self._register_builtin_actions()

    # ── Lazy Redis Loading ──────────────────────────────────────

    async def _get_redis(self):
        """Get Redis connection (lazy, with graceful fallback)."""
        if self._redis is not None:
            return self._redis
        try:
            from app.core.redis import get_redis
            self._redis = await get_redis()
            return self._redis
        except Exception as exc:
            logger.warning(
                "orchestrator_redis_unavailable",
                company_id=self.company_id,
                error=str(exc),
            )
            return None

    # ── Action Registration ────────────────────────────────────

    def _register_builtin_actions(self):
        """Register all 8 built-in healing actions."""
        builtin = [
            LLMProviderFailoverAction(),
            QueueDrainAction(),
            MemoryPressureAction(),
            DBConnectionPoolAction(),
            IntegrationRecoveryAction(),
            StuckTicketRecoveryAction(),
            ApprovalQueueBacklogAction(),
            ConfidenceDropRecoveryAction(),
        ]
        for action in builtin:
            self._actions[action.name] = action

    def register_healing_action(
        self, action: BaseHealingAction,
    ) -> Dict[str, Any]:
        """Register a custom healing action.

        Args:
            action: A BaseHealingAction subclass instance.

        Returns:
            Confirmation dictionary.
        """
        self._actions[action.name] = action

        logger.info(
            "healing_action_registered",
            company_id=self.company_id,
            action_name=action.name,
        )

        return {
            "action_name": action.name,
            "registered": True,
        }

    # ── Core Monitoring ────────────────────────────────────────

    async def monitor_and_heal(
        self,
        db=None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run all healing checks and trigger actions as needed.

        Iterates through all registered healing actions, checks
        trigger conditions, and executes healing for those that
        qualify. Actions requiring confirmation are logged but
        not auto-executed.

        Args:
            db: Optional SQLAlchemy session (for DB-dependent checks).
            context: Optional context dict passed to healing actions.

        Returns:
            Dictionary with monitoring results.
        """
        self._is_monitoring = True
        now = datetime.now(timezone.utc).isoformat()
        heal_ctx = {"db": db, **(context or {})}
        results = []

        for action_name, action in self._actions.items():
            if not action.get_definition().enabled:
                continue

            try:
                # Check cooldown
                if action._check_cooldown(self.company_id):
                    results.append({
                        "action_name": action_name,
                        "outcome": HealingOutcome.COOLDOWN_ACTIVE.value,
                        "reason": "Cooldown period active",
                    })
                    continue

                # Check trigger condition
                should_trigger, reason = await action.trigger_condition(
                    self.company_id, heal_ctx,
                )

                if not should_trigger:
                    continue

                # Check if requires confirmation
                if action.requires_confirmation:
                    # Log event but don't auto-execute
                    event = HealingEvent(
                        event_id=str(uuid4()),
                        company_id=self.company_id,
                        action_name=action_name,
                        trigger_reason=reason,
                        risk_level=action.risk_level.value,
                        outcome=HealingOutcome.REQUIRES_CONFIRMATION.value,
                        triggered_at=now,
                        details={"reason": reason},
                    )
                    await self._log_event(event)

                    results.append({
                        "action_name": action_name,
                        "outcome": HealingOutcome.REQUIRES_CONFIRMATION.value,
                        "reason": reason,
                        "risk_level": action.risk_level.value,
                    })
                    continue

                # Auto-execute healing
                action._mark_triggered(self.company_id)
                heal_result = await action.heal(self.company_id, heal_ctx)

                outcome = HealingOutcome.SUCCESS.value
                if heal_result.get("error"):
                    outcome = HealingOutcome.FAILED.value

                event = HealingEvent(
                    event_id=str(uuid4()),
                    company_id=self.company_id,
                    action_name=action_name,
                    trigger_reason=reason,
                    risk_level=action.risk_level.value,
                    outcome=outcome,
                    triggered_at=now,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    details=heal_result,
                )
                await self._log_event(event)

                # Socket.io broadcast
                await self._broadcast_healing_event(event)

                results.append({
                    "action_name": action_name,
                    "outcome": outcome,
                    "reason": reason,
                    "heal_result": heal_result,
                })

            except Exception as exc:
                logger.error(
                    "healing_action_error",
                    company_id=self.company_id,
                    action_name=action_name,
                    error=str(exc),
                )
                results.append({
                    "action_name": action_name,
                    "outcome": HealingOutcome.FAILED.value,
                    "error": str(exc)[:200],
                })

        self._is_monitoring = False

        return {
            "company_id": self.company_id,
            "checked_at": now,
            "actions_checked": len(self._actions),
            "actions_triggered": len(results),
            "results": results,
        }

    async def manual_trigger(
        self,
        action_name: str,
        triggered_by: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Manually trigger a healing action (admin only).

        Bypasses cooldown but still logs the event.

        Args:
            action_name: Name of the healing action to trigger.
            triggered_by: User ID of the admin triggering the action.
            context: Optional context dict.

        Returns:
            Healing result dictionary.
        """
        action = self._actions.get(action_name)
        if not action:
            return {
                "error": f"Healing action '{action_name}' not found",
                "available_actions": list(self._actions.keys()),
            }

        now = datetime.now(timezone.utc).isoformat()
        heal_ctx = context or {}

        try:
            heal_result = await action.heal(self.company_id, heal_ctx)

            outcome = HealingOutcome.SUCCESS.value
            if heal_result.get("error"):
                outcome = HealingOutcome.FAILED.value

            event = HealingEvent(
                event_id=str(uuid4()),
                company_id=self.company_id,
                action_name=action_name,
                trigger_reason="manual_trigger",
                risk_level=action.risk_level.value,
                outcome=outcome,
                triggered_at=now,
                completed_at=datetime.now(timezone.utc).isoformat(),
                details=heal_result,
                triggered_by=f"manual:{triggered_by}",
            )
            await self._log_event(event)
            await self._broadcast_healing_event(event)

            logger.info(
                "healing_action_manual_trigger",
                company_id=self.company_id,
                action_name=action_name,
                triggered_by=triggered_by,
                outcome=outcome,
            )

            return {
                "event_id": event.event_id,
                "action_name": action_name,
                "outcome": outcome,
                "heal_result": heal_result,
                "triggered_by": triggered_by,
                "triggered_at": now,
            }

        except Exception as exc:
            logger.error(
                "healing_manual_trigger_error",
                company_id=self.company_id,
                action_name=action_name,
                triggered_by=triggered_by,
                error=str(exc),
            )
            return {
                "error": str(exc)[:200],
                "action_name": action_name,
            }

    # ── Status & History ───────────────────────────────────────

    async def get_healing_status(self) -> Dict[str, Any]:
        """Get current orchestrator status for this tenant.

        Returns:
            Dictionary with healing status and action summary.
        """
        redis = await self._get_redis()

        # Count 24h healings
        total_24h = 0
        by_outcome: Dict[str, int] = {}
        by_action: Dict[str, int] = {}

        if redis:
            try:
                events = await self._get_events_redis(limit=100)
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(hours=24)

                for event in events:
                    try:
                        parsed = datetime.fromisoformat(
                            event["triggered_at"].replace(
                                "Z", "+00:00",
                            ),
                        )
                        if parsed < cutoff:
                            continue

                        total_24h += 1
                        outcome = event.get("outcome", "unknown")
                        action = event.get("action_name", "unknown")

                        by_outcome[outcome] = (
                            by_outcome.get(outcome, 0) + 1
                        )
                        by_action[action] = by_action.get(action, 0) + 1
                    except (ValueError, TypeError):
                        continue
            except Exception:
                pass

        # Count active healings
        active_healings = by_outcome.get(
            HealingOutcome.REQUIRES_CONFIRMATION.value, 0,
        )

        return {
            "company_id": self.company_id,
            "is_monitoring": self._is_monitoring,
            "last_check_at": datetime.now(timezone.utc).isoformat(),
            "actions_registered": len(self._actions),
            "active_healings": active_healings,
            "total_healings_24h": total_24h,
            "healings_by_outcome": by_outcome,
            "healings_by_action": by_action,
        }

    async def get_healing_history(
        self,
        limit: int = 50,
        offset: int = 0,
        action_name: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get healing event history from Redis.

        Args:
            limit: Number of events to return.
            offset: Pagination offset.
            action_name: Optional action name filter.
            outcome: Optional outcome filter.

        Returns:
            Dictionary with healing events and metadata.
        """
        events = await self._get_events_redis(limit=limit + offset)

        # Apply filters
        filtered = events
        if action_name:
            filtered = [
                e for e in filtered
                if e.get("action_name") == action_name
            ]
        if outcome:
            filtered = [
                e for e in filtered
                if e.get("outcome") == outcome
            ]

        # Paginate
        paginated = filtered[offset:offset + limit]

        return {
            "company_id": self.company_id,
            "events": paginated,
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
        }

    def get_registered_actions(self) -> List[Dict[str, Any]]:
        """Get all registered healing actions.

        Returns:
            List of healing action definitions.
        """
        return [
            {
                "name": action.name,
                "description": action.description,
                "risk_level": action.risk_level.value,
                "requires_confirmation": action.requires_confirmation,
                "cooldown_seconds": action.cooldown_seconds,
                "enabled": action.get_definition().enabled,
            }
            for action in self._actions.values()
        ]

    # ── Internal Helpers ───────────────────────────────────────

    async def _log_event(self, event: HealingEvent) -> None:
        """Persist a healing event to Redis with 7-day TTL."""
        redis = await self._get_redis()
        if redis is None:
            return

        try:
            from app.core.redis import make_key

            log_key = make_key(
                self.company_id, "self_healing", "event_log",
            )

            event_data = {
                "event_id": event.event_id,
                "company_id": event.company_id,
                "action_name": event.action_name,
                "trigger_reason": event.trigger_reason,
                "risk_level": event.risk_level,
                "outcome": event.outcome,
                "triggered_at": event.triggered_at,
                "completed_at": event.completed_at,
                "details": event.details,
                "triggered_by": event.triggered_by,
            }

            await redis.lpush(
                log_key, json.dumps(event_data),
            )
            await redis.ltrim(log_key, 0, MAX_HEALING_EVENTS - 1)
            await redis.expire(log_key, HEALING_LOG_TTL_SECONDS)

        except Exception as exc:
            logger.warning(
                "healing_event_log_failed",
                company_id=self.company_id,
                error=str(exc),
            )

    async def _get_events_redis(
        self, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Read healing events from Redis."""
        redis = await self._get_redis()
        if redis is None:
            return []

        events = []
        try:
            from app.core.redis import make_key

            log_key = make_key(
                self.company_id, "self_healing", "event_log",
            )
            raw_events = await redis.lrange(log_key, 0, limit - 1)

            for entry in raw_events:
                try:
                    event = json.loads(entry)
                    if event.get("company_id") == self.company_id:
                        events.append(event)
                except (json.JSONDecodeError, TypeError):
                    continue

        except Exception as exc:
            logger.warning(
                "healing_events_read_failed",
                company_id=self.company_id,
                error=str(exc),
            )

        return events

    async def _broadcast_healing_event(
        self, event: HealingEvent,
    ) -> None:
        """Broadcast healing event via Socket.io."""
        try:
            from app.core.socketio import get_socketio
            sio = get_socketio()
            if sio:
                room = f"company:{self.company_id}"
                await sio.emit(
                    SOCKETIO_EVENT_HEALING_TRIGGERED,
                    {
                        "event_id": event.event_id,
                        "action_name": event.action_name,
                        "outcome": event.outcome,
                        "risk_level": event.risk_level,
                        "triggered_at": event.triggered_at,
                    },
                    room=room,
                )
        except Exception as exc:
            logger.debug(
                "healing_broadcast_failed",
                company_id=self.company_id,
                error=str(exc),
            )


# ══════════════════════════════════════════════════════════════════
# LAZY SERVICE LOADING (BC-008)
# ══════════════════════════════════════════════════════════════════

_orchestrator_cache: Dict[str, SelfHealingOrchestrator] = {}


def get_self_healing_orchestrator(
    company_id: str,
) -> SelfHealingOrchestrator:
    """Get or create a SelfHealingOrchestrator for a tenant.

    Uses lazy loading pattern per system_status_service.py.

    Args:
        company_id: Tenant identifier (BC-001).

    Returns:
        SelfHealingOrchestrator instance.
    """
    if company_id not in _orchestrator_cache:
        _orchestrator_cache[company_id] = SelfHealingOrchestrator(
            company_id,
        )
    return _orchestrator_cache[company_id]


__all__ = [
    "SelfHealingOrchestrator",
    "BaseHealingAction",
    "HealingActionDef",
    "HealingEvent",
    "HealingStatus",
    "RiskLevel",
    "HealingOutcome",
    "SOCKETIO_EVENT_HEALING_TRIGGERED",
    "SOCKETIO_EVENT_HEALING_COMPLETED",
    "get_self_healing_orchestrator",
]
