"""
Rule → AI Migration Engine (F-158)

Orchestrates gradual migration from rule-based classification and assignment
to AI-powered alternatives with automatic fallback on failure.

Core pattern:
    1. Check if AI is enabled for the company (per-feature toggle).
    2. Consult the per-feature circuit breaker.
    3. If circuit is closed / half-open → try AI.
       - Success  → record_success, return AI result.
       - Failure  → record_failure, fall back to rule-based.
    4. If circuit is open → skip AI, use rule-based immediately.
    5. Every decision is logged for analytics and observability.

GAP-011 FIX: Feature-level circuit breaker.
  N consecutive failures → open circuit for M seconds → half-open retry.

BC-001: company_id is always the second positional parameter.
BC-008: Never drop a request — always return a usable result via fallback.

Parent: Week 9, Day 8 (Friday)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _CompatLogger:
    """Wrapper to support structlog-style kwargs on stdlib logging."""

    def __init__(self, base_logger):
        self._logger = base_logger

    def _call(self, _method, msg, *args, **kwargs):
        extra = kwargs.pop("extra", None)
        exc_info = kwargs.pop("exc_info", False)
        stack_info = kwargs.pop("stack_info", False)
        if kwargs:
            parts = [f"{k}={v}" for k, v in kwargs.items()]
            msg = msg + " " + " ".join(parts)
        getattr(self._logger, _method)(
            msg, *args, extra=extra, exc_info=exc_info, stack_info=stack_info
        )

    def info(self, msg, *a, **kw):
        self._call("info", msg, *a, **kw)

    def warning(self, msg, *a, **kw):
        self._call("warning", msg, *a, **kw)

    def error(self, msg, *a, **kw):
        self._call("error", msg, *a, **kw)

    def debug(self, msg, *a, **kw):
        self._call("debug", msg, *a, **kw)


logger = _CompatLogger(logger)


# ═══════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════

_REDIS_PREFIX = "migration"
_FEATURES = ("classification", "assignment")
_DEFAULT_FAILURE_THRESHOLD = 5
_DEFAULT_RECOVERY_TIMEOUT = 300  # seconds
_DEFAULT_HALF_OPEN_SUCCESSES = 2
_FALLBACK_LOG_MAX = 100  # max entries in Redis list


# ═══════════════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════════════


class CircuitState(str, Enum):
    """Possible states of a feature circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class MigrationMethod(str, Enum):
    """Method used for classification / assignment."""

    AI = "ai"
    RULE = "rule"
    KEYWORD = "keyword"


# ═══════════════════════════════════════════════════════════════════════
#  GAP-011: Per-feature Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single AI feature (classification / assignment).

    State machine:
        closed  ──(N failures)──▶ open ──(M seconds)──▶ half_open
        half_open ──(success × K)──▶ closed
        half_open ──(1 failure)──▶ open
    """

    feature: str = ""
    state: str = CircuitState.CLOSED.value
    failure_count: int = 0
    failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD
    recovery_timeout: int = _DEFAULT_RECOVERY_TIMEOUT  # seconds
    last_failure_time: float = 0.0
    half_open_successes_needed: int = _DEFAULT_HALF_OPEN_SUCCESSES
    half_open_success_count: int = 0
    total_successes: int = 0
    total_failures: int = 0

    # ── Public API ────────────────────────────────────────────────

    async def can_execute(self) -> bool:
        """Return *True* when a call may be attempted.

        In ``open`` state the breaker will transition to ``half_open``
        automatically once the recovery timeout has elapsed.
        """
        if self.state == CircuitState.CLOSED.value:
            return True

        if self.state == CircuitState.HALF_OPEN.value:
            return True

        # state == OPEN — check timeout
        now = time.monotonic()
        if (now - self.last_failure_time) >= self.recovery_timeout:
            self.state = CircuitState.HALF_OPEN.value
            self.half_open_success_count = 0
            logger.info(
                "circuit_half_open feature=%s elapsed_s=%s",
                self.feature,
                round(now - self.last_failure_time),
            )
            return True

        return False

    async def record_success(self) -> None:
        """Record a successful call.

        In ``half_open`` state, increment the success counter and
        transition to ``closed`` once the threshold is reached.
        """
        self.total_successes += 1

        if self.state == CircuitState.HALF_OPEN.value:
            self.half_open_success_count += 1
            if self.half_open_success_count >= self.half_open_successes_needed:
                self._close()
            logger.info(
                "circuit_closed_after_half_open feature=%s successes=%s",
                self.feature,
                self.half_open_success_count,
            )
            return

        # closed or just recovered — reset failure counter
        if self.state == CircuitState.CLOSED.value:
            self.failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed call.

        In ``half_open`` state, any failure immediately re-opens the
        circuit.  In ``closed`` state, increment the failure counter
        and open once the threshold is reached.
        """
        self.total_failures += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN.value:
            self._open()
            logger.warning(
                "circuit_reopened_from_half_open feature=%s failure_count=%s",
                self.feature,
                self.failure_count,
            )
            return

        # closed — count failures
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._open()
            logger.warning(
                "circuit_opened feature=%s failure_count=%s threshold=%s",
                self.feature,
                self.failure_count,
                self.failure_threshold,
            )

    async def get_state(self) -> str:
        """Return the current state, potentially transitioning open→half_open."""
        _ = await self.can_execute()  # side-effect: may transition
        return self.state

    async def reset(self) -> None:
        """Forcefully reset the breaker to *closed* (admin operation)."""
        prev = self.state
        self._close()
        logger.info("circuit_reset feature=%s previous_state=%s", self.feature, prev)

    # ── Serialisation helpers ─────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
            "half_open_successes_needed": self.half_open_successes_needed,
            "half_open_success_count": self.half_open_success_count,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitBreaker":
        return cls(
            feature=data.get("feature", ""),
            state=data.get("state", CircuitState.CLOSED.value),
            failure_count=data.get("failure_count", 0),
            failure_threshold=data.get("failure_threshold", _DEFAULT_FAILURE_THRESHOLD),
            recovery_timeout=data.get("recovery_timeout", _DEFAULT_RECOVERY_TIMEOUT),
            last_failure_time=data.get("last_failure_time", 0.0),
            half_open_successes_needed=data.get(
                "half_open_successes_needed", _DEFAULT_HALF_OPEN_SUCCESSES
            ),
            half_open_success_count=data.get("half_open_success_count", 0),
            total_successes=data.get("total_successes", 0),
            total_failures=data.get("total_failures", 0),
        )

    # ── Private transitions ───────────────────────────────────────

    def _open(self) -> None:
        self.state = CircuitState.OPEN.value

    def _close(self) -> None:
        self.state = CircuitState.CLOSED.value
        self.failure_count = 0
        self.half_open_success_count = 0


