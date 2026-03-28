"""
Backend Middleware Module for PARWA.

Week 26 - Builder 4: API Response Caching + Compression

Middleware components:
- cache_middleware: API response caching
- compression_middleware: Gzip/Brotli compression
- rate_limit_middleware: Token bucket rate limiting
"""

from backend.middleware.cache_middleware import (
    CacheMiddleware,
    setup_cache_middleware,
)

from backend.middleware.compression_middleware import (
    CompressionMiddleware,
    setup_compression_middleware,
)

from backend.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
    TokenBucket,
    setup_rate_limit_middleware,
)


__all__ = [
    "CacheMiddleware",
    "setup_cache_middleware",
    "CompressionMiddleware",
    "setup_compression_middleware",
    "RateLimitMiddleware",
    "TokenBucket",
    "setup_rate_limit_middleware",
]
