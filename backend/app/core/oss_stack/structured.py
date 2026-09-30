"""
Structured LLM extraction via Instructor (optional) + LiteLLM router
(optional). Both are thin wrappers: when deps/flags are off, callers use
the existing LLM path unchanged.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from typing import Any, Optional, Type

logger = logging.getLogger("parwa.oss.structured")


def instructor_available() -> bool:
    try:
        return importlib.util.find_spec("instructor") is not None
    except Exception:
        return False


def litellm_available() -> bool:
    try:
        if importlib.util.find_spec("litellm") is None:
            return False
        return os.environ.get("OSS_LITELLM", "0").strip() in ("1", "true", "yes", "on")
    except Exception:
        return False


def extract_structured(
    text: str,
    schema: Type,
    system: str = "Extract structured data from the support ticket.",
) -> Optional[Any]:
    """Extract a pydantic model from text. Caller supplies the schema class.
    `client` may be any OpenAI-compatible client (PARWA passes its own).
    Returns None when instructor is unavailable or extraction fails —
    callers keep their existing parsing as the fallback."""
    if not instructor_available():
        return None
    try:
        import instructor  # type: ignore
        from openai import OpenAI  # type: ignore

        api_key = os.environ.get("OSS_STRUCTURED_API_KEY", "sk-placeholder")
        base_url = os.environ.get("OSS_STRUCTURED_BASE_URL")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        iclient = instructor.from_openai(client)
        model = os.environ.get("OSS_STRUCTURED_MODEL", "gpt-4o-mini")
        return iclient.chat.completions.create(
            model=model,
            response_model=schema,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text[:4000]},
            ],
            max_retries=2,
        )
    except Exception as exc:
        logger.warning("oss_structured failed: %s", str(exc)[:200])
        return None


def llm_completion(
    prompt: str,
    system: str = "",
    max_tokens: int = 800,
    fallback_models: Optional[list] = None,
) -> Optional[str]:
    """LiteLLM completion with fallback chain + cost cap. Off unless
    OSS_LITELLM=1. Returns None when unavailable (caller uses own path)."""
    if not litellm_available():
        return None
    try:
        import litellm  # type: ignore

        litellm.suppress_debug_info = True
        chain = fallback_models or [
            os.environ.get("OSS_LITELLM_PRIMARY", "openai/gpt-4o-mini"),
            os.environ.get("OSS_LITELLM_SECONDARY", "gemini/gemini-1.5-flash"),
        ]
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt[:8000]}
        ]
        last_exc = None
        for model in chain:
            try:
                resp = litellm.completion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    num_retries=1,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                last_exc = exc
                continue
        if last_exc:
            logger.warning("oss_llm_router chain exhausted: %s", str(last_exc)[:200])
        return None
    except Exception as exc:
        logger.warning("oss_llm_router failed: %s", str(exc)[:200])
        return None
