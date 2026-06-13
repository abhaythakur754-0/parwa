"""Production LLM client using ZAI SDK (primary) + Google AI + OpenRouter (fallback).

Per PARWA Product Documentation v6.0 Smart Router:
- Light Tier:  gemini-2.0-flash-lite           (FAQs, Greetings, Order Status)
- Medium Tier: gemini-2.0-flash                (Drafting, Summarizing, Recommendations)
- Heavy Tier:  gemini-2.0-flash                (Refunds, Fraud, Complex Logic)

Routing: complexity 0-4 → Light, 5-9 → Medium, 10+ → Heavy
Failover: If primary model hits rate limit → auto-failover to next in tier.

Provider Priority (in order):
1. ZAI SDK (z-ai-web-dev-sdk) — highest throughput, best TPM, batch support
2. Google AI direct — generous free tier, reliable
3. OpenRouter free tier — needs OPENROUTER_KEY env var

API Keys (from environment variables):
- ZAI_SDK: Built-in via z-ai-web-dev-sdk (no key needed)
- GOOGLE_AI_KEY: Fallback — Google Gemini direct calls (generous free tier)
- OPENROUTER_KEY: Last resort — OpenRouter free tier models (if set)

Features:
- ZAI SDK as primary (maximizes TPM, avoids rate limits via batching)
- Direct HTTP calls via httpx for Google/OpenRouter (no extra dependency)
- Automatic failover: ZAI → Google → OpenRouter
- Rate limit handling with retry-after
- Circuit breaker per provider
- Token tracking for TurboQuant budget
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

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")  # Fallback — only used if key is set
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY", "AIzaSyATHbcolmlaNufj6ZHR6tebMmlqqcmCsEs")  # Primary

# ─── Provider Endpoints ─────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GOOGLE_AI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# ─── Model Definitions (aligned with config.py MODEL_TIERS per Docs v6.0) ───────

MODEL_MAP: dict[str, dict[str, str]] = {
    # ZAI SDK tier entries (primary — uses z-ai-web-dev-sdk via subprocess)
    "zai/light": {"provider": "zai", "model": "light"},
    "zai/medium": {"provider": "zai", "model": "medium"},
    "zai/heavy": {"provider": "zai", "model": "heavy"},
    "zai/guardrail": {"provider": "zai", "model": "guardrail"},
    # Light tier (Per docs: google/gemma-3-4b-it:free)
    "openrouter/google/gemma-3-4b-it:free": {"provider": "openrouter", "model": "google/gemma-3-4b-it:free"},
    "openrouter/meta-llama/llama-3.1-8b-instruct:free": {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free"},
    "gemini/gemini-2.0-flash-lite": {"provider": "google", "model": "gemini-2.0-flash-lite"},
    # Medium tier (Per docs: google/gemini-2.0-flash-exp:free)
    "openrouter/google/gemini-2.0-flash-exp:free": {"provider": "openrouter", "model": "google/gemini-2.0-flash-exp:free"},
    "gemini/gemini-2.0-flash": {"provider": "google", "model": "gemini-2.0-flash"},
    "openrouter/google/gemma-3-4b-it:free_fallback": {"provider": "openrouter", "model": "google/gemma-3-4b-it:free"},
    # Heavy tier (Per docs: deepseek/deepseek-r1-0528:free)
    "openrouter/deepseek/deepseek-r1-0528:free": {"provider": "openrouter", "model": "deepseek/deepseek-r1-0528:free"},
    "openrouter/meta-llama/llama-4-maverick:free": {"provider": "openrouter", "model": "meta-llama/llama-4-maverick:free"},
    # Guardrail
    "openrouter/meta-llama/llama-guard-4-12b:free": {"provider": "openrouter", "model": "meta-llama/llama-guard-4-12b:free"},
}

# Provider → API key mapping (ZAI SDK has no key — uses built-in auth)
PROVIDER_KEYS: dict[str, str] = {
    "zai": "builtin",  # ZAI SDK authenticates internally
    "openrouter": OPENROUTER_KEY,
    "google": GOOGLE_AI_KEY,
}

# Provider → URL mapping (ZAI SDK uses its own endpoint via subprocess)
PROVIDER_URLS: dict[str, str] = {
    "zai": "sdk://z-ai-web-dev-sdk",
    "openrouter": OPENROUTER_URL,
    "google": GOOGLE_AI_URL,
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
        if provider not in self._open_until:
            return False
        if time.time() < self._open_until[provider]:
            return True
        del self._open_until[provider]
        self._failures[provider] = 0
        return False

    def record_failure(self, provider: str) -> None:
        self._failures[provider] = self._failures.get(provider, 0) + 1
        if self._failures[provider] >= self.failure_threshold:
            self._open_until[provider] = time.time() + self.reset_timeout
            logger.warning("circuit_breaker: OPEN for %s (%d failures, reset in %.0fs)",
                          provider, self._failures[provider], self.reset_timeout)

    def record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        if provider in self._open_until:
            del self._open_until[provider]


_circuit_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30.0)  # More lenient — rate limits are temporary
# Register ZAI in circuit breaker tracking
_circuit_breaker._failures["zai"] = 0

# ─── Rate Limiter (simple per-provider) ─────────────────────────────────────────

_last_call_time: dict[str, float] = {}
MIN_CALL_INTERVAL = 0.3  # seconds between calls to same provider


async def _rate_limit_wait(provider: str) -> None:
    now = time.time()
    last = _last_call_time.get(provider, 0)
    elapsed = now - last
    if elapsed < MIN_CALL_INTERVAL:
        await asyncio.sleep(MIN_CALL_INTERVAL - elapsed)
    _last_call_time[provider] = time.time()


# ─── Google AI Native Call ──────────────────────────────────────────────────────

async def _call_google_ai_native(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call Google AI using the native generateContent endpoint."""
    if not GOOGLE_AI_KEY:
        raise ValueError("No Google AI API key configured")

    if _circuit_breaker.is_open("google"):
        raise ConnectionError("Circuit breaker open for Google AI")

    await _rate_limit_wait("google")

    url = GOOGLE_AI_URL.format(model=model) + f"?key={GOOGLE_AI_KEY}"

    system_instruction = None
    if system_prompt:
        system_instruction = {"parts": [{"text": system_prompt}]}

    contents = [{"role": "user", "parts": [{"text": user_prompt}]}]

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "5"))
            logger.warning("rate_limit: Google AI returned 429, retry after %.1fs", retry_after)
            await asyncio.sleep(min(retry_after, 10))
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            error_body = resp.text[:500]
            logger.error("google_ai: %s returned %d: %s", model, resp.status_code, error_body)
            _circuit_breaker.record_failure("google")
            raise RuntimeError(f"Google AI returned {resp.status_code}: {error_body}")

        data = resp.json()
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)

        usage_meta = data.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            "total_tokens": usage_meta.get("totalTokenCount", 0),
        }

        _circuit_breaker.record_success("google")

        return {
            "content": content,
            "model": f"google/{model}",
            "usage": usage,
        }

    except httpx.TimeoutException:
        _circuit_breaker.record_failure("google")
        raise TimeoutError("Google AI timed out after 60s")
    except httpx.ConnectError:
        _circuit_breaker.record_failure("google")
        raise ConnectionError("Cannot connect to Google AI")
    except Exception as exc:
        _circuit_breaker.record_failure("google")
        raise


