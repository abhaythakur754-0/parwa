"""
High LLM Client -- LLM wrapper for High Parwa nodes.

Uses the OpenAI Python SDK to call gpt-4o (Heavy tier) for all industries.
High uses the most capable model with the highest token limits.

Falls back gracefully on error -- never crashes (BC-008).

Design:
  - Tries existing SmartRouter if available for model selection
  - Falls back to direct OpenAI API call
  - Falls back to template response if both fail
  - Returns (response_text, tokens_used) tuple
  - High always uses gpt-4o regardless of industry

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except -- never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from app.logger import get_logger

logger = get_logger("high_llm_client")

# Default model for High tier -- always gpt-4o (most capable)
DEFAULT_MODEL = "gpt-4o"

# Industry -> model mapping (High: ALL industries get gpt-4o)
INDUSTRY_MODEL_MAP: Dict[str, str] = {
    "saas": "gpt-4o",
    "ecommerce": "gpt-4o",
    "logistics": "gpt-4o",
    "general": "gpt-4o",
}


class HighLLMClient:
    """High-tier LLM client for the Parwa High pipeline.

    Uses the OpenAI Python SDK with graceful fallback.
    Always uses gpt-4o regardless of industry.
    Highest token limits for richest, most detailed responses.

    Usage:
        client = HighLLMClient()
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
        industry: str = "",
    ) -> None:
        """Initialize the High LLM client.

        Args:
            model: OpenAI model name. Overridden by industry if set.
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Optional base URL for OpenAI-compatible APIs.
            industry: Industry for model selection (High: always gpt-4o).
        """
        # High always uses gpt-4o regardless of industry
        if industry and industry in INDUSTRY_MODEL_MAP:
            self.model = INDUSTRY_MODEL_MAP[industry]
        else:
            self.model = model

        self.model_name = self.model  # Alias for audit logging
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
                "high_llm_client_initialized",
                model=self.model,
                has_api_key=bool(self._api_key),
            )
        except Exception:
            logger.exception("high_llm_client_init_failed")
            self._initialized = True  # Don't retry init

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1000,  # High: highest default
        temperature: float = 0.3,  # High: lowest temperature for most precise output
    ) -> Tuple[str, int]:
        """Send a chat completion request to the LLM.

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            max_tokens: Maximum tokens in the response (High default: 1000).
            temperature: Sampling temperature (0.0-2.0, High default: 0.3).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns ("", 0).
        """
        try:
            self._ensure_client()

            if self._client is None:
                logger.warning("high_llm_client_not_available")
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
            logger.exception("high_llm_chat_failed")
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
                "high_llm_chat_success",
                model=self.model,
                tokens=tokens,
                response_length=len(text),
            )
            return (text, tokens)

        except Exception:
            logger.exception("high_llm_sync_chat_failed")
            return ("", 0)

    async def chat_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        fallback_text: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.3,
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
