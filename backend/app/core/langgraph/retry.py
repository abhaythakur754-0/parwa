"""LLM call retry with exponential backoff for LangGraph nodes.

All 19 LangGraph nodes call LLM APIs but had no retry with exponential
backoff. This shared utility provides a single entry point for wrapping
LLM calls with configurable retry behaviour.

Task ID 6 enhancements:
- Transient error classification: only retries on rate-limit, timeout,
  and connection errors. Does NOT retry on authentication or invalid
  request errors.
- Exponential backoff: 1s, 2s, 4s (base_delay=1.0, default 3 retries)
- Logs each retry attempt with error type classification.

Usage:
    from app.core.langgraph.retry import retry_llm_call, llm_call_with_retry

    # Generic retry (works with any callable):
    result = await retry_llm_call(
        my_llm_function, arg1, arg2,
        max_retries=3,
        base_delay=1.0,
    )

    # LLM-specific convenience wrapper (same behaviour, self-documenting):
    result = await llm_call_with_retry(
        generate_response, message, system_prompt="...",
        max_retries=3, base_delay=1.0,
    )

BC-008: Even if all retries fail the exception is re-raised so the
calling node can fall back to its own safe-default path.
"""

import asyncio
import logging
from typing import Any, Callable, Optional, Set, Tuple, Type

logger = logging.getLogger(__name__)


# ── Transient error classification ──────────────────────────────────

# HTTP status codes that indicate transient (retryable) errors
_TRANSIENT_STATUS_CODES: Set[int] = {
    429,  # Too Many Requests (rate limit)
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
    520,  # Web Server Unknown Error (Cloudflare)
    522,  # Connection Timed Out (Cloudflare)
    524,  # Timeout Occurred (Cloudflare)
}

# Exception class name substrings that indicate transient errors
_TRANSIENT_ERROR_PATTERNS: Tuple[str, ...] = (
    "ratelimit",
    "rate_limit",
    "throttl",
    "timeout",
    "timedout",
    "timed_out",
    "connectionerror",
    "connection_error",
    "connectionreset",
    "connection_reset",
    "connectionrefused",
    "connection_refused",
    "brokenpipe",
    "networkerror",
    "network_error",
    "serviceunavailable",
    "service_unavailable",
    "badgateway",
    "bad_gateway",
    "gatewaytimeout",
    "gateway_timeout",
    "servererror",
    "temporaryfailure",
    "temporary_failure",
    "overload",
    "capacity",
    "retryable",
    "retry_after",
)

# Exception class name substrings that indicate NON-retryable errors
# These should NOT be retried — they indicate a fundamental problem
_NON_RETRYABLE_ERROR_PATTERNS: Tuple[str, ...] = (
    "authentication",
    "auth_error",
    "unauthorized",
    "forbidden",
    "invalid_api_key",
    "invalidkey",
    "invalid_request",
    "invalidrequest",
    "badrequest",
    "bad_request",
    "validationerror",
    "validation_error",
    "invalidargument",
    "invalid_argument",
    "permissiondenied",
    "permission_denied",
    "notfound",
    "not_found",
    "methodnotallowed",
    "conflict",
    "payloadtoolarge",
    "unsupportedmediatype",
    "unprocessable",
)


def is_transient_error(exc: Exception) -> bool:
    """Classify whether an exception is transient (retryable).

    Transient errors include rate limits, timeouts, connection errors,
    and server errors (5xx). Non-retryable errors include authentication
    failures, invalid requests, and permission errors.

    Args:
        exc: The exception to classify.

    Returns:
        True if the exception is transient and should be retried.
    """
    exc_name = type(exc).__name__.lower()
    exc_message = str(exc).lower()

    # Check for HTTP status code in the exception
    status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status_code is not None:
        try:
            code = int(status_code)
            if code in _TRANSIENT_STATUS_CODES:
                return True
            if 400 <= code < 500:
                # Client errors (4xx) are generally not retryable
                # Exception: 429 (rate limit) which is already in _TRANSIENT_STATUS_CODES
                return False
            if code >= 500:
                # Server errors (5xx) are generally retryable
                return True
        except (ValueError, TypeError):
            pass

    # Check for non-retryable patterns first (takes precedence)
    for pattern in _NON_RETRYABLE_ERROR_PATTERNS:
        if pattern in exc_name or pattern in exc_message:
            return False

    # Check for transient patterns
    for pattern in _TRANSIENT_ERROR_PATTERNS:
        if pattern in exc_name or pattern in exc_message:
            return True

    # Check for common exception types by class hierarchy
    if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True

    # OSError with errno for connection-related issues
    if isinstance(exc, OSError):
        import errno
        transient_errnos = {
            errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED,
            errno.ETIMEDOUT, errno.ENETUNREACH, errno.EHOSTUNREACH,
        }
        if getattr(exc, "errno", None) in transient_errnos:
            return True

    # Default: NOT transient — safer to not retry unknown errors
    return False


async def retry_llm_call(
    fn: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    **kwargs,
) -> Any:
    """Call an LLM function with exponential backoff retry.

    Only retries on transient errors (rate limit, timeout, connection).
    Non-transient errors (authentication, invalid request) are re-raised
    immediately without retry.

    Args:
        fn: The async function to call (LLM API call)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay between retries (default: 10.0)

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries are exhausted or the error
        is non-transient.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        except Exception as exc:
            last_exception = exc

            # Classify the error
            transient = is_transient_error(exc)

            if not transient:
                # Non-transient error: don't retry, raise immediately
                logger.error(
                    "LLM call failed with non-transient error (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1,
                    str(exc)[:200],
                )
                raise

            if attempt == max_retries:
                logger.error(
                    "LLM call failed after %d retries (transient): %s",
                    max_retries, str(exc)[:200],
                )
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "LLM call attempt %d/%d failed (transient): %s. Retrying in %.1fs",
                attempt + 1, max_retries + 1, str(exc)[:100], delay,
            )
            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise last_exception


# ── Convenience wrapper ────────────────────────────────────────────


async def llm_call_with_retry(
    fn: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    **kwargs,
) -> Any:
    """Convenience wrapper around retry_llm_call for LLM API calls.

    Semantically identical to retry_llm_call but with an explicit name
    that makes it clear this is for LLM (Large Language Model) API
    invocations only. Use this in LangGraph nodes that call LLM
    endpoints so the intent is self-documenting.

    Retry policy:
      - Exponential backoff: 1s, 2s, 4s (base_delay=1.0, default 3 retries)
      - Only retries on transient errors (rate-limit, timeout, connection)
      - Does NOT retry on auth / invalid-request errors
      - Logs every retry attempt with error classification

    Args:
        fn: The async function to call (LLM API call)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay between retries (default: 10.0)

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries are exhausted or the error
        is non-transient.

    Example::

        from app.core.langgraph.retry import llm_call_with_retry

        result = await llm_call_with_retry(
            generate_response, message, system_prompt="...",
            max_retries=3, base_delay=1.0,
        )
    """
    return await retry_llm_call(
        fn, *args,
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        **kwargs,
    )
