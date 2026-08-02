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
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.pipeline.llm")

# ── Provider Pool with Cooldown + Round-Robin ──────────────────────

class ProviderPool:
    """Smart routing pool — rotates across providers, cools down on 429.

    When a provider returns 429 (rate limited) or 5xx, it's marked as
    "cooling down" for COOLDOWN_SECONDS. Subsequent calls skip cooling-down
    providers and use the next available one. This lets us spread load
    across Groq, Cerebras, Google, NVIDIA instead of hammering one provider.

    Usage:
        pool = get_provider_pool()
        provider_name, fn = pool.next_available()
        result = await fn(messages, temp, max_tokens, call_id)
        pool.record_result(provider_name, success=True)
    """

    COOLDOWN_SECONDS: float = 60.0  # Cool down for 60s after a 429
    MAX_CALLS_PER_PROVIDER: int = 25  # Reset counter after this many success

    def __init__(self):
        self._cooldown_until: Dict[str, float] = {}  # provider → expiry timestamp
        self._call_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)
        self._fail_counts: Dict[str, int] = defaultdict(int)
        self._rr_index: int = 0  # round-robin counter
        self._lock = asyncio.Lock()

    def _is_available(self, provider_name: str, providers: List[str]) -> bool:
        """Check if a provider is available (not cooling down)."""
        expiry = self._cooldown_until.get(provider_name, 0)
        if time.time() < expiry:
            return False
        return True

    def next_available(self, providers: List[Tuple[str, callable]]) -> Optional[Tuple[str, callable]]:
        """Get the next available provider via round-robin (skips cooling-down)."""
        if not providers:
            return None
        n = len(providers)
        for i in range(n):
            idx = (self._rr_index + i) % n
            name, fn = providers[idx]
            if self._is_available(name, providers):
                self._rr_index = (idx + 1) % n  # advance for next call
                return name, fn
        # All cooling down — return the one with earliest cooldown expiry
        return providers[0]  # fallback: try first anyway

    def record_success(self, provider_name: str):
        """Record a successful call."""
        self._call_counts[provider_name] += 1
        self._success_counts[provider_name] += 1
        # Clear any cooldown on success
        self._cooldown_until.pop(provider_name, None)

    def record_failure(self, provider_name: str, status_code: int = 0):
        """Record a failed call. If 429/5xx, cool down the provider."""
        self._call_counts[provider_name] += 1
        self._fail_counts[provider_name] += 1
        if status_code == 429 or status_code >= 500:
            self._cooldown_until[provider_name] = time.time() + self.COOLDOWN_SECONDS
            logger.warning(
                "provider_cooldown name=%s status=%d cooldown_until=%.0fs reason=rate_limited_or_server_error",
                provider_name, status_code, self.COOLDOWN_SECONDS,
            )

    def get_status(self) -> Dict[str, Dict]:
        """Get provider health status (for debugging)."""
        now = time.time()
        status = {}
        for name in list(self._cooldown_until.keys()) + list(self._call_counts.keys()):
            cooldown_left = max(0, self._cooldown_until.get(name, 0) - now)
            status[name] = {
                "available": cooldown_left == 0,
                "cooldown_seconds_left": round(cooldown_left, 1),
                "total_calls": self._call_counts.get(name, 0),
                "successes": self._success_counts.get(name, 0),
                "failures": self._fail_counts.get(name, 0),
            }
        return status


# Global provider pool singleton
_provider_pool: Optional[ProviderPool] = None

def get_provider_pool() -> ProviderPool:
    """Get the global provider pool singleton."""
    global _provider_pool
    if _provider_pool is None:
        _provider_pool = ProviderPool()
    return _provider_pool


# ── Rate Limiter ───────────────────────────────────────────────────

_last_call_time: float = 0.0
_rate_lock: asyncio.Lock = None
MIN_CALL_INTERVAL: float = 0.2  # 300 RPM across all providers (was 0.5/120 RPM)
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

    # ── PRIMARY: Provider Pool with round-robin + cooldown ──
    # Rotates across Groq, Google, Cerebras, NVIDIA. When a provider returns
    # 429 (rate limited), it's cooled down for 60s and subsequent calls skip it.
    # This spreads load across all configured providers instead of hammering one.
    pool = get_provider_pool()
    all_providers = [
        ("groq", _call_groq_direct),
        ("google", _call_google_direct),
        ("cerebras", _call_cerebras_direct),
        ("nvidia", _call_nvidia_direct),
    ]

    # Try each available provider via round-robin
    tried_providers = set()
    for _attempt in range(len(all_providers)):
        next_provider = pool.next_available(all_providers)
        if not next_provider:
            break
        provider_name, provider_fn = next_provider
        if provider_name in tried_providers:
            break  # already tried all available
        tried_providers.add(provider_name)

        try:
            result = await provider_fn(messages, temperature, max_tokens, call_id)
            if result and len(result.strip()) > 0:
                pool.record_success(provider_name)
                logger.info("LLM call #%d: %s SUCCESS (%d chars)", call_id, provider_name, len(result))
                return result
            pool.record_failure(provider_name, status_code=0)  # empty response
            logger.warning("LLM call #%d: %s returned empty response", call_id, provider_name)
        except RuntimeError as exc:
            # Extract status code from error message like "Groq API error 429: ..."
            status_code = 0
            msg = str(exc)
            for part in msg.split():
                if part.isdigit():
                    status_code = int(part)
                    break
            pool.record_failure(provider_name, status_code=status_code)
            logger.warning("LLM call #%d: %s failed (status=%d): %s", call_id, provider_name, status_code, str(exc)[:100])
        except Exception as exc:
            pool.record_failure(provider_name, status_code=0)
            logger.warning("LLM call #%d: %s error: %s", call_id, provider_name, str(exc)[:100])

    # ── FALLBACK: Smart Router (LiteLLM — 11 models via 3 API keys) ──
    try:
        smart_result = await _call_smart_router(messages, temperature, max_tokens, call_id, step_type)
        if smart_result and len(smart_result.strip()) > 0:
            logger.info("LLM call #%d: Smart Router SUCCESS (%d chars)", call_id, len(smart_result))
            return smart_result
        logger.warning("LLM call #%d: Smart Router returned empty/short response", call_id)
    except Exception as exc:
        logger.warning("LLM call #%d: Smart Router error (%s)", call_id, str(exc)[:150])

    # ── LAST RESORT: Direct LiteLLM call ──
    try:
        direct_result = await _call_litellm_direct(messages, temperature, max_tokens, call_id)
        if direct_result and len(direct_result.strip()) > 0:
            logger.info("LLM call #%d: Direct LiteLLM SUCCESS (%d chars)", call_id, len(direct_result))
            return direct_result
    except Exception as exc:
        logger.warning("LLM call #%d: Direct LiteLLM error (%s)", call_id, str(exc)[:150])

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
