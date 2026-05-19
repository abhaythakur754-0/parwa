"""
PARWA Jarvis Safety Gate — The Human-in-the-Loop Layer

Before any function call is executed, it passes through the Safety Gate.
This is what prevents Jarvis from accidentally doing something costly or
irreversible without the client knowing.

Safety Levels (from jarvis_function_registry):
  - none: Execute immediately. No confirmation needed. (e.g., check health)
  - confirmation_required: Ask the client "are you sure?" before executing.
    The client must confirm before the action proceeds. (e.g., pause AI)
  - approval_required: Require explicit "confirm" — for monetary, destructive,
    or irreversible actions. The client must type "confirm" or "yes" to proceed.
    (e.g., process refund, delete data, change billing)

Flow:
  1. Orchestrator calls check_safety(function_name, user_message, session_state)
  2. Safety Gate looks up the function's safety_level from the registry
  3. If safety_level == "none": Return immediately with status=approved
  4. If safety_level == "confirmation_required":
     a. Check if the session has a pending confirmation for this function
     b. If yes and user confirmed: Approve and execute
     c. If yes and user declined: Reject
     d. If no pending confirmation: Return status=needs_confirmation
        with a human-friendly message asking for confirmation
  5. If safety_level == "approval_required":
     a. Same flow, but requires explicit "confirm" / "yes" keyword
     b. More strict — the confirmation message must contain an affirmative

The Safety Gate is ENFORCED at the orchestrator level. The LLM CANNOT
bypass it — even if the LLM generates a function call, the orchestrator
will intercept it and require confirmation before executing.

Pending confirmations are stored in Redis with a TTL (5 minutes default).
If the client doesn't confirm within the TTL, the confirmation expires
and they need to ask again.

BC-001: company_id used for Redis key namespacing.
BC-008: Never crash — if Redis is down, fail-safe to confirmation_required.
BC-012: All timestamps UTC.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.logger import get_logger
from app.services.jarvis_function_registry import (
    SAFETY_APPROVAL,
    SAFETY_CONFIRMATION,
    SAFETY_NONE,
    get_safety_level,
)

logger = get_logger("jarvis_safety_gate")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

# How long a pending confirmation stays active (seconds)
DEFAULT_CONFIRMATION_TTL = 300  # 5 minutes

# Affirmative keywords for approval_required level
# Only explicit, unambiguous words — "ok" and "sure" are NOT enough for
# monetary/destructive/irreversible actions. They need to explicitly confirm.
APPROVAL_KEYWORDS = {"confirm", "yes", "approved", "approve", "go ahead", "do it", "proceed"}

# Negative keywords for rejecting confirmations
REJECTION_KEYWORDS = {"no", "cancel", "stop", "never mind", "nevermind", "don't", "abort", "decline"}


# ══════════════════════════════════════════════════════════════════
# SAFETY CHECK RESULT
# ══════════════════════════════════════════════════════════════════


class SafetyCheckResult:
    """Result of a safety gate check."""

    def __init__(
        self,
        status: str,  # "approved", "needs_confirmation", "needs_approval", "rejected", "expired"
        function_name: str,
        safety_level: str,
        message: str = "",
        pending_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.function_name = function_name
        self.safety_level = safety_level
        self.message = message
        self.pending_id = pending_id
        self.params = params or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "function_name": self.function_name,
            "safety_level": self.safety_level,
            "message": self.message,
            "pending_id": self.pending_id,
            "params": self.params,
        }

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    @property
    def needs_human_input(self) -> bool:
        return self.status in ("needs_confirmation", "needs_approval")


# ══════════════════════════════════════════════════════════════════
# IN-MEMORY PENDING CONFIRMATION STORE
# ══════════════════════════════════════════════════════════════════
# In production, this would use Redis. For now, we use an in-memory
# dict with TTL-based expiry. The Redis integration is straightforward
# and can be swapped in later.

_pending_confirmations: Dict[str, Dict[str, Any]] = {}


def _make_pending_key(company_id: str, session_id: str) -> str:
    """Create a Redis-like key for pending confirmations."""
    return f"jarvis:safety:pending:{company_id}:{session_id}"


def _store_pending_confirmation(
    company_id: str,
    session_id: str,
    function_name: str,
    params: Dict[str, Any],
    safety_level: str,
    ttl: int = DEFAULT_CONFIRMATION_TTL,
) -> str:
    """Store a pending confirmation. Returns a pending_id."""
    pending_id = f"{function_name}_{int(time.time())}"
    key = _make_pending_key(company_id, session_id)

    entry = {
        "pending_id": pending_id,
        "function_name": function_name,
        "params": params,
        "safety_level": safety_level,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": time.time() + ttl,
    }

    _pending_confirmations[key] = entry

    logger.info(
        "safety_pending_created: function=%s, safety=%s, "
        "company=%s, session=%s, pending_id=%s",
        function_name, safety_level, company_id, session_id, pending_id,
    )

    return pending_id


def _get_pending_confirmation(
    company_id: str,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Get and validate a pending confirmation. Returns None if expired or not found."""
    key = _make_pending_key(company_id, session_id)

    entry = _pending_confirmations.get(key)
    if not entry:
        return None

    # Check TTL
    if time.time() > entry.get("expires_at", 0):
        del _pending_confirmations[key]
        logger.info("safety_pending_expired: key=%s", key)
        return None

    return entry


