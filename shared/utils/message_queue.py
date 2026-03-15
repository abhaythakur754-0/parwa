"""
Message Queue client for PARWA using Redis Streams.
Provides async publish/consume capabilities for background tasks.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger("message_queue")

# ---------------------------------------------------------------------------
# Known stream name constants
# ---------------------------------------------------------------------------
STREAM_AGENT_LIGHTNING = "parwa:agent_lightning"
STREAM_NOTIFICATIONS   = "parwa:notifications"
STREAM_WEBHOOKS        = "parwa:webhooks"


class MessageQueueError(Exception):
    """Base exception for MessageQueue errors."""


class MessageQueue:
    """Async Redis Streams message queue client."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """Open a connection to Redis."""
        self._redis = await aioredis.from_url(
            str(self._settings.redis_url),
            decode_responses=True,
        )

    def _ensure_connected(self) -> aioredis.Redis:
        if self._redis is None:
            raise MessageQueueError("MessageQueue is not connected. Call `await connect()` first.")
        return self._redis

    # ------------------------------------------------------------------
    # publish
    # ------------------------------------------------------------------
    async def publish(self, stream: str, message: dict) -> str:
        """
        Publish a message to a named Redis Stream.

        Auto-injects ``id`` and ``published_at`` into the message.
        Returns the Redis message ID produced by XADD.
        """
        redis = self._ensure_connected()
        payload = {
            **message,
            "id": str(uuid.uuid4()),
            "published_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            msg_id: str = await redis.xadd(stream, payload)
            logger.info(
                "Message published",
                extra={"context": {"stream": stream, "msg_id": msg_id}},
            )
            return msg_id
        except Exception as exc:
            logger.error(
                f"Failed to publish to stream '{stream}': {exc}",
                extra={"context": {"stream": stream}},
            )
            raise MessageQueueError(str(exc)) from exc

    # ------------------------------------------------------------------
    # consume
    # ------------------------------------------------------------------
    async def consume(
        self, stream: str, group: str, consumer: str, count: int = 10
    ) -> list[dict]:
        """
        Read up to *count* pending messages from a Consumer Group via XREADGROUP.

        Creates the consumer group on first call if it does not exist.
        Returns a list of deserialized message dicts. Never raises.
        """
        redis = self._ensure_connected()
        # Create group if missing ─────────────────────────────────────
        try:
            await redis.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                logger.warning(
                    f"Unexpected error creating group '{group}': {exc}",
                    extra={"context": {"stream": stream, "group": group}},
                )

        try:
            raw: list = await redis.xreadgroup(
                group, consumer, streams={stream: ">"}, count=count
            )
            messages: list[dict] = []
            if raw:
                for _stream, entries in raw:
                    for msg_id, fields in entries:
                        messages.append({"_id": msg_id, **fields})
            logger.info(
                f"Consumed {len(messages)} messages",
                extra={"context": {"stream": stream, "group": group, "count": len(messages)}},
            )
            return messages
        except Exception as exc:
            logger.error(
                f"Failed to consume from stream '{stream}': {exc}",
                extra={"context": {"stream": stream, "group": group}},
            )
            return []

    # ------------------------------------------------------------------
    # acknowledge
    # ------------------------------------------------------------------
    async def acknowledge(self, stream: str, group: str, message_id: str) -> bool:
        """Acknowledge a processed message via XACK. Returns True on success."""
        redis = self._ensure_connected()
        try:
            await redis.xack(stream, group, message_id)
            return True
        except Exception as exc:
            logger.error(
                f"Failed to acknowledge message '{message_id}': {exc}",
                extra={"context": {"stream": stream, "group": group, "message_id": message_id}},
            )
            return False

    # ------------------------------------------------------------------
    # get_pending_count
    # ------------------------------------------------------------------
    async def get_pending_count(self, stream: str, group: str) -> int:
        """Return the number of unacknowledged messages in a group via XPENDING."""
        redis = self._ensure_connected()
        try:
            summary = await redis.xpending(stream, group)
            return summary.get("pending", 0) if isinstance(summary, dict) else 0
        except Exception as exc:
            logger.error(
                f"Failed to get pending count for group '{group}': {exc}",
                extra={"context": {"stream": stream, "group": group}},
            )
            return 0


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_mq: Optional[MessageQueue] = None


async def get_message_queue() -> MessageQueue:
    """Return a connected singleton MessageQueue instance."""
    global _mq
    if _mq is None:
        _mq = MessageQueue()
        await _mq.connect()
    return _mq
