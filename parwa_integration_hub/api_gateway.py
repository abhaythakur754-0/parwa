"""
Week 58 - Builder 1: API Gateway Module
Advanced API Gateway with rate limiting, routing, and response caching
"""

import time
import hashlib
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_second: int = 100
    burst_size: int = 150
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    key_extractor: Optional[Callable] = None


@dataclass
class Route:
    """API route definition"""
    path: str
    method: str
    handler: str
    rate_limit: Optional[RateLimitConfig] = None
    auth_required: bool = True
    cache_ttl: int = 0
    timeout: int = 30


@dataclass
class GatewayConfig:
    """Gateway configuration"""
    name: str
    routes: List[Route] = field(default_factory=list)
    default_rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    default_timeout: int = 30
    enable_cache: bool = True


class RateLimiter:
    """Rate limiter with multiple strategies"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_refill = time.time()
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def _refill_tokens(self):
        """Refill tokens based on rate"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.config.burst_size,
            self.tokens + elapsed * self.config.requests_per_second
        )
        self.last_refill = now

    def is_allowed(self, key: str = "default") -> bool:
        """Check if request is allowed"""
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                self._refill_tokens()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                return False

            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                now = time.time()
                window_start = now - 1.0  # 1 second window
                self.requests[key] = [
                    t for t in self.requests[key] if t > window_start
                ]
                if len(self.requests[key]) < self.config.requests_per_second:
                    self.requests[key].append(now)
                    return True
                return False

            else:  # FIXED_WINDOW
                now = time.time()
                window = int(now)
                window_key = f"{key}:{window}"
                if len(self.requests[window_key]) < self.config.requests_per_second:
                    self.requests[window_key].append(now)
                    return True
                return False

    def get_remaining(self, key: str = "default") -> int:
        """Get remaining requests"""
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                self._refill_tokens()
                return int(self.tokens)
            return max(0, self.config.requests_per_second - len(self.requests.get(key, [])))


class APIGateway:
    """
    Advanced API Gateway with rate limiting, routing, and authentication
    """

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.routes: Dict[str, Route] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()

        # Initialize routes
        for route in config.routes:
            key = f"{route.method}:{route.path}"
            self.routes[key] = route
            if route.rate_limit:
                self.rate_limiters[key] = RateLimiter(route.rate_limit)

        # Default rate limiter
        self.default_limiter = RateLimiter(config.default_rate_limit)

    def register_route(self, route: Route) -> None:
        """Register a new route"""
        key = f"{route.method}:{route.path}"
        with self.lock:
            self.routes[key] = route
            if route.rate_limit:
                self.rate_limiters[key] = RateLimiter(route.rate_limit)

    def get_route(self, method: str, path: str) -> Optional[Route]:
        """Get route by method and path"""
        key = f"{method}:{path}"
        return self.routes.get(key)

    def check_rate_limit(self, method: str, path: str, client_id: str = "default") -> bool:
        """Check if request is within rate limit"""
        key = f"{method}:{path}"
        limiter = self.rate_limiters.get(key, self.default_limiter)
        return limiter.is_allowed(client_id)

    def record_request(self, method: str, path: str) -> None:
        """Record a request"""
        key = f"{method}:{path}"
        with self.lock:
            self.request_counts[key] += 1

    def record_error(self, method: str, path: str) -> None:
        """Record an error"""
        key = f"{method}:{path}"
        with self.lock:
            self.error_counts[key] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics"""
        with self.lock:
            return {
                "total_requests": sum(self.request_counts.values()),
                "total_errors": sum(self.error_counts.values()),
                "routes": len(self.routes),
                "request_counts": dict(self.request_counts),
                "error_counts": dict(self.error_counts)
            }

    def list_routes(self) -> List[Dict[str, Any]]:
        """List all registered routes"""
        return [
            {
                "method": route.method,
                "path": route.path,
                "handler": route.handler,
                "auth_required": route.auth_required,
                "cache_ttl": route.cache_ttl
            }
            for route in self.routes.values()
        ]


class RequestRouter:
    """
    Request router with load balancing and failover support
    """

    def __init__(self):
        self.backends: Dict[str, List[str]] = defaultdict(list)
        self.backend_health: Dict[str, bool] = {}
        self.backend_index: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()

    def register_backend(self, service: str, url: str) -> None:
        """Register a backend for a service"""
        with self.lock:
            self.backends[service].append(url)
            self.backend_health[url] = True

    def unregister_backend(self, url: str) -> None:
        """Unregister a backend"""
        with self.lock:
            self.backend_health[url] = False

    def mark_healthy(self, url: str) -> None:
        """Mark backend as healthy"""
        with self.lock:
            self.backend_health[url] = True

    def mark_unhealthy(self, url: str) -> None:
        """Mark backend as unhealthy"""
        with self.lock:
            self.backend_health[url] = False

    def get_backend(self, service: str) -> Optional[str]:
        """Get next backend using round-robin"""
        with self.lock:
            backends = [
                b for b in self.backends[service]
                if self.backend_health.get(b, False)
            ]
            if not backends:
                return None

            index = self.backend_index[service] % len(backends)
            self.backend_index[service] += 1
            return backends[index]

    def get_all_backends(self, service: str) -> List[str]:
        """Get all backends for a service"""
        with self.lock:
            return [
                b for b in self.backends[service]
                if self.backend_health.get(b, False)
            ]

    def get_health_status(self) -> Dict[str, Dict[str, bool]]:
        """Get health status of all backends"""
        with self.lock:
            return {
                service: {
                    url: self.backend_health.get(url, False)
                    for url in urls
                }
                for service, urls in self.backends.items()
            }


class ResponseCache:
    """
    Response cache with TTL and invalidation support
    """

    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _generate_key(self, method: str, path: str, params: Dict = None) -> str:
        """Generate cache key"""
        content = f"{method}:{path}:{sorted(params.items()) if params else ''}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, method: str, path: str, params: Dict = None) -> Optional[Any]:
        """Get cached response"""
        key = self._generate_key(method, path, params)
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if time.time() < entry["expires"]:
                    return entry["data"]
                else:
                    del self.cache[key]
        return None

    def set(self, method: str, path: str, data: Any, ttl: int = None) -> None:
        """Cache a response"""
        key = self._generate_key(method, path)
        with self.lock:
            self.cache[key] = {
                "data": data,
                "expires": time.time() + (ttl or self.default_ttl),
                "created": time.time()
            }

    def invalidate(self, method: str, path: str) -> None:
        """Invalidate cache entry"""
        key = self._generate_key(method, path)
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all entries matching pattern"""
        count = 0
        with self.lock:
            keys_to_delete = [
                k for k in self.cache.keys()
                if pattern in k
            ]
            for key in keys_to_delete:
                del self.cache[key]
                count += 1
        return count

    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            now = time.time()
            valid_entries = sum(
                1 for entry in self.cache.values()
                if entry["expires"] > now
            )
            return {
                "total_entries": len(self.cache),
                "valid_entries": valid_entries,
                "expired_entries": len(self.cache) - valid_entries
            }
