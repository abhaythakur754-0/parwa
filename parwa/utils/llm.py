"""LLM client utilities for PARWA nodes.

Uses LangChain's ChatOpenAI for LLM interactions.
For development/testing, supports mock mode.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

# Global LLM instance cache
_llm_cache: dict[str, BaseChatModel] = {}

# Mock mode flag - when True, returns deterministic responses
MOCK_MODE = os.getenv("PARWA_MOCK_MODE", "true").lower() == "true"


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
        )
    return _llm_cache[cache_key]


def clear_llm_cache() -> None:
    """Clear the LLM instance cache."""
    _llm_cache.clear()


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
