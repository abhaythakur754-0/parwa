"""
PARWA Pipeline V2 — Shared LLM Client

Production LLM routing: water-filling over the 3 free-forever backbone
providers, then Smart Router as last resort.

Backbone (user directive 2026-09: ONLY these — everything else is
daily-capped or dead):
  Groq 30 RPM + Mistral 60 RPM + NVIDIA 40 RPM = 130 RPM
  (~7 tickets/min, ~10k tickets/day ceiling)

Routing (capacity dominates; task-size hints are tie-breakers):
  LIGHT / MEDIUM / HEAVY: Groq → Mistral → NVIDIA (same pool)
  BUILDER:                Groq (onboarding agent creation)
  GUARDRAIL:              Groq GPT-OSS Safeguard 20B

Cerebras / Google / Aion / OpenRouter are REMOVED from the runtime chain
(daily caps / dead keys / 402 payment). Smart Router remains last resort
— its GOOGLE/CEREBRAS/AI21 RPM limits are 0, so it can only ever land
on the backbone too. NVIDIA stays hard-disabled (NVIDIA_RPM=0) until a
valid nvapi-* key is set on the service.
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
    across Groq, Mistral and NVIDIA instead of hammering one provider.

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
        self._last_error: Dict[str, str] = {}  # provider → last error summary
        # 2026-09-18 live bug: Mistral 429'd on 25/25 calls but each 429
        # only cooled it down 60s — after a minute it was tried first again
        # (60 RPM wins the water-filling sort), failed again, and every
        # call in the ticket paid a dead-provider attempt. Escalate the
        # cooldown for CONSECUTIVE 429/5xx failures: 60s → 120s → 240s →
        # 480s → 900s (cap). One success resets the streak.
        self._consec_429: Dict[str, int] = defaultdict(int)
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
        self._consec_429[provider_name] = 0
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
        # 2026-09-18: remember WHY a provider fails — /debug/provider-pool
        # shows it, so outages (404 model rotation, 429 daily quota, 401
        # revoked key) are diagnosable from one endpoint instead of
        # guessing from Render logs.
        self._last_error[provider_name] = (
            f"[{status_code or 'err'}] {(error_text or 'unknown')[:160]}"
        )
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
            self._consec_429[provider_name] += 1
            streak = self._consec_429[provider_name]
            cooldown = min(
                self.COOLDOWN_SECONDS * (2 ** min(streak - 1, 4)),
                self.AUTH_ERROR_COOLDOWN_SECONDS,
            )
            self._cooldown_until[provider_name] = time.time() + cooldown
            logger.warning(
                "provider_cooldown name=%s status=%d cooldown_until=%.0fs consecutive_failures=%d reason=rate_limited_or_server_error",
                provider_name, status_code, cooldown, streak,
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
                "last_error": self._last_error.get(name, ""),
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
# env-driven there: GROQ_RPM (30) / MISTRAL_RPM (60) / NVIDIA_RPM (40 once
# a valid key lands; 0 = hard-disabled) — the 3-provider backbone.
# GOOGLE_RPM / CEREBRAS_RPM / AI21_RPM default 0 = disabled (removed from
# the rotation 2026-09: daily caps / dead keys / 402 payment).
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
# Backbone only (2026-09): cerebras/gemini removed from the chain.
_RPM_NAME_MAP = {
    "groq": _SRProvider.GROQ if _SR_AVAILABLE else None,
    "mistral": _SRProvider.MISTRAL if _SR_AVAILABLE else None,
    "nvidia": _SRProvider.NVIDIA if _SR_AVAILABLE else None,
}

# The one and only pool — drained in parallel by remaining capacity
# (water-filling). No reserve pool (removed 2026-09).
_PRIMARY_PIPELINE_PROVIDERS = {"groq", "mistral", "nvidia"}


def _rpm_remaining(provider_name: str) -> int:
    """Remaining RPM slots for a provider in the shared sliding window."""
    tracker = _get_sr_tracker()
    if tracker is None:
        return 1  # tracker unavailable — don't gate, legacy behavior
    p = _RPM_NAME_MAP.get(provider_name)
    if p is None:
        return 0  # unknown provider — fail closed, never call
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
        return True  # unknown provider — fail closed, never call
    from app.core.smart_router import PROVIDER_RPM_LIMITS
    return PROVIDER_RPM_LIMITS.get(p, 30) <= 0


MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 2.0

# ── Backbone ordering (2026-09-18 live-log fix) ──────────────────────
# Groq/Mistral answer in ~1-5s; NVIDIA needs ~60-90s/call. The old
# water-filling sorted ALL providers by remaining RPM, so a fresh NVIDIA
# window (40 RPM) outranked Groq (30 RPM) and whole tickets were routed
# to the slow provider → "NVIDIA timeout … waiting 60s" retry storms →
# 4.5-minute tickets (Render logs 2026-09-18 08:35Z). Fast providers
# water-fill among themselves; NVIDIA is a LAST RESORT, tried only when
# every fast provider failed / is cooling down / is RPM-full.
FAST_PROVIDERS = ("groq", "mistral")


def _order_backbone_candidates(cands):
    """Order LLM provider candidates for one llm_call attempt.

    Fast providers (groq/mistral) come first, ordered by most remaining
    RPM capacity (water-filling). Slow providers (nvidia) are appended
    AFTER every fast one regardless of capacity. Hard-disabled providers
    (RPM limit = 0) are removed entirely — never tried, even as last
    resort.
    """
    fast = [(n, f) for n, f in cands
            if n in FAST_PROVIDERS and not _provider_disabled(n)]
    fast.sort(key=lambda nf: -_rpm_remaining(nf[0]))
    slow = [(n, f) for n, f in cands
            if n not in FAST_PROVIDERS and not _provider_disabled(n)]
    return fast + slow

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


def _status_from_error(msg: str) -> int:
    """Extract the HTTP status from a provider error message.

    2026-09-18 live bug: the old word-by-word isdigit() check NEVER matched
    because callers raise f"Mistral API error 429: ..." — the token is
    "429:" WITH a colon, so status stayed 0 and NO 429 cooldown was ever
    applied to any provider (live proof: Mistral 25 calls / 25 failures /
    zero cooldowns in /debug/provider-pool). Parse "429:" correctly.
    """
    m = re.search(r"\b(\d{3})\b", str(msg))
    return int(m.group(1)) if m else 0


async def llm_call(
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str = "",
    step_type: str = "",
    ticket_id: str = "",
) -> str:
    """Single LLM call — water-filling routing (2026-09).

    Backbone pool (drained in parallel by remaining capacity):
      Groq 30 RPM, Mistral 60 RPM (1 RPS), NVIDIA 40 RPM = 130 RPM.
      Per call, providers are reordered by MOST remaining RPM capacity
      in the shared 60s sliding window (SmartRouter tracker) — this
      self-balances traffic and maximises throughput.
    Task-size hints (light→groq-first) are kept as tie-breakers;
    capacity always dominates. Smart Router = last resort only.
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

    # ── BACKBONE ONLY (2026-09 user directive): Groq + Mistral + NVIDIA ──
    #
    # Cerebras/Google/Aion removed from the chain entirely (daily caps /
    # dead keys / 402). Task-size tiers collapsed — capacity water-filling
    # dominates anyway; order below is just the tie-breaker preference.
    #
    # NVIDIA is LAST (see FAST_PROVIDERS / _order_backbone_candidates):
    # ~58s/call (warm) / 90s+ (cold). Routing a ticket to NVIDIA
    # mid-pipeline makes 5-10 calls take 5-10 MINUTES → Render HTTP
    # timeout → ticket escalates. It also stays hard-disabled (RPM=0) via
    # _provider_disabled until NVIDIA_RPM=40 + a valid key are set.
    preferred_order = [
        ("groq", _call_groq_direct),
        ("mistral", _call_mistral_direct),
        ("nvidia", _call_nvidia_direct),
    ]

    # ── TRY: fast water-filling first, NVIDIA strictly last ──
    pool = get_provider_pool()

    for provider_name, provider_fn in _order_backbone_candidates(preferred_order):
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
            msg = str(exc)
            status_code = _status_from_error(msg)
            pool.record_failure(provider_name, status_code=status_code, error_text=msg)
            logger.warning("LLM call #%d: %s failed (status=%d): %s", 
                          call_id, provider_name, status_code, str(exc)[:100])
        except Exception as exc:
            # str(httpx.TimeoutException) is EMPTY — record the TYPE so
            # /debug/provider-pool never shows "[err] unknown" again.
            _err = f"{type(exc).__name__}: {exc or 'no message'}"
            pool.record_failure(provider_name, status_code=0, error_text=_err)
            logger.warning("LLM call #%d: %s error: %s", call_id, provider_name, _err[:100])

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


