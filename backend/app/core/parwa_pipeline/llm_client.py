"""
PARWA Pipeline V2 — Shared LLM Client

Production LLM routing via node-based assembly line + Smart Router fallback.

User-validated (2026-08-12): "llama-3.1-8b gives best results for ALL pipeline
tasks." Groq llama-3.1-8b-instant is now PRIMARY for all runtime tiers.

Node-based routing (assembly line — no ticket waits for another):
  LIGHT  (≤150 tok): Groq → Cerebras → Mistral → Gemini → Aion → NVIDIA
  MEDIUM (≤300 tok): Groq → Cerebras → Mistral → Gemini → Aion → NVIDIA
  HEAVY  (300+ tok): Cerebras → Groq → Mistral → Gemini → Aion → NVIDIA
  BUILDER:           Groq llama-3.1-8b-instant (onboarding agent creation)
  GUARDRAIL:         Groq GPT-OSS Safeguard 20B

NVIDIA GLM-5.2 is LAST in runtime fallback chains because it takes ~58s/call
(warm) / 90s+ (cold) — using it as primary caused the 11-node pipeline to
take 5-10 MINUTES per ticket → Render HTTP timeout → ticket escalated.
NVIDIA is still used for embeddings (different endpoint, fast).

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
    # 401/403/402 (key missing/revoked/quota-dead) do NOT self-heal in 60s
    # (live case 2026-09-10: NVIDIA key inference revoked → every call
    # 403/hang, retried forever). Park the provider for 15 minutes.
    AUTH_ERROR_COOLDOWN_SECONDS: float = 900.0
    TIMEOUT_COOLDOWN_SECONDS: float = 120.0
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

    def record_failure(self, provider_name: str, status_code: int = 0, error_text: str = ""):
        """Record a failed call. If 429/5xx, cool down the provider.

        If 401/403/402 (auth/quota error) or the error text carries auth
        failure signatures, cool down for AUTH_ERROR_COOLDOWN_SECONDS —
        a revoked key will not fix itself in 60 seconds.
        """
        self._call_counts[provider_name] += 1
        self._fail_counts[provider_name] += 1
        _err_lower = (error_text or "").lower()
        _is_auth = status_code in (401, 402, 403) or any(
            sig in _err_lower for sig in (
                "unauthorized", "forbidden", "authorization failed",
                "invalid api key", "not set — provider key missing",
                "payment required", "payment_required",
            )
        )
        if _is_auth:
            self._cooldown_until[provider_name] = time.time() + self.AUTH_ERROR_COOLDOWN_SECONDS
            logger.error(
                "provider_penalty_box name=%s status=%d cooldown_until=%.0fs reason=auth_or_quota_error: %s",
                provider_name, status_code, self.AUTH_ERROR_COOLDOWN_SECONDS, error_text[:120],
            )
        elif status_code == 429 or status_code >= 500:
            self._cooldown_until[provider_name] = time.time() + self.COOLDOWN_SECONDS
            logger.warning(
                "provider_cooldown name=%s status=%d cooldown_until=%.0fs reason=rate_limited_or_server_error",
                provider_name, status_code, self.COOLDOWN_SECONDS,
            )
        elif "timeout" in _err_lower or "timed out" in _err_lower:
            # Timeouts previously got NO cooldown (status 0) — a slow/hanging
            # provider was re-tried on every call, burning 60-90s each time.
            # Cool down for 2 minutes so traffic moves on.
            self._cooldown_until[provider_name] = time.time() + self.TIMEOUT_COOLDOWN_SECONDS
            logger.warning(
                "provider_cooldown name=%s cooldown_until=%.0fs reason=timeout: %s",
                provider_name, self.TIMEOUT_COOLDOWN_SECONDS, error_text[:120],
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

# ── Per-Provider RPM Budgets (2026-09 water-filling) ─────────────────
# User capacity plan: Groq 30 RPM, Mistral 60 RPM, NVIDIA 40 RPM
# (130 RPM aggregate). Uses the SAME shared sliding-window tracker as
# SmartRouter (app/core/smart_router.ProviderHealthTracker) so both
# routing layers draw from ONE budget per provider. Limits are
# env-driven there: GROQ_RPM / MISTRAL_RPM / NVIDIA_RPM / GOOGLE_RPM /
# CEREBRAS_RPM (0 = disabled) / AI21_RPM (0 = disabled).
try:
    from app.core.smart_router import (
        ModelProvider as _SRProvider,
        ProviderHealthTracker as _SRTracker,
    )
    _SR_AVAILABLE = True
except Exception:
    _SR_AVAILABLE = False

_SR_TRACKER = None


def _get_sr_tracker():
    """Get the shared SmartRouter health tracker (BC-008 safe)."""
    global _SR_TRACKER
    if _SR_TRACKER is None and _SR_AVAILABLE:
        _SR_TRACKER = _SRTracker()
    return _SR_TRACKER


# pipeline provider name -> smart_router ModelProvider (None = ungated)
_RPM_NAME_MAP = {
    "groq": _SRProvider.GROQ if _SR_AVAILABLE else None,
    "mistral": _SRProvider.MISTRAL if _SR_AVAILABLE else None,
    "nvidia": _SRProvider.NVIDIA if _SR_AVAILABLE else None,
    "cerebras": _SRProvider.CEREBRAS if _SR_AVAILABLE else None,
    "gemini": _SRProvider.GOOGLE if _SR_AVAILABLE else None,
}

# PRIMARY pool = the big free tiers (drained in parallel, water-filling).
# Reserves (cerebras/gemini/aion) only when no primary has capacity.
_PRIMARY_PIPELINE_PROVIDERS = {"groq", "mistral", "nvidia"}


def _rpm_remaining(provider_name: str) -> int:
    """Remaining RPM slots for a provider in the shared sliding window."""
    tracker = _get_sr_tracker()
    if tracker is None:
        return 1  # tracker unavailable — don't gate, legacy behavior
    p = _RPM_NAME_MAP.get(provider_name)
    if p is None:
        return 999  # aion — self-limited internally (15 RPM, 20K TPD)
    return tracker.get_provider_rpm_available(p)


def _record_rpm_use(provider_name: str) -> None:
    """Record one call into the shared per-provider sliding window."""
    tracker = _get_sr_tracker()
    if tracker is None:
        return
    p = _RPM_NAME_MAP.get(provider_name)
    if p is None:
        return
    import threading as _threading
    lock = tracker._get_provider_lock(p)
    with lock:
        tracker._get_provider_timestamps(p).append(time.time())


def _provider_disabled(provider_name: str) -> bool:
    """True when the provider is hard-disabled via its RPM limit = 0.

    Hard-disabled providers are NEVER called — not as primary, not as
    reserve, not even when every other window is full. This is what keeps
    a dead/revoked key (e.g. NVIDIA 2026-09-10) from burning 90s timeouts
    inside every LLM call. Re-enable purely via env: NVIDIA_RPM=40.
    """
    if not _SR_AVAILABLE:
        return False
    p = _RPM_NAME_MAP.get(provider_name)
    if p is None:
        return False  # aion etc. — self-limited internally, keep enabled
    from app.core.smart_router import PROVIDER_RPM_LIMITS
    return PROVIDER_RPM_LIMITS.get(p, 30) <= 0


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
    ticket_id: str = "",
) -> str:
    """Single LLM call — water-filling routing (2026-09).

    PRIMARY pool (drained in parallel by remaining capacity):
      Groq 30 RPM, Mistral 60 RPM (1 RPS), NVIDIA 40 RPM = 130 RPM.
      Per call, providers are reordered by MOST remaining RPM capacity
      in the shared 60s sliding window (SmartRouter tracker) — this
      self-balances traffic 23%/46%/31% and maximises throughput.
    RESERVE pool (only when no primary has capacity):
      Cerebras (disabled via CEREBRAS_RPM=0), Gemini (15 RPM), Aion.
    Task-size hints (light→groq-first, hard→quality order) are kept as
    tie-breakers; capacity always dominates.
    """
    global _call_count, _total_errors

    await _wait_for_rate_limit()
    _call_count += 1
    call_id = _call_count
    _check_pipeline_timeout()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # ── NODE-BASED ROUTING: pick provider based on token size ──
    #
    # IMPORTANT (verified live 2026-08-12):
    #   - Groq llama-3.1-8b-instant: ~0.5-1s/call   (user-validated for ALL tasks)
    #   - Cerebras gpt-oss-120b:    ~1-2s/call       (great quality, fast)
    #   - Mistral Small 4:          ~2-3s/call
    #   - NVIDIA GLM-5.2:           ~58s/call (WARM) / 90s+ COLD  ← BLOCKING
    #
    # NVIDIA is intentionally LAST in runtime fallback chains.
    # At 58s/call, routing a ticket to NVIDIA makes the 5-10 LLM calls in the
    # pipeline take 5-10 MINUTES → Render HTTP timeout → ticket escalates
    # instead of resolving. NVIDIA is still used for:
    #   - BUILDER tier (onboarding agent creation, latency acceptable)
    #   - Last-resort fallback when all other providers are 429'd
    if max_tokens <= 150:
        # Light task → Groq (fastest)
        preferred_order = [
            ("groq", _call_groq_direct),
            ("cerebras", _call_cerebras_direct),
            ("mistral", _call_mistral_direct),
            ("gemini", _call_gemini_direct),
            ("aion", _call_aion_direct),
            ("nvidia", _call_nvidia_direct),
        ]
    elif max_tokens <= 300:
        # Medium task → Groq (best balance of speed + quality, user-validated)
        preferred_order = [
            ("groq", _call_groq_direct),
            ("cerebras", _call_cerebras_direct),
            ("mistral", _call_mistral_direct),
            ("gemini", _call_gemini_direct),
            ("aion", _call_aion_direct),
            ("nvidia", _call_nvidia_direct),
        ]
    else:
        # Hard task → Cerebras GPT-OSS 120B (best fast reasoning, 1-2s/call)
        # NVIDIA GLM-5.2 was preferred here but takes 58s/call → pipeline timeout
        preferred_order = [
            ("cerebras", _call_cerebras_direct),
            ("groq", _call_groq_direct),
            ("mistral", _call_mistral_direct),
            ("gemini", _call_gemini_direct),
            ("aion", _call_aion_direct),
            ("nvidia", _call_nvidia_direct),
        ]

    # ── TRY: water-filling across primaries, then reserves ──
    pool = get_provider_pool()

    def _order_candidates(cands):
        """Primaries first (most remaining RPM capacity wins, stable for
        ties so task-size speed preferences survive), then reserves.
        Hard-disabled providers (RPM limit = 0) are removed entirely —
        they are never tried, even as last resort."""
        cands = [(n, f) for n, f in cands if not _provider_disabled(n)]
        primaries = [(n, f) for n, f in cands if n in _PRIMARY_PIPELINE_PROVIDERS]
        reserves = [(n, f) for n, f in cands if n not in _PRIMARY_PIPELINE_PROVIDERS]
        primaries.sort(key=lambda nf: -_rpm_remaining(nf[0]))
        reserves.sort(key=lambda nf: -_rpm_remaining(nf[0]))
        return primaries + reserves

    for provider_name, provider_fn in _order_candidates(preferred_order):
        # Hard-disabled providers (RPM limit = 0 via env) are never called.
        if _provider_disabled(provider_name):
            continue

        # Check if provider is cooling down (429)
        if not pool._is_available(provider_name, []):
            continue

        # RPM budget gate: skip providers whose sliding window is full.
        # If EVERY candidate is full, wait briefly and proceed anyway —
        # the window rolls forward and a 429 just triggers cooldown.
        if _rpm_remaining(provider_name) <= 0:
            others = [
                n for n, _ in preferred_order
                if not _provider_disabled(n) and _rpm_remaining(n) > 0 and pool._is_available(n, [])
            ]
            if others:
                continue
            logger.info("LLM call #%d: all RPM windows full — brief wait", call_id)
            await asyncio.sleep(2.0)

        # Record this call into the shared per-provider RPM window
        _record_rpm_use(provider_name)

        try:
            result = await provider_fn(messages, temperature, max_tokens, call_id)
            if result and len(result.strip()) > 0:
                pool.record_success(provider_name)
                logger.info("LLM call #%d: %s SUCCESS (%d chars, step=%s, tokens=%d)", 
                           call_id, provider_name, len(result), step_type, max_tokens)
                return result
            pool.record_failure(provider_name, status_code=0, error_text="empty response")
            logger.warning("LLM call #%d: %s returned empty response", call_id, provider_name)
        except RuntimeError as exc:
            status_code = 0
            msg = str(exc)
            for part in msg.split():
                if part.isdigit():
                    status_code = int(part)
                    break
            pool.record_failure(provider_name, status_code=status_code, error_text=str(exc))
            logger.warning("LLM call #%d: %s failed (status=%d): %s", 
                          call_id, provider_name, status_code, str(exc)[:100])
        except Exception as exc:
            pool.record_failure(provider_name, status_code=0, error_text=str(exc))
            logger.warning("LLM call #%d: %s error: %s", call_id, provider_name, str(exc)[:100])

    # ── LAST RESORT: Smart Router (LiteLLM — 11 models) ──
    try:
        smart_result = await _call_smart_router(messages, temperature, max_tokens, call_id, step_type)
        if smart_result and len(smart_result.strip()) > 0:
            logger.info("LLM call #%d: Smart Router SUCCESS (%d chars)", call_id, len(smart_result))
            return smart_result
    except Exception as exc:
        logger.warning("LLM call #%d: Smart Router error (%s)", call_id, str(exc)[:150])

    _total_errors += 1
    logger.error("LLM call #%d FAILED: All providers exhausted", call_id)
    raise RuntimeError("LLM call failed: all providers exhausted")


async def _call_mistral_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Mistral API call — 1 RPS (1 request per second), 500K TPM.
    
    Includes a 1-second delay between calls to respect the 1 RPS limit.
    """
    import os
    import time as _time
    import asyncio
    import httpx

    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"MISTRAL_API_KEY not set — provider key missing on this service"
        )

    # ── 1 RPS LIMITER: ensure 1 second gap between Mistral calls ──
    global _last_mistral_call_time
    if '_last_mistral_call_time' not in globals():
        _last_mistral_call_time = 0.0
    
    now = _time.time()
    elapsed = now - _last_mistral_call_time
    if elapsed < 1.0:
        wait_time = 1.0 - elapsed
        logger.info("Mistral 1 RPS: waiting %.1fs (call #%d)", wait_time, call_id)
        await asyncio.sleep(wait_time)
    
    _last_mistral_call_time = _time.time()

    payload = {
        "model": "mistral-small-latest",  # Mistral Small 4 (free tier)
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
            "https://api.mistral.ai/v1/chat/completions",
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
        raise RuntimeError(f"Mistral API error {r.status_code}: {r.text[:200]}")




async def _call_aion_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Aion Labs API call — 15 RPM, 20K TPD.
    
    Uses Aion 3.0 Mini (reasoning model).
    Best for: medium tasks when Groq/Mistral are rate-limited.
    Cuts off after 20K tokens/day (falls back to other providers).
    """
    import os
    import httpx

    api_key = os.environ.get("AION_API_KEY", "").strip()
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"AION_API_KEY not set — provider key missing on this service"
        )

    payload = {
        "model": "aion-3.0-mini",
        "messages": messages,
        "temperature": temperature,
        # Aion 3.0 Mini is a reasoning model — same truncation risk as
        # GLM-5.2 (see _call_nvidia_direct). Give it room to finish the
        # think block AND the answer; delivery strips the reasoning.
        "max_tokens": min(max(max_tokens * 3, 1200), 3000),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.aionlabs.ai/v1/chat/completions",
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
            raise RuntimeError(f"Aion API error {r.status_code}: {r.text[:200]}")
    except httpx.TimeoutException:
        raise RuntimeError(f"Aion timeout (call #{call_id})")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Aion call failed: {str(exc)[:200]}")



async def _call_gemini_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Google Gemini Flash-Lite API call — 30 RPM, 1,500 RPD.
    
    Best for: chat/new request tickets (fast, multimodal).
    """
    import os
    import httpx

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"GEMINI_API_KEY not set — provider key missing on this service"
        )

    # Convert messages to Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=payload)

        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                return text.strip()
        else:
            raise RuntimeError(f"Gemini API error {r.status_code}: {r.text[:200]}")
    except httpx.TimeoutException:
        raise RuntimeError(f"Gemini timeout (call #{call_id})")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Gemini call failed: {str(exc)[:200]}")


