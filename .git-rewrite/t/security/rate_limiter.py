"""
Redis-backed rate limiting utility for PARWA.
"""
from shared.utils.cache import Cache
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    Fixed-window rate limiter using Redis.
    """
    def __init__(self):
        self.cache = Cache()

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        Check if a request is allowed based on a key (e.g., IP or User ID).
        
        Args:
            key: Unique identifier for the rate limit.
            limit: Maximum requests allowed in the window.
            window: Time window in seconds.
            
        Returns:
            True if allowed, False if limit exceeded.
        """
        redis_key = f"rate_limit:{key}"
        try:
            conn = await self.cache._get_conn()
            
            # Atomic increment
            count = await conn.incr(redis_key)
            
            # If this is a new key, set the expiration
            if count == 1:
                await conn.expire(redis_key, window)
            
            if count > limit:
                logger.warning("rate_limit_exceeded", extra={"context": {"key": key, "count": count, "limit": limit}})
                return False
                
            return True
        except Exception as e:
            logger.error("rate_limiter_error", extra={"context": {"key": key, "error": str(e)}})
            # Fail open to avoid blocking users if Redis is down, but log the error
            return True

    async def close(self):
        """Clean up resources."""
        await self.cache.close()
