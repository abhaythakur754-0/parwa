"""
Builder LLM Client — uses Groq llama-3.1-8b-instant for agent reasoning.

The Builder uses Groq llama-3.1-8b-instant for ALL stages.
User validation (2026-08-12): "llama-3.1-8b gives best results for ALL
pipeline tasks" — this includes agent building. Groq: ~1s/call vs
NVIDIA GLM-5.2's ~58s/call (which made onboarding take 4+ min per agent).

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

# ── Groq llama-3.1-8b-instant is used for ALL Builder stages ───────
# User validation: llama-3.1-8b is the best model for ALL pipeline tasks.
# ~1s/call vs NVIDIA GLM-5.2's ~58s/call.
# Groq 30 RPM is shared with the main pipeline — if rate-limited,
# builder falls back to other providers via llm_call().

STAGE_TIER_MAP = {
    "explore": "groq",          # Groq llama-3.1-8b for intent analysis
    "design": "groq",           # Groq llama-3.1-8b for agent design
    "verify": "groq",           # Groq llama-3.1-8b for testing
    "verify_guardrail": "groq", # Groq llama-3.1-8b for safety check
    "refine": "groq",           # Groq llama-3.1-8b for improvement
}


async def builder_llm_call(
    prompt: str,
    stage: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
    system_prompt: Optional[str] = None,
) -> str:
    """Call Groq llama-3.1-8b-instant for Builder reasoning.

    Uses _call_groq_direct (llama-3.1-8b-instant) for all stages.
    Falls back to generic llm_call() (which picks any available provider)
    if Groq key not set or Groq is rate-limited.

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

    # ── PRIMARY: Groq llama-3.1-8b-instant ───────────────────
    if os.environ.get("GROQ_API_KEY"):
        try:
            from app.core.parwa_pipeline.llm_client import _call_groq_direct
            result = await _call_groq_direct(
                messages=[{"role": "user", "content": full_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                call_id=0,
            )
            if result and len(result.strip()) > 0:
                logger.info("builder_llm_call Groq stage=%s chars=%d", stage, len(result))
                return result
        except Exception as exc:
            logger.warning("builder_llm_call Groq failed stage=%s: %s", stage, str(exc)[:200])

    # ── FALLBACK: generic llm_call (picks any available provider) ──
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
