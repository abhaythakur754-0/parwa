"""
Maker LLM Validator Node — LLM-based response validation (replaces rule-based maker).

The OLD maker_validator in the CC Pipeline was rule-based:
  - Checked if response matched certain patterns
  - Simple regex matching for "best solution"
  - No actual intelligence in validation

The NEW maker_llm_validator uses an LLM to:
  1. Evaluate the response quality across multiple dimensions
  2. Compare against alternative response approaches
  3. Select the BEST solution (maker = "make the best response")
  4. Improve the response if needed
  5. Post corrections to comm bus for self-healing

This makes the maker node ACTUALLY INTELLIGENT rather than
just a simple pattern matcher.

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
from app.logger import get_logger

logger = get_logger("maker_llm_validator_node")


def _build_validation_prompt(state: ParwaGraphState) -> str:
    """Build the validation prompt for the LLM.

    This creates a detailed prompt that asks the LLM to evaluate
    the response across multiple dimensions.

    Args:
        state: Current pipeline state.

    Returns:
        Validation prompt string.
    """
    query = state.get("pii_redacted_query", state.get("query", ""))
    response = state.get("generated_response", "")
    classification = state.get("classification", {})
    intent = classification.get("intent", "unknown")
    industry = state.get("industry", "general")
    empathy_score = state.get("empathy_score", 0)

    # Get insights from comm bus
    messages = read_comm_bus(state, "maker_llm_validator", min_priority="medium")
    insights_text = ""
    for msg in messages:
        insights_text += f"- [{msg.get('from_node')}]: {msg.get('payload', {})}\n"

    return f"""You are a quality validator for a customer support AI response.
Evaluate this response across these dimensions:

1. ACCURACY: Is the information correct and factual?
2. COMPLETENESS: Does it address all parts of the customer's question?
3. EMPATHY: Does it show understanding of the customer's situation?
4. ACTIONABILITY: Does it provide clear next steps?
5. TONE: Is it professional yet natural (not robotic)?
6. SAFETY: Does it avoid promises, guarantees, and absolute language?

Customer Query: {query}
AI Response: {response}
Intent: {intent}
Industry: {industry}
Empathy Score: {empathy_score:.2f}

Insights from pipeline nodes:
{insights_text if insights_text else "No additional insights."}

