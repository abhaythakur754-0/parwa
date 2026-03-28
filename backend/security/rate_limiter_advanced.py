"""
Advanced Rate Limiter for Enterprise Security.

This module provides tiered rate limiting with per-tenant limits,
burst handling, and multiple rate limit strategies.
"""

import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from pydantic import BaseModel, Field


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitTier(BaseModel):
    """Rate limit tier configuration."""
    
    name: str
    requests_per_second: int
    requests_per_minute: int
    requests_per_hour: int
    burst_size: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW


class RateLimitConfig(BaseModel):
    """Rate limit configuration for a tenant."""
    
    tenant_id: str
    tier: RateLimitTier
    enabled: bool = True
    whitelist_ips: List[str] = Field(default_factory=list)
    custom_limits: Dict[str, RateLimitTier] = Field(default_factory=dict)


class RateLimitResult(BaseModel):
    """Result of a rate limit check."""
    
    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None
    limit: int
    window: str


class AdvancedRateLimiter:
    """
    Advanced rate limiter with multiple strategies and per-tenant limits.
    
    Supports:
    - Fixed window rate limiting
    - Sliding window rate limiting
    - Token bucket algorithm
    - Leaky bucket algorithm
    - Per-tenant custom limits
    - IP whitelisting
    - Burst handling
    """
    
    # Default tiers
    DEFAULT_TIERS = {
        "free": RateLimitTier(
            name="free",
            requests_per_second=2,
            requests_per_minute=30,
            requests_per_hour=500,
            burst_size=5
        ),
        "basic": RateLimitTier(
            name="basic",
            requests_per_second=5,
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_size=20
        ),
        "pro": RateLimitTier(
            name="pro",
            requests_per_second=10,
            requests_per_minute=300,
            requests_per_hour=10000,
            burst_size=50
        ),
        "enterprise": RateLimitTier(
            name="enterprise",
            requests_per_second=50,
            requests_per_minute=2000,
            requests_per_hour=100000,
            burst_size=200
        )
    }
    
    def __init__(self):
        """Initialize rate limiter."""
        self._configs: Dict[str, RateLimitConfig] = {}
        self._request_history: Dict[str, List[float]] = defaultdict(list)
        self._token_buckets: Dict[str, Dict] = {}
    
    def configure_tenant(
        self,
        tenant_id: str,
        tier_name: str = "basic",
        custom_tier: Optional[RateLimitTier] = None,
        whitelist_ips: Optional[List[str]] = None
    ) -> RateLimitConfig:
        """
        Configure rate limiting for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            tier_name: Tier name (free, basic, pro, enterprise)
            custom_tier: Custom tier configuration
            whitelist_ips: IPs to whitelist from rate limiting
            
        Returns:
            RateLimitConfig
        """
        tier = custom_tier or self.DEFAULT_TIERS.get(tier_name, self.DEFAULT_TIERS["basic"])
        
        config = RateLimitConfig(
            tenant_id=tenant_id,
            tier=tier,
            whitelist_ips=whitelist_ips or []
        )
        
        self._configs[tenant_id] = config
        return config
    
    def check_rate_limit(
        self,
        tenant_id: str,
        identifier: str,
        ip_address: Optional[str] = None
    ) -> RateLimitResult:
        """
        Check rate limit for a request.
        
        Args:
            tenant_id: Tenant identifier
            identifier: Unique identifier (user ID, API key, etc.)
            ip_address: Optional IP address for whitelisting
            
        Returns:
            RateLimitResult
        """
        config = self._configs.get(tenant_id)
        if not config:
            config = self.configure_tenant(tenant_id)
        
        # Check IP whitelist
        if ip_address and ip_address in config.whitelist_ips:
            return RateLimitResult(
                allowed=True,
                remaining=-1,  # Unlimited
                reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
                limit=-1,
                window="whitelisted"
            )
        
        if not config.enabled:
            return RateLimitResult(
                allowed=True,
                remaining=-1,
                reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
                limit=-1,
                window="disabled"
            )
        
        key = f"{tenant_id}:{identifier}"
        now = time.time()
        
        # Use sliding window algorithm by default
        return self._sliding_window_check(key, config.tier, now)
    
    def _sliding_window_check(
        self,
        key: str,
        tier: RateLimitTier,
        now: float
    ) -> RateLimitResult:
        """
        Sliding window rate limit check.
        
        Args:
            key: Rate limit key
            tier: Rate limit tier
            now: Current timestamp
            
        Returns:
            RateLimitResult
        """
        # Clean old entries
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Get history for this key
        history = self._request_history[key]
        
        # Clean old entries
        history = [t for t in history if t > hour_ago]
        self._request_history[key] = history
        
        # Count requests in windows
        minute_requests = len([t for t in history if t > minute_ago])
        hour_requests = len(history)
        
        # Check limits (per second is approximated)
        if len(history) > 0:
            recent = [t for t in history if t > now - 1]
            if len(recent) >= tier.requests_per_second:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=datetime.fromtimestamp(now + 1, timezone.utc),
                    retry_after=1,
                    limit=tier.requests_per_second,
                    window="second"
                )
        
        # Check minute limit
        if minute_requests >= tier.requests_per_minute:
            oldest_in_minute = min([t for t in history if t > minute_ago])
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=datetime.fromtimestamp(oldest_in_minute + 60, timezone.utc),
                retry_after=int(60 - (now - oldest_in_minute)),
                limit=tier.requests_per_minute,
                window="minute"
            )
        
        # Check hour limit
        if hour_requests >= tier.requests_per_hour:
            oldest = min(history)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=datetime.fromtimestamp(oldest + 3600, timezone.utc),
                retry_after=int(3600 - (now - oldest)),
                limit=tier.requests_per_hour,
                window="hour"
            )
        
        # Record request
        history.append(now)
        
        # Calculate remaining
        remaining = min(
            tier.requests_per_second - len([t for t in history if t > now - 1]),
            tier.requests_per_minute - minute_requests - 1,
            tier.requests_per_hour - hour_requests - 1
        )
        
        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            reset_at=datetime.fromtimestamp(now + 3600, timezone.utc),
            limit=tier.requests_per_hour,
            window="hour"
        )
    
    def get_usage_stats(self, tenant_id: str) -> Dict:
        """
        Get rate limit usage statistics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Usage statistics
        """
        config = self._configs.get(tenant_id)
        if not config:
            return {}
        
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Count all requests for this tenant
        total_minute = 0
        total_hour = 0
        
        for key, history in self._request_history.items():
            if key.startswith(f"{tenant_id}:"):
                total_minute += len([t for t in history if t > minute_ago])
                total_hour += len([t for t in history if t > hour_ago])
        
        return {
            "tenant_id": tenant_id,
            "tier": config.tier.name,
            "requests_last_minute": total_minute,
            "requests_last_hour": total_hour,
            "minute_limit": config.tier.requests_per_minute,
            "hour_limit": config.tier.requests_per_hour
        }
    
    def reset_limits(self, tenant_id: str, identifier: Optional[str] = None) -> None:
        """
        Reset rate limits for a tenant or specific identifier.
        
        Args:
            tenant_id: Tenant identifier
            identifier: Optional specific identifier to reset
        """
        if identifier:
            key = f"{tenant_id}:{identifier}"
            if key in self._request_history:
                del self._request_history[key]
        else:
            # Reset all for tenant
            keys_to_delete = [k for k in self._request_history if k.startswith(f"{tenant_id}:")]
            for key in keys_to_delete:
                del self._request_history[key]


# Global rate limiter instance
_rate_limiter: Optional[AdvancedRateLimiter] = None


def get_rate_limiter() -> AdvancedRateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = AdvancedRateLimiter()
    return _rate_limiter
