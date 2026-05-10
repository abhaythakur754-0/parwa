"""
Unified LLM Gateway for AI Techniques (Day 3 - AI Core Security)

Provides a single async interface for all 12 AI techniques to call
external LLMs. Supports two provider modes:

  1. Production: Uses SmartRouter → LiteLLM → Google/Cerebras/Groq
  2. Testing/China: Uses z-ai gateway via HTTP (z-ai-web-dev-sdk compatible)

Design Principles:
  - BC-007: All AI model interaction goes through this gateway
  - BC-008: Never crash — always returns a usable response
  - BC-001: company_id isolation supported
  - Graceful fallback: LLM failure → deterministic template fallback
  - Token tracking per technique call

Usage in techniques:
    from app.core.llm_gateway import llm_gateway

    response = await llm_gateway.generate(
        technique_id="chain_of_thought",
        system_prompt="You are a reasoning assistant...",
        user_message="Break down this query: ...",
        max_tokens=300,
        temperature=0.5,
        company_id="comp_123",
    )
    # response = LLMResponse(text="...", tokens_used=42, model="...")

Building Codes: BC-001, BC-007, BC-008, BC-012
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("parwa.llm_gateway")


# ── Response Types ──────────────────────────────────────────────────


@dataclass
class LLMResponse:
    """Standard response from the LLM gateway."""
    text: str = ""
    tokens_used: int = 0
    model: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    fallback_used: bool = False
    error: Optional[str] = None


# ── Provider Mode ───────────────────────────────────────────────────


class LLMProvider(str, Enum):
    """Supported LLM provider modes."""
    LITELLM = "litellm"          # Production: SmartRouter → Google/Cerebras/Groq
    ZAI_GATEWAY = "zai_gateway"  # Testing: z-ai HTTP API
    OPENAI = "openai"            # Direct OpenAI API


# ── LLM Gateway ──────────────────────────────────────────────────────


class LLMGateway:
    """
    Unified LLM Gateway for all AI techniques.

    Provides a simple async interface:
        response = await gateway.generate(system_prompt, user_message, ...)

    Provider selection:
      - LITELLM: Uses LiteLLM with SmartRouter routing (production)
      - ZAI_GATEWAY: Uses z-ai HTTP API (testing/China access)
      - OPENAI: Uses OpenAI SDK directly

    Graceful degradation:
      - If LLM call fails, returns empty response (not crash)
      - Techniques should check response.text and fall back to templates
      - All errors are logged but never raised to callers
    """

    # Default timeouts
    CONNECT_TIMEOUT_SECONDS = 10.0
    READ_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.LITELLM,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        default_max_tokens: int = 300,
        default_temperature: float = 0.5,
    ) -> None:
        """
        Initialize the LLM gateway.

        Args:
            provider: Which LLM provider to use.
            model: Model identifier. Provider-specific if empty.
            api_key: API key. Falls back to env vars if empty.
            base_url: Base URL for OpenAI-compatible APIs.
            default_max_tokens: Default max tokens for responses.
            default_temperature: Default temperature for sampling.
        """
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature
        self._client = None
        self._initialized = False

        # Stats tracking
        self._call_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_tokens = 0

    # ── Lazy Initialization ────────────────────────────────────────

    async def _ensure_initialized(self) -> bool:
        """Ensure the LLM client is initialized. Returns True on success."""
        if self._initialized:
            return self._client is not None

        try:
            if self.provider == LLMProvider.LITELLM:
                return self._init_litellm()
            elif self.provider == LLMProvider.ZAI_GATEWAY:
                return self._init_zai_gateway()
            elif self.provider == LLMProvider.OPENAI:
                return self._init_openai()
            else:
                logger.error("Unknown provider: %s", self.provider.value)
                self._initialized = True
                return False
        except Exception:
            logger.exception("LLM gateway initialization failed")
            self._initialized = True
            return False

    def _init_litellm(self) -> bool:
        """Initialize LiteLLM client."""
        try:
            import litellm
            self._client = litellm
            self.model = self.model or os.environ.get(
                "AI_MEDIUM_MODEL", "gemini/gemini-2.0-flash"
            )
            logger.info(
                "LLM gateway initialized with LiteLLM, model=%s",
                self.model,
            )
            self._initialized = True
            return True
        except ImportError:
            logger.warning("LiteLLM not installed, falling back to no-LLM mode")
            self._initialized = True
            return False

    def _init_zai_gateway(self) -> bool:
        """Initialize z-ai gateway HTTP client."""
        self._api_key = self._api_key or os.environ.get("ZAI_API_KEY", "")
        self._base_url = self._base_url or os.environ.get(
            "ZAI_BASE_URL", "http://localhost:3000/api"
        )
        self.model = self.model or os.environ.get(
            "ZAI_MODEL", "default"
        )
        logger.info(
            "LLM gateway initialized with z-ai gateway, "
            "base_url=%s, model=%s",
            self._base_url,
            self.model,
        )
        self._initialized = True
        return True

    def _init_openai(self) -> bool:
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI

            api_key = self._api_key or os.environ.get("OPENAI_API_KEY", "")
            base_url = self._base_url or os.environ.get("OPENAI_BASE_URL", None)
            self.model = self.model or "gpt-4o-mini"

            kwargs: Dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url

            self._client = OpenAI(**kwargs)
            logger.info("LLM gateway initialized with OpenAI, model=%s", self.model)
            self._initialized = True
            return True
        except ImportError:
            logger.warning("OpenAI not installed, falling back to no-LLM mode")
            self._initialized = True
            return False

    # ── Public API ──────────────────────────────────────────────────

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        technique_id: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        company_id: str = "",
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> LLMResponse:
        """
        Generate an LLM response.

        This is the main interface for all AI techniques.

        Args:
            system_prompt: System prompt for the LLM.
            user_message: User message / query.
            technique_id: ID of the calling technique (for logging/metrics).
            max_tokens: Max tokens in response. Uses default if None.
            temperature: Sampling temperature. Uses default if None.
            company_id: Tenant identifier (BC-001).
            messages: Optional pre-built message list. If provided,
                system_prompt and user_message are ignored.

        Returns:
            LLMResponse with text, tokens_used, model, etc.
            On failure, returns empty text with error info.
        """
        self._call_count += 1
        start_time = time.time()

        _max_tokens = max_tokens or self.default_max_tokens
        _temperature = temperature if temperature is not None else self.default_temperature

        try:
            available = await self._ensure_initialized()
            if not available:
                return LLMResponse(
                    text="",
                    tokens_used=0,
                    model=self.model,
                    provider=self.provider.value,
                    latency_ms=0.0,
                    fallback_used=False,
                    error="LLM client not available",
                )

            # Build messages
            if messages is None:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]

            # Route to appropriate provider
            if self.provider == LLMProvider.LITELLM:
                response = await self._call_litellm(
                    messages, _max_tokens, _temperature, technique_id, company_id,
                )
            elif self.provider == LLMProvider.ZAI_GATEWAY:
                response = await self._call_zai_gateway(
                    messages, _max_tokens, _temperature, technique_id, company_id,
                )
            elif self.provider == LLMProvider.OPENAI:
                response = await self._call_openai(
                    messages, _max_tokens, _temperature, technique_id, company_id,
                )
            else:
                response = LLMResponse(error="Unknown provider")

            latency_ms = (time.time() - start_time) * 1000
            response.latency_ms = round(latency_ms, 2)

            if response.text:
                self._success_count += 1
                self._total_tokens += response.tokens_used
            else:
                self._failure_count += 1

            return response

        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            self._failure_count += 1
            logger.warning(
                "LLM generate failed [technique=%s, company=%s]: %s",
                technique_id, company_id, str(exc)[:200],
            )
            return LLMResponse(
                text="",
                tokens_used=0,
                model=self.model,
                provider=self.provider.value,
                latency_ms=round(latency_ms, 2),
                fallback_used=False,
                error=str(exc),
            )

    async def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        technique_id: str = "",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        company_id: str = "",
    ) -> Dict[str, Any]:
        """
        Generate an LLM response and parse as JSON.

        Wraps generate() with JSON parsing. Returns parsed dict
        or empty dict on failure.

        Args:
            system_prompt: System prompt (should request JSON output).
            user_message: User message / query.
            technique_id: ID of the calling technique.
            max_tokens: Max tokens in response.
            temperature: Sampling temperature.
            company_id: Tenant identifier.

        Returns:
            Parsed JSON dict, or {} on failure.
        """
        response = await self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            technique_id=technique_id,
            max_tokens=max_tokens,
            temperature=temperature,
            company_id=company_id,
        )

        if not response.text:
            return {}

        try:
            # Try to extract JSON from the response
            text = response.text.strip()

            # Handle markdown code blocks
            if "```json" in text:
                json_match = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_match)
            elif "```" in text:
                json_match = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_match)

            # Try direct parse
            return json.loads(text)
        except (json.JSONDecodeError, IndexError, ValueError) as exc:
            logger.warning(
                "LLM JSON parse failed [technique=%s]: %s",
                technique_id, str(exc)[:100],
            )
            return {}

    # ── Provider-Specific Call Methods ──────────────────────────────

    async def _call_litellm(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        technique_id: str,
        company_id: str,
    ) -> LLMResponse:
        """Call LLM via LiteLLM."""
        try:
            import litellm

            start = time.time()

            response = await asyncio.to_thread(
                litellm.completion,
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.READ_TIMEOUT_SECONDS,
            )

            latency = (time.time() - start) * 1000

            text = ""
            tokens = 0
            if response and response.choices:
                text = response.choices[0].message.content or ""
                if response.usage:
                    tokens = response.usage.total_tokens or 0

            return LLMResponse(
                text=text,
                tokens_used=tokens,
                model=response.model if response else self.model,
                provider="litellm",
                latency_ms=round(latency, 2),
            )

        except Exception as exc:
            logger.warning(
                "LiteLLM call failed [technique=%s, model=%s]: %s",
                technique_id, self.model, str(exc)[:200],
            )
            return LLMResponse(
                text="",
                tokens_used=0,
                model=self.model,
                provider="litellm",
                error=str(exc),
            )

    async def _call_zai_gateway(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        technique_id: str,
        company_id: str,
    ) -> LLMResponse:
        """Call LLM via z-ai gateway HTTP API (z-ai-web-dev-sdk compatible)."""
        try:
            start = time.time()

            headers: Dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.CONNECT_TIMEOUT_SECONDS,
                    read=self.READ_TIMEOUT_SECONDS,
                    write=self.CONNECT_TIMEOUT_SECONDS,
                ),
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                text = ""
                tokens = 0

                if isinstance(data, dict):
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        text = msg.get("content", "")
                    usage = data.get("usage", {})
                    tokens = usage.get("total_tokens", 0)

                return LLMResponse(
                    text=text,
                    tokens_used=tokens,
                    model=data.get("model", self.model) if isinstance(data, dict) else self.model,
                    provider="zai_gateway",
                    latency_ms=round(latency, 2),
                )
            else:
                logger.warning(
                    "z-ai gateway returned %d [technique=%s]: %s",
                    response.status_code, technique_id,
                    response.text[:200] if response.text else "no body",
                )
                return LLMResponse(
                    text="",
                    tokens_used=0,
                    model=self.model,
                    provider="zai_gateway",
                    error=f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            logger.warning(
                "z-ai gateway timeout [technique=%s]", technique_id,
            )
            return LLMResponse(
                text="", tokens_used=0, model=self.model,
                provider="zai_gateway", error="timeout",
            )
        except Exception as exc:
            logger.warning(
                "z-ai gateway call failed [technique=%s]: %s",
                technique_id, str(exc)[:200],
            )
            return LLMResponse(
                text="",
                tokens_used=0,
                model=self.model,
                provider="zai_gateway",
                error=str(exc),
            )

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        technique_id: str,
        company_id: str,
    ) -> LLMResponse:
        """Call LLM via OpenAI Python SDK."""
        try:
            start = time.time()

            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            latency = (time.time() - start) * 1000

            text = ""
            tokens = 0
            if response and response.choices:
                text = response.choices[0].message.content or ""
                if response.usage:
                    tokens = response.usage.total_tokens or 0

            return LLMResponse(
                text=text,
                tokens_used=tokens,
                model=self.model,
                provider="openai",
                latency_ms=round(latency, 2),
            )

        except Exception as exc:
            logger.warning(
                "OpenAI call failed [technique=%s, model=%s]: %s",
                technique_id, self.model, str(exc)[:200],
            )
            return LLMResponse(
                text="",
                tokens_used=0,
                model=self.model,
                provider="openai",
                error=str(exc),
            )

    # ── Utility Methods ────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """Quick check if gateway has credentials configured."""
        if self.provider == LLMProvider.ZAI_GATEWAY:
            return bool(self._api_key or os.environ.get("ZAI_API_KEY"))
        elif self.provider == LLMProvider.OPENAI:
            return bool(self._api_key or os.environ.get("OPENAI_API_KEY"))
        elif self.provider == LLMProvider.LITELLM:
            return bool(
                os.environ.get("GOOGLE_AI_API_KEY")
                or os.environ.get("CEREBRAS_API_KEY")
                or os.environ.get("GROQ_API_KEY")
            )
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Return gateway usage statistics."""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "total_calls": self._call_count,
            "successful_calls": self._success_count,
            "failed_calls": self._failure_count,
            "total_tokens": self._total_tokens,
            "is_available": self.is_available,
        }


# ── Global Singleton ────────────────────────────────────────────────

# Auto-detect provider based on environment:
#   - If ZAI_API_KEY is set → use zai_gateway (for testing/China)
#   - If any LLM provider key is set → use litellm (production)
#   - Otherwise → litellm (will fail gracefully to deterministic fallback)

def _detect_provider() -> LLMProvider:
    """Auto-detect the best LLM provider based on environment."""
    if os.environ.get("ZAI_API_KEY"):
        return LLMProvider.ZAI_GATEWAY
    if os.environ.get("LLM_PROVIDER") == "zai_gateway":
        return LLMProvider.ZAI_GATEWAY
    if os.environ.get("LLM_PROVIDER") == "openai":
        return LLMProvider.OPENAI
    return LLMProvider.LITELLM


# Module-level singleton instance
# Techniques import this directly:
#   from app.core.llm_gateway import llm_gateway
llm_gateway = LLMGateway(
    provider=_detect_provider(),
    model=os.environ.get("LLM_MODEL", ""),
)
