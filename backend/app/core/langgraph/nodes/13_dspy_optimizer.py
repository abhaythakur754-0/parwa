"""
DSPy Optimizer Node — Group 8: Prompt Optimization

Applies DSPy-based prompt optimization to improve response quality.
DSPy (Demonstrate-Search-Predict) uses compiled examples and
teleprompter techniques to optimize prompts for the specific
tenant and domain.

Tier Behavior:
  Mini: Skip DSPy entirely (not worth the token cost)
  Pro:  Apply DSPy only for complex queries (complexity > 0.5)
  High: Always apply DSPy for maximum response quality

State Contract:
  Reads:  variant_tier, pii_redacted_message, intent,
          agent_response, tenant_id, complexity_score
  Writes: prompt_optimized, optimized_prompt_version

BC-008: Never crash — if DSPy unavailable, sets prompt_optimized=False.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("node_dspy_optimizer")


# ──────────────────────────────────────────────────────────────
# Default fallback values for DSPy output
# ──────────────────────────────────────────────────────────────

_DEFAULT_DSPY_STATE: Dict[str, Any] = {
    "prompt_optimized": False,
    "optimized_prompt_version": "",
}


# ═══════════════════════════════════════════════════════════════
# Internal: DSPy optimization core
# ═══════════════════════════════════════════════════════════════


def _apply_dspy_optimization(
    message: str,
    agent_response: str,
    intent: str,
    tenant_id: str,
    variant_tier: str,
) -> Dict[str, Any]:
    """
    Apply DSPy prompt optimization.

    Uses the production dspy_integration module to compile and
    optimize prompts. Falls back gracefully if unavailable.

    Args:
        message: The PII-redacted customer message.
        agent_response: The domain agent's response.
        intent: Classified intent string.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        Dict with 'optimized', 'version', 'optimized_prompt' keys.
    """
    try:
        from app.core.dspy_integration import optimize_prompt  # type: ignore[import-untyped]

        result = optimize_prompt(
            query=message,
            response=agent_response,
            intent=intent,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        optimized = bool(result.get("optimized", False))
        version = str(result.get("version", ""))

        logger.info(
            "dspy_optimization_applied",
            tenant_id=tenant_id,
            optimized=optimized,
            version=version,
        )

        return {
            "optimized": optimized,
            "version": version,
            "optimized_prompt": result.get("optimized_prompt", ""),
        }

    except ImportError:
        logger.info(
            "dspy_integration_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as dspy_exc:
        logger.warning(
            "dspy_optimization_error",
            tenant_id=tenant_id,
            error=str(dspy_exc),
        )

    return {
        "optimized": False,
        "version": "",
        "optimized_prompt": "",
    }


# ═══════════════════════════════════════════════════════════════
# Internal: Complexity threshold check
# ═══════════════════════════════════════════════════════════════


def _should_apply_dspy(
    variant_tier: str,
    complexity_score: float,
    tenant_id: str,
) -> bool:
    """
    Determine whether DSPy should be applied for this request.

    Tier rules:
      - Mini: Never (skip entirely — not worth token cost)
      - Pro:  Only if complexity > 0.5 (cost-benefit tradeoff)
      - High: Always (maximum quality)

    Args:
        variant_tier: Variant tier string.
        complexity_score: Query complexity 0.0-1.0.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        True if DSPy should be applied.
    """
    if variant_tier == "mini":
        logger.info(
            "dspy_skipped_mini_tier",
            tenant_id=tenant_id,
            reason="DSPy skipped for mini tier (not worth token cost)",
        )
        return False

    if variant_tier == "pro":
        if complexity_score <= 0.5:
            logger.info(
                "dspy_skipped_pro_low_complexity",
                tenant_id=tenant_id,
                complexity_score=complexity_score,
                threshold=0.5,
                reason="DSPy skipped for Pro tier with low complexity query",
            )
            return False
        return True

    # High tier: always apply
    return True


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def dspy_optimizer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    DSPy Optimizer Node — Prompt optimization for improved response quality.

    Applies DSPy-based prompt optimization based on variant tier:
      - Mini: Skip DSPy entirely (not worth token cost)
      - Pro:  Apply DSPy only for complex queries (complexity > 0.5)
      - High: Always apply DSPy

    If DSPy module is unavailable, sets prompt_optimized=False gracefully.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with DSPy optimizer output fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "dspy_optimizer_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        intent=state.get("intent", "unknown"),
    )

    try:
        # ── Extract state fields ────────────────────────────────
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        intent = state.get("intent", "general")
        agent_response = state.get("agent_response", "")
        complexity_score = float(state.get("complexity_score", 0.0))

        # ── Check if DSPy should be applied ─────────────────────
        if not _should_apply_dspy(variant_tier, complexity_score, tenant_id):
            return {
                "prompt_optimized": False,
                "optimized_prompt_version": "",
            }

        # ── Apply DSPy optimization ─────────────────────────────
        dspy_result = _apply_dspy_optimization(
            message=message,
            agent_response=agent_response,
            intent=intent,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        prompt_optimized = dspy_result.get("optimized", False)
        optimized_prompt_version = dspy_result.get("version", "")

        # ── Build state update ──────────────────────────────────
        result = {
            "prompt_optimized": prompt_optimized,
            "optimized_prompt_version": optimized_prompt_version,
        }

        logger.info(
            "dspy_optimizer_node_success",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            prompt_optimized=prompt_optimized,
            optimized_prompt_version=optimized_prompt_version,
        )

        return result

    except Exception as exc:
        logger.error(
            "dspy_optimizer_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: If DSPy fails, just skip optimization
        return {
            **_DEFAULT_DSPY_STATE,
            "errors": [f"DSPy optimizer fatal error: {exc}"],
        }