# ── Groq model fallback chain (2026-09-18 live fix) ─────────────────
# THE root cause of the 4.5-minute tickets: Groq rotated their model
# (qwen3.6-27b → 404 model_not_found), every Groq call failed instantly,
# and all traffic fell to NVIDIA (~60-90s/call) → retry storms.
# Groq rotates models without notice, so: try candidates in order, on
# 404 model_not_found move to the next one, and CACHE the winner so the
# hot path never pays the fallback cost again.
GROQ_MODEL_CANDIDATES = [
    "qwen/qwen3.8-27b",      # live 2026-09-18 via /debug/llm-test model list
    "openai/gpt-oss-20b",    # live in the same list — fast, verified tier
    "openai/gpt-oss-120b",   # stronger fallback, still fast on Groq
    "groq/compound-mini",    # last resort compound system
]
_groq_resolved_model: Optional[str] = None


async def _call_groq_direct(messages: list, temperature: float, max_tokens: int, call_id: int) -> str:
    """Direct Groq API call (raw HTTP, no LiteLLM dependency).

    2026-09-18: self-healing against Groq model rotation — if the
    current model 404s (model_not_found), the next candidate is tried
    and the working model is cached for subsequent calls.
    """
    import httpx

    global _groq_resolved_model

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        # 2026-09: fail LOUDLY — silent "" was indistinguishable
        # from a real failure, hiding missing env vars on Render.
        raise RuntimeError(
            f"GROQ_API_KEY not set — provider key missing on this service"
        )

    # Candidate order: explicit env override FIRST (so GROQ_MODEL still
    # wins when valid), then the last-resolved working model, then the
    # default chain.
    candidates: List[str] = []
    _env_model = os.environ.get("GROQ_MODEL", "").strip()
    if _env_model:
        candidates.append(_env_model)
    if _groq_resolved_model and _groq_resolved_model not in candidates:
        candidates.append(_groq_resolved_model)
    for _cand in GROQ_MODEL_CANDIDATES:
        if _cand not in candidates:
            candidates.append(_cand)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for model_id in candidates:
            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            )

            if r.status_code == 200:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                # 2026-09-10: qwen3.x is a hybrid reasoner — its <think>…</think>
                # block lands inline in content. The direct path previously returned
                # raw reasoning text to pipeline nodes (live bug 2026-09-06 pattern,
                # fixed for smart_router but not here). Strip before returning.
                try:
                    from app.core.email_utils import strip_reasoning
                    content = strip_reasoning(content)
                except Exception:
                    import re as _re_strip
                    content = _re_strip.sub(r"<think>[\s\S]*?(</think>|$)", "", content).strip()
                global _total_tokens
                _total_tokens += data.get("usage", {}).get("total_tokens", 0)
                if _groq_resolved_model != model_id:
                    logger.info(
                        "Groq model resolved: %s (was %s) — cached for future calls",
                        model_id, _groq_resolved_model,
                    )
                _groq_resolved_model = model_id
                return content.strip()

            last_error = f"Groq API error {r.status_code}: {r.text[:200]}"
            # 404 model_not_found → Groq rotated the model again — try the
            # next candidate. Everything else (429, 5xx, auth) fails now;
            # the provider pool cooldown logic handles those.
            if r.status_code == 404 and "model" in r.text.lower():
                logger.warning(
                    "Groq model %s NOT FOUND (rotated?) — trying next candidate",
                    model_id,
                )
                continue
            raise RuntimeError(last_error)

    raise RuntimeError(last_error or "Groq API error: all model candidates failed")


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