# ═══════════════════════════════════════════════════════════════════════
#  Data classes — request / result objects
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class MigrationRequest:
    """Unified request for classify + assign in one call."""

    text: str
    company_id: str
    variant_type: str = "parwa"
    ticket_data: Optional[Dict[str, Any]] = None
    customer_id: Optional[str] = None
    priority: str = "medium"
    language: str = "en"
    force_method: Optional[str] = None  # "ai" or "rule" — for testing


@dataclass
class MigrationClassifyResult:
    """Result of a single classification attempt."""

    intent: str
    confidence: float
    method: str  # "ai", "rule", "keyword"
    was_fallback: bool
    fallback_reason: Optional[str]
    processing_time_ms: float
    circuit_breaker_state: str


@dataclass
class MigrationAssignResult:
    """Result of a single assignment attempt."""

    assigned_agent_id: str
    assigned_agent_name: str
    method: str  # "ai", "rule", "manual"
    was_fallback: bool
    fallback_reason: Optional[str]
    score_breakdown: Optional[Dict[str, Any]]
    processing_time_ms: float


@dataclass
class MigrationResult:
    """Combined result of classify_and_assign."""

    classification: MigrationClassifyResult
    assignment: Optional[MigrationAssignResult]
    total_time_ms: float
    used_ai: bool
    fallback_reason: Optional[str]


@dataclass
class MigrationStatus:
    """Snapshot of migration state for a company."""

    company_id: str
    classification_method: str  # "ai", "rule", "hybrid"
    assignment_method: str
    classification_circuit_state: str
    assignment_circuit_state: str
    classification_fallback_count: int
    assignment_fallback_count: int
    total_ai_calls: int
    total_rule_fallbacks: int
    ai_success_rate: float


@dataclass
class FallbackStats:
    """Detailed fallback statistics for a company."""

    company_id: str
    classification: Dict[str, Any]
    assignment: Dict[str, Any]
    recent_fallbacks: List[Dict[str, Any]]
    circuit_breaker_history: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════
#  Rule-based fallback implementations
# ═══════════════════════════════════════════════════════════════════════


