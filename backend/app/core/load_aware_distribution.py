"""
SG-07: Load-Aware Distribution (Week 10 Day 4)

Distributes workload across multiple instances of the same variant
type. Implements weighted round-robin, sticky sessions, failover,
and capacity-aware routing for same-type variant overlap scenarios.

Building Codes: BC-001, BC-007, BC-008, BC-012

Responsibilities:
    - Load measurement per instance (active tickets, queued tickets, token usage)
    - Round-robin with weight adjustment across instances
    - Sticky sessions (route same customer/conversation to same instance)
    - Failover between instances when unhealthy or overloaded
    - Capacity-aware routing that respects instance limits
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

DEFAULT_STICKY_TTL_SECONDS: float = 3600.0  # 1 hour
DEFAULT_MAX_CONCURRENT_TICKETS: int = 50
DEFAULT_TOKEN_BUDGET_SHARE: int = 1_000_000  # 1M tokens
DEFAULT_INSTANCE_WEIGHT: float = 1.0
OVERLOAD_THRESHOLD_PCT: float = 0.90  # 90 % utilisation triggers OVERLOADED
# How much queued count affects effective load
QUEUE_PRESSURE_WEIGHT_FACTOR: float = 0.5
# Minimum weight delta to trigger rebalance
REBALANCE_MIN_DIFFERENCE: float = 0.1


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class InstanceStatus(str, Enum):
    """Health status of a variant instance.

    ACTIVE     — Normal operation, accepting tickets.
    WARMING    — Starting up, can accept limited traffic.
    OVERLOADED — Exceeded capacity threshold, deprioritised but not disabled.
    UNHEALTHY  — Failed health check, excluded from routing.
    INACTIVE   — Explicitly disabled or decommissioned.
    """

    ACTIVE = "active"
    WARMING = "warming"
    OVERLOADED = "overloaded"
    UNHEALTHY = "unhealthy"
    INACTIVE = "inactive"


class RoutingMethod(str, Enum):
    """How a ticket was routed to an instance."""

    STICKY = "sticky"
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FAILOVER = "failover"
    NO_INSTANCE_AVAILABLE = "no_instance_available"


class FailoverReason(str, Enum):
    """Why a failover was triggered."""

    INSTANCE_UNHEALTHY = "instance_unhealthy"
    INSTANCE_OVERLOADED = "instance_overloaded"
    INSTANCE_DEREGISTERED = "instance_deregistered"
    MANUAL = "manual"
    SESSION_INVALIDATED = "session_invalidated"


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class InstanceInfo:
    """Runtime information about a single variant instance.

    Attributes:
        instance_id:        Unique identifier for this instance.
        company_id:         Tenant this instance belongs to (BC-001).
        variant_type:       Which variant this instance runs (e.g. ``parwa``).
        status:             Current health / lifecycle status.
        channel_assignment: Comma-separated channels this instance handles.
        capacity_config:    Dict with ``max_concurrent_tickets`` and
                            ``token_budget_share``.
        current_load:       Number of tickets actively being processed.
        queued_count:       Number of tickets waiting in queue.
        tokens_used_today:  Token consumption for the current UTC day.
        weight:             Routing weight (higher = more traffic).
        created_at:         UTC ISO-8601 timestamp of registration (BC-012).
        metadata:           Arbitrary key-value extensions.
    """

    instance_id: str
    company_id: str
    variant_type: str
    status: InstanceStatus = InstanceStatus.ACTIVE
    channel_assignment: str = "email,chat,web_widget"
    capacity_config: Dict[str, Any] = field(default_factory=lambda: {
        "max_concurrent_tickets": DEFAULT_MAX_CONCURRENT_TICKETS,
        "token_budget_share": DEFAULT_TOKEN_BUDGET_SHARE,
    })
    current_load: int = 0
    queued_count: int = 0
    tokens_used_today: int = 0
    weight: float = DEFAULT_INSTANCE_WEIGHT
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Derived helpers ──────────────────────────────────────────

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent tickets this instance can handle."""
        return self.capacity_config.get(
            "max_concurrent_tickets", DEFAULT_MAX_CONCURRENT_TICKETS,
        )

    @property
    def token_budget(self) -> int:
        """Daily token budget share for this instance."""
        return self.capacity_config.get(
            "token_budget_share", DEFAULT_TOKEN_BUDGET_SHARE,
        )

    @property
    def utilization_pct(self) -> float:
        """Current load as a percentage of max capacity."""
        if self.max_concurrent <= 0:
            return 1.0
        return self.current_load / self.max_concurrent

    @property
    def effective_load(self) -> float:
        """Combined load score factoring in active tickets and queue.

        Queued tickets contribute at a discounted rate (they haven't
        started consuming resources yet).
        """
        return (
            float(self.current_load)
            + self.queued_count * QUEUE_PRESSURE_WEIGHT_FACTOR
        )

    @property
    def available_capacity(self) -> int:
        """Remaining slots before hitting max concurrent."""
        return max(0, self.max_concurrent - self.current_load)

    @property
    def is_routable(self) -> bool:
        """Whether this instance should receive new traffic."""
        return self.status in (
            InstanceStatus.ACTIVE,
            InstanceStatus.WARMING,
        )

    @property
    def is_overloaded(self) -> bool:
        """Whether the instance exceeds the overload threshold."""
        return self.utilization_pct >= OVERLOAD_THRESHOLD_PCT

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary for API responses."""
        return {
            "instance_id": self.instance_id,
            "company_id": self.company_id,
            "variant_type": self.variant_type,
            "status": self.status.value,
            "channel_assignment": self.channel_assignment,
            "capacity_config": self.capacity_config,
            "current_load": self.current_load,
            "queued_count": self.queued_count,
            "tokens_used_today": self.tokens_used_today,
            "weight": round(self.weight, 4),
            "utilization_pct": round(self.utilization_pct * 100, 2),
            "effective_load": round(self.effective_load, 2),
            "available_capacity": self.available_capacity,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class StickySession:
    """Maps a session key to a specific instance.

    Attributes:
        session_key:    Identifier (ticket_id or customer_id).
        instance_id:    The instance the session is pinned to.
        created_at:     Monotonic timestamp of creation.
        last_used:      Monotonic timestamp of last access.
        ttl_seconds:    Time-to-live; expired sessions are eligible for cleanup.
    """

    session_key: str
    instance_id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    ttl_seconds: float = DEFAULT_STICKY_TTL_SECONDS

    @property
    def is_expired(self) -> bool:
        """Check whether this session has exceeded its TTL."""
        return (time.time() - self.last_used) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Seconds since creation."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last_used to now, refreshing the session."""
        self.last_used = time.time()


