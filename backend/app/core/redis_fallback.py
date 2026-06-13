"""
Redis Fallback — Uses fakeredis when real Redis is unavailable.

This module provides a drop-in replacement for the redis.asyncio client
when Redis server is not running locally. It patches the get_redis()
function to return a fakeredis client instead.

BC-012: Graceful degradation — app works without real Redis.
"""

import fakeredis.aioredis

_fake_redis = None

async def get_fake_redis():
    """Get or create a fakeredis async client."""
    global _fake_redis
    if _fake_redis is None:
        _fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return _fake_redis
