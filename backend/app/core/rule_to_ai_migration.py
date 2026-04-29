"""
Rule to AI Migration Engine.

PARWA SaaS — Gradual, tenant-scoped migration from deterministic rule-based
logic to AI-powered decision-making, with safety guardrails and observability.

Redis key convention
--------------------
    migration:{tenant_id}:{feature}  →  "ai" (enabled) | "rule" (disabled)

Feature-flag semantics
----------------------
    ``_is_ai_enabled(val)`` returns **True** when ``val != "rule"``.
    * ``"ai"``          → AI enabled
    * ``None``          → AI enabled (fail-open default)
    * ``"rule"``        → AI disabled, fall back to legacy rules
    * any other string  → AI enabled (future-proofing)

Safety model
------------
    * **Fail-open**: if Redis is unreachable, AI is enabled (assumes the
      calling service degraded gracefully).
    * **Confidence threshold**: each feature can set a minimum confidence.
      When the AI model's confidence is below this threshold the call
      is routed back to the rule engine.
    * **Rollout percentage**: supports canary / ring deployments by
      routing only ``rollout_percentage`` of requests to AI.
    * **Circuit breaker**: after ``error_threshold`` consecutive errors
      the feature is automatically rolled back for a cooldown period.

Observability
-------------
    * ``MigrationEngine.get_metrics()`` exposes counters, gauges, and
      per-feature breakdowns.
    * Every flag check is logged at DEBUG level.
    * ``MigrationEventBus`` provides an in-process pub/sub so callers
      can hook into ``migration.rolled_out``, ``migration.rolled_back``,
      ``migration.circuit_opened``, etc.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MigrationStatus(Enum):
    """Lifecycle states for a feature migration."""

    RULE_BASED = "rule"
    AI_BASED = "ai"
    TRANSITIONING = "transitioning"
    PAUSED = "paused"
    ROLLED_BACK = "rolled_back"


class FeatureCategory(Enum):
    """High-level grouping of migratable features."""

    TICKET_ASSIGNMENT = "ticket_assignment"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    AUTO_RESPONSE = "auto_response"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    PRIORITY_PREDICTION = "priority_prediction"
    SLA_PREDICTION = "sla_prediction"
    CUSTOMER_ROUTING = "customer_routing"
    ANOMALY_DETECTION = "anomaly_detection"


class RolloutStrategy(Enum):
    """Supported rollout strategies."""

    PERCENTAGE = "percentage"
    CANARY_TENANTS = "canary_tenants"
    ALLOW_LIST = "allow_list"
    GEOGRAPHIC = "geographic"
    ALL_AT_ONCE = "all_at_once"


class CircuitState(Enum):
    """Circuit-breaker states."""

    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failing, requests short-circuit to rule
    HALF_OPEN = "half_open"  # probing to see if AI has recovered


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class MigrationConfig:
    """Per-tenant, per-feature migration configuration."""

    tenant_id: str
    feature: str
    rollout_percentage: float = 0.0  # 0.0 → 1.0
    rollout_strategy: RolloutStrategy = RolloutStrategy.PERCENTAGE
    enabled: bool = True
    confidence_threshold: float = 0.80
    fallback_to_rule: bool = True
    canary_tenants: List[str] = field(default_factory=list)
    allow_list: List[str] = field(default_factory=list)
    geo_regions: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = self.created_at
        self.rollout_percentage = max(0.0, min(1.0, self.rollout_percentage))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "feature": self.feature,
            "rollout_percentage": self.rollout_percentage,
            "rollout_strategy": self.rollout_strategy.value,
            "enabled": self.enabled,
            "confidence_threshold": self.confidence_threshold,
            "fallback_to_rule": self.fallback_to_rule,
            "canary_tenants": self.canary_tenants,
            "allow_list": self.allow_list,
            "geo_regions": self.geo_regions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MigrationResult:
    """Outcome of a single ``should_use_ai`` check."""

    tenant_id: str
    feature: str
    use_ai: bool
    reason: str
    strategy_used: str
    confidence: float = 0.0
    rollout_pct: float = 0.0
    circuit_state: str = "closed"
    latency_ms: float = 0.0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "feature": self.feature,
            "use_ai": self.use_ai,
            "reason": self.reason,
            "strategy_used": self.strategy_used,
            "confidence": round(self.confidence, 4),
            "rollout_pct": round(self.rollout_pct, 4),
            "circuit_state": self.circuit_state,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class CircuitBreakerState:
    """Per-feature circuit-breaker bookkeeping."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: Optional[str] = None
    last_success_at: Optional[str] = None
    opened_at: Optional[str] = None
    error_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 3
    half_open_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_at": self.last_failure_at,
            "last_success_at": self.last_success_at,
            "opened_at": self.opened_at,
            "error_threshold": self.error_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "half_open_max_calls": self.half_open_max_calls,
            "half_open_calls": self.half_open_calls,
        }


