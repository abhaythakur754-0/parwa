"""
Guardrails Integration Module (Day 2 - Safety & Compliance)

Wires the GuardrailsEngine to the Smart Router / AI Pipeline.
Every LLM response passes through guardrails BEFORE reaching the customer.

Integration Flow:
1. Smart Router executes LLM call
2. Response passes through Day 4 output scanners (PII → Prompt Injection → Info Leak)
3. Response passes through GuardrailsEngine.run_full_scan() (Layers 1-8)
4. If BLOCKED → Route to BlockedResponseManager
5. If FLAG_FOR_REVIEW → Deliver with metadata flag
6. If ALLOW → Deliver normally

Day 1 Sprint: Wire Day 4 output scanners into the live pipeline,
add shadow mode bypass, add Prometheus metrics.

BC-007: All AI through Smart Router
BC-009: Approval workflow for blocked responses
BC-001: company_id is always second parameter
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.guardrails_engine import GuardrailsReport, GuardrailsEngine
    from app.core.blocked_response_manager import BlockedResponseManager

logger = logging.getLogger("parwa.guardrails_integration")


# ── Prometheus Metrics (Day 1 Sprint) ──────────────────────────────

try:
    from app.core.metrics import get_registry

    _metrics_registry = get_registry()
    _guardrails_total = _metrics_registry.counter(
        "parwa_guardrails_checks_total",
        "Total guardrails checks",
        ["company_id", "variant_type", "action"],
    )
    _guardrails_duration = _metrics_registry.histogram(
        "parwa_guardrails_check_duration_seconds",
        "Guardrails check duration",
        ["company_id", "variant_type"],
    )
    _guardrails_blocks = _metrics_registry.counter(
        "parwa_guardrails_blocks_total",
        "Total responses blocked by guardrails",
        ["company_id", "variant_type", "layer"],
    )
    _output_scans_total = _metrics_registry.counter(
        "parwa_output_scans_total",
        "Total Day 4 output scans",
        ["company_id", "scanner", "action"],
    )
    _METRICS_ENABLED = True
except Exception:
    _METRICS_ENABLED = False
    logger.debug("Prometheus metrics not available for guardrails integration")


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
    shadow_mode: Optional[str] = None,
) -> GuardrailsCheckResult:
    """Check LLM response through all guardrail layers.

    This is the main integration point called after LLM generation.
    Runs Day 4 output scanners (PII, Prompt Injection, Info Leak)
    BEFORE the main guardrails engine.

    Day 1 Sprint: Added shadow_mode parameter — when shadow mode is
    'shadow' (observation only), guardrails still runs but actions
    are downgraded to FLAG_FOR_REVIEW instead of BLOCK.

    Args:
        response_content: The LLM-generated response text.
        original_query: The customer's original query.
        company_id: Tenant identifier (BC-001).
        variant_type: PARWA variant for strictness level.
        confidence: AI confidence score from LLM.
        engine: Optional pre-configured GuardrailsEngine.
        shadow_mode: Current shadow mode for the company (None, 'shadow',
                     'supervised', 'graduated'). When 'shadow', blocks are
                     downgraded to flags.

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

    start_time = time.monotonic()

    # ── Day 4 Output Scanners (run BEFORE main guardrails) ────────────
    day4_issues = _run_day4_output_scanners(
        response_content=response_content,
        original_query=original_query,
        company_id=company_id,
    )

    # Lazy import to avoid circular dependencies
    from app.core.guardrails_engine import GuardrailsEngine

    # Use provided engine or create new one
    guardrails_engine = engine or GuardrailsEngine()

    try:
        # Run full guardrail scan (Layers 1-8)
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

        # Add Day 4 scanner results to reasons
        for issue in day4_issues:
            if issue["severity"] in ("critical", "high"):
                blocked_reasons.append(issue["reason"])
            else:
                flagged_layers.append(issue["scanner"])

        # Shadow mode bypass: downgrade BLOCK to FLAG_FOR_REVIEW
        if shadow_mode == "shadow" and action == GuardrailsAction.BLOCK:
            logger.info(
                "Shadow mode bypass: downgrading BLOCK to FLAG_FOR_REVIEW "
                "for company_id=%s shadow_mode=%s",
                company_id, shadow_mode,
            )
            action = GuardrailsAction.FLAG_FOR_REVIEW
            flagged_layers.extend(
                [r.split(":")[0] for r in blocked_reasons]
            )
            blocked_reasons = []

        # Record Prometheus metrics
        duration = time.monotonic() - start_time
        if _METRICS_ENABLED:
            try:
                _guardrails_total.labels(
                    company_id=company_id,
                    variant_type=variant_type,
                    action=action.value,
                ).inc()
                _guardrails_duration.labels(
                    company_id=company_id,
                    variant_type=variant_type,
                ).observe(duration)
                if action == GuardrailsAction.BLOCK:
                    for reason in blocked_reasons:
                        layer = reason.split(
                            ":")[0] if ":" in reason else "unknown"
                        _guardrails_blocks.labels(
                            company_id=company_id,
                            variant_type=variant_type,
                            layer=layer,
                        ).inc()
            except Exception:
                logger.debug("Failed to record guardrails metrics")

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
    if any("hate_speech" in r.lower() or "violence" in r.lower()
           for r in blocked_reasons):
        return (
            "I apologize, but I'm not able to provide a response to that request. "
            "Please feel free to rephrase your question or ask about something else. "
            "I'm here to help!")

    if any("pii" in r.lower() for r in blocked_reasons):
        return (
            "For your security, I've withheld some information from my response. "
            "If you need specific details, please contact our support team directly. "
            "How else can I assist you today?")

    if any("policy" in r.lower() for r in blocked_reasons):
        return (
            "I'm not able to provide advice on that topic. "
            "For specific guidance, please consult a qualified professional. "
            "Is there something else I can help you with?"
        )

    # Generic safe response
    return ("I apologize, but I'm unable to provide a complete response to your request. "
            "Please try rephrasing your question, or contact our support team for further assistance.")


