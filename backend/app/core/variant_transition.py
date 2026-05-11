"""
SG-08 + SG-09: Variant Transition Handler (Week 10 Day 4)

SG-08 — Variant Upgrade Mid-Ticket: Seamless Capability Transition
SG-09 — Variant Downgrade: Graceful Degradation

Handles plan changes while tickets are in-flight. Ensures
seamless capability transitions without data loss or
interrupted conversations.

Key behaviours:
  Upgrade (SG-08):
    1. Complete current turn with old variant capabilities
    2. On next turn, activate new variant's features
    3. Do NOT retroactively re-process
    4. Log transition point
    5. Update technique tier access immediately

  Downgrade (SG-09):
    1. Immediately restrict to lower variant's technique tier
    2. In-flight tickets complete with old capabilities (current turn only)
    3. Disable higher-tier features on next turn
    4. Show deactivation notice in admin panel
    5. Cache cleared for restricted features

Building Codes: BC-002, BC-001, BC-008, BC-009
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger(__name__)


# ── Constants ──────────────────────────────────────────────────────

VALID_VARIANT_TYPES: List[str] = [
    "mini_parwa",
    "parwa",
    "parwa_high",
]

VARIANT_RANKING: Dict[str, int] = {
    "mini_parwa": 1,
    "parwa": 2,
    "parwa_high": 3,
}

# All 14 reasoning techniques across three tiers
_TIER_1_TECHNIQUES: List[str] = [
    "clara",
    "crp",
    "gsd",
]

_TIER_2_TECHNIQUES: List[str] = [
    "chain_of_thought",
    "reverse_thinking",
    "react",
    "step_back",
    "thread_of_thought",
]

_TIER_3_TECHNIQUES: List[str] = [
    "gst",
    "universe_of_thoughts",
    "tree_of_thoughts",
    "self_consistency",
    "reflexion",
    "least_to_most",
]

# Feature names that can be enabled/disabled per variant
_ALL_KNOWN_FEATURES: List[str] = [
    "basic_classification",
    "sentiment_analysis",
    "context_compression",
    "technique_boosting",
    "chain_of_thought_reasoning",
    "reverse_thinking",
    "react_tool_use",
    "step_back_analysis",
    "thread_of_thought",
    "advanced_reasoning",
    "tree_of_thoughts",
    "self_consistency_check",
    "reflexion_cycles",
    "least_to_most_decomposition",
    "gst_general_skills",
    "universe_of_thoughts",
    "multi_model_routing",
    "heavy_model_access",
    "conversation_summarization",
    "brand_voice_training",
    "custom_model_fine_tuning",
    "priority_queue_access",
    "dedicated_ai_agents",
]


# ── Enums ──────────────────────────────────────────────────────────


class TransitionType(str, Enum):
    """Type of variant transition being performed."""

    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class TransitionStatus(str, Enum):
    """Lifecycle status of a variant transition."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


# ── Data Structures ────────────────────────────────────────────────


@dataclass
class VariantCapabilities:
    """Full capability profile for a specific variant type.

    Defines the technique tiers, smart router access, confidence
    thresholds, agent limits, and feature flags available to
    each PARWA variant.
    """

    variant_type: str
    max_tier: int  # 1, 2, or 3
    allowed_techniques: List[str] = field(default_factory=list)
    smart_router_tiers: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.95
    max_agents: int = 1
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise capabilities to a plain dict for persistence."""
        return {
            "variant_type": self.variant_type,
            "max_tier": self.max_tier,
            "allowed_techniques": list(self.allowed_techniques),
            "smart_router_tiers": list(self.smart_router_tiers),
            "confidence_threshold": self.confidence_threshold,
            "max_agents": self.max_agents,
            "features": list(self.features),
        }


@dataclass
class InFlightTicket:
    """Tracks a ticket that is currently being processed by the AI agent.

    Captures the variant context at creation time and tracks any
    pending transitions so that the correct capabilities are applied
    on a per-turn basis.
    """

    ticket_id: str
    company_id: str
    current_variant: str  # variant at time of ticket creation
    effective_variant: str  # variant currently in effect
    turn_count: int = 0
    created_at: float = 0.0
    last_turn_at: float = 0.0
    transition_pending: bool = False
    pending_variant: Optional[str] = None
    uses_old_capabilities: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise ticket tracking state to a plain dict."""
        return {
            "ticket_id": self.ticket_id,
            "company_id": self.company_id,
            "current_variant": self.current_variant,
            "effective_variant": self.effective_variant,
            "turn_count": self.turn_count,
            "created_at": self.created_at,
            "last_turn_at": self.last_turn_at,
            "transition_pending": self.transition_pending,
            "pending_variant": self.pending_variant,
            "uses_old_capabilities": self.uses_old_capabilities,
            "metadata": dict(self.metadata),
        }