# Request IDs currently being re-fired by a previous recovery cycle.
# Calls take minutes; without this guard the 30s loop re-fired the SAME
# row again and again → duplicate NVIDIA calls → 429 storm (live logs
# 2026-09-18: "found 10 stuck requests" every 30s).
_recovery_inflight: set = set()

async def _recover_stuck_llm_requests() -> None:
    """Find stuck LLM requests in DB and retry them.

    Called by background loop every 30 seconds. Finds:
      - status='rate_limited' AND next_retry_at < NOW() (rate limit expired)
      - status='in_progress' (Render died mid-call — these are stale)
      - status='pending' (never got picked up)

    Retries each via _call_nvidia_direct (which re-inserts + re-tries).
    On success → row deleted by the call. On failure → marked failed.

    2026-09-18 live fix: rows that are HEALTHY and simply in-flight
    (NVIDIA calls take 60-90s) were being re-flagged as "stuck" every
    30s cycle because the query had NO time filter. Now only rows that
    are genuinely stale are touched:
      - rate_limited: only when next_retry_at has passed
      - in_progress / pending: only when older than 5 minutes

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

            # Find stuck rows — with TIME filters (see docstring above).
            now = datetime.now(timezone.utc)
            from datetime import timedelta as _timedelta
            from sqlalchemy import or_ as _or, and_ as _and
            _stale_cutoff = now - _timedelta(minutes=5)
            stuck_rows = _db.query(LLMRequestQueue).filter(
                _or(
                    _and(
                        LLMRequestQueue.status == "rate_limited",
                        _or(
                            LLMRequestQueue.next_retry_at.is_(None),
                            LLMRequestQueue.next_retry_at < now,
                        ),
                    ),
                    _and(
                        LLMRequestQueue.status == "in_progress",
                        LLMRequestQueue.created_at.isnot(None),
                        LLMRequestQueue.created_at < _stale_cutoff,
                    ),
                    _and(
                        LLMRequestQueue.status == "pending",
                        LLMRequestQueue.created_at.isnot(None),
                        LLMRequestQueue.created_at < _stale_cutoff,
                    ),
                )
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

                # Only NVIDIA writes rows to this queue today — a stray row
                # from another provider can't be retried via NVIDIA. Drain it.
                if (row.provider or "") != "nvidia":
                    row.status = "failed"
                    row.error_message = f"recovery drain: unknown provider '{row.provider}'"
                    row.completed_at = now
                    _db.commit()
                    continue

                # In-flight guard: a re-fire from an earlier cycle is still
                # running (calls take minutes). Never double-fire.
                if row.id in _recovery_inflight:
                    continue

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
                    _recovery_inflight.add(row.id)
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
        # 2026-09-18: httpx.TimeoutException's str() is EMPTY — Render logs
        # showed "err=" with nothing after it. Always include the TYPE.
        _err = (f"{type(exc).__name__}: {exc or 'no message'}")[:200]
        _mark_llm_queue_failed(request_id, f"retry failed: {_err}")
        logger.warning(
            "llm_queue_recovery_retry_exception: request=%s err=%s",
            request_id[:8], _err,
        )
    finally:
        _recovery_inflight.discard(request_id)



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
      4. On 429 → UPDATE row (status='rate_limited', next_retry_at=NOW+15s)
         → sleep 15s in memory → retry (up to 2 times); on timeout →
         fail fast (no wait)
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
                model=os.environ.get("NVIDIA_MODEL", "z-ai/glm-5.3-flash"),
                messages=_json.dumps(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                call_id=call_id,
                status="in_progress",
                max_retries=2,
            )
            _db.add(_queue_row)
            _db.commit()
        finally:
            _db.close()
    except Exception as persist_exc:
        # Don't fail the call if DB persistence fails — just log
        logger.warning("llm_queue_persist_failed: %s", str(persist_exc)[:200])

    # 2026-09 (revalidated with real nvapi key): nemotron-70b 404s on new
    # accounts; z-ai/glm-5.3-flash verified live (~2.4s, clean content).
    # GLM may emit <think> — stripped on the success path below (same guard
    # as groq). Override with NVIDIA_MODEL env if needed.
    _nvidia_model = os.environ.get("NVIDIA_MODEL", "z-ai/glm-5.3-flash")

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

    # 2026-09-18 live-tuning: NVIDIA is a LAST-RESORT provider. The old
    # 60s wait × 3 retries inside this function could block ONE pipeline
    # node for ~6 minutes (Render logs: "NVIDIA timeout … waiting 60s"
    # ×3 back-to-back) while the ticket burned wall-clock. Fast-fail
    # instead — llm_call() falls through to the next provider / Smart
    # Router, so the ticket survives without the multi-minute stall.
    MAX_RETRIES = 2
    RATE_LIMIT_WAIT = 15  # seconds — short 429 backoff, then fall through
    _NVIDIA_HTTP_TIMEOUT = 45.0  # was 60s — bound the hang window

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_NVIDIA_HTTP_TIMEOUT) as client:
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

                # 2026-09: nemotron (Llama-3.1 family) is a hybrid reasoner —
                # strip <think>…</think> (and an unterminated think from a
                # truncated response) so reasoning never reaches nodes.
                content = re.sub(r"<think>[\s\S]*?(</think>|$)", "", content or "").strip()
                if not content:
                    _delete_llm_queue_row(request_id)
                    raise RuntimeError("NVIDIA returned empty content after <think> strip")

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
            # 2026-09-18: NO in-function sleep-retry on timeout — a hanging
            # provider rarely recovers inside a short window, and every 60s
            # wait stalled the whole ticket (live retry-storm logs). Fail
            # fast: the provider pool benches NVIDIA for 120s
            # (TIMEOUT_COOLDOWN_SECONDS) and llm_call() moves to the next
            # provider / Smart Router.
            _mark_llm_queue_failed(
                request_id,
                f"timeout after {attempt + 1} attempt(s) — fast-fail, no wait",
            )
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


