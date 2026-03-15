"""
Unit tests for shared/utils/message_queue.py
All Redis calls are mocked — no live Redis required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers: build a mock redis instance
# ---------------------------------------------------------------------------
def _make_mock_redis(
    xadd_return="1234567890-0",
    xgroup_create_side_effect=None,
    xreadgroup_return=None,
    xack_return=1,
    xpending_return=None,
):
    r = AsyncMock()
    r.xadd = AsyncMock(return_value=xadd_return)
    r.xgroup_create = AsyncMock(side_effect=xgroup_create_side_effect)
    r.xreadgroup = AsyncMock(return_value=xreadgroup_return or [])
    r.xack = AsyncMock(return_value=xack_return)
    r.xpending = AsyncMock(return_value=xpending_return or {"pending": 0})
    return r


# ---------------------------------------------------------------------------
# Fixture: connected MessageQueue with mocked redis
# ---------------------------------------------------------------------------
@pytest.fixture()
def mq_instance():
    """Return a MessageQueue that is already 'connected' to a mock Redis."""
    from shared.utils.message_queue import MessageQueue

    instance = MessageQueue.__new__(MessageQueue)
    instance._settings = MagicMock()
    instance._settings.redis_url = "redis://localhost:6379"
    instance._redis = _make_mock_redis()
    return instance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_returns_message_id(mq_instance):
    """publish() should return the Redis message ID string."""
    msg_id = await mq_instance.publish("parwa:test", {"event": "ping"})
    assert msg_id == "1234567890-0"


@pytest.mark.asyncio
async def test_publish_auto_adds_id_and_published_at(mq_instance):
    """publish() must inject 'id' and 'published_at' into the payload."""
    capture = {}

    async def fake_xadd(stream, payload):
        capture.update(payload)
        return "1234567890-0"

    mq_instance._redis.xadd = fake_xadd
    await mq_instance.publish("parwa:test", {"event": "ping"})
    assert "id" in capture
    assert "published_at" in capture
    assert "event" in capture


@pytest.mark.asyncio
async def test_publish_raises_on_redis_error(mq_instance):
    """publish() must raise MessageQueueError when Redis fails."""
    from shared.utils.message_queue import MessageQueueError

    mq_instance._redis.xadd = AsyncMock(side_effect=Exception("connection refused"))
    with pytest.raises(MessageQueueError):
        await mq_instance.publish("parwa:test", {"event": "fail"})


@pytest.mark.asyncio
async def test_consume_returns_list(mq_instance):
    """consume() should deserialize Redis entries into list of dicts."""
    mq_instance._redis.xreadgroup = AsyncMock(
        return_value=[("parwa:test", [("1234567890-0", {"event": "ping", "id": "abc"})])]
    )
    results = await mq_instance.consume("parwa:test", "group1", "consumer1")
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["event"] == "ping"
    assert results[0]["_id"] == "1234567890-0"


@pytest.mark.asyncio
async def test_consume_creates_group_if_not_exists(mq_instance):
    """consume() should attempt to create the consumer group before reading."""
    await mq_instance.consume("parwa:test", "new_group", "consumer1")
    mq_instance._redis.xgroup_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_returns_empty_on_error(mq_instance):
    """consume() must return empty list instead of raising on Redis error."""
    mq_instance._redis.xgroup_create = AsyncMock(return_value=None)
    mq_instance._redis.xreadgroup = AsyncMock(side_effect=Exception("stream error"))
    result = await mq_instance.consume("parwa:test", "group1", "consumer1")
    assert result == []


@pytest.mark.asyncio
async def test_acknowledge_returns_true_on_success(mq_instance):
    """acknowledge() should return True when XACK succeeds."""
    result = await mq_instance.acknowledge("parwa:test", "group1", "1234567890-0")
    assert result is True


@pytest.mark.asyncio
async def test_get_pending_count_returns_zero_on_error(mq_instance):
    """get_pending_count() must return 0 when XPENDING raises."""
    mq_instance._redis.xpending = AsyncMock(side_effect=Exception("xpending failed"))
    count = await mq_instance.get_pending_count("parwa:test", "group1")
    assert count == 0
