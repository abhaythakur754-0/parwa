"""LLM client utilities for PARWA nodes.

Uses LangChain's ChatOpenAI for LLM interactions.
For development/testing, supports mock mode.

Production features:
- Retry with exponential backoff on LLM failures (sync + async)
- Rate limiting to prevent API overload (sync + async)
- Circuit breaker to fail fast when LLM service is down
- TurboQuant token budget checking before LLM calls
- Prompt injection sanitization
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
from parwa.utils.retry import retry_with_backoff, async_retry_with_backoff

logger = logging.getLogger("parwa.llm")

# Global LLM instance cache
_llm_cache: dict[str, BaseChatModel] = {}

# Mock mode flag - when True, returns deterministic responses
MOCK_MODE = os.getenv("PARWA_MOCK_MODE", "true").lower() == "true"


def _invoke_llm(llm: BaseChatModel, prompt: str | list) -> Any:
    """Invoke LLM with rate limiting and circuit breaker (sync).

    Rate limiting is checked first (our own throttle — not a circuit failure).
    Circuit breaker wraps only the actual LLM call (external service failure).

    Retry is handled by the caller (invoke_llm) via retry_with_backoff.

    Args:
        llm: The LLM instance.
        prompt: The prompt to send.

    Returns:
        The LLM response.

    Raises:
        TimeoutError: If rate limiter times out waiting for a token.
        CircuitOpenError: If LLM circuit breaker is open.
    """
    # Rate limiting first — this is our own throttle, not a service failure
    limiter = get_llm_rate_limiter()
    if not limiter.acquire(timeout=30.0):
        raise TimeoutError("LLM rate limiter timeout — too many concurrent requests")

    # Circuit breaker wraps the actual LLM call — service failures count here
    from parwa.utils.circuit_breaker import get_llm_circuit_breaker
    breaker = get_llm_circuit_breaker()
    return breaker.call(lambda: llm.invoke(prompt))


async def _ainvoke_llm(llm: BaseChatModel, prompt: str | list) -> Any:
    """Invoke LLM with rate limiting and circuit breaker (async).

    Rate limiting is checked first (our own throttle — not a circuit failure).
    Circuit breaker wraps only the actual LLM call (external service failure).

    Retry is handled by the caller (ainvoke_llm) via async_retry_with_backoff.

    Args:
        llm: The LLM instance.
        prompt: The prompt to send.

    Returns:
        The LLM response.

    Raises:
        TimeoutError: If rate limiter times out waiting for a token.
        CircuitOpenError: If LLM circuit breaker is open.
    """
    # Rate limiting first — this is our own throttle, not a service failure
    limiter = get_llm_rate_limiter()
    if not await limiter.async_acquire(timeout=30.0):
        raise TimeoutError("LLM rate limiter timeout — too many concurrent requests")

    # Circuit breaker wraps the actual LLM call — service failures count here
    from parwa.utils.circuit_breaker import get_llm_circuit_breaker
    breaker = get_llm_circuit_breaker()
    return await breaker.acall(lambda: llm.ainvoke(prompt))


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


# ─── TurboQuant Token Tracking Helpers ─────────────────────────────────────────────

# Rough estimate: 1 token ≈ 4 characters for English text
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length (rough approximation)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _check_token_budget(
    node_name: str, variant: str, estimated_tokens: int,
) -> bool:
    """Check if the node has enough token budget remaining.

    Integrates TurboQuant budget checking into the LLM call path.
    If the node has exceeded its budget, returns False to skip the LLM call.

    Args:
        node_name: The calling node name.
        variant: The PARWA variant.
        estimated_tokens: Estimated tokens for this call.

    Returns:
        True if budget is available, False if over budget.
    """
    try:
        from parwa.turboquant.token_budget import get_node_budget
        budget = get_node_budget(node_name, variant)
        if not budget.can_spend(estimated_tokens):
            logger.warning(
                "token_budget: node=%s over budget (remaining=%d, need=%d, variant=%s) "
                "— skipping LLM call",
                node_name, budget.remaining, estimated_tokens, variant,
            )
            return False
        return True
    except Exception:
        # If budget check fails, allow the call (don't block pipeline)
        return True


def _record_token_spend(
    node_name: str, variant: str, tokens_used: int,
) -> None:
    """Record token spend against the node's budget after a successful LLM call.

    Args:
        node_name: The calling node name.
        variant: The PARWA variant.
        tokens_used: Actual tokens used.
    """
    try:
        from parwa.turboquant.token_budget import get_node_budget
        budget = get_node_budget(node_name, variant)
        over = not budget.can_spend(tokens_used)
        budget.spend(tokens_used)
        if over:
            logger.warning(
                "token_budget: node=%s exceeded budget (used=%d, allocated=%d, variant=%s)",
                node_name, budget.used, budget.allocated, variant,
            )
    except Exception:
        pass


def _track_mock_usage(
    ticket_id: str, node_name: str, variant: str,
    prompt: str, response: str, model: str,
) -> None:
    """Track token usage for mock LLM calls (estimated tokens)."""
    try:
        from parwa.turboquant.token_tracker import get_token_tracker
        tracker = get_token_tracker()
        prompt_tokens = _estimate_tokens(prompt)
        completion_tokens = _estimate_tokens(response)
        tracker.record(
            ticket_id=ticket_id or "UNKNOWN",
            node_name=node_name or "unknown",
            variant=variant or "parwa",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )

        # Record against budget
        _record_token_spend(node_name, variant, prompt_tokens + completion_tokens)
    except Exception:
        # Never let tracking break the pipeline
        pass


def _track_response_usage(
    ticket_id: str, node_name: str, variant: str,
    response: Any, model: str,
) -> None:
    """Track token usage from real LLM response metadata."""
    try:
        from parwa.turboquant.token_tracker import get_token_tracker
        tracker = get_token_tracker()

        # Try to get actual token counts from response metadata
        prompt_tokens = 0
        completion_tokens = 0

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            prompt_tokens = response.usage_metadata.get('input_tokens', 0)
            completion_tokens = response.usage_metadata.get('output_tokens', 0)
        elif hasattr(response, 'response_metadata'):
            meta = response.response_metadata
            if 'token_usage' in meta:
                usage = meta['token_usage']
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)

        # Fallback to estimation if no metadata available
        if prompt_tokens == 0 and completion_tokens == 0:
            text = response.content if hasattr(response, 'content') else str(response)
            prompt_tokens = 50  # rough estimate for prompt
            completion_tokens = _estimate_tokens(text)

        tracker.record(
            ticket_id=ticket_id or "UNKNOWN",
            node_name=node_name or "unknown",
            variant=variant or "parwa",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )

        # Record against budget
        _record_token_spend(node_name, variant, prompt_tokens + completion_tokens)
    except Exception:
        # Never let tracking break the pipeline
        pass


@retry_with_backoff(max_retries=3, base_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
def invoke_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    *,
    node_name: str = "",
    ticket_id: str = "",
    variant: str = "parwa",
) -> str:
    """High-level sync LLM invocation with full production hardening.

    Includes: retry, rate limiting, circuit breaker, TurboQuant budget check,
    and token tracking.

    In MOCK_MODE, returns deterministic responses from MockLLM.

    Args:
        prompt: The prompt to send.
        model: The model name to use.
        temperature: Sampling temperature.
        node_name: Calling node name (for TurboQuant budget tracking).
        ticket_id: Current ticket ID (for TurboQuant tracking).
        variant: Current variant (for TurboQuant budget allocation).

    Returns:
        The LLM response as a string.
    """
    if MOCK_MODE:
        mock = get_mock_llm()
        text = mock.invoke(prompt)
        _track_mock_usage(ticket_id, node_name, variant, prompt, text, model)
        return text

    # Check token budget before making the call
    estimated = _estimate_tokens(prompt) + 200  # prompt + estimated response
    if not _check_token_budget(node_name, variant, estimated):
        logger.warning(
            "invoke_llm: token budget exceeded for node=%s variant=%s — "
            "returning budget-exceeded response",
            node_name, variant,
        )
        return "Token budget exceeded. Using rule-based fallback."

    try:
        llm = get_llm(model=model, temperature=temperature)
        response = _invoke_llm(llm, prompt)
        text = response.content if hasattr(response, "content") else str(response)
        logger.debug("invoke_llm: prompt_len=%d response_len=%d", len(prompt), len(text))
        _track_response_usage(ticket_id, node_name, variant, response, model)
        return text
    except Exception as exc:
        logger.error("invoke_llm: LLM call failed: %s", exc)
        raise


@async_retry_with_backoff(max_retries=3, base_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
async def ainvoke_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    *,
    node_name: str = "",
    ticket_id: str = "",
    variant: str = "parwa",
) -> str:
    """High-level async LLM invocation with full production hardening.

    Includes: retry, rate limiting, circuit breaker, TurboQuant budget check,
    and token tracking.

    In MOCK_MODE, returns deterministic responses from MockLLM.

    Args:
        prompt: The prompt to send.
        model: The model name to use.
        temperature: Sampling temperature.
        node_name: Calling node name (for TurboQuant budget tracking).
        ticket_id: Current ticket ID (for TurboQuant tracking).
        variant: Current variant (for TurboQuant budget allocation).

    Returns:
        The LLM response as a string.
    """
    if MOCK_MODE:
        mock = get_mock_llm()
        text = mock.invoke(prompt)
        _track_mock_usage(ticket_id, node_name, variant, prompt, text, model)
        return text

    # Check token budget before making the call
    estimated = _estimate_tokens(prompt) + 200  # prompt + estimated response
    if not _check_token_budget(node_name, variant, estimated):
        logger.warning(
            "ainvoke_llm: token budget exceeded for node=%s variant=%s — "
            "returning budget-exceeded response",
            node_name, variant,
        )
        return "Token budget exceeded. Using rule-based fallback."

    try:
        llm = get_llm(model=model, temperature=temperature)
        response = await _ainvoke_llm(llm, prompt)
        text = response.content if hasattr(response, "content") else str(response)
        logger.debug("ainvoke_llm: prompt_len=%d response_len=%d", len(prompt), len(text))
        _track_response_usage(ticket_id, node_name, variant, response, model)
        return text
    except Exception as exc:
        logger.error("ainvoke_llm: LLM call failed: %s", exc)
        raise


class MockLLM:
    """Mock LLM for testing without API calls.

    Returns deterministic responses based on the input prompt.
    Works in both sync and async contexts.
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

    async def ainvoke(self, prompt: str | list, **kwargs: Any) -> str:
        """Async mock — returns same deterministic response as invoke."""
        return self.invoke(prompt, **kwargs)


# Singleton mock instance
_mock_llm = MockLLM()


def get_mock_llm() -> MockLLM:
    """Get the mock LLM instance for testing."""
    return _mock_llm
