"""
Mini LLM Client — Lightweight LLM wrapper for Mini Parwa nodes.

Day 3 (AI Core): Delegates to the unified llm_gateway for provider-agnostic
LLM calls. Supports LiteLLM (production), ZAI Gateway (testing/China),
and OpenAI (direct) automatically based on environment.

Falls back gracefully on error — never crashes (BC-008).
Returns (response_text, tokens_used) tuple.

BC-001: company_id first parameter on public methods.
BC-007: All AI model interaction through llm_gateway.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from app.core.llm_gateway import llm_gateway, LLMProvider
from app.logger import get_logger

logger = get_logger("mini_llm_client")

# Default model for Mini tier
DEFAULT_MODEL = "gpt-4o-mini"


class MiniLLMClient:
    """Lightweight LLM client for the Mini Parwa pipeline.

    Uses the OpenAI Python SDK with graceful fallback.
    Designed for gpt-4o-mini — the cheapest capable model.

    Usage:
        client = MiniLLMClient()
        text, tokens = await client.chat(
            system_prompt="You are a helpful assistant.",
            user_message="Hello!",
        )
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Initialize the Mini LLM client.

        Day 3: Now delegates to the unified llm_gateway.
        Legacy parameters (api_key, base_url) are accepted for backward
        compatibility but the gateway auto-detects the provider.

        Args:
            model: Model name (default: gpt-4o-mini).
            api_key: API key (gateway uses env vars if empty).
            base_url: Base URL for OpenAI-compatible APIs.
        """
        self.model = model
        self._api_key = api_key or ""
        self._base_url = base_url or None
        # Configure the gateway if custom settings provided
        if self._api_key:
            llm_gateway._api_key = self._api_key
        if self._base_url:
            llm_gateway._base_url = self._base_url
        logger.info(
            "mini_llm_client_initialized",
            model=self.model,
            provider=llm_gateway.provider.value,
        )

    def _ensure_client(self) -> None:
        """No-op: gateway handles lazy initialization."""
        pass

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        company_id: str = "",
    ) -> Tuple[str, int]:
        """Send a chat completion request via the unified llm_gateway.

        Day 3: Delegates to llm_gateway.generate() for provider-agnostic
        LLM access (LiteLLM / ZAI Gateway / OpenAI).

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0-2.0).
            company_id: Tenant identifier (BC-001).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns ("", 0).
        """
        try:
            response = await llm_gateway.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                technique_id="mini_parwa",
                max_tokens=max_tokens,
                temperature=temperature,
                company_id=company_id,
            )
            text = response.text or ""
            tokens = response.tokens_used or 0

            if text:
                logger.debug(
                    "mini_llm_chat_success",
                    model=response.model,
                    provider=response.provider,
                    tokens=tokens,
                    response_length=len(text),
                )
            else:
                logger.warning(
                    "mini_llm_chat_empty",
                    provider=response.provider,
                    error=response.error,
                )

            return (text, tokens)

        except Exception:
            logger.exception("mini_llm_chat_failed")
            return ("", 0)

    async def chat_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        fallback_text: str = "",
        max_tokens: int = 256,
        temperature: float = 0.7,
        company_id: str = "",
    ) -> Tuple[str, int]:
        """Chat with a fallback text if LLM fails.

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            fallback_text: Text to return if LLM call fails.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            company_id: Tenant identifier (BC-001).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns (fallback_text, 0).
        """
        text, tokens = await self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
            company_id=company_id,
        )
        if not text:
            return (fallback_text, 0)
        return (text, tokens)

    @property
    def is_available(self) -> bool:
        """Check if the LLM client is available via gateway."""
        return llm_gateway.is_available
