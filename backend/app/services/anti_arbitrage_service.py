"""
Anti-Arbitrage Service (F-159)

Detects and prevents multi-instance capacity gaming across PARWA variants.
Malicious tenants could create many cheap mini_parwa instances to get the
capacity of a parwa_high instance for less money.

Pricing Context:
  mini_parwa: $999 / 2,000 tickets  (weight=1.0)
  parwa:      $2,499 / 5,000 tickets (weight=2.5)
  parwa_high: $3,999 / 15,000 tickets (weight=7.5)

GAP Fixes:
  W9-GAP-014 (HIGH):   Atomic check with Redis INCR + Lua script for
                        instance creation — no race conditions.
  W9-GAP-025 (MEDIUM): Weighted capacity calculation across variants,
                        not just raw instance count.

BC-001: All public methods take company_id as first parameter.
BC-008: Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════

class ArbitrageAlertLevel(str, Enum):
    """Severity levels for arbitrage detection alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InstanceAction(str, Enum):
    """Possible outcomes of an instance creation check."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    FLAGGED = "flagged"
    LIMITED = "limited"


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class VariantInstance:
    """Represents a registered variant instance for a tenant."""
    instance_id: str
    variant_type: str
    company_id: str
    ticket_limit: int
    capacity_weight: float
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass
class CapacityCheck:
    """Result of a weighted capacity check for a tenant."""
    company_id: str
    current_weighted_capacity: float
    max_weighted_capacity: float
    instance_count: int
    max_instances: int
    utilization_pct: float
    action: InstanceAction
    reason: str = ""
    variant_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class ArbitrageAlert:
    """Alert raised when suspicious arbitrage patterns are detected."""
    alert_id: str
    company_id: str
    level: ArbitrageAlertLevel
    alert_type: str
    description: str
    details: Dict = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    resolved: bool = False


@dataclass
class AntiArbitrageConfig:
    """Configuration for the anti-arbitrage service.

    capacity_weights map variant types to a normalised weight that
    represents their relative capacity.  The sum of weights across
    all of a tenant's instances must not exceed max_weighted_capacity
    (default 7.5 = 1 parwa_high).
    """
    max_instances_per_variant: int = 10
    max_weighted_capacity: float = 7.5
    capacity_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "mini_parwa": 1.0,
            "parwa": 2.5,
            "parwa_high": 7.5,
        },
    )
    ticket_limits: Dict[str, int] = field(
        default_factory=lambda: {
            "mini_parwa": 2000,
            "parwa": 5000,
            "parwa_high": 15000,
        },
    )
    alert_thresholds: Dict[str, int] = field(
        default_factory=lambda: {
            "rapid_instance_creation": 3,
            "capacity_threshold_pct": 80,
            "critical_threshold_pct": 95,
        },
    )


# ══════════════════════════════════════════════════════════════════
# CUSTOM ERROR
# ══════════════════════════════════════════════════════════════════

class AntiArbitrageError(ParwaBaseError):
    """Raised when an anti-arbitrage policy is violated."""
    pass


# ══════════════════════════════════════════════════════════════════
# LUA SCRIPTS  (W9-GAP-014 — atomic Redis check-and-set)
# ══════════════════════════════════════════════════════════════════

# Atomic capacity check via Redis Lua script.
# KEYS[1] = capacity counter key   (parwa:aa:cap:{company_id})
# KEYS[2] = instance count key     (parwa:aa:cnt:{company_id})
# ARGV[1] = additional weight for the new instance
# ARGV[2] = max weighted capacity
# ARGV[3] = rapid-creation window key (parwa:aa:rapid:{company_id})
# ARGV[4] = rapid-creation threshold (e.g. 3)
# ARGV[5] = rapid-creation window TTL in seconds (e.g. 600)
#
# Returns: [status_code, current_capacity, instance_count, rapid_count]
#   status_code:  0 = allowed, 1 = blocked (capacity), 2 = blocked (rapid)
ATOMIC_CAPACITY_CHECK_LUA = """
local cap_key   = KEYS[1]
local cnt_key   = KEYS[2]
local add_wt    = tonumber(ARGV[1])
local max_cap   = tonumber(ARGV[2])
local rapid_key = ARGV[3]
local rapid_thr = tonumber(ARGV[4])
local rapid_ttl = tonumber(ARGV[5])