async def _call_groq_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Groq API call (raw HTTP, no LiteLLM dependency)."""
    import httpx

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"GROQ_API_KEY not set — provider key missing on this service"
        )

    payload = {
        # 2026-09: llama-3.1-8b-instant is RETIRED on Groq (404).
        # qwen/qwen3.6-27b is completion-verified live (see smart_router
        # MODEL_REGISTRY notes). Override with GROQ_MODEL env if needed.
        "model": os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b"),
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
        # 2026-09-10: qwen3.x is a hybrid reasoner — its <think>…</think>
        # block lands inline in content. The direct path previously returned
        # raw reasoning text to pipeline nodes (live bug 2026-09-06 pattern,
        # fixed for smart_router but not here). Strip before returning.
        try:
            from app.core.email_utils import strip_reasoning
            content = strip_reasoning(content or "")
        except Exception:
            import re as _re_strip
            content = _re_strip.sub(r"<think>[\s\S]*?</think>", "", content or "").strip()
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
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"GOOGLE_AI_API_KEY not set — provider key missing on this service"
        )

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


# ── Recovery Worker: retries stuck LLM requests after Render restart ──
# User vision: 'free render can erase the ram thats why i am saying there'
#
# When Render restarts, in-flight LLM calls lose their in-memory state.
# But their DB rows survive (status='rate_limited' or 'in_progress').
# This function finds those stuck rows and retries them.

# Track if we've already warned about the missing table (avoid log spam)
_llm_queue_table_missing_warned = False

async def _recover_stuck_llm_requests() -> None:
    """Find stuck LLM requests in DB and retry them.

    Called by background loop every 30 seconds. Finds:
      - status='rate_limited' AND next_retry_at < NOW() (rate limit expired)
      - status='in_progress' (Render died mid-call — these are stale)
      - status='pending' (never got picked up)

    Retries each via _call_nvidia_direct (which re-inserts + re-tries).
    On success → row deleted by the call. On failure → marked failed.

    If the llm_request_queue table doesn't exist yet (fresh DB), this
    function silently skips — no log spam. The table is created on first
    LLM call that needs DB-backed queueing.
    """
    global _llm_queue_table_missing_warned
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        from datetime import datetime, timezone
        import json as _json
        from sqlalchemy import text as _sql_text

        _db = SessionLocal()
        try:
            # Check if table exists first (avoid spamming errors every 30s)
            try:
                _db.execute(_sql_text("SELECT 1 FROM llm_request_queue LIMIT 1"))
            except Exception as table_check_exc:
                if "does not exist" in str(table_check_exc).lower():
                    if not _llm_queue_table_missing_warned:
                        logger.info(
                            "llm_queue_recovery: table llm_request_queue not yet created — "
                            "will be auto-created on first NVIDIA DB-backed call. Skipping recovery loop."
                        )
                        _llm_queue_table_missing_warned = True
                    return  # Table doesn't exist yet — silent skip
                raise  # Different error — re-raise

            # Find stuck rows (rate_limited with retry_at in past, OR in_progress for >5 min)
            now = datetime.now(timezone.utc)
            stuck_rows = _db.query(LLMRequestQueue).filter(
                LLMRequestQueue.status.in_(["rate_limited", "in_progress", "pending"])
            ).limit(10).all()  # cap at 10 per cycle to avoid overload

            if not stuck_rows:
                return  # nothing to recover

            # Table exists now — reset the warned flag
            _llm_queue_table_missing_warned = False

            # 2026-09-10 CRASH-LOOP FIX: rows belonging to a HARD-DISABLED
            # provider (RPM limit = 0, e.g. NVIDIA with the revoked key) are
            # marked failed immediately — never re-fired. Re-firing them was
            # re-starting 90s×3 hanging calls on EVERY backend boot, which
            # killed the free-tier service in a restart→recover→crash loop.
            _recover_fires = 0  # max real re-fires per 30s cycle
            logger.info("llm_queue_recovery: found %d stuck requests", len(stuck_rows))

            for row in stuck_rows:
                # Disabled provider (e.g. nvidia with NVIDIA_RPM=0) — drain
                # the row instead of re-firing the dead endpoint forever.
                if _provider_disabled(row.provider or ""):
                    row.status = "failed"
                    row.error_message = "provider disabled (RPM limit 0) — drained by recovery"
                    row.completed_at = now
                    _db.commit()
                    logger.warning(
                        "llm_queue_recovery: request %s drained (provider '%s' disabled)",
                        row.id[:8], row.provider,
                    )
                    continue

                # Skip rate_limited rows whose retry_at hasn't passed yet
                if row.status == "rate_limited" and row.next_retry_at and row.next_retry_at > now:
                    continue  # not yet time to retry

                # Skip if max retries exceeded
                if row.retry_count >= row.max_retries:
                    row.status = "failed"
                    row.error_message = "max retries exceeded during recovery"
                    row.completed_at = now
                    _db.commit()
                    logger.warning(
                        "llm_queue_recovery: request %s marked failed (max retries)",
                        row.id[:8],
                    )
                    continue

                # Cap REAL re-fires per cycle — each one spawns a background
                # task holding a DB session + HTTP client for minutes.
                if _recover_fires >= 2:
                    continue
                _recover_fires += 1

                # Re-try this request via its provider's direct call
                # The call will DELETE the row on success or update it on 429
                try:
                    messages = _json.loads(row.messages)
                    # Spawn as background task — don't block the recovery loop
                    import asyncio as _asyncio
                    _asyncio.create_task(
                        _retry_single_llm_request(
                            request_id=row.id,
                            messages=messages,
                            temperature=row.temperature or 0.1,
                            max_tokens=row.max_tokens or 1000,
                            call_id=row.call_id or 0,
                        )
                    )
                except Exception as retry_exc:
                    logger.warning(
                        "llm_queue_recovery_retry_failed: request=%s err=%s",
                        row.id[:8], str(retry_exc)[:200],
                    )
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("recover_stuck_llm_requests_error: %s", str(exc)[:200])


async def _retry_single_llm_request(
    request_id: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    call_id: int,
) -> None:
    """Retry a single stuck LLM request (called as background task).

    Calls _call_nvidia_direct which will:
      - INSERT a new row (since the original is being retried)
      - On success: DELETE the new row
      - On 429: UPDATE the new row + retry

    The ORIGINAL row is marked as 'completed' (retried via new call).
    """
    try:
        # Mark original row as 'in_progress' (being retried)
        _update_llm_queue_status(request_id, "in_progress")

        # Make a fresh NVIDIA call (which creates its own DB row)
        result = await _call_nvidia_direct(messages, temperature, max_tokens, call_id)

        if result:
            # Success — delete the original stuck row
            _delete_llm_queue_row(request_id)
            logger.info("llm_queue_recovery: request %s retried successfully", request_id[:8])
        else:
            _mark_llm_queue_failed(request_id, "retry returned empty result")
    except Exception as exc:
        _mark_llm_queue_failed(request_id, f"retry failed: {str(exc)[:200]}")
        logger.warning(
            "llm_queue_recovery_retry_exception: request=%s err=%s",
            request_id[:8], str(exc)[:200],
        )



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
        # Smart-router pool includes hybrid reasoners (Groq Qwen3 family)
        # that emit <think>…</think> blocks by default. Strip here so no
        # downstream consumer ever sees model reasoning (live bug
        # 2026-09-06: truncated think text was delivered as the answer).
        from app.core.email_utils import strip_reasoning
        content = strip_reasoning(content or "")
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

        model = os.environ.get("AI_LIGHT_MODEL", "groq/qwen/qwen3.6-27b")

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
    """Direct NVIDIA API call — DB-BACKED QUEUE (survives Render restarts).

    User vision: 'see u can keep that request or that queue in database ok
    well dont keep that in ram ad here as that request get solved delete that
    ok because here free render can erase the ram thats why i am saying there'

    EVERY call gets persisted to DB before the HTTP request:
      1. INSERT row (status='in_progress')
      2. Call NVIDIA API
      3. On success → DELETE row (queue drained)
      4. On 429 → UPDATE row (status='rate_limited', next_retry_at=NOW+60s)
         → sleep 60s in memory → retry (up to 3 times)
      5. On Render restart during sleep:
         - Row stays in DB with status='rate_limited'
         - Recovery worker on startup finds stuck rows + retries them
         - No lost work, no orphan requests

    This is the same DB-backed queue pattern used for tickets.
    """
    import asyncio
    import httpx
    import json as _json
    import uuid as _uuid
    from datetime import datetime, timezone, timedelta

    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"NVIDIA_API_KEY not set — provider key missing on this service"
        )

    # ── Step 1: Persist request to DB (survives Render restart) ──
    request_id = str(_uuid.uuid4())
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        _db = SessionLocal()
        try:
            _queue_row = LLMRequestQueue(
                id=request_id,
                provider="nvidia",
                model=os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-flash-0731"),
                messages=_json.dumps(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                call_id=call_id,
                status="in_progress",
                max_retries=3,
            )
            _db.add(_queue_row)
            _db.commit()
        finally:
            _db.close()
    except Exception as persist_exc:
        # Don't fail the call if DB persistence fails — just log
        logger.warning("llm_queue_persist_failed: %s", str(persist_exc)[:200])

    # 2026-09: z-ai/glm-5.2 is RETIRED on NVIDIA NIM (404/410 — model
    # removed from catalog). deepseek-ai/deepseek-v4-flash-0731 is
    # completion-verified live (see smart_router MODEL_REGISTRY notes).
    # Override with NVIDIA_MODEL env if needed.
    _nvidia_model = os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-flash-0731")

    payload = {
        "model": _nvidia_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": min(max(max_tokens * 3, 1200), 3000),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    MAX_RETRIES = 3
    RATE_LIMIT_WAIT = 60  # seconds — NVIDIA rate limit renews every 60s

    for attempt in range(MAX_RETRIES + 1):
        try:
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

                # ── SUCCESS: delete from queue (user's vision) ──
                _delete_llm_queue_row(request_id)
                return content.strip()

            if r.status_code == 429 and attempt < MAX_RETRIES:
                # ── RATE LIMIT: update DB + wait + retry (don't terminate) ──
                _update_llm_queue_rate_limited(request_id, attempt + 1, r.text[:200])
                logger.warning(
                    "NVIDIA 429 rate limit on call #%d (attempt %d/%d) — waiting %ds, then retrying",
                    call_id, attempt + 1, MAX_RETRIES, RATE_LIMIT_WAIT,
                )
                await asyncio.sleep(RATE_LIMIT_WAIT)
                # Mark back to in_progress before retry
                _update_llm_queue_status(request_id, "in_progress")
                continue

            # Non-429 error OR out of retries → mark failed in DB (keep for audit)
            _mark_llm_queue_failed(request_id, f"NVIDIA {r.status_code}: {r.text[:200]}")
            raise RuntimeError(f"NVIDIA API error {r.status_code}: {r.text[:200]}")

        except httpx.TimeoutException:
            if attempt < MAX_RETRIES:
                _update_llm_queue_rate_limited(request_id, attempt + 1, "timeout")
                logger.warning(
                    "NVIDIA timeout on call #%d (attempt %d/%d) — waiting %ds, then retrying",
                    call_id, attempt + 1, MAX_RETRIES, RATE_LIMIT_WAIT,
                )
                await asyncio.sleep(RATE_LIMIT_WAIT)
                _update_llm_queue_status(request_id, "in_progress")
                continue
            _mark_llm_queue_failed(request_id, "timeout after 3 retries")
            raise

    # Exhausted retries — mark failed in DB
    _mark_llm_queue_failed(request_id, f"exhausted {MAX_RETRIES} retries")
    raise RuntimeError(f"NVIDIA API: exhausted {MAX_RETRIES} retries on rate limit")


# ── DB queue helpers (small + surgical) ─────────────────────────────

def _delete_llm_queue_row(request_id: str) -> None:
    """Delete a completed request from the queue (user's vision: 'as that request
    get solved delete that')."""
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        _db = SessionLocal()
        try:
            _db.query(LLMRequestQueue).filter(LLMRequestQueue.id == request_id).delete()
            _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("llm_queue_delete_failed: %s", str(exc)[:200])


def _update_llm_queue_rate_limited(request_id: str, retry_count: int, error: str) -> None:
    """Mark a request as rate_limited with next_retry_at = NOW + 60s.

    If Render restarts during the 60s sleep, the row stays here with
    next_retry_at in the past. Recovery worker picks it up on startup.
    """
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        from datetime import datetime, timezone, timedelta
        _db = SessionLocal()
        try:
            row = _db.query(LLMRequestQueue).filter(LLMRequestQueue.id == request_id).first()
            if row:
                row.status = "rate_limited"
                row.retry_count = retry_count
                row.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=60)
                row.error_message = error[:500]
                _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("llm_queue_update_rate_limited_failed: %s", str(exc)[:200])


