"""
High LLM Client -- LLM wrapper for High Parwa nodes.

Day 3 (AI Core): Delegates to the unified llm_gateway for provider-agnostic
LLM calls. Supports LiteLLM (production), ZAI Gateway (testing/China),
and OpenAI (direct) automatically based on environment.

Uses gpt-4o (Heavy tier) for all industries.
High uses the most capable model with the highest token limits.

Falls back gracefully on error -- never crashes (BC-008).
Returns (response_text, tokens_used) tuple.

Design:
  - Delegates to llm_gateway.generate() for provider-agnostic calls
  - Falls back to template response if LLM fails
  - Returns (response_text, tokens_used) tuple
  - High always uses gpt-4o regardless of industry

BC-001: company_id first parameter on public methods.
BC-007: All AI model interaction through llm_gateway.
BC-008: Every public method wrapped in try/except -- never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from app.core.llm_gateway import llm_gateway, LLMProvider
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
        self._api_key = api_key or ""
        self._base_url = base_url or None
        # Configure the gateway if custom settings provided
        if self._api_key:
            llm_gateway._api_key = self._api_key
        if self._base_url:
            llm_gateway._base_url = self._base_url
        logger.info(
            "high_llm_client_initialized",
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
        max_tokens: int = 1000,  # High: highest default
        temperature: float = 0.3,  # High: lowest temperature for most precise output
        company_id: str = "",
    ) -> Tuple[str, int]:
        """Send a chat completion request via the unified llm_gateway.

        Day 3: Delegates to llm_gateway.generate() for provider-agnostic
        LLM access (LiteLLM / ZAI Gateway / OpenAI).

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            max_tokens: Maximum tokens in the response (High default: 1000).
            temperature: Sampling temperature (0.0-2.0, High default: 0.3).
            company_id: Tenant identifier (BC-001).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns ("", 0).
        """
        try:
            response = await llm_gateway.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                technique_id="parwa_high",
                max_tokens=max_tokens,
                temperature=temperature,
                company_id=company_id,
            )
            text = response.text or ""
            tokens = response.tokens_used or 0

            if text:
                logger.debug(
                    "high_llm_chat_success",
                    model=response.model,
                    provider=response.provider,
                    tokens=tokens,
                    response_length=len(text),
                )
            else:
                logger.warning(
                    "high_llm_chat_empty",
                    provider=response.provider,
                    error=response.error,
                )

            return (text, tokens)

        except Exception:
            logger.exception("high_llm_chat_failed")
            return ("", 0)

    async def chat_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        fallback_text: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.3,
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
