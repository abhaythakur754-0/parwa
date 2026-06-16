"""Production LLM client using real API providers: NVIDIA, Google AI, Cerebras, Groq.

v2: Adds NVIDIA API as primary provider with GLM-5.1, DeepSeek, and Llama models.

Replaces ZAI SDK subprocess calls with direct HTTP API calls.
Uses the Smart Router tier system: Light → Medium → Heavy with automatic failover.

API Keys (from environment variables):
- NVIDIA: NVIDIA_API_KEY (PRIMARY — highest rate limits)
- Google AI: GOOGLE_AI_KEY
- Cerebras: CEREBRAS_KEY
- Groq: GROQ_KEY

Features:
- Direct HTTP calls via httpx (no subprocess, no ZAI SDK dependency)
- Automatic failover: if primary model fails, try next in tier chain
- Rate limit handling with retry-after
- Circuit breaker per provider
- Token tracking for TurboQuant budget
- NVIDIA API as primary (highest throughput, supports GLM-5.1)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("parwa.real_llm")

# ─── API Keys (from environment or defaults) ────────────────────────────────────

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "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")
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY", "")
CEREBRAS_KEY = os.getenv("CEREBRAS_KEY", "")
GROQ_KEY = os.getenv("GROQ_KEY", "")

# ─── Provider Endpoints ─────────────────────────────────────────────────────────

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GOOGLE_AI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── Model Definitions (v2: NVIDIA as primary) ─────────────────────────────────

# Maps our model names to provider + actual model ID
MODEL_MAP: dict[str, dict[str, str]] = {
    # ── NVIDIA models (PRIMARY — highest rate limits) ──
    "nvidia/glm-5.1": {"provider": "nvidia", "model": "z-ai/glm-5.1"},
    "nvidia/deepseek-v4-flash": {"provider": "nvidia", "model": "deepseek-ai/deepseek-v4-flash"},
    "nvidia/llama-3.3-70b": {"provider": "nvidia", "model": "meta/llama-3.3-70b-instruct"},
    # ── Light tier ──
    "cerebras/llama-3.1-8b": {"provider": "cerebras", "model": "llama-3.1-8b"},
    "groq/llama-3.1-8b-instant": {"provider": "groq", "model": "llama-3.1-8b-instant"},
    "gemini/gemma-3-27b-it": {"provider": "google", "model": "gemma-3-27b-it"},
    # ── Medium tier ──
    "gemini/gemini-2.0-flash-lite": {"provider": "google", "model": "gemini-2.0-flash-lite"},
    "gemini/gemini-2.0-flash": {"provider": "google", "model": "gemini-2.0-flash"},
    "groq/llama-3.3-70b-versatile": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    "groq/qwen3-32b": {"provider": "groq", "model": "qwen3-32b"},
    # ── Heavy tier ──
    "cerebras/llama-4-scout-17b-16e-instruct": {"provider": "cerebras", "model": "llama-4-scout-17b-16e-instruct"},
    # ── Guardrail ──
    "groq/llama-guard-4-12b": {"provider": "groq", "model": "llama-guard-4-12b"},
}

# Provider → API key mapping
PROVIDER_KEYS: dict[str, str] = {
    "nvidia": NVIDIA_KEY,
    "google": GOOGLE_AI_KEY,
    "cerebras": CEREBRAS_KEY,
    "groq": GROQ_KEY,
}

# Provider → URL mapping
PROVIDER_URLS: dict[str, str] = {
    "nvidia": NVIDIA_URL,
    "google": GOOGLE_AI_URL,
    "cerebras": CEREBRAS_URL,
    "groq": GROQ_URL,
}

# ─── Default Model Chains (v2: NVIDIA first) ───────────────────────────────────

DEFAULT_MODEL_CHAINS: dict[str, list[str]] = {
    "routing": ["nvidia/deepseek-v4-flash", "nvidia/llama-3.3-70b"],
    "reasoning": ["nvidia/glm-5.1", "nvidia/deepseek-v4-flash", "nvidia/llama-3.3-70b"],
    "response": ["nvidia/glm-5.1", "nvidia/deepseek-v4-flash", "nvidia/llama-3.3-70b"],
    "evaluation": ["nvidia/deepseek-v4-flash", "nvidia/llama-3.3-70b"],
    "light": ["nvidia/deepseek-v4-flash", "cerebras/llama-3.1-8b", "groq/llama-3.1-8b-instant"],
    "medium": ["nvidia/glm-5.1", "nvidia/deepseek-v4-flash", "groq/llama-3.3-70b-versatile"],
    "heavy": ["nvidia/glm-5.1", "nvidia/deepseek-v4-flash", "cerebras/llama-4-scout-17b-16e-instruct"],
}

# ─── Circuit Breaker ────────────────────────────────────────────────────────────

class CircuitBreaker:
    """Per-provider circuit breaker. Opens after N failures, resets after timeout."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        """Check if the circuit is open (provider is down)."""
        if provider not in self._open_until:
            return False
        if time.time() < self._open_until[provider]:
            return True
        # Timeout passed — reset
        del self._open_until[provider]
        self._failures[provider] = 0
        return False

    def record_failure(self, provider: str) -> None:
        """Record a failure for this provider."""
        self._failures[provider] = self._failures.get(provider, 0) + 1
        if self._failures[provider] >= self.failure_threshold:
            self._open_until[provider] = time.time() + self.reset_timeout
            logger.warning("circuit_breaker: OPEN for %s (%d failures, reset in %.0fs)",
                          provider, self._failures[provider], self.reset_timeout)

    def record_success(self, provider: str) -> None:
        """Record a success — reset failure count."""
        self._failures[provider] = 0
        if provider in self._open_until:
            del self._open_until[provider]


_circuit_breaker = CircuitBreaker()

# ─── Rate Limiter (simple per-provider) ─────────────────────────────────────────

_last_call_time: dict[str, float] = {}
MIN_CALL_INTERVAL = 0.3  # seconds between calls to same provider (NVIDIA can go faster)
NVIDIA_MIN_INTERVAL = 0.1  # NVIDIA has higher rate limits


async def _rate_limit_wait(provider: str) -> None:
    """Wait if needed to respect per-provider rate limits."""
    min_interval = NVIDIA_MIN_INTERVAL if provider == "nvidia" else MIN_CALL_INTERVAL
    now = time.time()
    last = _last_call_time.get(provider, 0)
    elapsed = now - last
    if elapsed < min_interval:
        await asyncio.sleep(min_interval - elapsed)
    _last_call_time[provider] = time.time()


# ─── Core LLM Call ──────────────────────────────────────────────────────────────

async def call_llm(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call an LLM via direct HTTP API. Returns {content, model, usage}.

    Uses OpenAI-compatible API format (supported by all 4 providers).

    Args:
        model_name: Our model key (e.g. "nvidia/glm-5.1")
        system_prompt: System instructions
        user_prompt: User message
        temperature: Sampling temperature
        max_tokens: Max response tokens

    Returns:
        Dict with content, model, usage (prompt_tokens, completion_tokens, total_tokens)
    """
    model_info = MODEL_MAP.get(model_name)
    if not model_info:
        raise ValueError(f"Unknown model: {model_name}")

    provider = model_info["provider"]
    actual_model = model_info["model"]
    api_key = PROVIDER_KEYS.get(provider, "")
    base_url = PROVIDER_URLS.get(provider, "")

    if not api_key:
        raise ValueError(f"No API key for provider: {provider}")

    # Circuit breaker check
    if _circuit_breaker.is_open(provider):
        raise ConnectionError(f"Circuit breaker open for {provider}")

    # Rate limit
    await _rate_limit_wait(provider)

    # Build request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": actual_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(base_url, headers=headers, json=payload)

        if resp.status_code == 429:
            # Rate limited — extract retry-after
            retry_after = float(resp.headers.get("retry-after", "5"))
            logger.warning("rate_limit: %s returned 429, retry after %.1fs", provider, retry_after)
            await asyncio.sleep(retry_after)
            # Retry once
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(base_url, headers=headers, json=payload)

        if resp.status_code != 200:
            error_body = resp.text[:500]
            logger.error("llm_call: %s/%s returned %d: %s", provider, actual_model, resp.status_code, error_body)
            _circuit_breaker.record_failure(provider)
            raise RuntimeError(f"{provider} API returned {resp.status_code}: {error_body}")

        data = resp.json()

        # Parse OpenAI-compatible response
        content = ""
        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        if not usage:
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        _circuit_breaker.record_success(provider)

        return {
            "content": content,
            "model": f"{provider}/{actual_model}",
            "usage": usage,
        }

    except httpx.TimeoutException:
        _circuit_breaker.record_failure(provider)
        raise TimeoutError(f"{provider} API timed out after 45s")
    except httpx.ConnectError:
        _circuit_breaker.record_failure(provider)
        raise ConnectionError(f"Cannot connect to {provider} API")
    except Exception as exc:
        _circuit_breaker.record_failure(provider)
        raise