class RuleBasedClassifier:
    """Keyword-based intent classification fallback.

    Used when AI classification is disabled or the circuit breaker is open.
    Mirrors the keyword patterns in ``classification_engine.py`` but
    operates independently so there is no import-time coupling.
    """

    INTENT_KEYWORDS: Dict[str, List[str]] = {
        "refund": [
            "refund",
            "money back",
            "return",
            "reimburse",
            "chargeback",
            "credit back",
            "cancel order",
            "get my money",
            "want my money back",
            "refund policy",
            "refundable",
            "non-refundable",
        ],
        "technical": [
            "bug",
            "error",
            "crash",
            "not working",
            "broken",
            "issue",
            "fix",
            "doesn't work",
            "failed",
            "glitch",
            "not loading",
            "slow",
            "connection",
            "timeout",
            "offline",
            "down",
            "500 error",
            "404",
            "exception",
            "stack trace",
        ],
        "billing": [
            "invoice",
            "payment",
            "charge",
            "bill",
            "pricing",
            "cost",
            "fee",
            "overcharge",
            "duplicate charge",
            "unauthorized charge",
            "subscription cancel",
            "renewal",
            "billing",
            "receipt",
            "transaction",
        ],
        "complaint": [
            "complaint",
            "unhappy",
            "terrible",
            "awful",
            "worst",
            "angry",
            "upset",
            "disappointed",
            "frustrated",
            "horrible",
            "unacceptable",
            "speak to manager",
            "escalate",
            "outrageous",
            "appalling",
            "disgusting",
        ],
        "cancellation": [
            "cancel",
            "unsubscribe",
            "delete account",
            "close account",
            "stop",
            "terminate",
            "end subscription",
            "deactivate",
            "cancel my plan",
            "i want to cancel",
            "please cancel",
            "cancel right now",
            "cancel immediately",
            "cancel my subscription",
        ],
        "shipping": [
            "shipping",
            "delivery",
            "track",
            "package",
            "order status",
            "shipment",
            "ship",
            "deliver",
            "courier",
            "transit",
            "parcel",
            "tracking number",
            "estimated delivery",
            "lost package",
        ],
        "escalation": [
            "manager",
            "supervisor",
            "speak to someone",
            "escalate",
            "senior",
            "higher up",
            "not resolved",
            "still waiting",
            "take this further",
            "next level",
        ],
        "feature_request": [
            "feature",
            "wish",
            "would be nice",
            "can you add",
            "suggestion",
            "please add",
            "would like to see",
            "enhancement",
            "improve",
            "new functionality",
            "missing feature",
            "roadmap",
        ],
        "account": [
            "password",
            "login",
            "account",
            "sign in",
            "access",
            "locked",
            "profile",
            "reset password",
            "verify",
            "mfa",
            "two-factor",
            "email change",
            "username",
            "settings",
            "delete account",
        ],
        "feedback": [
            "feedback",
            "suggestion",
            "improvement",
            "love",
            "hate",
            "opinion",
            "thought",
            "experience",
            "rating",
            "review",
            "suggestion box",
            "great job",
            "amazing",
            "keep it up",
        ],
        "general": [],
    }

    # Intent weights — complaints get extra weight for sensitivity
    _WEIGHTS: Dict[str, float] = {
        "complaint": 1.2,
        "escalation": 1.1,
        "general": 0.3,
    }

    async def classify(self, text: str) -> Dict[str, Any]:
        """Classify *text* using keyword matching.

        Returns a dict compatible with ``MigrationClassifyResult`` fields
        plus a ``classification_method`` key set to ``"keyword"``.
        """
        start = time.monotonic()
        text_lower = text.lower().strip()

        if not text_lower or len(text_lower) < 3:
            elapsed = round((time.monotonic() - start) * 1000, 2)
            return {
                "intent": "general",
                "confidence": 0.0,
                "classification_method": "keyword",
                "processing_time_ms": elapsed,
            }

        scores: Dict[str, float] = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            weight = self._WEIGHTS.get(intent, 1.0)
            if not keywords:
                scores[intent] = 0.01
                continue

            raw = sum(len(kw.split()) for kw in keywords if kw in text_lower)
            scores[intent] = raw * weight

        # Ensure "general" has presence if nothing else matched
        max_non_general = max(
            (v for k, v in scores.items() if k != "general"),
            default=0,
        )
        if max_non_general == 0:
            scores["general"] = max(scores.get("general", 0.0), 0.1)

        total = sum(scores.values())
        if total > 0:
            scores = {k: round(v / total, 4) for k, v in scores.items()}
        else:
            scores = {intent: 0.0 for intent in self.INTENT_KEYWORDS}

        primary = max(scores, key=scores.get)
        confidence = min(scores[primary], 0.95)
        if primary == "general":
            confidence = min(confidence, 0.5)

        elapsed = round((time.monotonic() - start) * 1000, 2)

        return {
            "intent": primary,
            "confidence": confidence,
            "classification_method": "keyword",
            "processing_time_ms": elapsed,
            "all_scores": scores,
        }


