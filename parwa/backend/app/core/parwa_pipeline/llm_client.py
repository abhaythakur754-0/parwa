"""
PARWA Pipeline V2 — Shared LLM Client

Single place for all LLM calls across all 8 nodes.
Uses NVIDIA API with Llama 3.1 8B.

Every node imports from here — no duplicate LLM call code.
"""

from __future__ import annotations

import logging
import re

from app.core.parwa_pipeline.config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL

logger = logging.getLogger("parwa.pipeline.llm")


async def llm_call(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Single LLM call. Returns the response text.

    Uses OpenAI-compatible format with NVIDIA API base.
    """
    import litellm

    try:
        resp = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            api_base=LLM_API_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        # Fallback: try direct httpx call for NVIDIA if litellm routing fails
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{LLM_API_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error("NVIDIA direct call failed: %s %s", r.status_code, r.text[:200])
                    raise
        except Exception as e2:
            logger.error("Fallback LLM call also failed: %s", e2)
        raise


def parse_confidence(text: str, default: float = 0.7) -> float:
    """Extract a 0.0-1.0 confidence number from LLM response text."""
    match = re.search(r"(\d+\.?\d*)", text.strip())
    if match:
        val = float(match.group(1))
        # If value looks like percentage (e.g. 85), normalize to 0-1
        if val > 1:
            val = val / 100
        return max(0.0, min(1.0, val))
    return default