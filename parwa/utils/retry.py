"""Retry logic for PARWA nodes and LLM calls.

Provides exponential backoff retry with jitter for resilience
against transient failures (LLM timeouts, rate limits, network errors).
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger("parwa.retry")

F = TypeVar("F", bound=Callable[..., Any])

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_BACKOFF_FACTOR = 2.0

# Exceptions that are retryable (transient errors)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    retryable_exceptions: tuple[type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts (0 = no retries).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay cap in seconds.
        backoff_factor: Multiplier for each successive delay.
        retryable_exceptions: Exception types that trigger a retry.
        on_retry: Optional callback(attempt, exception) called before each retry.

    Returns:
        Decorated function with retry logic.

    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def call_llm(prompt):
            return llm.invoke(prompt)
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt >= max_retries:
                        logger.error(
                            "retry_with_backoff: %s failed after %d attempts: %s",
                            func.__name__, attempt + 1, exc,
                        )
                        raise

                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay * (backoff_factor ** attempt),
                        max_delay,
                    )
                    jitter = random.uniform(0, delay * 0.25)
                    total_delay = delay + jitter

                    logger.warning(
                        "retry_with_backoff: %s attempt %d/%d failed (%s), "
                        "retrying in %.1fs",
                        func.__name__, attempt + 1, max_retries + 1,
                        type(exc).__name__, total_delay,
                    )

                    if on_retry:
                        on_retry(attempt + 1, exc)

                    time.sleep(total_delay)
                except Exception as exc:
                    # Non-retryable exception — raise immediately
                    logger.error(
                        "retry_with_backoff: %s failed with non-retryable %s: %s",
                        func.__name__, type(exc).__name__, exc,
                    )
                    raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"retry_with_backoff: unexpected state for {func.__name__}")

        return wrapper  # type: ignore[return-value]

    return decorator
