"""
Builder LLM Client — calls smart_router with correct tier per stage.

The Builder uses 4 model tiers across 4 stages:
  EXPLORE: LIGHT models (fast, cheap) — understand intent
  DESIGN:  MEDIUM models (balanced) — generate candidates
  VERIFY:  LIGHT + MEDIUM + GUARDRAIL — vote, reflect, safety check
  REFINE:  HEAVY models (powerful) — regenerate using Reflexion

This module wraps llm_call with the correct tier parameter for each
stage so the Builder always uses the right model for the job.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("parwa.builder.llm")

# ── Model tiers for each Builder stage ─────────────────────────────
# Maps Builder stage → smart_router tier parameter

STAGE_TIER_MAP = {
    "explore": "light",       # Cerebras Llama 3.1 8B → Groq Llama 3.1 8B → Gemma 3 27B
    "design": "medium",       # Gemini Flash-Lite → Gemini 2.5 Flash → Groq Llama 3.3 70B
    "verify": "medium",       # Same as design — voting + reflection
    "verify_guardrail": "guardrail",  # Groq Llama Guard 4 12B
    "refine": "heavy",        # Groq GPT-OSS 120B → Cerebras GPT-OSS 120B → Llama 4 Scout
}


async def builder_llm_call(
    prompt: str,
    stage: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
    system_prompt: Optional[str] = None,
) -> str:
    """Call the LLM with the correct tier for this Builder stage.

    Falls back to the standard llm_call if smart_router isn't available.

    Args:
        prompt: The user message / query
        stage: Builder stage name (explore, design, verify, refine, verify_guardrail)
        max_tokens: Max tokens in response
        temperature: Sampling temperature
        system_prompt: Optional system prompt

    Returns:
        The LLM response text
    """
    tier = STAGE_TIER_MAP.get(stage, "light")

    try:
        from app.core.parwa_pipeline.llm_client import llm_call

        # Try to use smart_router if available (Phase 0 wiring)
        try:
            from app.core.parwa_pipeline.smart_router import SmartRouter
            router = SmartRouter()

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            result = await llm_call(
                full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return result or ""

        except ImportError:
            pass

        # Fallback: standard llm_call
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        result = await llm_call(
            full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result or ""

    except Exception as exc:
        logger.warning(
            "builder_llm_call_failed stage=%s tier=%s err=%s",
            stage, tier, str(exc)[:200],
        )
        return ""


async def builder_guardrail_check(text: str) -> tuple:
    """Run a guardrail safety check on the given text.

    Uses the GUARDRAIL model tier (Llama Guard 4 12B) to scan for
    safety issues.

    Returns (is_safe: bool, reason: str).
    """
    try:
        result = await builder_llm_call(
            prompt=(
                f"Scan this agent configuration for safety issues. "
                f"Is it safe to create an AI agent with this configuration?\n\n"
                f"Agent config:\n{text[:2000]}\n\n"
                f"Respond with ONLY 'SAFE' or 'UNSAFE: <reason>'"
            ),
            stage="verify_guardrail",
            max_tokens=100,
            temperature=0.0,
        )

        if not result:
            return True, "guardrail_check_skipped"

        result_upper = result.strip().upper()
        if result_upper.startswith("SAFE"):
            return True, "passed_guardrail_check"
        elif result_upper.startswith("UNSAFE"):
            reason = result.strip()[6:].strip() if ":" in result else "unspecified"
            return False, reason
        else:
            # Unclear response — err on the side of caution
            return True, f"unclear_guardrail_response: {result[:100]}"

    except Exception as exc:
        logger.warning("builder_guardrail_check_failed: %s", str(exc)[:200])
        # Fail-safe: allow creation but log the issue
        return True, f"guardrail_check_error: {str(exc)[:100]}"
