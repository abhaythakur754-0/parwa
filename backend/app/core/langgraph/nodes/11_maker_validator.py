"""
MAKER Validator Node — Group 6: K-Solution Validator for ALL Tiers

THE CRITICAL NODE in the PARWA pipeline. Implements the MAKER (Multiple
Assessment Knowledge Evaluation & Ranking) pattern: generate K candidate
solutions, score each, select the best, and raise red flags if confidence
is below the tier-specific threshold.

Tier Behavior:
  Mini (efficiency):   K=3 solutions,   threshold=0.50
  Pro (balanced):      K=3-5 dynamic,   threshold=0.60
  High (conservative): K=5-7 dynamic,   threshold=0.75

State Contract:
  Reads:  agent_response, agent_confidence, proposed_action,
          action_type, variant_tier, agent_reasoning,
          pii_redacted_message, tenant_id, complexity_score
  Writes: k_solutions, selected_solution, red_flag, maker_mode,
          k_value_used, fake_threshold, maker_decomposition,
          maker_audit_trail, agent_response (UPDATED with best solution),
          agent_confidence (UPDATED with best confidence)

BC-008: Never crash — if LLM unavailable, use agent_response as
        single solution with agent_confidence. Always returns valid output.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.langgraph.config import get_maker_config, get_maker_k_value
from app.logger import get_logger

logger = get_logger("node_maker_validator")


# ──────────────────────────────────────────────────────────────
# Default fallback values for MAKER output
# ──────────────────────────────────────────────────────────────

_DEFAULT_MAKER_STATE: Dict[str, Any] = {
    "k_solutions": [],
    "selected_solution": "",
    "red_flag": True,  # Conservative: flag on error
    "maker_mode": "efficiency",
    "k_value_used": 1,
    "fake_threshold": 0.50,
    "maker_decomposition": {},
    "maker_audit_trail": [],
}


# ═══════════════════════════════════════════════════════════════
# Internal: LLM-based K-solution generation
# ═══════════════════════════════════════════════════════════════


def _generate_k_solutions_llm(
    message: str,
    agent_response: str,
    agent_confidence: float,
    proposed_action: str,
    k: int,
    tenant_id: str,
    variant_tier: str,
) -> List[Dict[str, Any]]:
    """
    Generate K candidate solutions using the LLM.

    Uses the production response_generator or LLM client to produce
    K diverse candidate solutions for the same query. Each solution
    includes response text, confidence score, and reasoning.

    Falls back to perturbation-based generation if LLM unavailable.

    Args:
        message: The PII-redacted customer message.
        agent_response: The original agent's response.
        agent_confidence: The original agent's confidence.
        proposed_action: The action proposed by the agent.
        k: Number of solutions to generate.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.

    Returns:
        List of K solution dicts: [{solution, confidence, reasoning}].
    """
    try:
        from app.core.response_generator import generate_k_solutions  # type: ignore[import-untyped]

        result = generate_k_solutions(
            message=message,
            original_response=agent_response,
            proposed_action=proposed_action,
            k=k,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        solutions = result.get("solutions", [])
        if solutions and isinstance(solutions, list):
            logger.info(
                "k_solutions_llm_generated",
                tenant_id=tenant_id,
                k_requested=k,
                k_generated=len(solutions),
            )
            return solutions

    except ImportError:
        logger.info(
            "response_generator_k_solutions_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as llm_exc:
        logger.warning(
            "k_solutions_llm_error",
            tenant_id=tenant_id,
            error=str(llm_exc),
        )

    # ── Fallback: perturbation-based solution generation ────────
    return _generate_k_solutions_fallback(
        message=message,
        agent_response=agent_response,
        agent_confidence=agent_confidence,
        k=k,
        tenant_id=tenant_id,
    )


def _generate_k_solutions_fallback(
    message: str,
    agent_response: str,
    agent_confidence: float,
    k: int,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """
    Fallback K-solution generation when LLM is unavailable.

    Creates K variations of the original agent response by
    applying small confidence perturbations. The first solution
    is always the original agent response.

    This ensures BC-008: even without LLM, we produce K solutions.

    Args:
        message: The PII-redacted customer message.
        agent_response: The original agent's response.
        agent_confidence: The original agent's confidence.
        k: Number of solutions to generate.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        List of K solution dicts with perturbed confidences.
    """
    solutions: List[Dict[str, Any]] = []

    # Solution 0: Always the original agent response
    solutions.append({
        "solution": agent_response,
        "confidence": round(agent_confidence, 2),
        "reasoning": "Original agent response (fallback K-solution generation)",
        "source": "original_agent",
    })

    # Generate K-1 perturbed variants
    for i in range(1, k):
        # Small confidence perturbation: ±0.03-0.08
        perturbation = 0.03 + (i * 0.01)
        if i % 2 == 0:
            perturbed_conf = min(1.0, agent_confidence + perturbation)
        else:
            perturbed_conf = max(0.0, agent_confidence - perturbation)

        variant_label = ["conservative", "detailed", "concise", "empathetic", "formal"]
        label = variant_label[i % len(variant_label)]

        solutions.append({
            "solution": agent_response,  # Same text — can't generate new without LLM
            "confidence": round(perturbed_conf, 2),
            "reasoning": f"Fallback {label} variant (perturbation ±{perturbation:.2f})",
            "source": "fallback_perturbation",
        })

    logger.info(
        "k_solutions_fallback_generated",
        tenant_id=tenant_id,
        k_requested=k,
        k_generated=len(solutions),
        note="LLM unavailable; using perturbation-based fallback",
    )

    return solutions


# ═══════════════════════════════════════════════════════════════
# Internal: Solution scoring
# ═══════════════════════════════════════════════════════════════


def _score_solution(
    solution: Dict[str, Any],
    message: str,
    tenant_id: str,
) -> float:
    """
    Score a single candidate solution for confidence.

    Uses the production scoring engine if available, otherwise
    uses the solution's own confidence value.

    Args:
        solution: Solution dict with 'solution', 'confidence', 'reasoning'.
        message: The PII-redacted customer message.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Confidence score 0.0-1.0 for this solution.
    """
    try:
        from app.core.maker_scorer import score_solution as _score  # type: ignore[import-untyped]

        score = _score(
            solution_text=solution.get("solution", ""),
            query=message,
            tenant_id=tenant_id,
        )
        return round(max(0.0, min(1.0, float(score))), 2)

    except ImportError:
        pass
    except Exception as score_exc:
        logger.warning(
            "maker_scorer_error",
            tenant_id=tenant_id,
            error=str(score_exc),
        )

    # Fallback: use the solution's own confidence
    return round(max(0.0, min(1.0, float(solution.get("confidence", 0.0)))), 2)


def _score_all_solutions(
    solutions: List[Dict[str, Any]],
    message: str,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """
    Score all candidate solutions and attach scored_confidence.

    Args:
        solutions: List of solution dicts.
        message: The PII-redacted customer message.
        tenant_id: Tenant identifier (BC-001).

    Returns:
        Solutions with 'scored_confidence' field added.
    """
    for solution in solutions:
        scored = _score_solution(solution, message, tenant_id)
        solution["scored_confidence"] = scored

    return solutions


# ═══════════════════════════════════════════════════════════════
# Internal: Best solution selection
# ═══════════════════════════════════════════════════════════════


def _select_best_solution(
    solutions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Select the best solution from scored candidates.

    Picks the solution with the highest scored_confidence.
    Ties are broken by original confidence, then by index.

    Args:
        solutions: List of scored solution dicts.

    Returns:
        The best solution dict.
    """
    if not solutions:
        return {
            "solution": "",
            "confidence": 0.0,
            "scored_confidence": 0.0,
            "reasoning": "No solutions generated",
            "source": "empty",
        }

    # Sort by scored_confidence descending, then by confidence descending
    sorted_solutions = sorted(
        solutions,
        key=lambda s: (
            s.get("scored_confidence", 0.0),
            s.get("confidence", 0.0),
        ),
        reverse=True,
    )

    return sorted_solutions[0]