# ── Day 4 Output Scanners (Day 1 Sprint wiring) ──────────────────


def _run_day4_output_scanners(
    response_content: str,
    original_query: str,
    company_id: str,
) -> List[Dict[str, Any]]:
    """Run Day 4 output scanners on LLM response BEFORE main guardrails.

    Scans in order: PII Output Scan → Prompt Injection Output Scan → Info Leak Guard.
    This implements layers 9-11 from the guardrails engine TODO list.

    Each scanner is called defensively — a failure in one scanner
    does not prevent others from running (BC-012).

    Args:
        response_content: The LLM-generated response text.
        original_query: The customer's original query.
        company_id: Tenant identifier (BC-001).

    Returns:
        List of issue dicts with keys: scanner, severity, reason.
        Empty list means all scanners passed.
    """
    issues: List[Dict[str, Any]] = []

    # Scanner 1: PII Output Scan (Layer 11)
    try:
        from app.core.pii_redaction_engine import PIIDetector
        pii_detector = PIIDetector()
        pii_matches = pii_detector.detect(response_content)
        if pii_matches:
            high_conf_pii = [m for m in pii_matches if m.confidence >= 0.80]
            if high_conf_pii:
                pii_types = sorted({m.pii_type for m in high_conf_pii})
                issues.append({
                    "scanner": "pii_output_scan",
                    "severity": "critical",
                    "reason": (
                        "PII detected in LLM output: "
                        f"{', '.join(pii_types)} "
                        f"({len(high_conf_pii)} instance(s))"
                    ),
                })
                logger.warning(
                    "PII detected in LLM output for company_id=%s types=%s count=%d",
                    company_id,
                    pii_types,
                    len(high_conf_pii),
                )
        # Record metrics
        if _METRICS_ENABLED:
            try:
                action = "block" if pii_matches and any(
                    m.confidence >= 0.80 for m in pii_matches
                ) else "allow"
                _output_scans_total.labels(
                    company_id=company_id,
                    scanner="pii_output_scan",
                    action=action,
                ).inc()
            except Exception:
                pass
    except Exception as e:
        logger.error(
            "PII output scan failed for company_id=%s: %s",
            company_id,
            e)

    # Scanner 2: Prompt Injection Output Scan (Layer 10)
    try:
        from app.core.prompt_injection_defense import PromptInjectionDetector
        injection_detector = PromptInjectionDetector()
        injection_result = injection_detector.scan(
            query=response_content,  # Scan the OUTPUT for injection remnants
            company_id=company_id,
        )
        if injection_result and getattr(
                injection_result, "is_injection", False):
            issues.append({
                "scanner": "prompt_injection_output",
                "severity": "high",
                "reason": (
                    "Prompt injection remnants in LLM output: "
                    f"{getattr(injection_result, 'reason', 'unknown')}"
                ),
            })
            logger.warning(
                "Prompt injection remnants in LLM output for company_id=%s",
                company_id,
            )
        # Record metrics
        if _METRICS_ENABLED:
            try:
                action = "block" if injection_result and getattr(
                    injection_result, "is_injection", False
                ) else "allow"
                _output_scans_total.labels(
                    company_id=company_id,
                    scanner="prompt_injection_output",
                    action=action,
                ).inc()
            except Exception:
                pass
    except Exception as e:
        logger.error(
            "Prompt injection output scan failed for company_id=%s: %s",
            company_id,
            e)

    # Scanner 3: Info Leak Guard (Layer 9)
    try:
        from app.core.info_leak_guard import InfoLeakGuard
        info_leak_guard = InfoLeakGuard()
        leak_result = info_leak_guard.scan(
            response=response_content,
            company_id=company_id,
        )
        if leak_result and getattr(leak_result, "has_leak", False):
            leak_action = getattr(leak_result, "action", "allow")
            categories = sorted({
                m.category for m in getattr(leak_result, "matches", [])
            })
            severity = "high" if leak_action == "block" else "medium"
            issues.append({
                "scanner": "info_leak_guard",
                "severity": severity,
                "reason": (
                    "Information leak in LLM output: "
                    f"categories={', '.join(categories)} "
                    f"action={leak_action}"
                ),
            })
            logger.warning(
                "Info leak detected in LLM output for company_id=%s categories=%s",
                company_id,
                categories,
            )
        # Record metrics
        if _METRICS_ENABLED:
            try:
                action = getattr(
                    leak_result,
                    "action",
                    "allow") if leak_result else "allow"
                _output_scans_total.labels(
                    company_id=company_id,
                    scanner="info_leak_guard",
                    action=action,
                ).inc()
            except Exception:
                pass
    except Exception as e:
        logger.error(
            "Info leak output scan failed for company_id=%s: %s",
            company_id,
            e)

    return issues


# ── Smart Router Integration Helper ──────────────────────────────────


def apply_guardrails_to_llm_result(
    llm_result: dict,
    original_query: str,
    company_id: str,
    variant_type: str = "parwa",
    shadow_mode: Optional[str] = None,
) -> dict:
    """Apply guardrails to an LLM result dict from Smart Router.

    This is the primary integration point for Smart Router.
    Call this AFTER Smart Router executes the LLM call.

    Day 1 Sprint: Added shadow_mode parameter for shadow mode bypass.

    Args:
        llm_result: Dict with 'content' key from Smart Router.
        original_query: The customer's original query.
        company_id: Tenant identifier.
        variant_type: PARWA variant type.
        shadow_mode: Current shadow mode for the company.

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
        shadow_mode=shadow_mode,
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
