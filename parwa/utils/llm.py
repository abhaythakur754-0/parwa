"""LLM client utilities for PARWA nodes.

Uses LangChain's ChatOpenAI for LLM interactions.
For development/testing, supports mock mode.

Production features:
- Retry with exponential backoff on LLM failures
- Rate limiting to prevent API overload
- Async support for concurrent ticket processing
- Structured logging for all LLM calls
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from parwa.utils.rate_limiter import get_llm_rate_limiter
from parwa.utils.retry import retry_with_backoff

logger = logging.getLogger("parwa.llm")

# Global LLM instance cache
_llm_cache: dict[str, BaseChatModel] = {}

# Mock mode flag - when True, returns deterministic responses
MOCK_MODE = os.getenv("PARWA_MOCK_MODE", "true").lower() == "true"


@retry_with_backoff(max_retries=3, base_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
def _invoke_llm(llm: BaseChatModel, prompt: str | list) -> Any:
    """Invoke LLM with retry and rate limiting.

    Args:
        llm: The LLM instance.
        prompt: The prompt to send.

    Returns:
        The LLM response.
    """
    limiter = get_llm_rate_limiter()
    limiter.acquire(timeout=30.0)
    return llm.invoke(prompt)


def get_llm(model: str = "gpt-4o-mini", temperature: float = 0.1) -> BaseChatModel:
    """Get or create a cached LLM instance.

    Args:
        model: The model name to use
        temperature: Sampling temperature

    Returns:
        A ChatOpenAI instance
    """
    cache_key = f"{model}_{temperature}"
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=2,
            timeout=30.0,
        )
    return _llm_cache[cache_key]


def clear_llm_cache() -> None:
    """Clear the LLM instance cache."""
    _llm_cache.clear()


def invoke_llm(prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.1) -> str:
    """High-level LLM invocation with retry, rate limiting, and error handling.

    This is the recommended way to call LLMs in PARWA nodes.
    In MOCK_MODE, returns deterministic responses from MockLLM.

    Args:
        prompt: The prompt to send.
        model: The model name to use.
        temperature: Sampling temperature.

    Returns:
        The LLM response as a string.
    """
    if MOCK_MODE:
        mock = get_mock_llm()
        return mock.invoke(prompt)

    try:
        llm = get_llm(model=model, temperature=temperature)
        response = _invoke_llm(llm, prompt)
        text = response.content if hasattr(response, "content") else str(response)
        logger.debug("invoke_llm: prompt_len=%d response_len=%d", len(prompt), len(text))
        return text
    except Exception as exc:
        logger.error("invoke_llm: LLM call failed: %s", exc)
        raise


class MockLLM:
    """Mock LLM for testing without API calls.

    Returns deterministic responses based on the input prompt.
    """

    def invoke(self, prompt: str | list, **kwargs: Any) -> str:
        """Return a mock response based on keywords in the prompt."""
        if isinstance(prompt, list):
            prompt_str = str(prompt)
        else:
            prompt_str = str(prompt)

        prompt_lower = prompt_str.lower()

        # Intent classification
        if "intent" in prompt_lower and "classify" in prompt_lower:
            if "refund" in prompt_lower or "charged twice" in prompt_lower:
                return "refund_request|0.97"
            if "cancel" in prompt_lower:
                return "cancellation|0.92"
            if "order status" in prompt_lower or "where is my order" in prompt_lower:
                return "order_status|0.95"
            if "account" in prompt_lower:
                return "account_modification|0.88"
            if "billing" in prompt_lower or "charge" in prompt_lower:
                return "billing_issue|0.90"
            return "general_inquiry|0.75"

        # Sentiment
        if "sentiment" in prompt_lower or "emotion" in prompt_lower:
            if "angry" in prompt_lower or "frustrated" in prompt_lower or "unacceptable" in prompt_lower:
                return "frustrated|0.85"
            if "happy" in prompt_lower or "great" in prompt_lower or "thanks" in prompt_lower:
                return "happy|0.80"
            return "neutral|0.70"

        # Escalation
        if "escalat" in prompt_lower:
            if "legal" in prompt_lower or "attorney" in prompt_lower:
                return "true|legal_threat"
            if "urgent" in prompt_lower or "unacceptable" in prompt_lower:
                return "true|high_urgency"
            return "false|"

        # FAQ matching
        if "faq" in prompt_lower:
            if "refund" in prompt_lower:
                return "refund_policy|0.90|Refunds are available within 30 days of purchase for duplicate charges."
            if "shipping" in prompt_lower:
                return "shipping_faq|0.85|Standard shipping takes 3-5 business days."
            return "no_match|0.00|"

        # Knowledge base
        if "knowledge" in prompt_lower or "kb" in prompt_lower or "retriev" in prompt_lower:
            return "Found relevant document: Refund policy allows full refund for duplicate charges within 30 days."

        # Integration
        if "crm" in prompt_lower or "integration" in prompt_lower or "lookup" in prompt_lower:
            return '{"order_id": "ORD-12345", "status": "delivered", "charges": [{"amount": 49.99, "date": "2025-01-05"}, {"amount": 49.99, "date": "2025-01-05"}]}'

        # Reasoning
        if "reason" in prompt_lower or "think" in prompt_lower:
            return "Step 1: Customer reports duplicate charge. Step 2: CRM confirms two charges on same date. Step 3: Policy allows refund within 30 days. Conclusion: Customer is eligible for full refund of $49.99."

        # Reverse thinking
        if "reverse" in prompt_lower or "backward" in prompt_lower or "trace" in prompt_lower:
            return "Goal: Refund processed. Trace: Need approval -> Need evidence -> CRM shows duplicate -> Policy allows refund -> Evidence confirmed. Validation: PASSED."

        # Tree of thoughts
        if "tree" in prompt_lower or "paths" in prompt_lower or "explore" in prompt_lower:
            return 'Path 1: Full refund (confidence: 0.95, selected: true). Path 2: Partial refund (confidence: 0.40). Path 3: Store credit (confidence: 0.30).'

        # Strategy
        if "strateg" in prompt_lower or "plan" in prompt_lower:
            return "Step 1: Verify duplicate charge in CRM. Step 2: Calculate refund amount ($49.99). Step 3: Submit for approval or execute refund."

        # Action planning
        if "action" in prompt_lower and "plan" in prompt_lower:
            return "Action: Process refund of $49.99 to original payment method."

        # Quality scoring
        if "quality" in prompt_lower or "score" in prompt_lower:
            return "85|accurate,complete,compliant"

        # PII detection
        if "pii" in prompt_lower or "personal" in prompt_lower or "redact" in prompt_lower:
            return "false|No PII detected in message."

        # Proactive
        if "proactive" in prompt_lower or "predict" in prompt_lower or "next" in prompt_lower:
            return "Customer may ask about shipping status next (confidence: 0.80)."

        # Default response
        return "Analysis complete. No specific pattern matched."


# Singleton mock instance
_mock_llm = MockLLM()


def get_mock_llm() -> MockLLM:
    """Get the mock LLM instance for testing."""
    return _mock_llm
