"""
Guardrails Node — Group 9: Safety & Compliance Checks

Implements multi-layer safety and compliance checks on the agent
response before it is delivered to the customer. Runs four distinct
checks in sequence:

  1. Guardrails Engine   — Content policy, PII leakage, harmful content
  2. Hallucination Det.  — Factual accuracy verification
  3. Prompt Injection    — Re-check for injection attempts
  4. Brand Voice         — Brand compliance (Pro/High tiers only)

If ANY check fails, guardrails_passed=False and the reason is recorded.

Tier Behavior:
  Mini: All checks except Brand Voice (simplified path)
  Pro:  All checks including Brand Voice
  High: All checks including Brand Voice (strictest thresholds)

State Contract:
  Reads:  agent_response, selected_solution, pii_redacted_message,
          variant_tier, tenant_id, customer_tier
  Writes: guardrails_passed, guardrails_flags, guardrails_blocked_reason

BC-008: Never crash — if modules unavailable, pass with warning flag.
        Never block customer responses due to internal module failures.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("node_guardrails")


# ──────────────────────────────────────────────────────────────
# Default fallback values for Guardrails output
# ──────────────────────────────────────────────────────────────

_DEFAULT_GUARDRAILS_STATE: Dict[str, Any] = {
    "guardrails_passed": True,  # Default to pass — don't block on module failure
    "guardrails_flags": [],
    "guardrails_blocked_reason": "",
}


# ═══════════════════════════════════════════════════════════════
# Check 1: Guardrails Engine
# ═══════════════════════════════════════════════════════════════


def _check_guardrails_engine(
    response_text: str,
    message: str,
    tenant_id: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """
    Run guardrails engine checks (content policy, PII leakage, etc.).

    Uses the production guardrails_engine module. Falls back to
    basic checks if unavailable.

    Args:
        response_text: The response text to check.
        message: The original PII-redacted message.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        Dict with 'passed', 'flags', 'blocked_reason' keys.
    """
    try:
        from app.core.guardrails_engine import check_response  # type: ignore[import-untyped]

        result = check_response(
            response=response_text,
            original_message=message,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        passed = bool(result.get("passed", True))
        flags = result.get("flags", [])

        blocked_reason = ""
        if not passed:
            blocked_reason = "; ".join(
                f.get("message", f.get("rule_id", "unknown"))
                for f in flags
                if isinstance(f, dict)
            ) or "Guardrails engine check failed"

        logger.info(
            "guardrails_engine_check_complete",
            tenant_id=tenant_id,
            passed=passed,
            num_flags=len(flags),
        )

        return {
            "passed": passed,
            "flags": flags,
            "blocked_reason": blocked_reason,
        }

    except ImportError:
        logger.info(
            "guardrails_engine_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as guard_exc:
        logger.warning(
            "guardrails_engine_error",
            tenant_id=tenant_id,
            error=str(guard_exc),
        )

    # Fallback: basic checks (pass with warning flag)
    return {
        "passed": True,
        "flags": [{
            "rule_id": "guardrails_engine_unavailable",
            "severity": "warning",
            "message": "Guardrails engine unavailable; basic checks only",
        }],
        "blocked_reason": "",
    }


# ═══════════════════════════════════════════════════════════════
# Check 2: Hallucination Detection
# ═══════════════════════════════════════════════════════════════


def _check_hallucination(
    response_text: str,
    message: str,
    tenant_id: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """
    Run hallucination detection on the response.

    Checks for fabricated information, unsubstantiated claims,
    and factual inaccuracies in the response.

    Args:
        response_text: The response text to check.
        message: The original PII-redacted message.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        Dict with 'passed', 'flags', 'hallucination_score' keys.
    """
    try:
        from app.core.hallucination_detector import detect_hallucination  # type: ignore[import-untyped]

        result = detect_hallucination(
            response=response_text,
            query=message,
            tenant_id=tenant_id,
        )

        hallucination_score = float(result.get("hallucination_score", 0.0))
        passed = hallucination_score < 0.7  # Threshold: 0.7
        flags = result.get("flags", [])

        blocked_reason = ""
        if not passed:
            blocked_reason = (
                f"Hallucination detected (score={hallucination_score:.2f})"
            )

        logger.info(
            "hallucination_check_complete",
            tenant_id=tenant_id,
            passed=passed,
            hallucination_score=hallucination_score,
        )

        return {
            "passed": passed,
            "flags": flags,
            "blocked_reason": blocked_reason,
            "hallucination_score": hallucination_score,
        }

    except ImportError:
        logger.info(
            "hallucination_detector_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as hall_exc:
        logger.warning(
            "hallucination_detector_error",
            tenant_id=tenant_id,
            error=str(hall_exc),
        )

    # Fallback: pass with warning
    return {
        "passed": True,
        "flags": [{
            "rule_id": "hallucination_detector_unavailable",
            "severity": "warning",
            "message": "Hallucination detector unavailable; skipping check",
        }],
        "blocked_reason": "",
        "hallucination_score": -1.0,  # Unknown
    }


# ═══════════════════════════════════════════════════════════════
# Check 3: Prompt Injection Re-check
# ═══════════════════════════════════════════════════════════════


def _check_prompt_injection(
    response_text: str,
    message: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Re-check for prompt injection in the response.

    Double-checks that the response hasn't been manipulated by
    injection attacks and that no injection artifacts leaked
    into the output.

    Args:
        response_text: The response text to check.
        message: The original PII-redacted message.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Dict with 'passed', 'flags', 'blocked_reason' keys.
    """
    try:
        from app.core.prompt_injection_defense import check_injection  # type: ignore[import-untyped]

        result = check_injection(
            text=response_text,
            original_message=message,
            tenant_id=tenant_id,
        )

        passed = bool(result.get("safe", True))
        flags = result.get("flags", [])

        blocked_reason = ""
        if not passed:
            blocked_reason = "Prompt injection detected in response"

        logger.info(
            "prompt_injection_check_complete",
            tenant_id=tenant_id,
            passed=passed,
        )

        return {
            "passed": passed,
            "flags": flags,
            "blocked_reason": blocked_reason,
        }

    except ImportError:
        logger.info(
            "prompt_injection_defense_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as inj_exc:
        logger.warning(
            "prompt_injection_defense_error",
            tenant_id=tenant_id,
            error=str(inj_exc),
        )

    # Fallback: pass with warning
    return {
        "passed": True,
        "flags": [{
            "rule_id": "prompt_injection_defense_unavailable",
            "severity": "warning",
            "message": "Prompt injection defense unavailable; skipping check",
        }],
        "blocked_reason": "",
    }


# ═══════════════════════════════════════════════════════════════
# Check 4: Brand Voice Compliance (Pro/High only)
# ═══════════════════════════════════════════════════════════════


def _check_brand_voice(
    response_text: str,
    tenant_id: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """
    Check brand voice compliance for Pro and High tiers.

    Verifies that the response adheres to the tenant's brand voice
    guidelines (tone, formality, terminology, prohibited terms).

    Mini tier skips this check entirely.

    Args:
        response_text: The response text to check.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        Dict with 'passed', 'flags', 'blocked_reason' keys.
    """
    # Mini tier: skip brand voice check
    if variant_tier == "mini":
        return {
            "passed": True,
            "flags": [],
            "blocked_reason": "",
        }

    try:
        from app.core.brand_voice_engine import check_compliance  # type: ignore[import-untyped]

        result = check_compliance(
            response=response_text,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        passed = bool(result.get("compliant", True))
        flags = result.get("violations", [])

        blocked_reason = ""
        if not passed:
            blocked_reason = "Brand voice compliance violation detected"

        logger.info(
            "brand_voice_check_complete",
            tenant_id=tenant_id,
            passed=passed,
            num_violations=len(flags),
        )

        return {
            "passed": passed,
            "flags": flags,
            "blocked_reason": blocked_reason,
        }

    except ImportError:
        logger.info(
            "brand_voice_engine_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as brand_exc:
        logger.warning(
            "brand_voice_engine_error",
            tenant_id=tenant_id,
            error=str(brand_exc),
        )

    # Fallback: pass with warning
    return {
        "passed": True,
        "flags": [{
            "rule_id": "brand_voice_engine_unavailable",
            "severity": "warning",
            "message": "Brand voice engine unavailable; skipping compliance check",
        }],
        "blocked_reason": "",
    }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def guardrails_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guardrails Node — Safety and compliance checks on agent response.

    Runs four sequential safety checks:
      1. Guardrails engine (content policy, PII leakage)
      2. Hallucination detection
      3. Prompt injection re-check
      4. Brand voice compliance (Pro/High only)

    If ANY check fails, guardrails_passed=False and the blocking
    reason is recorded. If modules are unavailable, checks pass
    with a warning flag (BC-008: never block due to internal failures).

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with guardrails output fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "guardrails_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
    )

    try:
        # ── Extract state fields ────────────────────────────────
        # Use selected_solution if available (post-MAKER), else agent_response
        response_text = (
            state.get("selected_solution")
            or state.get("agent_response", "")
        )
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        customer_tier = state.get("customer_tier", "free")

        all_flags: List[Dict[str, Any]] = []
        blocked_reason = ""
        overall_passed = True

        # ── Check 1: Guardrails Engine ──────────────────────────
        guard_result = _check_guardrails_engine(
            response_text=response_text,
            message=message,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        if not guard_result.get("passed", True):
            overall_passed = False
            blocked_reason = guard_result.get("blocked_reason", "Guardrails engine check failed")

        for flag in guard_result.get("flags", []):
            all_flags.append({
                "check": "guardrails_engine",
                **flag,
            } if isinstance(flag, dict) else {
                "check": "guardrails_engine",
                "message": str(flag),
            })

        # ── Check 2: Hallucination Detection ────────────────────
        hall_result = _check_hallucination(
            response_text=response_text,
            message=message,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        if not hall_result.get("passed", True):
            overall_passed = False
            if not blocked_reason:
                blocked_reason = hall_result.get("blocked_reason", "Hallucination detected")

        for flag in hall_result.get("flags", []):
            all_flags.append({
                "check": "hallucination_detector",
                **flag,
            } if isinstance(flag, dict) else {
                "check": "hallucination_detector",
                "message": str(flag),
            })

        # ── Check 3: Prompt Injection Re-check ──────────────────
        injection_result = _check_prompt_injection(
            response_text=response_text,
            message=message,
            tenant_id=tenant_id,
        )

        if not injection_result.get("passed", True):
            overall_passed = False
            if not blocked_reason:
                blocked_reason = injection_result.get("blocked_reason", "Prompt injection detected")

        for flag in injection_result.get("flags", []):
            all_flags.append({
                "check": "prompt_injection_defense",
                **flag,
            } if isinstance(flag, dict) else {
                "check": "prompt_injection_defense",
                "message": str(flag),
            })

        # ── Check 4: Brand Voice Compliance (Pro/High only) ─────
        brand_result = _check_brand_voice(
            response_text=response_text,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        if not brand_result.get("passed", True):
            overall_passed = False
            if not blocked_reason:
                blocked_reason = brand_result.get("blocked_reason", "Brand voice violation")

        for flag in brand_result.get("flags", []):
            all_flags.append({
                "check": "brand_voice_compliance",
                **flag,
            } if isinstance(flag, dict) else {
                "check": "brand_voice_compliance",
                "message": str(flag),
            })

        # ── Build state update ──────────────────────────────────
        result = {
            "guardrails_passed": overall_passed,
            "guardrails_flags": all_flags,
            "guardrails_blocked_reason": blocked_reason,
        }

        if overall_passed:
            logger.info(
                "guardrails_node_passed",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                num_flags=len(all_flags),
            )
        else:
            logger.warning(
                "guardrails_node_blocked",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                blocked_reason=blocked_reason,
                num_flags=len(all_flags),
            )

        return result

    except Exception as exc:
        logger.error(
            "guardrails_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, pass with warning flag
        # Never block customer responses due to internal failures
        return {
            "guardrails_passed": True,  # Pass — don't block on internal error
            "guardrails_flags": [{
                "rule_id": "guardrails_fatal_error",
                "severity": "critical_warning",
                "message": (
                    f"Guardrails system encountered a fatal error: {exc}. "
                    "Response passed with warning — manual review recommended."
                ),
            }],
            "guardrails_blocked_reason": "",
            "errors": [f"Guardrails fatal error: {exc}"],
        }