@dataclass
class DistributionResult:
    """Outcome of a distribution (routing) decision.

    Attributes:
        instance_id:       Target instance that will handle the ticket.
        company_id:        Tenant identifier (BC-001).
        variant_type:      Variant type of the selected instance.
        routing_method:    Algorithm used to select the instance.
        load_at_routing:   Instance load at the moment of routing.
        capacity:          Instance max concurrent capacity.
        reason:            Human-readable explanation.
    """

    instance_id: str
    company_id: str
    variant_type: str
    routing_method: str
    load_at_routing: int
    capacity: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary for API responses."""
        return {
            "instance_id": self.instance_id,
            "company_id": self.company_id,
            "variant_type": self.variant_type,
            "routing_method": self.routing_method,
            "load_at_routing": self.load_at_routing,
            "capacity": self.capacity,
            "reason": self.reason,
        }


@dataclass
class FailoverEvent:
    """Record of a failover event for analytics.

    Attributes:
        ticket_id:        Ticket that was rerouted.
        company_id:       Tenant identifier.
        from_instance_id: Source instance that failed.
        to_instance_id:   Destination instance.
        reason:           Why the failover was needed.
        timestamp:        UTC ISO-8601 (BC-012).
    """

    ticket_id: str
    company_id: str
    from_instance_id: str
    to_instance_id: str
    reason: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "company_id": self.company_id,
            "from_instance_id": self.from_instance_id,
            "to_instance_id": self.to_instance_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class DistributionStats:
    """Aggregated routing statistics for a company.

    Tracks how many times each routing method was used, how many
    failovers occurred, and sticky session hit/miss rates.
    """

    sticky_hits: int = 0
    sticky_misses: int = 0
    sticky_expired: int = 0
    round_robin_routes: int = 0
    least_loaded_routes: int = 0
    failover_count: int = 0
    no_instance_available: int = 0
    total_distributions: int = 0
    sessions_cleared: int = 0

    @property
    def sticky_hit_rate(self) -> float:
        """Percentage of distributions served by sticky sessions."""
        total = self.sticky_hits + self.sticky_misses
        if total == 0:
            return 0.0
        return round((self.sticky_hits / total) * 100.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary for API responses."""
        return {
            "sticky_hits": self.sticky_hits,
            "sticky_misses": self.sticky_misses,
            "sticky_expired": self.sticky_expired,
            "sticky_hit_rate": self.sticky_hit_rate,
            "round_robin_routes": self.round_robin_routes,
            "least_loaded_routes": self.least_loaded_routes,
            "failover_count": self.failover_count,
            "no_instance_available": self.no_instance_available,
            "total_distributions": self.total_distributions,
            "sessions_cleared": self.sessions_cleared,
        }


# ══════════════════════════════════════════════════════════════════
# LOAD-AWARE DISTRIBUTOR
# ══════════════════════════════════════════════════════════════════


