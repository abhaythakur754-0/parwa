import asyncio
from types import SimpleNamespace

import pytest

from app.core import redis as redis_module


class _UnavailableRedis:
    async def ping(self):
        raise ConnectionError("redis unavailable")


def test_production_redis_failure_does_not_fall_back_to_memory(monkeypatch):
    monkeypatch.setattr(
        redis_module,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://user:password@redis.example:6379/0",
            REDIS_PASSWORD="",
            is_production=True,
        ),
    )
    monkeypatch.setattr(redis_module.aioredis, "from_url", lambda *args, **kwargs: _UnavailableRedis())
    monkeypatch.setattr(redis_module, "_redis_client", None)
    monkeypatch.setattr(redis_module, "_redis_init_lock", asyncio.Lock())

    with pytest.raises(RuntimeError, match="Redis is unavailable in production"):
        asyncio.run(redis_module.get_redis())

    assert redis_module._redis_client is None
