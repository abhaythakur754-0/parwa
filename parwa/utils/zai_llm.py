"""ZAI SDK LLM client for PARWA — primary provider with batch support.

Wraps the z-ai-web-dev-sdk (Node.js) for use in PARWA's Python pipeline.
Calls the SDK via subprocess (zai_llm_helper.mjs) since the SDK is JavaScript-only.

Features:
- Async-first: all functions are async
- Batch processing: group multiple LLM calls into single subprocess invocations
- Circuit breaker: opens after repeated ZAI SDK failures
- Rate limiting: built-in delay between calls to maximize TPM
- Fallback: if ZAI SDK fails, falls back to real_llm.py (Google AI / OpenRouter)
- Model tier routing: light/medium/heavy → ZAI SDK (which handles routing internally)

Architecture:
  Python zai_llm.py
    → asyncio.create_subprocess_exec("node", "zai_llm_helper.mjs")
      → Node.js zai_llm_helper.mjs
        → ZAI SDK (z-ai-web-dev-sdk)
          → LLM completion
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("parwa.zai_llm")

# ─── Path to Node.js helper script ───────────────────────────────────────────────

_HELPER_SCRIPT = Path(__file__).parent / "zai_llm_helper.mjs"

# ─── Circuit Breaker for ZAI SDK ─────────────────────────────────────────────────

class ZAICircuitBreaker:
    """Circuit breaker specifically for ZAI SDK calls.

    Opens after N consecutive failures, resets after timeout.
    Prevents repeated subprocess spawns when the SDK is down.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures: int = 0
        self._open_until: float = 0.0

    def is_open(self) -> bool:
        """Check if the circuit is open (should fail-fast)."""
        if self._open_until == 0.0:
            return False
        if time.monotonic() < self._open_until:
            return True
        # Timeout elapsed → half-open: allow one attempt
        self._open_until = 0.0
        self._failures = 0
        return False

    def record_failure(self) -> None:
        """Record a failure. Opens circuit if threshold is reached."""
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._open_until = time.monotonic() + self.reset_timeout
            logger.warning(
                "zai_circuit_breaker: OPEN (%d failures, reset in %.0fs)",
                self._failures,
                self.reset_timeout,
            )

    def record_success(self) -> None:
        """Record a success. Resets failure count."""
        self._failures = 0
        self._open_until = 0.0


_zai_circuit_breaker = ZAICircuitBreaker(failure_threshold=8, reset_timeout=60.0)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────────

_last_call_time: float = 0.0
_MIN_CALL_INTERVAL = 1.5  # seconds between ZAI subprocess spawns (increased for TPM management)


async def _rate_limit_wait() -> None:
    """Wait if needed to respect rate limits."""
    global _last_call_time
    now = time.monotonic()
    elapsed = now - _last_call_time
    if elapsed < _MIN_CALL_INTERVAL:
        await asyncio.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_time = time.monotonic()


# ─── Model Tier Mapping ──────────────────────────────────────────────────────────

# The ZAI SDK handles model routing internally, but we map tiers to
# descriptive identifiers for logging and tracking.
TIER_MODEL_LABEL = {
    "light": "zai/light",
    "medium": "zai/medium",
    "heavy": "zai/heavy",
    "guardrail": "zai/guardrail",
}

# ─── Subprocess Call to Node.js Helper ───────────────────────────────────────────

