"""
Cross-Variant Interaction Module.

Handles three critical situation gaps for how PARWA AI variants interact
when multiple variants are hired by the same company:

1. **Confidence-Based Escalation** — When a variant generates a response
   with a low confidence score, auto-escalate to a higher-tier variant
   that can handle it better.

2. **Same-Ticket Handoff with Context Transfer** — When a ticket is
   escalated from one variant to another, the receiving variant gets the
   full conversation context bundled in a ``HandoffContext``.

3. **Multi-Variant Conflict Resolution** — When a company has multiple
   variants hired and a customer interacts across multiple channels,
   different variants may respond. This module detects conflicts and
   resolves them.

This module is complementary to ``cross_variant_routing.py`` which
handles capacity-based escalation, complexity escalation, and initial
routing.  This module does NOT duplicate those concerns.

BC-001: company_id is always first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger(__name__)


# ── Constants ───────────────────────────────────────────────────────

# Minimum confidence thresholds per variant.  When a variant's
# confidence score falls below its threshold the response is
# escalated to the next higher tier.
CONFIDENCE_THRESHOLDS: Dict[str, float] = {
    "mini_parwa": 0.65,  # Tier 1 — escalate if confidence < 0.65
    "parwa": 0.45,  # Tier 2 — escalate if confidence < 0.45
    "high_parwa": 0.30,  # Tier 3 — escalate if confidence < 0.30 (rare)
}

# Ordered escalation chain — lowest to highest variant tier.
ESCALATION_CHAIN: List[str] = [
    "mini_parwa",  # Tier 1 — Starter
    "parwa",  # Tier 2 — Growth
    "high_parwa",  # Tier 3 — High
]

VALID_VARIANTS: set = set(ESCALATION_CHAIN)

# Time window (seconds) within which responses from different variants
# on different channels are considered a potential conflict.
CONFLICT_TIME_WINDOW_SECONDS: float = 300.0  # 5 minutes


# ── Enums ───────────────────────────────────────────────────────────


class EscalationReason(str, Enum):
    """Reasons why a cross-variant interaction escalation was triggered.

    Distinct from ``cross_variant_routing.EscalationReason`` which covers
    capacity and complexity.  This enum covers interaction-layer triggers
    such as low confidence and conflict detection.
    """

    LOW_CONFIDENCE = "low_confidence"
    CONTEXT_TRANSFER = "context_transfer"
    CONFLICT_DETECTED = "conflict_detected"
    TECHNIQUE_UNAVAILABLE = "technique_unavailable"
    MANUAL_REQUEST = "manual_request"


class ConflictSeverity(str, Enum):
    """Severity level for a detected multi-variant conflict."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ResolutionStrategy(str, Enum):
    """Strategy for resolving a multi-variant conflict.

    - ``NO_ACTION`` — Responses are similar, nothing to do.
    - ``MERGE_PREFER_HIGH_CONFIDENCE`` — Slightly different responses;
      merge them, prefer the one with higher confidence.
    - ``HUMAN_REVIEW`` — Contradictory responses; flag for human review
      and use the highest-tier variant's response in the meantime.
    """

    NO_ACTION = "no_action"
    MERGE_PREFER_HIGH_CONFIDENCE = "merge_prefer_high_confidence"
    HUMAN_REVIEW = "human_review"


