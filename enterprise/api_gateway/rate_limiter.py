"""Rate Limiter - Token bucket and sliding window rate limiting"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import time
import threading

logger = logging.getLogger(__name__)

class RateLimitStrategy(str, Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"

@dataclass
class RateLimitConfig:
    requests_per_second: int = 10
    burst_size: int = 20
    window_size_seconds: int = 60

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None

class RateLimiter:
    def __init__(self, strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET):
        self.strategy = strategy
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._metrics = {"total_requests": 0, "rate_limited": 0}

    def check_rate_limit(self, key: str, config: RateLimitConfig) -> RateLimitResult:
        self._metrics["total_requests"] += 1
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = self._init_bucket(config)
            bucket = self._buckets[key]
            now = time.time()

            if self.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._token_bucket_check(key, bucket, config, now)
            elif self.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return self._sliding_window_check(key, bucket, config, now)
            else:
                return self._fixed_window_check(key, bucket, config, now)

    def _init_bucket(self, config: RateLimitConfig) -> Dict[str, Any]:
        return {"tokens": config.burst_size, "last_update": time.time(), "requests": []}

    def _token_bucket_check(self, key: str, bucket: Dict, config: RateLimitConfig, now: float) -> RateLimitResult:
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(config.burst_size, bucket["tokens"] + elapsed * config.requests_per_second)
        bucket["last_update"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return RateLimitResult(allowed=True, remaining=int(bucket["tokens"]), reset_at=now + 1)
        else:
            self._metrics["rate_limited"] += 1
            return RateLimitResult(allowed=False, remaining=0, reset_at=now + (1 / config.requests_per_second), retry_after=1 / config.requests_per_second)

    def _sliding_window_check(self, key: str, bucket: Dict, config: RateLimitConfig, now: float) -> RateLimitResult:
        window_start = now - config.window_size_seconds
        bucket["requests"] = [t for t in bucket["requests"] if t > window_start]

        if len(bucket["requests"]) < config.requests_per_second * config.window_size_seconds:
            bucket["requests"].append(now)
            return RateLimitResult(allowed=True, remaining=int(config.requests_per_second * config.window_size_seconds - len(bucket["requests"])), reset_at=now + config.window_size_seconds)
        else:
            self._metrics["rate_limited"] += 1
            return RateLimitResult(allowed=False, remaining=0, reset_at=bucket["requests"][0] + config.window_size_seconds, retry_after=bucket["requests"][0] + config.window_size_seconds - now)

    def _fixed_window_check(self, key: str, bucket: Dict, config: RateLimitConfig, now: float) -> RateLimitResult:
        window_start = int(now // config.window_size_seconds) * config.window_size_seconds
        window_key = f"{key}:{window_start}"

        if "count" not in bucket or bucket.get("window_start") != window_start:
            bucket["count"] = 0
            bucket["window_start"] = window_start

        if bucket["count"] < config.requests_per_second * config.window_size_seconds:
            bucket["count"] += 1
            return RateLimitResult(allowed=True, remaining=int(config.requests_per_second * config.window_size_seconds - bucket["count"]), reset_at=window_start + config.window_size_seconds)
        else:
            self._metrics["rate_limited"] += 1
            return RateLimitResult(allowed=False, remaining=0, reset_at=window_start + config.window_size_seconds, retry_after=window_start + config.window_size_seconds - now)

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics, "active_buckets": len(self._buckets)}
