"""
GSD State Engine (F-053) — Guided Support Dialogue

Manages multi-step conversation states for the PARWA support pipeline.
The engine is a deterministic state machine with AI-driven next-state
determination, escalation handling, and per-variant configuration.

States (GSDState enum):
    NEW → GREETING → DIAGNOSIS → RESOLUTION → FOLLOW_UP → CLOSED
                                            ↘ ESCALATE → HUMAN_HANDOFF → DIAGNOSIS

Variant Support:
    mini_parwa  — Simplified linear flow (NEW → GREETING → DIAGNOSIS → RESOLUTION → CLOSED)
    parwa       — Full transitions with escalation support
    high_parwa  — Full transitions + HUMAN_HANDOFF loop + DIAGNOSIS loop

Design Patterns:
    - structlog for all logging and event emission
    - dataclasses for configuration
    - async methods throughout
    - BC-001: company_id scoping
    - BC-008: graceful degradation (never crash)

Parent: Week 10 Day 11 (Thursday)
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger

if TYPE_CHECKING:
    from app.core.techniques.base import ConversationState as _ConversationState  # noqa: F401
    ConversationState = _ConversationState

logger = get_logger("gsd_engine")


# ══════════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════════


class GSDEngineError(Exception):
    """Base exception for the GSD State Engine."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class InvalidTransitionError(GSDEngineError):
    """Raised when an illegal state transition is attempted.

    Attributes:
        from_state: The current GSDState before the transition attempt.
        to_state: The target GSDState that was rejected.
        reason: Human-readable explanation of why the transition is illegal.
    """

    def __init__(
        self,
        from_state: str,
        to_state: str,
        reason: str = "transition not permitted",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            message=f"Invalid transition: {from_state} → {to_state} ({reason})",
            details={
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                **(details or {}),
            },
        )


class EscalationCooldownError(GSDEngineError):
    """Raised when an escalation is attempted during the cooldown period.

    The cooldown prevents rapid re-escalation (default: 5 minutes) to
    avoid thrashing between AI and human agents.
    """

    def __init__(
        self,
        cooldown_remaining_seconds: float,
        last_escalation_time: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.cooldown_remaining_seconds = cooldown_remaining_seconds
        self.last_escalation_time = last_escalation_time
        super().__init__(
            message=(
                f"Escalation cooldown active: "
                f"{cooldown_remaining_seconds:.1f}s remaining"
            ),
            details={
                "cooldown_remaining_seconds": cooldown_remaining_seconds,
                "last_escalation_time": last_escalation_time,
                **(details or {}),
            },
        )


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION DATA CLASSES
# ══════════════════════════════════════════════════════════════════


class GSDVariant(str, Enum):
    """PARWA variant identifiers for GSD configuration."""
    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    PARWA_HIGH = "high_parwa"


@dataclass
class GSDConfig:
    """Per-tenant GSD state engine configuration.

    Attributes:
        company_id: Tenant identifier (BC-001).
        variant: PARWA variant determining available transitions.
        frustration_threshold: Frustration score (0-100) triggering escalation.
        confidence_threshold: Minimum classification confidence for DIAGNOSIS→RESOLUTION.
        escalation_cooldown_seconds: Seconds between allowed escalations.
        max_diagnosis_loops: Max loops before auto-escalation.
        max_history_entries: Ring buffer size for gsd_history.
        auto_close_intents: Intent types eligible for auto-close after RESOLUTION.
        auto_close_delay_seconds: Seconds to wait before auto-closing.
        vip_tiers: Customer tiers treated as VIP (escalation priority).
    """

    company_id: str = ""
    variant: str = GSDVariant.PARWA.value
    frustration_threshold: float = 80.0
    confidence_threshold: float = 0.6
    escalation_cooldown_seconds: float = 300.0  # 5 minutes
    max_diagnosis_loops: int = 3
    max_history_entries: int = 100
    auto_close_intents: List[str] = field(default_factory=lambda: [
        "billing", "faq", "inquiry", "feedback", "general",
    ])
    auto_close_delay_seconds: float = 30.0
    vip_tiers: List[str] = field(default_factory=lambda: [
        "enterprise", "vip",
    ])


@dataclass
class TransitionRecord:
    """A single entry in the GSD state history.

    Attributes:
        state: The GSDState value after the transition.
        timestamp: ISO 8601 UTC timestamp of when the transition occurred.
        trigger: Human-readable reason for the transition.
        metadata: Additional context (signals, scores, etc.).
    """

    state: str
    timestamp: str
    trigger: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "state": self.state,
            "timestamp": self.timestamp,
            "trigger": self.trigger,
            "metadata": self.metadata,
        }


@dataclass
class TransitionEvent:
    """Event emitted on each state transition.

    Attributes:
        ticket_id: Optional ticket identifier.
        from_state: GSDState value before transition.
        to_state: GSDState value after transition.
        trigger_reason: Why the transition occurred.
        timestamp: ISO 8601 UTC timestamp.
        company_id: Tenant identifier.
        metadata: Additional context.
    """

    ticket_id: Optional[str]
    from_state: str
    to_state: str
    trigger_reason: str
    timestamp: str
    company_id: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# STATE TRANSITION TABLE
# ══════════════════════════════════════════════════════════════════

# Full transition table for PARWA and PARWA_HIGH variants.
# Key: current GSDState value → Set of valid target GSDState values.
FULL_TRANSITION_TABLE: Dict[str, Set[str]] = {
    "new": {"greeting"},
    "greeting": {"diagnosis"},
    "diagnosis": {"resolution", "escalate"},
    "resolution": {"follow_up", "closed"},
    "follow_up": {"closed", "diagnosis"},
    "escalate": {"human_handoff"},
    "human_handoff": {"diagnosis"},
    "closed": {"new"},
}

# Simplified transition table for MINI_PARWA variant.
# No escalation or human handoff support.
MINI_TRANSITION_TABLE: Dict[str, Set[str]] = {
    "new": {"greeting"},
    "greeting": {"diagnosis"},
    "diagnosis": {"resolution"},
    "resolution": {"closed"},
    "follow_up": {"closed"},
    "escalate": set(),  # not available
    "human_handoff": set(),  # not available
    "closed": {"new"},
}

# Escalation-eligible states (any state can escalate to ESCALATE).
ESCALATION_ELIGIBLE_STATES: Set[str] = {
    "greeting", "diagnosis", "resolution", "follow_up",
}


# ══════════════════════════════════════════════════════════════════
# TRANSITION TRIGGER CONSTANTS
# ══════════════════════════════════════════════════════════════════

# Phrases indicating customer satisfaction (for FOLLOW_UP→CLOSED).
SATISFACTION_PHRASES: Set[str] = {
    "thanks", "thank you", "thx", "ty", "appreciate it",
    "resolved", "that works", "that worked", "perfect",
    "great", "awesome", "excellent", "all good", "sorted",
    "problem solved", "fixed", "got it", "makes sense",
    "yes that's it", "exactly what I needed", "done",
    "no further questions", "that's all", "nothing else",
}

# Legal/sensitive intents that force escalation.
LEGAL_INTENTS: Set[str] = {
    "legal", "lawsuit", "attorney", "sue", "litigation",
    "regulatory", "compliance", "breach", "gdpr",
    "subpoena", "court", "defamation",
}

# Simple intents eligible for auto-close after resolution.
SIMPLE_RESOLUTION_INTENTS: Set[str] = {
    "billing", "faq", "inquiry", "feedback", "general",
    "shipping", "account",
}

# Phrases that indicate the customer has a new/ different question
# (for FOLLOW_UP→DIAGNOSIS).
NEW_ISSUE_PHRASES: Set[str] = {
    "also", "another thing", "one more question", "while I'm here",
    "by the way", "additionally", "unrelated", "different issue",
    "new problem", "separate question", "actually i also",
    "i also need", "there's something else",
}