local cur_cap = tonumber(redis.call('GET', cap_key) or '0')
local cur_cnt = tonumber(redis.call('GET', cnt_key) or '0')

local rapid = tonumber(redis.call('GET', rapid_key) or '0')

-- Check rapid-creation rate first
if rapid + 1 > rapid_thr then
    redis.call('INCR', rapid_key)
    return {2, cur_cap, cur_cnt, rapid + 1}
end

-- Check weighted capacity
local new_cap = cur_cap + add_wt
if new_cap > max_cap then
    return {1, cur_cap, cur_cnt, rapid}
end

-- All checks passed — atomically update counters
redis.call('SET', cap_key, new_cap)
redis.call('INCR', cnt_key)
redis.call('INCR', rapid_key)
redis.call('EXPIRE', rapid_key, rapid_ttl)
return {0, new_cap, cur_cnt + 1, rapid + 1}
"""

ATOMIC_REMOVE_LUA = """
local cap_key = KEYS[1]
local cnt_key = KEYS[2]
local wt      = tonumber(ARGV[1])

local cur_cap = tonumber(redis.call('GET', cap_key) or '0')
local cur_cnt = tonumber(redis.call('GET', cnt_key) or '0')

local new_cap = math.max(0, cur_cap - wt)
local new_cnt = math.max(0, cur_cnt - 1)

