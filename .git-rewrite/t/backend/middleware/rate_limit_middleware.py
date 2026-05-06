"""
Rate Limit Middleware for PARWA Performance Optimization.

Week 26 - Builder 4: API Response Caching + Compression
Target: Rate limiting works, 100 req/min per client, burst 20

Features:
- Token bucket algorithm
- Rate: 100 requests/minute per client
- Burst: 20 requests
- Rate limit headers in response
- 429 response with retry-after
"""

import time
import logging
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    tokens: float
    last_update: float
    capacity: float
    refill_rate: float  # tokens per second


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Features:
    - Token bucket algorithm
    - Per-client rate limiting
    - Configurable rate and burst
    - Rate limit headers in response
    """

    # Default rate limits
    DEFAULT_RATE = 100  # requests per minute
    DEFAULT_BURST = 20  # burst capacity

    # Paths to skip rate limiting
    SKIP_PATHS = {
        "/api/v1/health",
        "/api/v1/metrics",
    }

    def __init__(
        self,
        app: ASGIApp,
        rate: int = DEFAULT_RATE,
        burst: int = DEFAULT_BURST,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: ASGI application.
            rate: Maximum requests per minute.
            burst: Burst capacity.
            redis_client: Optional Redis client for distributed rate limiting.
        """
        super().__init__(app)
        self.rate = rate
        self.burst = burst
        self.redis_client = redis_client
        self.refill_rate = rate / 60.0  # tokens per second

        # Local token buckets (for single-instance deployment)
        self._buckets: Dict[str, TokenBucket] = {}

    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier from request.

        Args:
            request: FastAPI request.

        Returns:
            Client identifier string.
        """
        # Try to get from state
        client_id = getattr(request.state, "client_id", None)
        if client_id:
            return f"client:{client_id}"

        # Try to get from header
        client_id = request.headers.get("x-client-id")
        if client_id:
            return f"client:{client_id}"

        # Fall back to IP
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _should_rate_limit(self, request: Request) -> bool:
        """
        Determine if request should be rate limited.

        Args:
            request: FastAPI request.

        Returns:
            True if request should be rate limited.
        """
        path = request.url.path
        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return False
        return True

    def _get_bucket(self, client_id: str) -> TokenBucket:
        """
        Get or create token bucket for client.

        Args:
            client_id: Client identifier.

        Returns:
            TokenBucket instance.
        """
        if client_id not in self._buckets:
            self._buckets[client_id] = TokenBucket(
                tokens=self.burst,
                last_update=time.time(),
                capacity=self.burst,
                refill_rate=self.refill_rate
            )
        return self._buckets[client_id]

    def _refill_bucket(self, bucket: TokenBucket) -> None:
        """
        Refill tokens in bucket based on elapsed time.

        Args:
            bucket: Token bucket to refill.
        """
        now = time.time()
        elapsed = now - bucket.last_update

        # Calculate tokens to add
        tokens_to_add = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_update = now

    def _consume_token(self, bucket: TokenBucket) -> bool:
        """
        Try to consume a token from bucket.

        Args:
            bucket: Token bucket.

        Returns:
            True if token was consumed, False if rate limited.
        """
        self._refill_bucket(bucket)

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True
        return False

    def _get_remaining(self, bucket: TokenBucket) -> int:
        """
        Get remaining tokens in bucket.

        Args:
            bucket: Token bucket.

        Returns:
            Number of remaining tokens.
        """
        self._refill_bucket(bucket)
        return int(bucket.tokens)

    def _get_retry_after(self, bucket: TokenBucket) -> int:
        """
        Calculate seconds until a token is available.

        Args:
            bucket: Token bucket.

        Returns:
            Seconds until retry.
        """
        tokens_needed = 1 - bucket.tokens
        return max(1, int(tokens_needed / bucket.refill_rate))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through rate limit middleware.

        Args:
            request: FastAPI request.
            call_next: Next middleware/handler.

        Returns:
            Response.
        """
        # Check if should rate limit
        if not self._should_rate_limit(request):
            return await call_next(request)

        # Get client ID
        client_id = self._get_client_id(request)

        # Get bucket
        bucket = self._get_bucket(client_id)

        # Try to consume token
        if not self._consume_token(bucket):
            # Rate limited
            retry_after = self._get_retry_after(bucket)

            logger.warning(f"Rate limited: {client_id}")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.rate),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate)
        response.headers["X-RateLimit-Remaining"] = str(self._get_remaining(bucket))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

        return response

    def cleanup_old_buckets(self, max_age: int = 3600) -> int:
        """
        Remove old inactive buckets.

        Args:
            max_age: Maximum age in seconds.

        Returns:
            Number of buckets removed.
        """
        now = time.time()
        to_remove = []

        for client_id, bucket in self._buckets.items():
            if now - bucket.last_update > max_age:
                to_remove.append(client_id)

        for client_id in to_remove:
            del self._buckets[client_id]

        return len(to_remove)


def setup_rate_limit_middleware(
    app: ASGIApp,
    rate: int = 100,
    burst: int = 20
) -> None:
    """
    Setup rate limit middleware on FastAPI app.

    Args:
        app: FastAPI application.
        rate: Maximum requests per minute.
        burst: Burst capacity.
    """
    app.add_middleware(RateLimitMiddleware, rate=rate, burst=burst)


__all__ = [
    "TokenBucket",
    "RateLimitMiddleware",
    "setup_rate_limit_middleware",
]