class LoadAwareDistributor:
    """Distributes workload across multiple instances of the same variant.

    Implements SG-07 requirements:
    1.  Load measurement per instance (active, queued, tokens).
    2.  Weighted round-robin with dynamic weight adjustment.
    3.  Sticky sessions for conversation continuity.
    4.  Automatic failover when instances go unhealthy.
    5.  Capacity-aware routing that respects instance limits.

    Thread-safety:
        All mutable state is protected by ``_lock`` (``threading.RLock``).

    BC-001: ``company_id`` is the first parameter on every public method.
    BC-008: Every public method is wrapped in ``try/except`` and never
            raises — failures are logged and safe defaults returned.
    BC-012: All timestamps are UTC ISO-8601 strings or ``time.time()``.

    Usage::

        dist = LoadAwareDistributor()
        dist.register_instance("co_1", "inst_1", "parwa", "email,chat")
        result = dist.distribute("co_1", "parwa", "tkt_42", "cust_7", "email")
        print(result.instance_id, result.routing_method)
    """

    def __init__(self) -> None:
        # Instance registry: {(company_id, instance_id): InstanceInfo}
        self._instances: Dict[Tuple[str, str], InstanceInfo] = {}
        # Sticky session store: {(company_id, session_key): StickySession}
        self._sticky_sessions: Dict[Tuple[str, str], StickySession] = {}
        # Reverse sticky mapping: {(company_id, instance_id): Set[session_key]}
        self._instance_sessions: Dict[Tuple[str, str], Set[str]] = {}
        # Round-robin counter: {(company_id, variant_type): int}
        self._rr_counter: Dict[Tuple[str, str], int] = {}
        # Failover event history: {company_id: List[FailoverEvent]}
        self._failover_history: Dict[str, List[FailoverEvent]] = {}
        # Distribution statistics: {company_id: DistributionStats}
        self._stats: Dict[str, DistributionStats] = {}
        # Per-company token reset tracking: {company_id: str (date string)}
        self._last_token_reset: Dict[str, str] = {}
        # Thread safety
        self._lock = threading.RLock()

        logger.info(
            "LoadAwareDistributor initialised — overload_threshold=%.0f%%, "
            "default_sticky_ttl=%.0fs",
            OVERLOAD_THRESHOLD_PCT * 100,
            DEFAULT_STICKY_TTL_SECONDS,
        )

    # ── Helper: UTC timestamp (BC-012) ──────────────────────────

    @staticmethod
    def _utc_now_iso() -> str:
        """Return the current UTC time as an ISO-8601 string (BC-012)."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _utc_today_str() -> str:
        """Return the current UTC date as a YYYY-MM-DD string for token tracking."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Helper: Stats access ─────────────────────────────────────

    def _get_stats(self, company_id: str) -> DistributionStats:
        """Get or create distribution stats for a company."""
        if company_id not in self._stats:
            self._stats[company_id] = DistributionStats()
        return self._stats[company_id]

    # ── Helper: Token daily reset ────────────────────────────────

    def _maybe_reset_tokens(self, company_id: str) -> None:
        """Reset token counters for all instances of a company if the UTC day changed.

        Must be called while holding ``_lock``.
        """
        today = self._utc_today_str()
        if self._last_token_reset.get(company_id) != today:
            self._last_token_reset[company_id] = today
            for (cid, iid), instance in self._instances.items():
                if cid == company_id and instance.tokens_used_today > 0:
                    instance.tokens_used_today = 0
            logger.info(
                "Daily token counters reset for company_id=%s (new UTC day: %s)",
                company_id,
                today,
            )

    # ── Helper: Eligible instances ───────────────────────────────

    def _get_eligible_instances(
        self,
        company_id: str,
        variant_type: str,
        preferred_channel: str = "",
    ) -> List[InstanceInfo]:
        """Return instances that are eligible for routing.

        Filters by:
        - company_id and variant_type
        - routable status (ACTIVE or WARMING)
        - channel match (if preferred_channel specified)

        Must be called while holding ``_lock``.
        """
        result: List[InstanceInfo] = []
        for (cid, _iid), instance in self._instances.items():
            if cid != company_id:
                continue
            if instance.variant_type != variant_type:
                continue
            if not instance.is_routable:
                continue
            if preferred_channel:
                channels = [
                    ch.strip() for ch in instance.channel_assignment.split(",")
                ]
                if preferred_channel.strip() not in channels:
                    continue
            result.append(instance)
        return result

    # ══════════════════════════════════════════════════════════════
    # INSTANCE REGISTRATION
    # ══════════════════════════════════════════════════════════════

    def register_instance(
        self,
        company_id: str,
        instance_id: str,
        variant_type: str,
        channel_assignment: str = "email,chat,web_widget",
        capacity_config: Optional[Dict[str, Any]] = None,
        weight: float = DEFAULT_INSTANCE_WEIGHT,
        status: InstanceStatus = InstanceStatus.ACTIVE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[InstanceInfo]:
        """Register a new variant instance for load-aware distribution.

        If an instance with the same ``(company_id, instance_id)`` already
        exists, it is replaced with the new configuration.

        Args:
            company_id:         Tenant identifier (BC-001).
            instance_id:        Unique identifier for the instance.
            variant_type:       Variant this instance handles (e.g. ``parwa``).
            channel_assignment: Comma-separated channels (e.g. ``email,chat``).
            capacity_config:    Dict with ``max_concurrent_tickets`` and
                                ``token_budget_share``.  Uses defaults if not
                                provided.
            weight:             Routing weight (default 1.0).
            status:             Initial instance status (default ACTIVE).
            metadata:           Arbitrary key-value extensions.

        Returns:
            The registered :class:`InstanceInfo`, or ``None`` on error (BC-008).
        """
        try:
            config = capacity_config or {
                "max_concurrent_tickets": DEFAULT_MAX_CONCURRENT_TICKETS,
                "token_budget_share": DEFAULT_TOKEN_BUDGET_SHARE,
            }

            if weight <= 0:
                logger.warning(
                    "register_instance: weight must be > 0, got %.4f for "
                    "instance_id=%s — using default %.1f",
                    weight, instance_id, DEFAULT_INSTANCE_WEIGHT,
                )
                weight = DEFAULT_INSTANCE_WEIGHT

            # Validate capacity_config
            max_concurrent = config.get(
                "max_concurrent_tickets", DEFAULT_MAX_CONCURRENT_TICKETS,
            )
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                logger.warning(
                    "register_instance: invalid max_concurrent_tickets=%s "
                    "for instance_id=%s — using default %d",
                    max_concurrent,
                    instance_id,
                    DEFAULT_MAX_CONCURRENT_TICKETS,
                )
                config["max_concurrent_tickets"] = DEFAULT_MAX_CONCURRENT_TICKETS

            instance = InstanceInfo(
                instance_id=instance_id,
                company_id=company_id,
                variant_type=variant_type,
                status=status,
                channel_assignment=channel_assignment,
                capacity_config=config,
                weight=weight,
                created_at=self._utc_now_iso(),
                metadata=metadata or {},
            )

            with self._lock:
                key = (company_id, instance_id)
                is_update = key in self._instances
                self._instances[key] = instance

                # Initialise reverse sticky mapping
                if key not in self._instance_sessions:
                    self._instance_sessions[key] = set()

            action = "updated" if is_update else "registered"
            logger.info(
                "Instance %s: company_id=%s, instance_id=%s, variant=%s, "
                "channels=%s, weight=%.2f, capacity=%d, status=%s",
                action,
                company_id,
                instance_id,
                variant_type,
                channel_assignment,
                weight,
                config.get(
                    "max_concurrent_tickets",
                    DEFAULT_MAX_CONCURRENT_TICKETS),
                status.value,
            )
            return instance
        except Exception:
            logger.exception(
                "register_instance failed for company_id=%s, instance_id=%s",
                company_id, instance_id,
            )
            return None

    def deregister_instance(
        self,
        company_id: str,
        instance_id: str,
    ) -> bool:
        """Remove an instance from the registry and clean up its state.

        Clears all sticky sessions pinned to this instance and redistributes
        any affected session keys so they can be re-assigned on next access.

        Args:
            company_id:  Tenant identifier (BC-001).
            instance_id: Instance to remove.

        Returns:
            ``True`` if the instance was found and removed, ``False`` otherwise.
        """
        try:
            with self._lock:
                key = (company_id, instance_id)
                instance = self._instances.pop(key, None)

                if instance is None:
                    logger.debug(
                        "deregister_instance: instance_id=%s not found for "
                        "company_id=%s — nothing to remove",
                        instance_id, company_id,
                    )
                    return False

                # Clean up sticky sessions pinned to this instance
                session_keys = self._instance_sessions.pop(key, set())
                for session_key in session_keys:
                    session_map_key = (company_id, session_key)
                    self._sticky_sessions.pop(session_map_key, None)

                # Clean up round-robin counter if this was the only instance
                variant_key = (company_id, instance.variant_type)
                remaining = [inst for (cid, _), inst in self._instances.items(
                ) if cid == company_id and inst.variant_type == instance.variant_type]
                if not remaining:
                    self._rr_counter.pop(variant_key, None)

                # Clear failover history referencing this instance
                if company_id in self._failover_history:
                    self._failover_history[company_id] = [
                        evt for evt in self._failover_history[company_id]
                        if evt.from_instance_id != instance_id
                    ]

            logger.info(
                "Instance deregistered: company_id=%s, instance_id=%s, "
                "variant=%s, sticky_sessions_cleared=%d",
                company_id,
                instance_id,
                instance.variant_type,
                len(session_keys),
            )
            return True
        except Exception:
            logger.exception(
                "deregister_instance failed for company_id=%s, instance_id=%s",
                company_id, instance_id,
            )
            return False

    # ══════════════════════════════════════════════════════════════
    # LOAD METRICS
    # ══════════════════════════════════════════════════════════════

    def update_instance_load(
        self,
        company_id: str,
        instance_id: str,
        active_tickets: int = 0,
        queued_tickets: int = 0,
        tokens_used: int = 0,
    ) -> bool:
        """Update live load metrics for an instance.

        Args:
            company_id:      Tenant identifier (BC-001).
            instance_id:     Instance to update.
            active_tickets:  Number of tickets currently being processed.
            queued_tickets:  Number of tickets waiting in the queue.
            tokens_used:     Cumulative tokens consumed today (if non-zero,
                             replaces the current value; if zero, leaves
                             the current value unchanged).

        Returns:
            ``True`` if the instance was found and updated, ``False`` otherwise.
        """
        try:
            with self._lock:
                self._maybe_reset_tokens(company_id)
                key = (company_id, instance_id)
                instance = self._instances.get(key)
                if instance is None:
                    logger.warning(
                        "update_instance_load: instance_id=%s not found for "
                        "company_id=%s",
                        instance_id, company_id,
                    )
                    return False

                instance.current_load = max(0, active_tickets)
                instance.queued_count = max(0, queued_tickets)
                if tokens_used > 0:
                    instance.tokens_used_today = max(0, tokens_used)

                # Auto-detect overload status
                if (
                    instance.status == InstanceStatus.ACTIVE
                    and instance.is_overloaded
                ):
                    instance.status = InstanceStatus.OVERLOADED
                    logger.warning(
                        "Instance auto-marked OVERLOADED: instance_id=%s, "
                        "load=%d/%d (%.1f%%) for company_id=%s",
                        instance_id, instance.current_load,
                        instance.max_concurrent,
                        instance.utilization_pct * 100,
                        company_id,
                    )

            logger.debug(
                "Load updated: company_id=%s, instance_id=%s, active=%d, "
                "queued=%d, tokens=%d",
                company_id, instance_id, active_tickets, queued_tickets,
                instance.tokens_used_today,
            )
            return True
        except Exception:
            logger.exception(
                "update_instance_load failed for company_id=%s, instance_id=%s",
                company_id,
                instance_id,
            )
            return False

    def update_instance_status(
        self,
        company_id: str,
        instance_id: str,
        status: InstanceStatus,
    ) -> bool:
        """Mark an instance as healthy, unhealthy, overloaded, etc.

        When an instance is marked UNHEALTHY, all sticky sessions pinned
        to it are cleared so future requests are re-routed.

        Args:
            company_id:  Tenant identifier (BC-001).
            instance_id: Instance to update.
            status:      New status.

        Returns:
            ``True`` if the instance was found and updated, ``False`` otherwise.
        """
        try:
            with self._lock:
                key = (company_id, instance_id)
                instance = self._instances.get(key)
                if instance is None:
                    logger.warning(
                        "update_instance_status: instance_id=%s not found "
                        "for company_id=%s",
                        instance_id, company_id,
                    )
                    return False

                old_status = instance.status
                instance.status = status

                # When going unhealthy, invalidate sticky sessions
                if (
                    status == InstanceStatus.UNHEALTHY
                    and old_status != InstanceStatus.UNHEALTHY
                ):
                    session_keys = self._instance_sessions.get(key, set())
                    invalidated = 0
                    for session_key in list(session_keys):
                        session_map_key = (company_id, session_key)
                        session = self._sticky_sessions.pop(
                            session_map_key, None,
                        )
                        if session is not None:
                            invalidated += 1
                    session_keys.clear()

                    stats = self._get_stats(company_id)
                    stats.sticky_expired += invalidated

                    logger.warning(
                        "Instance %s → UNHEALTHY: company_id=%s, "
                        "instance_id=%s, sticky_sessions_invalidated=%d",
                        old_status.value, company_id, instance_id, invalidated,
                    )

                # When recovering from OVERLOADED, restore to ACTIVE
                if (
                    old_status == InstanceStatus.OVERLOADED
                    and status == InstanceStatus.OVERLOADED
                    and not instance.is_overloaded
                ):
                    instance.status = InstanceStatus.ACTIVE
                    logger.info(
                        "Instance auto-recovered OVERLOADED → ACTIVE: "
                        "company_id=%s, instance_id=%s",
                        company_id, instance_id,
                    )

            logger.info(
                "Instance status: company_id=%s, instance_id=%s, %s → %s",
                company_id, instance_id, old_status.value, status.value,
            )
            return True
        except Exception:
            logger.exception(
                "update_instance_status failed for company_id=%s, "
                "instance_id=%s",
                company_id, instance_id,
            )
            return False

    # ══════════════════════════════════════════════════════════════
    # MAIN DISTRIBUTION (ROUTING)
    # ══════════════════════════════════════════════════════════════

    def distribute(
        self,
        company_id: str,
        variant_type: str,
        ticket_id: str,
        customer_id: str = "",
        preferred_channel: str = "",
    ) -> DistributionResult:
        """Main routing entry point — find the best instance for a ticket.

        Routing priority order:
        1.  **Sticky session** — if ticket_id or customer_id is already
            pinned to a healthy instance, use it.
        2.  **Round-robin** — cycle through instances using weighted
            round-robin, skipping unhealthy/overloaded ones.
        3.  **Least-loaded fallback** — if all instances have equal weight,
            pick the one with the lowest effective load.

        After routing, the ticket_id is registered as a sticky session
        so future messages in the same conversation go to the same instance.

        Args:
            company_id:        Tenant identifier (BC-001).
            variant_type:      Which variant pool to distribute within.
            ticket_id:         Ticket being routed.
            customer_id:       Customer for sticky session lookup.
            preferred_channel: Preferred channel for filtering instances.

        Returns:
            A :class:`DistributionResult` with the selected instance and
            routing method used.
        """
        try:
            with self._lock:
                self._maybe_reset_tokens(company_id)
                stats = self._get_stats(company_id)

                # ── Step 1: Sticky session lookup ────────────────
                sticky_result = self._try_sticky_routing(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    customer_id=customer_id,
                    variant_type=variant_type,
                    stats=stats,
                )
                if sticky_result is not None:
                    stats.total_distributions += 1
                    return sticky_result

                # ── Step 2: Eligible instances ───────────────────
                eligible = self._get_eligible_instances(
                    company_id, variant_type, preferred_channel,
                )

                if not eligible:
                    logger.warning(
                        "No eligible instances for company_id=%s, "
                        "variant=%s, channel=%s",
                        company_id, variant_type, preferred_channel or "(any)",
                    )
                    stats.no_instance_available += 1
                    stats.total_distributions += 1
                    return DistributionResult(
                        instance_id="",
                        company_id=company_id,
                        variant_type=variant_type,
                        routing_method=RoutingMethod.NO_INSTANCE_AVAILABLE.value,
                        load_at_routing=0,
                        capacity=0,
                        reason=(
                            "No eligible instances available. All instances "
                            "may be unhealthy, inactive, or filtered out by "
                            "channel assignment."),
                    )

                # ── Step 3: Weighted round-robin ──────────────────
                result = self._weighted_round_robin(
                    company_id=company_id,
                    variant_type=variant_type,
                    eligible=eligible,
                    stats=stats,
                )

                # ── Step 4: Auto-register sticky session ──────────
                if result.instance_id:
                    self._register_sticky_internal(
                        company_id=company_id,
                        session_key=ticket_id,
                        instance_id=result.instance_id,
                        ttl_seconds=DEFAULT_STICKY_TTL_SECONDS,
                    )

                stats.total_distributions += 1
                return result

        except Exception:
            logger.exception(
                "distribute failed for company_id=%s, variant=%s, "
                "ticket_id=%s — returning no_instance_available",
                company_id, variant_type, ticket_id,
            )
            return DistributionResult(
                instance_id="",
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.NO_INSTANCE_AVAILABLE.value,
                load_at_routing=0,
                capacity=0,
                reason="Internal error during distribution routing.",
            )

    def _try_sticky_routing(
        self,
        company_id: str,
        ticket_id: str,
        customer_id: str,
        variant_type: str,
        stats: DistributionStats,
    ) -> Optional[DistributionResult]:
        """Attempt to route via an existing sticky session.

        Checks ticket_id first, then customer_id.  If a session is found
        and the target instance is healthy, returns the result immediately.
        If the session exists but the instance is unhealthy, clears the
        session and returns ``None`` to trigger round-robin fallback.

        Must be called while holding ``_lock``.
        """
        # Try ticket_id as session key first (highest priority)
        session_keys_to_try: List[str] = []
        if ticket_id:
            session_keys_to_try.append(ticket_id)
        if customer_id and customer_id != ticket_id:
            session_keys_to_try.append(customer_id)

        for session_key in session_keys_to_try:
            map_key = (company_id, session_key)
            session = self._sticky_sessions.get(map_key)

            if session is None:
                stats.sticky_misses += 1
                continue

            if session.is_expired:
                # Expired — clean up and continue
                self._sticky_sessions.pop(map_key, None)
                inst_key = (company_id, session.instance_id)
                sessions_set = self._instance_sessions.get(inst_key)
                if sessions_set:
                    sessions_set.discard(session_key)
                stats.sticky_expired += 1
                stats.sticky_misses += 1
                logger.debug(
                    "Sticky session expired: company_id=%s, "
                    "session_key=%s, instance_id=%s",
                    company_id, session_key, session.instance_id,
                )
                continue

            # Check if the target instance still exists and is routable
            inst_key = (company_id, session.instance_id)
            instance = self._instances.get(inst_key)

            if instance is None or not instance.is_routable:
                # Instance gone or not routable — clear session
                self._sticky_sessions.pop(map_key, None)
                sessions_set = self._instance_sessions.get(inst_key)
                if sessions_set:
                    sessions_set.discard(session_key)
                stats.sticky_expired += 1
                stats.sticky_misses += 1
                logger.info(
                    "Sticky session invalidated (instance unavailable): "
                    "company_id=%s, session_key=%s, instance_id=%s",
                    company_id, session_key, session.instance_id,
                )
                continue

            # Check variant type still matches
            if instance.variant_type != variant_type:
                stats.sticky_misses += 1
                continue

            # Valid sticky session — use it
            session.touch()
            stats.sticky_hits += 1

            logger.info(
                "Sticky routing hit: company_id=%s, session_key=%s → "
                "instance_id=%s, variant=%s",
                company_id, session_key, instance.instance_id, variant_type,
            )
            return DistributionResult(
                instance_id=instance.instance_id,
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.STICKY.value,
                load_at_routing=instance.current_load,
                capacity=instance.max_concurrent,
                reason=(
                    f"Sticky session: session_key={session_key} → "
                    f"instance={instance.instance_id}"
                ),
            )

        return None

    def _weighted_round_robin(
        self,
        company_id: str,
        variant_type: str,
        eligible: List[InstanceInfo],
        stats: DistributionStats,
    ) -> DistributionResult:
        """Select an instance using weighted round-robin.

        Builds a weighted candidate list and advances the counter.
        Skips instances that are overloaded (unless no other choice).
        Falls back to least-loaded selection if all weights are equal.

        Must be called while holding ``_lock``.
        """
        rr_key = (company_id, variant_type)
        counter = self._rr_counter.get(rr_key, 0)

        # Build weighted candidate list: each instance appears
        # ``weight * 100`` times (using int for round-robin index)
        weighted_candidates: List[InstanceInfo] = []
        for inst in eligible:
            slots = max(1, int(inst.weight * 100))
            weighted_candidates.extend([inst] * slots)

        if not weighted_candidates:
            # No candidates at all — should not happen since caller checks
            return DistributionResult(
                instance_id="",
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.NO_INSTANCE_AVAILABLE.value,
                load_at_routing=0,
                capacity=0,
                reason="No candidates for weighted round-robin.",
            )

        # Try non-overloaded candidates first
        non_overloaded = [
            inst for inst in eligible
            if not inst.is_overloaded and inst.available_capacity > 0
        ]

        if non_overloaded:
            # Build weighted list from non-overloaded only
            non_ol_candidates: List[InstanceInfo] = []
            for inst in non_overloaded:
                slots = max(1, int(inst.weight * 100))
                non_ol_candidates.extend([inst] * slots)

            idx = counter % len(non_ol_candidates)
            selected = non_ol_candidates[idx]
            self._rr_counter[rr_key] = counter + 1

            logger.info(
                "Round-robin routing: company_id=%s, variant=%s → "
                "instance_id=%s (index=%d, weight=%.2f, "
                "load=%d/%d, candidates=%d)",
                company_id, variant_type, selected.instance_id, idx,
                selected.weight, selected.current_load,
                selected.max_concurrent, len(non_ol_candidates),
            )
            stats.round_robin_routes += 1
            return DistributionResult(
                instance_id=selected.instance_id,
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.ROUND_ROBIN.value,
                load_at_routing=selected.current_load,
                capacity=selected.max_concurrent,
                reason=(
                    f"Weighted round-robin: instance={selected.instance_id}, "
                    f"weight={selected.weight:.2f}, "
                    f"load={selected.current_load}/{selected.max_concurrent}"
                ),
            )

        # All instances overloaded or at capacity — use least-loaded
        selected = self._select_least_loaded(eligible)
        if selected is None:
            return DistributionResult(
                instance_id="",
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.NO_INSTANCE_AVAILABLE.value,
                load_at_routing=0,
                capacity=0,
                reason="All instances at full capacity.",
            )

        self._rr_counter[rr_key] = counter + 1
        stats.least_loaded_routes += 1

        logger.info(
            "Least-loaded routing (all overloaded): company_id=%s, "
            "variant=%s → instance_id=%s (effective_load=%.1f, "
            "load=%d/%d)",
            company_id, variant_type, selected.instance_id,
            selected.effective_load, selected.current_load,
            selected.max_concurrent,
        )
        return DistributionResult(
            instance_id=selected.instance_id,
            company_id=company_id,
            variant_type=variant_type,
            routing_method=RoutingMethod.LEAST_LOADED.value,
            load_at_routing=selected.current_load,
            capacity=selected.max_concurrent,
            reason=(
                f"Least-loaded fallback: instance={selected.instance_id}, "
                f"effective_load={selected.effective_load:.1f}, "
                f"load={selected.current_load}/{selected.max_concurrent}"
            ),
        )

    def _select_least_loaded(
        self,
        eligible: List[InstanceInfo],
    ) -> Optional[InstanceInfo]:
        """Pick the instance with the lowest effective load.

        Considers both active tickets and queued count.  If tied,
        prefers the one with more available capacity.

        Must be called while holding ``_lock``.
        """
        if not eligible:
            return None

        # Sort by effective_load ascending, then by available_capacity
        # descending
        sorted_instances = sorted(
            eligible,
            key=lambda inst: (inst.effective_load, -inst.available_capacity),
        )
        return sorted_instances[0]

    # ══════════════════════════════════════════════════════════════
    # STICKY SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def register_sticky_session(
        self,
        company_id: str,
        session_key: str,
        instance_id: str,
        ttl_seconds: float = DEFAULT_STICKY_TTL_SECONDS,
    ) -> bool:
        """Pin a session key (ticket_id or customer_id) to an instance.

        Future calls to :meth:`distribute` will prefer routing the same
        session key back to this instance for conversation continuity.

        Args:
            company_id:    Tenant identifier (BC-001).
            session_key:   Identifier to pin (ticket_id or customer_id).
            instance_id:   Instance to pin the session to.
            ttl_seconds:   Session time-to-live in seconds (default 3600).

        Returns:
            ``True`` if the session was registered, ``False`` otherwise.
        """
        try:
            with self._lock:
                return self._register_sticky_internal(
                    company_id, session_key, instance_id, ttl_seconds,
                )
        except Exception:
            logger.exception(
                "register_sticky_session failed for company_id=%s, "
                "session_key=%s, instance_id=%s",
                company_id, session_key, instance_id,
            )
            return False

    def _register_sticky_internal(
        self,
        company_id: str,
        session_key: str,
        instance_id: str,
        ttl_seconds: float,
    ) -> bool:
        """Internal sticky session registration (caller must hold lock)."""
        # Validate instance exists
        inst_key = (company_id, instance_id)
        if inst_key not in self._instances:
            logger.warning(
                "register_sticky_session: instance_id=%s not found for "
                "company_id=%s — cannot pin session",
                instance_id, company_id,
            )
            return False

        map_key = (company_id, session_key)

        # If re-pinning to a different instance, clean old mapping
        old_session = self._sticky_sessions.get(map_key)
        if old_session and old_session.instance_id != instance_id:
            old_inst_key = (company_id, old_session.instance_id)
            old_sessions = self._instance_sessions.get(old_inst_key)
            if old_sessions:
                old_sessions.discard(session_key)

        session = StickySession(
            session_key=session_key,
            instance_id=instance_id,
            ttl_seconds=ttl_seconds,
        )
        self._sticky_sessions[map_key] = session

        # Update reverse mapping
        if inst_key not in self._instance_sessions:
            self._instance_sessions[inst_key] = set()
        self._instance_sessions[inst_key].add(session_key)

        logger.debug(
            "Sticky session registered: company_id=%s, session_key=%s → "
            "instance_id=%s, ttl=%.0fs",
            company_id, session_key, instance_id, ttl_seconds,
        )
        return True

    def get_sticky_instance(
        self,
        company_id: str,
        session_key: str,
    ) -> Optional[str]:
        """Find which instance a session key is pinned to.

        Returns ``None`` if no session exists or it has expired.

        Args:
            company_id:   Tenant identifier (BC-001).
            session_key:  Identifier to look up.

        Returns:
            Instance ID string, or ``None``.
        """
        try:
            with self._lock:
                map_key = (company_id, session_key)
                session = self._sticky_sessions.get(map_key)

                if session is None:
                    return None

                if session.is_expired:
                    self._sticky_sessions.pop(map_key, None)
                    inst_key = (company_id, session.instance_id)
                    sessions_set = self._instance_sessions.get(inst_key)
                    if sessions_set:
                        sessions_set.discard(session_key)
                    return None

                session.touch()
                return session.instance_id
        except Exception:
            logger.exception(
                "get_sticky_instance failed for company_id=%s, "
                "session_key=%s",
                company_id, session_key,
            )
            return None

    def clear_sticky_session(
        self,
        company_id: str,
        session_key: str,
    ) -> bool:
        """Remove a sticky session pin.

        Args:
            company_id:   Tenant identifier (BC-001).
            session_key:  Identifier to unpin.

        Returns:
            ``True`` if a session was found and removed, ``False`` otherwise.
        """
        try:
            with self._lock:
                map_key = (company_id, session_key)
                session = self._sticky_sessions.pop(map_key, None)

                if session is None:
                    return False

                inst_key = (company_id, session.instance_id)
                sessions_set = self._instance_sessions.get(inst_key)
                if sessions_set:
                    sessions_set.discard(session_key)

                stats = self._get_stats(company_id)
                stats.sessions_cleared += 1

                logger.info(
                    "Sticky session cleared: company_id=%s, session_key=%s, "
                    "was_instance_id=%s",
                    company_id, session_key, session.instance_id,
                )
                return True
        except Exception:
            logger.exception(
                "clear_sticky_session failed for company_id=%s, "
                "session_key=%s",
                company_id, session_key,
            )
            return False

    def cleanup_expired_sessions(
        self,
        company_id: str,
        max_age_seconds: float = 7200.0,
    ) -> int:
        """Remove old sticky sessions that have exceeded their TTL or age.

        This is a housekeeping method intended to be called periodically
        (e.g. by a cron job or background task) to prevent unbounded
        memory growth of the session store.

        Args:
            company_id:        Tenant identifier (BC-001).
            max_age_seconds:   Maximum session age in seconds (default 2h).
                                Sessions older than this are removed regardless
                                of TTL.

        Returns:
            Number of sessions that were cleaned up.
        """
        try:
            cleaned = 0
            now = time.time()

            with self._lock:
                # Collect expired keys
                keys_to_remove: List[Tuple[str, str]] = []
                for (cid, skey), session in self._sticky_sessions.items():
                    if cid != company_id:
                        continue
                    if session.is_expired or session.age_seconds > max_age_seconds:
                        keys_to_remove.append((cid, skey))

                # Remove them
                for key in keys_to_remove:
                    session = self._sticky_sessions.pop(key, None)
                    if session is not None:
                        inst_key = (company_id, session.instance_id)
                        sessions_set = self._instance_sessions.get(inst_key)
                        if sessions_set:
                            sessions_set.discard(session.session_key)
                        cleaned += 1

                stats = self._get_stats(company_id)
                stats.sticky_expired += cleaned
                stats.sessions_cleared += cleaned

            if cleaned > 0:
                logger.info(
                    "Expired session cleanup: company_id=%s, "
                    "sessions_cleaned=%d, remaining=%d",
                    company_id, cleaned,
                    sum(
                        1 for (cid, _) in self._sticky_sessions
                        if cid == company_id
                    ),
                )
            return cleaned
        except Exception:
            logger.exception(
                "cleanup_expired_sessions failed for company_id=%s",
                company_id,
            )
            return 0

    # ══════════════════════════════════════════════════════════════
    # FAILOVER
    # ══════════════════════════════════════════════════════════════

    def failover_ticket(
        self,
        company_id: str,
        ticket_id: str,
        from_instance_id: str,
        reason: str = "",
    ) -> Optional[DistributionResult]:
        """Reroute a ticket from a failed/overloaded instance to another.

        Selects the least-loaded eligible instance as the failover target.
        Logs the failover event for analytics.  Clears any sticky session
        that pins the ticket to the old instance.

        Args:
            company_id:        Tenant identifier (BC-001).
            ticket_id:         Ticket being rerouted.
            from_instance_id:  Source instance that failed.
            reason:            Human-readable reason for the failover.

        Returns:
            A :class:`DistributionResult` for the new target instance,
            or ``None`` if no eligible target was found.
        """
        try:
            with self._lock:
                self._maybe_reset_tokens(company_id)
                stats = self._get_stats(company_id)

                # Get the source instance to know the variant type
                src_key = (company_id, from_instance_id)
                src_instance = self._instances.get(src_key)
                if src_instance is None:
                    logger.warning(
                        "failover_ticket: source instance_id=%s not found "
                        "for company_id=%s — cannot determine variant_type",
                        from_instance_id, company_id,
                    )
                    return None

                variant_type = src_instance.variant_type

                # Get eligible instances (exclude the source)
                eligible = [
                    inst for inst in self._get_eligible_instances(
                        company_id, variant_type,
                    )
                    if inst.instance_id != from_instance_id
                ]

                if not eligible:
                    logger.error(
                        "failover_ticket: no eligible target instances for "
                        "company_id=%s, variant=%s, from_instance=%s",
                        company_id, variant_type, from_instance_id,
                    )
                    stats.failover_count += 1
                    return None

                # Select least-loaded target
                target = self._select_least_loaded(eligible)
                if target is None:
                    stats.failover_count += 1
                    return None

                # Clear sticky session for this ticket (it was pinned to old)
                self._sticky_sessions.pop((company_id, ticket_id), None)
                inst_sessions = self._instance_sessions.get(src_key)
                if inst_sessions:
                    inst_sessions.discard(ticket_id)

                # Register new sticky session to the target
                self._register_sticky_internal(
                    company_id=company_id,
                    session_key=ticket_id,
                    instance_id=target.instance_id,
                    ttl_seconds=DEFAULT_STICKY_TTL_SECONDS,
                )

                # Record failover event
                event = FailoverEvent(
                    ticket_id=ticket_id,
                    company_id=company_id,
                    from_instance_id=from_instance_id,
                    to_instance_id=target.instance_id,
                    reason=reason or "instance_failure",
                )
                if company_id not in self._failover_history:
                    self._failover_history[company_id] = []
                self._failover_history[company_id].append(event)

                # Keep failover history bounded
                max_history = 10_000
                if len(self._failover_history[company_id]) > max_history:
                    self._failover_history[company_id] = (
                        self._failover_history[company_id][-max_history // 2:]
                    )

                stats.failover_count += 1

            logger.warning(
                "Failover: ticket_id=%s, company_id=%s, %s → %s, "
                "variant=%s, reason=%s",
                ticket_id, company_id, from_instance_id,
                target.instance_id, variant_type, reason,
            )
            return DistributionResult(
                instance_id=target.instance_id,
                company_id=company_id,
                variant_type=variant_type,
                routing_method=RoutingMethod.FAILOVER.value,
                load_at_routing=target.current_load,
                capacity=target.max_concurrent,
                reason=(
                    f"Failover from {from_instance_id}: {reason}. "
                    f"Rerouted to {target.instance_id} "
                    f"(load={target.current_load}/{target.max_concurrent})."
                ),
            )
        except Exception:
            logger.exception(
                "failover_ticket failed for company_id=%s, ticket_id=%s, "
                "from_instance=%s",
                company_id, ticket_id, from_instance_id,
            )
            return None

    # ══════════════════════════════════════════════════════════════
    # INSTANCE QUERIES
    # ══════════════════════════════════════════════════════════════

    def get_all_instances(
        self,
        company_id: str,
        variant_type: str = "",
    ) -> List[InstanceInfo]:
        """List all registered instances for a company.

        Args:
            company_id:   Tenant identifier (BC-001).
            variant_type: If provided, filter to this variant only.

        Returns:
            List of :class:`InstanceInfo` objects.  Empty list on error (BC-008).
        """
        try:
            with self._lock:
                result: List[InstanceInfo] = []
                for (cid, _iid), instance in self._instances.items():
                    if cid != company_id:
                        continue
                    if variant_type and instance.variant_type != variant_type:
                        continue
                    result.append(instance)
                return result
        except Exception:
            logger.exception(
                "get_all_instances failed for company_id=%s, variant=%s",
                company_id, variant_type,
            )
            return []

    def get_instance_load_summary(
        self,
        company_id: str,
        variant_type: str = "",
    ) -> Dict[str, Any]:
        """Load overview across all instances for a company.

        Returns a summary dictionary with per-instance metrics and
        aggregate statistics.

        Args:
            company_id:   Tenant identifier (BC-001).
            variant_type: If provided, filter to this variant only.

        Returns:
            Dict with ``instances``, ``total_active``, ``total_queued``,
            ``total_capacity``, ``aggregate_utilization_pct``, etc.
        """
        try:
            instances = self.get_all_instances(company_id, variant_type)

            total_active = 0
            total_queued = 0
            total_capacity = 0
            total_tokens = 0
            instance_summaries: List[Dict[str, Any]] = []
            status_counts: Dict[str, int] = {}

            for inst in instances:
                total_active += inst.current_load
                total_queued += inst.queued_count
                total_capacity += inst.max_concurrent
                total_tokens += inst.tokens_used_today

                status_counts[inst.status.value] = (
                    status_counts.get(inst.status.value, 0) + 1
                )

                instance_summaries.append(inst.to_dict())

            agg_utilization = (
                (total_active / total_capacity * 100.0)
                if total_capacity > 0
                else 0.0
            )

            summary: Dict[str, Any] = {
                "company_id": company_id,
                "variant_type": variant_type or "(all)",
                "total_instances": len(instances),
                "total_active_tickets": total_active,
                "total_queued_tickets": total_queued,
                "total_capacity": total_capacity,
                "total_available_capacity": max(
                    0, total_capacity - total_active,
                ),
                "aggregate_utilization_pct": round(agg_utilization, 2),
                "total_tokens_used_today": total_tokens,
                "status_breakdown": status_counts,
                "instances": instance_summaries,
                "generated_at_utc": self._utc_now_iso(),
            }

            return summary
        except Exception:
            logger.exception(
                "get_instance_load_summary failed for company_id=%s, "
                "variant=%s",
                company_id, variant_type,
            )
            return {
                "company_id": company_id,
                "variant_type": variant_type,
                "error": "Failed to generate load summary",
                "instances": [],
                "generated_at_utc": self._utc_now_iso(),
            }

    # ══════════════════════════════════════════════════════════════
    # WEIGHT REBALANCING
    # ══════════════════════════════════════════════════════════════

    def rebalance_weights(
        self,
        company_id: str,
        variant_type: str,
    ) -> Dict[str, Any]:
        """Dynamically adjust instance weights based on current load.

        Algorithm:
        1.  Calculate each instance's utilisation ratio.
        2.  Instances with low utilisation get *increased* weight (send more).
        3.  Instances with high utilisation get *decreased* weight (send less).
        4.  Weights are normalised so the total is proportional to the
            number of instances (average weight stays near 1.0).
        5.  Changes smaller than :data:`REBALANCE_MIN_DIFFERENCE` are skipped
            to avoid unnecessary churn.

        Args:
            company_id:   Tenant identifier (BC-001).
            variant_type: Variant pool to rebalance.

        Returns:
            Dict with ``weight_changes``, ``before``, ``after`` summaries.
        """
        try:
            with self._lock:
                instances = [
                    inst for (cid, _iid), inst in self._instances.items()
                    if cid == company_id and inst.variant_type == variant_type
                ]

                if len(instances) < 2:
                    logger.info(
                        "rebalance_weights: need ≥ 2 instances for "
                        "company_id=%s, variant=%s (found %d) — skipping",
                        company_id, variant_type, len(instances),
                    )
                    return {
                        "company_id": company_id,
                        "variant_type": variant_type,
                        "skipped": True,
                        "reason": (
                            f"Need at least 2 instances for rebalancing, "
                            f"found {len(instances)}"
                        ),
                    }

                changes: List[Dict[str, Any]] = []

                for inst in instances:
                    old_weight = inst.weight
                    utilisation = inst.utilization_pct

                    if utilisation < 0.3:
                        # Under-utilised: boost weight to attract traffic
                        adjustment = 1.0 + (0.3 - utilisation)
                    elif utilisation > 0.7:
                        # High utilisation: reduce weight to shed traffic
                        adjustment = max(0.1, 1.0 - (utilisation - 0.7))
                    else:
                        # Moderate: keep near current
                        adjustment = 1.0

                    new_weight = round(inst.weight * adjustment, 4)
                    new_weight = max(0.05, min(10.0, new_weight))

                    # Skip trivial changes
                    if abs(new_weight - old_weight) < REBALANCE_MIN_DIFFERENCE:
                        continue

                    inst.weight = new_weight
                    changes.append({
                        "instance_id": inst.instance_id,
                        "old_weight": round(old_weight, 4),
                        "new_weight": new_weight,
                        "utilisation_pct": round(utilisation * 100, 2),
                        "adjustment_factor": round(adjustment, 4),
                    })

                # Log results
                if changes:
                    logger.info(
                        "Weights rebalanced: company_id=%s, variant=%s, "
                        "changes=%d: %s",
                        company_id, variant_type, len(changes),
                        ", ".join(
                            f"{c['instance_id']}: {c['old_weight']:.2f}→"
                            f"{c['new_weight']:.2f}"
                            for c in changes
                        ),
                    )
                else:
                    logger.info(
                        "Weights rebalanced: company_id=%s, variant=%s — "
                        "no changes needed (all within tolerance)",
                        company_id, variant_type,
                    )

                return {
                    "company_id": company_id,
                    "variant_type": variant_type,
                    "skipped": False,
                    "changes_count": len(changes),
                    "changes": changes,
                    "current_weights": {
                        inst.instance_id: round(inst.weight, 4)
                        for inst in instances
                    },
                    "rebalanced_at_utc": self._utc_now_iso(),
                }
        except Exception:
            logger.exception(
                "rebalance_weights failed for company_id=%s, variant=%s",
                company_id, variant_type,
            )
            return {
                "company_id": company_id,
                "variant_type": variant_type,
                "skipped": True,
                "reason": "Internal error during weight rebalancing",
                "changes": [],
            }

    # ══════════════════════════════════════════════════════════════
    # DISTRIBUTION STATISTICS
    # ══════════════════════════════════════════════════════════════

    def get_distribution_stats(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get routing statistics for a company.

        Includes sticky session hit rate, round-robin count, failover count,
        and recent failover events.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with routing statistics and recent failover history.
        """
        try:
            with self._lock:
                stats = self._get_stats(company_id)
                failover_events = self._failover_history.get(company_id, [])

                # Count active sticky sessions
                active_sessions = sum(
                    1 for (cid, _), session in self._sticky_sessions.items()
                    if cid == company_id and not session.is_expired
                )

                # Count instances per status
                instance_status_counts: Dict[str, int] = {}
                for (cid, _iid), inst in self._instances.items():
                    if cid == company_id:
                        instance_status_counts[inst.status.value] = (
                            instance_status_counts.get(inst.status.value, 0) + 1
                        )

                # Recent failover events (last 50)
                recent_failovers = [
                    evt.to_dict() for evt in failover_events[-50:]
                ]

            return {
                "company_id": company_id,
                "routing_stats": stats.to_dict(),
                "active_sticky_sessions": active_sessions,
                "instance_status_counts": instance_status_counts,
                "total_failover_events": len(failover_events),
                "recent_failovers": recent_failovers,
                "generated_at_utc": self._utc_now_iso(),
            }
        except Exception:
            logger.exception(
                "get_distribution_stats failed for company_id=%s",
                company_id,
            )
            return {
                "company_id": company_id,
                "routing_stats": DistributionStats().to_dict(),
                "active_sticky_sessions": 0,
                "instance_status_counts": {},
                "total_failover_events": 0,
                "recent_failovers": [],
                "error": "Failed to generate distribution stats",
                "generated_at_utc": self._utc_now_iso(),
            }

    # ══════════════════════════════════════════════════════════════
    # UTILITY / MAINTENANCE
    # ══════════════════════════════════════════════════════════════

    def get_failover_history(
        self,
        company_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent failover events for a company.

        Args:
            company_id: Tenant identifier (BC-001).
            limit:      Maximum events to return (default 100).

        Returns:
            List of failover event dictionaries, newest first.
        """
        try:
            with self._lock:
                events = self._failover_history.get(company_id, [])
                recent = events[-limit:]
                # Return newest first
                return [evt.to_dict() for evt in reversed(recent)]
        except Exception:
            logger.exception(
                "get_failover_history failed for company_id=%s",
                company_id,
            )
            return []

    def get_instance_info(
        self,
        company_id: str,
        instance_id: str,
    ) -> Optional[InstanceInfo]:
        """Get detailed information about a single instance.

        Args:
            company_id:  Tenant identifier (BC-001).
            instance_id: Instance to look up.

        Returns:
            :class:`InstanceInfo` if found, ``None`` otherwise.
        """
        try:
            with self._lock:
                return self._instances.get((company_id, instance_id))
        except Exception:
            logger.exception(
                "get_instance_info failed for company_id=%s, instance_id=%s",
                company_id, instance_id,
            )
            return None

    def get_instance_sticky_sessions(
        self,
        company_id: str,
        instance_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all sticky sessions pinned to a specific instance.

        Args:
            company_id:  Tenant identifier (BC-001).
            instance_id: Instance to query.

        Returns:
            List of session info dictionaries.
        """
        try:
            with self._lock:
                session_keys = self._instance_sessions.get(
                    (company_id, instance_id), set(),
                )
                result: List[Dict[str, Any]] = []
                for skey in session_keys:
                    session = self._sticky_sessions.get(
                        (company_id, skey),
                    )
                    if session is not None:
                        result.append({
                            "session_key": session.session_key,
                            "instance_id": session.instance_id,
                            "age_seconds": round(session.age_seconds, 1),
                            "last_used_seconds_ago": round(
                                time.time() - session.last_used, 1,
                            ),
                            "ttl_seconds": session.ttl_seconds,
                            "is_expired": session.is_expired,
                        })
                return result
        except Exception:
            logger.exception(
                "get_instance_sticky_sessions failed for company_id=%s, "
                "instance_id=%s",
                company_id, instance_id,
            )
            return []

    def reset_round_robin_counter(
        self,
        company_id: str,
        variant_type: str,
    ) -> bool:
        """Reset the round-robin counter for a company+variant combination.

        Useful after instance registration changes to avoid bias.

        Args:
            company_id:   Tenant identifier (BC-001).
            variant_type: Variant to reset.

        Returns:
            ``True`` if the counter was reset, ``False`` if it didn't exist.
        """
        try:
            with self._lock:
                key = (company_id, variant_type)
                if key in self._rr_counter:
                    self._rr_counter[key] = 0
                    logger.info(
                        "Round-robin counter reset: company_id=%s, "
                        "variant=%s",
                        company_id, variant_type,
                    )
                    return True
                return False
        except Exception:
            logger.exception(
                "reset_round_robin_counter failed for company_id=%s, "
                "variant=%s",
                company_id, variant_type,
            )
            return False

    def clear_company_data(
        self,
        company_id: str,
    ) -> None:
        """Remove all data for a company (useful for cleanup / testing).

        Removes all instances, sticky sessions, round-robin counters,
        failover history, and stats for the given company.

        Args:
            company_id: Tenant identifier (BC-001).
        """
        try:
            with self._lock:
                # Collect instance IDs to clean up
                instance_keys = [
                    k for k, _ in self._instances.items()
                    if k[0] == company_id
                ]

                # Remove instances
                for key in instance_keys:
                    self._instances.pop(key, None)
                    self._instance_sessions.pop(key, None)

                # Remove sticky sessions for this company
                sticky_keys_to_remove = [
                    key for (cid, _) in self._sticky_sessions
                    if cid == company_id
                ]
                for key in sticky_keys_to_remove:
                    self._sticky_sessions.pop(key, None)

                # Remove round-robin counters
                rr_keys_to_remove = [
                    key for (cid, _) in self._rr_counter
                    if cid == company_id
                ]
                for key in rr_keys_to_remove:
                    self._rr_counter.pop(key, None)

                # Remove failover history
                self._failover_history.pop(company_id, None)

                # Remove stats
                self._stats.pop(company_id, None)

                # Remove token reset tracking
                self._last_token_reset.pop(company_id, None)

            logger.info(
                "All data cleared for company_id=%s (instances=%d, "
                "sticky_sessions=%d, rr_counters=%d)",
                company_id, len(instance_keys),
                len(sticky_keys_to_remove), len(rr_keys_to_remove),
            )
        except Exception:
            logger.exception(
                "clear_company_data failed for company_id=%s",
                company_id,
            )
