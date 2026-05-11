"""
Centralized LLM client wrapper for AI techniques.

This module provides a single import point for all technique nodes
to access the LLM gateway.  All re-exports come from
``app.core.llm_gateway`` so that technique implementations never
need to know the underlying provider or gateway location.

Usage inside any technique node::

    from app.core.techniques.llm_client import (
        llm_gateway,
        LLMResponse,
        LLMGateway,
        LLMProvider,
        execute_llm_call,
        async_execute_llm_call,
    )

    # Async (preferred for LangGraph nodes)
    response = await async_execute_llm_call(
        system_prompt="You are a reasoning assistant…",
        user_message="Explain …",
        technique_id="chain_of_thought",
    )

    # Synchronous convenience wrapper (runs the event loop)
    response = execute_llm_call(
        system_prompt="…",
        user_message="…",
        technique_id="chain_of_thought",
    )

Building Codes: BC-007, BC-008
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

# ── Re-exports from the canonical LLM gateway ─────────────────────

from app.core.llm_gateway import (  # noqa: F401
    LLMGateway,
    LLMProvider,
    LLMResponse,
    llm_gateway,
)

logger = logging.getLogger("parwa.techniques.llm_client")


# ── Convenience helpers ────────────────────────────────────────────


async def async_execute_llm_call(
    *,
    system_prompt: str = "",
    user_message: str = "",
    technique_id: str = "",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    company_id: str = "",
    messages: Optional[List[Dict[str, str]]] = None,
) -> LLMResponse:
    """Async convenience wrapper around :pymeth:`LLMGateway.generate`.

    Simply forwards all arguments to the global ``llm_gateway`` singleton
    and returns the :class:`LLMResponse`.  Errors are already handled
    gracefully by the gateway (BC-008), but this wrapper adds an extra
    safety net and structured logging.
    """
    try:
        return await llm_gateway.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            technique_id=technique_id,
            max_tokens=max_tokens,
            temperature=temperature,
            company_id=company_id,
            messages=messages,
        )
    except Exception as exc:
        logger.error(
            "async_execute_llm_call unexpected error [technique=%s]: %s",
            technique_id,
            str(exc)[:300],
        )
        return LLMResponse(error=str(exc))


def execute_llm_call(
    *,
    system_prompt: str = "",
    user_message: str = "",
    technique_id: str = "",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    company_id: str = "",
    messages: Optional[List[Dict[str, str]]] = None,
) -> LLMResponse:
    """Synchronous convenience wrapper around :func:`async_execute_llm_call`.

    Creates a new event loop (or reuses the running one) so that
    non-async callers can still invoke the LLM gateway.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an async context — schedule as a task
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                async_execute_llm_call(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    technique_id=technique_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    company_id=company_id,
                    messages=messages,
                ),
            )
            return future.result(timeout=60)
    else:
        return asyncio.run(
            async_execute_llm_call(
                system_prompt=system_prompt,
                user_message=user_message,
                technique_id=technique_id,
                max_tokens=max_tokens,
                temperature=temperature,
                company_id=company_id,
                messages=messages,
            ),
        )