# Diagnostic question templates per intent type.
DIAGNOSTIC_QUESTIONS: Dict[str, List[str]] = {
    "refund": [
        "Could you provide your order number so I can look up the transaction?",
        "What was the reason for the refund request?",
        "When did you place this order?",
    ],
    "technical": [
        "Can you describe the error message you're seeing?",
        "What device and browser are you using?",
        "When did this issue first start occurring?",
        "Have you tried clearing your cache or restarting the app?",
    ],
    "billing": [
        "Could you share the invoice or charge amount in question?",
        "Is this a one-time charge or a recurring subscription?",
        "What payment method was used?",
    ],
    "complaint": [
        "I'm sorry to hear about your experience. Can you tell me more details?",
        "Which team or service was this regarding?",
        "What outcome are you hoping for?",
    ],
    "shipping": [
        "What is your tracking number or order reference?",
        "What was the expected delivery date?",
        "What is your shipping address?",
    ],
    "account": [
        "What is the email address associated with your account?",
        "Are you able to log in at all, or is access completely blocked?",
        "Have you recently changed your password or email?",
    ],
    "cancellation": [
        "What is your account email or subscription ID?",
        "Is there a specific reason you'd like to cancel?",
        "Would you like to explore any alternatives before canceling?",
    ],
    "feature_request": [
        "Can you describe the feature you'd like to see in more detail?",
        "How would this feature help your workflow?",
        "Are there any existing workarounds you've tried?",
    ],
    "general": [
        "Could you provide more details about your question?",
        "What have you already tried so far?",
    ],
    "inquiry": [
        "What specific information are you looking for?",
        "Is this related to a particular feature or service?",
    ],
    "feedback": [
        "Thank you for your feedback! What specific aspect would you like to comment on?",
        "Is this positive feedback, or is there something we could improve?",
    ],
    "escalation": [
        "I understand your concern. Let me connect you with a senior team member.",
        "Could you briefly summarize the issue so I can escalate it properly?",
    ],
    "legal": [
        "I understand this is a sensitive matter. Let me connect you with the appropriate team.",
        "Could you provide more context so I can route this to the right department?",
    ],
}

# Estimated resolution time (minutes) per intent + complexity combination.
RESOLUTION_TIME_ESTIMATES: Dict[str, Dict[str, int]] = {
    "refund": {"low": 5, "medium": 15, "high": 30},
    "technical": {"low": 10, "medium": 25, "high": 60},
    "billing": {"low": 5, "medium": 15, "high": 45},
    "complaint": {"low": 15, "medium": 30, "high": 60},
    "shipping": {"low": 5, "medium": 15, "high": 30},
    "account": {"low": 5, "medium": 20, "high": 45},
    "cancellation": {"low": 5, "medium": 10, "high": 20},
    "feature_request": {"low": 5, "medium": 10, "high": 15},
    "general": {"low": 3, "medium": 8, "high": 15},
    "inquiry": {"low": 3, "medium": 8, "high": 15},
    "feedback": {"low": 2, "medium": 5, "high": 10},
    "escalation": {"low": 20, "medium": 45, "high": 90},
    "legal": {"low": 30, "medium": 60, "high": 120},
}

# Default estimates for unknown intents.
DEFAULT_RESOLUTION_ESTIMATE: Dict[str, int] = {
    "low": 10, "medium": 20, "high": 45,
}


# ══════════════════════════════════════════════════════════════════
# GSD STATE ENGINE
# ══════════════════════════════════════════════════════════════════


