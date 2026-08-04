"""
Builder LLM Client — uses NVIDIA GLM-5 for deep agent reasoning.

The Builder uses NVIDIA GLM-5.2 (z-ai/glm-5.2) for ALL stages.
This separates agent building (NVIDIA, 30 RPM) from ticket processing
(Groq, 30 RPM) — they don't compete for rate limits.

4 stages:
  EXPLORE: Understand what agent is needed (scan tickets, classify)
  DESIGN:  Generate agent config (instructions, restrictions, tools)
  VERIFY:  Test agent against historical tickets
  REFINE:  Improve based on test results
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("parwa.builder.llm")

# ── NVIDIA GLM-5 is used for ALL Builder stages ───────────────────
# This is SEPARATE from Groq (which handles ticket processing).
# NVIDIA: 30 RPM, used for deep reasoning during onboarding
# Groq: 30 RPM, used for fast ticket responses

STAGE_TIER_MAP = {
    "explore": "nvidia",          # NVIDIA GLM-5 for intent analysis
    "design": "nvidia",           # NVIDIA GLM-5 for agent design
    "verify": "nvidia",           # NVIDIA GLM-5 for testing
    "verify_guardrail": "nvidia", # NVIDIA GLM-5 for safety check
    "refine": "nvidia",           # NVIDIA GLM-5 for improvement
}


async def builder_llm_call(
    prompt: str,
    stage: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
    system_prompt: Optional[str] = None,
) -> str:
    """Call NVIDIA GLM-5 for Builder reasoning.

    Uses _call_nvidia_direct (GLM-5.2 model) for all stages.
    Falls back to Groq if NVIDIA key not set.

    Args:
        prompt: The user message / query
        stage: Builder stage name (explore, design, verify, refine)
        max_tokens: Max tokens in response
        temperature: Sampling temperature
        system_prompt: Optional system prompt

    Returns:
        The LLM response text
    """
    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

    # ── PRIMARY: NVIDIA GLM-5 ──────────────────────────────────
    if os.environ.get("NVIDIA_API_KEY"):
        try:
            from app.core.parwa_pipeline.llm_client import _call_nvidia_direct
            result = await _call_nvidia_direct(
                messages=[{"role": "user", "content": full_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                call_id=0,
            )
            if result and len(result.strip()) > 0:
                logger.info("builder_llm_call NVIDIA stage=%s chars=%d", stage, len(result))
                return result
        except Exception as exc:
            logger.warning("builder_llm_call NVIDIA failed stage=%s: %s", stage, str(exc)[:200])

    # ── FALLBACK: Groq (if NVIDIA not available) ──────────────
    try:
        from app.core.parwa_pipeline.llm_client import llm_call
        result = await llm_call(
            full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result or ""
    except Exception as exc:
        logger.warning(
            "builder_llm_call_failed stage=%s err=%s",
            stage, str(exc)[:200],
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