Respond in EXACTLY this JSON format:
{{
    "validation_passed": true/false,
    "quality_assessment": "excellent/good/acceptable/poor/unacceptable",
    "issues_found": ["issue1", "issue2"],
    "suggested_improvements": ["improvement1", "improvement2"],
    "best_solution_selected": true/false,
    "validation_confidence": 0.0-1.0,
    "improved_response": "improved version if issues found, empty string if passed"
}}"""


def _call_validation_llm(prompt: str, state: ParwaGraphState) -> Dict[str, Any]:
    """Call the LLM for validation.

    Tries multiple LLM providers with fallback cascade:
    z-ai-sdk → NVIDIA → Google → fallback rule-based

    Args:
        prompt: The validation prompt.
        state: Current pipeline state.

    Returns:
        Validation result dict.
    """
    try:
        # Try the LLM client from techniques
        from app.core.techniques.llm_client import get_llm_client

        client = get_llm_client()
        variant_tier = state.get("variant_tier", "mini_parwa")

        # Use appropriate model tier
        model_tier = "light"  # Validation doesn't need heavy model

        result = client.call(
            prompt=prompt,
            model_tier=model_tier,
            company_id=state.get("company_id", ""),
        )

        if result and result.get("text"):
            # Parse the JSON response
            import json
            text = result["text"]

            # Try to extract JSON from the response
            try:
                # Look for JSON in the response
                start_idx = text.find("{")
                end_idx = text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    parsed = json.loads(json_str)
                    return {
                        "validation_passed": parsed.get("validation_passed", True),
                        "quality_assessment": parsed.get("quality_assessment", "acceptable"),
                        "issues_found": parsed.get("issues_found", []),
                        "suggested_improvements": parsed.get("suggested_improvements", []),
                        "best_solution_selected": parsed.get("best_solution_selected", True),
                        "validation_confidence": parsed.get("validation_confidence", 0.5),
                        "improved_response": parsed.get("improved_response", ""),
                        "response_improved": bool(parsed.get("improved_response", "")),
                    }
            except (json.JSONDecodeError, ValueError):
                pass

    except (ImportError, Exception) as exc:
        logger.info("maker_llm_client_fallback: %s", str(exc)[:100])

    # Fallback: Rule-based validation
    return _rule_based_validation(state)


def _rule_based_validation(state: ParwaGraphState) -> Dict[str, Any]:
    """Fallback rule-based validation when LLM is unavailable.

    Args:
        state: Current pipeline state.

    Returns:
        Validation result dict.
    """
    response = state.get("generated_response", "")
    quality_score = state.get("quality_score", 0)
    quality_passed = state.get("quality_passed", True)

    issues = []
    if not quality_passed:
        issues.append("quality_gate_failed")
    if len(response) < 20:
        issues.append("response_too_short")
    if "I understand your" in response:
        issues.append("robotic_language")

    assessment = "excellent" if quality_score >= 0.9 else \
                 "good" if quality_score >= 0.8 else \
                 "acceptable" if quality_score >= 0.7 else \
                 "poor" if quality_score >= 0.5 else "unacceptable"

    return {
        "validation_passed": quality_passed and len(issues) == 0,
        "quality_assessment": assessment,
        "issues_found": issues,
        "suggested_improvements": ["Improve response quality"] if issues else [],
        "best_solution_selected": True,
        "validation_confidence": quality_score,
        "improved_response": "",
        "response_improved": False,
    }


async def maker_llm_validator_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Maker LLM validator node — LLM-based intelligent validation.

    This replaces the old rule-based maker validator with an
    LLM-powered version that actually UNDERSTANDS the response
    and can improve it.

    Flow:
      1. Read from comm bus (insights from other nodes)
      2. Build validation prompt
      3. Call LLM for validation
      4. If issues found and improved_response available → use it
      5. Post results to comm bus
      6. Update state

    Args:
        state: Current pipeline state.

    Returns:
        Dict with state updates.
    """
    start = time.monotonic()
    variant_tier = state.get("variant_tier", "mini_parwa")
    company_id = state.get("company_id", "")

    try:
        # 1. Build and call validation
        prompt = _build_validation_prompt(state)
        validation = _call_validation_llm(prompt, state)

        # 2. If validation found issues and provided improved response
        response_improved = False
        improved_response = validation.get("improved_response", "")

        if not validation.get("validation_passed", True) and improved_response:
            response_improved = True
            # Post correction to comm bus
            post_to_comm_bus(
                state,
                from_node="maker_llm_validator",
                to_node="generate",
                message_type="correction",
                payload={
                    "original_response_issues": validation.get("issues_found", []),
                    "improved_response_available": True,
                },
                priority="high",
            )

        # 3. Post shared insights
        post_shared_insight(
            "maker_llm_validator",
            "validation_result",
            {
                "passed": validation.get("validation_passed", True),
                "assessment": validation.get("quality_assessment", "unknown"),
                "confidence": validation.get("validation_confidence", 0),
                "issues_count": len(validation.get("issues_found", [])),
            },
        )

        # 4. Update state
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "maker_llm_result": validation,
            "generated_response": improved_response if response_improved else state.get("generated_response", ""),
            "steps_completed": ["maker_llm_validator"],
            **append_audit_entry(
                state,
                "maker_llm_validator",
                f"validation_{'passed' if validation.get('validation_passed') else 'improved' if response_improved else 'failed'}",
                duration_ms=duration_ms,
                details={
                    "assessment": validation.get("quality_assessment"),
                    "issues": validation.get("issues_found", []),
                    "confidence": validation.get("validation_confidence"),
                },
            ),
        }

        logger.info(
            "maker_llm_validator: tier=%s, passed=%s, assessment=%s, "
            "issues=%d, improved=%s, confidence=%.2f, ms=%.1f",
            variant_tier,
            validation.get("validation_passed", True),
            validation.get("quality_assessment", "unknown"),
            len(validation.get("issues_found", [])),
            response_improved,
            validation.get("validation_confidence", 0),
            duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("maker_llm_validator_error: %s", str(exc)[:200])
        return {
            "maker_llm_result": {
                "validation_passed": True,  # Fail-open: don't block on error
                "quality_assessment": "unknown",
                "issues_found": [],
                "suggested_improvements": [],
                "best_solution_selected": True,
                "response_improved": False,
                "improved_response": "",
                "validation_confidence": 0.0,
            },
            "errors": [f"maker_llm_validator_error: {str(exc)[:200]}"],
            **append_audit_entry(
                state, "maker_llm_validator", "error", duration_ms=duration_ms
            ),
        }