# ─── OpenRouter Call ─────────────────────────────────────────────────────────────

async def _call_openrouter(
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call OpenRouter API for free-tier models."""
    if not OPENROUTER_KEY:
        raise ValueError("No OpenRouter API key configured")

    if _circuit_breaker.is_open("openrouter"):
        raise ConnectionError("Circuit breaker open for OpenRouter")

    await _rate_limit_wait("openrouter")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://parwa.ai",
        "X-Title": "PARWA AI Customer Support",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "5"))
            logger.warning("rate_limit: OpenRouter returned 429, retry after %.1fs", retry_after)
            await asyncio.sleep(min(retry_after, 10))
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)

        if resp.status_code != 200:
            error_body = resp.text[:500]
            logger.error("openrouter: %s returned %d: %s", model, resp.status_code, error_body)
            _circuit_breaker.record_failure("openrouter")
            raise RuntimeError(f"OpenRouter returned {resp.status_code}: {error_body}")

        data = resp.json()
        content = ""
        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "")

        usage = data.get("usage", {})
        if not usage:
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        _circuit_breaker.record_success("openrouter")

        return {
            "content": content,
            "model": f"openrouter/{model}",
            "usage": usage,
        }

    except httpx.TimeoutException:
        _circuit_breaker.record_failure("openrouter")
        raise TimeoutError("OpenRouter timed out after 60s")
    except httpx.ConnectError:
        _circuit_breaker.record_failure("openrouter")
        raise ConnectionError("Cannot connect to OpenRouter")
    except Exception as exc:
        _circuit_breaker.record_failure("openrouter")
        raise


# ─── Core LLM Call ──────────────────────────────────────────────────────────────

# ─── ZAI SDK Call ────────────────────────────────────────────────────────────────

async def _call_zai_sdk(
    tier: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call LLM via the ZAI SDK (z-ai-web-dev-sdk) through the Python wrapper.

    Uses zai_llm.py which spawns a Node.js subprocess to call the SDK.
    The ZAI SDK handles model routing internally based on the tier label.
    """
    from parwa.utils.zai_llm import call_zai_llm

    if _circuit_breaker.is_open("zai"):
        raise ConnectionError("Circuit breaker open for ZAI SDK")

    await _rate_limit_wait("zai")

    try:
        result = await call_zai_llm(
            system_prompt, user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_tier=tier,
        )
        _circuit_breaker.record_success("zai")
        result["provider"] = "zai"
        return result
    except (RuntimeError, ConnectionError, TimeoutError, FileNotFoundError) as exc:
        _circuit_breaker.record_failure("zai")
        raise


# ─── Core LLM Call ──────────────────────────────────────────────────────────────

async def call_llm(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call an LLM via the appropriate provider. Returns {content, model, usage}.

    Routes to:
    1. ZAI SDK (for zai/ prefixed models — primary, highest throughput)
    2. OpenRouter (for openrouter/ prefixed models — free tier)
    3. Google AI direct (for gemini/ prefixed models — direct API)
    """
    model_info = MODEL_MAP.get(model_name)
    if not model_info:
        raise ValueError(f"Unknown model: {model_name}")

    provider = model_info["provider"]
    actual_model = model_info["model"]

    if provider == "zai":
        return await _call_zai_sdk(
            actual_model, system_prompt, user_prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
    elif provider == "openrouter":
        return await _call_openrouter(
            actual_model, system_prompt, user_prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
    elif provider == "google":
        return await _call_google_ai_native(
            actual_model, system_prompt, user_prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


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
    Provider priority: ZAI SDK → Google AI → OpenRouter.
    Returns the first successful response, or raises if all fail.
    """
    last_error = None
    for model_name in model_chain:
        # Skip models we don't have keys for
        model_info = MODEL_MAP.get(model_name)
        if model_info:
            provider = model_info["provider"]
            api_key = PROVIDER_KEYS.get(provider, "")
            if not api_key:
                continue

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


# ─── Test Connection ─────────────────────────────────────────────────────────────

async def test_provider(provider: str) -> dict[str, Any]:
    """Test if a provider's API key works by making a simple call."""
    api_key = PROVIDER_KEYS.get(provider)

    if not api_key:
        return {"provider": provider, "status": "error", "message": "No API key configured"}

    test_models = {
        "zai": "zai/light",
        "openrouter": "google/gemma-3-4b-it:free",
        "google": "gemini-2.0-flash-lite",
    }
    model = test_models.get(provider, "google/gemma-3-4b-it:free")

    try:
        if provider == "zai":
            # Test ZAI SDK via the subprocess wrapper
            start = time.time()
            result = await _call_zai_sdk(
                "light", "", "Say hello in one word.",
                temperature=0.1, max_tokens=10,
            )
            elapsed = time.time() - start
            return {
                "provider": provider,
                "status": "ok",
                "latency_ms": round(elapsed * 1000),
                "response": result.get("content", "")[:100],
                "model": result.get("model", "zai/unknown"),
            }

        elif provider == "openrouter":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://parwa.ai",
                "X-Title": "PARWA AI Test",
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Say hello in one word."}],
                "max_tokens": 10,
                "temperature": 0.1,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                start = time.time()
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
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

        elif provider == "google":
            url = GOOGLE_AI_URL.format(model=model) + f"?key={api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Say hello in one word."}]}],
                "generationConfig": {"maxOutputTokens": 10, "temperature": 0.1},
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                start = time.time()
                resp = await client.post(url, json=payload)
                elapsed = time.time() - start

            if resp.status_code == 200:
                data = resp.json()
                content = ""
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join(p.get("text", "") for p in parts)
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
        return {"provider": provider, "status": "error", "message": str(exc)[:200]}


async def test_all_providers() -> dict[str, dict[str, Any]]:
    """Test all providers and return results."""
    results = {}
    providers_to_test = []

    # ZAI is always available (no key needed)
    providers_to_test.append("zai")
    if OPENROUTER_KEY:
        providers_to_test.append("openrouter")
    if GOOGLE_AI_KEY:
        providers_to_test.append("google")

    tasks = [test_provider(p) for p in providers_to_test]
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
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                call_llm(model_name, system_prompt, user_prompt,
                        temperature=temperature, max_tokens=max_tokens)
            )
            return future.result(timeout=65)
    else:
        return asyncio.run(
            call_llm(model_name, system_prompt, user_prompt,
                    temperature=temperature, max_tokens=max_tokens)
        )
