"""
Guardrails Integration Module (Day 2 - Safety & Compliance)

Wires the GuardrailsEngine to the Smart Router / AI Pipeline.
Every LLM response passes through guardrails BEFORE reaching the customer.

Integration Flow:
1. Smart Router executes LLM call
2. Response passes through GuardrailsEngine.run_full_scan()
3. If BLOCKED → Route to BlockedResponseManager
4. If FLAG_FOR_REVIEW → Deliver with metadata flag
5. If ALLOW → Deliver normally

BC-007: All AI through Smart Router
BC-009: Approval workflow for blocked responses
BC-001: company_id is always second parameter
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.guardrails_engine import GuardrailsReport, GuardrailsEngine
    from app.core.blocked_response_manager import BlockedResponseManager

logger = logging.getLogger("parwa.guardrails_integration")


class GuardrailsAction(str, Enum):
    """Actions from guardrails check."""
    ALLOW = "allow"
    BLOCK = "block"
    FLAG_FOR_REVIEW = "flag_for_review"
    REWRITE = "rewrite"


@dataclass
class GuardrailsCheckResult:
    """Result of guardrails check on LLM response."""
    action: GuardrailsAction
    original_response: str
    safe_response: Optional[str] = None
    report: Optional["GuardrailsReport"] = None
    blocked_reasons: List[str] = field(default_factory=list)
    flagged_layers: List[str] = field(default_factory=list)
    confidence: float = 0.0
    company_id: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def check_llm_response(
    response_content: str,
    original_query: str,
    company_id: str,
    variant_type: str = "parwa",
    confidence: float = 85.0,
    engine: Optional["GuardrailsEngine"] = None,
) -> GuardrailsCheckResult:
    """Check LLM response through all guardrail layers.

    This is the main integration point called after LLM generation.

    Args:
        response_content: The LLM-generated response text.
        original_query: The customer's original query.
        company_id: Tenant identifier (BC-001).
        variant_type: PARWA variant for strictness level.
        confidence: AI confidence score from LLM.
        engine: Optional pre-configured GuardrailsEngine.

    Returns:
        GuardrailsCheckResult with action and details.
    """
    if not response_content or not response_content.strip():
        return GuardrailsCheckResult(
            action=GuardrailsAction.BLOCK,
            original_response=response_content or "",
            blocked_reasons=["Empty response"],
            company_id=company_id,
        )

    # Lazy import to avoid circular dependencies
    from app.core.guardrails_engine import GuardrailsEngine

    # Use provided engine or create new one
    guardrails_engine = engine or GuardrailsEngine()

    try:
        # Run full guardrail scan
        report = guardrails_engine.run_full_check(
            query=original_query,
            response=response_content,
            confidence=confidence,
            company_id=company_id,
            variant_type=variant_type,
        )

        # Determine action
        action = _map_action(report.overall_action)

        # Extract blocked/flagged details
        blocked_reasons = []
        flagged_layers = []

        for result in report.results:
            if not result.passed:
                if result.action == "block":
                    blocked_reasons.append(f"{result.layer}: {result.reason}")
                elif result.action == "flag_for_review":
                    flagged_layers.append(result.layer)

        return GuardrailsCheckResult(
            action=action,
            original_response=response_content,
            safe_response=response_content if action != GuardrailsAction.BLOCK else None,
            report=report,
            blocked_reasons=blocked_reasons,
            flagged_layers=flagged_layers,
            confidence=confidence,
            company_id=company_id,
        )

    except Exception as e:
        # BC-008: Guardrails failure should not crash - fail open with logging
        logger.exception(
            "Guardrails check failed for company_id=%s, allowing response: %s",
            company_id, str(e),
        )
        return GuardrailsCheckResult(
            action=GuardrailsAction.ALLOW,
            original_response=response_content,
            safe_response=response_content,
            blocked_reasons=[],
            flagged_layers=[],
            confidence=confidence,
            company_id=company_id,
        )


def handle_blocked_response(
    result: GuardrailsCheckResult,
    blocked_manager: Optional["BlockedResponseManager"] = None,
) -> str:
    """Handle a blocked response through BlockedResponseManager.

    Args:
        result: The guardrails check result with BLOCK action.
        blocked_manager: Optional BlockedResponseManager instance.

    Returns:
        Safe fallback response for the customer.
    """
    if result.action != GuardrailsAction.BLOCK:
        return result.original_response

    # Log the block
    logger.warning(
        "Response blocked for company_id=%s reasons=%s",
        result.company_id, result.blocked_reasons,
    )

    # Try to route through BlockedResponseManager if available
    if blocked_manager is not None:
        try:
            from app.core.blocked_response_manager import BlockedResponse
            blocked = BlockedResponse(
                company_id=result.company_id,
                original_response=result.original_response,
                blocked_reasons=result.blocked_reasons,
                guardrails_report=result.report,
            )
            blocked_manager.handle_blocked(blocked)
        except Exception:
            logger.exception("Failed to route to BlockedResponseManager")

    # Return safe fallback response
    return _get_safe_fallback_response(result.blocked_reasons)


def _map_action(action_str: str) -> GuardrailsAction:
    """Map string action to enum."""
    mapping = {
        "allow": GuardrailsAction.ALLOW,
        "block": GuardrailsAction.BLOCK,
        "flag_for_review": GuardrailsAction.FLAG_FOR_REVIEW,
        "rewrite": GuardrailsAction.REWRITE,
    }
    return mapping.get(action_str.lower(), GuardrailsAction.ALLOW)


def _get_safe_fallback_response(blocked_reasons: List[str]) -> str:
    """Generate a safe fallback response for blocked content.

    This response is customer-facing and should be professional.
    """
    if any("hate_speech" in r.lower() or "violence" in r.lower() for r in blocked_reasons):
        return (
            "I apologize, but I'm not able to provide a response to that request. "
            "Please feel free to rephrase your question or ask about something else. "
            "I'm here to help!"
        )

    if any("pii" in r.lower() for r in blocked_reasons):
        return (
            "For your security, I've withheld some information from my response. "
            "If you need specific details, please contact our support team directly. "
            "How else can I assist you today?"
        )

    if any("policy" in r.lower() for r in blocked_reasons):
        return (
            "I'm not able to provide advice on that topic. "
            "For specific guidance, please consult a qualified professional. "
            "Is there something else I can help you with?"
        )

    # Generic safe response
    return (
        "I apologize, but I'm unable to provide a complete response to your request. "
        "Please try rephrasing your question, or contact our support team for further assistance."
    )


# ── Smart Router Integration Helper ──────────────────────────────────


def apply_guardrails_to_llm_result(
    llm_result: dict,
    original_query: str,
    company_id: str,
    variant_type: str = "parwa",
) -> dict:
    """Apply guardrails to an LLM result dict from Smart Router.

    This is the primary integration point for Smart Router.
    Call this AFTER Smart Router executes the LLM call.

    Args:
        llm_result: Dict with 'content' key from Smart Router.
        original_query: The customer's original query.
        company_id: Tenant identifier.
        variant_type: PARWA variant type.

    Returns:
        Modified dict with guardrails applied:
        - 'content': Safe response or fallback
        - 'guardrails_action': allow/block/flag_for_review
        - 'guardrails_report': Full report (if available)
        - 'blocked_reasons': List of reasons (if blocked)
        - 'flagged_for_review': True if flagged
    """
    content = llm_result.get("content", "")
    confidence = llm_result.get("confidence", 85.0)

    result = check_llm_response(
        response_content=content,
        original_query=original_query,
        company_id=company_id,
        variant_type=variant_type,
        confidence=confidence,
    )

    # Build output dict
    output = dict(llm_result)  # Copy original
    output["guardrails_action"] = result.action.value
    output["guardrails_checked_at"] = result.checked_at

    if result.action == GuardrailsAction.BLOCK:
        output["content"] = handle_blocked_response(result)
        output["blocked_reasons"] = result.blocked_reasons
        output["original_content_blocked"] = True
        logger.info(
            "Guardrails BLOCKED response for company_id=%s reasons=%s",
            company_id, result.blocked_reasons[:3],
        )

    elif result.action == GuardrailsAction.FLAG_FOR_REVIEW:
        output["flagged_for_review"] = True
        output["flagged_layers"] = result.flagged_layers
        logger.info(
            "Guardrails FLAGGED response for company_id=%s layers=%s",
            company_id, result.flagged_layers,
        )

    else:
        output["guardrails_passed"] = True

    return output