def _clear_pending_confirmation(company_id: str, session_id: str) -> None:
    """Clear a pending confirmation after it's resolved."""
    key = _make_pending_key(company_id, session_id)
    _pending_confirmations.pop(key, None)


# ══════════════════════════════════════════════════════════════════
# MAIN SAFETY CHECK
# ══════════════════════════════════════════════════════════════════


def check_safety(
    company_id: str,
    session_id: str,
    function_name: str,
    function_params: Dict[str, Any],
    user_message: str = "",
) -> SafetyCheckResult:
    """Check if a function call is safe to execute.

    This is the main entry point for the Safety Gate. The orchestrator
    calls this before executing any function call returned by the LLM.

    Args:
        company_id: Company ID for BC-001.
        session_id: Session ID for pending confirmation scoping.
        function_name: The function the LLM wants to call.
        function_params: Parameters the LLM provided.
        user_message: The user's latest message (for confirmation checking).

    Returns:
        SafetyCheckResult with:
          - status "approved": Safe to execute immediately
          - status "needs_confirmation": Ask client before executing
          - status "needs_approval": Require explicit "confirm" before executing
          - status "rejected": Client declined the action
          - status "expired": Pending confirmation timed out
    """
    try:
        safety_level = get_safety_level(function_name)

        # ── Level 1: No safety check needed ──
        if safety_level == SAFETY_NONE:
            return SafetyCheckResult(
                status="approved",
                function_name=function_name,
                safety_level=safety_level,
                message="Action is safe to execute.",
            )

        # ── Check for pending confirmation ──
        pending = _get_pending_confirmation(company_id, session_id)

        if pending and pending["function_name"] == function_name:
            # There's a pending confirmation for this function
            # Check if the user's message confirms or rejects it
            normalized_msg = user_message.strip().lower()

            # Check for rejection
            for keyword in REJECTION_KEYWORDS:
                if keyword in normalized_msg:
                    _clear_pending_confirmation(company_id, session_id)
                    logger.info(
                        "safety_rejected: function=%s, company=%s, session=%s",
                        function_name, company_id, session_id,
                    )
                    return SafetyCheckResult(
                        status="rejected",
                        function_name=function_name,
                        safety_level=safety_level,
                        message=f"Action '{function_name}' has been cancelled.",
                        params=pending.get("params", {}),
                    )

            # Check for confirmation
            if safety_level == SAFETY_CONFIRMATION:
                # For confirmation_required, any non-rejection response counts
                # as confirmation (the user just needs to respond)
                if normalized_msg:
                    _clear_pending_confirmation(company_id, session_id)
                    logger.info(
                        "safety_confirmed: function=%s, company=%s, session=%s",
                        function_name, company_id, session_id,
                    )
                    return SafetyCheckResult(
                        status="approved",
                        function_name=function_name,
                        safety_level=safety_level,
                        message="Action confirmed by user.",
                        params=pending.get("params", {}),
                    )

            elif safety_level == SAFETY_APPROVAL:
                # For approval_required, need an explicit affirmative keyword
                for keyword in APPROVAL_KEYWORDS:
                    if keyword in normalized_msg:
                        _clear_pending_confirmation(company_id, session_id)
                        logger.info(
                            "safety_approved: function=%s, company=%s, session=%s",
                            function_name, company_id, session_id,
                        )
                        return SafetyCheckResult(
                            status="approved",
                            function_name=function_name,
                            safety_level=safety_level,
                            message="Action approved by user.",
                            params=pending.get("params", {}),
                        )

                # No approval keyword found — still pending
                return SafetyCheckResult(
                    status="needs_approval",
                    function_name=function_name,
                    safety_level=safety_level,
                    message=_build_approval_message(function_name, pending.get("params", {})),
                    pending_id=pending.get("pending_id"),
                    params=pending.get("params", {}),
                )

        # ── No pending confirmation — create one ──
        if safety_level == SAFETY_CONFIRMATION:
            pending_id = _store_pending_confirmation(
                company_id=company_id,
                session_id=session_id,
                function_name=function_name,
                params=function_params,
                safety_level=safety_level,
            )
            return SafetyCheckResult(
                status="needs_confirmation",
                function_name=function_name,
                safety_level=safety_level,
                message=_build_confirmation_message(function_name, function_params),
                pending_id=pending_id,
                params=function_params,
            )

        elif safety_level == SAFETY_APPROVAL:
            pending_id = _store_pending_confirmation(
                company_id=company_id,
                session_id=session_id,
                function_name=function_name,
                params=function_params,
                safety_level=safety_level,
            )
            return SafetyCheckResult(
                status="needs_approval",
                function_name=function_name,
                safety_level=safety_level,
                message=_build_approval_message(function_name, function_params),
                pending_id=pending_id,
                params=function_params,
            )

        # Fallback: fail-safe to confirmation required
        logger.warning(
            "safety_unknown_level: function=%s, level=%s — defaulting to confirmation",
            function_name, safety_level,
        )
        return SafetyCheckResult(
            status="needs_confirmation",
            function_name=function_name,
            safety_level=safety_level,
            message=f"I want to run '{function_name}'. Can I proceed?",
        )

    except Exception:
        logger.exception(
            "safety_check_error: function=%s, company=%s",
            function_name, company_id,
        )
        # Fail-safe: require confirmation
        return SafetyCheckResult(
            status="needs_confirmation",
            function_name=function_name,
            safety_level=SAFETY_CONFIRMATION,
            message="I want to perform an action. Can I proceed?",
        )


