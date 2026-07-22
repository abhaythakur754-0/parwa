"""
PARWA Pipeline V2 — Shared LLM Client

Production LLM routing via Smart Router (11 models across 4 tiers via 3 API keys).

Tier configuration:
  LIGHT  (ALL tasks): Cerebras Llama 3.1 8B → Groq Llama 3.1 8B → Google Gemma 3 27B
  MEDIUM (reserved):  Google Gemini Flash-Lite → Google Gemini Flash → Groq Llama 3.3 70B → Groq Qwen3 32B
  HEAVY  (reserved):  Groq GPT-OSS 120B → Cerebras GPT-OSS 120B → Groq Llama 4 Scout
  GUARDRAIL:          Groq GPT-OSS 120B (user-tested best for safety checks)

User-validated: llama-3.1-8b gives best results for ALL pipeline tasks.
Only guardrail/checking uses gpt-oss-120b.
All variants get ALL model tiers; only restrictions differ.

LiteLLM auto-routes cerebras/, groq/, gemini/ prefixes to the correct API key.
The Smart Router handles priority-based failover — if the primary model in a
tier fails, it automatically tries the next one.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time

logger = logging.getLogger("parwa.pipeline.llm")

# ── Rate Limiter ───────────────────────────────────────────────────

_last_call_time: float = 0.0
_rate_lock: asyncio.Lock = None
MIN_CALL_INTERVAL: float = 0.5  # Conservative: 120 RPM across all providers
MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 2.0

# ── Stats ──────────────────────────────────────────────────────────

_call_count: int = 0
_total_tokens: int = 0
_total_errors: int = 0


async def _get_rate_lock() -> asyncio.Lock:
    global _rate_lock
    if _rate_lock is None:
        _rate_lock = asyncio.Lock()
    return _rate_lock


async def _wait_for_rate_limit():
    """Enforce minimum interval between calls."""
    global _last_call_time
    lock = await _get_rate_lock()
    async with lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < MIN_CALL_INTERVAL:
            wait = MIN_CALL_INTERVAL - elapsed
            logger.debug("Rate limit: waiting %.1fs", wait)
            await asyncio.sleep(wait)
        _last_call_time = time.monotonic()


# Global pipeline timeout — no single ticket should take longer than this
PIPELINE_HARD_TIMEOUT: float = 300.0  # 5 minutes absolute max
_call_start_time: float = 0.0


def set_pipeline_timeout(seconds: float = 300.0) -> None:
    """Set the hard timeout for the current pipeline run."""
    global PIPELINE_HARD_TIMEOUT, _call_start_time
    PIPELINE_HARD_TIMEOUT = seconds
    _call_start_time = time.monotonic()


def _check_pipeline_timeout() -> None:
    """Raise if the pipeline has exceeded its hard timeout."""
    if _call_start_time and (time.monotonic() - _call_start_time) > PIPELINE_HARD_TIMEOUT:
        raise RuntimeError(
            f"Pipeline hard timeout ({PIPELINE_HARD_TIMEOUT:.0f}s) exceeded — "
            f"aborting to prevent hang"
        )


async def llm_call(
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str = "",
    step_type: str = "",
) -> str:
    """Single LLM call — uses Smart Router (11 models) with automatic failover.

    Production path: Smart Router → LiteLLM → Google/Groq/Cerebras.
    The Smart Router selects the best model per atomic step type and
    handles priority-based failover within tiers automatically.

    Args:
        prompt: The user prompt to send to the LLM.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature.
        system_prompt: Optional system prompt.
        step_type: Atomic step type for Smart Router tier selection.
            Maps to AtomicStepType enum. Common values:
            - "intent_classification", "pii_redaction", "sentiment_analysis" → LIGHT
            - "draft_response_moderate", "draft_response_complex" → MEDIUM
            - "draft_response_complex", "reflexion_cycle" → HEAVY
            - "guardrail_check" → GUARDRAIL
            If empty, defaults to draft_response_moderate.

    Returns:
        The LLM response text string.

    Raises:
        RuntimeError: If all models in the Smart Router fail.
    """
    global _call_count, _total_errors

    await _wait_for_rate_limit()

    _call_count += 1
    call_id = _call_count

    _check_pipeline_timeout()

    # Build messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # ── PRIMARY: Smart Router (LiteLLM — 11 models via 3 API keys) ──
    try:
        smart_result = await _call_smart_router(messages, temperature, max_tokens, call_id, step_type)
        if smart_result and len(smart_result) > 5:
            logger.info("LLM call #%d: Smart Router SUCCESS (%d chars)", call_id, len(smart_result))
            return smart_result
        logger.warning("LLM call #%d: Smart Router returned empty/short response, retrying", call_id)
    except Exception as exc:
        logger.warning("LLM call #%d: Smart Router error (%s), trying direct LiteLLM", call_id, str(exc)[:150])

    # ── FALLBACK: Direct LiteLLM call with env-configured model ──
    try:
        direct_result = await _call_litellm_direct(messages, temperature, max_tokens, call_id)
        if direct_result and len(direct_result) > 5:
            logger.info("LLM call #%d: Direct LiteLLM SUCCESS (%d chars)", call_id, len(direct_result))
            return direct_result
        logger.warning("LLM call #%d: Direct LiteLLM returned empty, trying per-provider", call_id)
    except Exception as exc:
        logger.warning("LLM call #%d: Direct LiteLLM error (%s), trying per-provider", call_id, str(exc)[:150])

    # ── LAST RESORT: Try each provider directly via raw HTTP ──
    # NVIDIA first (most reliable during testing), then others
    for provider_name, provider_fn in [
        ("nvidia", _call_nvidia_direct),
        ("cerebras", _call_cerebras_direct),
        ("groq", _call_groq_direct),
        ("google", _call_google_direct),
    ]:
        try:
            result = await provider_fn(messages, temperature, max_tokens, call_id)
            if result and len(result) > 5:
                logger.info("LLM call #%d: %s direct SUCCESS (%d chars)", call_id, provider_name, len(result))
                return result
        except Exception as exc:
            logger.warning("LLM call #%d: %s direct failed: %s", call_id, provider_name, str(exc)[:100])

    _total_errors += 1
    logger.error("LLM call #%d FAILED: All providers exhausted (Smart Router + direct)", call_id)
    raise RuntimeError("LLM call failed: all providers (Smart Router + direct) exhausted")


async def _call_smart_router(messages: list, temperature: float, max_tokens: int, call_id: int, step_type: str = "") -> str:
    """Call Smart Router (LiteLLM with 11 models via 3 API keys).

    Args:
        step_type: Atomic step type string for tier selection.
            If empty or unknown, defaults to DRAFT_RESPONSE_MODERATE.
    """
    try:
        from app.core.smart_router import SmartRouter, AtomicStepType
        router = SmartRouter()

        # Resolve step type — map string to AtomicStepType enum
        step_type_map = {e.value: e for e in AtomicStepType}
        atomic_step = step_type_map.get(step_type, AtomicStepType.DRAFT_RESPONSE_MODERATE)

        routing = router.route(
            company_id="pipeline",
            variant_type="parwa",
            atomic_step=atomic_step,
        )
        result = await router.async_execute_llm_call(
            company_id="pipeline",
            routing_decision=routing,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = result.get("content", "")
        model_used = result.get("model", "?")
        provider = result.get("provider", "?")
        fallback = result.get("fallback_used", False)
        if content and len(content) > 0:
            logger.info(
                "LLM call #%d: SmartRouter %s/%s (%d chars, fallback=%s)",
                call_id, provider, model_used, len(content), fallback,
            )
            return content.strip()
        return ""
    except ImportError:
        logger.warning("Smart Router not available (import error) — falling back to direct LiteLLM")
        return ""
    except Exception as exc:
        logger.warning("LLM call #%d: Smart Router error: %s", call_id, str(exc)[:200])
        return ""


async def _call_litellm_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct LiteLLM call using env-configured model (bypass Smart Router)."""
    try:
        import litellm

        if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_AI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_AI_API_KEY"]

        model = os.environ.get("AI_LIGHT_MODEL", "nvidia/z-ai/glm-5.2")

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=30,
        )

        if response and response.choices:
            content = response.choices[0].message.content or ""
            if response.usage:
                global _total_tokens
                _total_tokens += response.usage.total_tokens or 0
            return content.strip()
        return ""
    except ImportError:
        logger.warning("LiteLLM not installed — cannot use direct LiteLLM path")
        return ""
    except Exception as exc:
        logger.warning("LLM call #%d: Direct LiteLLM failed: %s", call_id, str(exc)[:200])
        return ""


