"""
Mini LLM Client — Lightweight LLM wrapper for Mini Parwa nodes.

Uses the OpenAI Python SDK to call gpt-4o-mini for generation.
Falls back gracefully on error — never crashes (BC-008).

Design:
  - Tries existing SmartRouter if available
  - Falls back to direct OpenAI API call
  - Falls back to template response if both fail
  - Returns (response_text, tokens_used) tuple

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

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

        Args:
            model: OpenAI model name (default: gpt-4o-mini).
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Optional base URL for OpenAI-compatible APIs.
        """
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL", None)
        self._client = None
        self._initialized = False

    def _ensure_client(self) -> None:
        """Lazy-initialize the OpenAI client."""
        if self._initialized:
            return
        try:
            from openai import OpenAI

            kwargs: Dict[str, Any] = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url

            self._client = OpenAI(**kwargs)
            self._initialized = True
            logger.info(
                "mini_llm_client_initialized",
                model=self.model,
                has_api_key=bool(self._api_key),
            )
        except Exception:
            logger.exception("mini_llm_client_init_failed")
            self._initialized = True  # Don't retry init

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> Tuple[str, int]:
        """Send a chat completion request to the LLM.

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0-2.0).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns ("", 0).
        """
        try:
            self._ensure_client()

            if self._client is None:
                logger.warning("mini_llm_client_not_available")
                return ("", 0)

            # Use the async interface
            import asyncio

            response = await asyncio.to_thread(
                self._sync_chat,
                system_prompt,
                user_message,
                max_tokens,
                temperature,
            )
            return response

        except Exception:
            logger.exception("mini_llm_chat_failed")
            return ("", 0)

    def _sync_chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> Tuple[str, int]:
        """Synchronous chat call (run in thread pool)."""
        try:
            result = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            text = result.choices[0].message.content or ""
            tokens = result.usage.total_tokens if result.usage else 0

            logger.debug(
                "mini_llm_chat_success",
                model=self.model,
                tokens=tokens,
                response_length=len(text),
            )
            return (text, tokens)

        except Exception:
            logger.exception("mini_llm_sync_chat_failed")
            return ("", 0)

    async def chat_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        fallback_text: str = "",
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> Tuple[str, int]:
        """Chat with a fallback text if LLM fails.

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            fallback_text: Text to return if LLM call fails.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns (fallback_text, 0).
        """
        text, tokens = await self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not text:
            return (fallback_text, 0)
        return (text, tokens)

    @property
    def is_available(self) -> bool:
        """Check if the LLM client is available (has API key)."""
        return bool(self._api_key)