async def _run_helper_script(prompts: list[dict]) -> list[dict]:
    """Run the ZAI helper Node.js script with the given prompts.

    Args:
        prompts: List of prompt dicts, each with:
            - id: unique identifier
            - messages: list of {role, content} dicts
            - temperature: float (optional)
            - max_tokens: int (optional)

    Returns:
        List of result dicts, each with:
            - id: matches input id
            - content: response text
            - model: model identifier
            - usage: token usage dict
            - error: error message or None

    Raises:
        RuntimeError: If the subprocess fails entirely (not individual prompt errors)
    """
    if not _HELPER_SCRIPT.exists():
        raise FileNotFoundError(f"ZAI helper script not found: {_HELPER_SCRIPT}")

    input_json = json.dumps(prompts)

    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            str(_HELPER_SCRIPT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=input_json.encode("utf-8")),
            timeout=120.0,  # 2 min timeout for the whole batch
        )

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[:500]
            logger.error("zai_helper: subprocess exited %d: %s", proc.returncode, err_msg)
            raise RuntimeError(f"ZAI helper script exited with code {proc.returncode}: {err_msg}")

        # Parse stdout
        output_text = stdout.decode("utf-8")
        if not output_text.strip():
            raise RuntimeError("ZAI helper script returned empty output")

        results = json.loads(output_text)
        if not isinstance(results, list):
            raise RuntimeError(f"ZAI helper returned unexpected type: {type(results).__name__}")

        return results

    except asyncio.TimeoutError:
        proc.kill()  # type: ignore[union-attr]
        raise TimeoutError("ZAI helper script timed out after 120s")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ZAI helper returned invalid JSON: {exc}")


# ─── Public API: Single Call ─────────────────────────────────────────────────────

