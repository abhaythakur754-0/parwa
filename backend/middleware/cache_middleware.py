"""
Cache Middleware for PARWA Performance Optimization.

Week 26 - Builder 4: API Response Caching + Compression
Target: Middleware caches correctly, ETag support, Cache-Control headers

Features:
- Intercept GET requests
- Check Redis cache first
- Cache successful responses (200 only)
- Set Cache-Control headers
- ETag support for conditional requests
"""

import hashlib
import json
import time
import logging
from typing import Optional, Callable, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Send, Scope

logger = logging.getLogger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for caching API responses.

    Features:
    - Caches GET requests in Redis
    - ETag support for conditional requests
    - Cache-Control header management
    - Bypass for non-cacheable requests
    """

    # Methods that should not be cached
    CACHEABLE_METHODS = {"GET", "HEAD"}

    # Status codes that should be cached
    CACHEABLE_STATUS_CODES = {200}

    # Endpoints to skip caching
    SKIP_PATHS = {
        "/api/v1/health",
        "/api/v1/metrics",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/logout",
        "/api/v1/webhooks",
    }

    # Default TTL by endpoint pattern (in seconds)
    TTL_PATTERNS = {
        "/api/v1/dashboard": 30,
        "/api/v1/tickets": 60,
        "/api/v1/approvals": 30,
        "/api/v1/analytics": 300,
        "/api/v1/settings": 300,
        "/api/v1/faq": 3600,
        "/api/v1/kb": 3600,
    }

    def __init__(
        self,
        app: ASGIApp,
        cache_client: Optional[Any] = None,
        default_ttl: int = 60
    ):
        """
        Initialize cache middleware.

        Args:
            app: ASGI application.
            cache_client: Cache client (Redis or local).
            default_ttl: Default cache TTL in seconds.
        """
        super().__init__(app)
        self.cache_client = cache_client
        self.default_ttl = default_ttl

    def _should_cache(self, request: Request) -> bool:
        """
        Determine if request should be cached.

        Args:
            request: FastAPI request.

        Returns:
            True if request should be cached.
        """
        # Only cache GET/HEAD
        if request.method not in self.CACHEABLE_METHODS:
            return False

        # Skip certain paths
        path = request.url.path
        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return False

        return True

    def _get_ttl_for_path(self, path: str) -> int:
        """
        Get TTL for a specific path.

        Args:
            path: Request path.

        Returns:
            TTL in seconds.
        """
        for pattern, ttl in self.TTL_PATTERNS.items():
            if path.startswith(pattern):
                return ttl
        return self.default_ttl

    def _generate_cache_key(self, request: Request) -> str:
        """
        Generate cache key for request.

        Args:
            request: FastAPI request.

        Returns:
            Cache key string.
        """
        # Get client ID from headers or state
        client_id = getattr(request.state, "client_id", "anonymous")

        # Include path and query params
        path = request.url.path
        query = str(request.query_params)

        # Generate hash
        content = f"{client_id}:{path}:{query}"
        key_hash = hashlib.md5(content.encode()).hexdigest()[:16]

        return f"parwa:middleware:cache:{client_id}:{key_hash}"

    def _generate_etag(self, content: bytes) -> str:
        """
        Generate ETag for response content.

        Args:
            content: Response body bytes.

        Returns:
            ETag string.
        """
        return hashlib.md5(content).hexdigest()

    async def _get_cached_response(self, key: str) -> Optional[Dict]:
        """
        Get cached response from store.

        Args:
            key: Cache key.

        Returns:
            Cached response dict or None.
        """
        if not self.cache_client:
            return None

        try:
            cached = await self._cache_get(key)
            if cached:
                return {
                    "content": cached.get("content"),
                    "etag": cached.get("etag"),
                    "headers": cached.get("headers", {}),
                    "status_code": cached.get("status_code", 200),
                }
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")

        return None

    async def _cache_response(
        self,
        key: str,
        content: bytes,
        etag: str,
        headers: Dict,
        status_code: int,
        ttl: int
    ) -> None:
        """
        Cache a response.

        Args:
            key: Cache key.
            content: Response content.
            etag: ETag string.
            headers: Response headers.
            status_code: HTTP status code.
            ttl: TTL in seconds.
        """
        if not self.cache_client:
            return

        try:
            await self._cache_set(key, {
                "content": content.decode() if isinstance(content, bytes) else content,
                "etag": etag,
                "headers": headers,
                "status_code": status_code,
            }, ttl)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through cache middleware.

        Args:
            request: FastAPI request.
            call_next: Next middleware/handler.

        Returns:
            Response.
        """
        # Check if request should be cached
        if not self._should_cache(request):
            return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Check for If-None-Match header (conditional request)
        if_none_match = request.headers.get("if-none-match")

        # Try to get cached response
        cached = await self._get_cached_response(cache_key)

        if cached:
            etag = cached.get("etag")

            # Check if client has fresh copy
            if if_none_match and if_none_match == etag:
                return Response(status_code=304, headers={"ETag": etag})

            # Return cached response
            headers = dict(cached.get("headers", {}))
            headers["ETag"] = etag
            headers["X-Cache"] = "HIT"
            headers["Cache-Control"] = f"max-age={self._get_ttl_for_path(request.url.path)}"

            return JSONResponse(
                content=json.loads(cached["content"]) if isinstance(cached["content"], str) else cached["content"],
                status_code=cached.get("status_code", 200),
                headers=headers
            )

        # Process request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code in self.CACHEABLE_STATUS_CODES:
            # Get response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Generate ETag
            etag = self._generate_etag(response_body)

            # Get TTL
            ttl = self._get_ttl_for_path(request.url.path)

            # Cache response
            await self._cache_response(
                cache_key,
                response_body,
                etag,
                dict(response.headers),
                response.status_code,
                ttl
            )

            # Create new response with cache headers
            headers = dict(response.headers)
            headers["ETag"] = etag
            headers["X-Cache"] = "MISS"
            headers["Cache-Control"] = f"max-age={ttl}"

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type
            )

        # Return non-cacheable response
        response.headers["X-Cache"] = "BYPASS"
        return response

    # Cache client helper methods
    async def _cache_get(self, key: str) -> Optional[Dict]:
        """Get from cache client."""
        if hasattr(self.cache_client, "get"):
            return await self.cache_client.get(key)
        return None

    async def _cache_set(self, key: str, value: Dict, ttl: int) -> None:
        """Set in cache client."""
        if hasattr(self.cache_client, "set"):
            await self.cache_client.set(key, value, ttl=ttl)


def setup_cache_middleware(app: ASGIApp, cache_client: Optional[Any] = None) -> None:
    """
    Setup cache middleware on FastAPI app.

    Args:
        app: FastAPI application.
        cache_client: Cache client instance.
    """
    app.add_middleware(CacheMiddleware, cache_client=cache_client)


__all__ = [
    "CacheMiddleware",
    "setup_cache_middleware",
]