# ══════════════════════════════════════════════════════════════════
# CONVERSATIONAL MESSAGE BUILDERS
# ══════════════════════════════════════════════════════════════════
# These build human-friendly messages that Jarvis would actually say.
# NOT robotic — like a smart colleague asking for permission.


def _build_confirmation_message(
    function_name: str,
    params: Dict[str, Any],
) -> str:
    """Build a conversational confirmation message.

    Instead of "Confirm: pause_all_ai", it says something like
    "I'll pause all AI activity for you. Just want to make sure — shall I go ahead?"
    """
    messages = {
        "pause_all_ai": "I'll pause all AI agents for you. They'll stop handling tickets until you tell me to resume. Shall I go ahead?",
        "resume_all_ai": "I'll resume all AI agents so they start handling tickets again. Should I proceed?",
        "pause_refunds": "I'll pause automated refund processing. Any new refund requests will be queued. Want me to do that?",
        "resume_refunds": "I'll resume refund processing so queued refunds start going through again. Shall I?",
        "escalate_urgent_tickets": "I'll escalate all urgent tickets to your human team right away. Should I go ahead?",
        "add_agents": f"I'll add {params.get('count', 1)} more AI agent{'s' if params.get('count', 1) != 1 else ''} to handle more tickets. Want me to proceed?",
        "call_customer": "I'll set up a call to this customer. Should I go ahead?",
        "setup_email_channel": f"I'll connect {params.get('email_address', 'your email')} as a support channel. Want me to set that up?",
        "setup_sms_channel": f"I'll set up SMS support on {params.get('phone_number', 'your number')}. Should I proceed?",
        "emergency_stop": "This will immediately stop ALL automated operations — AI agents, refunds, scheduled tasks. Everything pauses. Are you sure?",
        "update_settings": "I'll update those settings for you. Shall I go ahead?",
        "disable_auto_approve_rule": "I'll disable that auto-approve rule. This means those actions will need manual approval instead. Want me to proceed?",
        "solve_ticket": f"I'll route this ticket through the variant pipeline for AI solving. The AI will generate a response to resolve the customer's issue. Shall I go ahead?",
        "batch_solve_tickets": f"I'll solve up to {params.get('max_tickets', 10)} open tickets through the variant pipeline. Each one will get an AI-generated response. Want me to proceed?",
        "generate_fake_requests": (
            f"I'll generate {params.get('count', 5)} fake customer requests and create tickets from them. "
            f"{'They will also be automatically solved by the variant pipeline.' if params.get('auto_solve') else 'They will be created as open tickets for you to test with.'} "
            "Want me to go ahead?"
        ),
    }

    return messages.get(
        function_name,
        f"I'd like to run '{function_name}'. Can I go ahead?"
    )