class RuleBasedAssigner:
    """Rule-based ticket assignment fallback.

    Mirrors the rules in ``AssignmentService.DEFAULT_RULES`` but
    operates without a database session so it can be used as a
    pure-logic fallback when AI assignment is unavailable.
    """

    DEFAULT_RULES: Dict[str, Dict[str, str]] = {
        "critical": {"pool": "senior_support", "agent_name": "Senior Support Lead"},
        "high_technical": {"pool": "tech_lead", "agent_name": "Technical Lead"},
        "high_billing": {"pool": "billing_manager", "agent_name": "Billing Manager"},
        "complaint": {"pool": "customer_success", "agent_name": "Customer Success"},
        "cancellation": {"pool": "retention", "agent_name": "Retention Specialist"},
        "technical": {"pool": "tech_support", "agent_name": "Tech Support Agent"},
        "billing": {"pool": "finance", "agent_name": "Finance Agent"},
        "shipping": {"pool": "logistics", "agent_name": "Logistics Agent"},
        "feature_request": {"pool": "product", "agent_name": "Product Team"},
        "account": {"pool": "support", "agent_name": "Account Support"},
        "feedback": {"pool": "support", "agent_name": "Support Agent"},
        "escalation": {"pool": "escalation", "agent_name": "Escalation Manager"},
        "default": {"pool": "general_support", "agent_name": "General Support"},
    }

    async def assign(
        self,
        intent: str,
        priority: str,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Return a rule-based assignment decision.

        Returns a dict with ``agent_id``, ``agent_name``, ``pool``,
        and ``method`` set to ``"rule"``.
        """
        start = time.monotonic()

        # Priority-first overrides
        if priority == "critical":
            rule = self.DEFAULT_RULES["critical"]
        elif priority == "high":
            if intent in ("technical", "bug"):
                rule = self.DEFAULT_RULES["high_technical"]
            elif intent in ("billing", "refund", "invoice"):
                rule = self.DEFAULT_RULES["high_billing"]
            elif intent == "complaint":
                rule = self.DEFAULT_RULES["complaint"]
            else:
                rule = self.DEFAULT_RULES["critical"]
        else:
            # Match by intent, fall through to default
            rule = self.DEFAULT_RULES.get(intent, self.DEFAULT_RULES["default"])

        elapsed = round((time.monotonic() - start) * 1000, 2)

        return {
            "agent_id": f"pool:{
                rule['pool']}",
            "agent_name": rule["agent_name"],
            "pool": rule["pool"],
            "method": "rule",
            "processing_time_ms": elapsed,
            "score_breakdown": {
                "rule_match": 1.0,
                "priority_boost": 0.3 if priority in ("critical", "high") else 0.0,
                "intent_match": 0.8 if intent in self.DEFAULT_RULES else 0.0,
                "workload_balance": 0.0,
            },
        }


# ═══════════════════════════════════════════════════════════════════════
#  Redis key helpers
# ═══════════════════════════════════════════════════════════════════════


def _redis_key(company_id: str, suffix: str) -> str:
    """Build a namespaced Redis key for migration state.

    BC-001: company_id is always included in the key.
    """
    return f"{_REDIS_PREFIX}:{company_id}:{suffix}"


def _circuit_redis_key(company_id: str, feature: str) -> str:
    return _redis_key(company_id, f"circuit:{feature}")


def _method_redis_key(company_id: str, feature: str) -> str:
    return _redis_key(company_id, f"{feature}_method")


def _stats_redis_key(company_id: str) -> str:
    return _redis_key(company_id, "stats")


def _fallback_log_key(company_id: str) -> str:
    return _redis_key(company_id, "fallback_log")


def _utc_iso() -> str:
    """Return current UTC time as ISO-8601 string (BC-012)."""
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════
#  Main engine
# ═══════════════════════════════════════════════════════════════════════


class RuleAIMigrationEngine:
    """Orchestrates migration from rule-based to AI classification and assignment.

    Features per company can be independently toggled between ``"ai"``
    and ``"rule"``.  When AI is enabled, a circuit breaker guards against
    cascading failures by automatically falling back to rules.

    Redis keys (all namespaced under ``migration:{company_id}:``):
        - ``classification_method`` / ``assignment_method`` — "ai" | "rule"
        - ``stats`` — hash with running counters
        - ``circuit:{feature}`` — serialised circuit breaker state
        - ``fallback_log`` — list of recent fallback events
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        db: Optional[Any] = None,
    ) -> None:
        self._redis = redis_client
        self._db = db

        # Lazy-loaded collaborators
        self._classification_engine: Optional[Any] = None
        self._assignment_engine: Optional[Any] = None

        # Rule-based fallbacks (always available — no external deps)
        self._rule_classifier = RuleBasedClassifier()
        self._rule_assigner = RuleBasedAssigner()

        # Per-feature circuit breakers — keyed by feature name
        self._breakers: Dict[str, CircuitBreaker] = {
            feat: CircuitBreaker(feature=feat) for feat in _FEATURES
        }

    # ── Lazy loaders ──────────────────────────────────────────────

    def _get_classification_engine(self) -> Any:
        """Lazily import and return the AI classification engine."""
        if self._classification_engine is None:
            from app.core.classification_engine import ClassificationEngine

            self._classification_engine = ClassificationEngine()
        return self._classification_engine

    def _get_assignment_engine(self) -> Any:
        """Lazily import and return the AI assignment engine."""
        if self._assignment_engine is None:
            from app.core.ai_assignment_engine import AIAssignmentEngine

            self._assignment_engine = AIAssignmentEngine()
        return self._assignment_engine

    # ── Redis helpers ─────────────────────────────────────────────

    async def _redis_get(self, key: str) -> Optional[str]:
        """Safe Redis GET that returns *None* on any failure."""
        if self._redis is None:
            return None
        try:
            val = await self._redis.get(key)
            if val is not None and isinstance(val, bytes):
                val = val.decode("utf-8")
            return val
        except Exception:
            logger.warning("redis_get_failed key=%s", key, exc_info=True)
            return None

    async def _redis_set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Safe Redis SET that logs failures but never raises."""
        if self._redis is None:
            return False
        try:
            await self._redis.set(key, value, ex=ex)
            return True
        except Exception:
            logger.warning("redis_set_failed key=%s", key, exc_info=True)
            return False

    async def _redis_hincrby(self, key: str, hash_field: str, amount: int = 1) -> None:
        """Safe Redis HINCRBY."""
        if self._redis is None:
            return
        try:
            await self._redis.hincrby(key, hash_field, amount)
        except Exception:
            logger.warning(
                "redis_hincrby_failed key=%s field=%s", key, hash_field, exc_info=True
            )

    async def _redis_lpush(
        self, key: str, value: str, maxlen: int = _FALLBACK_LOG_MAX
    ) -> None:
        """LPUSH with LTRIM to cap list length."""
        if self._redis is None:
            return
        try:
            await self._redis.lpush(key, value)
            await self._redis.ltrim(key, 0, maxlen - 1)
        except Exception:
            logger.warning("redis_lpush_failed key=%s", key, exc_info=True)

    async def _redis_lrange(
        self, key: str, start: int = 0, stop: int = -1
    ) -> List[str]:
        """Safe Redis LRANGE."""
        if self._redis is None:
            return []
        try:
            result = await self._redis.lrange(key, start, stop)
            if result:
                return [
                    r.decode("utf-8") if isinstance(r, bytes) else r for r in result
                ]
            return []
        except Exception:
            logger.warning("redis_lrange_failed key=%s", key, exc_info=True)
            return []

    async def _load_circuit_breaker(
        self,
        company_id: str,
        feature: str,
    ) -> CircuitBreaker:
        """Load circuit breaker state from Redis, or return in-memory."""
        if self._redis is None:
            return self._breakers[feature]

        key = _circuit_redis_key(company_id, feature)
        raw = await self._redis_get(key)
        if raw:
            try:
                data = json.loads(raw)
                cb = CircuitBreaker.from_dict(data)
                self._breakers[feature] = cb
                return cb
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("circuit_deserialize_failed feature=%s", feature)
        return self._breakers[feature]

    async def _save_circuit_breaker(
        self,
        company_id: str,
        feature: str,
    ) -> None:
        """Persist circuit breaker state to Redis (24 h TTL)."""
        cb = self._breakers[feature]
        key = _circuit_redis_key(company_id, feature)
        await self._redis_set(key, json.dumps(cb.to_dict()), ex=86400)

    # ── Feature toggle helpers ────────────────────────────────────

    async def _is_ai_enabled(self, company_id: str, feature: str) -> bool:
        """Check whether AI is enabled for *feature*.

        Returns *True* when no Redis value is stored (default = AI enabled).
        """
        key = _method_redis_key(company_id, feature)
        val = await self._redis_get(key)
        return val != "rule"

    async def _record_fallback_event(
        self,
        company_id: str,
        feature: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Push a fallback event to the Redis log and increment counters."""
        event = {
            "timestamp": _utc_iso(),
            "feature": feature,
            "reason": reason,
            **(details or {}),
        }
        await self._redis_lpush(
            _fallback_log_key(company_id),
            json.dumps(event),
        )
        # Increment fallback counter in stats hash
        await self._redis_hincrby(
            _stats_redis_key(company_id),
            f"{feature}_fallbacks",
        )
        await self._redis_hincrby(
            _stats_redis_key(company_id),
            "total_rule_fallbacks",
        )

    async def _record_ai_call(
        self, company_id: str, feature: str, success: bool
    ) -> None:
        """Increment AI call / success counters."""
        await self._redis_hincrby(
            _stats_redis_key(company_id),
            f"{feature}_ai_calls",
        )
        await self._redis_hincrby(
            _stats_redis_key(company_id),
            "total_ai_calls",
        )
        if success:
            await self._redis_hincrby(
                _stats_redis_key(company_id),
                f"{feature}_ai_successes",
            )
            await self._redis_hincrby(
                _stats_redis_key(company_id),
                "total_ai_successes",
            )

    # ═══════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════

    async def classify_and_assign(
        self,
        request: MigrationRequest,
    ) -> MigrationResult:
        """Classify intent and optionally assign in one shot.

        BC-008: Always returns a usable result even if both AI and
        rules fail.
        """
        total_start = time.monotonic()

        # Step 1 — classify
        classify_result = await self.classify(
            text=request.text,
            company_id=request.company_id,
            variant_type=request.variant_type,
        )

        # Step 2 — assign (only if ticket_data is provided)
        assign_result: Optional[MigrationAssignResult] = None
        if request.ticket_data is not None:
            ticket_data = {
                **request.ticket_data,
                "intent": classify_result.intent,
                "priority": request.priority,
                "language": request.language,
            }
            assign_result = await self.assign(
                request=ticket_data,
                company_id=request.company_id,
            )

        total_ms = round((time.monotonic() - total_start) * 1000, 2)

        used_ai = classify_result.method == MigrationMethod.AI.value and (
            assign_result is None or assign_result.method == MigrationMethod.AI.value
        )

        fallback_reasons: List[str] = []
        if classify_result.was_fallback:
            fallback_reasons.append(f"classify: {
                    classify_result.fallback_reason}")
        if assign_result is not None and assign_result.was_fallback:
            fallback_reasons.append(f"assign: {assign_result.fallback_reason}")

        return MigrationResult(
            classification=classify_result,
            assignment=assign_result,
            total_time_ms=total_ms,
            used_ai=used_ai,
            fallback_reason="; ".join(fallback_reasons) if fallback_reasons else None,
        )

    async def classify(
        self,
        text: str,
        company_id: str,
        variant_type: str,
    ) -> MigrationClassifyResult:
        """Classify *text* with AI, falling back to rule-based.

        Flow:
            1. Load / check feature toggle.
            2. Check circuit breaker.
            3. Try AI classification engine.
            4. On failure → rule-based fallback.
        """
        cb = await self._load_circuit_breaker(company_id, "classification")
        cb_state = await cb.get_state()
        ai_enabled = await self._is_ai_enabled(company_id, "classification")

        # ── Forced method for testing ──────────────────────────
        # (Not part of the public API signature but accessible via
        # classify_and_assign's force_method field.)
        # Handled upstream; here we honour the toggle + circuit breaker.

        should_try_ai = ai_enabled and await cb.can_execute()

        if should_try_ai:
            try:
                engine = self._get_classification_engine()
                intent_result = await engine.classify(
                    text=text,
                    company_id=company_id,
                    variant_type=variant_type,
                    use_ai=True,
                )

                await cb.record_success()
                await self._save_circuit_breaker(company_id, "classification")
                await self._record_ai_call(company_id, "classification", success=True)

                logger.info(
                    "classify_ai_success company_id=%s intent=%s confidence=%s method=%s time_ms=%s",
                    company_id,
                    intent_result.primary_intent,
                    intent_result.primary_confidence,
                    intent_result.classification_method,
                    intent_result.processing_time_ms,
                )

                return MigrationClassifyResult(
                    intent=intent_result.primary_intent,
                    confidence=intent_result.primary_confidence,
                    method=intent_result.classification_method,
                    was_fallback=False,
                    fallback_reason=None,
                    processing_time_ms=intent_result.processing_time_ms,
                    circuit_breaker_state=await cb.get_state(),
                )

            except Exception as exc:
                await cb.record_failure()
                await self._save_circuit_breaker(company_id, "classification")
                await self._record_ai_call(company_id, "classification", success=False)

                fallback_reason = f"ai_error: {str(exc)[:120]}"
                logger.warning(
                    "classify_ai_failed company_id=%s error=%s",
                    company_id,
                    str(exc),
                    circuit_state=await cb.get_state(),
                )

                # Fall through to rule-based below
                rule_result = await self._rule_classifier.classify(text)

                await self._record_fallback_event(
                    company_id,
                    "classification",
                    fallback_reason,
                    details={"intent": rule_result.get("intent")},
                )

                return MigrationClassifyResult(
                    intent=rule_result["intent"],
                    confidence=rule_result["confidence"],
                    method="keyword",
                    was_fallback=True,
                    fallback_reason=fallback_reason,
                    processing_time_ms=rule_result["processing_time_ms"],
                    circuit_breaker_state=await cb.get_state(),
                )

        # ── Circuit open or AI disabled → rule-based directly ───
        reason: Optional[str] = None
        if not ai_enabled:
            reason = "ai_disabled_for_company"
        elif not await cb.can_execute():
            reason = f"circuit_breaker_open (state={cb_state})"

        rule_result = await self._rule_classifier.classify(text)

        if reason:
            await self._record_fallback_event(
                company_id,
                "classification",
                reason,
                details={"intent": rule_result.get("intent")},
            )

            logger.info(
                "classify_rule_fallback company_id=%s intent=%s",
                company_id,
                rule_result.get("intent"),
                reason=reason,
            )

        return MigrationClassifyResult(
            intent=rule_result["intent"],
            confidence=rule_result["confidence"],
            method="keyword",
            was_fallback=ai_enabled,  # fallback only if AI was supposed to be used
            fallback_reason=reason,
            processing_time_ms=rule_result["processing_time_ms"],
            circuit_breaker_state=await cb.get_state(),
        )

    async def assign(
        self,
        request: Dict[str, Any],
        company_id: str = "",
    ) -> MigrationAssignResult:
        """Assign a ticket using AI, falling back to rule-based.

        ``request`` must contain at least ``intent`` and ``priority``.
        Additional fields (``customer_id``, ``language``, etc.) are
        forwarded to the AI engine when available.

        BC-001: company_id is the second parameter.
        """
        intent = request.get("intent", "general")
        priority = request.get("priority", "medium")

        cb = await self._load_circuit_breaker(company_id, "assignment")
        cb_state = await cb.get_state()
        ai_enabled = await self._is_ai_enabled(company_id, "assignment")

        should_try_ai = ai_enabled and await cb.can_execute()

        if should_try_ai:
            try:
                engine = self._get_assignment_engine()

                # Build a request object compatible with AIAssignmentEngine
                assign_request = self._build_ai_assign_request(request)

                assign_result = await engine.assign_ticket(assign_request)

                await cb.record_success()
                await self._save_circuit_breaker(company_id, "assignment")
                await self._record_ai_call(company_id, "assignment", success=True)

                logger.info(
                    "assign_ai_success company_id=%s agent_id=%s",
                    company_id,
                    getattr(assign_result, "assigned_agent_id", ""),
                    method="ai",
                )

                return MigrationAssignResult(
                    assigned_agent_id=getattr(assign_result, "assigned_agent_id", ""),
                    assigned_agent_name=getattr(
                        assign_result, "assigned_agent_name", "AI Agent"
                    ),
                    method="ai",
                    was_fallback=False,
                    fallback_reason=None,
                    score_breakdown=getattr(assign_result, "score_breakdown", None),
                    processing_time_ms=getattr(
                        assign_result, "processing_time_ms", 0.0
                    ),
                )

            except Exception as exc:
                await cb.record_failure()
                await self._save_circuit_breaker(company_id, "assignment")
                await self._record_ai_call(company_id, "assignment", success=False)

                fallback_reason = f"ai_error: {str(exc)[:120]}"
                logger.warning(
                    "assign_ai_failed company_id=%s error=%s",
                    company_id,
                    str(exc),
                    circuit_state=await cb.get_state(),
                )

                rule_result = await self._rule_assigner.assign(intent, priority)

                await self._record_fallback_event(
                    company_id,
                    "assignment",
                    fallback_reason,
                    details={"intent": intent, "priority": priority},
                )

                return MigrationAssignResult(
                    assigned_agent_id=rule_result["agent_id"],
                    assigned_agent_name=rule_result["agent_name"],
                    method="rule",
                    was_fallback=True,
                    fallback_reason=fallback_reason,
                    score_breakdown=rule_result.get("score_breakdown"),
                    processing_time_ms=rule_result["processing_time_ms"],
                )

        # ── Circuit open or AI disabled → rule-based ────────────
        reason: Optional[str] = None
        if not ai_enabled:
            reason = "ai_disabled_for_company"
        elif not await cb.can_execute():
            reason = f"circuit_breaker_open (state={cb_state})"

        rule_result = await self._rule_assigner.assign(intent, priority)

        if reason:
            await self._record_fallback_event(
                company_id,
                "assignment",
                reason,
                details={"intent": intent, "priority": priority},
            )

            logger.info(
                "assign_rule_fallback company_id=%s intent=%s priority=%s reason=%s",
                company_id,
                intent,
                priority,
                reason,
            )

        return MigrationAssignResult(
            assigned_agent_id=rule_result["agent_id"],
            assigned_agent_name=rule_result["agent_name"],
            method="rule",
            was_fallback=ai_enabled,
            fallback_reason=reason,
            score_breakdown=rule_result.get("score_breakdown"),
            processing_time_ms=rule_result["processing_time_ms"],
        )

    async def get_migration_status(self, company_id: str) -> MigrationStatus:
        """Return a snapshot of migration state for *company_id*.

        Aggregates circuit breaker states, toggle settings, and
        running counters from Redis.
        """
        # Circuit breaker states
        classif_cb = await self._load_circuit_breaker(company_id, "classification")
        assign_cb = await self._load_circuit_breaker(company_id, "assignment")

        classif_cb_state = await classif_cb.get_state()
        assign_cb_state = await assign_cb.get_state()

        # Feature toggles
        classif_method = (
            "ai" if await self._is_ai_enabled(company_id, "classification") else "rule"
        )
        assign_method = (
            "ai" if await self._is_ai_enabled(company_id, "assignment") else "rule"
        )

        # Stats from Redis
        stats: Dict[str, int] = {}
        if self._redis is not None:
            try:
                raw = await self._redis.hgetall(_stats_redis_key(company_id))
                if raw:
                    stats = {
                        (k.decode("utf-8") if isinstance(k, bytes) else k): (
                            int(v) if isinstance(v, (bytes, str, int)) else 0
                        )
                        for k, v in raw.items()
                    }
            except Exception:
                logger.warning("migration_stats_read_failed company=%s", company_id)

        total_ai = stats.get("total_ai_calls", 0)
        total_successes = stats.get("total_ai_successes", 0)
        total_fallbacks = stats.get("total_rule_fallbacks", 0)

        ai_success_rate = round(total_successes / total_ai, 4) if total_ai > 0 else 1.0

        return MigrationStatus(
            company_id=company_id,
            classification_method=classif_method,
            assignment_method=assign_method,
            classification_circuit_state=classif_cb_state,
            assignment_circuit_state=assign_cb_state,
            classification_fallback_count=stats.get("classification_fallbacks", 0),
            assignment_fallback_count=stats.get("assignment_fallbacks", 0),
            total_ai_calls=total_ai,
            total_rule_fallbacks=total_fallbacks,
            ai_success_rate=ai_success_rate,
        )

    async def enable_ai(self, company_id: str, feature: str) -> None:
        """Enable AI for *feature* (``"classification"`` or ``"assignment"``).

        Does NOT reset the circuit breaker — use ``reset_circuit`` if
        you want to force-close it as well.
        """
        if feature not in _FEATURES:
            raise ValueError(f"Invalid feature '{feature}'. Must be one of: {
                    ', '.join(_FEATURES)}")
        key = _method_redis_key(company_id, feature)
        await self._redis_set(key, "ai")
        logger.info("ai_enabled company_id=%s feature=%s", company_id, feature)

    async def disable_ai(self, company_id: str, feature: str) -> None:
        """Disable AI for *feature*, forcing rule-based processing."""
        if feature not in _FEATURES:
            raise ValueError(f"Invalid feature '{feature}'. Must be one of: {
                    ', '.join(_FEATURES)}")
        key = _method_redis_key(company_id, feature)
        await self._redis_set(key, "rule")
        logger.info("ai_disabled company_id=%s feature=%s", company_id, feature)

    async def get_fallback_stats(self, company_id: str) -> FallbackStats:
        """Return detailed fallback statistics for a company.

        Includes per-feature breakdowns, recent fallback events,
        and circuit breaker history.
        """
        # ── Per-feature counters from Redis ───────────────────
        stats: Dict[str, int] = {}
        if self._redis is not None:
            try:
                raw = await self._redis.hgetall(_stats_redis_key(company_id))
                if raw:
                    stats = {
                        (k.decode("utf-8") if isinstance(k, bytes) else k): (
                            int(v) if isinstance(v, (bytes, str, int)) else 0
                        )
                        for k, v in raw.items()
                    }
            except Exception:
                logger.warning("fallback_stats_read_failed company=%s", company_id)

        classif_ai = stats.get("classification_ai_calls", 0)
        classif_success = stats.get("classification_ai_successes", 0)
        classif_fallbacks = stats.get("classification_fallbacks", 0)

        assign_ai = stats.get("assignment_ai_calls", 0)
        assign_success = stats.get("assignment_ai_successes", 0)
        assign_fallbacks = stats.get("assignment_fallbacks", 0)

        # ── Recent fallback log ────────────────────────────────
        raw_log = await self._redis_lrange(_fallback_log_key(company_id), 0, 9)
        recent_fallbacks: List[Dict[str, Any]] = []
        for entry in raw_log:
            try:
                recent_fallbacks.append(json.loads(entry))
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Circuit breaker snapshots ──────────────────────────
        circuit_history: List[Dict[str, Any]] = []
        for feat in _FEATURES:
            cb = await self._load_circuit_breaker(company_id, feat)
            circuit_history.append(cb.to_dict())

        return FallbackStats(
            company_id=company_id,
            classification={
                "ai_calls": classif_ai,
                "ai_successes": classif_success,
                "fallbacks": classif_fallbacks,
                "success_rate": (
                    round(classif_success / classif_ai, 4) if classif_ai > 0 else 1.0
                ),
                "avg_confidence": 0.0,  # not tracked without DB queries
            },
            assignment={
                "ai_calls": assign_ai,
                "ai_successes": assign_success,
                "fallbacks": assign_fallbacks,
                "success_rate": (
                    round(assign_success / assign_ai, 4) if assign_ai > 0 else 1.0
                ),
            },
            recent_fallbacks=recent_fallbacks,
            circuit_breaker_history=circuit_history,
        )

    async def reset_circuit(self, company_id: str, feature: str) -> None:
        """Force-close a circuit breaker (admin operation).

        Resets both in-memory and Redis state.
        """
        if feature not in _FEATURES:
            raise ValueError(f"Invalid feature '{feature}'. Must be one of: {
                    ', '.join(_FEATURES)}")
        cb = self._breakers[feature]
        await cb.reset()
        await self._save_circuit_breaker(company_id, feature)
        logger.info(
            "circuit_reset_by_admin company_id=%s feature=%s", company_id, feature
        )

    async def get_circuit_state(self, company_id: str, feature: str) -> Dict[str, Any]:
        """Return circuit breaker details for a feature."""
        if feature not in _FEATURES:
            raise ValueError(f"Invalid feature '{feature}'. Must be one of: {
                    ', '.join(_FEATURES)}")
        cb = await self._load_circuit_breaker(company_id, feature)
        return cb.to_dict()

    # ── Private helpers ───────────────────────────────────────────

    @staticmethod
    def _build_ai_assign_request(ticket_data: Dict[str, Any]) -> Any:
        """Build a ``TicketAssignmentRequest`` for the AI engine.

        Uses a try/except import so this module can be loaded even if
        ``ai_assignment_engine`` has not been created yet.
        """
        try:
            from app.core.ai_assignment_engine import TicketAssignmentRequest

            return TicketAssignmentRequest(
                ticket_id=ticket_data.get("ticket_id", ""),
                company_id=ticket_data.get("company_id", ""),
                intent_type=ticket_data.get("intent", "general"),
                priority=ticket_data.get("priority", "medium"),
                sentiment_score=ticket_data.get("sentiment_score", 0.5),
                customer_tier=ticket_data.get("customer_tier", "basic"),
                variant_type=ticket_data.get("variant_type", "parwa"),
                customer_id=ticket_data.get("customer_id"),
                language=ticket_data.get("language", "en"),
                channel=ticket_data.get("channel", "email"),
            )
        except ImportError:
            # If AI assignment engine doesn't exist yet, return the raw dict.
            # The assign() method's try/except will catch the resulting error
            # and fall back to rules.
            logger.debug(
                "ai_assignment_engine_not_available detail=%s",
                "Falling back to rule-based assignment",
            )
            return ticket_data


# ═══════════════════════════════════════════════════════════════════════
#  Convenience singleton (for use in dependency injection)
# ═══════════════════════════════════════════════════════════════════════

_default_engine: Optional[RuleAIMigrationEngine] = None


async def get_migration_engine(
    redis_client: Optional[Any] = None,
    db: Optional[Any] = None,
) -> RuleAIMigrationEngine:
    """Return the module-level singleton, creating it if necessary."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RuleAIMigrationEngine(
            redis_client=redis_client,
            db=db,
        )
    return _default_engine