redis.call('SET', cap_key, new_cap)
redis.call('SET', cnt_key, new_cnt)
return {new_cap, new_cnt}
"""


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_VARIANT_TYPES = {"mini_parwa", "parwa", "parwa_high"}

_RAPID_CREATION_WINDOW_SECONDS = 600  # 10 minutes


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════

def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required."""
    if not company_id or not str(company_id).strip():
        raise AntiArbitrageError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate variant_type is a known PARWA variant."""
    if variant_type not in VALID_VARIANT_TYPES:
        raise AntiArbitrageError(
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

class AntiArbitrageService:
    """
    Anti-Arbitrage Service (F-159).

    Detects and prevents tenants from gaming capacity by spawning
    many cheap mini_parwa instances instead of purchasing a single
    parwa_high instance.

    All public methods accept ``company_id`` as their first argument
    (BC-001) and are wrapped in try/except for graceful degradation
    (BC-008).
    """

    def __init__(
        self,
        config: Optional[AntiArbitrageConfig] = None,
        redis_client=None,
    ) -> None:
        self.config = config or AntiArbitrageConfig()
        self._redis = redis_client

        # Compile Lua scripts when a Redis client is available
        self._lua_capacity_check = None
        self._lua_remove = None
        if self._redis is not None:
            try:
                self._lua_capacity_check = self._redis.register_script(
                    ATOMIC_CAPACITY_CHECK_LUA,
                )
                self._lua_remove = self._redis.register_script(
                    ATOMIC_REMOVE_LUA,
                )
            except Exception as exc:
                logger.warning(
                    "lua_script_registration_failed",
                    error=str(exc),
                )

        # In-memory state (fallback when Redis is unavailable)
        self._instances: Dict[str, List[VariantInstance]] = {}
        self._alerts: List[ArbitrageAlert] = []
        self._rapid_creation_counts: Dict[str, List[datetime]] = {}
        self._lock = threading.Lock()

    # ── Redis key helpers ───────────────────────────────────────

    def _cap_key(self, company_id: str) -> str:
        return f"parwa:aa:cap:{company_id}"

    def _cnt_key(self, company_id: str) -> str:
        return f"parwa:aa:cnt:{company_id}"

    def _rapid_key(self, company_id: str) -> str:
        return f"parwa:aa:rapid:{company_id}"

    # ── In-memory fallback helpers ──────────────────────────────

    def _get_instances(self, company_id: str) -> List[VariantInstance]:
        return self._instances.get(company_id, [])

    def _set_instances(
        self, company_id: str, insts: List[VariantInstance],
    ) -> None:
        self._instances[company_id] = insts

    # ── Weighted Capacity (W9-GAP-025) ─────────────────────────

    def calculate_weighted_capacity(self, company_id: str) -> float:
        """Sum capacity_weight for all registered instances.

        W9-GAP-025: Uses weighted capacity across variant types,
        not raw instance count, to accurately represent resource
        consumption.
        """
        try:
            _validate_company_id(company_id)

            # Prefer Redis counter when available
            if self._redis is not None:
                try:
                    val = self._redis.get(self._cap_key(company_id))
                    if val is not None:
                        return float(val)
                except Exception as exc:
                    logger.warning(
                        "redis_capacity_read_failed_falling_back",
                        company_id=company_id,
                        error=str(exc),
                    )

            # In-memory fallback
            instances = self._get_instances(company_id)
            total = sum(inst.capacity_weight for inst in instances)

            logger.debug(
                "weighted_capacity_calculated",
                company_id=company_id,
                weighted_capacity=total,
                instance_count=len(instances),
            )
            return total

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "calculate_weighted_capacity_error",
                company_id=company_id,
                error=str(exc),
            )
            return 0.0

    # ── Capacity Check ──────────────────────────────────────────

    def check_capacity(self, company_id: str) -> CapacityCheck:
        """Check current weighted capacity utilisation for a tenant.

        Returns a CapacityCheck with action indicating whether
        the tenant is within limits or approaching/exceeding them.
        """
        try:
            _validate_company_id(company_id)

            current_cap = self.calculate_weighted_capacity(company_id)
            max_cap = self.config.max_weighted_capacity
            instances = self._get_instances(company_id)
            instance_count = len(instances)
            max_instances = self.config.max_instances_per_variant

            utilisation = (
                (current_cap / max_cap * 100.0) if max_cap > 0 else 0.0
            )

            threshold_pct = self.config.alert_thresholds[
                "capacity_threshold_pct"
            ]
            critical_pct = self.config.alert_thresholds[
                "critical_threshold_pct"
            ]

            if utilisation >= critical_pct:
                action = InstanceAction.BLOCKED
                reason = (
                    f"Weighted capacity at {utilisation:.1f}% "
                    f"(>= {critical_pct}% critical threshold)"
                )
            elif utilisation >= threshold_pct:
                action = InstanceAction.FLAGGED
                reason = (
                    f"Weighted capacity at {utilisation:.1f}% "
                    f"(>= {threshold_pct}% alert threshold)"
                )
            else:
                action = InstanceAction.ALLOWED
                reason = "Within acceptable capacity limits"

            variant_breakdown: Dict[str, int] = {}
            for inst in instances:
                variant_breakdown[inst.variant_type] = (
                    variant_breakdown.get(inst.variant_type, 0) + 1
                )

            logger.info(
                "capacity_checked",
                company_id=company_id,
                weighted_capacity=current_cap,
                utilisation_pct=utilisation,
                action=action.value,
            )

            return CapacityCheck(
                company_id=company_id,
                current_weighted_capacity=current_cap,
                max_weighted_capacity=max_cap,
                instance_count=instance_count,
                max_instances=max_instances,
                utilization_pct=utilisation,
                action=action,
                reason=reason,
                variant_breakdown=variant_breakdown,
            )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "check_capacity_error",
                company_id=company_id,
                error=str(exc),
            )
            return CapacityCheck(
                company_id=company_id,
                current_weighted_capacity=0.0,
                max_weighted_capacity=self.config.max_weighted_capacity,
                instance_count=0,
                max_instances=self.config.max_instances_per_variant,
                utilization_pct=0.0,
                action=InstanceAction.ALLOWED,
                reason=f"Capacity check error (graceful degradation): {exc}",
            )

    # ── Pre-check before creation (W9-GAP-014) ─────────────────

    def check_instance_creation_allowed(
        self,
        company_id: str,
        variant_type: str,
    ) -> CapacityCheck:
        """Pre-check if creating a new instance is allowed.

        W9-GAP-014: Uses atomic Redis INCR + Lua script so that
        concurrent requests cannot race past capacity limits.
        Falls back to in-memory locking when Redis is unavailable.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            weight = self.config.capacity_weights.get(variant_type, 1.0)
            instances = self._get_instances(company_id)
            variant_count = sum(
                1 for i in instances if i.variant_type == variant_type
            )

            # Per-variant limit check
            if variant_count >= self.config.max_instances_per_variant:
                return CapacityCheck(
                    company_id=company_id,
                    current_weighted_capacity=self.calculate_weighted_capacity(company_id),
                    max_weighted_capacity=self.config.max_weighted_capacity,
                    instance_count=len(instances),
                    max_instances=self.config.max_instances_per_variant,
                    utilization_pct=0.0,
                    action=InstanceAction.BLOCKED,
                    reason=(
                        f"Max {self.config.max_instances_per_variant} "
                        f"instances reached for variant '{variant_type}'"
                    ),
                )

            # ── Redis atomic path (W9-GAP-014) ──
            if self._lua_capacity_check is not None and self._redis is not None:
                try:
                    result = self._lua_capacity_check(
                        keys=[
                            self._cap_key(company_id),
                            self._cnt_key(company_id),
                        ],
                        args=[
                            weight,
                            self.config.max_weighted_capacity,
                            self._rapid_key(company_id),
                            self.config.alert_thresholds["rapid_instance_creation"],
                            _RAPID_CREATION_WINDOW_SECONDS,
                        ],
                    )

                    status_code = int(result[0])
                    new_cap = float(result[1])
                    new_cnt = int(result[2])
                    rapid_cnt = int(result[3])

                    if status_code == 2:
                        # Rapid-creation rate exceeded
                        self._create_alert(
                            company_id=company_id,
                            level=ArbitrageAlertLevel.HIGH,
                            alert_type="rapid_instance_creation",
                            description=(
                                f"Rapid instance creation detected: "
                                f"{rapid_cnt} instances in "
                                f"{_RAPID_CREATION_WINDOW_SECONDS // 60} min"
                            ),
                            details={
                                "rapid_count": rapid_cnt,
                                "variant_type": variant_type,
                            },
                        )
                        return CapacityCheck(
                            company_id=company_id,
                            current_weighted_capacity=new_cap,
                            max_weighted_capacity=self.config.max_weighted_capacity,
                            instance_count=new_cnt,
                            max_instances=self.config.max_instances_per_variant,
                            utilization_pct=(
                                new_cap / self.config.max_weighted_capacity * 100
                                if self.config.max_weighted_capacity > 0
                                else 0.0
                            ),
                            action=InstanceAction.BLOCKED,
                            reason=(
                                f"Rapid instance creation rate exceeded: "
                                f"{rapid_cnt} in last "
                                f"{_RAPID_CREATION_WINDOW_SECONDS // 60} min"
                            ),
                        )

                    if status_code == 1:
                        # Capacity exceeded — Lua did NOT increment
                        return CapacityCheck(
                            company_id=company_id,
                            current_weighted_capacity=new_cap,
                            max_weighted_capacity=self.config.max_weighted_capacity,
                            instance_count=new_cnt,
                            max_instances=self.config.max_instances_per_variant,
                            utilization_pct=(
                                new_cap / self.config.max_weighted_capacity * 100
                                if self.config.max_weighted_capacity > 0
                                else 0.0
                            ),
                            action=InstanceAction.BLOCKED,
                            reason=(
                                f"Adding {variant_type} (weight {weight}) "
                                f"would exceed max weighted capacity "
                                f"({self.config.max_weighted_capacity})"
                            ),
                        )

                    # status_code == 0 — Lua already incremented counters
                    utilisation = (
                        new_cap / self.config.max_weighted_capacity * 100
                        if self.config.max_weighted_capacity > 0
                        else 0.0
                    )
                    action = InstanceAction.ALLOWED
                    reason = "Instance creation allowed"

                    threshold_pct = self.config.alert_thresholds["capacity_threshold_pct"]
                    if utilisation >= threshold_pct:
                        action = InstanceAction.FLAGGED
                        reason = (
                            f"Allowed but flagged — capacity at "
                            f"{utilisation:.1f}% (>= {threshold_pct}% threshold)"
                        )
                        self._create_alert(
                            company_id=company_id,
                            level=ArbitrageAlertLevel.MEDIUM,
                            alert_type="capacity_approaching_limit",
                            description=(
                                f"Weighted capacity at {utilisation:.1f}% "
                                f"after adding {variant_type} instance"
                            ),
                            details={
                                "weighted_capacity": new_cap,
                                "utilisation_pct": round(utilisation, 2),
                                "variant_type": variant_type,
                            },
                        )

                    return CapacityCheck(
                        company_id=company_id,
                        current_weighted_capacity=new_cap,
                        max_weighted_capacity=self.config.max_weighted_capacity,
                        instance_count=new_cnt,
                        max_instances=self.config.max_instances_per_variant,
                        utilization_pct=utilisation,
                        action=action,
                        reason=reason,
                    )

                except Exception as exc:
                    logger.warning(
                        "redis_atomic_check_failed_falling_back",
                        company_id=company_id,
                        error=str(exc),
                    )

            # ── In-memory fallback (thread-safe) ──
            with self._lock:
                current_cap = sum(
                    i.capacity_weight for i in instances
                )
                new_capacity = current_cap + weight

                rapid_count = self._get_rapid_count(company_id)

                if rapid_count >= self.config.alert_thresholds["rapid_instance_creation"]:
                    return CapacityCheck(
                        company_id=company_id,
                        current_weighted_capacity=current_cap,
                        max_weighted_capacity=self.config.max_weighted_capacity,
                        instance_count=len(instances),
                        max_instances=self.config.max_instances_per_variant,
                        utilization_pct=(
                            current_cap / self.config.max_weighted_capacity * 100
                            if self.config.max_weighted_capacity > 0
                            else 0.0
                        ),
                        action=InstanceAction.BLOCKED,
                        reason=(
                            f"Rapid instance creation rate exceeded "
                            f"(in-memory fallback)"
                        ),
                    )

                if new_capacity > self.config.max_weighted_capacity:
                    return CapacityCheck(
                        company_id=company_id,
                        current_weighted_capacity=current_cap,
                        max_weighted_capacity=self.config.max_weighted_capacity,
                        instance_count=len(instances),
                        max_instances=self.config.max_instances_per_variant,
                        utilization_pct=(
                            current_cap / self.config.max_weighted_capacity * 100
                            if self.config.max_weighted_capacity > 0
                            else 0.0
                        ),
                        action=InstanceAction.BLOCKED,
                        reason=(
                            f"Adding {variant_type} (weight {weight}) "
                            f"would exceed max weighted capacity "
                            f"({self.config.max_weighted_capacity})"
                        ),
                    )

                # Allowed — record rapid-creation timestamp
                self._record_creation(company_id)

                utilisation = (
                    new_capacity / self.config.max_weighted_capacity * 100
                    if self.config.max_weighted_capacity > 0
                    else 0.0
                )
                action = InstanceAction.ALLOWED
                reason = "Instance creation allowed (in-memory)"

                threshold_pct = self.config.alert_thresholds["capacity_threshold_pct"]
                if utilisation >= threshold_pct:
                    action = InstanceAction.FLAGGED
                    reason = f"Allowed but flagged — capacity at {utilisation:.1f}%"

                return CapacityCheck(
                    company_id=company_id,
                    current_weighted_capacity=new_capacity,
                    max_weighted_capacity=self.config.max_weighted_capacity,
                    instance_count=len(instances) + 1,
                    max_instances=self.config.max_instances_per_variant,
                    utilization_pct=utilisation,
                    action=action,
                    reason=reason,
                )

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "check_instance_creation_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            return CapacityCheck(
                company_id=company_id,
                current_weighted_capacity=0.0,
                max_weighted_capacity=self.config.max_weighted_capacity,
                instance_count=0,
                max_instances=self.config.max_instances_per_variant,
                utilization_pct=0.0,
                action=InstanceAction.ALLOWED,
                reason=f"Pre-check error (graceful degradation): {exc}",
            )

    # ── Register Instance ───────────────────────────────────────

    def register_instance(
        self,
        company_id: str,
        instance_id: str,
        variant_type: str,
    ) -> CapacityCheck:
        """Register a new instance with atomic capacity check.

        This is the primary entry point for instance creation.
        Performs an atomic capacity check (W9-GAP-014) and, if
        allowed, registers the instance in the in-memory store.

        The Redis Lua script atomically increments counters when
        allowed, so callers must NOT call check + register as
        separate steps — use this single method instead.
        """
        try:
            _validate_company_id(company_id)
            _validate_variant_type(variant_type)

            if not instance_id or not str(instance_id).strip():
                raise AntiArbitrageError(
                    error_code="INVALID_INSTANCE_ID",
                    message="instance_id is required and cannot be empty",
                    status_code=400,
                )

            # Run the atomic pre-check (increments Redis counters if allowed)
            check = self.check_instance_creation_allowed(
                company_id, variant_type,
            )

            if check.action == InstanceAction.BLOCKED:
                logger.warning(
                    "instance_creation_blocked",
                    company_id=company_id,
                    instance_id=instance_id,
                    variant_type=variant_type,
                    reason=check.reason,
                )
                return check

            # Register in in-memory store (authoritative for lookups)
            weight = self.config.capacity_weights.get(variant_type, 1.0)
            ticket_limit = self.config.ticket_limits.get(variant_type, 2000)

            instance = VariantInstance(
                instance_id=instance_id,
                variant_type=variant_type,
                company_id=company_id,
                ticket_limit=ticket_limit,
                capacity_weight=weight,
            )

            with self._lock:
                insts = self._get_instances(company_id)
                insts.append(instance)
                self._set_instances(company_id, insts)

            logger.info(
                "instance_registered",
                company_id=company_id,
                instance_id=instance_id,
                variant_type=variant_type,
                weight=weight,
                total_instances=len(self._get_instances(company_id)),
                action=check.action.value,
            )

            return check

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "register_instance_error",
                company_id=company_id,
                instance_id=instance_id,
                variant_type=variant_type,
                error=str(exc),
            )
            return CapacityCheck(
                company_id=company_id,
                current_weighted_capacity=0.0,
                max_weighted_capacity=self.config.max_weighted_capacity,
                instance_count=0,
                max_instances=self.config.max_instances_per_variant,
                utilization_pct=0.0,
                action=InstanceAction.ALLOWED,
                reason=f"Registration error (graceful degradation): {exc}",
            )

    # ── Remove Instance ─────────────────────────────────────────

    def remove_instance(
        self,
        company_id: str,
        instance_id: str,
    ) -> bool:
        """Remove a registered instance and decrement counters.

        Uses atomic Redis Lua script (W9-GAP-014) when available,
        otherwise falls back to in-memory with thread lock.
        """
        try:
            _validate_company_id(company_id)

            with self._lock:
                insts = self._get_instances(company_id)
                target = None
                for inst in insts:
                    if inst.instance_id == instance_id:
                        target = inst
                        break

                if target is None:
                    logger.warning(
                        "instance_not_found_for_removal",
                        company_id=company_id,
                        instance_id=instance_id,
                    )
                    return False

                weight = target.capacity_weight
                insts.remove(target)
                self._set_instances(company_id, insts)

            # Decrement Redis counters atomically
            if self._lua_remove is not None and self._redis is not None:
                try:
                    self._lua_remove(
                        keys=[
                            self._cap_key(company_id),
                            self._cnt_key(company_id),
                        ],
                        args=[weight],
                    )
                except Exception as exc:
                    logger.warning(
                        "redis_atomic_remove_failed",
                        company_id=company_id,
                        instance_id=instance_id,
                        error=str(exc),
                    )

            logger.info(
                "instance_removed",
                company_id=company_id,
                instance_id=instance_id,
                variant_type=target.variant_type,
                weight=weight,
            )
            return True

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "remove_instance_error",
                company_id=company_id,
                instance_id=instance_id,
                error=str(exc),
            )
            return False

    # ── Suspicious Pattern Detection ────────────────────────────

    def detect_suspicious_patterns(
        self,
        company_id: str,
    ) -> List[ArbitrageAlert]:
        """Run all arbitrage-detection heuristics for a tenant.

        Checks for:
        - Rapid instance creation bursts
        - Capacity gaming (many cheap instances approaching high capacity)
        - Single-variant hoarding
        """
        try:
            _validate_company_id(company_id)

            alerts: List[ArbitrageAlert] = []
            instances = self._get_instances(company_id)

            if not instances:
                return alerts

            # ── 1. Rapid instance creation ──
            rapid_count = self._get_rapid_count(company_id)
            rapid_threshold = self.config.alert_thresholds[
                "rapid_instance_creation"
            ]
            if rapid_count >= rapid_threshold:
                alerts.append(ArbitrageAlert(
                    alert_id=str(uuid.uuid4()),
                    company_id=company_id,
                    level=ArbitrageAlertLevel.HIGH,
                    alert_type="rapid_instance_creation",
                    description=(
                        f"{rapid_count} instances created within "
                        f"{_RAPID_CREATION_WINDOW_SECONDS // 60} minutes"
                    ),
                    details={
                        "rapid_count": rapid_count,
                        "threshold": rapid_threshold,
                        "window_seconds": _RAPID_CREATION_WINDOW_SECONDS,
                    },
                ))

            # ── 2. Weighted capacity gaming ──
            current_cap = self.calculate_weighted_capacity(company_id)
            max_cap = self.config.max_weighted_capacity
            utilisation = (
                (current_cap / max_cap * 100.0) if max_cap > 0 else 0.0
            )
            threshold_pct = self.config.alert_thresholds[
                "capacity_threshold_pct"
            ]
            if utilisation >= threshold_pct:
                level = ArbitrageAlertLevel.CRITICAL if utilisation >= 95 else ArbitrageAlertLevel.MEDIUM
                alerts.append(ArbitrageAlert(
                    alert_id=str(uuid.uuid4()),
                    company_id=company_id,
                    level=level,
                    alert_type="capacity_gaming",
                    description=(
                        f"Weighted capacity utilisation at "
                        f"{utilisation:.1f}% (threshold {threshold_pct}%)"
                    ),
                    details={
                        "weighted_capacity": current_cap,
                        "max_capacity": max_cap,
                        "utilisation_pct": round(utilisation, 2),
                    },
                ))

            # ── 3. Single-variant hoarding ──
            variant_counts: Dict[str, int] = {}
            for inst in instances:
                variant_counts[inst.variant_type] = (
                    variant_counts.get(inst.variant_type, 0) + 1
                )
            for vtype, count in variant_counts.items():
                if count >= 5 and vtype == "mini_parwa":
                    alerts.append(ArbitrageAlert(
                        alert_id=str(uuid.uuid4()),
                        company_id=company_id,
                        level=ArbitrageAlertLevel.HIGH,
                        alert_type="single_variant_hoarding",
                        description=(
                            f"{count} mini_parwa instances detected — "
                            f"potential capacity gaming"
                        ),
                        details={
                            "variant_type": vtype,
                            "count": count,
                            "combined_weight": count * self.config.capacity_weights.get(vtype, 1.0),
                        },
                    ))

            # Store alerts
            for alert in alerts:
                self._alerts.append(alert)

            logger.info(
                "suspicious_patterns_checked",
                company_id=company_id,
                alerts_found=len(alerts),
                instance_count=len(instances),
                weighted_capacity=current_cap,
            )

            return alerts

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "detect_patterns_error",
                company_id=company_id,
                error=str(exc),
            )
            return []

    # ── Instance Summary ────────────────────────────────────────

    def get_instance_summary(self, company_id: str) -> Dict:
        """Get all instances with capacity breakdown for a tenant."""
        try:
            _validate_company_id(company_id)

            instances = self._get_instances(company_id)
            current_cap = self.calculate_weighted_capacity(company_id)
            max_cap = self.config.max_weighted_capacity

            variant_breakdown: Dict[str, Dict] = {}
            for inst in instances:
                vt = inst.variant_type
                if vt not in variant_breakdown:
                    variant_breakdown[vt] = {
                        "count": 0,
                        "total_weight": 0.0,
                        "total_tickets": 0,
                        "instances": [],
                    }
                variant_breakdown[vt]["count"] += 1
                variant_breakdown[vt]["total_weight"] += inst.capacity_weight
                variant_breakdown[vt]["total_tickets"] += inst.ticket_limit
                variant_breakdown[vt]["instances"].append({
                    "instance_id": inst.instance_id,
                    "created_at": inst.created_at.isoformat(),
                })

            utilisation = (
                (current_cap / max_cap * 100.0) if max_cap > 0 else 0.0
            )

            return {
                "company_id": company_id,
                "total_instances": len(instances),
                "weighted_capacity": current_cap,
                "max_weighted_capacity": max_cap,
                "utilisation_pct": round(utilisation, 2),
                "remaining_capacity": round(max(0.0, max_cap - current_cap), 2),
                "variant_breakdown": variant_breakdown,
            }

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_instance_summary_error",
                company_id=company_id,
                error=str(exc),
            )
            return {
                "company_id": company_id,
                "total_instances": 0,
                "weighted_capacity": 0.0,
                "max_weighted_capacity": self.config.max_weighted_capacity,
                "utilisation_pct": 0.0,
                "remaining_capacity": self.config.max_weighted_capacity,
                "variant_breakdown": {},
                "error": str(exc),
            }

    # ── Alerts ──────────────────────────────────────────────────

    def get_alerts(
        self,
        company_id: str,
        unresolved_only: bool = False,
    ) -> List[ArbitrageAlert]:
        """Get alerts for a company, optionally filtered to unresolved."""
        try:
            _validate_company_id(company_id)

            alerts = [
                a for a in self._alerts
                if a.company_id == company_id
            ]
            if unresolved_only:
                alerts = [a for a in alerts if not a.resolved]

            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_alerts_error",
                company_id=company_id,
                error=str(exc),
            )
            return []

    def resolve_alert(
        self,
        company_id: str,
        alert_id: str,
    ) -> bool:
        """Mark an alert as resolved."""
        try:
            _validate_company_id(company_id)

            for alert in self._alerts:
                if (
                    alert.company_id == company_id
                    and alert.alert_id == alert_id
                ):
                    alert.resolved = True
                    logger.info(
                        "alert_resolved",
                        company_id=company_id,
                        alert_id=alert_id,
                    )
                    return True

            logger.warning(
                "alert_not_found_for_resolution",
                company_id=company_id,
                alert_id=alert_id,
            )
            return False

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "resolve_alert_error",
                company_id=company_id,
                alert_id=alert_id,
                error=str(exc),
            )
            return False

    # ── Config ──────────────────────────────────────────────────

    def get_variant_config(self) -> Dict:
        """Return current variant weights, ticket limits, and thresholds."""
        try:
            return {
                "max_instances_per_variant": self.config.max_instances_per_variant,
                "max_weighted_capacity": self.config.max_weighted_capacity,
                "capacity_weights": dict(self.config.capacity_weights),
                "ticket_limits": dict(self.config.ticket_limits),
                "alert_thresholds": dict(self.config.alert_thresholds),
                "valid_variant_types": sorted(VALID_VARIANT_TYPES),
            }
        except Exception as exc:
            logger.error("get_variant_config_error", error=str(exc))
            return {}

    # ── Reset (testing) ─────────────────────────────────────────

    def reset(self, company_id: str = "") -> None:
        """Reset state for a company or all companies (for testing)."""
        try:
            with self._lock:
                if company_id:
                    self._instances.pop(company_id, None)
                    self._rapid_creation_counts.pop(company_id, None)
                    self._alerts = [
                        a for a in self._alerts
                        if a.company_id != company_id
                    ]
                    if self._redis is not None:
                        try:
                            self._redis.delete(
                                self._cap_key(company_id),
                                self._cnt_key(company_id),
                                self._rapid_key(company_id),
                            )
                        except Exception as exc:
                            logger.warning(
                                "redis_reset_failed",
                                company_id=company_id,
                                error=str(exc),
                            )
                else:
                    self._instances.clear()
                    self._rapid_creation_counts.clear()
                    self._alerts.clear()

            logger.info(
                "anti_arbitrage_reset",
                company_id=company_id or "ALL",
            )

        except Exception as exc:
            logger.error("reset_error", error=str(exc))

    # ══════════════════════════════════════════════════════════════
    # PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════

    def _get_rapid_count(self, company_id: str) -> int:
        """Count instance creations within the rapid-creation window."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=_RAPID_CREATION_WINDOW_SECONDS)

        with self._lock:
            timestamps = self._rapid_creation_counts.get(company_id, [])
            timestamps = [ts for ts in timestamps if ts > cutoff]
            self._rapid_creation_counts[company_id] = timestamps
            return len(timestamps)

    def _record_creation(self, company_id: str) -> None:
        """Record an instance creation timestamp for rate tracking."""
        with self._lock:
            if company_id not in self._rapid_creation_counts:
                self._rapid_creation_counts[company_id] = []
            self._rapid_creation_counts[company_id].append(
                datetime.now(timezone.utc),
            )

    def _create_alert(
        self,
        company_id: str,
        level: ArbitrageAlertLevel,
        alert_type: str,
        description: str,
        details: Optional[Dict] = None,
    ) -> ArbitrageAlert:
        """Create and store an arbitrage alert."""
        alert = ArbitrageAlert(
            alert_id=str(uuid.uuid4()),
            company_id=company_id,
            level=level,
            alert_type=alert_type,
            description=description,
            details=details or {},
        )
        self._alerts.append(alert)

        logger.warning(
            "arbitrage_alert_created",
            company_id=company_id,
            alert_id=alert.alert_id,
            level=level.value,
            alert_type=alert_type,
            description=description,
        )
        return alert