async def call_zai_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
    model_tier: str = "light",
) -> dict[str, Any]:
    """Make a single LLM call via the ZAI SDK.

    Args:
        system_prompt: System instruction.
        user_prompt: User message.
        temperature: Sampling temperature (0.0 - 1.0).
        max_tokens: Maximum output tokens.
        model_tier: Tier label for routing/logging (light/medium/heavy/guardrail).
                    The ZAI SDK handles actual model selection internally.

    Returns:
        Dict with keys: content, model, usage, tier.

    Raises:
        ConnectionError: If circuit breaker is open.
        RuntimeError: If the ZAI SDK call fails.
        TimeoutError: If the subprocess times out.
    """
    if _zai_circuit_breaker.is_open():
        raise ConnectionError("ZAI SDK circuit breaker is open — failing fast")

    await _rate_limit_wait()

    request_id = str(uuid.uuid4())[:8]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    prompts = [
        {
            "id": request_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ]

    logger.debug("zai_llm: calling ZAI SDK (id=%s, tier=%s)", request_id, model_tier)

    results = await _run_helper_script(prompts)
    result = results[0]

    if result.get("error"):
        _zai_circuit_breaker.record_failure()
        raise RuntimeError(f"ZAI SDK error: {result['error']}")

    _zai_circuit_breaker.record_success()

    return {
        "content": result["content"],
        "model": result.get("model", "zai/default"),
        "usage": result.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
        "tier": model_tier,
    }


# ─── Public API: Batch Call ───────────────────────────────────────────────────────

async def call_zai_llm_batch(
    prompts: list[dict],
) -> list[dict]:
    """Process multiple LLM prompts in a single ZAI SDK subprocess call.

    This is more efficient than calling call_zai_llm() in a loop because
    it spawns only one Node.js process and lets the helper script handle
    all prompts sequentially with rate-limit-friendly delays.

    Args:
        prompts: List of dicts, each with:
            - system_prompt: str (optional, defaults to "")
            - user_prompt: str (required)
            - temperature: float (optional, defaults to 0.1)
            - max_tokens: int (optional, defaults to 500)
            - model_tier: str (optional, for logging only)

    Returns:
        List of result dicts in the SAME ORDER as input, each with:
            - content: str (empty string if this item failed)
            - model: str
            - usage: dict
            - tier: str (from input)
            - error: str | None (error message if this item failed)

    Raises:
        ConnectionError: If circuit breaker is open (no prompts attempted).
        RuntimeError: If the entire subprocess fails.
    """
    if not prompts:
        return []

    if _zai_circuit_breaker.is_open():
        raise ConnectionError("ZAI SDK circuit breaker is open — failing fast")

    await _rate_limit_wait()

    # Convert to helper script format
    helper_prompts = []
    for i, p in enumerate(prompts):
        messages = []
        system = p.get("system_prompt", "")
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": p["user_prompt"]})

        helper_prompts.append({
            "id": p.get("id", f"batch-{i}"),
            "messages": messages,
            "temperature": p.get("temperature", 0.1),
            "max_tokens": p.get("max_tokens", 500),
        })

    logger.debug("zai_llm_batch: calling ZAI SDK with %d prompts", len(prompts))

    try:
        raw_results = await _run_helper_script(helper_prompts)
    except (RuntimeError, TimeoutError, FileNotFoundError) as exc:
        _zai_circuit_breaker.record_failure()
        # Return error results for all prompts
        return [
            {
                "content": "",
                "model": "zai/failed",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "tier": p.get("model_tier", "light"),
                "error": str(exc),
            }
            for p in prompts
        ]

    # Map results back, preserving order
    # Helper script returns results in the same order as input
    results = []
    all_ok = True
    for i, raw in enumerate(raw_results):
        tier = prompts[i].get("model_tier", "light") if i < len(prompts) else "light"
        error = raw.get("error")
        if error:
            all_ok = False

        results.append({
            "content": raw.get("content", ""),
            "model": raw.get("model", "zai/default"),
            "usage": raw.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            "tier": tier,
            "error": error,
        })

    if all_ok:
        _zai_circuit_breaker.record_success()
    else:
        # Partial failure — record failure but still return results
        _zai_circuit_breaker.record_failure()

    return results


# ─── Public API: Failover Call ────────────────────────────────────────────────────

async def call_zai_llm_with_failover(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
    model_tier: str = "light",
    model_chain: list[str] | None = None,
) -> dict[str, Any]:
    """Call ZAI SDK first; if it fails, fall back to real_llm providers.

    This is the main entry point for the PARWA pipeline. It tries ZAI SDK
    first (high throughput, avoids rate limits), then falls back to the
    existing Google AI / OpenRouter providers in real_llm.py.

    Args:
        system_prompt: System instruction.
        user_prompt: User message.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        model_tier: Tier for ZAI SDK routing/logging.
        model_chain: Fallback model chain for real_llm (e.g. from config.MODEL_TIERS).
                     If None, uses a sensible default for the tier.

    Returns:
        Dict with keys: content, model, usage, tier, provider.
    """
    # Try ZAI SDK first
    try:
        result = await call_zai_llm(
            system_prompt, user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_tier=model_tier,
        )
        result["provider"] = "zai"
        logger.debug("zai_llm_with_failover: ZAI succeeded (model=%s)", result.get("model"))
        return result
    except (RuntimeError, ConnectionError, TimeoutError, FileNotFoundError) as exc:
        logger.info("zai_llm_with_failover: ZAI failed (%s), falling back to real_llm", exc)

    # Fallback: use real_llm.py
    from parwa.utils.real_llm import call_llm_with_failover

    if model_chain is None:
        # Build a default fallback chain for the tier
        from parwa.config import MODEL_TIERS
        model_chain = MODEL_TIERS.get(model_tier, MODEL_TIERS["light"])

    try:
        result = await call_llm_with_failover(
            model_chain, system_prompt, user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result["provider"] = "real_llm_fallback"
        result["tier"] = model_tier
        logger.debug("zai_llm_with_failover: real_llm fallback succeeded (model=%s)", result.get("model"))
        return result
    except RuntimeError as exc:
        logger.error("zai_llm_with_failover: ALL providers failed: %s", exc)
        raise


# ─── Circuit Breaker Stats ────────────────────────────────────────────────────────

def get_zai_circuit_breaker_stats() -> dict[str, Any]:
    """Get current ZAI circuit breaker statistics."""
    return {
        "is_open": _zai_circuit_breaker.is_open(),
        "failures": _zai_circuit_breaker._failures,
        "failure_threshold": _zai_circuit_breaker.failure_threshold,
        "reset_timeout": _zai_circuit_breaker.reset_timeout,
        "open_until": _zai_circuit_breaker._open_until,
    }


def reset_zai_circuit_breaker() -> None:
    """Manually reset the ZAI circuit breaker."""
    _zai_circuit_breaker.record_success()
    logger.info("zai_circuit_breaker: manually reset to CLOSED")
