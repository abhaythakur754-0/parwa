"""
Usage Burst Protection Service (SG-16)

Detects and mitigates abnormal usage bursts that could indicate abuse,
DDoS attempts, or runaway processes across PARWA SaaS tenants.

PARWA Variants:
  mini_parwa  (L1): lightweight tier  — 60 RPM,   5 concurrent
  parwa       (L2): standard tier     — 200 RPM,  20 concurrent
  parwa_high  (L3): premium tier      — 600 RPM, 100 concurrent

Burst Detection Logic:
  - Tracks requests in a rolling 60-second window per company.
  - Calculates current RPM (requests per minute) and compares
    against variant-specific thresholds.
  - Escalation:  RPM > threshold × burst_multiplier → CRITICAL / BLOCK
                 RPM > threshold                      → HIGH    / THROTTLE
                 RPM > threshold × 0.8                → MEDIUM  / warn-only
  - Elevated error rates amplify severity.
  - Concurrent-request limits are enforced independently.

BC-001: All public methods take company_id as first parameter.
BC-008: Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════

class BurstSeverity(str, Enum):
    """Severity levels for burst-detection alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BurstAction(str, Enum):
    """Possible enforcement actions when a burst is detected."""
    ALLOW = "allow"
    THROTTLE = "throttle"
    RATE_LIMIT = "rate_limit"
    BLOCK = "block"


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class UsageMetrics:
    """Snapshot of current API usage for a single company.

    All counters reflect the rolling ``window_seconds`` window.
    """
    company_id: str
    total_requests: int = 0
    requests_per_minute: float = 0.0
    peak_rpm: float = 0.0
    avg_response_time_ms: float = 0.0
    error_rate_pct: float = 0.0
    unique_users: int = 0
    window_seconds: int = 60


@dataclass
class BurstDetection:
    """Result of a burst-detection check for a company.

    Includes the severity, recommended action, and supporting
    data such as the burst multiplier (current / threshold).
    """
    company_id: str
    severity: BurstSeverity = BurstSeverity.LOW
    action: BurstAction = BurstAction.ALLOW
    current_rpm: float = 0.0
    threshold_rpm: float = 0.0
    burst_multiplier: float = 0.0
    reason: str = ""
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    details: Dict = field(default_factory=dict)


@dataclass
class ThrottleDecision:
    """Decision on whether an incoming request should be allowed,
    throttled, rate-limited, or blocked outright.

    ``allowed`` is ``True`` only when the request may proceed
    without any restriction.
    """
    company_id: str
    allowed: bool = True
    throttle_rate: float = 1.0
    retry_after_seconds: float = 0.0
    reason: str = ""


@dataclass
class BurstProtectionConfig:
    """Tuneable thresholds and limits per PARWA variant.

    ``rpm_thresholds``  — max *normal* RPM per variant.
    ``burst_multiplier_threshold`` — multiplier above which a
        usage spike is classified as a burst.
    ``max_concurrent_requests`` — hard cap on simultaneous in-flight
        requests per variant.
    ``error_rate_threshold_pct`` — if the error rate exceeds this
        percentage, burst severity is upgraded by one level.
    ``alert_cooldown_seconds`` — minimum interval between consecutive
        alerts for the same company to reduce alert fatigue.
    """
    rpm_thresholds: Dict[str, int] = field(
        default_factory=lambda: {
            "mini_parwa": 60,
            "parwa": 200,
            "parwa_high": 600,
        },
    )
    burst_multiplier_threshold: float = 3.0
    window_seconds: int = 60
    throttle_duration_seconds: int = 30
    block_duration_seconds: int = 300
    max_concurrent_requests: Dict[str, int] = field(
        default_factory=lambda: {
            "mini_parwa": 5,
            "parwa": 20,
            "parwa_high": 100,
        },
    )
    error_rate_threshold_pct: float = 50.0
    alert_cooldown_seconds: int = 300


# ══════════════════════════════════════════════════════════════════
# CUSTOM ERROR
# ══════════════════════════════════════════════════════════════════

class BurstProtectionError(ParwaBaseError):
    """Raised when a burst-protection policy is violated."""
    pass


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_VARIANT_TYPES = {"mini_parwa", "parwa", "parwa_high"}

# Maximum number of alerts retained per company (prevents
# unbounded memory growth in long-running processes).
_MAX_ALERTS_PER_COMPANY = 100

# Maximum number of request-history entries retained per company.
_MAX_HISTORY_ENTRIES = 10_000


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════

