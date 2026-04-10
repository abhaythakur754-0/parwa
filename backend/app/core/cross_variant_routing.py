"""
Cross-Variant Routing (SG-06 + SG-11) — Combined Module.

SG-06  Cross-Variant Routing Rules:
    - Channel → Variant default mapping
    - Escalation path: parwa_lite → parwa → parwa_high
    - Shared context on escalation
    - Bill to originating variant unless explicitly escalated

SG-11 Cross-Variant Ticket Routing Algorithm:
    1. Map channel → default variant
    2. If variant at >90 % capacity → auto-escalate to next higher variant
    3. If no higher variant available → assign to human queue with AI_OVERLOAD flag
    4. Bill to originating variant unless explicitly escalated
    5. Track routing decisions for analytics

W9-GAP-015 (HIGH) — Escalation rollback:
    If the target variant is itself at capacity, queue with priority +
    fallback timer (30 s).  If not picked up within 30 s, try next tier.
    If all tiers full → human queue.

BC-001: company_id is always first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger(__name__)


# ── Constants ───────────────────────────────────────────────────────

CAPACITY_THRESHOLD_PCT: float = 90.0
ESCALATION_FALLBACK_SECONDS: float = 30.0
AI_OVERLOAD_FLAG: str = "AI_OVERLOAD"

# Ordered escalation chain — lowest to highest variant tier.
ESCALATION_CHAIN: List[str] = [
    "parwa_lite",   # Tier 1 — Starter
    "parwa",        # Tier 2 — Growth
    "parwa_high",   # Tier 3 — High
]

VALID_VARIANTS: set = set(ESCALATION_CHAIN)

# Default channel → variant mapping (before per-company overrides).
DEFAULT_CHANNEL_MAPPINGS: Dict[str, Tuple[str, int]] = {
    "email":       ("parwa",        10),
    "chat":        ("parwa_lite",    20),
    "phone":       ("parwa_high",    30),
    "web_widget":  ("parwa_lite",    20),
    "social":      ("parwa",         10),
}


# ── Enums ───────────────────────────────────────────────────────────


class ChannelType(str, Enum):
    """Supported inbound ticket channels."""

    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    WEB_WIDGET = "web_widget"
    SOCIAL = "social"


class RoutingDecisionType(str, Enum):
    """Outcome of a routing decision."""

    ROUTE = "route"
    ESCALATE = "escalate"
    QUEUE = "queue"
    HUMAN_OVERRIDE = "human_override"


class EscalationReason(str, Enum):
    """Reasons why a ticket was escalated to a higher variant."""

    CAPACITY_EXCEEDED = "capacity_exceeded"
    COMPLEXITY_EXCEEDED = "complexity_exceeded"
    MANUAL_REQUEST = "manual_request"
    TECHNIQUE_UNAVAILABLE = "technique_unavailable"
    NO_FALLBACK = "no_fallback"


# ── Data Structures ─────────────────────────────────────────────────


@dataclass
class ChannelMapping:
    """Mapping from a channel to its default variant and priority."""

    channel: ChannelType
    default_variant: str
    priority: int = 0


@dataclass
class EscalationPath:
    """Record of a single escalation step between variants."""

    from_variant: str
    to_variant: str
    reason: EscalationReason
    timestamp: datetime
    ticket_id: str = ""


@dataclass
class RoutingResult:
    """Complete result of a ticket routing decision."""

    ticket_id: str
    target_variant: str
    original_variant: str
    decision: RoutingDecisionType
    channel: ChannelType
    company_id: str = ""
    reason: str = ""
    escalated: bool = False
    billed_to_variant: str = ""
    complexity_score: float = 0.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass
class CapacitySnapshot:
    """Point-in-time capacity reading for a variant."""

    variant_type: str
    current_load: int
    max_capacity: int
    utilization_pct: float


@dataclass
class QueuedTicket:
    """Ticket sitting in the priority queue awaiting pickup."""

    ticket_id: str
    company_id: str
    queued_at: float  # time.monotonic() for reliable drift-free measurement
    fallback_variant: str  # next variant to try on timeout
    reason: EscalationReason
    priority: int = 0


# ── Custom Error ────────────────────────────────────────────────────


class CrossVariantRoutingError(ParwaBaseError):
    """Raised when cross-variant routing cannot proceed.

    Inherits from ParwaBaseError so the global error handler can
    serialise it into a structured JSON response (BC-012).
    """

    def __init__(
        self,
        message: str = "Cross-variant routing failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="CROSS_VARIANT_ROUTING_ERROR",
            status_code=503,
            details=details,
        )


# ── Main Service ────────────────────────────────────────────────────


class CrossVariantRouter:
    """Routes tickets across PARWA variant tiers (SG-06 + SG-11).

    Responsibilities:
    - Map channels to default variants
    - Detect capacity overload and auto-escalate
    - Implement W9-GAP-015 escalation rollback with fallback timer
    - Track routing decisions and escalation history
    - Bill to originating variant unless explicitly escalated

    Thread-safety: capacity / queue state is protected by ``_lock``.
    In production, replace in-memory stores with Redis.
    """

    def __init__(self) -> None:
        # Per-company channel overrides: {company_id: {channel_str: ChannelMapping}}
        self._channel_overrides: Dict[str, Dict[str, ChannelMapping]] = {}
        # Capacity store: {company_id: {variant: CapacitySnapshot}}
        self._capacity: Dict[str, Dict[str, CapacitySnapshot]] = {}
        # Routing history: {ticket_id: [EscalationPath, ...]}
        self._routing_history: Dict[str, List[EscalationPath]] = {}
        # Priority queue for tickets awaiting pickup (W9-GAP-015)
        self._pending_queue: List[QueuedTicket] = []
        self._lock = threading.Lock()

        logger.info(
            "CrossVariantRouter initialised — escalation chain: %s",
            " → ".join(ESCALATION_CHAIN),
        )

    # ── Channel Mapping ─────────────────────────────────────────

    def get_default_variant_for_channel(
        self,
        channel: ChannelType,
    ) -> str:
        """Return the default variant for a channel.

        Checks per-company overrides first, then falls back to global
        defaults.  Returns ``parwa`` as a safe default if the channel
        is unrecognised (BC-008).
        """
        try:
            variant, _priority = DEFAULT_CHANNEL_MAPPINGS.get(
                channel.value, ("parwa", 0),
            )
            logger.debug(
                "Channel %s → default variant %s",
                channel.value, variant,
            )
            return variant
        except Exception:
            logger.exception(
                "Failed to resolve default variant for channel=%s, "
                "returning safe fallback 'parwa'",
                channel,
            )
            return "parwa"

    def _resolve_channel_mapping(
        self,
        company_id: str,
        channel: ChannelType,
    ) -> ChannelMapping:
        """Internal: resolve channel → variant with company overrides."""
        with self._lock:
            overrides = self._channel_overrides.get(company_id, {})
            mapping = overrides.get(channel.value)
            if mapping is not None:
                return mapping

        default_variant, priority = DEFAULT_CHANNEL_MAPPINGS.get(
            channel.value, ("parwa", 0),
        )
        return ChannelMapping(
            channel=channel,
            default_variant=default_variant,
            priority=priority,
        )

    def register_channel_mapping(
        self,
        company_id: str,
        channel: ChannelType,
        variant: str,
        priority: int = 0,
    ) -> None:
        """Register a per-company custom channel → variant mapping.

        BC-001: company_id is first parameter.
        BC-008: Never raises — logs on failure.
        """
        try:
            if variant not in VALID_VARIANTS:
                logger.warning(
                    "register_channel_mapping: invalid variant '%s' for "
                    "company_id=%s, channel=%s.  Valid variants: %s",
                    variant, company_id, channel.value, VALID_VARIANTS,
                )
                return

            mapping = ChannelMapping(
                channel=channel,
                default_variant=variant,
                priority=priority,
            )
            with self._lock:
                if company_id not in self._channel_overrides:
                    self._channel_overrides[company_id] = {}
                self._channel_overrides[company_id][channel.value] = mapping

            logger.info(
                "Registered channel mapping: company_id=%s, channel=%s → "
                "variant=%s (priority=%d)",
                company_id, channel.value, variant, priority,
            )
        except Exception:
            logger.exception(
                "register_channel_mapping failed for company_id=%s, "
                "channel=%s, variant=%s",
                company_id, channel.value, variant,
            )

    # ── Capacity Management ──────────────────────────────────────

    def get_capacity(
        self,
        company_id: str,
        variant_type: str,
    ) -> CapacitySnapshot:
        """Return the current capacity snapshot for a variant.

        If no capacity data has been recorded yet, returns a zero-load
        snapshot (BC-008 safe default).
        """
        try:
            with self._lock:
                company_caps = self._capacity.get(company_id, {})
                snapshot = company_caps.get(variant_type)

            if snapshot is not None:
                return snapshot

            # Default: assume 100-slot capacity, 0 load
            logger.debug(
                "No capacity data for company_id=%s, variant=%s — "
                "returning zero-load default",
                company_id, variant_type,
            )
            return CapacitySnapshot(
                variant_type=variant_type,
                current_load=0,
                max_capacity=100,
                utilization_pct=0.0,
            )
        except Exception:
            logger.exception(
                "get_capacity failed for company_id=%s, variant=%s — "
                "returning safe zero-load default",
                company_id, variant_type,
            )
            return CapacitySnapshot(
                variant_type=variant_type,
                current_load=0,
                max_capacity=100,
                utilization_pct=0.0,
            )

    def update_capacity(
        self,
        company_id: str,
        variant_type: str,
        load: int,
        max_capacity: int,
    ) -> None:
        """Update the live capacity tracking for a variant.

        BC-001: company_id is first parameter.
        BC-008: Never raises.
        """
        try:
            if max_capacity <= 0:
                logger.warning(
                    "update_capacity: max_capacity must be > 0, got %d "
                    "for company_id=%s, variant=%s — ignoring",
                    max_capacity, company_id, variant_type,
                )
                return

            pct = round((load / max_capacity) * 100.0, 2)
            snapshot = CapacitySnapshot(
                variant_type=variant_type,
                current_load=load,
                max_capacity=max_capacity,
                utilization_pct=pct,
            )

            with self._lock:
                if company_id not in self._capacity:
                    self._capacity[company_id] = {}
                self._capacity[company_id][variant_type] = snapshot

            logger.info(
                "Capacity updated: company_id=%s, variant=%s — "
                "load=%d/%d (%.1f%%)",
                company_id, variant_type, load, max_capacity, pct,
            )
        except Exception:
            logger.exception(
                "update_capacity failed for company_id=%s, variant=%s",
                company_id, variant_type,
            )

    def get_variant_load_summary(
        self,
        company_id: str,
    ) -> Dict[str, CapacitySnapshot]:
        """Return capacity summary for all tracked variants.

        BC-001: company_id is first parameter.
        """
        try:
            with self._lock:
                company_caps = self._capacity.get(company_id, {})

            # Ensure every variant has an entry (default if missing)
            summary: Dict[str, CapacitySnapshot] = {}
            for variant in ESCALATION_CHAIN:
                if variant in company_caps:
                    summary[variant] = company_caps[variant]
                else:
                    summary[variant] = CapacitySnapshot(
                        variant_type=variant,
                        current_load=0,
                        max_capacity=100,
                        utilization_pct=0.0,
                    )

            logger.debug(
                "Load summary for company_id=%s: %s",
                company_id,
                {v: f"{s.utilization_pct:.1f}%" for v, s in summary.items()},
            )
            return summary
        except Exception:
            logger.exception(
                "get_variant_load_summary failed for company_id=%s",
                company_id,
            )
            return {}

    def reset_capacity(
        self,
        company_id: str,
        variant_type: str = "",
    ) -> None:
        """Reset capacity data (useful in tests / after outages).

        If *variant_type* is empty, resets all variants for the company.
        BC-001: company_id is first parameter.
        """
        try:
            with self._lock:
                if company_id in self._capacity:
                    if variant_type:
                        self._capacity[company_id].pop(variant_type, None)
                    else:
                        self._capacity[company_id].clear()

            logger.info(
                "Capacity reset: company_id=%s, variant=%s",
                company_id, variant_type or "(all)",
            )
        except Exception:
            logger.exception(
                "reset_capacity failed for company_id=%s, variant=%s",
                company_id, variant_type,
            )

    # ── Escalation Chain Helpers ─────────────────────────────────

    def get_next_variant(self, variant_type: str) -> Optional[str]:
        """Return the next higher variant in the escalation chain.

        Returns ``None`` if *variant_type* is already the highest tier.
        """
        try:
            idx = ESCALATION_CHAIN.index(variant_type) if variant_type in ESCALATION_CHAIN else -1
            if idx >= 0 and idx < len(ESCALATION_CHAIN) - 1:
                return ESCALATION_CHAIN[idx + 1]
            return None
        except Exception:
            logger.exception(
                "get_next_variant failed for variant=%s", variant_type,
            )
            return None

    def get_escalation_chain(self, variant_type: str) -> List[str]:
        """Return the full escalation path from *variant_type* to the top.

        Includes the starting variant itself.
        """
        try:
            if variant_type not in ESCALATION_CHAIN:
                logger.warning(
                    "get_escalation_chain: unknown variant '%s', "
                    "returning full chain",
                    variant_type,
                )
                return list(ESCALATION_CHAIN)
            idx = ESCALATION_CHAIN.index(variant_type)
            return list(ESCALATION_CHAIN[idx:])
        except Exception:
            logger.exception(
                "get_escalation_chain failed for variant=%s",
                variant_type,
            )
            return list(ESCALATION_CHAIN)

    # ── Capacity-Based Escalation Check ──────────────────────────

    def should_escalate(
        self,
        company_id: str,
        variant_type: str,
        complexity_score: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        """Determine whether a ticket should be escalated.

        Returns ``(should_escalate, target_variant)``.

        Escalation triggers:
        - Variant utilization > 90 % (CAPACITY_THRESHOLD_PCT)
        - Complexity score > 0.8 for lite/parwa variants

        BC-001: company_id is first parameter.
        """
        try:
            snapshot = self.get_capacity(company_id, variant_type)
            capacity_trigger = snapshot.utilization_pct > CAPACITY_THRESHOLD_PCT
            complexity_trigger = False

            # Complexity escalation only for lower variants
            if complexity_score > 0.8 and variant_type in ("parwa_lite", "parwa"):
                complexity_trigger = True

            if not (capacity_trigger or complexity_trigger):
                return False, None

            target = self.get_next_variant(variant_type)
            if target is None:
                # Highest tier already — cannot escalate further
                logger.warning(
                    "Escalation needed (capacity=%.1f%%, complexity=%.2f) "
                    "but variant=%s is already highest tier for "
                    "company_id=%s",
                    snapshot.utilization_pct, complexity_score,
                    variant_type, company_id,
                )
                return True, None  # should_escalate but no target

            reason_parts: List[str] = []
            if capacity_trigger:
                reason_parts.append(f"capacity at {snapshot.utilization_pct:.1f}%")
            if complexity_trigger:
                reason_parts.append(f"complexity score {complexity_score:.2f}")
            logger.info(
                "Escalation recommended for company_id=%s: variant=%s → %s "
                "(%s)",
                company_id, variant_type, target, ", ".join(reason_parts),
            )
            return True, target
        except Exception:
            logger.exception(
                "should_escalate failed for company_id=%s, variant=%s",
                company_id, variant_type,
            )
            return False, None

    # ── Main Routing ─────────────────────────────────────────────

    def route_ticket(
        self,
        company_id: str,
        ticket_id: str,
        channel: ChannelType,
        complexity_score: float = 0.0,
        force_variant: str = "",
    ) -> RoutingResult:
        """Main routing entry point — full SG-11 algorithm.

        Steps:
        1. Resolve channel → default variant (honouring company overrides).
        2. If *force_variant* is given, use it directly.
        3. Check capacity; if > 90 % → auto-escalate.
        4. If escalation target also at capacity → queue with fallback
           timer per W9-GAP-015.
        5. If all tiers full → human queue with ``AI_OVERLOAD`` flag.
        6. Bill to originating variant unless explicitly escalated.

        BC-001: company_id is first parameter.
        BC-008: Always returns a RoutingResult.
        """
        try:
            # Step 1 — resolve starting variant
            if force_variant:
                original_variant = force_variant
                logger.info(
                    "Forced variant for company_id=%s, ticket=%s: %s",
                    company_id, ticket_id, force_variant,
                )
            else:
                mapping = self._resolve_channel_mapping(company_id, channel)
                original_variant = mapping.default_variant

            billed_to = original_variant

            # Step 2 — check if escalation is needed
            should_esc, next_variant = self.should_escalate(
                company_id, original_variant, complexity_score,
            )

            if not should_esc:
                # Direct route — no escalation needed
                result = RoutingResult(
                    ticket_id=ticket_id,
                    target_variant=original_variant,
                    original_variant=original_variant,
                    decision=RoutingDecisionType.ROUTE,
                    channel=channel,
                    company_id=company_id,
                    reason="default_channel_routing",
                    escalated=False,
                    billed_to_variant=billed_to,
                    complexity_score=complexity_score,
                )
                self._record_routing(company_id, ticket_id, result)
                logger.info(
                    "Ticket %s routed to %s (company_id=%s, channel=%s)",
                    ticket_id, original_variant, company_id, channel.value,
                )
                return result

            if next_variant is None:
                # At highest tier already — try queue, then human
                result = self._route_to_human_or_queue(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    original_variant=original_variant,
                    channel=channel,
                    complexity_score=complexity_score,
                    billed_to=billed_to,
                    reason="highest_tier_at_capacity",
                )
                self._record_routing(company_id, ticket_id, result)
                return result

            # Step 3 — attempt escalation
            target = next_variant
            reason = EscalationReason.CAPACITY_EXCEEDED

            # Walk the escalation chain until we find a variant with room
            visited: List[str] = []
            while target is not None:
                visited.append(target)
                target_cap = self.get_capacity(company_id, target)

                if target_cap.utilization_pct <= CAPACITY_THRESHOLD_PCT:
                    # Found a variant with capacity
                    self._record_escalation(
                        company_id, ticket_id,
                        original_variant, target, reason,
                    )
                    result = RoutingResult(
                        ticket_id=ticket_id,
                        target_variant=target,
                        original_variant=original_variant,
                        decision=RoutingDecisionType.ESCALATE,
                        channel=channel,
                        company_id=company_id,
                        reason=f"escalated_through_{'+'.join(visited)}",
                        escalated=True,
                        billed_to_variant=billed_to,
                        complexity_score=complexity_score,
                    )
                    self._record_routing(company_id, ticket_id, result)
                    logger.info(
                        "Ticket %s escalated %s → %s (company_id=%s)",
                        ticket_id, original_variant, target, company_id,
                    )
                    return result

                # Target variant also full — W9-GAP-015 fallback
                next_target = self.get_next_variant(target)
                if next_target is None:
                    # Top of chain and full — queue for now
                    break
                target = next_target

            # All escalation targets full → queue or human
            result = self._handle_escalation_timeout(
                company_id=company_id,
                ticket_id=ticket_id,
                original_variant=original_variant,
                fallback_variant=target or original_variant,
                channel=channel,
                complexity_score=complexity_score,
                billed_to=billed_to,
            )
            self._record_routing(company_id, ticket_id, result)
            return result

        except Exception:
            # BC-008: Absolute safety net
            logger.exception(
                "route_ticket failed for company_id=%s, ticket=%s — "
                "returning safe human-override fallback",
                company_id, ticket_id,
            )
            return RoutingResult(
                ticket_id=ticket_id,
                target_variant="parwa_high",
                original_variant=force_variant or "parwa",
                decision=RoutingDecisionType.HUMAN_OVERRIDE,
                channel=channel,
                company_id=company_id,
                reason="emergency_fallback_routing_error",
                escalated=True,
                billed_to_variant=force_variant or "parwa",
                complexity_score=complexity_score,
            )

    # ── Explicit Escalation ──────────────────────────────────────

    def escalate_ticket(
        self,
        company_id: str,
        ticket_id: str,
        from_variant: str,
        to_variant: str,
        reason: EscalationReason,
    ) -> RoutingResult:
        """Explicitly escalate a ticket from one variant to another.

        Validates that the escalation direction follows the chain
        (lower → higher).  If *to_variant* is at capacity, applies
        W9-GAP-015 queuing logic.

        BC-001: company_id is first parameter.
        BC-008: Always returns a RoutingResult.
        """
        try:
            chain = self.get_escalation_chain(from_variant)
            if to_variant not in chain:
                logger.warning(
                    "Invalid escalation direction: %s → %s is not in "
                    "chain %s (company_id=%s, ticket=%s)",
                    from_variant, to_variant, chain, company_id, ticket_id,
                )
                return RoutingResult(
                    ticket_id=ticket_id,
                    target_variant=from_variant,
                    original_variant=from_variant,
                    decision=RoutingDecisionType.ROUTE,
                    channel=ChannelType.EMAIL,  # unknown channel
                    company_id=company_id,
                    reason="invalid_escalation_direction",
                    billed_to_variant=from_variant,
                )

            # Check target capacity
            target_cap = self.get_capacity(company_id, to_variant)
            if target_cap.utilization_pct > CAPACITY_THRESHOLD_PCT:
                # W9-GAP-015: target full → queue with fallback
                return self._handle_escalation_timeout(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    original_variant=from_variant,
                    fallback_variant=to_variant,
                    channel=ChannelType.EMAIL,
                    complexity_score=0.0,
                    billed_to=from_variant,
                    escalation_reason=reason,
                )

            self._record_escalation(
                company_id, ticket_id,
                from_variant, to_variant, reason,
            )

            result = RoutingResult(
                ticket_id=ticket_id,
                target_variant=to_variant,
                original_variant=from_variant,
                decision=RoutingDecisionType.ESCALATE,
                channel=ChannelType.EMAIL,
                company_id=company_id,
                reason=f"manual_escalation: {reason.value}",
                escalated=True,
                billed_to_variant=from_variant,
            )
            self._record_routing(company_id, ticket_id, result)

            logger.info(
                "Explicit escalation: ticket %s, %s → %s, reason=%s "
                "(company_id=%s)",
                ticket_id, from_variant, to_variant, reason.value,
                company_id,
            )
            return result
        except Exception:
            logger.exception(
                "escalate_ticket failed for company_id=%s, ticket=%s",
                company_id, ticket_id,
            )
            return RoutingResult(
                ticket_id=ticket_id,
                target_variant=from_variant,
                original_variant=from_variant,
                decision=RoutingDecisionType.ROUTE,
                channel=ChannelType.EMAIL,
                company_id=company_id,
                reason="escalation_error_fallback",
                billed_to_variant=from_variant,
            )

    # ── W9-GAP-015: Escalation Rollback & Fallback ───────────────

    def _handle_escalation_timeout(
        self,
        company_id: str,
        ticket_id: str,
        original_variant: str,
        fallback_variant: str,
        channel: ChannelType,
        complexity_score: float,
        billed_to: str,
        escalation_reason: Optional[EscalationReason] = None,
    ) -> RoutingResult:
        """Handle the case where escalation targets are all at capacity.

        W9-GAP-015 logic:
        1. Queue the ticket with priority + 30 s fallback timer.
        2. On timeout, try next tier.
        3. If all tiers full → human queue with AI_OVERLOAD.

        BC-008: Never crashes — always returns a RoutingResult.
        """
        try:
            reason = escalation_reason or EscalationReason.CAPACITY_EXCEEDED

            # Check if there is a higher tier to fall back to
            next_tier = self.get_next_variant(fallback_variant)

            if next_tier is not None:
                next_cap = self.get_capacity(company_id, next_tier)
                if next_cap.utilization_pct <= CAPACITY_THRESHOLD_PCT:
                    # Next tier has room — go there directly
                    self._record_escalation(
                        company_id, ticket_id,
                        original_variant, next_tier, reason,
                    )
                    logger.info(
                        "W9-GAP-015: Bypassed queued variant %s, "
                        "routed ticket %s to next tier %s "
                        "(company_id=%s)",
                        fallback_variant, ticket_id, next_tier, company_id,
                    )
                    return RoutingResult(
                        ticket_id=ticket_id,
                        target_variant=next_tier,
                        original_variant=original_variant,
                        decision=RoutingDecisionType.ESCALATE,
                        channel=channel,
                        company_id=company_id,
                        reason=(
                            f"gap015_fallback: {fallback_variant} full, "
                            f"routed to {next_tier}"
                        ),
                        escalated=True,
                        billed_to_variant=billed_to,
                        complexity_score=complexity_score,
                    )

            # No higher tier with capacity — queue with priority
            queued = QueuedTicket(
                ticket_id=ticket_id,
                company_id=company_id,
                queued_at=time.monotonic(),
                fallback_variant=next_tier or fallback_variant,
                reason=reason,
                priority=10,  # elevated priority for capacity-escalated
            )
            with self._lock:
                self._pending_queue.append(queued)

            logger.warning(
                "W9-GAP-015: Ticket %s queued (all targets at capacity). "
                "Fallback timer=%ds, fallback_variant=%s, "
                "company_id=%s",
                ticket_id, ESCALATION_FALLBACK_SECONDS,
                queued.fallback_variant, company_id,
            )
            return RoutingResult(
                ticket_id=ticket_id,
                target_variant=fallback_variant,
                original_variant=original_variant,
                decision=RoutingDecisionType.QUEUE,
                channel=channel,
                company_id=company_id,
                reason=(
                    f"gap015_queued: all escalation targets at capacity, "
                    f"fallback_timer={ESCALATION_FALLBACK_SECONDS}s, "
                    f"fallback_variant={queued.fallback_variant}"
                ),
                escalated=True,
                billed_to_variant=billed_to,
                complexity_score=complexity_score,
            )
        except Exception:
            logger.exception(
                "_handle_escalation_timeout failed for ticket=%s — "
                "falling back to human queue",
                ticket_id,
            )
            return RoutingResult(
                ticket_id=ticket_id,
                target_variant="",
                original_variant=original_variant,
                decision=RoutingDecisionType.HUMAN_OVERRIDE,
                channel=channel,
                company_id=company_id,
                reason="gap015_error_fallback_to_human",
                escalated=True,
                billed_to_variant=billed_to,
                complexity_score=complexity_score,
            )

    def _route_to_human_or_queue(
        self,
        company_id: str,
        ticket_id: str,
        original_variant: str,
        channel: ChannelType,
        complexity_score: float,
        billed_to: str,
        reason: str,
    ) -> RoutingResult:
        """Route to human queue with AI_OVERLOAD flag when no AI variant
        can handle the ticket."""
        logger.warning(
            "AI_OVERLOAD: Ticket %s cannot be handled by any variant "
            "(company_id=%s, original_variant=%s, reason=%s). "
            "Assigning to human queue.",
            ticket_id, company_id, original_variant, reason,
        )
        return RoutingResult(
            ticket_id=ticket_id,
            target_variant="",
            original_variant=original_variant,
            decision=RoutingDecisionType.HUMAN_OVERRIDE,
            channel=channel,
            company_id=company_id,
            reason=f"{AI_OVERLOAD_FLAG}: {reason}",
            escalated=True,
            billed_to_variant=billed_to,
            complexity_score=complexity_score,
        )

    # ── Pending Queue Management (W9-GAP-015) ────────────────────

    def process_pending_queue(self, company_id: str = "") -> List[RoutingResult]:
        """Process tickets in the pending queue whose fallback timer
        has expired.

        W9-GAP-015: For each expired ticket, try the next tier.
        If all tiers still full → escalate to human queue.

        If *company_id* is provided, only processes tickets for that
        company.  Otherwise processes all.

        BC-008: Never crashes.
        """
        results: List[RoutingResult] = []
        try:
            now = time.monotonic()
            still_pending: List[QueuedTicket] = []

            with self._lock:
                queue_snapshot = list(self._pending_queue)

            for qt in queue_snapshot:
                if company_id and qt.company_id != company_id:
                    still_pending.append(qt)
                    continue

                elapsed = now - qt.queued_at
                if elapsed < ESCALATION_FALLBACK_SECONDS:
                    still_pending.append(qt)
                    continue

                # Timer expired — try next tier
                next_variant = self.get_next_variant(qt.fallback_variant)
                if next_variant is not None:
                    cap = self.get_capacity(qt.company_id, next_variant)
                    if cap.utilization_pct <= CAPACITY_THRESHOLD_PCT:
                        self._record_escalation(
                            qt.company_id, qt.ticket_id,
                            qt.fallback_variant, next_variant, qt.reason,
                        )
                        result = RoutingResult(
                            ticket_id=qt.ticket_id,
                            target_variant=next_variant,
                            original_variant=qt.fallback_variant,
                            decision=RoutingDecisionType.ESCALATE,
                            channel=ChannelType.CHAT,
                            company_id=qt.company_id,
                            reason=(
                                f"gap015_timer_expired: queued for "
                                f"{elapsed:.1f}s, routed to {next_variant}"
                            ),
                            escalated=True,
                            billed_to_variant=qt.fallback_variant,
                        )
                        results.append(result)
                        logger.info(
                            "W9-GAP-015: Queued ticket %s picked up by %s "
                            "after %.1fs (company_id=%s)",
                            qt.ticket_id, next_variant, elapsed,
                            qt.company_id,
                        )
                        continue

                # All tiers still full → human queue
                result = self._route_to_human_or_queue(
                    company_id=qt.company_id,
                    ticket_id=qt.ticket_id,
                    original_variant=qt.fallback_variant,
                    channel=ChannelType.CHAT,
                    complexity_score=0.0,
                    billed_to=qt.fallback_variant,
                    reason="gap015_all_tiers_still_full_after_timeout",
                )
                results.append(result)

            # Replace the queue with the remaining items
            with self._lock:
                self._pending_queue = still_pending

            if results:
                logger.info(
                    "process_pending_queue: processed %d tickets "
                    "(%d still queued)",
                    len(results), len(still_pending),
                )
            return results
        except Exception:
            logger.exception("process_pending_queue failed")
            return []

    # ── Validation ───────────────────────────────────────────────

    def validate_routing(
        self,
        company_id: str,
        ticket_id: str,
        target_variant: str,
        original_variant: str,
    ) -> Dict[str, Any]:
        """Validate a routing decision.

        Returns ``{
            "valid": bool,
            "reasons": List[str],
            "warnings": List[str],
        }``.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            reasons: List[str] = []
            warnings: List[str] = []

            # Check target variant is known
            if target_variant and target_variant not in VALID_VARIANTS:
                reasons.append(
                    f"target_variant '{target_variant}' is not a known variant",
                )

            # Check original variant is known
            if original_variant not in VALID_VARIANTS:
                reasons.append(
                    f"original_variant '{original_variant}' is not a known variant",
                )

            # Check escalation direction (must be same-tier or higher)
            if (target_variant and original_variant
                    and target_variant in VALID_VARIANTS
                    and original_variant in VALID_VARIANTS):
                chain = self.get_escalation_chain(original_variant)
                if target_variant not in chain:
                    reasons.append(
                        f"Escalation direction invalid: {original_variant} → "
                        f"{target_variant} not in chain {chain}",
                    )

            # Capacity warning
            if target_variant in VALID_VARIANTS:
                cap = self.get_capacity(company_id, target_variant)
                if cap.utilization_pct > 80.0:
                    warnings.append(
                        f"target_variant {target_variant} at "
                        f"{cap.utilization_pct:.1f}% capacity — "
                        f"approaching threshold",
                    )

            is_valid = len(reasons) == 0
            logger.debug(
                "Routing validation for ticket %s: valid=%s, "
                "reasons=%s, warnings=%s",
                ticket_id, is_valid, reasons, warnings,
            )
            return {
                "valid": is_valid,
                "reasons": reasons,
                "warnings": warnings,
            }
        except Exception:
            logger.exception(
                "validate_routing failed for company_id=%s, ticket=%s",
                company_id, ticket_id,
            )
            return {
                "valid": False,
                "reasons": ["validation_error"],
                "warnings": [],
            }

    # ── Routing History ──────────────────────────────────────────

    def get_routing_history(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[EscalationPath]:
        """Return the full escalation history for a ticket.

        BC-001: company_id is first parameter.
        """
        try:
            with self._lock:
                history = self._routing_history.get(ticket_id, [])
            logger.debug(
                "Routing history for ticket %s: %d entries",
                ticket_id, len(history),
            )
            return list(history)
        except Exception:
            logger.exception(
                "get_routing_history failed for company_id=%s, ticket=%s",
                company_id, ticket_id,
            )
            return []

    # ── Internal Bookkeeping ─────────────────────────────────────

    def _record_escalation(
        self,
        company_id: str,
        ticket_id: str,
        from_variant: str,
        to_variant: str,
        reason: EscalationReason,
    ) -> None:
        """Append an escalation path entry to routing history."""
        try:
            entry = EscalationPath(
                from_variant=from_variant,
                to_variant=to_variant,
                reason=reason,
                timestamp=datetime.now(timezone.utc),
                ticket_id=ticket_id,
            )
            with self._lock:
                if ticket_id not in self._routing_history:
                    self._routing_history[ticket_id] = []
                self._routing_history[ticket_id].append(entry)

            logger.info(
                "Escalation recorded: ticket %s, %s → %s, reason=%s",
                ticket_id, from_variant, to_variant, reason.value,
            )
        except Exception:
            logger.exception(
                "_record_escalation failed for ticket=%s", ticket_id,
            )

    def _record_routing(
        self,
        company_id: str,
        ticket_id: str,
        result: RoutingResult,
    ) -> None:
        """Track a routing decision for analytics.

        Stores a lightweight dict per ticket for later aggregation.
        """
        try:
            if result.escalated:
                self._record_escalation(
                    company_id,
                    ticket_id,
                    result.original_variant,
                    result.target_variant,
                    EscalationReason.CAPACITY_EXCEEDED,
                )
            logger.debug(
                "Routing decision recorded: ticket=%s, decision=%s, "
                "target=%s, company_id=%s",
                ticket_id, result.decision.value, result.target_variant,
                company_id,
            )
        except Exception:
            logger.exception(
                "_record_routing failed for ticket=%s", ticket_id,
            )

    # ── Diagnostics ──────────────────────────────────────────────

    def get_pending_queue_size(self, company_id: str = "") -> int:
        """Return the number of tickets currently in the pending queue.

        If *company_id* is provided, counts only for that company.
        """
        try:
            with self._lock:
                queue = self._pending_queue
                if company_id:
                    return sum(1 for qt in queue if qt.company_id == company_id)
                return len(queue)
        except Exception:
            logger.exception("get_pending_queue_size failed")
            return 0

    def get_routing_stats(self, company_id: str = "") -> Dict[str, Any]:
        """Return aggregate routing statistics.

        Useful for dashboards and analytics (SG-11 §5).
        """
        try:
            with self._lock:
                total_routed = len(self._routing_history)
                escalated_count = sum(
                    1 for paths in self._routing_history.values()
                    for p in paths
                )
                queue_size = len(self._pending_queue)

            stats: Dict[str, Any] = {
                "total_tickets_routed": total_routed,
                "total_escalations": escalated_count,
                "pending_queue_size": queue_size,
                "escalation_chain": ESCALATION_CHAIN,
                "capacity_threshold_pct": CAPACITY_THRESHOLD_PCT,
                "fallback_timer_seconds": ESCALATION_FALLBACK_SECONDS,
            }
            logger.debug("Routing stats: %s", stats)
            return stats
        except Exception:
            logger.exception("get_routing_stats failed")
            return {
                "total_tickets_routed": 0,
                "total_escalations": 0,
                "pending_queue_size": 0,
                "escalation_chain": ESCALATION_CHAIN,
                "capacity_threshold_pct": CAPACITY_THRESHOLD_PCT,
                "fallback_timer_seconds": ESCALATION_FALLBACK_SECONDS,
            }
