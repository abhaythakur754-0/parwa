"""
Self-Healing Loop Node — OpenClaw-inspired self-healing in the variant pipeline.

This is the SELF-HEALING LOOP that the user wanted in both variants AND Jarvis.
Inspired by OpenClaw's architecture where the system automatically:
  1. Detects quality/accuracy issues in its own output
  2. Takes corrective actions
  3. Re-generates if needed
  4. Repeats until quality threshold met or max iterations reached

This replaces the simple quality_retry loop with a MUCH smarter approach:
  - Old: quality_retry just re-ran generate with same context
  - New: self_healing_loop DIAGNOSES what went wrong, applies corrections,
         and re-generates with IMPROVED context

Architecture:
  After CLARA quality gate → if quality failed:
    1. Analyze WHAT went wrong (not just "quality low")
    2. Check comm bus for insights from other nodes
    3. Apply corrections to context/prompt
    4. Re-generate with improved context
    5. Re-check quality
    6. If still failing, try different approach (switch technique, enrich context)
    7. Max 3 iterations (configurable by tier)

BC-008: Never crash.
BC-001: company_id first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.parwa_graph_state import (
    ParwaGraphState,
    read_comm_bus,
    post_to_comm_bus,
    post_shared_insight,
    append_audit_entry,
)
from app.core.variant_engine.tier_permissions import get_max_retries
from app.logger import get_logger

logger = get_logger("self_healing_loop_node")


def _diagnose_quality_issues(state: ParwaGraphState) -> List[Dict[str, Any]]:
    """Diagnose what went wrong with the response quality.

    Instead of just "quality failed", this looks at WHY:
    - Was it off-topic? (classification issue)
    - Was it hallucination? (generation issue)
    - Was it too robotic? (tone/brand issue)
    - Was it incomplete? (context issue)
    - Was it factually wrong? (reasoning issue)

    Args:
        state: Current pipeline state.

    Returns:
        List of diagnosed issues with suggested corrections.
    """
    issues = []
    quality_issues = state.get("quality_issues", [])
    quality_score = state.get("quality_score", 0)
    classification = state.get("classification", {})

    # Map quality issues to diagnoses
    issue_diagnoses = {
        "off_topic": {
            "diagnosis": "Response drifted from customer's actual question",
            "correction": "re_classify",
            "priority": "high",
        },
        "hallucination": {
            "diagnosis": "Response contains fabricated information",
            "correction": "ground_with_facts",
            "priority": "critical",
        },
        "tone_inconsistent": {
            "diagnosis": "Response tone doesn't match brand/industry",
            "correction": "adjust_tone",
            "priority": "medium",
        },
        "incomplete": {
            "diagnosis": "Response doesn't fully address the query",
            "correction": "enrich_context",
            "priority": "high",
        },
        "factual_error": {
            "diagnosis": "Response contains incorrect facts",
            "correction": "correct_facts",
            "priority": "critical",
        },
        "repetitive": {
            "diagnosis": "Response repeats information unnecessarily",
            "correction": "dedup_content",
            "priority": "low",
        },
        "no_empathy": {
            "diagnosis": "Response lacks emotional awareness",
            "correction": "add_empathy",
            "priority": "high",
        },
        "too_technical": {
            "diagnosis": "Response is too technical for customer",
            "correction": "simplify_language",
            "priority": "medium",
        },
    }

    for qi in quality_issues:
        diagnosis = issue_diagnoses.get(qi)
        if diagnosis:
            issues.append({
                "issue": qi,
                **diagnosis,
            })

    # Also check if empathy was low
    empathy_score = state.get("empathy_score", 0)
    if empathy_score < 0.3:
        issues.append({
            "issue": "low_empathy",
            "diagnosis": "Low empathy score detected",
            "correction": "add_empathy",
            "priority": "high",
        })

    # Check comm bus for warnings from other nodes
    messages = read_comm_bus(state, "self_healing_loop", message_types=["warning"])
    for msg in messages:
        issues.append({
            "issue": f"node_warning_{msg.get('from_node', 'unknown')}",
            "diagnosis": msg.get("payload", {}).get("warning", "Unknown warning"),
            "correction": "address_node_warning",
            "priority": msg.get("priority", "medium"),
        })

    if not issues and quality_score < 0.5:
        # Generic low quality
        issues.append({
            "issue": "generic_low_quality",
            "diagnosis": f"Quality score too low ({quality_score:.2f})",
            "correction": "regenerate_with_more_context",
            "priority": "high",
        })

    return issues


def _apply_correction(
    correction_type: str,
    state: ParwaGraphState,
) -> Dict[str, Any]:
    """Apply a correction based on the diagnosed issue.

    This is where the HEALING happens. Different corrections
    modify different parts of the state to improve the next
    generation attempt.

    Args:
        correction_type: Type of correction to apply.
        state: Current pipeline state.

    Returns:
        Dict with state updates for the correction.
    """
    corrections = {
        "re_classify": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "CRITICAL: Stay strictly on-topic. Address the customer's "
                "exact question without deviating. "
            ),
        },
        "ground_with_facts": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "CRITICAL: Only use information you are certain about. "
                "Do not fabricate details. If unsure, acknowledge it. "
            ),
        },
        "adjust_tone": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "TONE: Use warm, professional, empathetic language. "
                "Avoid robotic or formulaic phrases. "
            ),
        },
        "enrich_context": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "COMPLETENESS: Ensure every part of the customer's question "
                "is addressed. Do not leave any aspect unanswered. "
            ),
        },
        "correct_facts": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "ACCURACY: Double-check all factual claims. "
                "Reference known issues and policies when available. "
            ),
        },
        "add_empathy": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "EMPATHY: Start by acknowledging the customer's feelings. "
                "Show understanding before providing solutions. "
            ),
        },
        "simplify_language": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "LANGUAGE: Use simple, clear language. "
                "Avoid jargon. Explain technical terms. "
            ),
        },
        "dedup_content": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "CONCISENESS: Do not repeat information. "
                "Each point should be made once, clearly. "
            ),
        },
        "regenerate_with_more_context": {
            "enrichment_context": (
                f"{state.get('enrichment_context', '')} "
                "IMPROVEMENT: Provide a comprehensive, accurate, "
                "and empathetic response. "
            ),
        },
        "address_node_warning": {},
    }

    return corrections.get(correction_type, {})


async def self_healing_loop_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Self-healing loop node — OpenClaw-inspired self-correction.

    This node runs AFTER the quality gate determines the response
    is below threshold. It:
      1. Diagnoses what went wrong
      2. Applies corrections to the context
      3. Marks state for re-generation
      4. Posts insights for the next generation attempt

    The actual re-generation happens back in the generate node
    (quality_retry → generate loop), but now with IMPROVED context.

    Args:
        state: Current pipeline state.

    Returns:
        Dict with state updates including corrections.
    """
    start = time.monotonic()
    variant_tier = state.get("variant_tier", "mini_parwa")
    company_id = state.get("company_id", "")
    quality_passed = state.get("quality_passed", True)
    quality_score = state.get("quality_score", 0)
    retry_count = state.get("quality_retry_count", 0)

    try:
        # If quality passed, no healing needed
        if quality_passed:
            return {
                "self_healing_result": {
                    "issues_detected": [],
                    "healing_actions_taken": [],
                    "re_healed": False,
                    "original_quality_score": quality_score,
                    "healed_quality_score": quality_score,
                    "healing_iterations": 0,
                    "max_iterations_reached": False,
                },
                "steps_completed": ["self_healing_loop"],
                **append_audit_entry(
                    state, "self_healing_loop", "no_healing_needed"
                ),
            }

        # Diagnose what went wrong
        issues = _diagnose_quality_issues(state)

        # Apply corrections for all diagnosed issues
        healing_actions = []
        combined_context = state.get("enrichment_context", "")

        for issue in issues:
            correction = issue.get("correction", "regenerate_with_more_context")
            correction_updates = _apply_correction(correction, state)

            if correction_updates:
                combined_context += correction_updates.get("enrichment_context", "")
                healing_actions.append({
                    "issue": issue.get("issue"),
                    "correction_applied": correction,
                    "priority": issue.get("priority", "medium"),
                })

        # Post healing insights to comm bus for other nodes
        post_to_comm_bus(
            state,
            from_node="self_healing_loop",
            to_node="generate",
            message_type="correction",
            payload={
                "healing_applied": True,
                "issues_count": len(issues),
                "corrections": [a["correction_applied"] for a in healing_actions],
                "retry_number": retry_count + 1,
            },
            priority="high",
        )

        post_shared_insight(
            "self_healing_loop",
            "healing_status",
            {
                "issues_found": len(issues),
                "healing_applied": len(healing_actions),
                "original_quality": quality_score,
                "retry_number": retry_count + 1,
            },
        )

        max_retries = get_max_retries(variant_tier)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "self_healing_result": {
                "issues_detected": [i.get("issue") for i in issues],
                "healing_actions_taken": healing_actions,
                "re_healed": True,
                "original_quality_score": quality_score,
                "healed_quality_score": 0,  # Will be updated after re-generation
                "healing_iterations": retry_count + 1,
                "max_iterations_reached": retry_count >= max_retries,
            },
            "enrichment_context": combined_context,
            "steps_completed": ["self_healing_loop"],
            **append_audit_entry(
                state,
                "self_healing_loop",
                f"healed_{len(healing_actions)}_issues",
                duration_ms=duration_ms,
                details={
                    "issues": [i.get("issue") for i in issues],
                    "corrections": [a["correction_applied"] for a in healing_actions],
                    "retry": retry_count + 1,
                },
            ),
        }

        logger.info(
            "self_healing_loop: tier=%s, issues=%d, actions=%d, "
            "quality=%.2f, retry=%d/%d, ms=%.1f",
            variant_tier, len(issues), len(healing_actions),
            quality_score, retry_count + 1, max_retries, duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("self_healing_loop_error: %s", str(exc)[:200])
        return {
            "self_healing_result": {
                "issues_detected": ["self_healing_error"],
                "healing_actions_taken": [],
                "re_healed": False,
                "original_quality_score": quality_score,
                "healed_quality_score": quality_score,
                "healing_iterations": retry_count,
                "max_iterations_reached": False,
            },
            "errors": [f"self_healing_loop_error: {str(exc)[:200]}"],
            **append_audit_entry(
                state, "self_healing_loop", "error", duration_ms=duration_ms
            ),
        }
