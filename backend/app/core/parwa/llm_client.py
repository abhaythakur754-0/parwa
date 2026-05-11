"""
Pro LLM Client — LLM wrapper for Pro Parwa nodes.

Day 3 (AI Core): Delegates to the unified llm_gateway for provider-agnostic
LLM calls. Supports LiteLLM (production), ZAI Gateway (testing/China),
and OpenAI (direct) automatically based on environment.

Uses gpt-4o-mini (default) or gpt-4o (SaaS).
Pro uses a medium-tier model with higher token limits than Mini.

Falls back gracefully on error — never crashes (BC-008).
Returns (response_text, tokens_used) tuple.

Design:
  - Delegates to llm_gateway.generate() for provider-agnostic calls
  - Falls back to template response if LLM fails
  - Returns (response_text, tokens_used) tuple
  - Pro supports model switching: gpt-4o-mini for most, gpt-4o for SaaS

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

logger = get_logger("pro_llm_client")

# Default model for Pro tier (medium quality, cost-efficient)
DEFAULT_MODEL = "gpt-4o-mini"

# Industry → model mapping (SaaS gets gpt-4o for better technical responses)
INDUSTRY_MODEL_MAP: Dict[str, str] = {
    "saas": "gpt-4o",
    "ecommerce": "gpt-4o-mini",
    "logistics": "gpt-4o-mini",
    "general": "gpt-4o-mini",
}


class ProLLMClient:
    """Pro-tier LLM client for the Parwa pipeline.

    Uses the OpenAI Python SDK with graceful fallback.
    Default model: gpt-4o-mini. SaaS industry: gpt-4o.
    Higher token limits than Mini for richer responses.

    Usage:
        client = ProLLMClient()
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
        """Initialize the Pro LLM client.

        Args:
            model: OpenAI model name. Overridden by industry if set.
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Optional base URL for OpenAI-compatible APIs.
            industry: Industry for model selection (saas → gpt-4o).
        """
        # Industry-based model selection
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
            "pro_llm_client_initialized",
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
        max_tokens: int = 600,  # Pro: higher default than Mini's 256
        temperature: float = 0.5,  # Pro: lower temperature for more focused output
        company_id: str = "",
    ) -> Tuple[str, int]:
        """Send a chat completion request via the unified llm_gateway.

        Day 3: Delegates to llm_gateway.generate() for provider-agnostic
        LLM access (LiteLLM / ZAI Gateway / OpenAI).

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message content.
            max_tokens: Maximum tokens in the response (Pro default: 600).
            temperature: Sampling temperature (0.0-2.0, Pro default: 0.5).
            company_id: Tenant identifier (BC-001).

        Returns:
            Tuple of (response_text, tokens_used).
            On failure, returns ("", 0).
        """
        try:
            response = await llm_gateway.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                technique_id="parwa",
                max_tokens=max_tokens,
                temperature=temperature,
                company_id=company_id,
            )
            text = response.text or ""
            tokens = response.tokens_used or 0

            if text:
                logger.debug(
                    "pro_llm_chat_success",
                    model=response.model,
                    provider=response.provider,
                    tokens=tokens,
                    response_length=len(text),
                )
            else:
                logger.warning(
                    "pro_llm_chat_empty",
                    provider=response.provider,
                    error=response.error,
                )

            return (text, tokens)

        except Exception:
            logger.exception("pro_llm_chat_failed")
            return ("", 0)

    async def chat_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        fallback_text: str = "",
        max_tokens: int = 600,
        temperature: float = 0.5,
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
