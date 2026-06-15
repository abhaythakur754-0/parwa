"""
Loophole Check Node — Scans AI responses for 25 loophole categories.

This integrates the existing loophole_engine into the variant pipeline.
Previously, loophole checking was only in the CC Pipeline's guardrails node.
Now it's a FIRST-CLASS node in the variant pipeline.

The loophole engine detects:
  - Hallucination patterns
  - Off-topic responses
  - Brand voice violations
  - Pricing errors
  - PII leaks
  - Prompt injection attempts
  - Promise language ("we guarantee", "we will always")
  - And 18 more categories

This node:
  1. Runs the loophole engine against the generated response
  2. If issues found, attempts auto-correction
  3. If auto-correction works, replaces the response
  4. If blocking issue found, flags for human review
  5. Posts results to comm bus for other nodes

BC-008: Never crash.
BC-001: company_id first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.parwa_graph_state import (
    ParwaGraphState,
    post_to_comm_bus,
    post_shared_insight,
    append_audit_entry,
)
from app.logger import get_logger

logger = get_logger("loophole_check_node")


async def loophole_check_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Loophole check node — scans response for quality/safety issues.

    Flow:
      1. Get the generated response
      2. Run loophole engine against it
      3. Evaluate results
      4. Auto-correct if possible
      5. Block if necessary
      6. Post to comm bus

    Args:
        state: Current pipeline state.

    Returns:
        Dict with state updates.
    """
    start = time.monotonic()
    variant_tier = state.get("variant_tier", "mini_parwa")
    company_id = state.get("company_id", "")
    response = state.get("generated_response", "")

    try:
        if not response:
            return {
                "loophole_check_result": {
                    "matches_found": 0,
                    "matches": [],
                    "risk_level": "none",
                    "blocked": False,
                    "auto_corrected": False,
                    "corrected_response": "",
                },
                "steps_completed": ["loophole_check"],
                **append_audit_entry(
                    state, "loophole_check", "skipped_no_response"
                ),
            }

        # Run the loophole engine
        matches = []
        risk_level = "none"
        blocked = False

        try:
            from app.core.loophole_engine import LoopholeEngine

            engine = LoopholeEngine()
            scan_result = engine.scan(
                company_id=company_id,
                ai_response=response,
                industry=state.get("industry", "general"),
            )

            matches = [
                {
                    "category": m.category.name if hasattr(m.category, 'name') else str(m.category),
                    "matched_text": m.matched_text[:100] if hasattr(m, 'matched_text') else "",
                    "confidence": m.confidence if hasattr(m, 'confidence') else 0.5,
                }
                for m in scan_result.matches
            ]

            risk_level = (
                scan_result.risk_level.name
                if hasattr(scan_result.risk_level, 'name')
                else str(scan_result.risk_level)
            )
            blocked = scan_result.should_block if hasattr(scan_result, 'should_block') else False

        except ImportError:
            # Loophole engine not available — use lightweight rule-based check
            logger.info("loophole_engine_not_available_using_fallback")
            matches = _lightweight_loophole_check(response)
            risk_level = "low" if len(matches) < 3 else "medium"
            blocked = len(matches) >= 5

        except Exception as scan_exc:
            logger.warning(
                "loophole_scan_error: %s", str(scan_exc)[:200]
            )
            matches = []
            risk_level = "none"

        # Auto-correct if possible
        auto_corrected = False
        corrected_response = ""

        if matches and not blocked:
            corrected = _auto_correct_loopholes(response, matches)
            if corrected != response:
                auto_corrected = True
                corrected_response = corrected

        # Post to comm bus if issues found
        if matches:
            post_to_comm_bus(
                state,
                from_node="loophole_check",
                to_node="self_healing_loop",
                message_type="warning" if not blocked else "correction",
                payload={
                    "loophole_matches": len(matches),
                    "risk_level": risk_level,
                    "blocked": blocked,
                    "categories": [m["category"] for m in matches],
                },
                priority="critical" if blocked else "high",
            )

            post_shared_insight(
                "loophole_check",
                "loophole_status",
                {
                    "matches_found": len(matches),
                    "risk_level": risk_level,
                    "auto_corrected": auto_corrected,
                    "blocked": blocked,
                },
            )

        # If blocked, override the response
        final_response = corrected_response if auto_corrected else response
        if blocked:
            final_response = (
                "I want to make sure I give you the most accurate information. "
                "Let me connect you with a specialist who can help with this. "
                "Your request has been escalated for review."
            )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "loophole_check_result": {
                "matches_found": len(matches),
                "matches": matches,
                "risk_level": risk_level,
                "blocked": blocked,
                "auto_corrected": auto_corrected,
                "corrected_response": corrected_response,
            },
            "generated_response": final_response,
            "steps_completed": ["loophole_check"],
            **append_audit_entry(
                state,
                "loophole_check",
                f"{'blocked' if blocked else 'auto_corrected' if auto_corrected else 'passed'}",
                duration_ms=duration_ms,
                details={
                    "matches": len(matches),
                    "risk": risk_level,
                    "blocked": blocked,
                },
            ),
        }

        logger.info(
            "loophole_check: tier=%s, matches=%d, risk=%s, "
            "blocked=%s, auto_corrected=%s, ms=%.1f",
            variant_tier, len(matches), risk_level,
            blocked, auto_corrected, duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("loophole_check_error: %s", str(exc)[:200])
        return {
            "loophole_check_result": {
                "matches_found": 0,
                "matches": [],
                "risk_level": "none",
                "blocked": False,
                "auto_corrected": False,
                "corrected_response": "",
            },
            "errors": [f"loophole_check_error: {str(exc)[:200]}"],
            **append_audit_entry(
                state, "loophole_check", "error", duration_ms=duration_ms
            ),
        }


def _lightweight_loophole_check(response: str) -> list:
    """Lightweight rule-based loophole check when full engine is unavailable.

    Checks for common patterns that indicate quality/safety issues.

    Args:
        response: The AI response to check.

    Returns:
        List of match descriptors.
    """
    import re

    matches = []
    patterns = {
        "promise_language": r"\b(we (will )?always|we guarantee|we promise|100%)\b",
        "absolute_language": r"\b(never|always|impossible|no way|definitely)\b",
        "legal_risk": r"\b(sue|lawsuit|legal action|attorney|lawyer)\b",
        "price_commitment": r"\b(\$\d+\.?\d*\s*(off|discount|free|refund))\b",
        "pii_exposure": r"\b(\d{3}[-.]?\d{3}[-.]?\d{4}|[A-Z]\d{3}\s\d{2}\s\d{7})\b",
        "off_topic_ending": r"(by the way|also|additionally).{0,50}(buy|purchase|upgrade)",
        "hallucination_signal": r"\b(according to our records|our system shows|I can see that)\b",
        "robotic_language": r"\b(I understand your (frustration|concern)|thank you for (reaching out|contacting))\b",
    }

    for category, pattern in patterns.items():
        found = re.findall(pattern, response, re.IGNORECASE)
        if found:
            matches.append({
                "category": category,
                "matched_text": str(found[0])[:100],
                "confidence": 0.7,
            })

    return matches


def _auto_correct_loopholes(response: str, matches: list) -> str:
    """Attempt to auto-correct loophole issues in the response.

    Args:
        response: The original AI response.
        matches: List of loophole matches.

    Returns:
        Corrected response string.
    """
    import re

    corrected = response

    for match in matches:
        category = match.get("category", "")

        if category == "promise_language":
            # Remove absolute promises
            corrected = re.sub(
                r"\bwe (will )?always\b", "we typically", corrected, flags=re.IGNORECASE
            )
            corrected = re.sub(
                r"\bwe guarantee\b", "we aim to", corrected, flags=re.IGNORECASE
            )

        elif category == "absolute_language":
            # Soften absolute statements
            corrected = re.sub(
                r"\bnever\b", "rarely", corrected, flags=re.IGNORECASE
            )
            corrected = re.sub(
                r"\balways\b", "typically", corrected, flags=re.IGNORECASE
            )

        elif category == "robotic_language":
            # Replace robotic phrases with more natural ones
            corrected = re.sub(
                r"I understand your frustration",
                "I hear you — that's really frustrating",
                corrected,
                flags=re.IGNORECASE,
            )
            corrected = re.sub(
                r"thank you for reaching out",
                "thanks for getting in touch",
                corrected,
                flags=re.IGNORECASE,
            )

    return corrected