async def _call_nvidia_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct NVIDIA API call (raw HTTP, no LiteLLM dependency).

    Uses NVIDIA's OpenAI-compatible endpoint with GLM 5.2 model.
    This is the most reliable provider during testing.
    """
    import httpx

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        return ""

    payload = {
        "model": "z-ai/glm-5.2",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            json=payload,
            headers=headers,
        )

    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        global _total_tokens
        _total_tokens += data.get("usage", {}).get("total_tokens", 0)
        return content.strip()
    else:
        raise RuntimeError(f"NVIDIA API error {r.status_code}: {r.text[:200]}")


async def _call_cerebras_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Cerebras API call (raw HTTP, no LiteLLM dependency)."""
    import httpx

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        return ""

    payload = {
        "model": "gpt-oss-120b",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.cerebras.ai/v1/chat/completions",
            json=payload,
            headers=headers,
        )

    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        global _total_tokens
        _total_tokens += data.get("usage", {}).get("total_tokens", 0)
        return content.strip()
    else:
        raise RuntimeError(f"Cerebras API error {r.status_code}: {r.text[:200]}")


async def _call_groq_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Groq API call (raw HTTP, no LiteLLM dependency)."""
    import httpx

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return ""

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
        )

    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        global _total_tokens
        _total_tokens += data.get("usage", {}).get("total_tokens", 0)
        return content.strip()
    else:
        raise RuntimeError(f"Groq API error {r.status_code}: {r.text[:200]}")


async def _call_google_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Google AI Studio API call (raw HTTP, no LiteLLM dependency)."""
    import httpx

    api_key = os.environ.get("GOOGLE_AI_API_KEY", "")
    if not api_key:
        return ""

    contents = []
    system_instruction = None
    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("content", "")
        if role == "system":
            system_instruction = text
        else:
            contents.append({"role": role, "parts": [{"text": text}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    model_id = "gemini-2.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})

    if r.status_code == 200:
        data = r.json()
        candidates = data.get("candidates", [])
        if candidates:
            text_parts = candidates[0].get("content", {}).get("parts", [])
            content = text_parts[0].get("text", "") if text_parts else ""
            global _total_tokens
            _total_tokens += data.get("usageMetadata", {}).get("totalTokenCount", 0)
            return content.strip()
        return ""
    else:
        raise RuntimeError(f"Google API error {r.status_code}: {r.text[:200]}")


def get_stats() -> dict:
    """Return cumulative LLM call statistics."""
    return {
        "total_calls": _call_count,
        "total_tokens": _total_tokens,
        "total_errors": _total_errors,
    }


def reset_stats():
    """Reset statistics (for new test run)."""
    global _call_count, _total_tokens, _total_errors, _last_call_time, _call_start_time
    _call_count = 0
    _total_tokens = 0
    _total_errors = 0
    _last_call_time = 0.0
    _call_start_time = 0.0


def parse_confidence(text: str, default: float = 0.7) -> float:
    """Extract a 0.0-1.0 confidence number from LLM response text."""
    match = re.search(r"(\d+\.?\d*)", text.strip())
    if match:
        val = float(match.group(1))
        if val > 1:
            val = val / 100
        return max(0.0, min(1.0, val))
    return default
