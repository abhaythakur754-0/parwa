"""
PARWA Pipeline V2 — Shared LLM Client

Single place for all LLM calls across all 8 nodes.
Uses persistent z-ai SDK proxy (Node.js) for fast sequential calls.
Fallback chain: z-ai proxy → z-ai CLI → litellm → httpx direct.

Every node imports from here — no duplicate LLM call code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("parwa.pipeline.llm")

# ── z-ai Proxy Backend (persistent Node.js process) ─────────────

_proxy_process: subprocess.Popen = None
_proxy_lock: asyncio.Lock = None
_proxy_call_count: int = 0
_proxy_total_tokens: int = 0

PROXY_SCRIPT = "/home/z/my-project/parwa/backend/scripts/llm_proxy.js"


def _ensure_proxy_started():
    """Start the persistent z-ai proxy if not running."""
    global _proxy_process, _proxy_lock

    if _proxy_process is not None and _proxy_process.poll() is None:
        return  # Already running

    logger.info("Starting z-ai LLM proxy (bun)...")
    _proxy_process = subprocess.Popen(
        ["bun", "run", PROXY_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd="/home/z/my-project/parwa/backend/scripts",
    )

    # Wait for ready signal
    ready_line = _proxy_process.stderr.readline()
    if "LLM_PROXY_READY" not in ready_line:
        logger.error("z-ai proxy failed to start: %s", ready_line)
        _proxy_process = None
        raise RuntimeError("z-ai proxy failed to start")

    logger.info("z-ai LLM proxy ready")


async def _zai_proxy_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Call LLM via persistent z-ai proxy. No startup overhead per call."""
    global _proxy_call_count, _proxy_total_tokens, _proxy_lock

    _ensure_proxy_started()
    if _proxy_lock is None:
        _proxy_lock = asyncio.Lock()

    _proxy_call_count += 1
    call_id = str(_proxy_call_count)

    request = json.dumps({
        "id": call_id,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    })

    async with _proxy_lock:
        # Write request to proxy stdin
        _proxy_process.stdin.write(request + "\n")
        _proxy_process.stdin.flush()

        # Read response from proxy stdout
        response_line = await asyncio.get_event_loop().run_in_executor(
            None, _proxy_process.stdout.readline
        )

    if not response_line:
        raise RuntimeError("z-ai proxy returned empty response")

    data = json.loads(response_line.strip())

    if data.get("error"):
        raise RuntimeError(f"z-ai proxy error: {data['error']}")

    content = data.get("content", "")
    model = data.get("model", "unknown")
    tokens = data.get("tokens", 0)
    _proxy_total_tokens += tokens

    if _proxy_call_count % 5 == 0:
        logger.info(
            "z-ai proxy stats: calls=%d tokens=%d model=%s",
            _proxy_call_count, _proxy_total_tokens, model,
        )

    return content


# ── Fallback: z-ai CLI (one-shot subprocess) ────────────────────

async def _zai_cli_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Fallback: z-ai CLI as one-shot subprocess."""
    output_file = tempfile.mktemp(suffix='.json')

    try:
        proc = await asyncio.create_subprocess_exec(
            'z-ai', 'chat',
            '--prompt', prompt,
            '-o', output_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode != 0:
            raise RuntimeError(f"z-ai CLI exited with {proc.returncode}")

        with open(output_file, 'r') as f:
            data = json.load(f)

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Empty response from z-ai CLI")

        return content.strip()
    finally:
        try:
            os.unlink(output_file)
        except OSError:
            pass


# ── Fallback: litellm + httpx (NVIDIA direct) ───────────────────

async def _litellm_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Fallback: litellm with NVIDIA API."""
    from app.core.parwa_pipeline.config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL

    import litellm
    resp = await litellm.acompletion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=LLM_API_KEY,
        api_base=LLM_API_BASE,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


async def _httpx_fallback(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Last resort: direct httpx call to NVIDIA."""
    from app.core.parwa_pipeline.config import LLM_API_BASE, LLM_API_KEY, NVIDIA_MODEL

    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{LLM_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        if r.status_code == 200:
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            raise RuntimeError(f"NVIDIA API {r.status_code}: {r.text[:200]}")


# ── Main LLM Call (fallback chain) ──────────────────────────────

async def llm_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Single LLM call with automatic fallback chain.

    Chain: z-ai proxy (fast) → z-ai CLI → litellm → httpx direct
    Returns the response text.
    """
    # Primary: z-ai proxy (persistent process, no startup overhead)
    try:
        return await _zai_proxy_call(prompt, max_tokens, temperature)
    except Exception as e:
        logger.warning("z-ai proxy failed, trying CLI: %s", e)

    # Fallback 1: z-ai CLI (one-shot, has startup overhead)
    try:
        return await _zai_cli_call(prompt, max_tokens, temperature)
    except Exception as e:
        logger.warning("z-ai CLI failed, trying litellm: %s", e)

    # Fallback 2: litellm
    try:
        return await _litellm_call(prompt, max_tokens, temperature)
    except Exception as e:
        logger.warning("litellm failed, trying httpx: %s", e)

    # Fallback 3: httpx direct
    try:
        return await _httpx_fallback(prompt, max_tokens, temperature)
    except Exception as e:
        logger.error("All LLM backends failed: %s", e)
        raise RuntimeError(f"All LLM backends failed. Last error: {e}")


def shutdown_proxy():
    """Shutdown the z-ai proxy process."""
    global _proxy_process
    if _proxy_process and _proxy_process.poll() is None:
        _proxy_process.terminate()
        _proxy_process.wait(timeout=5)
        _proxy_process = None
        logger.info("z-ai LLM proxy shut down")


def parse_confidence(text: str, default: float = 0.7) -> float:
    """Extract a 0.0-1.0 confidence number from LLM response text."""
    match = re.search(r"(\d+\.?\d*)", text.strip())
    if match:
        val = float(match.group(1))
        if val > 1:
            val = val / 100
        return max(0.0, min(1.0, val))
    return default