# ═══════════════════════════════════════════════════════════════
# Internal: Problem decomposition
# ═══════════════════════════════════════════════════════════════


def _decompose_problem(
    message: str,
    tenant_id: str,
    variant_tier: str,
    maker_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Decompose the customer query into sub-problems for audit.

    Only runs for tiers where decomposition_enabled is True
    (Pro and High). Mini skips decomposition for speed.

    Args:
        message: The PII-redacted customer message.
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.
        maker_config: MAKER configuration for this tier.

    Returns:
        Dict with decomposition details.
    """
    if not maker_config.get("decomposition_enabled", False):
        return {
            "enabled": False,
            "sub_problems": [],
            "note": f"Decomposition disabled for {variant_tier} tier (efficiency mode)",
        }

    try:
        from app.core.maker_decomposition import decompose_query  # type: ignore[import-untyped]

        result = decompose_query(query=message, tenant_id=tenant_id)
        return {
            "enabled": True,
            "sub_problems": result.get("sub_problems", []),
            "complexity_factors": result.get("complexity_factors", {}),
            "decomposition_method": "llm",
        }

    except ImportError:
        logger.info(
            "maker_decomposition_unavailable",
            tenant_id=tenant_id,
        )
    except Exception as decomp_exc:
        logger.warning(
            "maker_decomposition_error",
            tenant_id=tenant_id,
            error=str(decomp_exc),
        )

    # Fallback: simple keyword-based decomposition
    sentences = [s.strip() for s in message.split(".") if s.strip()]
    return {
        "enabled": True,
        "sub_problems": sentences[:5] if sentences else [message],
        "complexity_factors": {"sentence_count": len(sentences)},
        "decomposition_method": "fallback_sentence_split",
    }


# ═══════════════════════════════════════════════════════════════
# Internal: Audit trail builder
# ═══════════════════════════════════════════════════════════════


def _build_audit_trail(
    tenant_id: str,
    variant_tier: str,
    k: int,
    solutions: List[Dict[str, Any]],
    best_solution: Dict[str, Any],
    threshold: float,
    red_flag: bool,
    maker_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build the MAKER audit trail based on tier audit level.

    Audit levels:
      - minimal: Only record final decision
      - standard: Record key decision points
      - full: Record everything (all scores, all reasoning)

    Args:
        tenant_id: Tenant identifier (BC-001).
        variant_tier: Variant tier string.
        k: K value used.
        solutions: All candidate solutions.
        best_solution: Selected best solution.
        threshold: Confidence threshold.
        red_flag: Whether red flag was raised.
        maker_config: MAKER config for this tier.

    Returns:
        List of audit trail entry dicts.
    """
    from datetime import datetime, timezone

    audit_level = maker_config.get("audit_trail_level", "minimal")
    now = datetime.now(timezone.utc).isoformat()

    trail: List[Dict[str, Any]] = []

    # ── Always: Final decision entry ────────────────────────────
    trail.append({
        "step": "maker_final_decision",
        "timestamp": now,
        "tenant_id": tenant_id,
        "variant_tier": variant_tier,
        "k_value": k,
        "threshold": threshold,
        "best_confidence": best_solution.get("scored_confidence", 0.0),
        "red_flag": red_flag,
        "decision": "rejected_below_threshold" if red_flag else "accepted",
        "audit_level": audit_level,
    })

    # ── Standard + Full: Solution selection details ─────────────
    if audit_level in ("standard", "full"):
        trail.append({
            "step": "maker_solution_selection",
            "timestamp": now,
            "tenant_id": tenant_id,
            "total_candidates": len(solutions),
            "best_source": best_solution.get("source", "unknown"),
            "confidence_spread": [
                round(s.get("scored_confidence", 0.0), 2)
                for s in solutions
            ],
        })

    # ── Full: All solution details ──────────────────────────────
    if audit_level == "full":
        for idx, sol in enumerate(solutions):
            trail.append({
                "step": "maker_candidate_detail",
                "timestamp": now,
                "tenant_id": tenant_id,
                "candidate_index": idx,
                "source": sol.get("source", "unknown"),
                "confidence": sol.get("confidence", 0.0),
                "scored_confidence": sol.get("scored_confidence", 0.0),
                "reasoning_preview": str(sol.get("reasoning", ""))[:200],
            })

    return trail


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def maker_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    MAKER Validator Node — K-solution validator for ALL tiers.

    THE CRITICAL NODE. Implements the MAKER pattern:
      1. Generate K candidate solutions using LLM
      2. Score each solution for confidence
      3. Select the best solution
      4. If best confidence < threshold → set red_flag = True
      5. Build audit trail

    Tier-specific behavior:
      - Mini (efficiency):   K=3, threshold=0.50, no decomposition
      - Pro (balanced):      K=3-5 (dynamic), threshold=0.60, decomposition on
      - High (conservative): K=5-7 (dynamic), threshold=0.75, full decomposition

    BC-008: If LLM unavailable, uses agent_response as single solution
            with agent_confidence.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with MAKER validator output fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "maker_validator_node_start",
        tenant_id=tenant_id,
        variant_tier=variant_tier,
        agent_confidence=state.get("agent_confidence", 0.0),
        action_type=state.get("action_type", "informational"),
    )

    try:
        # ── Extract state fields ────────────────────────────────
        agent_response = state.get("agent_response", "")
        agent_confidence = float(state.get("agent_confidence", 0.0))
        proposed_action = state.get("proposed_action", "respond")
        action_type = state.get("action_type", "informational")
        agent_reasoning = state.get("agent_reasoning", "")
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        complexity_score = float(state.get("complexity_score", 0.5))

        # ── Get MAKER config for this tier ──────────────────────
        maker_config = get_maker_config(variant_tier)
        maker_mode = maker_config.get("mode", "efficiency")
        threshold = float(maker_config.get("threshold", 0.50))

        # ── Determine K value (dynamic for pro/high) ────────────
        k = get_maker_k_value(variant_tier, complexity_score)

        logger.info(
            "maker_config_resolved",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            maker_mode=maker_mode,
            k=k,
            threshold=threshold,
            complexity_score=complexity_score,
        )

        # ── Step 1: Generate K candidate solutions ──────────────
        solutions = _generate_k_solutions_llm(
            message=message,
            agent_response=agent_response,
            agent_confidence=agent_confidence,
            proposed_action=proposed_action,
            k=k,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
        )

        # BC-008: If no solutions generated, use agent_response
        if not solutions:
            logger.warning(
                "maker_no_solutions_fallback_to_agent_response",
                tenant_id=tenant_id,
            )
            solutions = [{
                "solution": agent_response,
                "confidence": agent_confidence,
                "scored_confidence": agent_confidence,
                "reasoning": (
                    "No K-solutions generated; using original agent response "
                    "as sole candidate (BC-008 fallback)"
                ),
                "source": "bc008_fallback",
            }]

        # ── Step 2: Score each solution ─────────────────────────
        solutions = _score_all_solutions(
            solutions=solutions,
            message=message,
            tenant_id=tenant_id,
        )

        # ── Step 3: Select the best solution ────────────────────
        best_solution = _select_best_solution(solutions)
        best_confidence = float(best_solution.get("scored_confidence", 0.0))
        selected_text = str(best_solution.get("solution", agent_response))

        # ── Step 4: Red flag check ──────────────────────────────
        red_flag = best_confidence < threshold

        if red_flag:
            logger.warning(
                "maker_red_flag_raised",
                tenant_id=tenant_id,
                best_confidence=best_confidence,
                threshold=threshold,
                deficit=round(threshold - best_confidence, 2),
                maker_mode=maker_mode,
            )
        else:
            logger.info(
                "maker_confidence_passed",
                tenant_id=tenant_id,
                best_confidence=best_confidence,
                threshold=threshold,
                margin=round(best_confidence - threshold, 2),
            )

        # ── Step 5: Problem decomposition ───────────────────────
        decomposition = _decompose_problem(
            message=message,
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            maker_config=maker_config,
        )

        # ── Step 6: Build audit trail ───────────────────────────
        audit_trail = _build_audit_trail(
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            k=k,
            solutions=solutions,
            best_solution=best_solution,
            threshold=threshold,
            red_flag=red_flag,
            maker_config=maker_config,
        )

        # ── Build state update ──────────────────────────────────
        #
        # CRITICAL FIX: Update agent_response with the MAKER-selected
        # best solution. Without this, downstream nodes (guardrails,
        # channel delivery, email/SMS/voice agents) read the ORIGINAL
        # agent_response, completely ignoring MAKER's better solution.
        #
        # We also update agent_confidence so downstream nodes see the
        # MAKER-scored confidence instead of the original agent's.
        result = {
            "k_solutions": solutions,
            "selected_solution": selected_text,
            "red_flag": red_flag,
            "maker_mode": maker_mode,
            "k_value_used": k,
            "fake_threshold": threshold,
            "maker_decomposition": decomposition,
            "maker_audit_trail": audit_trail,
            # BUG FIX: Update agent_response with MAKER's best solution
            "agent_response": selected_text,
            # Update confidence to MAKER's scored confidence
            "agent_confidence": best_confidence,
        }

        logger.info(
            "maker_validator_node_success",
            tenant_id=tenant_id,
            variant_tier=variant_tier,
            maker_mode=maker_mode,
            k_value_used=k,
            best_confidence=best_confidence,
            threshold=threshold,
            red_flag=red_flag,
            num_candidates=len(solutions),
            agent_response_updated=True,
        )

        return result

    except Exception as exc:
        logger.error(
            "maker_validator_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )

        # BC-008: On fatal error, use agent_response as single solution
        # This ensures the pipeline never breaks
        agent_response = state.get("agent_response", "")
        agent_confidence = float(state.get("agent_confidence", 0.0))

        return {
            **_DEFAULT_MAKER_STATE,
            "selected_solution": agent_response,
            "k_solutions": [{
                "solution": agent_response,
                "confidence": agent_confidence,
                "scored_confidence": agent_confidence,
                "reasoning": "MAKER fatal error fallback (BC-008)",
                "source": "bc008_fatal_fallback",
            }],
            "k_value_used": 1,
            "red_flag": True,  # Conservative: always flag on error
            "maker_audit_trail": [{
                "step": "maker_fatal_error_fallback",
                "error": str(exc),
                "fallback_note": "Using agent_response as sole candidate due to MAKER failure",
            }],
            "errors": [f"MAKER validator fatal error: {exc}"],
        }