def _update_llm_queue_status(request_id: str, status: str) -> None:
    """Update status (e.g. back to in_progress before retry)."""
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        _db = SessionLocal()
        try:
            row = _db.query(LLMRequestQueue).filter(LLMRequestQueue.id == request_id).first()
            if row:
                row.status = status
                _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("llm_queue_update_status_failed: %s", str(exc)[:200])


def _mark_llm_queue_failed(request_id: str, error: str) -> None:
    """Mark a request as failed (kept in DB for audit, not deleted)."""
    try:
        from database.base import SessionLocal
        from database.models.core import LLMRequestQueue
        from datetime import datetime, timezone
        _db = SessionLocal()
        try:
            row = _db.query(LLMRequestQueue).filter(LLMRequestQueue.id == request_id).first()
            if row:
                row.status = "failed"
                row.error_message = error[:500]
                row.completed_at = datetime.now(timezone.utc)
                _db.commit()
        finally:
            _db.close()
    except Exception as exc:
        logger.warning("llm_queue_mark_failed_failed: %s", str(exc)[:200])


async def _call_cerebras_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Cerebras API call (raw HTTP, no LiteLLM dependency)."""
    import httpx

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"CEREBRAS_API_KEY not set — provider key missing on this service"
        )

    payload = {
        "model": "gpt-oss-120b",
        "messages": messages,
        "temperature": temperature,
        # gpt-oss is a reasoning model — via the raw Cerebras API its
        # analysis lands inline in content and it will burn the whole
        # caller budget thinking (live bug 2026-09-06: customers got
        # truncated reasoning instead of answers). reasoning_effort=low
        # shortens the thinking; the 3x budget leaves room for the answer.
        "reasoning_effort": "low",
        "max_tokens": min(max(max_tokens * 3, 1200), 3000),
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