# ---------------------------------------------------------------------------
# Feature-Flag Backend (abstract)
# ---------------------------------------------------------------------------


class FeatureFlagBackend(ABC):
    """Pluggable backend for feature-flag reads / writes."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class RedisFeatureFlagBackend(FeatureFlagBackend):
    """Redis-backed implementation."""

    def __init__(self, redis_client: Any, key_prefix: str = "migration") -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Optional[str]:
        try:
            val = await self._redis.get(self._full_key(key))
            if isinstance(val, bytes):
                val = val.decode()
            return val
        except Exception:
            logger.warning("Redis GET failed for %s", key)
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        try:
            kw: Dict[str, Any] = {}
            if ttl is not None:
                kw["ex"] = ttl
            await self._redis.set(self._full_key(key), value, **kw)
        except Exception:
            logger.warning("Redis SET failed for %s", key)

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(self._full_key(key))
        except Exception:
            logger.warning("Redis DELETE failed for %s", key)


class InMemoryFeatureFlagBackend(FeatureFlagBackend):
    """In-process dict-backed implementation (for tests / single-node)."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Standard circuit-breaker pattern per feature key.

    Transitions
    -----------
    CLOSED → OPEN         after *error_threshold* consecutive failures
    OPEN   → HALF_OPEN    after *recovery_timeout_seconds*
    HALF_OPEN → CLOSED    after *half_open_max_calls* consecutive successes
    HALF_OPEN → OPEN      on any failure during half-open probing
    """

    def __init__(
        self,
        error_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.error_threshold = error_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self._circuits: Dict[str, CircuitBreakerState] = {}

    def _ensure(self, key: str) -> CircuitBreakerState:
        if key not in self._circuits:
            self._circuits[key] = CircuitBreakerState(
                error_threshold=self.error_threshold,
                recovery_timeout_seconds=self.recovery_timeout_seconds,
                half_open_max_calls=self.half_open_max_calls,
            )
        return self._circuits[key]

    def _should_transition_to_half_open(self, cb: CircuitBreakerState) -> bool:
        if cb.state != CircuitState.OPEN or cb.opened_at is None:
            return False
        opened = datetime.fromisoformat(cb.opened_at)
        elapsed = (datetime.now(timezone.utc) - opened).total_seconds()
        return elapsed >= cb.recovery_timeout_seconds

    # -- public API --

    def record_success(self, key: str) -> None:
        cb = self._ensure(key)
        now = datetime.now(timezone.utc).isoformat()
        cb.success_count += 1
        cb.last_success_at = now

        if cb.state == CircuitState.HALF_OPEN:
            cb.half_open_calls += 1
            if cb.half_open_calls >= cb.half_open_max_calls:
                cb.state = CircuitState.CLOSED
                cb.failure_count = 0
                cb.half_open_calls = 0
                logger.info("Circuit CLOSED for %s after successful probe", key)

    def record_failure(self, key: str) -> None:
        cb = self._ensure(key)
        now = datetime.now(timezone.utc).isoformat()
        cb.failure_count += 1
        cb.last_failure_at = now

        if cb.state == CircuitState.HALF_OPEN:
            cb.state = CircuitState.OPEN
            cb.opened_at = now
            cb.half_open_calls = 0
            logger.warning("Circuit re-OPENED for %s during half-open probe", key)
        elif cb.failure_count >= cb.error_threshold:
            cb.state = CircuitState.OPEN
            cb.opened_at = now
            logger.warning("Circuit OPENED for %s (failures=%d)", key, cb.failure_count)

    def get_state(self, key: str) -> CircuitState:
        cb = self._ensure(key)
        if self._should_transition_to_half_open(cb):
            cb.state = CircuitState.HALF_OPEN
            cb.half_open_calls = 0
            logger.info("Circuit HALF_OPEN for %s (recovery timeout elapsed)", key)
        return cb.state

    def is_available(self, key: str) -> bool:
        """True when the circuit allows traffic (CLOSED or HALF_OPEN)."""
        return self.get_state(key) in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def get_state_detail(self, key: str) -> Dict[str, Any]:
        cb = self._ensure(key)
        self._should_transition_to_half_open(cb)  # trigger transition check
        return cb.to_dict()

    def reset(self, key: Optional[str] = None) -> None:
        if key:
            self._circuits.pop(key, None)
        else:
            self._circuits.clear()


# ---------------------------------------------------------------------------
# Rollout Evaluator
# ---------------------------------------------------------------------------


class RolloutEvaluator:
    """Determines whether a specific request falls within the rollout window."""

    @staticmethod
    def by_percentage(
        rollout_pct: float,
        tenant_id: str,
        ticket_id: Optional[str] = None,
    ) -> bool:
        """Hash-based deterministic rollout.  Returns True for *rollout_pct*
        fraction of (tenant, ticket) pairs."""
        if rollout_pct >= 1.0:
            return True
        if rollout_pct <= 0.0:
            return False
        seed = f"{tenant_id}:{ticket_id or ''}"
        bucket = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return bucket < rollout_pct

    @staticmethod
    def by_canary(
        tenant_id: str,
        canary_tenants: List[str],
    ) -> bool:
        return tenant_id in canary_tenants

    @staticmethod
    def by_allow_list(
        tenant_id: str,
        allow_list: List[str],
    ) -> bool:
        return tenant_id in allow_list

    @staticmethod
    def by_geography(
        region: Optional[str],
        allowed_regions: List[str],
    ) -> bool:
        if not region or not allowed_regions:
            return True  # no restriction
        return region in allowed_regions


# ---------------------------------------------------------------------------
# Migration Event Bus
# ---------------------------------------------------------------------------


class MigrationEvent:
    """Immutable record of a migration lifecycle event."""

    __slots__ = ("event_id", "event_type", "payload", "timestamp")

    def __init__(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.event_id = uuid.uuid4().hex[:12]
        self.event_type = event_type
        self.payload = payload
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class MigrationEventBus:
    """In-process pub/sub for migration events."""

    def __init__(self, max_history: int = 2000) -> None:
        self._subs: Dict[str, List[Any]] = {}
        self._history: List[MigrationEvent] = []
        self._max_history = max_history

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._subs.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Any) -> None:
        handlers = self._subs.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def publish(self, event: MigrationEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for handler in self._subs.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                logger.exception("Migration event handler error (%s)", event.event_type)

    def get_history(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[-limit:]]

    def clear_history(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# Migration Engine (main orchestrator)
# ---------------------------------------------------------------------------


class MigrationEngine:
    """Manages gradual rule → AI migration with Redis-backed feature flags.

    Usage::

        engine = MigrationEngine(redis_client=redis)
        use_ai, reason = await engine.check_should_use_ai("t1", "ticket_assignment", confidence=0.92)
    """

    def __init__(
        self,
        redis_client: Any = None,
        variant: str = "parwa",
        backend: Optional[FeatureFlagBackend] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        event_bus: Optional[MigrationEventBus] = None,
    ) -> None:
        self.variant = variant
        # Backend: explicit > Redis > in-memory
        if backend is not None:
            self._backend = backend
        elif redis_client is not None:
            self._backend = RedisFeatureFlagBackend(redis_client)
        else:
            self._backend = InMemoryFeatureFlagBackend()
        self._redis = redis_client  # kept for backward compat
        self._circuit = circuit_breaker or CircuitBreaker()
        self._event_bus = event_bus or MigrationEventBus()
        self._configs: Dict[str, MigrationConfig] = {}
        self._metrics: Dict[str, Any] = {
            "total_checks": 0,
            "ai_enabled_checks": 0,
            "rule_fallbacks": 0,
            "rollout_blocked": 0,
            "circuit_blocked": 0,
            "confidence_blocked": 0,
            "migration_errors": 0,
            "per_feature": {},
        }

    # -- Redis key helpers --

    @staticmethod
    def _redis_key(tenant_id: str, feature: str) -> str:
        return f"{tenant_id}:{feature}"

    @staticmethod
    def _is_ai_enabled(val: Optional[str]) -> bool:
        """Returns True when val != 'rule'.  None means enabled by default."""
        return val != "rule"

    # -- Feature-flag CRUD --

    async def is_ai_enabled(self, tenant_id: str, feature: str) -> bool:
        """Low-level flag check (does not consider rollout / circuit / confidence)."""
        self._metrics["total_checks"] += 1
        self._bump_feature(tenant_id, feature, "total_checks")
        try:
            key = self._redis_key(tenant_id, feature)
            val = await self._backend.get(key)
            result = self._is_ai_enabled(val)
            if result:
                self._metrics["ai_enabled_checks"] += 1
                self._bump_feature(tenant_id, feature, "ai_enabled")
            logger.debug(
                "Flag check: %s → val=%r, ai=%s",
                key,
                val,
                result,
            )
            return result
        except Exception as exc:
            logger.error(
                "Migration check error for %s:%s — %s", tenant_id, feature, exc
            )
            self._metrics["migration_errors"] += 1
            return True  # fail-open

    async def enable_ai(self, tenant_id: str, feature: str) -> bool:
        key = self._redis_key(tenant_id, feature)
        await self._backend.set(key, "ai")
        self._event_bus.publish(
            MigrationEvent(
                event_type="migration.ai_enabled",
                payload={"tenant_id": tenant_id, "feature": feature},
            )
        )
        logger.info("AI enabled for %s:%s", tenant_id, feature)
        return True

    async def disable_ai(self, tenant_id: str, feature: str) -> bool:
        key = self._redis_key(tenant_id, feature)
        await self._backend.set(key, "rule")
        self._event_bus.publish(
            MigrationEvent(
                event_type="migration.ai_disabled",
                payload={"tenant_id": tenant_id, "feature": feature},
            )
        )
        logger.info("AI disabled for %s:%s", tenant_id, feature)
        return True

    async def delete_flag(self, tenant_id: str, feature: str) -> None:
        key = self._redis_key(tenant_id, feature)
        await self._backend.delete(key)

    async def get_flag_value(self, tenant_id: str, feature: str) -> Optional[str]:
        key = self._redis_key(tenant_id, feature)
        return await self._backend.get(key)

    # -- Config CRUD --

    async def get_config(
        self, tenant_id: str, feature: str
    ) -> Optional[MigrationConfig]:
        key = self._redis_key(tenant_id, feature)
        return self._configs.get(key)

    async def set_config(self, config: MigrationConfig) -> None:
        config.updated_at = datetime.now(timezone.utc).isoformat()
        key = self._redis_key(config.tenant_id, config.feature)
        self._configs[key] = config
        self._event_bus.publish(
            MigrationEvent(
                event_type="migration.config_updated",
                payload=config.to_dict(),
            )
        )

    async def delete_config(self, tenant_id: str, feature: str) -> None:
        key = self._redis_key(tenant_id, feature)
        self._configs.pop(key, None)

    async def list_configs(
        self, tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        configs = self._configs.values()
        if tenant_id:
            configs = [c for c in configs if c.tenant_id == tenant_id]
        return [c.to_dict() for c in configs]

    # -- High-level decision --

    async def check_should_use_ai(
        self,
        tenant_id: str,
        feature: str,
        confidence: float = 1.0,
        region: Optional[str] = None,
        ticket_id: Optional[str] = None,
    ) -> MigrationResult:
        """Full decision pipeline: flag → circuit → rollout → confidence.

        Returns a ``MigrationResult`` with ``use_ai`` indicating the final
        decision and ``reason`` explaining the path taken.
        """
        start = time.monotonic()
        config = await self.get_config(tenant_id, feature)
        rollout_pct = config.rollout_percentage if config else 1.0
        rollout_strategy = config.rollout_strategy.value if config else "all_at_once"
        confidence_threshold = config.confidence_threshold if config else 0.80

        circuit_key = self._redis_key(tenant_id, feature)
        circuit_state = self._circuit.get_state(circuit_key)

        # Step 1: feature flag
        ai_enabled = await self.is_ai_enabled(tenant_id, feature)
        if not ai_enabled:
            self._metrics["rule_fallbacks"] += 1
            self._bump_feature(tenant_id, feature, "rule_fallbacks")
            return self._result(
                tenant_id,
                feature,
                False,
                "AI disabled by feature flag",
                rollout_strategy,
                confidence,
                rollout_pct,
                circuit_state.value,
                start,
            )

        # Step 2: circuit breaker
        if not self._circuit.is_available(circuit_key):
            self._metrics["circuit_blocked"] += 1
            self._bump_feature(tenant_id, feature, "circuit_blocked")
            return self._result(
                tenant_id,
                feature,
                False,
                f"Circuit breaker {
                    circuit_state.value} — short-circuit to rules",
                rollout_strategy,
                confidence,
                rollout_pct,
                circuit_state.value,
                start,
            )

        # Step 3: rollout
        rollout_ok = self._evaluate_rollout(
            tenant_id,
            config,
            region,
            ticket_id,
        )
        if not rollout_ok:
            self._metrics["rollout_blocked"] += 1
            self._bump_feature(tenant_id, feature, "rollout_blocked")
            return self._result(
                tenant_id,
                feature,
                False,
                f"Not in rollout (pct={rollout_pct:.0%})",
                rollout_strategy,
                confidence,
                rollout_pct,
                circuit_state.value,
                start,
            )

        # Step 4: confidence
        if confidence < confidence_threshold:
            self._metrics["confidence_blocked"] += 1
            self._bump_feature(tenant_id, feature, "confidence_blocked")
            return self._result(
                tenant_id,
                feature,
                False,
                f"Confidence {
                    confidence:.2f} < threshold {
                    confidence_threshold:.2f}",
                rollout_strategy,
                confidence,
                rollout_pct,
                circuit_state.value,
                start,
            )

        return self._result(
            tenant_id,
            feature,
            True,
            "AI enabled",
            rollout_strategy,
            confidence,
            rollout_pct,
            circuit_state.value,
            start,
        )

    # -- Rollout evaluation --

    def _evaluate_rollout(
        self,
        tenant_id: str,
        config: Optional[MigrationConfig],
        region: Optional[str],
        ticket_id: Optional[str],
    ) -> bool:
        if config is None:
            return True  # no config ⇒ no rollout restriction

        strategy = config.rollout_strategy

        if strategy == RolloutStrategy.ALL_AT_ONCE:
            return True

        if strategy == RolloutStrategy.PERCENTAGE:
            return RolloutEvaluator.by_percentage(
                config.rollout_percentage,
                tenant_id,
                ticket_id,
            )

        if strategy == RolloutStrategy.CANARY_TENANTS:
            return RolloutEvaluator.by_canary(tenant_id, config.canary_tenants)

        if strategy == RolloutStrategy.ALLOW_LIST:
            return RolloutEvaluator.by_allow_list(tenant_id, config.allow_list)

        if strategy == RolloutStrategy.GEOGRAPHIC:
            return RolloutEvaluator.by_geography(region, config.geo_regions)

        return True

    # -- Circuit-breaker feedback --

    def record_ai_success(self, tenant_id: str, feature: str) -> None:
        key = self._redis_key(tenant_id, feature)
        self._circuit.record_success(key)

    def record_ai_failure(self, tenant_id: str, feature: str) -> None:
        key = self._redis_key(tenant_id, feature)
        self._circuit.record_failure(key)
        state = self._circuit.get_state(key)
        if state == CircuitState.OPEN:
            self._event_bus.publish(
                MigrationEvent(
                    event_type="migration.circuit_opened",
                    payload={"tenant_id": tenant_id, "feature": feature},
                )
            )

    # -- Batch --

    async def batch_check(
        self, checks: List[Dict[str, Any]]
    ) -> Dict[str, MigrationResult]:
        results: Dict[str, MigrationResult] = {}
        for chk in checks:
            tid = chk["tenant_id"]
            feat = chk["feature"]
            conf = chk.get("confidence", 1.0)
            region = chk.get("region")
            ticket_id = chk.get("ticket_id")
            result = await self.check_should_use_ai(
                tid,
                feat,
                confidence=conf,
                region=region,
                ticket_id=ticket_id,
            )
            results[f"{tid}:{feat}"] = result
        return results

    async def batch_enable(self, pairs: List[Tuple[str, str]]) -> List[bool]:
        out = []
        for tid, feat in pairs:
            ok = await self.enable_ai(tid, feat)
            out.append(ok)
        return out

    async def batch_disable(self, pairs: List[Tuple[str, str]]) -> List[bool]:
        out = []
        for tid, feat in pairs:
            ok = await self.disable_ai(tid, feat)
            out.append(ok)
        return out

    # -- Metrics & introspection --

    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self._metrics,
            "per_feature": dict(self._metrics.get("per_feature", {})),
        }

    def get_circuit_state(self, tenant_id: str, feature: str) -> Dict[str, Any]:
        key = self._redis_key(tenant_id, feature)
        return self._circuit.get_state_detail(key)

    def get_event_history(
        self, event_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self._event_bus.get_history(event_type=event_type, limit=limit)

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._event_bus.subscribe(event_type, handler)

    async def reset_metrics(self) -> None:
        counters = [
            "total_checks",
            "ai_enabled_checks",
            "rule_fallbacks",
            "rollout_blocked",
            "circuit_blocked",
            "confidence_blocked",
            "migration_errors",
        ]
        for k in counters:
            self._metrics[k] = 0
        self._metrics["per_feature"] = {}

    def reset_circuits(self) -> None:
        self._circuit.reset()

    def reset(self) -> None:
        self._configs.clear()
        self._circuit.reset()
        self._event_bus.clear_history()

    # -- helpers --

    def _bump_feature(self, tenant_id: str, feature: str, metric: str) -> None:
        key = f"{tenant_id}:{feature}"
        pf = self._metrics.setdefault("per_feature", {})
        feat_map = pf.setdefault(key, {})
        feat_map[metric] = feat_map.get(metric, 0) + 1

    @staticmethod
    def _result(
        tenant_id: str,
        feature: str,
        use_ai: bool,
        reason: str,
        strategy_used: str,
        confidence: float,
        rollout_pct: float,
        circuit_state: str,
        start: float,
    ) -> MigrationResult:
        return MigrationResult(
            tenant_id=tenant_id,
            feature=feature,
            use_ai=use_ai,
            reason=reason,
            strategy_used=strategy_used,
            confidence=confidence,
            rollout_pct=rollout_pct,
            circuit_state=circuit_state,
            latency_ms=(time.monotonic() - start) * 1000,
        )


# ---------------------------------------------------------------------------
# Migration Planner (staged rollout orchestration)
# ---------------------------------------------------------------------------


class MigrationPlanner:
    """Plans and executes staged rollouts for a feature.

    Stages
    ------
    1. Canary (select tenants)
    2. Ring 1 (10 %)
    3. Ring 2 (25 %)
    4. Ring 3 (50 %)
    5. Ring 4 (75 %)
    6. Full (100 %)
    """

    STAGES: List[Dict[str, Any]] = [
        {"name": "canary", "percentage": 0.0, "description": "Canary tenants only"},
        {"name": "ring_1", "percentage": 0.10, "description": "10% rollout"},
        {"name": "ring_2", "percentage": 0.25, "description": "25% rollout"},
        {"name": "ring_3", "percentage": 0.50, "description": "50% rollout"},
        {"name": "ring_4", "percentage": 0.75, "description": "75% rollout"},
        {"name": "full", "percentage": 1.00, "description": "100% rollout"},
    ]

    def __init__(self, engine: MigrationEngine) -> None:
        self._engine = engine
        self._stage_index: Dict[str, int] = {}  # key → current stage index

    def _key(self, tenant_id: str, feature: str) -> str:
        return f"{tenant_id}:{feature}"

    async def advance(self, tenant_id: str, feature: str) -> Dict[str, Any]:
        """Move to the next rollout stage and return the new config."""
        key = self._key(tenant_id, feature)
        idx = self._stage_index.get(key, -1) + 1
        if idx >= len(self.STAGES):
            return {"status": "already_complete", "current_stage": "full"}

        self._stage_index[key] = idx
        stage = self.STAGES[idx]

        config = MigrationConfig(
            tenant_id=tenant_id,
            feature=feature,
            rollout_percentage=stage["percentage"],
        )
        await self._engine.set_config(config)
        await self._engine.enable_ai(tenant_id, feature)

        self._engine._event_bus.publish(
            MigrationEvent(
                event_type="migration.stage_advanced",
                payload={
                    "tenant_id": tenant_id,
                    "feature": feature,
                    "stage": stage["name"],
                    "percentage": stage["percentage"],
                },
            )
        )

        return {
            "status": "advanced",
            "stage": stage["name"],
            "percentage": stage["percentage"],
            "description": stage["description"],
        }

    async def rollback(self, tenant_id: str, feature: str) -> Dict[str, Any]:
        """Disable AI and reset stage index."""
        key = self._key(tenant_id, feature)
        prev_stage = self.STAGES[self._stage_index.get(key, 0)]["name"]
        self._stage_index[key] = -1
        await self._engine.disable_ai(tenant_id, feature)
        config = MigrationConfig(
            tenant_id=tenant_id,
            feature=feature,
            rollout_percentage=0.0,
        )
        await self._engine.set_config(config)

        self._engine._event_bus.publish(
            MigrationEvent(
                event_type="migration.rolled_back",
                payload={
                    "tenant_id": tenant_id,
                    "feature": feature,
                    "previous_stage": prev_stage,
                },
            )
        )

        return {"status": "rolled_back", "previous_stage": prev_stage}

    async def pause(self, tenant_id: str, feature: str) -> Dict[str, Any]:
        """Freeze at the current stage but keep AI enabled."""
        key = self._key(tenant_id, feature)
        idx = self._stage_index.get(key, 0)
        stage = self.STAGES[idx]
        return {"status": "paused", "stage": stage["name"]}

    def current_stage(self, tenant_id: str, feature: str) -> Dict[str, Any]:
        key = self._key(tenant_id, feature)
        idx = self._stage_index.get(key, -1)
        if idx < 0:
            return {"stage": "not_started", "percentage": 0.0}
        stage = self.STAGES[idx]
        return {"stage": stage["name"], "percentage": stage["percentage"]}

    async def set_canary_tenants(
        self, tenant_id: str, feature: str, canary_list: List[str]
    ) -> None:
        config = await self._engine.get_config(tenant_id, feature)
        if config is None:
            config = MigrationConfig(tenant_id=tenant_id, feature=feature)
        config.canary_tenants = list(canary_list)
        config.rollout_strategy = RolloutStrategy.CANARY_TENANTS
        await self._engine.set_config(config)


# ---------------------------------------------------------------------------
# Audit logger (optional companion for compliance)
# ---------------------------------------------------------------------------


class MigrationAuditLogger:
    """Persistent audit trail for migration state changes.

    Each entry is a JSON-serialisable dict suitable for writing to a
    database table, S3, or log aggregator.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._max = max_entries

    def log(
        self,
        action: str,
        tenant_id: str,
        feature: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "id": uuid.uuid4().hex[:16],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "tenant_id": tenant_id,
            "feature": feature,
            "actor": actor,
            "details": details or {},
        }
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]
        logger.info("AUDIT %s %s:%s by %s", action, tenant_id, feature, actor)
        return entry

    def query(
        self,
        tenant_id: Optional[str] = None,
        feature: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        results = self._entries
        if tenant_id:
            results = [e for e in results if e["tenant_id"] == tenant_id]
        if feature:
            results = [e for e in results if e["feature"] == feature]
        if action:
            results = [e for e in results if e["action"] == action]
        return list(reversed(results[-limit:]))

    def export_json(self) -> str:
        return json.dumps(self._entries, default=str)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_migration_engine(
    redis_client: Any = None,
    variant: str = "parwa",
) -> MigrationEngine:
    """Convenience factory."""
    return MigrationEngine(redis_client=redis_client, variant=variant)
