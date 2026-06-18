"""
PARWA Pipeline V2 — Shared LLM Client

Direct NVIDIA API (Llama 3.1 8B) via httpx.
40 RPM rate limit → 1.5s minimum between calls.
Retry with backoff on 429/5xx.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

from app.core.parwa_pipeline.config import NVIDIA_API_KEY, NVIDIA_API_BASE, NVIDIA_MODEL

logger = logging.getLogger("parwa.pipeline.llm")

# ── Rate Limiter (40 RPM → 1.5s between calls) ──────────────────

_last_call_time: float = 0.0
_rate_lock: asyncio.Lock = None
MIN_CALL_INTERVAL: float = 2.0  # 30 RPM safe (under 40 limit with margin)
MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 3.0  # seconds, exponential backoff

# ── Stats ───────────────────────────────────────────────────────

_call_count: int = 0
_total_tokens: int = 0
_total_errors: int = 0


async def _get_rate_lock() -> asyncio.Lock:
    global _rate_lock
    if _rate_lock is None:
        _rate_lock = asyncio.Lock()
    return _rate_lock


async def _wait_for_rate_limit():
    """Enforce minimum interval between calls (40 RPM)."""
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
    """Raise if the pipeline has exceeded its hard timeout.

    This prevents a runaway quality loop or rate-limit backoff from
    consuming unlimited time.  The caller should catch RuntimeError.
    """
    if _call_start_time and (time.monotonic() - _call_start_time) > PIPELINE_HARD_TIMEOUT:
        raise RuntimeError(
            f"Pipeline hard timeout ({PIPELINE_HARD_TIMEOUT:.0f}s) exceeded — "
            f"aborting to prevent hang"
        )


async def llm_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Single LLM call to NVIDIA API with rate limiting and retries.

    Returns the response text. Raises RuntimeError if all retries fail.
    """
    global _call_count, _total_tokens, _total_errors

    await _wait_for_rate_limit()

    _call_count += 1
    call_id = _call_count

    # Hard-timeout guard — fail fast instead of hanging forever
    _check_pipeline_timeout()

    url = f"{NVIDIA_API_BASE}/chat/completions"
    payload = {
        "model": NVIDIA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload, headers=headers)

            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > 15000:
                logger.warning("LLM call #%d slow: %dms", call_id, int(elapsed_ms))

            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"].strip()
                tokens = data.get("usage", {}).get("total_tokens", 0)
                _total_tokens += tokens

                if call_id % 10 == 0:
                    logger.info(
                        "LLM call #%d: %dms, %d tokens (cumulative: %d)",
                        call_id, int(elapsed_ms), tokens, _total_tokens,
                    )
                return content

            elif r.status_code == 429:
                retry_after = float(r.headers.get("retry-after", RETRY_BASE_DELAY * attempt))
                last_error = f"429 rate limit, retrying after {retry_after}s"
                logger.warning("LLM call #%d: 429, retry %d/%d after %.1fs", call_id, attempt, MAX_RETRIES, retry_after)
                await asyncio.sleep(retry_after)

            else:
                last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                logger.warning("LLM call #%d: %s", call_id, last_error)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BASE_DELAY * attempt)

        except httpx.TimeoutException:
            last_error = "Request timed out"
            logger.warning("LLM call #%d: timeout, retry %d/%d", call_id, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BASE_DELAY * attempt)

        except Exception as e:
            last_error = str(e)
            logger.warning("LLM call #%d: error '%s', retry %d/%d", call_id, e, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BASE_DELAY * attempt)

    _total_errors += 1
    logger.error("LLM call #%d FAILED after %d retries: %s", call_id, MAX_RETRIES, last_error)
    raise RuntimeError(f"LLM call failed after {MAX_RETRIES} retries: {last_error}")


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
    _call_start_time = 0.0  # also reset timeout tracking


def parse_confidence(text: str, default: float = 0.7) -> float:
    """Extract a 0.0-1.0 confidence number from LLM response text."""
    match = re.search(r"(\d+\.?\d*)", text.strip())
    if match:
        val = float(match.group(1))
        if val > 1:
            val = val / 100
        return max(0.0, min(1.0, val))
    return default