class GSDEngine:
    """GSD State Engine (F-053) — Guided Support Dialogue.

    Manages multi-step conversation states for the PARWA support
    pipeline. Implements a deterministic state machine with AI-driven
    next-state determination, escalation handling, and per-variant
    configuration.

    All public methods are async. Operations are scoped to company_id
    per BC-001. Errors are handled gracefully per BC-008.

    Usage::

        engine = GSDEngine()
        config = GSDConfig(company_id="co_123", variant="parwa")
        engine.update_config("co_123", config)

        state = ConversationState(query="I want a refund")
        state = await engine.transition(state, GSDState.GREETING)
        next_state = await engine.get_next_state(state)
    """

    def __init__(self) -> None:
        """Initialize the GSD State Engine."""
        self._tenant_configs: Dict[str, GSDConfig] = {}
        self._escalation_timestamps: Dict[str, str] = {}  # company_id → ISO timestamp
        logger.info("gsd_engine_initialized")

    # ── Configuration Management ──────────────────────────────────

    def update_config(self, company_id: str, config: GSDConfig) -> None:
        """Cache a tenant-specific GSD configuration.

        Args:
            company_id: Tenant identifier (BC-001).
            config: The GSD configuration to cache.
        """
        config.company_id = company_id
        self._tenant_configs[company_id] = config
        logger.info(
            "gsd_config_updated",
            company_id=company_id,
            variant=config.variant,
            frustration_threshold=config.frustration_threshold,
            confidence_threshold=config.confidence_threshold,
        )

    def get_config(self, company_id: str) -> GSDConfig:
        """Get the GSD configuration for a tenant.

        Falls back to default PARWA configuration if no tenant
        override exists.

        Args:
            company_id: Tenant identifier (BC-001).

        Returns:
            GSDConfig for the tenant.
        """
        if company_id and company_id in self._tenant_configs:
            return self._tenant_configs[company_id]
        return GSDConfig(company_id=company_id or "")

    def get_variant(self, company_id: Optional[str]) -> str:
        """Resolve the PARWA variant for a tenant.

        Args:
            company_id: Optional tenant identifier.

        Returns:
            Variant string (mini_parwa, parwa, high_parwa).
        """
        if company_id:
            config = self._tenant_configs.get(company_id)
            if config:
                return config.variant
        return GSDVariant.PARWA.value

    # ── Variant Resolution ──────────────────────────────────────

    def _get_variant_for_company(self, company_id: Optional[str]) -> str:
        """Get variant type for a company from the variant capability service.

        Tries the VariantCapabilityService first for authoritative variant
        lookup, then falls back to the cached tenant config, and finally
        defaults to "parwa" (BC-008: never crash).

        Args:
            company_id: Tenant identifier.

        Returns:
            Variant string (mini_parwa, parwa, high_parwa).
        """
        # 1. Try cached tenant config first (fast path)
        if company_id:
            config = self._tenant_configs.get(company_id)
            if config:
                return config.variant

        # 2. Try VariantCapabilityService for authoritative lookup
        if company_id:
            try:
                from app.services.variant_capability_service import VariantCapabilityService
                service = VariantCapabilityService()
                caps = service.get_variant_capabilities(company_id)
                if caps and hasattr(caps, 'variant_type'):
                    return caps.variant_type
            except Exception:
                # BC-008: Service unavailable — fall through to default
                pass

        return "parwa"  # Default

    # ── Transition Table Access ───────────────────────────────────

    def _get_transition_table(self, variant: str) -> Dict[str, Set[str]]:
        """Get the transition table for a given variant.

        Args:
            variant: PARWA variant identifier.

        Returns:
            Transition table mapping state → set of valid next states.
        """
        if variant == GSDVariant.MINI_PARWA.value:
            return MINI_TRANSITION_TABLE
        return FULL_TRANSITION_TABLE

    # ── Core State Machine Methods ────────────────────────────────

    async def transition(
        self,
        state: ConversationState,
        target_state: Any,
        trigger_reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationState:
        """Execute a state transition with full validation.

        Validates the transition is legal, updates the conversation
        state, records history, and emits a structured log event.

        Args:
            state: The current ConversationState (mutated and returned).
            target_state: The GSDState to transition to.
            trigger_reason: Human-readable explanation for the transition.
            metadata: Optional additional context for the history record.

        Returns:
            Updated ConversationState with new gsd_state and history.

        Raises:
            InvalidTransitionError: If the transition is not legal.
        """
        from app.core.techniques.base import GSDState

        # Normalize target_state to string for comparison
        target_str = target_state.value if isinstance(target_state, GSDState) else str(target_state)
        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)

        # Validate the transition using variant-aware check (BC-001)
        variant = self._get_variant_for_company(state.company_id)
        if not await self.can_transition_with_variant(state.gsd_state, target_state, variant):
            reason = await self._explain_invalid_transition(current_str, target_str, state)
            raise InvalidTransitionError(
                from_state=current_str,
                to_state=target_str,
                reason=reason,
            )

        # Auto-escalation check (unless this IS an escalation transition)
        if target_str != "escalate" and await self._should_auto_escalate(state):
            escalation_trigger = await self._get_escalation_reason(state)
            logger.warning(
                "auto_escalation_override",
                ticket_id=state.ticket_id,
                company_id=state.company_id,
                original_target=target_str,
                escalation_reason=escalation_trigger,
            )
            # Override target to escalate
            return await self.transition(
                state,
                GSDState.ESCALATE,
                trigger_reason=f"auto_escalation: {escalation_trigger}",
                metadata=metadata,
            )

        # Execute the transition
        previous_state = current_str
        state.gsd_state = target_state

        # Record in history (ring buffer)
        record = TransitionRecord(
            state=target_str,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger=trigger_reason or self._default_trigger(previous_state, target_str),
            metadata=metadata or {},
        )
        self._append_history(state, record)

        # Emit transition event
        self._emit_transition_event(
            ticket_id=state.ticket_id,
            from_state=previous_state,
            to_state=target_str,
            trigger_reason=trigger_reason or record.trigger,
            company_id=state.company_id,
            metadata=metadata,
        )

        logger.info(
            "gsd_state_transition",
            ticket_id=state.ticket_id,
            company_id=state.company_id,
            from_state=previous_state,
            to_state=target_str,
            trigger=trigger_reason or record.trigger,
        )

        # Post-transition hooks
        if target_str == "escalate":
            self._record_escalation_timestamp(state.company_id)

        return state

    async def get_next_state(self, state: ConversationState) -> Any:
        """Determine the AI-driven next state for a conversation.

        Analyzes signals from ConversationState (sentiment, intent,
        confidence, frustration) to determine the most appropriate
        next state.

        Args:
            state: Current ConversationState.

        Returns:
            The recommended GSDState for the next transition.
        """
        from app.core.techniques.base import GSDState

        current = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)
        variant = self.get_variant(state.company_id)

        # Check for auto-escalation first (except in mini_parwa)
        if variant != GSDVariant.MINI_PARWA.value and await self._should_auto_escalate(state):
            return GSDState.ESCALATE

        # State-specific next-state logic
        if current == "new":
            return GSDState.GREETING

        if current == "greeting":
            # After greeting, always move to diagnosis
            return GSDState.DIAGNOSIS

        if current == "diagnosis":
            return await self._determine_diagnosis_next(state, variant)

        if current == "resolution":
            return await self._determine_resolution_next(state, variant)

        if current == "follow_up":
            return await self._determine_follow_up_next(state, variant)

        if current == "escalate":
            # Escalate → HUMAN_HANDOFF is automatic
            return GSDState.HUMAN_HANDOFF

        if current == "human_handoff":
            # After human agent resolves, return to diagnosis
            return GSDState.DIAGNOSIS

        if current == "closed":
            # If new message arrives on closed ticket, reopen
            return GSDState.NEW

        # Fallback: stay in current state
        logger.warning(
            "gsd_unknown_state_staying",
            current_state=current,
            ticket_id=state.ticket_id,
            company_id=state.company_id,
        )
        return state.gsd_state

    async def is_terminal(self, state: ConversationState) -> bool:
        """Check if the conversation is in a terminal state.

        Terminal states are CLOSED and HUMAN_HANDOFF (from the AI's
        perspective — the conversation requires human action or is done).

        Args:
            state: Current ConversationState.

        Returns:
            True if in a terminal state, False otherwise.
        """
        from app.core.techniques.base import GSDState

        terminal_states = {GSDState.CLOSED, GSDState.HUMAN_HANDOFF}
        return state.gsd_state in terminal_states

    async def can_transition(
        self, current: Any, target: Any,
    ) -> bool:
        """Validate whether a state transition is legal.

        Checks the transition table for the appropriate variant. Also
        handles the universal escalation rule: any non-terminal state
        can escalate.

        Args:
            current: Current GSDState (enum or string value).
            target: Target GSDState (enum or string value).

        Returns:
            True if the transition is legal, False otherwise.
        """
        from app.core.techniques.base import GSDState

        # Normalize to strings
        current_str = current.value if isinstance(current, GSDState) else str(current)
        target_str = target.value if isinstance(target, GSDState) else str(target)

        # Determine variant (use default PARWA for standalone checks)
        # When called with ConversationState context, variant is resolved
        # elsewhere; this uses a safe default for simple validity checks.
        table = FULL_TRANSITION_TABLE

        # Universal escalation rule: any state in ESCALATION_ELIGIBLE_STATES
        # can transition to ESCALATE (except CLOSED and HUMAN_HANDOFF)
        if target_str == "escalate" and current_str in ESCALATION_ELIGIBLE_STATES:
            return True

        # Check transition table
        allowed = table.get(current_str, set())
        return target_str in allowed

    async def can_transition_with_variant(
        self,
        current: Any,
        target: Any,
        variant: str,
    ) -> bool:
        """Validate transition legality with explicit variant context.

        This method enforces strict state machine rules per variant:
        - MINI_PARWA: Linear flow only (NEW → GREETING → DIAGNOSIS → RESOLUTION → CLOSED)
        - PARWA: Full flow with escalation support
        - PARWA_HIGH: Full flow with DIAGNOSIS loop after HUMAN_HANDOFF

        CRITICAL: This validation prevents invalid transitions that could
        break the conversation flow and customer experience.

        Args:
            current: Current GSDState (enum or string value).
            target: Target GSDState (enum or string value).
            variant: PARWA variant identifier.

        Returns:
            True if the transition is legal for the given variant.
        """
        from app.core.techniques.base import GSDState

        current_str = current.value if isinstance(current, GSDState) else str(current)
        target_str = target.value if isinstance(target, GSDState) else str(target)

        # Normalize to lowercase for comparison
        current_str = current_str.lower().strip()
        target_str = target_str.lower().strip()

        table = self._get_transition_table(variant)

        # Universal escalation rule (not available in mini_parwa)
        if target_str == "escalate":
            if variant == GSDVariant.MINI_PARWA.value:
                return False
            return current_str in ESCALATION_ELIGIBLE_STATES

        # Check if transition is explicitly allowed in the table
        allowed = table.get(current_str, set())
        
        # GAP 5 FIX: Ensure strict validation - target must be in allowed set
        # This prevents skipping states like DIAGNOSIS → FOLLOW_UP (skipping RESOLUTION)
        is_allowed = target_str in allowed
        
        if not is_allowed:
            logger.debug(
                "transition_validation_failed",
                current_state=current_str,
                target_state=target_str,
                variant=variant,
                allowed_transitions=list(allowed),
            )
        
        return is_allowed

    async def get_available_transitions(
        self, current: Any, variant: Optional[str] = None,
    ) -> List[Any]:
        """List all valid next states from the current state.

        Args:
            current: Current GSDState (enum or string value).
            variant: Optional PARWA variant. Defaults to "parwa".

        Returns:
            Sorted list of valid target GSDState values.
        """
        from app.core.techniques.base import GSDState

        current_str = current.value if isinstance(current, GSDState) else str(current)
        resolved_variant = variant or GSDVariant.PARWA.value
        table = self._get_transition_table(resolved_variant)

        allowed = set(table.get(current_str, set()))

        # Add escalation if eligible (not in mini_parwa)
        if resolved_variant != GSDVariant.MINI_PARWA.value:
            if current_str in ESCALATION_ELIGIBLE_STATES:
                allowed.add("escalate")

        # Convert strings back to GSDState enum values
        result = []
        for state_str in sorted(allowed):
            try:
                result.append(GSDState(state_str))
            except ValueError:
                # Unknown state string — include as-is
                result.append(state_str)

        return result

    async def get_transition_reason(self, state: ConversationState) -> Dict[str, Any]:
        """Explain WHY a particular transition was or would be chosen.

        Analyzes the current ConversationState signals and produces
        a detailed explanation of the transition reasoning.

        Args:
            state: Current ConversationState.

        Returns:
            Dictionary with transition reasoning details.
        """
        from app.core.techniques.base import GSDState

        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)
        variant = self.get_variant(state.company_id)
        config = self.get_config(state.company_id)

        # Gather signal data
        signals = self._extract_signal_data(state)
        next_state = await self.get_next_state(state)
        next_str = next_state.value if isinstance(next_state, GSDState) else str(next_state)

        # Build reasoning chain
        reasoning: List[Dict[str, Any]] = []
        escalation_checks = await self._evaluate_escalation_conditions(state, config)

        # Current state context
        reasoning.append({
            "step": "current_state_check",
            "current_state": current_str,
            "variant": variant,
            "description": f"Conversation is in {current_str} state",
        })

        # Escalation evaluation
        for check in escalation_checks:
            reasoning.append(check)

        # Confidence check (for DIAGNOSIS→RESOLUTION)
        if current_str == "diagnosis":
            confidence = signals.get("confidence_score", 0.0)
            intent = signals.get("intent_type", "general")
            meets_threshold = confidence >= config.confidence_threshold
            reasoning.append({
                "step": "confidence_evaluation",
                "confidence_score": confidence,
                "threshold": config.confidence_threshold,
                "intent_type": intent,
                "meets_threshold": meets_threshold,
                "description": (
                    f"Classification confidence {confidence:.2f} "
                    f"{'≥' if meets_threshold else '<'} threshold "
                    f"{config.confidence_threshold:.2f}"
                ),
            })

        # Sentiment check
        frustration = signals.get("frustration_score", 0.0)
        if frustration > 0:
            reasoning.append({
                "step": "frustration_check",
                "frustration_score": frustration,
                "escalation_threshold": config.frustration_threshold,
                "description": (
                    f"Frustration at {frustration:.0f}/100 "
                    f"({'above' if frustration >= config.frustration_threshold else 'below'} "
                    f"escalation threshold {config.frustration_threshold:.0f})"
                ),
            })

        # VIP check
        customer_tier = signals.get("customer_tier", "free")
        is_vip = customer_tier.lower() in config.vip_tiers
        if is_vip:
            reasoning.append({
                "step": "vip_check",
                "customer_tier": customer_tier,
                "is_vip": True,
                "description": f"VIP customer ({customer_tier} tier) — escalation eligible",
            })

        # Diagnosis loop count
        diagnosis_loops = self._count_diagnosis_loops(state)
        if diagnosis_loops > 0:
            reasoning.append({
                "step": "loop_detection",
                "diagnosis_loop_count": diagnosis_loops,
                "max_loops": config.max_diagnosis_loops,
                "description": (
                    f"DIAGNOSIS entered {diagnosis_loops} time(s) "
                    f"(auto-escalate at {config.max_diagnosis_loops})"
                ),
            })

        return {
            "current_state": current_str,
            "recommended_next_state": next_str,
            "variant": variant,
            "reasoning_chain": reasoning,
            "signals_snapshot": signals,
            "escalation_conditions_met": any(
                c.get("condition_met", False) for c in escalation_checks
            ),
            "diagnosis_loops": diagnosis_loops,
        }

    # ── Escalation Handling ───────────────────────────────────────

    async def handle_escalation(
        self, state: ConversationState,
    ) -> ConversationState:
        """Handle escalation triggers for a conversation.

        Checks all escalation conditions (frustration, VIP, legal intent,
        loop count) and transitions to ESCALATE if warranted. Also
        enforces escalation cooldown.

        Args:
            state: Current ConversationState.

        Returns:
            Updated ConversationState (escalated or unchanged).

        Raises:
            EscalationCooldownError: If escalation is in cooldown period.
        """
        from app.core.techniques.base import GSDState

        config = self.get_config(state.company_id)

        # Check cooldown
        cooldown_remaining = await self._check_escalation_cooldown(
            state.company_id, config.escalation_cooldown_seconds,
        )
        if cooldown_remaining > 0:
            raise EscalationCooldownError(
                cooldown_remaining_seconds=cooldown_remaining,
                last_escalation_time=self._escalation_timestamps.get(state.company_id),
            )

        # Check if escalation is warranted
        if not await self._should_auto_escalate(state):
            logger.debug(
                "escalation_not_triggered",
                ticket_id=state.ticket_id,
                company_id=state.company_id,
                current_state=str(state.gsd_state),
            )
            return state

        # Build escalation metadata
        escalation_reason = await self._get_escalation_reason(state)
        signals = self._extract_signal_data(state)
        diagnosis_loops = self._count_diagnosis_loops(state)

        escalation_metadata = {
            "escalation_reason": escalation_reason,
            "frustration_score": signals.get("frustration_score", 0.0),
            "confidence_score": signals.get("confidence_score", 0.0),
            "intent_type": signals.get("intent_type", "unknown"),
            "customer_tier": signals.get("customer_tier", "free"),
            "diagnosis_loop_count": diagnosis_loops,
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.warning(
            "gsd_escalation_triggered",
            ticket_id=state.ticket_id,
            company_id=state.company_id,
            reason=escalation_reason,
            **escalation_metadata,
        )

        return await self.transition(
            state,
            GSDState.ESCALATE,
            trigger_reason=escalation_reason,
            metadata=escalation_metadata,
        )

    async def reset_conversation(
        self, state: ConversationState,
    ) -> ConversationState:
        """Reset a conversation to the NEW state.

        Clears GSD history (preserving a final closed record) and
        resets the state machine. Typically called when a new message
        arrives on a previously closed ticket.

        Args:
            state: Current ConversationState.

        Returns:
            Reset ConversationState with gsd_state = NEW.
        """
        from app.core.techniques.base import GSDState

        # Record the reset in history before clearing
        record = TransitionRecord(
            state="new",
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger="conversation_reset",
            metadata={"previous_state": str(state.gsd_state)},
        )
        self._append_history(state, record)

        # Reset the state
        state.gsd_state = GSDState.NEW

        # Clear escalation cooldown for this tenant
        company_id = state.company_id or ""
        if company_id in self._escalation_timestamps:
            del self._escalation_timestamps[company_id]

        # Best-effort clear Redis cooldown key
        try:
            from app.core.redis import get_redis, make_key
            redis = await get_redis()
            key = make_key(company_id, "escalation_cooldown")
            await redis.delete(key)
        except Exception:
            pass  # BC-008: Redis failure is non-fatal

        logger.info(
            "gsd_conversation_reset",
            ticket_id=state.ticket_id,
            company_id=state.company_id,
            previous_state=record.metadata.get("previous_state"),
        )

        return state

    # ── Utility Methods ───────────────────────────────────────────

    async def get_conversation_summary(
        self, state: ConversationState,
    ) -> Dict[str, Any]:
        """Generate a summary of the current conversation state.

        Provides a comprehensive snapshot of where the conversation
        is, how it got there, and key signal metrics.

        Args:
            state: Current ConversationState.

        Returns:
            Dictionary with conversation summary data.
        """
        from app.core.techniques.base import GSDState

        signals = self._extract_signal_data(state)
        history = self._get_history_records(state)
        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)
        diagnosis_loops = self._count_diagnosis_loops(state)
        is_terminal = await self.is_terminal(state)
        available = await self.get_available_transitions(state.gsd_state, self.get_variant(state.company_id))
        resolution_time = await self.estimate_resolution_time(state)

        # Calculate time in current state
        time_in_state = self._calculate_time_in_current_state(history)

        # State distribution
        state_distribution = self._calculate_state_distribution(history)

        return {
            "ticket_id": state.ticket_id,
            "conversation_id": state.conversation_id,
            "company_id": state.company_id,
            "current_state": current_str,
            "is_terminal": is_terminal,
            "available_transitions": [s.value if isinstance(s, GSDState) else str(s) for s in available],
            "signals": signals,
            "diagnosis_loop_count": diagnosis_loops,
            "history_entry_count": len(history),
            "time_in_current_state_seconds": time_in_state,
            "estimated_resolution_time_minutes": resolution_time,
            "state_distribution": state_distribution,
            "escalation_eligible": await self._should_auto_escalate(state),
            "auto_close_eligible": await self.should_auto_close(state),
            "variant": self.get_variant(state.company_id),
            "token_usage": state.token_usage,
        }

    async def estimate_resolution_time(
        self, state: ConversationState,
    ) -> int:
        """Estimate minutes remaining to resolution.

        Based on intent type, query complexity, and current GSD state.

        Args:
            state: Current ConversationState.

        Returns:
            Estimated minutes to resolution (integer).
        """
        from app.core.techniques.base import GSDState

        signals = self._extract_signal_data(state)
        intent = signals.get("intent_type", "general")
        complexity = signals.get("query_complexity", 0.5)

        # Map complexity to bucket
        if complexity < 0.33:
            complexity_bucket = "low"
        elif complexity < 0.66:
            complexity_bucket = "medium"
        else:
            complexity_bucket = "high"

        # Get base estimate
        intent_estimates = RESOLUTION_TIME_ESTIMATES.get(intent, DEFAULT_RESOLUTION_ESTIMATE)
        base_minutes = intent_estimates.get(complexity_bucket, 20)

        # Adjust for current state
        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)
        state_adjustments = {
            "new": 0,
            "greeting": 0,
            "diagnosis": -2,  # Already diagnosing, slightly less time
            "resolution": -base_minutes * 0.5,  # Halfway through resolution
            "follow_up": -base_minutes * 0.7,  # Nearly done
            "escalate": base_minutes * 0.5,  # Adds time
            "human_handoff": base_minutes * 0.3,  # Human will handle most
            "closed": 0,
        }
        adjustment = state_adjustments.get(current_str, 0)

        # Adjust for frustration (escalation likely → more time)
        frustration = signals.get("frustration_score", 0.0)
        if frustration > 60:
            adjustment += int(base_minutes * 0.3)
        elif frustration > 80:
            adjustment += int(base_minutes * 0.5)

        # Adjust for diagnosis loops (repeated diagnosis → more time)
        loops = self._count_diagnosis_loops(state)
        if loops > 1:
            adjustment += loops * 5

        estimated = max(0, base_minutes + int(adjustment))
        return estimated

    async def get_diagnostic_questions(
        self, state: ConversationState,
    ) -> List[str]:
        """Suggest next diagnostic questions based on conversation state.

        Selects questions from predefined templates based on the
        detected intent, excluding questions already asked (determined
        by conversation history overlap).

        Args:
            state: Current ConversationState.

        Returns:
            List of suggested diagnostic question strings.
        """
        from app.core.techniques.base import GSDState

        # Only relevant in DIAGNOSIS state
        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)
        if current_str != "diagnosis":
            return []

        signals = self._extract_signal_data(state)
        intent = signals.get("intent_type", "general")

        # Get questions for this intent
        all_questions = DIAGNOSTIC_QUESTIONS.get(intent, DIAGNOSTIC_QUESTIONS.get("general", []))

        if not all_questions:
            return ["Could you tell me more about your issue?"]

        # Filter out questions that overlap with the current query
        # (don't ask something they've already answered)
        query_lower = state.query.lower()
        filtered: List[str] = []
        for question in all_questions:
            question_words = set(re.findall(r"\b\w+\b", question.lower()))
            query_words = set(re.findall(r"\b\w+\b", query_lower))
            # Skip common stop words for comparison
            stop_words = {
                "the", "a", "an", "is", "are", "was", "were", "be",
                "to", "of", "in", "for", "on", "at", "by", "with",
                "and", "or", "but", "not", "can", "you", "your",
                "have", "has", "had", "do", "does", "did", "what",
                "when", "where", "how", "this", "that", "it",
            }
            content_overlap = question_words & query_words - stop_words
            # If less than 3 content words overlap, the question is novel
            if len(content_overlap) < 3:
                filtered.append(question)

        # Also filter based on reasoning thread (don't repeat questions)
        reasoning_texts = state.reasoning_thread or []
        reasoning_words = set()
        for text in reasoning_texts:
            reasoning_words.update(re.findall(r"\b\w+\b", text.lower()))

        final_questions: List[str] = []
        for question in filtered:
            q_words = set(re.findall(r"\b\w+\b", question.lower())) - stop_words
            overlap_with_reasoning = len(q_words & reasoning_words)
            if overlap_with_reasoning < 3:
                final_questions.append(question)

        return final_questions[:3] if final_questions else all_questions[:3]

    async def should_auto_close(self, state: ConversationState) -> bool:
        """Check whether the conversation is eligible for auto-close.

        A conversation can be auto-closed if:
        1. It's in RESOLUTION or FOLLOW_UP state
        2. The intent is a simple type (billing, FAQ, inquiry, etc.)
        3. The last customer message indicates satisfaction
        4. No follow-up is expected

        Args:
            state: Current ConversationState.

        Returns:
            True if auto-close is eligible, False otherwise.
        """
        from app.core.techniques.base import GSDState

        config = self.get_config(state.company_id)
        current_str = state.gsd_state.value if isinstance(state.gsd_state, GSDState) else str(state.gsd_state)

        # Must be in RESOLUTION or FOLLOW_UP state
        if current_str not in ("resolution", "follow_up"):
            return False

        # Check if intent is eligible for auto-close
        signals = self._extract_signal_data(state)
        intent = signals.get("intent_type", "general")
        if intent not in config.auto_close_intents and intent not in SIMPLE_RESOLUTION_INTENTS:
            return False

        # Check if the latest query indicates satisfaction
        query_lower = (state.query or "").lower().strip()
        if not query_lower:
            return False

        # In RESOLUTION state, auto-close if intent is simple and
        # the customer's message is brief (likely acknowledgment)
        if current_str == "resolution":
            word_count = len(re.findall(r"\b\w+\b", query_lower))
            is_simple_intent = intent in SIMPLE_RESOLUTION_INTENTS
            is_brief = word_count <= 5
            has_satisfaction = any(phrase in query_lower for phrase in SATISFACTION_PHRASES)
            return is_simple_intent and (is_brief or has_satisfaction)

        # In FOLLOW_UP state, check for satisfaction phrases
        if current_str == "follow_up":
            has_satisfaction = any(phrase in query_lower for phrase in SATISFACTION_PHRASES)
            return has_satisfaction

        return False

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: NEXT-STATE DETERMINATION HELPERS
    # ═══════════════════════════════════════════════════════════

    async def _determine_diagnosis_next(
        self, state: ConversationState, variant: str,
    ) -> Any:
        """Determine next state from DIAGNOSIS.

        Transition logic:
        - DIAGNOSIS → RESOLUTION: intent classified with sufficient confidence
        - DIAGNOSIS → ESCALATE: confidence too low or escalation triggers

        Args:
            state: Current ConversationState.
            variant: PARWA variant.

        Returns:
            GSDState for the recommended next transition.
        """
        from app.core.techniques.base import GSDState

        config = self.get_config(state.company_id)
        signals = self._extract_signal_data(state)
        confidence = signals.get("confidence_score", 0.0)
        intent = signals.get("intent_type", "general")

        # Check for legal intent (always escalate)
        if intent.lower() in LEGAL_INTENTS or any(
            legal_word in (state.query or "").lower() for legal_word in LEGAL_INTENTS
        ):
            return GSDState.ESCALATE

        # Check confidence threshold
        if confidence >= config.confidence_threshold:
            return GSDState.RESOLUTION

        # Check for escalation triggers
        if variant != GSDVariant.MINI_PARWA.value:
            if await self._should_auto_escalate(state):
                return GSDState.ESCALATE

        # Default: stay in diagnosis (need more info)
        # Return current state to indicate "gather more information"
        return GSDState.DIAGNOSIS

    async def _determine_resolution_next(
        self, state: ConversationState, variant: str,
    ) -> Any:
        """Determine next state from RESOLUTION.

        Transition logic:
        - RESOLUTION → FOLLOW_UP: response sent and CLARA quality gate passed
        - RESOLUTION → CLOSED: auto-close if simple resolution

        Args:
            state: Current ConversationState.
            variant: PARWA variant.

        Returns:
            GSDState for the recommended next transition.
        """
        from app.core.techniques.base import GSDState

        signals = self._extract_signal_data(state)
        intent = signals.get("intent_type", "general")

        # Check for auto-close eligibility
        if await self.should_auto_close(state):
            return GSDState.CLOSED

        # Default: move to follow_up
        return GSDState.FOLLOW_UP

    async def _determine_follow_up_next(
        self, state: ConversationState, variant: str,
    ) -> Any:
        """Determine next state from FOLLOW_UP.

        Transition logic:
        - FOLLOW_UP → CLOSED: customer satisfied
        - FOLLOW_UP → DIAGNOSIS: customer has new/ different question

        Args:
            state: Current ConversationState.
            variant: PARWA variant.

        Returns:
            GSDState for the recommended next transition.
        """
        from app.core.techniques.base import GSDState

        query_lower = (state.query or "").lower().strip()

        # Check for satisfaction signals → CLOSED
        if query_lower and any(
            phrase in query_lower for phrase in SATISFACTION_PHRASES
        ):
            return GSDState.CLOSED

        # Check for new issue signals → DIAGNOSIS
        if query_lower and any(
            phrase in query_lower for phrase in NEW_ISSUE_PHRASES
        ):
            return GSDState.DIAGNOSIS

        # Check if the query looks like a new question (has question marks,
        # is long enough, and doesn't contain satisfaction words)
        if query_lower:
            has_question = "?" in query_lower
            word_count = len(re.findall(r"\b\w+\b", query_lower))
            has_negation = any(
                w in query_lower for w in (
                    "but", "however", "wait", "actually",
                    "no", "not", "still", "wrong",
                )
            )
            if (has_question and word_count > 3) or (has_negation and word_count > 5):
                return GSDState.DIAGNOSIS

        # Default: close the conversation
        return GSDState.CLOSED

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: ESCALATION EVALUATION
    # ═══════════════════════════════════════════════════════════

    async def _should_auto_escalate(self, state: ConversationState) -> bool:
        """Evaluate whether the conversation should auto-escalate.

        Checks all escalation conditions:
        1. Frustration score > threshold (default: 80)
        2. Intent is legal/sensitive
        3. VIP customer tier
        4. Too many diagnosis loops (default: 3+)

        Args:
            state: Current ConversationState.

        Returns:
            True if auto-escalation should occur.
        """
        config = self.get_config(state.company_id)
        conditions = await self._evaluate_escalation_conditions(state, config)
        return any(c.get("condition_met", False) for c in conditions)

    async def _evaluate_escalation_conditions(
        self, state: ConversationState, config: GSDConfig,
    ) -> List[Dict[str, Any]]:
        """Evaluate each escalation condition independently.

        Returns a list of condition check results, each containing
        whether the condition was met and relevant metadata.

        Args:
            state: Current ConversationState.
            config: GSD configuration.

        Returns:
            List of condition evaluation results.
        """
        results: List[Dict[str, Any]] = []
        signals = self._extract_signal_data(state)

        # Condition 1: Frustration score exceeds threshold
        frustration = signals.get("frustration_score", 0.0)
        frustration_met = frustration >= config.frustration_threshold
        results.append({
            "condition": "frustration_exceeded",
            "condition_met": frustration_met,
            "frustration_score": frustration,
            "threshold": config.frustration_threshold,
            "description": (
                f"Frustration {frustration:.0f} "
                f"{'≥' if frustration_met else '<'} "
                f"threshold {config.frustration_threshold:.0f}"
            ),
        })

        # Condition 2: Legal/sensitive intent
        intent = signals.get("intent_type", "general")
        query_lower = (state.query or "").lower()
        has_legal_intent = intent.lower() in LEGAL_INTENTS or any(
            legal in query_lower for legal in LEGAL_INTENTS
        )
        results.append({
            "condition": "legal_intent",
            "condition_met": has_legal_intent,
            "intent_type": intent,
            "legal_keywords_found": [
                w for w in LEGAL_INTENTS if w in query_lower
            ],
            "description": (
                f"Legal/sensitive intent detected: {intent}"
                if has_legal_intent
                else "No legal intent detected"
            ),
        })

        # Condition 3: VIP customer tier
        customer_tier = signals.get("customer_tier", "free")
        is_vip = customer_tier.lower() in config.vip_tiers
        results.append({
            "condition": "vip_customer",
            "condition_met": is_vip,
            "customer_tier": customer_tier,
            "vip_tiers": config.vip_tiers,
            "description": (
                f"VIP customer ({customer_tier} tier)"
                if is_vip
                else f"Standard customer ({customer_tier} tier)"
            ),
        })

        # Condition 4: Excessive diagnosis loops
        diagnosis_loops = self._count_diagnosis_loops(state)
        loops_met = diagnosis_loops >= config.max_diagnosis_loops
        results.append({
            "condition": "diagnosis_loop_exceeded",
            "condition_met": loops_met,
            "loop_count": diagnosis_loops,
            "max_loops": config.max_diagnosis_loops,
            "description": (
                f"DIAGNOSIS looped {diagnosis_loops} time(s), "
                f"max is {config.max_diagnosis_loops}"
            ),
        })

        return results

    async def _get_escalation_reason(self, state: ConversationState) -> str:
        """Get a human-readable reason for the current escalation.

        Returns the primary escalation trigger reason.

        Args:
            state: Current ConversationState.

        Returns:
            String describing the escalation reason.
        """
        config = self.get_config(state.company_id)
        signals = self._extract_signal_data(state)

        # Priority: legal > frustration > VIP > loops
        intent = signals.get("intent_type", "general")
        query_lower = (state.query or "").lower()
        if intent.lower() in LEGAL_INTENTS or any(
            legal in query_lower for legal in LEGAL_INTENTS
        ):
            return f"legal_intent_detected: {intent}"

        frustration = signals.get("frustration_score", 0.0)
        if frustration >= config.frustration_threshold:
            return f"frustration_exceeded: {frustration:.0f}/100"

        customer_tier = signals.get("customer_tier", "free")
        if customer_tier.lower() in config.vip_tiers:
            return f"vip_customer: {customer_tier} tier"

        diagnosis_loops = self._count_diagnosis_loops(state)
        if diagnosis_loops >= config.max_diagnosis_loops:
            return f"diagnosis_loops_exceeded: {diagnosis_loops}/{config.max_diagnosis_loops}"

        return "multiple_conditions_met"

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: HISTORY MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def _append_history(
        self, state: ConversationState, record: TransitionRecord,
    ) -> None:
        """Append a transition record to the GSD history (ring buffer).

        The history is stored in ConversationState.gsd_history as a list
        of dicts. When the max size is exceeded, oldest entries are
        dropped (FIFO ring buffer).

        Args:
            state: ConversationState to update.
            record: TransitionRecord to append.
        """
        config = self.get_config(state.company_id)
        max_entries = config.max_history_entries

        # The field is typed as List[GSDState] in base.py but we store
        # dicts for richer history data. Python's dynamic typing allows this.
        history = state.gsd_history  # type: ignore[assignment]

        # Ensure it's a list (defensive)
        if not isinstance(history, list):
            state.gsd_history = []  # type: ignore[assignment]
            history = state.gsd_history  # type: ignore[assignment]

        # Append the record as a dict
        history.append(record.to_dict())  # type: ignore[append-attribute]

        # Ring buffer: trim oldest entries if over max
        while len(history) > max_entries:  # type: ignore[arg-type]
            history.pop(0)

    def _get_history_records(
        self, state: ConversationState,
    ) -> List[Dict[str, Any]]:
        """Extract history records from ConversationState.

        Handles both dict entries (new format) and raw GSDState
        entries (legacy format) gracefully.

        Args:
            state: ConversationState.

        Returns:
            List of history record dicts.
        """
        history = state.gsd_history
        if not isinstance(history, list):
            return []

        records: List[Dict[str, Any]] = []
        for entry in history:
            if isinstance(entry, dict):
                records.append(entry)
            else:
                # Legacy format: raw GSDState value
                records.append({
                    "state": str(entry),
                    "timestamp": "unknown",
                    "trigger": "legacy_entry",
                    "metadata": {},
                })
        return records

    def _count_diagnosis_loops(self, state: ConversationState) -> int:
        """Count how many times DIAGNOSIS has been entered.

        Used to detect when the AI is looping without resolving.

        Args:
            state: ConversationState.

        Returns:
            Number of times the DIAGNOSIS state has been entered.
        """
        records = self._get_history_records(state)
        count = 0
        for record in records:
            state_val = record.get("state", "")
            if state_val == "diagnosis":
                count += 1
        # Also count if currently in diagnosis
        current_str = state.gsd_state.value if hasattr(state.gsd_state, "value") else str(state.gsd_state)
        if current_str == "diagnosis":
            count += 1
        return count

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: ESCALATION COOLDOWN
    # ═══════════════════════════════════════════════════════════

    def _record_escalation_timestamp(self, company_id: Optional[str], ticket_id: Optional[str] = None) -> None:
        """Record the timestamp of an escalation for cooldown tracking.

        Persists the escalation timestamp to Redis with a 300-second TTL
        so cooldown survives process restarts and is shared across workers.
        Falls back to the in-memory dict if Redis is unavailable (BC-008).

        Args:
            company_id: Tenant identifier.
            ticket_id: Optional ticket ID for per-ticket cooldown keys.
        """
        if not company_id:
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        # Always update the local dict (backward-compat for tests)
        self._escalation_timestamps[company_id] = now_iso

        # Best-effort persist to Redis with TTL
        try:
            import asyncio

            async def _set_redis():
                try:
                    from app.core.redis import get_redis, make_key
                    redis = await get_redis()
                    if ticket_id:
                        key = make_key(company_id, "escalation_cooldown", ticket_id)
                    else:
                        key = make_key(company_id, "escalation_cooldown")
                    await redis.set(key, now_iso, ex=300)
                except Exception:
                    pass  # BC-008: Redis failure is non-fatal

            # Try to schedule; if no event loop, just use local dict
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_set_redis())
            except RuntimeError:
                # No running loop — fire-and-forget in new loop or skip
                pass
        except Exception:
            pass  # BC-008

    async def _record_escalation_timestamp_async(self, company_id: Optional[str], ticket_id: Optional[str] = None) -> None:
        """Async version of _record_escalation_timestamp for call sites with an event loop.

        Args:
            company_id: Tenant identifier.
            ticket_id: Optional ticket ID for per-ticket cooldown keys.
        """
        if not company_id:
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        # Always update the local dict (backward-compat for tests)
        self._escalation_timestamps[company_id] = now_iso

        # Best-effort persist to Redis with TTL
        try:
            from app.core.redis import get_redis, make_key
            redis = await get_redis()
            if ticket_id:
                key = make_key(company_id, "escalation_cooldown", ticket_id)
            else:
                key = make_key(company_id, "escalation_cooldown")
            await redis.set(key, now_iso, ex=300)
        except Exception:
            pass  # BC-008: Redis failure is non-fatal

    async def _check_escalation_cooldown(
        self, company_id: Optional[str], cooldown_seconds: float,
        ticket_id: Optional[str] = None,
    ) -> float:
        """Check if escalation cooldown is active.

        Checks Redis first for a persisted cooldown timestamp, then falls
        back to the in-memory dict. Returns the number of seconds remaining
        in cooldown, or 0 if cooldown has expired.

        Args:
            company_id: Tenant identifier.
            cooldown_seconds: Cooldown period in seconds.
            ticket_id: Optional ticket ID for per-ticket cooldown keys.

        Returns:
            Seconds remaining in cooldown, or 0 if cooldown has expired.
        """
        if not company_id:
            return 0.0

        last_escalation: Optional[str] = None

        # Try Redis first for authoritative cooldown
        try:
            from app.core.redis import get_redis, make_key
            redis = await get_redis()
            if ticket_id:
                key = make_key(company_id, "escalation_cooldown", ticket_id)
            else:
                key = make_key(company_id, "escalation_cooldown")
            redis_val = await redis.get(key)
            if redis_val:
                last_escalation = redis_val
        except Exception:
            pass  # BC-008: Redis failure — fall back to local

        # Fall back to in-memory dict
        if not last_escalation:
            last_escalation = self._escalation_timestamps.get(company_id)

        if not last_escalation:
            return 0.0

        try:
            last_time = datetime.fromisoformat(last_escalation)
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            elapsed = (now - last_time).total_seconds()
            remaining = cooldown_seconds - elapsed

            if remaining > 0:
                return remaining
            return 0.0
        except (ValueError, TypeError):
            # Invalid timestamp — allow escalation
            return 0.0

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: SIGNAL EXTRACTION HELPERS
    # ═══════════════════════════════════════════════════════════

    def _extract_signal_data(self, state: ConversationState) -> Dict[str, Any]:
        """Extract signal data from ConversationState for decision-making.

        Pulls data from the signals field (QuerySignals) and
        technique_results to provide a unified signal snapshot.

        GAP 6 FIX: Also extracts frustration_score from signals if available,
        ensuring escalation evaluation captures frustration atomically.

        Args:
            state: ConversationState.

        Returns:
            Dictionary of signal name → value.
        """
        signals: Dict[str, Any] = {}

        # Extract from QuerySignals
        query_signals = state.signals
        if query_signals:
            signals["query_complexity"] = getattr(query_signals, "query_complexity", 0.0)
            signals["confidence_score"] = getattr(query_signals, "confidence_score", 1.0)
            signals["sentiment_score"] = getattr(query_signals, "sentiment_score", 0.7)
            signals["customer_tier"] = getattr(query_signals, "customer_tier", "free")
            signals["monetary_value"] = getattr(query_signals, "monetary_value", 0.0)
            signals["turn_count"] = getattr(query_signals, "turn_count", 0)
            signals["intent_type"] = getattr(query_signals, "intent_type", "general")
            signals["previous_response_status"] = getattr(
                query_signals, "previous_response_status", "none",
            )
            signals["reasoning_loop_detected"] = getattr(
                query_signals, "reasoning_loop_detected", False,
            )
            signals["resolution_path_count"] = getattr(
                query_signals, "resolution_path_count", 1,
            )
            # GAP 6 FIX: Also extract frustration_score from signals if available
            signals["frustration_score"] = getattr(query_signals, "frustration_score", 0.0)

        # Extract frustration score from technique_results if available
        if state.technique_results:
            sentiment_result = state.technique_results.get("sentiment_analysis")
            if sentiment_result and isinstance(sentiment_result, dict):
                result_data = sentiment_result.get("result", {})
                if isinstance(result_data, dict):
                    signals["frustration_score"] = result_data.get(
                        "frustration_score", 0.0,
                    )
                elif hasattr(result_data, "frustration_score"):
                    signals["frustration_score"] = result_data.frustration_score

            # Extract classification confidence from technique_results
            classification_result = state.technique_results.get("intent_classification")
            if classification_result and isinstance(classification_result, dict):
                cls_data = classification_result.get("result", {})
                if isinstance(cls_data, dict):
                    cls_confidence = cls_data.get("primary_confidence", 0.0)
                    if cls_confidence > 0:
                        signals["confidence_score"] = cls_confidence
                    cls_intent = cls_data.get("primary_intent", "")
                    if cls_intent:
                        signals["intent_type"] = cls_intent

        # Convert sentiment_score (0.0-1.0) to frustration_score (0-100)
        # if frustration_score wasn't explicitly set
        if "frustration_score" not in signals:
            sentiment = signals.get("sentiment_score", 0.7)
            signals["frustration_score"] = round((1.0 - sentiment) * 100, 1)

        # Ensure essential keys exist
        signals.setdefault("query_complexity", 0.0)
        signals.setdefault("confidence_score", 1.0)
        signals.setdefault("sentiment_score", 0.7)
        signals.setdefault("customer_tier", "free")
        signals.setdefault("monetary_value", 0.0)
        signals.setdefault("turn_count", 0)
        signals.setdefault("intent_type", "general")
        signals.setdefault("frustration_score", 0.0)
        signals.setdefault("previous_response_status", "none")
        signals.setdefault("reasoning_loop_detected", False)
        signals.setdefault("resolution_path_count", 1)

        return signals

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: ANALYTICS HELPERS
    # ═══════════════════════════════════════════════════════════

    def _calculate_time_in_current_state(
        self, history: List[Dict[str, Any]],
    ) -> float:
        """Calculate seconds spent in the current state.

        Args:
            history: List of history record dicts.

        Returns:
            Seconds in the current state (0 if no history).
        """
        if not history:
            return 0.0

        latest = history[-1] if history else None
        if not latest or "timestamp" not in latest:
            return 0.0

        try:
            last_time = datetime.fromisoformat(latest["timestamp"])
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - last_time).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def _calculate_state_distribution(
        self, history: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """Calculate how many times each state has been visited.

        Args:
            history: List of history record dicts.

        Returns:
            Dict mapping state name to visit count.
        """
        distribution: Dict[str, int] = defaultdict(int)
        for record in history:
            state_val = record.get("state", "unknown")
            distribution[state_val] += 1
        return dict(distribution)

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: TRANSITION HELPERS
    # ═══════════════════════════════════════════════════════════

    async def _explain_invalid_transition(
        self, from_state: str, to_state: str, state: ConversationState,
    ) -> str:
        """Generate a human-readable explanation for an invalid transition.

        Args:
            from_state: Current state string.
            to_state: Target state string.
            state: ConversationState for context.

        Returns:
            String explaining why the transition is invalid.
        """
        variant = self.get_variant(state.company_id)
        table = self._get_transition_table(variant)
        allowed = table.get(from_state, set())

        # Check if target state exists at all
        all_states = set(FULL_TRANSITION_TABLE.keys())
        if to_state not in all_states:
            return f"Unknown target state: {to_state}. Valid states: {sorted(all_states)}"

        # Check if from_state exists
        if from_state not in all_states:
            return f"Unknown current state: {from_state}. Valid states: {sorted(all_states)}"

        # Check variant restrictions
        if variant == GSDVariant.MINI_PARWA.value and to_state in ("escalate", "human_handoff"):
            return (
                f"Escalation and human handoff are not available in "
                f"{GSDVariant.MINI_PARWA.value} variant"
            )

        available = ", ".join(sorted(allowed)) if allowed else "none"
        return (
            f"Transition from '{from_state}' to '{to_state}' is not permitted. "
            f"Available transitions from '{from_state}': [{available}]"
        )

    def _default_trigger(self, from_state: str, to_state: str) -> str:
        """Generate a default trigger reason for a transition.

        Args:
            from_state: Source state string.
            to_state: Target state string.

        Returns:
            Default trigger reason string.
        """
        default_triggers = {
            ("new", "greeting"): "initial_greeting",
            ("greeting", "diagnosis"): "user_message_received",
            ("diagnosis", "resolution"): "intent_classified",
            ("diagnosis", "escalate"): "escalation_triggered",
            ("resolution", "follow_up"): "resolution_delivered",
            ("resolution", "closed"): "auto_close_simple",
            ("follow_up", "closed"): "customer_satisfied",
            ("follow_up", "diagnosis"): "new_issue_detected",
            ("escalate", "human_handoff"): "auto_handoff",
            ("human_handoff", "diagnosis"): "agent_resolved_return_to_ai",
            ("closed", "new"): "new_message_on_closed_ticket",
        }
        return default_triggers.get(
            (from_state, to_state), f"manual_transition_{from_state}_to_{to_state}",
        )

    # ═══════════════════════════════════════════════════════════
    # INTERNAL: EVENT EMISSION
    # ═══════════════════════════════════════════════════════════

    def _emit_transition_event(
        self,
        ticket_id: Optional[str],
        from_state: str,
        to_state: str,
        trigger_reason: str,
        company_id: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a structured log event for a state transition.

        Uses structlog to emit a transition event with full context.
        This event can be consumed by monitoring, analytics, and
        audit systems.

        Args:
            ticket_id: Optional ticket identifier.
            from_state: GSDState value before transition.
            to_state: GSDState value after transition.
            trigger_reason: Why the transition occurred.
            company_id: Tenant identifier.
            metadata: Additional context.
        """
        event = TransitionEvent(
            ticket_id=ticket_id,
            from_state=from_state,
            to_state=to_state,
            trigger_reason=trigger_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            company_id=company_id,
            metadata=metadata or {},
        )

        logger.info(
            "gsd_transition_event",
            ticket_id=event.ticket_id,
            from_state=event.from_state,
            to_state=event.to_state,
            trigger_reason=event.trigger_reason,
            timestamp=event.timestamp,
            company_id=event.company_id,
            **event.metadata,
        )


# ══════════════════════════════════════════════════════════════════
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

# Singleton engine instance for module-level access
_default_engine: Optional[GSDEngine] = None


def get_gsd_engine() -> GSDEngine:
    """Get or create the default GSD Engine singleton.

    Returns:
        The shared GSDEngine instance.
    """
    global _default_engine
    if _default_engine is None:
        _default_engine = GSDEngine()
    return _default_engine


async def transition_state(
    state: ConversationState,
    target_state: Any,
    trigger_reason: str = "",
) -> ConversationState:
    """Convenience function to transition GSD state using the default engine.

    Args:
        state: Current ConversationState.
        target_state: Target GSDState.
        trigger_reason: Optional trigger reason.

    Returns:
        Updated ConversationState.
    """
    engine = get_gsd_engine()
    return await engine.transition(state, target_state, trigger_reason)


async def get_next_gsd_state(state: ConversationState) -> Any:
    """Convenience function to get the recommended next GSD state.

    Args:
        state: Current ConversationState.

    Returns:
        Recommended GSDState.
    """
    engine = get_gsd_engine()
    return await engine.get_next_state(state)


async def should_escalate(state: ConversationState) -> bool:
    """Convenience function to check if a conversation should escalate.

    Args:
        state: Current ConversationState.

    Returns:
        True if escalation is recommended.
    """
    engine = get_gsd_engine()
    return await engine._should_auto_escalate(state)