def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required and non-empty."""
    if not company_id or not str(company_id).strip():
        raise BurstProtectionError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate that *variant_type* is a known PARWA variant."""
    if variant_type not in VALID_VARIANT_TYPES:
        raise BurstProtectionError(
            error_code="INVALID_VARIANT_TYPE",
            message=(
                f"Invalid variant_type '{variant_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_VARIANT_TYPES))}"
            ),
            status_code=400,
        )


# ══════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════

class UsageBurstProtectionService:
    """
    Usage Burst Protection Service (SG-16).

    Monitors per-company API request rates in a rolling time window
    and detects abnormal usage bursts.  When a burst is detected the
    service recommends an enforcement action (throttle / rate-limit /
    block) that callers can apply at the middleware or API-gateway
    layer.

    All public methods accept ``company_id`` as their first argument
    (BC-001) and are wrapped in try/except for graceful degradation
    (BC-008).

    Supports optional Redis for distributed state; falls back to an
    in-memory store protected by ``threading.Lock`` (replaced with
    ``RLock`` in unit tests for re-entrant safety).
    """

    # ── Constructor ─────────────────────────────────────────────

    def __init__(
        self,
        config: Optional[BurstProtectionConfig] = None,
        redis_client=None,
    ) -> None:
        self.config = config or BurstProtectionConfig()
        self._redis = redis_client

        # ── In-memory state (fallback when Redis is unavailable) ──
        # request_history[company_id] = list of dicts with
        #   keys: timestamp, response_time_ms, success, user_id
        self._request_history: Dict[str, List[dict]] = {}

        # peak_rpm tracking per company (high-water mark)
        self._peak_rpm: Dict[str, float] = {}

        # Burst alerts per company
        self._alerts: Dict[str, List[BurstDetection]] = {}

        # Throttle/block state per company:
        #   {"action": "throttle"|"block",
        #    "expires_at": <unix_ts>,
        #    "set_at": <unix_ts>}
        self._throttle_state: Dict[str, dict] = {}

        # Currently active (in-flight) requests per company
        self._concurrent_requests: Dict[str, int] = {}

        # Last alert timestamp per company (for cooldown)
        self._last_alert_at: Dict[str, float] = {}

        # Thread lock — patched to RLock in tests
        self._lock = threading.Lock()

    # ── Redis key helpers ───────────────────────────────────────

    @staticmethod
    def _redis_history_key(company_id: str) -> str:
        """Key for the sorted-set storing request timestamps."""
        return f"parwa:ubp:history:{company_id}"

    @staticmethod
    def _redis_peak_key(company_id: str) -> str:
        """Key for the peak RPM counter."""
        return f"parwa:ubp:peak:{company_id}"

    @staticmethod
    def _redis_throttle_key(company_id: str) -> str:
        """Key for the throttle/block state hash."""
        return f"parwa:ubp:throttle:{company_id}"

    @staticmethod
    def _redis_concurrent_key(company_id: str) -> str:
        """Key for the concurrent-request counter."""
        return f"parwa:ubp:concurrent:{company_id}"

    @staticmethod
    def _redis_alert_key(company_id: str) -> str:
        """Key for the last-alert timestamp."""
        return f"parwa:ubp:last_alert:{company_id}"

    # ── Internal: request history ───────────────────────────────

    def _get_request_history(self, company_id: str) -> List[dict]:
        """Return request records for *company_id* within the
        configured rolling window.

        Each record is a dict with keys:
          ``timestamp``, ``response_time_ms``, ``success``, ``user_id``

        Prefer Redis sorted-set when available; otherwise fall back
        to the in-memory list.
        """
        now = time.time()
        cutoff = now - self.config.window_seconds

        # ── Redis path ──
        if self._redis is not None:
            try:
                key = self._redis_history_key(company_id)
                # Fetch entries within the window using score range.
                # Score = unix timestamp of the request.
                raw = self._redis.zrangebyscore(key, cutoff, now)
                if raw:
                    import json
                    return [json.loads(entry) for entry in raw]
                return []
            except Exception as exc:
                logger.warning(
                    "redis_history_read_failed_falling_back",
                    company_id=company_id,
                    error=str(exc),
                )

        # ── In-memory fallback ──
        history = self._request_history.get(company_id, [])
        # Prune entries outside the window
        pruned = [
            entry for entry in history
            if entry["timestamp"] >= cutoff
        ]
        with self._lock:
            self._request_history[company_id] = pruned
        return pruned

    # ── Internal: RPM calculation ───────────────────────────────

    def _calculate_rpm(self, company_id: str) -> float:
        """Calculate the current requests-per-minute for *company_id*.

        RPM is derived from the count of requests in the rolling
        window, normalised to a 60-second rate.
        """
        try:
            history = self._get_request_history(company_id)
            window = self.config.window_seconds
            # Scale the request count to a per-minute rate
            rpm = (len(history) / window) * 60.0 if window > 0 else 0.0

            # Update peak RPM tracking (high-water mark)
            if rpm > self._peak_rpm.get(company_id, 0.0):
                self._peak_rpm[company_id] = rpm
                # Also update in Redis if available
                if self._redis is not None:
                    try:
                        self._redis.set(
                            self._redis_peak_key(company_id),
                            str(rpm),
                            ex=self.config.window_seconds * 2,
                        )
                    except Exception as exc:
                        logger.warning(
                            "redis_peak_write_failed",
                            company_id=company_id,
                            error=str(exc),
                        )

            return rpm
        except Exception as exc:
            logger.error(
                "calculate_rpm_error",
                company_id=company_id,
                error=str(exc),
            )
            return 0.0

    # ── Internal: burst pattern detection ───────────────────────

    def _detect_burst_pattern(
        self,
        company_id: str,
        variant_type: str,
    ) -> Optional[BurstDetection]:
        """Evaluate the current usage pattern for *company_id* and
        return a :class:`BurstDetection` if a burst is identified,
        or ``None`` if usage is normal.

        Detection rules (applied in order of severity):
          1. Concurrent requests exceeding variant max → BLOCK
          2. RPM > threshold × burst_multiplier → CRITICAL / BLOCK
          3. RPM > threshold → HIGH / THROTTLE
          4. RPM > threshold × 0.8 → MEDIUM / ALLOW (warning only)
          5. Elevated error rate upgrades severity by one level.
        """
        try:
            rpm_threshold = self.config.rpm_thresholds.get(
                variant_type, 200,
            )
            burst_mult = self.config.burst_multiplier_threshold
            current_rpm = self._calculate_rpm(company_id)
            history = self._get_request_history(company_id)

            # ── Error rate calculation ──
            error_rate = 0.0
            if history:
                error_count = sum(
                    1 for entry in history if not entry.get("success", True)
                )
                error_rate = (error_count / len(history)) * 100.0

            # ── Unique user count ──
            unique_users = len({
                entry.get("user_id")
                for entry in history
                if entry.get("user_id") is not None
            })

            # ── 1. Concurrent request check ──
            max_concurrent = self.config.max_concurrent_requests.get(
                variant_type, 20,
            )
            current_concurrent = self._concurrent_requests.get(
                company_id, 0,
            )

            if current_concurrent > max_concurrent:
                burst_multiplier_val = (
                    current_concurrent / max_concurrent
                    if max_concurrent > 0 else 0.0
                )
                return BurstDetection(
                    company_id=company_id,
                    severity=BurstSeverity.CRITICAL,
                    action=BurstAction.BLOCK,
                    current_rpm=current_rpm,
                    threshold_rpm=float(rpm_threshold),
                    burst_multiplier=burst_multiplier_val,
                    reason=(
                        f"Concurrent requests ({current_concurrent}) "
                        f"exceed max ({max_concurrent}) for "
                        f"variant '{variant_type}'"
                    ),
                    details={
                        "concurrent_requests": current_concurrent,
                        "max_concurrent": max_concurrent,
                        "variant_type": variant_type,
                        "error_rate_pct": round(error_rate, 2),
                        "unique_users": unique_users,
                    },
                )

            # ── 2–4. RPM-based checks ──
            severity: Optional[BurstSeverity] = None
            action: Optional[BurstAction] = None
            reason = ""
            burst_multiplier_val = 0.0

            if current_rpm == 0:
                # No traffic — nothing to detect
                return None

            if current_rpm > rpm_threshold * burst_mult:
                # ── CRITICAL: extreme burst ──
                severity = BurstSeverity.CRITICAL
                action = BurstAction.BLOCK
                burst_multiplier_val = current_rpm / rpm_threshold
                reason = (
                    f"RPM ({current_rpm:.1f}) exceeds "
                    f"{burst_mult}× threshold ({rpm_threshold}) — "
                    f"critical burst detected"
                )
            elif current_rpm > rpm_threshold:
                # ── HIGH: over threshold ──
                severity = BurstSeverity.HIGH
                action = BurstAction.THROTTLE
                burst_multiplier_val = current_rpm / rpm_threshold
                reason = (
                    f"RPM ({current_rpm:.1f}) exceeds threshold "
                    f"({rpm_threshold}) — high burst detected"
                )
            elif current_rpm > rpm_threshold * 0.8:
                # ── MEDIUM: approaching threshold ──
                severity = BurstSeverity.MEDIUM
                action = BurstAction.ALLOW
                burst_multiplier_val = current_rpm / rpm_threshold
                reason = (
                    f"RPM ({current_rpm:.1f}) approaching threshold "
                    f"({rpm_threshold}) — medium burst warning"
                )

            if severity is None or action is None:
                return None

            # ── 5. Error-rate severity upgrade ──
            error_threshold = self.config.error_rate_threshold_pct
            if error_rate > error_threshold:
                severity = self._upgrade_severity(severity)
                if action == BurstAction.ALLOW:
                    action = BurstAction.THROTTLE
                reason += (
                    f" (upgraded: error rate {error_rate:.1f}% > "
                    f"{error_threshold}%)"
                )

            return BurstDetection(
                company_id=company_id,
                severity=severity,
                action=action,
                current_rpm=current_rpm,
                threshold_rpm=float(rpm_threshold),
                burst_multiplier=burst_multiplier_val,
                reason=reason,
                details={
                    "variant_type": variant_type,
                    "error_rate_pct": round(error_rate, 2),
                    "unique_users": unique_users,
                    "window_seconds": self.config.window_seconds,
                    "total_requests_in_window": len(history),
                },
            )

        except Exception as exc:
            logger.error(
                "detect_burst_pattern_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            return None

    @staticmethod
    def _upgrade_severity(current: BurstSeverity) -> BurstSeverity:
        """Upgrade burst severity by one level.

        LOW → MEDIUM, MEDIUM → HIGH, HIGH → CRITICAL.
        CRITICAL cannot be upgraded further.
        """
        upgrade_map = {
            BurstSeverity.LOW: BurstSeverity.MEDIUM,
            BurstSeverity.MEDIUM: BurstSeverity.HIGH,
            BurstSeverity.HIGH: BurstSeverity.CRITICAL,
            BurstSeverity.CRITICAL: BurstSeverity.CRITICAL,
        }
        return upgrade_map.get(current, BurstSeverity.CRITICAL)

    # ── Internal: create alert ──────────────────────────────────

    def _create_alert(
        self,
        company_id: str,
        severity: BurstSeverity,
        action: BurstAction,
        reason: str,
        details: Optional[Dict] = None,
    ) -> BurstDetection:
        """Create and store a burst alert for *company_id*.

        Respects ``alert_cooldown_seconds`` to prevent alert fatigue.
        If cooldown has not elapsed the call is a no-op and returns
        the last recorded alert.
        """
        now = time.time()
        last_alert = self._last_alert_at.get(company_id, 0.0)

        if now - last_alert < self.config.alert_cooldown_seconds:
            # Cooldown period — skip alert creation
            existing_alerts = self._alerts.get(company_id, [])
            if existing_alerts:
                return existing_alerts[-1]
            # Should not happen, but return a sensible default
            return BurstDetection(
                company_id=company_id,
                severity=severity,
                action=action,
                reason="(cooldown active — alert suppressed)",
                details=details or {},
            )

        alert = BurstDetection(
            company_id=company_id,
            severity=severity,
            action=action,
            reason=reason,
            details=details or {},
        )

        with self._lock:
            if company_id not in self._alerts:
                self._alerts[company_id] = []
            self._alerts[company_id].append(alert)
            # Enforce per-company alert cap
            if len(self._alerts[company_id]) > _MAX_ALERTS_PER_COMPANY:
                self._alerts[company_id] = self._alerts[company_id][
                    -_MAX_ALERTS_PER_COMPANY:
                ]
            self._last_alert_at[company_id] = now

        logger.warning(
            "burst_alert_created",
            company_id=company_id,
            severity=severity.value,
            action=action.value,
            reason=reason,
        )
        return alert

    # ── Internal: throttle state ────────────────────────────────

    def _get_throttle_state(self, company_id: str) -> dict:
        """Return the current throttle/block state for *company_id*.

        State dict keys:
          ``action``    — "throttle" or "block"
          ``expires_at`` — unix timestamp when the state expires
          ``set_at``    — unix timestamp when the state was set

        Returns an empty dict if no active throttle/block is in
        effect (i.e. the state has expired or was never set).
        """
        # ── Redis path ──
        if self._redis is not None:
            try:
                key = self._redis_throttle_key(company_id)
                state = self._redis.hgetall(key)
                if state:
                    import json
                    expires_at = float(state.get(b"expires_at", 0))
                    if expires_at > time.time():
                        return {
                            "action": state.get(b"action", b"").decode(),
                            "expires_at": expires_at,
                            "set_at": float(state.get(b"set_at", 0)),
                        }
                    else:
                        # Expired — clean up
                        self._redis.delete(key)
            except Exception as exc:
                logger.warning(
                    "redis_throttle_state_read_failed",
                    company_id=company_id,
                    error=str(exc),
                )

        # ── In-memory fallback ──
        state = self._throttle_state.get(company_id)
        if not state:
            return {}

        if state.get("expires_at", 0) > time.time():
            return state

        # State has expired — clean up
        with self._lock:
            self._throttle_state.pop(company_id, None)
        return {}

    def _set_throttle_state(
        self,
        company_id: str,
        action: str,
        duration_seconds: int,
    ) -> None:
        """Activate a throttle or block for *company_id* lasting
        *duration_seconds*.
        """
        now = time.time()
        expires_at = now + duration_seconds
        state = {
            "action": action,
            "expires_at": expires_at,
            "set_at": now,
        }

        # ── Redis path ──
        if self._redis is not None:
            try:
                key = self._redis_throttle_key(company_id)
                self._redis.hset(key, mapping=state)
                self._redis.expireat(key, int(expires_at))
            except Exception as exc:
                logger.warning(
                    "redis_throttle_state_write_failed",
                    company_id=company_id,
                    error=str(exc),
                )

        # ── In-memory fallback ──
        with self._lock:
            self._throttle_state[company_id] = state

        logger.info(
            "throttle_state_set",
            company_id=company_id,
            action=action,
            duration_seconds=duration_seconds,
            expires_at=expires_at,
        )

    # ── Internal: helper to compute usage metrics ───────────────

    def _compute_metrics(self, company_id: str) -> UsageMetrics:
        """Build a :class:`UsageMetrics` snapshot from the current
        rolling-window data for *company_id*.
        """
        history = self._get_request_history(company_id)
        current_rpm = self._calculate_rpm(company_id)
        peak_rpm = self._peak_rpm.get(company_id, 0.0)

        # Average response time (only from successful requests)
        response_times = [
            entry["response_time_ms"]
            for entry in history
            if entry.get("response_time_ms", 0) > 0
        ]
        avg_response_time = (
            sum(response_times) / len(response_times)
            if response_times else 0.0
        )

        # Error rate
        error_rate = 0.0
        if history:
            error_count = sum(
                1 for entry in history if not entry.get("success", True)
            )
            error_rate = (error_count / len(history)) * 100.0

        # Unique users
        unique_users = len({
            entry.get("user_id")
            for entry in history
            if entry.get("user_id") is not None
        })

        return UsageMetrics(
            company_id=company_id,
            total_requests=len(history),
            requests_per_minute=round(current_rpm, 2),
            peak_rpm=round(peak_rpm, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            error_rate_pct=round(error_rate, 2),
            unique_users=unique_users,
            window_seconds=self.config.window_seconds,
        )

    # ═══════════════════════════════════════════════════════════════
    # PUBLIC METHODS
    # ═══════════════════════════════════════════════════════════════

    def record_request(
        self,
        company_id: str,
        variant_type: str,
        response_time_ms: float = 0,
        success: bool = True,
        user_id: Optional[str] = None,
    ) -> UsageMetrics:
        """Track a single API request and return updated metrics.

        Records the request in the rolling window, increments the
        concurrent-request counter, and triggers a background burst
        check.  The concurrent counter is **not** decremented here —
        callers must invoke :meth:`_decrement_concurrent` (or the
        public wrapper) when the request completes.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        variant_type:
            PARWA variant (``mini_parwa``, ``parwa``, ``parwa_high``).
        response_time_ms:
            Wall-clock response time of the request.
        success:
            ``True`` if the request completed without error.
        user_id:
            Optional end-user identifier for unique-user tracking.

        Returns
        -------
        UsageMetrics
            Current usage snapshot after recording.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            now = time.time()
            entry = {
                "timestamp": now,
                "response_time_ms": response_time_ms,
                "success": success,
                "user_id": user_id,
            }

            # ── Redis path ──
            if self._redis is not None:
                try:
                    import json
                    key = self._redis_history_key(company_id)
                    self._redis.zadd(key, {json.dumps(entry): now})
                    # Evict entries outside the rolling window
                    cutoff = now - self.config.window_seconds
                    self._redis.zremrangebyscore(key, "-inf", cutoff)
                    self._redis.expire(
                        key, self.config.window_seconds * 2,
                    )
                except Exception as exc:
                    logger.warning(
                        "redis_request_record_failed_falling_back",
                        company_id=company_id,
                        error=str(exc),
                    )

            # ── In-memory fallback ──
            with self._lock:
                if company_id not in self._request_history:
                    self._request_history[company_id] = []
                self._request_history[company_id].append(entry)
                # Enforce history cap
                if (
                    len(self._request_history[company_id])
                    > _MAX_HISTORY_ENTRIES
                ):
                    self._request_history[company_id] = (
                        self._request_history[company_id]
                        [-_MAX_HISTORY_ENTRIES:]
                    )

            # Increment concurrent requests
            with self._lock:
                self._concurrent_requests[company_id] = (
                    self._concurrent_requests.get(company_id, 0) + 1
                )

            # Run burst check in the background (best-effort)
            try:
                burst = self._detect_burst_pattern(company_id, variant_type)
                if burst is not None and burst.action != BurstAction.ALLOW:
                    self._create_alert(
                        company_id=company_id,
                        severity=burst.severity,
                        action=burst.action,
                        reason=burst.reason,
                        details=burst.details,
                    )
                    # Auto-apply throttle/block
                    if burst.action == BurstAction.BLOCK:
                        self._set_throttle_state(
                            company_id,
                            "block",
                            self.config.block_duration_seconds,
                        )
                    elif burst.action == BurstAction.THROTTLE:
                        self._set_throttle_state(
                            company_id,
                            "throttle",
                            self.config.throttle_duration_seconds,
                        )
            except Exception as exc:
                logger.warning(
                    "background_burst_check_failed",
                    company_id=company_id,
                    error=str(exc),
                )

            metrics = self._compute_metrics(company_id)

            logger.debug(
                "request_recorded",
                company_id=company_id,
                variant_type=variant_type,
                current_rpm=metrics.requests_per_minute,
                success=success,
                response_time_ms=response_time_ms,
            )

            return metrics

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "record_request_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            return UsageMetrics(
                company_id=company_id,
                reason=f"Record error (graceful degradation): {exc}",
            )

    def decrement_concurrent(self, company_id: str) -> None:
        """Decrement the in-flight request counter for *company_id*.

        Call this when a request handled by :meth:`record_request`
        completes its processing.  If the counter drops to zero or
        below it is clamped to zero.
        """
        try:
            _validate_company_id(company_id)

            with self._lock:
                current = self._concurrent_requests.get(company_id, 0)
                self._concurrent_requests[company_id] = max(0, current - 1)

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "decrement_concurrent_error",
                company_id=company_id,
                error=str(exc),
            )

    def check_burst(
        self,
        company_id: str,
        variant_type: Optional[str] = None,
    ) -> BurstDetection:
        """Check whether the current usage pattern for *company_id*
        indicates a burst.

        If *variant_type* is ``None`` the method defaults to
        ``"parwa"`` (the standard tier) for threshold lookups.

        Returns a :class:`BurstDetection` with ``severity=LOW`` and
        ``action=ALLOW`` when no burst is detected.
        """
        try:
            _validate_company_id(company_id)

            if variant_type is None:
                variant_type = "parwa"

            _validate_variant_type(variant_type)

            detection = self._detect_burst_pattern(
                company_id, variant_type,
            )

            if detection is not None:
                # Persist alert for non-trivial detections
                if detection.severity in (
                    BurstSeverity.HIGH,
                    BurstSeverity.CRITICAL,
                ):
                    self._create_alert(
                        company_id=company_id,
                        severity=detection.severity,
                        action=detection.action,
                        reason=detection.reason,
                        details=detection.details,
                    )
                logger.info(
                    "burst_detected",
                    company_id=company_id,
                    severity=detection.severity.value,
                    action=detection.action.value,
                    current_rpm=detection.current_rpm,
                    threshold_rpm=detection.threshold_rpm,
                )
                return detection

            # No burst — return a benign detection
            return BurstDetection(
                company_id=company_id,
                severity=BurstSeverity.LOW,
                action=BurstAction.ALLOW,
                current_rpm=self._calculate_rpm(company_id),
                threshold_rpm=float(
                    self.config.rpm_thresholds.get(variant_type, 200)
                ),
                reason="Usage within normal thresholds",
            )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "check_burst_error",
                company_id=company_id,
                error=str(exc),
            )
            return BurstDetection(
                company_id=company_id,
                severity=BurstSeverity.LOW,
                action=BurstAction.ALLOW,
                reason=f"Burst check error (graceful degradation): {exc}",
            )

    def get_throttle_decision(
        self,
        company_id: str,
        variant_type: str,
    ) -> ThrottleDecision:
        """Determine whether the next request from *company_id*
        should be allowed, throttled, rate-limited, or blocked.

        Checks are applied in the following order:
          1. Is there an active block? → BLOCK
          2. Is there an active throttle? → THROTTLE
          3. Is the current RPM above the burst multiplier? → BLOCK
          4. Is the current RPM above the threshold? → THROTTLE
          5. Otherwise → ALLOW

        Returns a :class:`ThrottleDecision` with ``allowed=True``
        when no restriction is necessary.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            # ── 1. Check active throttle/block state ──
            state = self._get_throttle_state(company_id)
            if state:
                action = state.get("action", "")
                expires_at = state.get("expires_at", 0)
                retry_after = max(0.0, expires_at - time.time())

                if action == "block":
                    return ThrottleDecision(
                        company_id=company_id,
                        allowed=False,
                        throttle_rate=0.0,
                        retry_after_seconds=round(retry_after, 2),
                        reason=(
                            f"Company is blocked. "
                            f"Retry after {retry_after:.0f}s."
                        ),
                    )

                if action == "throttle":
                    # Calculate throttle rate based on RPM vs threshold
                    rpm = self._calculate_rpm(company_id)
                    threshold = float(
                        self.config.rpm_thresholds.get(variant_type, 200)
                    )
                    throttle_rate = (
                        threshold / rpm if rpm > 0 else 1.0
                    )
                    throttle_rate = max(0.1, min(1.0, throttle_rate))

                    return ThrottleDecision(
                        company_id=company_id,
                        allowed=True,
                        throttle_rate=round(throttle_rate, 2),
                        retry_after_seconds=round(retry_after, 2),
                        reason=(
                            f"Company is throttled "
                            f"(rate={throttle_rate:.2f}). "
                            f"Full access after {retry_after:.0f}s."
                        ),
                    )

            # ── 2. Real-time burst check ──
            burst = self._detect_burst_pattern(company_id, variant_type)

            if burst is not None:
                if burst.action == BurstAction.BLOCK:
                    self._set_throttle_state(
                        company_id,
                        "block",
                        self.config.block_duration_seconds,
                    )
                    self._create_alert(
                        company_id=company_id,
                        severity=burst.severity,
                        action=burst.action,
                        reason=burst.reason,
                        details=burst.details,
                    )
                    return ThrottleDecision(
                        company_id=company_id,
                        allowed=False,
                        throttle_rate=0.0,
                        retry_after_seconds=float(
                            self.config.block_duration_seconds
                        ),
                        reason=(
                            f"Burst detected: {burst.reason}. "
                            f"Blocked for "
                            f"{self.config.block_duration_seconds}s."
                        ),
                    )

                if burst.action == BurstAction.THROTTLE:
                    self._set_throttle_state(
                        company_id,
                        "throttle",
                        self.config.throttle_duration_seconds,
                    )
                    self._create_alert(
                        company_id=company_id,
                        severity=burst.severity,
                        action=burst.action,
                        reason=burst.reason,
                        details=burst.details,
                    )
                    rpm = burst.current_rpm
                    threshold = burst.threshold_rpm
                    throttle_rate = (
                        threshold / rpm if rpm > 0 else 1.0
                    )
                    throttle_rate = max(0.1, min(1.0, throttle_rate))

                    return ThrottleDecision(
                        company_id=company_id,
                        allowed=True,
                        throttle_rate=round(throttle_rate, 2),
                        retry_after_seconds=float(
                            self.config.throttle_duration_seconds
                        ),
                        reason=(
                            f"Burst detected: {burst.reason}. "
                            f"Throttled (rate={throttle_rate:.2f}) for "
                            f"{self.config.throttle_duration_seconds}s."
                        ),
                    )

            # ── 3. All clear ──
            return ThrottleDecision(
                company_id=company_id,
                allowed=True,
                throttle_rate=1.0,
                retry_after_seconds=0.0,
                reason="Request allowed — usage within normal limits",
            )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_throttle_decision_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            # On error, allow the request (fail-open) for resilience
            return ThrottleDecision(
                company_id=company_id,
                allowed=True,
                throttle_rate=1.0,
                retry_after_seconds=0.0,
                reason=(
                    f"Throttle check error (fail-open): {exc}"
                ),
            )

    def get_usage_metrics(self, company_id: str) -> UsageMetrics:
        """Return the current rolling-window usage metrics for
        *company_id*.
        """
        try:
            _validate_company_id(company_id)
            return self._compute_metrics(company_id)
        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_usage_metrics_error",
                company_id=company_id,
                error=str(exc),
            )
            return UsageMetrics(
                company_id=company_id,
                reason=f"Metrics error (graceful degradation): {exc}",
            )

    def get_alerts(self, company_id: str) -> List[BurstDetection]:
        """Return recent burst alerts for *company_id*, ordered
        most-recent first.
        """
        try:
            _validate_company_id(company_id)

            alerts = self._alerts.get(company_id, [])
            # Return a copy in reverse chronological order
            return list(reversed(alerts))

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_alerts_error",
                company_id=company_id,
                error=str(exc),
            )
            return []

    def reset(self, company_id: str = "") -> None:
        """Reset all in-memory state for one company or every company.

        When *company_id* is empty (or whitespace) the entire service
        state is cleared.  This is primarily intended for use in
        tests and maintenance operations.
        """
        try:
            with self._lock:
                if company_id and company_id.strip():
                    self._request_history.pop(company_id, None)
                    self._peak_rpm.pop(company_id, None)
                    self._alerts.pop(company_id, None)
                    self._throttle_state.pop(company_id, None)
                    self._concurrent_requests.pop(company_id, None)
                    self._last_alert_at.pop(company_id, None)

                    # Also clean Redis keys when available
                    if self._redis is not None:
                        try:
                            keys_to_delete = [
                                self._redis_history_key(company_id),
                                self._redis_peak_key(company_id),
                                self._redis_throttle_key(company_id),
                                self._redis_concurrent_key(company_id),
                                self._redis_alert_key(company_id),
                            ]
                            self._redis.delete(*keys_to_delete)
                        except Exception as exc:
                            logger.warning(
                                "redis_reset_failed",
                                company_id=company_id,
                                error=str(exc),
                            )

                    logger.info("state_reset_for_company", company_id=company_id)
                else:
                    self._request_history.clear()
                    self._peak_rpm.clear()
                    self._alerts.clear()
                    self._throttle_state.clear()
                    self._concurrent_requests.clear()
                    self._last_alert_at.clear()

                    logger.info("full_state_reset")

        except Exception as exc:
            logger.error(
                "reset_error",
                company_id=company_id,
                error=str(exc),
            )

    def is_healthy(self, company_id: str) -> bool:
        """Quick health check — returns ``True`` if the service can
        access state for *company_id* without errors.

        Checks:
        - In-memory history is readable.
        - Redis is reachable (when configured).
        - No active block is in effect.
        """
        try:
            _validate_company_id(company_id)

            # Verify in-memory path works
            _ = self._get_request_history(company_id)

            # Verify Redis connectivity (when configured)
            if self._redis is not None:
                try:
                    self._redis.ping()
                except Exception as exc:
                    logger.warning(
                        "health_check_redis_unhealthy",
                        company_id=company_id,
                        error=str(exc),
                    )
                    # Redis down is not a hard failure — we have fallback
                    return True

            return True

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "is_healthy_error",
                company_id=company_id,
                error=str(exc),
            )
            return False

    def get_variant_config(
        self,
        company_id: str,
        variant_type: str,
    ) -> dict:
        """Return the burst-protection configuration relevant to
        *variant_type*, as a plain dict suitable for API responses.

        Includes RPM threshold, burst multiplier, max concurrent
        requests, throttle/block durations, and error-rate threshold.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            return {
                "variant_type": variant_type,
                "rpm_threshold": self.config.rpm_thresholds.get(
                    variant_type, 200,
                ),
                "burst_multiplier_threshold": (
                    self.config.burst_multiplier_threshold
                ),
                "window_seconds": self.config.window_seconds,
                "max_concurrent_requests": (
                    self.config.max_concurrent_requests.get(
                        variant_type, 20,
                    )
                ),
                "throttle_duration_seconds": (
                    self.config.throttle_duration_seconds
                ),
                "block_duration_seconds": (
                    self.config.block_duration_seconds
                ),
                "error_rate_threshold_pct": (
                    self.config.error_rate_threshold_pct
                ),
                "alert_cooldown_seconds": (
                    self.config.alert_cooldown_seconds
                ),
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_variant_config_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            return {
                "variant_type": variant_type,
                "error": f"Config retrieval failed: {exc}",
            }