async def call_llm_with_failover(
    model_chain: list[str],
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call LLM with automatic failover through the model chain.

    Tries each model in order until one succeeds.
    Returns the first successful response, or raises if all fail.
    """
    last_error = None
    for model_name in model_chain:
        try:
            result = await call_llm(
                model_name, system_prompt, user_prompt,
                temperature=temperature, max_tokens=max_tokens,
            )
            return result
        except (RuntimeError, ConnectionError, TimeoutError, ValueError) as exc:
            logger.debug("failover: %s failed (%s), trying next", model_name, exc)
            last_error = exc
            continue

    raise RuntimeError(f"All models in chain failed. Last error: {last_error}")


# ─── Convenience: Call with default chain ──────────────────────────────────────

async def call_for_purpose(
    purpose: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call LLM with the default model chain for a purpose.

    Args:
        purpose: One of "routing", "reasoning", "response", "evaluation"
        system_prompt: System instructions
        user_prompt: User message
        temperature: Sampling temperature
        max_tokens: Max response tokens

    Returns:
        Dict with content, model, usage
    """
    chain = DEFAULT_MODEL_CHAINS.get(purpose, DEFAULT_MODEL_CHAINS["medium"])
    return await call_llm_with_failover(
        chain, system_prompt, user_prompt,
        temperature=temperature, max_tokens=max_tokens,
    )


# ─── Test Connection ────────────────────────────────────────────────────────────

async def test_provider(provider: str) -> dict[str, Any]:
    """Test if a provider's API key works by making a simple call."""
    api_key = PROVIDER_KEYS.get(provider)
    base_url = PROVIDER_URLS.get(provider)

    if not api_key or not base_url:
        return {"provider": provider, "status": "error", "message": "No API key or URL"}

    # Pick a model for this provider
    test_models = {
        "nvidia": "deepseek-ai/deepseek-v4-flash",
        "google": "gemma-3-27b-it",
        "cerebras": "llama-3.1-8b",
        "groq": "llama-3.1-8b-instant",
    }
    model = test_models.get(provider, "llama-3.1-8b")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Say hello in one word."},
        ],
        "max_tokens": 10,
        "temperature": 0.1,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            start = time.time()
            resp = await client.post(base_url, headers=headers, json=payload)
            elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            content = ""
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("message", {}).get("content", "")
            return {
                "provider": provider,
                "status": "ok",
                "latency_ms": round(elapsed * 1000),
                "response": content[:100],
                "model": model,
            }
        else:
            return {
                "provider": provider,
                "status": "error",
                "status_code": resp.status_code,
                "message": resp.text[:200],
            }
    except Exception as exc:
        return {
            "provider": provider,
            "status": "error",
            "message": str(exc)[:200],
        }


async def test_all_providers() -> dict[str, dict[str, Any]]:
    """Test all providers and return results."""
    results = {}
    tasks = [test_provider(p) for p in ["nvidia", "cerebras", "groq", "google"]]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    for resp in responses:
        if isinstance(resp, Exception):
            results["unknown"] = {"status": "error", "message": str(resp)}
        else:
            results[resp["provider"]] = resp
    return results


# ─── Sync wrapper for convenience ───────────────────────────────────────────────

def call_llm_sync(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Synchronous wrapper for call_llm."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context already — use nest_asyncio or run in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                call_llm(model_name, system_prompt, user_prompt,
                        temperature=temperature, max_tokens=max_tokens)
            )
            return future.result(timeout=35)
    else:
        return asyncio.run(
            call_llm(model_name, system_prompt, user_prompt,
                    temperature=temperature, max_tokens=max_tokens)
        )