def _build_approval_message(
    function_name: str,
    params: Dict[str, Any],
) -> str:
    """Build a conversational approval message for high-safety actions.

    For monetary/destructive/irreversible actions. Requires explicit
    "confirm" or "yes" from the user.
    """
    messages = {
        "process_refund": (
            f"This will issue a refund of {params.get('amount', 'the specified amount')} "
            f"to the customer. This is a monetary action and can't be easily reversed. "
            f"Please type 'confirm' if you want me to proceed."
        ),
    }

    return messages.get(
        function_name,
        f"This action ('{function_name}') has significant consequences. "
        f"Please type 'confirm' if you want me to proceed."
    )


# ══════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def get_pending_status(
    company_id: str,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Check if there's a pending confirmation for a session.

    Returns the pending confirmation details, or None if none exists.
    """
    return _get_pending_confirmation(company_id, session_id)


def clear_all_pending(company_id: str, session_id: str) -> None:
    """Clear all pending confirmations for a session (e.g., on session end)."""
    _clear_pending_confirmation(company_id, session_id)


def force_approve(
    company_id: str,
    session_id: str,
) -> bool:
    """Force-approve the pending confirmation for a session.

    Used for testing or admin override. Returns True if a pending
    confirmation was found and approved.
    """
    pending = _get_pending_confirmation(company_id, session_id)
    if pending:
        _clear_pending_confirmation(company_id, session_id)
        logger.info(
            "safety_force_approved: function=%s, company=%s, session=%s",
            pending["function_name"], company_id, session_id,
        )
        return True
    return False


__all__ = [
    # Main check
    "check_safety",
    # Result type
    "SafetyCheckResult",
    # Pending management
    "get_pending_status",
    "clear_all_pending",
    "force_approve",
    # Constants
    "DEFAULT_CONFIRMATION_TTL",
    "APPROVAL_KEYWORDS",
    "REJECTION_KEYWORDS",
]