@dataclass
class TransitionRecord:
    """Audit record for a variant upgrade or downgrade event.

    Captures the full context of what changed, which tickets were
    affected, and the outcome of the transition process.
    """

    transition_id: str
    company_id: str
    transition_type: TransitionType
    from_variant: str
    to_variant: str
    timestamp: str  # ISO-8601 UTC
    in_flight_tickets_affected: int = 0
    status: TransitionStatus = TransitionStatus.ACTIVE
    cache_cleared: bool = False
    deactivation_notice_sent: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise transition record to a plain dict."""
        return {
            "transition_id": self.transition_id,
            "company_id": self.company_id,
            "transition_type": self.transition_type.value,
            "from_variant": self.from_variant,
            "to_variant": self.to_variant,
            "timestamp": self.timestamp,
            "in_flight_tickets_affected": self.in_flight_tickets_affected,
            "status": self.status.value,
            "cache_cleared": self.cache_cleared,
            "deactivation_notice_sent": self.deactivation_notice_sent,
            "details": dict(self.details),
        }


@dataclass
class DeactivationNotice:
    """Notification shown in the admin panel when features are disabled.

    Lists which features will no longer be available after a downgrade
    and prompts the admin to acknowledge the change.
    """

    company_id: str
    variant_from: str
    variant_to: str
    restricted_features: List[str] = field(default_factory=list)
    message: str = ""
    timestamp: str = ""  # ISO-8601 UTC
    acknowledged: bool = False
    notice_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise deactivation notice to a plain dict."""
        return {
            "notice_id": self.notice_id,
            "company_id": self.company_id,
            "variant_from": self.variant_from,
            "variant_to": self.variant_to,
            "restricted_features": list(self.restricted_features),
            "message": self.message,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


# ── Variant Transition Handler ─────────────────────────────────────


class VariantTransitionHandler:
    """Handles seamless variant transitions while tickets are in-flight.

    SG-08 (Upgrade Mid-Ticket):
      - Complete current turn with old variant capabilities.
      - On next turn, activate new variant's features.
      - Do NOT retroactively re-process.
      - Log transition point.
      - Update technique tier access immediately.

    SG-09 (Downgrade):
      - Immediately restrict to lower variant's technique tier.
      - In-flight tickets complete with old capabilities (current turn only).
      - Disable higher-tier features on next turn.
      - Show deactivation notice in admin panel.
      - Cache cleared for restricted features.

    Thread-safety: All mutable state is protected by ``_lock`` (RLock).
    In production, replace in-memory stores with Redis for multi-worker
    consistency.

    BC-001: company_id is always the first parameter on public methods.
    BC-008: Every public method wrapped in try/except — never crash.
    BC-012: All timestamps are UTC.
    """

    def __init__(self) -> None:
        """Initialize the handler with variant capabilities, registries, and locks.

        Pre-defines capability maps for all three variant types
        (mini_parwa, parwa, parwa_high) and initializes empty
        in-memory registries for tickets, transitions, and notices.
        """
        # Thread-safe lock for all mutable state
        self._lock = threading.RLock()

        # Variant capability definitions (built once, read-only after init)
        self._capabilities: Dict[str, VariantCapabilities] = {}
        self._build_variant_capabilities()

        # In-flight ticket registry: {ticket_id: InFlightTicket}
        self._ticket_registry: Dict[str, InFlightTicket] = {}

        # Company → ticket ids index for fast lookups
        self._company_tickets: Dict[str, List[str]] = {}

        # Transition history: {transition_id: TransitionRecord}
        self._transition_history: Dict[str, TransitionRecord] = {}

        # Company → transition ids index
        self._company_transitions: Dict[str, List[str]] = {}

        # Sticky variant mapping — tracks the effective company-level
        # variant so new tickets inherit the correct variant after
        # a transition is completed.
        self._company_effective_variant: Dict[str, str] = {}

        # Deactivation notices: {notice_id: DeactivationNotice}
        self._deactivation_notices: Dict[str, DeactivationNotice] = {}

        # Company → notice ids index
        self._company_notices: Dict[str, List[str]] = {}

        # Simulated cache entries for restricted-feature clearing.
        # Keys are "company_id:feature_name", values are timestamps.
        self._feature_cache: Dict[str, float] = {}

        logger.info(
            "VariantTransitionHandler initialised with %d variant types: %s",
            len(self._capabilities),
            list(self._capabilities.keys()),
        )

    # ── Variant Capabilities Builder ───────────────────────────────

    def _build_variant_capabilities(self) -> None:
        """Build capability profiles for all three variant types.

        Each variant has a distinct max tier, technique set, smart
        router access, confidence threshold, agent limit, and
        feature flag list.
        """
        # mini_parwa: Tier 1 only — Starter tier
        mini_parwa_features: List[str] = [
            "basic_classification",
            "sentiment_analysis",
            "context_compression",
            "technique_boosting",
        ]
        self._capabilities["mini_parwa"] = VariantCapabilities(
            variant_type="mini_parwa",
            max_tier=1,
            allowed_techniques=list(_TIER_1_TECHNIQUES),
            smart_router_tiers=["light"],
            confidence_threshold=0.95,
            max_agents=1,
            features=list(mini_parwa_features),
        )

        # parwa: Tier 1 + Tier 2 — Growth tier
        parwa_features: List[str] = [
            "basic_classification",
            "sentiment_analysis",
            "context_compression",
            "technique_boosting",
            "chain_of_thought_reasoning",
            "reverse_thinking",
            "react_tool_use",
            "step_back_analysis",
            "thread_of_thought",
            "multi_model_routing",
            "conversation_summarization",
            "brand_voice_training",
        ]
        self._capabilities["parwa"] = VariantCapabilities(
            variant_type="parwa",
            max_tier=2,
            allowed_techniques=list(_TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES),
            smart_router_tiers=["light", "medium"],
            confidence_threshold=0.85,
            max_agents=3,
            features=list(parwa_features),
        )

        # parwa_high: Tier 1 + Tier 2 + Tier 3 — High tier (all 14 techniques)
        parwa_high_features: List[str] = [
            "basic_classification",
            "sentiment_analysis",
            "context_compression",
            "technique_boosting",
            "chain_of_thought_reasoning",
            "reverse_thinking",
            "react_tool_use",
            "step_back_analysis",
            "thread_of_thought",
            "advanced_reasoning",
            "tree_of_thoughts",
            "self_consistency_check",
            "reflexion_cycles",
            "least_to_most_decomposition",
            "gst_general_skills",
            "universe_of_thoughts",
            "multi_model_routing",
            "heavy_model_access",
            "conversation_summarization",
            "brand_voice_training",
            "custom_model_fine_tuning",
            "priority_queue_access",
            "dedicated_ai_agents",
        ]
        self._capabilities["parwa_high"] = VariantCapabilities(
            variant_type="parwa_high",
            max_tier=3,
            allowed_techniques=list(
                _TIER_1_TECHNIQUES + _TIER_2_TECHNIQUES + _TIER_3_TECHNIQUES
            ),
            smart_router_tiers=["light", "medium", "heavy"],
            confidence_threshold=0.75,
            max_agents=5,
            features=list(parwa_high_features),
        )

    # ── Timestamp Helper ───────────────────────────────────────────

    @staticmethod
    def _utc_now_iso() -> str:
        """Return the current UTC time as an ISO-8601 string (BC-012)."""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _utc_now_timestamp() -> float:
        """Return the current UTC time as a Unix timestamp."""
        return time.time()

    # ── Ticket Registration ────────────────────────────────────────

    def register_ticket(
        self,
        company_id: str,
        ticket_id: str,
        variant_type: str,
    ) -> InFlightTicket:
        """Register a new in-flight ticket with its current variant.

        If a transition is already active for the company, the ticket
        is registered with the effective (target) variant so new
        tickets immediately benefit from the change.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a valid InFlightTicket.
        """
        try:
            now = self._utc_now_timestamp()

            # Resolve effective variant: if a transition has set a new
            # effective variant for the company, use that for new tickets
            effective = self._resolve_effective_variant(company_id, variant_type)

            ticket = InFlightTicket(
                ticket_id=ticket_id,
                company_id=company_id,
                current_variant=variant_type,
                effective_variant=effective,
                turn_count=0,
                created_at=now,
                last_turn_at=now,
                transition_pending=False,
                pending_variant=None,
                uses_old_capabilities=False,
                metadata={
                    "registered_at": self._utc_now_iso(),
                    "original_variant": variant_type,
                    "effective_on_registration": effective,
                },
            )

            with self._lock:
                self._ticket_registry[ticket_id] = ticket
                if company_id not in self._company_tickets:
                    self._company_tickets[company_id] = []
                self._company_tickets[company_id].append(ticket_id)

            logger.info(
                "Ticket registered: ticket_id=%s, company_id=%s, "
                "variant=%s, effective=%s",
                ticket_id, company_id, variant_type, effective,
            )
            return ticket

        except Exception:
            logger.exception(
                "register_ticket failed for company_id=%s, ticket_id=%s — "
                "returning safe fallback ticket",
                company_id, ticket_id,
            )
            # BC-008: Return a safe fallback ticket
            now = self._utc_now_timestamp()
            fallback = InFlightTicket(
                ticket_id=ticket_id,
                company_id=company_id,
                current_variant=variant_type or "mini_parwa",
                effective_variant=variant_type or "mini_parwa",
                turn_count=0,
                created_at=now,
                last_turn_at=now,
                metadata={"registration_error": True},
            )
            return fallback

    def unregister_ticket(
        self,
        company_id: str,
        ticket_id: str,
    ) -> bool:
        """Remove a ticket from in-flight tracking.

        Called when a ticket is closed, resolved, or otherwise no
        longer being actively processed by the AI agent.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns False on error.
        """
        try:
            with self._lock:
                removed = self._ticket_registry.pop(ticket_id, None)
                if removed is None:
                    logger.debug(
                        "unregister_ticket: ticket_id=%s not found "
                        "(already removed or never registered)",
                        ticket_id,
                    )
                    return False

                # Remove from company index
                company_ids = self._company_tickets.get(company_id, [])
                if ticket_id in company_ids:
                    company_ids.remove(ticket_id)

            logger.info(
                "Ticket unregistered: ticket_id=%s, company_id=%s, "
                "variant=%s, turns=%d",
                ticket_id, company_id,
                removed.effective_variant, removed.turn_count,
            )
            return True

        except Exception:
            logger.exception(
                "unregister_ticket failed for company_id=%s, ticket_id=%s",
                company_id, ticket_id,
            )
            return False

    def get_ticket(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[InFlightTicket]:
        """Retrieve the current state of an in-flight ticket.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns None on error.
        """
        try:
            with self._lock:
                ticket = self._ticket_registry.get(ticket_id)
                if ticket is not None and ticket.company_id != company_id:
                    logger.warning(
                        "get_ticket: ticket_id=%s belongs to company_id=%s, "
                        "not requested company_id=%s",
                        ticket_id, ticket.company_id, company_id,
                    )
                    return None
                return ticket

        except Exception:
            logger.exception(
                "get_ticket failed for company_id=%s, ticket_id=%s",
                company_id, ticket_id,
            )
            return None

    def get_in_flight_tickets(
        self,
        company_id: str,
    ) -> List[InFlightTicket]:
        """List all tracked in-flight tickets for a company.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            with self._lock:
                ticket_ids = self._company_tickets.get(company_id, [])
                tickets: List[InFlightTicket] = []
                for tid in ticket_ids:
                    ticket = self._ticket_registry.get(tid)
                    if ticket is not None:
                        tickets.append(ticket)
                return tickets

        except Exception:
            logger.exception(
                "get_in_flight_tickets failed for company_id=%s",
                company_id,
            )
            return []

    # ── Effective Variant Resolution ───────────────────────────────

    def _resolve_effective_variant(
        self,
        company_id: str,
        default_variant: str,
    ) -> str:
        """Resolve the effective variant for a company.

        If a recent transition has set a sticky effective variant
        for the company, return that. Otherwise fall back to the
        default_variant provided.

        Must be called while holding ``_lock``.
        """
        effective = self._company_effective_variant.get(company_id)
        if effective is not None:
            return effective
        return default_variant

    # ── Upgrade (SG-08) ────────────────────────────────────────────

    def initiate_upgrade(
        self,
        company_id: str,
        from_variant: str,
        to_variant: str,
        reason: str = "",
    ) -> TransitionRecord:
        """Start the upgrade process for a company (SG-08).

        Steps:
          1. Validate that the transition direction is an upgrade
             (to_variant has higher rank than from_variant).
          2. Create a transition record with ACTIVE status.
          3. Mark all in-flight tickets with ``transition_pending=True``
             and ``pending_variant=to_variant``. Set
             ``uses_old_capabilities=True`` so the current turn
             completes with old capabilities.
          4. Log the transition point.
          5. Return the transition record.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — always returns a TransitionRecord.
        """
        try:
            # Validate transition direction
            is_valid, validation_msg = self.validate_transition(
                from_variant, to_variant,
            )
            if not is_valid:
                logger.warning(
                    "initiate_upgrade: invalid transition for company_id=%s: "
                    "%s → %s (%s)",
                    company_id, from_variant, to_variant, validation_msg,
                )
                return self._create_error_transition_record(
                    company_id=company_id,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    reason=validation_msg,
                )

            # Verify it's actually an upgrade
            from_rank = VARIANT_RANKING.get(from_variant, 0)
            to_rank = VARIANT_RANKING.get(to_variant, 0)
            if to_rank <= from_rank:
                logger.warning(
                    "initiate_upgrade: not an upgrade (rank %d → %d) "
                    "for company_id=%s",
                    from_rank, to_rank, company_id,
                )
                return self._create_error_transition_record(
                    company_id=company_id,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    reason=(
                        f"Not an upgrade: {from_variant} (rank {from_rank}) "
                        f"→ {to_variant} (rank {to_rank})"
                    ),
                )

            transition_id = f"tr_{uuid.uuid4().hex[:12]}"
            now_iso = self._utc_now_iso()

            # Mark all in-flight tickets for the company
            affected_count = 0
            with self._lock:
                ticket_ids = self._company_tickets.get(company_id, [])
                for tid in ticket_ids:
                    ticket = self._ticket_registry.get(tid)
                    if ticket is not None and not ticket.transition_pending:
                        ticket.transition_pending = True
                        ticket.pending_variant = to_variant
                        ticket.uses_old_capabilities = True
                        affected_count += 1
                        logger.info(
                            "Upgrade: marked ticket %s for transition "
                            "(uses_old_capabilities=True)",
                            tid,
                        )

                # Create transition record
                record = TransitionRecord(
                    transition_id=transition_id,
                    company_id=company_id,
                    transition_type=TransitionType.UPGRADE,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    timestamp=now_iso,
                    in_flight_tickets_affected=affected_count,
                    status=TransitionStatus.ACTIVE,
                    cache_cleared=False,
                    deactivation_notice_sent=False,
                    details={
                        "reason": reason,
                        "from_rank": from_rank,
                        "to_rank": to_rank,
                        "affected_ticket_ids": list(ticket_ids),
                    },
                )

                # Store in history
                self._transition_history[transition_id] = record
                if company_id not in self._company_transitions:
                    self._company_transitions[company_id] = []
                self._company_transitions[company_id].append(transition_id)

            logger.info(
                "Upgrade initiated: company_id=%s, %s → %s, "
                "transition_id=%s, tickets_affected=%d, reason='%s'",
                company_id, from_variant, to_variant,
                transition_id, affected_count, reason,
            )
            return record

        except Exception:
            logger.exception(
                "initiate_upgrade failed for company_id=%s, "
                "%s → %s — returning error record",
                company_id, from_variant, to_variant,
            )
            return self._create_error_transition_record(
                company_id=company_id,
                from_variant=from_variant,
                to_variant=to_variant,
                reason="internal_error_in_initiate_upgrade",
            )

    def on_turn_start(
        self,
        company_id: str,
        ticket_id: str,
    ) -> str:
        """Called at the start of each turn to determine effective variant.

        SG-08 logic:
          - If the ticket has a pending upgrade and
            ``uses_old_capabilities`` is True, this means the previous
            turn was still using old capabilities.  We now switch to
            the new variant's capabilities:
              * Set ``effective_variant = pending_variant``
              * Set ``uses_old_capabilities = False``
              * Set ``transition_pending = False``
          - Return the effective variant name for this turn.

        SG-09 logic:
          - If the ticket has a pending downgrade and
            ``uses_old_capabilities`` is True, the current turn is
            still using old capabilities.  After the first turn
            completes (see ``on_turn_complete``), the next call will
            switch to the lower variant.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — always returns a valid variant name.
        """
        try:
            with self._lock:
                ticket = self._ticket_registry.get(ticket_id)
                if ticket is None:
                    logger.warning(
                        "on_turn_start: ticket_id=%s not found "
                        "for company_id=%s — returning mini_parwa fallback",
                        ticket_id, company_id,
                    )
                    return "mini_parwa"

                if ticket.company_id != company_id:
                    logger.warning(
                        "on_turn_start: ticket_id=%s belongs to %s, "
                        "not %s — returning mini_parwa fallback",
                        ticket_id, ticket.company_id, company_id,
                    )
                    return "mini_parwa"

                # Increment turn count
                ticket.turn_count += 1
                ticket.last_turn_at = self._utc_now_timestamp()

                # Check if transition should be applied now
                if ticket.transition_pending and ticket.pending_variant:
                    if ticket.uses_old_capabilities:
                        # Previous turn completed with old capabilities.
                        # Now activate the new variant for this turn.
                        old_variant = ticket.effective_variant
                        new_variant = ticket.pending_variant
                        ticket.effective_variant = new_variant
                        ticket.uses_old_capabilities = False
                        ticket.transition_pending = False

                        logger.info(
                            "Turn %d: Transition applied for ticket %s — "
                            "%s → %s (company_id=%s)",
                            ticket.turn_count, ticket_id,
                            old_variant, new_variant, company_id,
                        )
                    else:
                        # uses_old_capabilities is False but still pending.
                        # This shouldn't normally happen, but handle it
                        # gracefully by applying the transition immediately.
                        logger.warning(
                            "on_turn_start: ticket %s has transition_pending "
                            "but uses_old_capabilities=False — applying "
                            "immediately (company_id=%s)",
                            ticket_id, company_id,
                        )
                        ticket.effective_variant = ticket.pending_variant
                        ticket.transition_pending = False
                        ticket.pending_variant = None

                return ticket.effective_variant

        except Exception:
            logger.exception(
                "on_turn_start failed for company_id=%s, ticket_id=%s — "
                "returning mini_parwa fallback",
                company_id, ticket_id,
            )
            return "mini_parwa"

    def on_turn_complete(
        self,
        company_id: str,
        ticket_id: str,
    ) -> None:
        """Mark a turn as complete for a ticket.

        For SG-08 (Upgrade):
          After the first turn completes with old capabilities
          (``uses_old_capabilities=True``), set up for the next
          turn to use new capabilities.  The actual switch happens
          in ``on_turn_start`` on the next turn.

        For SG-09 (Downgrade):
          Same pattern — the first turn after downgrade completes
          with old capabilities, and the next turn switches.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                ticket = self._ticket_registry.get(ticket_id)
                if ticket is None:
                    logger.debug(
                        "on_turn_complete: ticket_id=%s not found "
                        "(may have been unregistered)",
                        ticket_id,
                    )
                    return

                if ticket.transition_pending and ticket.uses_old_capabilities:
                    # The current turn just finished with old capabilities.
                    # Keep uses_old_capabilities=True so that on_turn_start
                    # on the NEXT turn will apply the transition.
                    logger.info(
                        "Turn %d completed with old capabilities for "
                        "ticket %s — transition will apply on next turn "
                        "(company_id=%s, pending=%s)",
                        ticket.turn_count, ticket_id, company_id,
                        ticket.pending_variant,
                    )

        except Exception:
            logger.exception(
                "on_turn_complete failed for company_id=%s, ticket_id=%s",
                company_id, ticket_id,
            )

    def complete_transition(
        self,
        company_id: str,
        transition_id: str,
    ) -> Optional[TransitionRecord]:
        """Mark a transition as fully completed.

        Updates the transition status to COMPLETED and sets the
        company's effective variant to the target variant.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns None on error.
        """
        try:
            with self._lock:
                record = self._transition_history.get(transition_id)
                if record is None:
                    logger.warning(
                        "complete_transition: transition_id=%s not found "
                        "for company_id=%s",
                        transition_id, company_id,
                    )
                    return None

                if record.company_id != company_id:
                    logger.warning(
                        "complete_transition: transition_id=%s belongs to "
                        "company_id=%s, not %s",
                        transition_id, record.company_id, company_id,
                    )
                    return None

                record.status = TransitionStatus.COMPLETED

                # Set sticky effective variant for the company
                self._company_effective_variant[company_id] = record.to_variant

                logger.info(
                    "Transition completed: transition_id=%s, company_id=%s, "
                    "%s → %s",
                    transition_id, company_id,
                    record.from_variant, record.to_variant,
                )
                return record

        except Exception:
            logger.exception(
                "complete_transition failed for company_id=%s, "
                "transition_id=%s",
                company_id, transition_id,
            )
            return None

    # ── Downgrade (SG-09) ──────────────────────────────────────────

    def initiate_downgrade(
        self,
        company_id: str,
        from_variant: str,
        to_variant: str,
        reason: str = "",
    ) -> TransitionRecord:
        """Start the downgrade process for a company (SG-09).

        Steps:
          1. Validate that the transition direction is a downgrade
             (to_variant has lower rank than from_variant).
          2. Mark all in-flight tickets: they complete current turn
             with old capabilities (``uses_old_capabilities=True``).
          3. Immediately restrict technique tier access — new tickets
             and subsequent turns use lower variant capabilities.
          4. Clear cache for restricted features.
          5. Generate a deactivation notice for the admin panel.
          6. Return the transition record.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — always returns a TransitionRecord.
        """
        try:
            # Validate transition direction
            is_valid, validation_msg = self.validate_transition(
                from_variant, to_variant,
            )
            if not is_valid:
                logger.warning(
                    "initiate_downgrade: invalid transition for "
                    "company_id=%s: %s → %s (%s)",
                    company_id, from_variant, to_variant, validation_msg,
                )
                return self._create_error_transition_record(
                    company_id=company_id,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    reason=validation_msg,
                )

            # Verify it's actually a downgrade
            from_rank = VARIANT_RANKING.get(from_variant, 0)
            to_rank = VARIANT_RANKING.get(to_variant, 0)
            if to_rank >= from_rank:
                logger.warning(
                    "initiate_downgrade: not a downgrade (rank %d → %d) "
                    "for company_id=%s",
                    from_rank, to_rank, company_id,
                )
                return self._create_error_transition_record(
                    company_id=company_id,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    reason=(
                        f"Not a downgrade: {from_variant} (rank {from_rank}) "
                        f"→ {to_variant} (rank {to_rank})"
                    ),
                )

            transition_id = f"tr_{uuid.uuid4().hex[:12]}"
            now_iso = self._utc_now_iso()

            # 1. Mark all in-flight tickets
            affected_count = 0
            with self._lock:
                ticket_ids = self._company_tickets.get(company_id, [])
                for tid in ticket_ids:
                    ticket = self._ticket_registry.get(tid)
                    if ticket is not None:
                        ticket.transition_pending = True
                        ticket.pending_variant = to_variant
                        ticket.uses_old_capabilities = True
                        affected_count += 1
                        logger.info(
                            "Downgrade: marked ticket %s for transition "
                            "(uses_old_capabilities=True)",
                            tid,
                        )

            # 2. Get restricted features
            restricted = self.get_restricted_features(
                company_id, from_variant, to_variant,
            )

            # 3. Clear cache for restricted features
            cleared_keys = self.clear_restricted_cache(
                company_id, from_variant, to_variant,
            )

            # 4. Generate deactivation notice
            notice = self._create_deactivation_notice(
                company_id=company_id,
                from_variant=from_variant,
                to_variant=to_variant,
                restricted_features=restricted,
            )
            notice_sent = True

            # 5. Set the company's effective variant immediately
            #    (for new tickets and routing decisions)
            with self._lock:
                self._company_effective_variant[company_id] = to_variant

                record = TransitionRecord(
                    transition_id=transition_id,
                    company_id=company_id,
                    transition_type=TransitionType.DOWNGRADE,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    timestamp=now_iso,
                    in_flight_tickets_affected=affected_count,
                    status=TransitionStatus.ACTIVE,
                    cache_cleared=len(cleared_keys) > 0,
                    deactivation_notice_sent=notice_sent,
                    details={
                        "reason": reason,
                        "from_rank": from_rank,
                        "to_rank": to_rank,
                        "affected_ticket_ids": ticket_ids,
                        "restricted_features": restricted,
                        "cleared_cache_keys": cleared_keys,
                        "deactivation_notice_id": notice.notice_id,
                    },
                )

                self._transition_history[transition_id] = record
                if company_id not in self._company_transitions:
                    self._company_transitions[company_id] = []
                self._company_transitions[company_id].append(transition_id)

            logger.info(
                "Downgrade initiated: company_id=%s, %s → %s, "
                "transition_id=%s, tickets_affected=%d, "
                "restricted_features=%d, cache_cleared=%d, "
                "notice_sent=%s, reason='%s'",
                company_id, from_variant, to_variant,
                transition_id, affected_count,
                len(restricted), len(cleared_keys),
                notice_sent, reason,
            )
            return record

        except Exception:
            logger.exception(
                "initiate_downgrade failed for company_id=%s, "
                "%s → %s — returning error record",
                company_id, from_variant, to_variant,
            )
            return self._create_error_transition_record(
                company_id=company_id,
                from_variant=from_variant,
                to_variant=to_variant,
                reason="internal_error_in_initiate_downgrade",
            )

    def get_restricted_features(
        self,
        company_id: str,
        from_variant: str,
        to_variant: str,
    ) -> List[str]:
        """List features that will be restricted in a downgrade.

        Computes the set difference between the source variant's
        features and the target variant's features.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            from_caps = self._capabilities.get(from_variant)
            to_caps = self._capabilities.get(to_variant)

            if from_caps is None or to_caps is None:
                logger.warning(
                    "get_restricted_features: unknown variant for "
                    "company_id=%s (from=%s, to=%s)",
                    company_id, from_variant, to_variant,
                )
                return []

            from_set = set(from_caps.features)
            to_set = set(to_caps.features)
            restricted = sorted(from_set - to_set)

            logger.info(
                "Restricted features for company_id=%s (%s → %s): %s",
                company_id, from_variant, to_variant, restricted,
            )
            return restricted

        except Exception:
            logger.exception(
                "get_restricted_features failed for company_id=%s",
                company_id,
            )
            return []

    def get_deactivation_notices(
        self,
        company_id: str,
    ) -> List[DeactivationNotice]:
        """Get all deactivation notices for a company.

        Includes both acknowledged and unacknowledged notices.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            with self._lock:
                notice_ids = self._company_notices.get(company_id, [])
                notices: List[DeactivationNotice] = []
                for nid in notice_ids:
                    notice = self._deactivation_notices.get(nid)
                    if notice is not None:
                        notices.append(notice)
                return notices

        except Exception:
            logger.exception(
                "get_deactivation_notices failed for company_id=%s",
                company_id,
            )
            return []

    def acknowledge_deactivation(
        self,
        company_id: str,
        notice_id: str,
    ) -> bool:
        """Mark a deactivation notice as acknowledged by an admin.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns False on error.
        """
        try:
            with self._lock:
                notice = self._deactivation_notices.get(notice_id)
                if notice is None:
                    logger.warning(
                        "acknowledge_deactivation: notice_id=%s not found "
                        "for company_id=%s",
                        notice_id, company_id,
                    )
                    return False

                if notice.company_id != company_id:
                    logger.warning(
                        "acknowledge_deactivation: notice_id=%s belongs to "
                        "company_id=%s, not %s",
                        notice_id, notice.company_id, company_id,
                    )
                    return False

                notice.acknowledged = True

            logger.info(
                "Deactivation notice acknowledged: notice_id=%s, "
                "company_id=%s, %s → %s",
                notice_id, company_id,
                notice.variant_from, notice.variant_to,
            )
            return True

        except Exception:
            logger.exception(
                "acknowledge_deactivation failed for company_id=%s, "
                "notice_id=%s",
                company_id, notice_id,
            )
            return False

    def clear_restricted_cache(
        self,
        company_id: str,
        variant_from: str,
        variant_to: str,
    ) -> List[str]:
        """Clear cache entries for features no longer available after downgrade.

        Simulates cache clearing by removing entries from the
        in-memory feature cache that belong to the restricted
        feature set. In production, this would call the actual
        caching layer (Redis, etc.).

        Returns the list of cache keys that were cleared.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            restricted = self.get_restricted_features(
                company_id, variant_from, variant_to,
            )

            cleared_keys: List[str] = []
            with self._lock:
                for feature in restricted:
                    cache_key = f"{company_id}:{feature}"
                    if cache_key in self._feature_cache:
                        del self._feature_cache[cache_key]
                        cleared_keys.append(cache_key)

            if cleared_keys:
                logger.info(
                    "Cache cleared for company_id=%s downgrade (%s → %s): "
                    "%d entries removed: %s",
                    company_id, variant_from, variant_to,
                    len(cleared_keys),
                    cleared_keys[:5],  # log first 5 for brevity
                )
            else:
                logger.debug(
                    "No cache entries to clear for company_id=%s "
                    "downgrade (%s → %s)",
                    company_id, variant_from, variant_to,
                )

            return cleared_keys

        except Exception:
            logger.exception(
                "clear_restricted_cache failed for company_id=%s",
                company_id,
            )
            return []

    # ── Query Methods ──────────────────────────────────────────────

    def get_effective_capabilities(
        self,
        company_id: str,
        ticket_id: str,
    ) -> VariantCapabilities:
        """Get the current capabilities for a ticket's effective variant.

        Looks up the ticket's effective_variant and returns the
        corresponding VariantCapabilities. If the ticket is not
        found or the variant is unknown, returns mini_parwa
        capabilities as the safest default (BC-008).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — always returns valid capabilities.
        """
        try:
            with self._lock:
                ticket = self._ticket_registry.get(ticket_id)

            if ticket is None or ticket.company_id != company_id:
                logger.warning(
                    "get_effective_capabilities: ticket_id=%s not found "
                    "or mismatched company — returning mini_parwa caps",
                    ticket_id,
                )
                return self._capabilities["mini_parwa"]

            caps = self._capabilities.get(ticket.effective_variant)
            if caps is None:
                logger.warning(
                    "get_effective_capabilities: unknown variant '%s' "
                    "for ticket %s — returning mini_parwa caps",
                    ticket.effective_variant, ticket_id,
                )
                return self._capabilities["mini_parwa"]

            return caps

        except Exception:
            logger.exception(
                "get_effective_capabilities failed for company_id=%s, "
                "ticket_id=%s — returning mini_parwa caps",
                company_id, ticket_id,
            )
            return self._capabilities["mini_parwa"]

    def get_transition_history(
        self,
        company_id: str,
    ) -> List[TransitionRecord]:
        """List all transition records for a company.

        Returns transitions in chronological order (newest last).

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            with self._lock:
                transition_ids = self._company_transitions.get(company_id, [])
                records: List[TransitionRecord] = []
                for tid in transition_ids:
                    record = self._transition_history.get(tid)
                    if record is not None:
                        records.append(record)
                return records

        except Exception:
            logger.exception(
                "get_transition_history failed for company_id=%s",
                company_id,
            )
            return []

    def get_active_transitions(
        self,
        company_id: str,
    ) -> List[TransitionRecord]:
        """List all in-progress (ACTIVE or PENDING) transitions.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            all_transitions = self.get_transition_history(company_id)
            active = [
                t for t in all_transitions
                if t.status in (TransitionStatus.ACTIVE, TransitionStatus.PENDING)
            ]
            return active

        except Exception:
            logger.exception(
                "get_active_transitions failed for company_id=%s",
                company_id,
            )
            return []

    def get_variant_capabilities(
        self,
        variant_type: str,
    ) -> VariantCapabilities:
        """Get the full capability profile for a specific variant type.

        Returns mini_parwa capabilities as a safe default if the
        variant is unknown (BC-008).

        BC-008: Never crashes.
        """
        try:
            caps = self._capabilities.get(variant_type)
            if caps is not None:
                return caps

            logger.warning(
                "get_variant_capabilities: unknown variant '%s' — "
                "returning mini_parwa capabilities",
                variant_type,
            )
            return self._capabilities["mini_parwa"]

        except Exception:
            logger.exception(
                "get_variant_capabilities failed for variant_type=%s",
                variant_type,
            )
            return self._capabilities["mini_parwa"]

    def get_technique_access_for_ticket(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[str]:
        """Get the list of allowed techniques for a ticket's effective variant.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns empty list on error.
        """
        try:
            caps = self.get_effective_capabilities(company_id, ticket_id)
            return list(caps.allowed_techniques)

        except Exception:
            logger.exception(
                "get_technique_access_for_ticket failed for company_id=%s, "
                "ticket_id=%s",
                company_id, ticket_id,
            )
            return []

    def is_technique_available(
        self,
        company_id: str,
        ticket_id: str,
        technique_id: str,
    ) -> bool:
        """Check if a specific technique is available for a ticket.

        Returns True if the technique is in the ticket's effective
        variant's allowed techniques list.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns False on error.
        """
        try:
            caps = self.get_effective_capabilities(company_id, ticket_id)
            normalized = technique_id.strip().lower()
            return normalized in caps.allowed_techniques

        except Exception:
            logger.exception(
                "is_technique_available failed for company_id=%s, "
                "ticket_id=%s, technique=%s",
                company_id, ticket_id, technique_id,
            )
            return False

    # ── Utility Methods ────────────────────────────────────────────

    def validate_transition(
        self,
        from_variant: str,
        to_variant: str,
    ) -> Tuple[bool, str]:
        """Check if a variant transition is valid.

        Validates:
          - Both variants are recognised.
          - The variants are different.
          - The transition direction is valid (either upgrade or downgrade).

        Returns ``(is_valid, reason_message)``.

        BC-008: Never crashes.
        """
        try:
            if not from_variant or not to_variant:
                return False, "variant names must not be empty"

            from_clean = from_variant.strip().lower()
            to_clean = to_variant.strip().lower()

            if from_clean not in VARIANT_RANKING:
                return False, f"unknown from_variant '{from_clean}'"
            if to_clean not in VARIANT_RANKING:
                return False, f"unknown to_variant '{to_clean}'"

            if from_clean == to_clean:
                return False, "from_variant and to_variant must be different"

            from_rank = VARIANT_RANKING[from_clean]
            to_rank = VARIANT_RANKING[to_clean]

            if to_rank > from_rank:
                direction = "upgrade"
            elif to_rank < from_rank:
                direction = "downgrade"
            else:
                return False, "variants have the same rank — no transition needed"

            return True, f"valid {direction} ({from_clean} rank {from_rank} → {to_clean} rank {to_rank})"

        except Exception:
            logger.exception(
                "validate_transition failed for %s → %s",
                from_variant, to_variant,
            )
            return False, "internal error during transition validation"

    def rollback_transition(
        self,
        company_id: str,
        transition_id: str,
    ) -> Optional[TransitionRecord]:
        """Roll back a transition that has not yet been fully applied.

        Only ACTIVE transitions can be rolled back.  Reverts all
        in-flight tickets back to their original variant and removes
        the pending transition flags.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns None on error.
        """
        try:
            with self._lock:
                record = self._transition_history.get(transition_id)
                if record is None:
                    logger.warning(
                        "rollback_transition: transition_id=%s not found "
                        "for company_id=%s",
                        transition_id, company_id,
                    )
                    return None

                if record.company_id != company_id:
                    logger.warning(
                        "rollback_transition: transition_id=%s belongs to "
                        "company_id=%s, not %s",
                        transition_id, record.company_id, company_id,
                    )
                    return None

                if record.status not in (
                    TransitionStatus.ACTIVE,
                    TransitionStatus.PENDING,
                ):
                    logger.warning(
                        "rollback_transition: transition_id=%s has status "
                        "'%s' — cannot roll back completed/rolled-back "
                        "transitions",
                        transition_id, record.status.value,
                    )
                    return None

                # Revert all affected tickets
                reverted_count = 0
                ticket_ids = record.details.get("affected_ticket_ids", [])
                for tid in ticket_ids:
                    ticket = self._ticket_registry.get(tid)
                    if ticket is not None and ticket.transition_pending:
                        ticket.transition_pending = False
                        ticket.pending_variant = None
                        ticket.uses_old_capabilities = False
                        # Revert effective variant to the original
                        ticket.effective_variant = record.from_variant
                        reverted_count += 1

                # Restore company effective variant to the original
                if company_id in self._company_effective_variant:
                    self._company_effective_variant[company_id] = record.from_variant

                record.status = TransitionStatus.ROLLED_BACK
                record.details["rollback_timestamp"] = self._utc_now_iso()
                record.details["tickets_reverted"] = reverted_count

            logger.info(
                "Transition rolled back: transition_id=%s, company_id=%s, "
                "%s → %s (was %s), tickets_reverted=%d",
                transition_id, company_id,
                record.to_variant, record.from_variant,
                record.transition_type.value, reverted_count,
            )
            return record

        except Exception:
            logger.exception(
                "rollback_transition failed for company_id=%s, "
                "transition_id=%s",
                company_id, transition_id,
            )
            return None

    # ── Internal Helpers ───────────────────────────────────────────

    def _create_error_transition_record(
        self,
        company_id: str,
        from_variant: str,
        to_variant: str,
        reason: str,
    ) -> TransitionRecord:
        """Create a transition record that represents a failed validation.

        Uses ROLLED_BACK status to indicate the transition was
        rejected and never applied.
        """
        return TransitionRecord(
            transition_id=f"tr_err_{uuid.uuid4().hex[:8]}",
            company_id=company_id,
            transition_type=TransitionType.UPGRADE,  # default; caller may override
            from_variant=from_variant,
            to_variant=to_variant,
            timestamp=self._utc_now_iso(),
            in_flight_tickets_affected=0,
            status=TransitionStatus.ROLLED_BACK,
            cache_cleared=False,
            deactivation_notice_sent=False,
            details={
                "error": True,
                "reason": reason,
            },
        )

    def _create_deactivation_notice(
        self,
        company_id: str,
        from_variant: str,
        to_variant: str,
        restricted_features: List[str],
    ) -> DeactivationNotice:
        """Create and store a deactivation notice for an admin panel.

        The notice lists which features are being disabled and
        provides a human-readable message.
        """
        notice_id = f"dn_{uuid.uuid4().hex[:12]}"
        now_iso = self._utc_now_iso()

        feature_list = (
            ", ".join(restricted_features) if restricted_features
            else "No additional features were restricted."
        )

        message = (
            f"Your PARWA variant has been downgraded from "
            f"'{from_variant}' to '{to_variant}'. "
            f"The following features are no longer available: "
            f"{feature_list}. "
            f"Existing tickets in-flight will complete their current "
            f"turn with previous capabilities before switching."
        )

        notice = DeactivationNotice(
            notice_id=notice_id,
            company_id=company_id,
            variant_from=from_variant,
            variant_to=to_variant,
            restricted_features=list(restricted_features),
            message=message,
            timestamp=now_iso,
            acknowledged=False,
        )

        with self._lock:
            self._deactivation_notices[notice_id] = notice
            if company_id not in self._company_notices:
                self._company_notices[company_id] = []
            self._company_notices[company_id].append(notice_id)

        logger.info(
            "Deactivation notice created: notice_id=%s, company_id=%s, "
            "%s → %s, restricted_count=%d",
            notice_id, company_id,
            from_variant, to_variant,
            len(restricted_features),
        )
        return notice

    # ── Administrative / Diagnostic Methods ────────────────────────

    def get_all_variant_types(self) -> List[str]:
        """Return all known variant type names."""
        try:
            return list(VALID_VARIANT_TYPES)
        except Exception:
            logger.exception("get_all_variant_types failed")
            return []

    def get_variant_rank(self, variant_type: str) -> int:
        """Return the numeric rank of a variant (1, 2, or 3).

        Returns 0 for unknown variants.

        BC-008: Never crashes.
        """
        try:
            return VARIANT_RANKING.get(variant_type.strip().lower(), 0)
        except Exception:
            logger.exception(
                "get_variant_rank failed for variant_type=%s",
                variant_type,
            )
            return 0

    def get_ticket_count(self, company_id: str) -> int:
        """Return the number of in-flight tickets for a company.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                ticket_ids = self._company_tickets.get(company_id, [])
                return len(ticket_ids)
        except Exception:
            logger.exception(
                "get_ticket_count failed for company_id=%s",
                company_id,
            )
            return 0

    def get_all_pending_tickets(self) -> List[InFlightTicket]:
        """Return all in-flight tickets across all companies that have
        a pending transition.

        Useful for monitoring and debugging transition states.

        BC-008: Never crashes.
        """
        try:
            with self._lock:
                pending: List[InFlightTicket] = []
                for ticket in self._ticket_registry.values():
                    if ticket.transition_pending:
                        pending.append(ticket)
                return pending
        except Exception:
            logger.exception("get_all_pending_tickets failed")
            return []

    def get_company_effective_variant(
        self,
        company_id: str,
    ) -> str:
        """Return the current effective variant for a company.

        If no transition has set an effective variant, returns
        an empty string.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            with self._lock:
                return self._company_effective_variant.get(company_id, "")
        except Exception:
            logger.exception(
                "get_company_effective_variant failed for company_id=%s",
                company_id,
            )
            return ""

    def reset_company_variant(
        self,
        company_id: str,
        default_variant: str,
    ) -> bool:
        """Reset a company's effective variant to a specified default.

        Useful for testing and administrative overrides.  Does NOT
        affect in-flight tickets — only the sticky company-level
        variant used when registering new tickets.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            if default_variant not in VARIANT_RANKING:
                logger.warning(
                    "reset_company_variant: invalid variant '%s' "
                    "for company_id=%s",
                    default_variant, company_id,
                )
                return False

            with self._lock:
                self._company_effective_variant[company_id] = default_variant

            logger.info(
                "Company variant reset: company_id=%s → %s",
                company_id, default_variant,
            )
            return True

        except Exception:
            logger.exception(
                "reset_company_variant failed for company_id=%s",
                company_id,
            )
            return False

    def compare_variant_capabilities(
        self,
        variant_a: str,
        variant_b: str,
    ) -> Dict[str, Any]:
        """Compare two variants' capabilities side by side.

        Returns a dict with common, only_in_a, only_in_b lists
        for techniques and features.

        BC-008: Never crashes.
        """
        try:
            caps_a = self.get_variant_capabilities(variant_a)
            caps_b = self.get_variant_capabilities(variant_b)

            tech_a = set(caps_a.allowed_techniques)
            tech_b = set(caps_b.allowed_techniques)
            feat_a = set(caps_a.features)
            feat_b = set(caps_b.features)

            return {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "variant_a_rank": VARIANT_RANKING.get(variant_a, 0),
                "variant_b_rank": VARIANT_RANKING.get(variant_b, 0),
                "variant_a_max_tier": caps_a.max_tier,
                "variant_b_max_tier": caps_b.max_tier,
                "techniques": {
                    "common": sorted(tech_a & tech_b),
                    "only_in_a": sorted(tech_a - tech_b),
                    "only_in_b": sorted(tech_b - tech_a),
                    "a_count": len(tech_a),
                    "b_count": len(tech_b),
                },
                "features": {
                    "common": sorted(feat_a & feat_b),
                    "only_in_a": sorted(feat_a - feat_b),
                    "only_in_b": sorted(feat_b - feat_a),
                    "a_count": len(feat_a),
                    "b_count": len(feat_b),
                },
                "smart_router": {
                    "a_tiers": caps_a.smart_router_tiers,
                    "b_tiers": caps_b.smart_router_tiers,
                },
                "agents": {
                    "a_max": caps_a.max_agents,
                    "b_max": caps_b.max_agents,
                },
                "confidence": {
                    "a_threshold": caps_a.confidence_threshold,
                    "b_threshold": caps_b.confidence_threshold,
                },
            }

        except Exception:
            logger.exception(
                "compare_variant_capabilities failed for %s vs %s",
                variant_a, variant_b,
            )
            return {"error": "comparison_failed"}

    def get_transition_summary(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get a summary of all transitions and current state for a company.

        Returns aggregate statistics and the current effective variant.

        BC-001: company_id is first parameter.
        BC-008: Never crashes.
        """
        try:
            history = self.get_transition_history(company_id)
            active = self.get_active_transitions(company_id)
            tickets = self.get_in_flight_tickets(company_id)
            pending_tickets = [t for t in tickets if t.transition_pending]
            notices = self.get_deactivation_notices(company_id)
            unacknowledged = [n for n in notices if not n.acknowledged]

            upgrades = [t for t in history if t.transition_type == TransitionType.UPGRADE]
            downgrades = [t for t in history if t.transition_type == TransitionType.DOWNGRADE]
            completed = [t for t in history if t.status == TransitionStatus.COMPLETED]
            rolled_back = [t for t in history if t.status == TransitionStatus.ROLLED_BACK]

            effective_variant = self.get_company_effective_variant(company_id)

            return {
                "company_id": company_id,
                "effective_variant": effective_variant,
                "total_transitions": len(history),
                "upgrades": len(upgrades),
                "downgrades": len(downgrades),
                "active_transitions": len(active),
                "completed_transitions": len(completed),
                "rolled_back_transitions": len(rolled_back),
                "in_flight_tickets": len(tickets),
                "tickets_with_pending_transition": len(pending_tickets),
                "deactivation_notices": len(notices),
                "unacknowledged_notices": len(unacknowledged),
                "latest_transition": (
                    history[-1].to_dict() if history else None
                ),
            }

        except Exception:
            logger.exception(
                "get_transition_summary failed for company_id=%s",
                company_id,
            )
            return {"error": "summary_generation_failed"}