class HandoffStatus(str, Enum):
    """Status of a handoff between variants."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"


# ── Data Structures ─────────────────────────────────────────────────


@dataclass
class ConfidenceHistoryEntry:
    """Single entry in a ticket's confidence history.

    Tracks the confidence score, variant that produced it, and whether
    it triggered an escalation — used for analytics.
    """

    ticket_id: str
    variant_type: str
    confidence_score: float
    timestamp: datetime
    escalated: bool = False
    escalation_target: str = ""
    reason: str = ""


@dataclass
class ConfidenceEscalationResult:
    """Result of evaluating whether a response should be escalated
    based on its confidence score.

    Attributes:
        should_escalate: Whether the response needs escalation.
        target_variant: The variant to escalate to (empty if no
            escalation needed or already at highest tier).
        reason: Human-readable explanation for the decision.
        escalation_context: Dictionary containing the original query,
            the low-confidence response, and any metadata — passed to
            the higher-tier variant so it can produce a better answer.
        confidence_score: The original confidence score (echoed back).
        original_variant: The variant that produced the low-confidence
            response.
        requires_human_review: True when ``high_parwa`` still produces
            a low-confidence response and no higher tier exists.
    """

    should_escalate: bool = False
    target_variant: str = ""
    reason: str = ""
    escalation_context: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    original_variant: str = ""
    requires_human_review: bool = False


@dataclass
class HandoffContext:
    """Full context bundle transferred during a same-ticket handoff.

    Contains everything the receiving variant needs to seamlessly
    continue the conversation without losing any prior context.

    Attributes:
        ticket_id: The ticket being handed off.
        from_variant: The variant initiating the handoff.
        to_variant: The variant receiving the handoff.
        conversation_history: List of prior messages in the format
            ``[{"role": "user"|"agent", "content": "...",
            "variant": "...", "timestamp": "..."}]``.
        classification_data: Optional ticket classification data.
        sentiment_data: Optional sentiment analysis data.
        customer_context: Optional customer profile / context data.
        reason: Why the handoff was initiated (e.g. low confidence).
        created_at: UTC timestamp when the handoff was created.
        acknowledged: Whether the target variant has confirmed receipt.
        acknowledged_at: UTC timestamp when the handoff was acknowledged.
    """

    ticket_id: str = ""
    from_variant: str = ""
    to_variant: str = ""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    classification_data: Optional[Dict[str, Any]] = None
    sentiment_data: Optional[Dict[str, Any]] = None
    customer_context: Optional[Dict[str, Any]] = None
    reason: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


@dataclass
class HandoffResult:
    """Result of initiating a same-ticket handoff.

    Attributes:
        success: Whether the handoff was created successfully.
        handoff_context: The full ``HandoffContext`` that was stored.
        message: Human-readable status message.
        duplicate_prevented: True if a duplicate handoff for the same
            ticket+variant combo was detected and prevented.
    """

    success: bool = False
    handoff_context: Optional[HandoffContext] = None
    message: str = ""
    duplicate_prevented: bool = False


@dataclass
class RegisteredResponse:
    """A single response registered in the multi-variant conflict
    tracker.

    Attributes:
        ticket_id: Ticket the response belongs to.
        customer_id: Customer who received the response.
        variant_type: Variant that generated the response.
        channel: Channel through which the response was delivered.
        response_content: The actual response text.
        confidence_score: Confidence score of the response.
        timestamp: UTC timestamp when the response was registered.
    """

    ticket_id: str
    customer_id: str
    variant_type: str
    channel: str
    response_content: str
    confidence_score: float
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass
class ConflictCheckResult:
    """Immediate result when a new response is registered.

    Indicates whether the registration triggered a conflict detection.

    Attributes:
        has_conflict: Whether a conflict was detected.
        conflict_id: UUID of the detected conflict (empty if none).
        severity: Severity of the detected conflict.
        conflicting_responses: List of responses that conflict.
        customer_id: Customer involved in the conflict.
    """

    has_conflict: bool = False
    conflict_id: str = ""
    severity: ConflictSeverity = ConflictSeverity.LOW
    conflicting_responses: List[RegisteredResponse] = field(default_factory=list)
    customer_id: str = ""


@dataclass
class ConflictResult:
    """Full representation of a detected multi-variant conflict.

    Attributes:
        conflict_id: Unique identifier for this conflict.
        customer_id: Customer affected by the conflict.
        responses: All responses involved in the conflict.
        severity: How severe the conflict is.
        resolution_strategy: Recommended strategy to resolve.
        detected_at: UTC timestamp when the conflict was detected.
        resolved: Whether the conflict has been resolved.
    """

    conflict_id: str
    customer_id: str
    responses: List[RegisteredResponse]
    severity: ConflictSeverity
    resolution_strategy: ResolutionStrategy
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    resolved: bool = False


@dataclass
class ResolutionResult:
    """Result of resolving a multi-variant conflict.

    Attributes:
        resolved: Whether the conflict was successfully resolved.
        final_response: The agreed-upon response content after
            resolution.
        strategy_used: The strategy that was applied.
        conflicts_merged: Number of individual conflicts that were
            merged into this resolution.
        conflict_id: The conflict that was resolved.
        message: Human-readable status message.
    """

    resolved: bool = False
    final_response: str = ""
    strategy_used: ResolutionStrategy = ResolutionStrategy.NO_ACTION
    conflicts_merged: int = 0
    conflict_id: str = ""
    message: str = ""


@dataclass
class CustomerInteractionSummary:
    """Summary of a customer's recent interactions across all variants
    and channels.

    Attributes:
        customer_id: The customer being summarised.
        total_interactions: Total number of registered responses.
        variants_used: Set of variant types that responded.
        channels_used: Set of channels used.
        last_interaction_at: UTC timestamp of the most recent
            interaction.
        active_conflicts: List of unresolved conflict IDs.
        interactions_by_variant: Breakdown of interactions per variant.
    """

    customer_id: str
    total_interactions: int = 0
    variants_used: List[str] = field(default_factory=list)
    channels_used: List[str] = field(default_factory=list)
    last_interaction_at: Optional[datetime] = None
    active_conflicts: List[str] = field(default_factory=list)
    interactions_by_variant: Dict[str, int] = field(default_factory=dict)


# ── Custom Error ────────────────────────────────────────────────────


class CrossVariantInteractionError(ParwaBaseError):
    """Raised when a cross-variant interaction operation cannot proceed.

    Inherits from ``ParwaBaseError`` so the global error handler can
    serialise it into a structured JSON response (BC-012).
    """

    def __init__(
        self,
        message: str = "Cross-variant interaction failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="CROSS_VARIANT_INTERACTION_ERROR",
            status_code=503,
            details=details,
        )


# ── Main Service ────────────────────────────────────────────────────


class CrossVariantInteractionService:
    """Manages cross-variant interactions for multi-variant companies.

    Provides three core capabilities that complement the routing layer
    (``cross_variant_routing.py``):

    1. **Confidence-Based Escalation** — evaluates variant confidence
       scores and auto-escalates to higher tiers when thresholds are
       not met.

    2. **Same-Ticket Handoff** — bundles full conversation context
       when a ticket moves from one variant to another, ensuring
       the receiving variant has everything it needs.

    3. **Multi-Variant Conflict Resolution** — detects when different
       variants give conflicting responses to the same customer on
       different channels, and resolves them by severity level.

    Thread-safety: All mutable state is protected by ``_lock``.
    In production, replace in-memory stores with Redis or a database.
    """

    def __init__(self) -> None:
        # ── Confidence escalation state ───────────────────────
        # Per-ticket confidence history: {ticket_id: [ConfidenceHistoryEntry]}
        self._confidence_history: Dict[str, List[ConfidenceHistoryEntry]] = {}

        # ── Handoff state ─────────────────────────────────────
        # Handoff store keyed by "{company_id}:{ticket_id}:{to_variant}"
        self._handoffs: Dict[str, HandoffContext] = {}
        # Set of active (unacknowledged) handoff keys per company
        self._active_handoff_keys: Dict[str, List[str]] = {}

        # ── Conflict resolution state ─────────────────────────
        # Per-company customer interactions: {company_id: {customer_id:
        # [RegisteredResponse]}}
        self._customer_interactions: Dict[str, Dict[str, List[RegisteredResponse]]] = {}
        # Detected conflicts: {conflict_id: ConflictResult}
        self._conflicts: Dict[str, ConflictResult] = {}
        # Per-customer active conflict IDs: {company_id: {customer_id:
        # [conflict_id, ...]}}
        self._customer_conflicts: Dict[str, Dict[str, List[str]]] = {}

        self._lock = threading.Lock()

        logger.info(
            "CrossVariantInteractionService initialised — "
            "confidence thresholds: %s, conflict window: %.0fs",
            CONFIDENCE_THRESHOLDS,
            CONFLICT_TIME_WINDOW_SECONDS,
        )

    # ═══════════════════════════════════════════════════════════════
    #  1. CONFIDENCE-BASED ESCALATION
    # ═══════════════════════════════════════════════════════════════

    def _get_next_variant(self, variant_type: str) -> Optional[str]:
        """Return the next higher variant in the escalation chain.

        Returns ``None`` if *variant_type* is already the highest tier.
        This is an internal helper — not a public method.
        """
        try:
            if variant_type not in ESCALATION_CHAIN:
                return None
            idx = ESCALATION_CHAIN.index(variant_type)
            if 0 <= idx < len(ESCALATION_CHAIN) - 1:
                return ESCALATION_CHAIN[idx + 1]
            return None
        except Exception:
            logger.exception(
                "_get_next_variant failed for variant=%s",
                variant_type,
            )
            return None

    def _record_confidence(
        self,
        ticket_id: str,
        variant_type: str,
        confidence_score: float,
        escalated: bool,
        escalation_target: str = "",
        reason: str = "",
    ) -> None:
        """Record a confidence history entry for a ticket.

        Thread-safe.  Used internally for analytics tracking.
        """
        try:
            entry = ConfidenceHistoryEntry(
                ticket_id=ticket_id,
                variant_type=variant_type,
                confidence_score=confidence_score,
                timestamp=datetime.now(timezone.utc),
                escalated=escalated,
                escalation_target=escalation_target,
                reason=reason,
            )
            with self._lock:
                if ticket_id not in self._confidence_history:
                    self._confidence_history[ticket_id] = []
                self._confidence_history[ticket_id].append(entry)
        except Exception:
            logger.exception(
                "_record_confidence failed for ticket_id=%s",
                ticket_id,
            )

    def get_confidence_history(
        self,
        company_id: str,
        ticket_id: str,
    ) -> List[ConfidenceHistoryEntry]:
        """Retrieve the confidence history for a ticket.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns an empty list on failure.
        """
        try:
            with self._lock:
                history = self._confidence_history.get(ticket_id, [])
            logger.debug(
                "Confidence history for ticket_id=%s: %d entries",
                ticket_id,
                len(history),
            )
            return list(history)
        except Exception:
            logger.exception(
                "get_confidence_history failed for company_id=%s, " "ticket_id=%s",
                company_id,
                ticket_id,
            )
            return []

    def evaluate_confidence_escalation(
        self,
        company_id: str,
        ticket_id: str,
        variant_type: str,
        confidence_score: float,
        original_query: str,
        generated_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceEscalationResult:
        """Evaluate whether a variant's response should be escalated
        based on its confidence score.

        Each variant tier has a different confidence threshold (see
        ``CONFIDENCE_THRESHOLDS``).  When a variant's confidence falls
        below its threshold, the response is escalated to the next
        higher tier.  If the variant is already ``high_parwa`` and
        still has low confidence, the result is flagged for human review.

        The method also records the confidence score in the ticket's
        history for analytics.

        Args:
            company_id: The company that owns the ticket (BC-001).
            ticket_id: Unique ticket identifier.
            variant_type: The variant that generated the response
                (e.g. ``"mini_parwa"``).
            confidence_score: The confidence score of the generated
                response (0.0 – 1.0).
            original_query: The customer's original query.
            generated_response: The response the variant generated.
            metadata: Optional additional context for the higher-tier
                variant.

        Returns:
            A ``ConfidenceEscalationResult`` with the escalation
            decision and context bundle for the target variant.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a safe default on failure.
        BC-012: All timestamps UTC.
        """
        try:
            # Validate inputs
            if variant_type not in VALID_VARIANTS:
                logger.warning(
                    "evaluate_confidence_escalation: unknown variant "
                    "'%s' for company_id=%s, ticket_id=%s — returning "
                    "no-escalation result",
                    variant_type,
                    company_id,
                    ticket_id,
                )
                self._record_confidence(
                    ticket_id=ticket_id,
                    variant_type=variant_type,
                    confidence_score=confidence_score,
                    escalated=False,
                    reason="unknown_variant_type",
                )
                return ConfidenceEscalationResult(
                    should_escalate=False,
                    target_variant="",
                    reason=f"unknown variant type: {variant_type}",
                    escalation_context={},
                    confidence_score=confidence_score,
                    original_variant=variant_type,
                    requires_human_review=False,
                )

            threshold = CONFIDENCE_THRESHOLDS.get(variant_type, 0.50)

            # Clamp confidence score to valid range
            clamped_score = max(0.0, min(1.0, confidence_score))

            if clamped_score >= threshold:
                # Confidence is sufficient — no escalation needed
                self._record_confidence(
                    ticket_id=ticket_id,
                    variant_type=variant_type,
                    confidence_score=clamped_score,
                    escalated=False,
                    reason="confidence_within_threshold",
                )
                logger.info(
                    "Confidence OK for ticket_id=%s: variant=%s, "
                    "score=%.3f >= threshold=%.3f (company_id=%s)",
                    ticket_id,
                    variant_type,
                    clamped_score,
                    threshold,
                    company_id,
                )
                return ConfidenceEscalationResult(
                    should_escalate=False,
                    target_variant="",
                    reason=(
                        f"confidence {clamped_score:.3f} meets "
                        f"threshold {threshold:.3f} for {variant_type}"
                    ),
                    escalation_context={},
                    confidence_score=clamped_score,
                    original_variant=variant_type,
                    requires_human_review=False,
                )

            # Confidence is below threshold — determine escalation
            next_variant = self._get_next_variant(variant_type)

            escalation_context: Dict[str, Any] = {
                "original_query": original_query,
                "low_confidence_response": generated_response,
                "confidence_score": clamped_score,
                "threshold": threshold,
                "from_variant": variant_type,
                "metadata": metadata or {},
            }

            if next_variant is None:
                # Already at highest tier — flag for human review
                self._record_confidence(
                    ticket_id=ticket_id,
                    variant_type=variant_type,
                    confidence_score=clamped_score,
                    escalated=True,
                    reason="highest_tier_low_confidence_human_review",
                )
                logger.warning(
                    "HUMAN REVIEW REQUIRED for ticket_id=%s: "
                    "variant=%s has confidence %.3f < threshold %.3f "
                    "but is already highest tier (company_id=%s)",
                    ticket_id,
                    variant_type,
                    clamped_score,
                    threshold,
                    company_id,
                )
                return ConfidenceEscalationResult(
                    should_escalate=True,
                    target_variant="",
                    reason=(
                        f"{variant_type} confidence {clamped_score:.3f} "
                        f"below threshold {threshold:.3f} — highest "
                        "tier reached, escalating to human review"
                    ),
                    escalation_context=escalation_context,
                    confidence_score=clamped_score,
                    original_variant=variant_type,
                    requires_human_review=True,
                )

            # Escalate to next higher tier
            self._record_confidence(
                ticket_id=ticket_id,
                variant_type=variant_type,
                confidence_score=clamped_score,
                escalated=True,
                escalation_target=next_variant,
                reason="low_confidence_escalation",
            )
            logger.info(
                "CONFIDENCE ESCALATION for ticket_id=%s: "
                "variant=%s (score=%.3f < threshold=%.3f) → %s "
                "(company_id=%s)",
                ticket_id,
                variant_type,
                clamped_score,
                threshold,
                next_variant,
                company_id,
            )
            return ConfidenceEscalationResult(
                should_escalate=True,
                target_variant=next_variant,
                reason=(
                    f"{variant_type} confidence {clamped_score:.3f} "
                    f"below threshold {threshold:.3f} — escalating "
                    f"to {next_variant}"
                ),
                escalation_context=escalation_context,
                confidence_score=clamped_score,
                original_variant=variant_type,
                requires_human_review=False,
            )

        except Exception:
            logger.exception(
                "evaluate_confidence_escalation failed for "
                "company_id=%s, ticket_id=%s, variant=%s — "
                "returning safe no-escalation result",
                company_id,
                ticket_id,
                variant_type,
            )
            return ConfidenceEscalationResult(
                should_escalate=False,
                target_variant="",
                reason="internal_error_during_evaluation",
                escalation_context={},
                confidence_score=confidence_score,
                original_variant=variant_type,
                requires_human_review=False,
            )

    # ═══════════════════════════════════════════════════════════════
    #  2. SAME-TICKET HANDOFF WITH CONTEXT TRANSFER
    # ═══════════════════════════════════════════════════════════════

    def _handoff_key(
        self,
        company_id: str,
        ticket_id: str,
        target_variant: str,
    ) -> str:
        """Build the canonical storage key for a handoff."""
        return f"{company_id}:{ticket_id}:{target_variant}"

    def initiate_handoff(
        self,
        company_id: str,
        ticket_id: str,
        from_variant: str,
        to_variant: str,
        conversation_history: List[Dict[str, Any]],
        classification_data: Optional[Dict[str, Any]] = None,
        sentiment_data: Optional[Dict[str, Any]] = None,
        customer_context: Optional[Dict[str, Any]] = None,
    ) -> HandoffResult:
        """Initiate a handoff from one variant to another for a ticket.

        Creates a ``HandoffContext`` that bundles the full conversation
        history, classification data, sentiment data, and customer
        context into a single transferable package.  The context is
        stored internally so the receiving variant can retrieve it.

        Duplicate handoffs for the same ticket+target_variant
        combination are prevented — if one already exists and is still
        pending, the existing one is returned with
        ``duplicate_prevented=True``.

        Args:
            company_id: The company that owns the ticket (BC-001).
            ticket_id: The ticket being handed off.
            from_variant: The variant initiating the handoff.
            to_variant: The variant receiving the handoff.
            conversation_history: List of prior messages in the format
                ``[{"role": "user"|"agent", "content": "...",
                "variant": "...", "timestamp": "..."}]``.
            classification_data: Optional ticket classification.
            sentiment_data: Optional sentiment analysis results.
            customer_context: Optional customer profile data.

        Returns:
            A ``HandoffResult`` indicating success/failure and the
            stored context.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a safe default on failure.
        BC-012: All timestamps UTC.
        """
        try:
            # Validate variant names
            if from_variant not in VALID_VARIANTS:
                return HandoffResult(
                    success=False,
                    message=f"invalid from_variant: {from_variant}",
                )
            if to_variant not in VALID_VARIANTS:
                return HandoffResult(
                    success=False,
                    message=f"invalid to_variant: {to_variant}",
                )

            key = self._handoff_key(company_id, ticket_id, to_variant)

            with self._lock:
                # Prevent duplicate handoffs
                existing = self._handoffs.get(key)
                if existing is not None and not existing.acknowledged:
                    logger.info(
                        "Duplicate handoff prevented for key=%s — "
                        "existing handoff still pending "
                        "(company_id=%s, ticket_id=%s)",
                        key,
                        company_id,
                        ticket_id,
                    )
                    return HandoffResult(
                        success=True,
                        handoff_context=existing,
                        message=(
                            "Handoff already exists and is pending "
                            f"for ticket_id={ticket_id} → "
                            f"{to_variant}"
                        ),
                        duplicate_prevented=True,
                    )

                # Determine handoff reason
                reason = EscalationReason.CONTEXT_TRANSFER.value
                # Check if there's a confidence escalation for this
                # ticket that might provide a better reason
                history = self._confidence_history.get(ticket_id, [])
                for entry in reversed(history):
                    if entry.escalated:
                        reason = entry.reason or EscalationReason.LOW_CONFIDENCE.value
                        break

                context = HandoffContext(
                    ticket_id=ticket_id,
                    from_variant=from_variant,
                    to_variant=to_variant,
                    conversation_history=list(conversation_history),
                    classification_data=classification_data,
                    sentiment_data=sentiment_data,
                    customer_context=customer_context,
                    reason=reason,
                    created_at=datetime.now(timezone.utc),
                    acknowledged=False,
                    acknowledged_at=None,
                )

                self._handoffs[key] = context

                # Track as active handoff for the company
                if company_id not in self._active_handoff_keys:
                    self._active_handoff_keys[company_id] = []
                if key not in self._active_handoff_keys[company_id]:
                    self._active_handoff_keys[company_id].append(key)

            logger.info(
                "Handoff initiated: ticket_id=%s, %s → %s "
                "(company_id=%s, reason=%s, history_entries=%d)",
                ticket_id,
                from_variant,
                to_variant,
                company_id,
                reason,
                len(conversation_history),
            )
            return HandoffResult(
                success=True,
                handoff_context=context,
                message=(
                    f"Handoff created: {from_variant} → {to_variant} "
                    f"for ticket_id={ticket_id}"
                ),
                duplicate_prevented=False,
            )

        except Exception:
            logger.exception(
                "initiate_handoff failed for company_id=%s, "
                "ticket_id=%s, %s → %s — returning safe failure",
                company_id,
                ticket_id,
                from_variant,
                to_variant,
            )
            return HandoffResult(
                success=False,
                message="internal_error_during_handoff_creation",
            )

    def get_handoff_context(
        self,
        company_id: str,
        ticket_id: str,
        target_variant: str,
    ) -> Optional[HandoffContext]:
        """Retrieve the handoff context for a ticket and target variant.

        Returns the ``HandoffContext`` if a pending handoff exists, or
        ``None`` if no handoff is found.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns None on failure.
        """
        try:
            key = self._handoff_key(company_id, ticket_id, target_variant)
            with self._lock:
                context = self._handoffs.get(key)
            if context is not None:
                logger.debug(
                    "Handoff context retrieved for key=%s " "(acknowledged=%s)",
                    key,
                    context.acknowledged,
                )
            else:
                logger.debug(
                    "No handoff context found for key=%s",
                    key,
                )
            return context
        except Exception:
            logger.exception(
                "get_handoff_context failed for company_id=%s, "
                "ticket_id=%s, target=%s",
                company_id,
                ticket_id,
                target_variant,
            )
            return None

    def acknowledge_handoff(
        self,
        company_id: str,
        ticket_id: str,
        target_variant: str,
    ) -> bool:
        """Mark that the target variant has received and processed
        the handoff context.

        Once acknowledged, the handoff is removed from the active
        handoff list but remains in storage for audit purposes.

        Args:
            company_id: The company that owns the ticket (BC-001).
            ticket_id: The ticket that was handed off.
            target_variant: The variant that received the handoff.

        Returns:
            ``True`` if the handoff was successfully acknowledged,
            ``False`` if no pending handoff was found.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns False on failure.
        BC-012: Acknowledged-at timestamp is UTC.
        """
        try:
            key = self._handoff_key(company_id, ticket_id, target_variant)
            now = datetime.now(timezone.utc)

            with self._lock:
                context = self._handoffs.get(key)
                if context is None:
                    logger.debug(
                        "acknowledge_handoff: no handoff found for "
                        "key=%s (company_id=%s)",
                        key,
                        company_id,
                    )
                    return False

                if context.acknowledged:
                    logger.debug(
                        "acknowledge_handoff: handoff key=%s already "
                        "acknowledged (company_id=%s)",
                        key,
                        company_id,
                    )
                    return True

                context.acknowledged = True
                context.acknowledged_at = now

                # Remove from active handoffs
                active_keys = self._active_handoff_keys.get(company_id, [])
                if key in active_keys:
                    active_keys.remove(key)

            logger.info(
                "Handoff acknowledged: ticket_id=%s → %s " "(company_id=%s, key=%s)",
                ticket_id,
                target_variant,
                company_id,
                key,
            )
            return True

        except Exception:
            logger.exception(
                "acknowledge_handoff failed for company_id=%s, "
                "ticket_id=%s, target=%s",
                company_id,
                ticket_id,
                target_variant,
            )
            return False

    def get_active_handoffs(
        self,
        company_id: str,
    ) -> List[HandoffResult]:
        """Return all pending (unacknowledged) handoffs for a company.

        Each result contains the full ``HandoffContext`` so the caller
        can inspect the details.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns an empty list on failure.
        """
        try:
            results: List[HandoffResult] = []
            with self._lock:
                active_keys = self._active_handoff_keys.get(company_id, [])
                for key in active_keys:
                    context = self._handoffs.get(key)
                    if context is not None and not context.acknowledged:
                        results.append(
                            HandoffResult(
                                success=True,
                                handoff_context=context,
                                message=(
                                    "Active handoff: "
                                    f"{context.from_variant} → "
                                    f"{context.to_variant} for "
                                    f"ticket_id={context.ticket_id}"
                                ),
                            )
                        )

            logger.debug(
                "Active handoffs for company_id=%s: %d",
                company_id,
                len(results),
            )
            return results

        except Exception:
            logger.exception(
                "get_active_handoffs failed for company_id=%s",
                company_id,
            )
            return []

    # ═══════════════════════════════════════════════════════════════
    #  3. MULTI-VARIANT CONFLICT RESOLUTION
    # ═══════════════════════════════════════════════════════════════

    def _variant_tier_rank(self, variant_type: str) -> int:
        """Return the tier rank of a variant (0 = lowest, 2 = highest).

        Used to determine which variant's response to prefer during
        conflict resolution.
        """
        try:
            if variant_type in ESCALATION_CHAIN:
                return ESCALATION_CHAIN.index(variant_type)
            return -1
        except Exception:
            return -1

    def register_response(
        self,
        company_id: str,
        ticket_id: str,
        customer_id: str,
        variant_type: str,
        channel: str,
        response_content: str,
        confidence_score: float,
    ) -> ConflictCheckResult:
        """Register a variant's response and check for conflicts.

        Tracks all responses per customer and checks whether the new
        response conflicts with existing responses from **other**
        variants on **different** channels within the configured time
        window (``CONFLICT_TIME_WINDOW_SECONDS``).

        Conflict detection only triggers when the new response comes
        from a *different* variant than an existing response and on a
        *different* channel within the time window.  Responses from
        the same variant or on the same channel are not considered
        conflicts.

        Args:
            company_id: The company that owns the ticket (BC-001).
            ticket_id: The ticket the response belongs to.
            customer_id: The customer who received the response.
            variant_type: The variant that generated the response.
            channel: The channel through which it was delivered.
            response_content: The actual response text.
            confidence_score: The confidence score of the response.

        Returns:
            A ``ConflictCheckResult`` indicating whether a conflict
            was detected.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a safe default on failure.
        BC-012: All timestamps UTC.
        """
        try:
            now = datetime.now(timezone.utc)

            # Clamp confidence score
            clamped_confidence = max(0.0, min(1.0, confidence_score))

            response = RegisteredResponse(
                ticket_id=ticket_id,
                customer_id=customer_id,
                variant_type=variant_type,
                channel=channel,
                response_content=response_content,
                confidence_score=clamped_confidence,
                timestamp=now,
            )

            # Store the response
            with self._lock:
                if company_id not in self._customer_interactions:
                    self._customer_interactions[company_id] = {}
                if customer_id not in self._customer_interactions[company_id]:
                    self._customer_interactions[company_id][customer_id] = []
                self._customer_interactions[company_id][customer_id].append(
                    response,
                )

            # Check for conflicts
            conflicts = self._detect_conflicts_for_response(
                company_id=company_id,
                customer_id=customer_id,
                new_response=response,
            )

            if not conflicts:
                logger.info(
                    "Response registered: ticket_id=%s, customer_id=%s, "
                    "variant=%s, channel=%s (no conflicts) "
                    "(company_id=%s)",
                    ticket_id,
                    customer_id,
                    variant_type,
                    channel,
                    company_id,
                )
                return ConflictCheckResult(
                    has_conflict=False,
                    customer_id=customer_id,
                )

            # Create a ConflictResult for the first detected conflict
            conflict_id = str(uuid.uuid4())
            all_conflicting = [response] + conflicts
            severity = self._assess_conflict_severity(all_conflicting)
            strategy = self._determine_resolution_strategy(severity)

            conflict = ConflictResult(
                conflict_id=conflict_id,
                customer_id=customer_id,
                responses=all_conflicting,
                severity=severity,
                resolution_strategy=strategy,
                detected_at=now,
                resolved=False,
            )

            with self._lock:
                self._conflicts[conflict_id] = conflict
                if company_id not in self._customer_conflicts:
                    self._customer_conflicts[company_id] = {}
                if customer_id not in self._customer_conflicts[company_id]:
                    self._customer_conflicts[company_id][customer_id] = []
                self._customer_conflicts[company_id][customer_id].append(
                    conflict_id,
                )

            logger.warning(
                "CONFLICT DETECTED: conflict_id=%s, customer_id=%s, "
                "severity=%s, strategy=%s, responses=%d "
                "(company_id=%s)",
                conflict_id,
                customer_id,
                severity.value,
                strategy.value,
                len(all_conflicting),
                company_id,
            )
            return ConflictCheckResult(
                has_conflict=True,
                conflict_id=conflict_id,
                severity=severity,
                conflicting_responses=all_conflicting,
                customer_id=customer_id,
            )

        except Exception:
            logger.exception(
                "register_response failed for company_id=%s, "
                "ticket_id=%s, customer_id=%s — returning safe "
                "no-conflict result",
                company_id,
                ticket_id,
                customer_id,
            )
            return ConflictCheckResult(
                has_conflict=False,
                customer_id=customer_id,
            )

    def _detect_conflicts_for_response(
        self,
        company_id: str,
        customer_id: str,
        new_response: RegisteredResponse,
    ) -> List[RegisteredResponse]:
        """Find existing responses that conflict with the new one.

        A conflict exists when an existing response:
        - Is from a **different** variant
        - Is on a **different** channel
        - Falls within the ``CONFLICT_TIME_WINDOW_SECONDS`` of the
          new response

        Returns a list of conflicting ``RegisteredResponse`` objects.
        """
        try:
            conflicting: List[RegisteredResponse] = []
            now = new_response.timestamp

            with self._lock:
                interactions = self._customer_interactions.get(
                    company_id,
                    {},
                ).get(customer_id, [])

            for existing in interactions:
                # Skip the response we just registered
                if existing is new_response:
                    continue

                # Same variant or same channel — not a conflict
                if (
                    existing.variant_type == new_response.variant_type
                    or existing.channel == new_response.channel
                ):
                    continue

                # Check time window
                time_delta = (now - existing.timestamp).total_seconds()
                if abs(time_delta) <= CONFLICT_TIME_WINDOW_SECONDS:
                    conflicting.append(existing)

            return conflicting

        except Exception:
            logger.exception(
                "_detect_conflicts_for_response failed for " "customer_id=%s",
                customer_id,
            )
            return []

    def _assess_conflict_severity(
        self,
        responses: List[RegisteredResponse],
    ) -> ConflictSeverity:
        """Assess the severity of a conflict between responses.

        Uses a simple heuristic based on response content similarity
        and confidence delta:

        - **LOW**: Responses are substantively similar (high confidence
          overlap, no contradictions).
        - **MEDIUM**: Responses differ slightly but are not
          contradictory (moderate confidence delta).
        - **HIGH**: Responses are contradictory or have very different
          confidence levels from different tier variants.

        In production this could use embedding similarity or a more
        sophisticated NLP comparison.
        """
        try:
            if len(responses) < 2:
                return ConflictSeverity.LOW

            # Extract confidence scores
            scores = [r.confidence_score for r in responses]
            max_conf = max(scores) if scores else 0.0
            min_conf = min(scores) if scores else 0.0
            conf_delta = max_conf - min_conf

            # Extract variant tiers
            tiers = [self._variant_tier_rank(r.variant_type) for r in responses]
            tier_delta = max(tiers) - min(tiers) if tiers else 0

            # Check for near-identical content (simple heuristic)
            content_set = set(r.response_content.strip().lower() for r in responses)
            content_identical = len(content_set) <= 1

            if content_identical:
                return ConflictSeverity.LOW

            # Large confidence delta + different tiers = likely contradiction
            if conf_delta > 0.40 and tier_delta >= 2:
                return ConflictSeverity.HIGH

            # Moderate differences
            if conf_delta > 0.20 or tier_delta >= 1:
                return ConflictSeverity.MEDIUM

            # Small differences from nearby variants on different channels
            return ConflictSeverity.LOW

        except Exception:
            logger.exception("_assess_conflict_severity failed")
            return ConflictSeverity.LOW

    def _determine_resolution_strategy(
        self,
        severity: ConflictSeverity,
    ) -> ResolutionStrategy:
        """Map a conflict severity to a resolution strategy.

        - LOW → ``NO_ACTION`` — similar responses, no action needed.
        - MEDIUM → ``MERGE_PREFER_HIGH_CONFIDENCE`` — merge, prefer
          higher-confidence response.
        - HIGH → ``HUMAN_REVIEW`` — contradictory, flag for human.
        """
        try:
            strategy_map = {
                ConflictSeverity.LOW: ResolutionStrategy.NO_ACTION,
                ConflictSeverity.MEDIUM: ResolutionStrategy.MERGE_PREFER_HIGH_CONFIDENCE,
                ConflictSeverity.HIGH: ResolutionStrategy.HUMAN_REVIEW,
            }
            return strategy_map.get(severity, ResolutionStrategy.NO_ACTION)
        except Exception:
            logger.exception("_determine_resolution_strategy failed")
            return ResolutionStrategy.NO_ACTION

    def check_conflicts(
        self,
        company_id: str,
        customer_id: str,
    ) -> List[ConflictResult]:
        """Check for all active (unresolved) conflicts for a customer.

        Returns a list of ``ConflictResult`` objects representing each
        unresolved conflict.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns an empty list on failure.
        """
        try:
            results: List[ConflictResult] = []

            with self._lock:
                conflict_ids = self._customer_conflicts.get(company_id, {}).get(
                    customer_id, []
                )

                for cid in conflict_ids:
                    conflict = self._conflicts.get(cid)
                    if conflict is not None and not conflict.resolved:
                        results.append(conflict)

            logger.debug(
                "Active conflicts for customer_id=%s, " "company_id=%s: %d",
                customer_id,
                company_id,
                len(results),
            )
            return results

        except Exception:
            logger.exception(
                "check_conflicts failed for company_id=%s, " "customer_id=%s",
                company_id,
                customer_id,
            )
            return []

    def resolve_conflict(
        self,
        company_id: str,
        conflict_id: str,
        strategy: ResolutionStrategy,
    ) -> ResolutionResult:
        """Resolve a detected multi-variant conflict.

        Applies the specified resolution strategy:

        - ``NO_ACTION``: Marks the conflict as resolved with the
          first response as the final answer.
        - ``MERGE_PREFER_HIGH_CONFIDENCE``: Uses the response with
          the highest confidence score as the final answer.
        - ``HUMAN_REVIEW``: Marks the conflict as resolved (human
          reviewed it), uses the highest-tier variant's response.

        Args:
            company_id: The company that owns the conflict (BC-001).
            conflict_id: The unique conflict identifier.
            strategy: The resolution strategy to apply.

        Returns:
            A ``ResolutionResult`` with the final response and
            details of what was done.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a safe default on failure.
        """
        try:
            with self._lock:
                conflict = self._conflicts.get(conflict_id)

            if conflict is None:
                logger.warning(
                    "resolve_conflict: conflict_id=%s not found " "(company_id=%s)",
                    conflict_id,
                    company_id,
                )
                return ResolutionResult(
                    resolved=False,
                    conflict_id=conflict_id,
                    message=f"conflict {conflict_id} not found",
                )

            if conflict.resolved:
                logger.info(
                    "resolve_conflict: conflict_id=%s already resolved "
                    "(company_id=%s)",
                    conflict_id,
                    company_id,
                )
                return ResolutionResult(
                    resolved=True,
                    final_response=(
                        conflict.responses[0].response_content
                        if conflict.responses
                        else ""
                    ),
                    strategy_used=conflict.resolution_strategy,
                    conflicts_merged=1,
                    conflict_id=conflict_id,
                    message=f"conflict {conflict_id} already resolved",
                )

            responses = conflict.responses
            final_response = ""

            if strategy == ResolutionStrategy.NO_ACTION:
                # Keep the first response as-is
                final_response = responses[0].response_content if responses else ""

            elif strategy == ResolutionStrategy.MERGE_PREFER_HIGH_CONFIDENCE:
                # Pick the highest-confidence response
                best = max(responses, key=lambda r: r.confidence_score)
                final_response = best.response_content
                logger.info(
                    "MERGE: selected response from %s "
                    "(confidence=%.3f) for conflict_id=%s",
                    best.variant_type,
                    best.confidence_score,
                    conflict_id,
                )

            elif strategy == ResolutionStrategy.HUMAN_REVIEW:
                # Use the highest-tier variant's response
                best = max(
                    responses,
                    key=lambda r: self._variant_tier_rank(r.variant_type),
                )
                final_response = best.response_content
                logger.info(
                    "HUMAN REVIEW: using response from %s (tier %d) "
                    "for conflict_id=%s — flagged for human oversight",
                    best.variant_type,
                    self._variant_tier_rank(best.variant_type),
                    conflict_id,
                )

            else:
                # Unknown strategy — default to first response
                final_response = responses[0].response_content if responses else ""
                logger.warning(
                    "resolve_conflict: unknown strategy '%s' for "
                    "conflict_id=%s — using first response as default",
                    (
                        strategy.value
                        if isinstance(strategy, ResolutionStrategy)
                        else strategy
                    ),
                    conflict_id,
                )

            # Mark conflict as resolved
            with self._lock:
                if conflict_id in self._conflicts:
                    self._conflicts[conflict_id].resolved = True

            logger.info(
                "Conflict resolved: conflict_id=%s, strategy=%s, "
                "responses_merged=%d (company_id=%s)",
                conflict_id,
                strategy.value,
                len(responses),
                company_id,
            )
            return ResolutionResult(
                resolved=True,
                final_response=final_response,
                strategy_used=strategy,
                conflicts_merged=len(responses),
                conflict_id=conflict_id,
                message=(
                    f"Conflict {conflict_id} resolved using "
                    f"{strategy.value} strategy — "
                    f"{len(responses)} responses merged"
                ),
            )

        except Exception:
            logger.exception(
                "resolve_conflict failed for company_id=%s, "
                "conflict_id=%s — returning safe failure",
                company_id,
                conflict_id,
            )
            return ResolutionResult(
                resolved=False,
                conflict_id=conflict_id,
                message="internal_error_during_resolution",
            )

    def get_customer_interaction_summary(
        self,
        company_id: str,
        customer_id: str,
    ) -> CustomerInteractionSummary:
        """Return a comprehensive summary of a customer's recent
        interactions across all variants and channels.

        The summary includes total interaction count, variants used,
        channels used, the timestamp of the last interaction, and
        any active unresolved conflicts.

        BC-001: company_id is first parameter.
        BC-008: Never crashes — returns a safe default on failure.
        """
        try:
            with self._lock:
                interactions = self._customer_interactions.get(company_id, {}).get(
                    customer_id, []
                )

                conflict_ids = self._customer_conflicts.get(company_id, {}).get(
                    customer_id, []
                )

                active_conflict_ids: List[str] = []
                for cid in conflict_ids:
                    c = self._conflicts.get(cid)
                    if c is not None and not c.resolved:
                        active_conflict_ids.append(cid)

            if not interactions:
                logger.debug(
                    "No interactions found for customer_id=%s, " "company_id=%s",
                    customer_id,
                    company_id,
                )
                return CustomerInteractionSummary(
                    customer_id=customer_id,
                    total_interactions=0,
                    variants_used=[],
                    channels_used=[],
                    last_interaction_at=None,
                    active_conflicts=active_conflict_ids,
                    interactions_by_variant={},
                )

            # Compute summary stats
            variants = sorted(set(r.variant_type for r in interactions))
            channels = sorted(set(r.channel for r in interactions))
            last_at = max(r.timestamp for r in interactions)
            variant_counts: Dict[str, int] = {}
            for r in interactions:
                variant_counts[r.variant_type] = (
                    variant_counts.get(r.variant_type, 0) + 1
                )

            logger.debug(
                "Interaction summary for customer_id=%s, "
                "company_id=%s: %d interactions, variants=%s, "
                "channels=%s, active_conflicts=%d",
                customer_id,
                company_id,
                len(interactions),
                variants,
                channels,
                len(active_conflict_ids),
            )
            return CustomerInteractionSummary(
                customer_id=customer_id,
                total_interactions=len(interactions),
                variants_used=variants,
                channels_used=channels,
                last_interaction_at=last_at,
                active_conflicts=active_conflict_ids,
                interactions_by_variant=variant_counts,
            )

        except Exception:
            logger.exception(
                "get_customer_interaction_summary failed for "
                "company_id=%s, customer_id=%s",
                company_id,
                customer_id,
            )
            return CustomerInteractionSummary(
                customer_id=customer_id,
                total_interactions=0,
                variants_used=[],
                channels_used=[],
                last_interaction_at=None,
                active_conflicts=[],
                interactions_by_variant={},
            )
