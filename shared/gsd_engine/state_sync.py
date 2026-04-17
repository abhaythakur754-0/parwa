"""
GSD State Synchronization (GSD-2)

Synchronizes GSD engine state across workers:
- Active conversation states
- Escalation timestamps
- State transition history

Uses Redis pub/sub for real-time state updates across workers.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
import asyncio

import redis.asyncio as aioredis

logger = logging.getLogger("parwa.gsd_state_sync")

# Redis key patterns
REDIS_GSD_STATE_PREFIX = "parwa:gsd:state"
REDIS_GSD_STATE_TTL = 3600  # 1 hour (active conversation)
REDIS_GSD_ESCALATION_PREFIX = "parwa:gsd:escalation"
REDIS_GSD_PUBSUB_CHANNEL = "parwa:gsd:events"


@dataclass
class GSDConversationState:
    """State of an active GSD conversation."""

    conversation_id: str
    company_id: str
    ticket_id: str

    current_state: str = "NEW"
    previous_state: str = ""

    # State-specific data
    turn_count: int = 0
    diagnosis_questions_asked: int = 0
    resolution_attempted: bool = False
    follow_up_scheduled: bool = False

    # Confidence tracking
    confidence_score: float = 0.0

    # Timestamps
    started_at: str = ""
    last_activity_at: str = ""
    state_entered_at: str = ""

    # Escalation info
    escalated: bool = False
    escalated_to: str = ""
    escalation_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GSDConversationState":
        """Create from dictionary."""
        return cls(
            conversation_id=data.get("conversation_id", ""),
            company_id=data.get("company_id", ""),
            ticket_id=data.get("ticket_id", ""),
            current_state=data.get("current_state", "NEW"),
            previous_state=data.get("previous_state", ""),
            turn_count=data.get("turn_count", 0),
            diagnosis_questions_asked=data.get("diagnosis_questions_asked", 0),
            resolution_attempted=data.get("resolution_attempted", False),
            follow_up_scheduled=data.get("follow_up_scheduled", False),
            confidence_score=data.get("confidence_score", 0.0),
            started_at=data.get("started_at", ""),
            last_activity_at=data.get("last_activity_at", ""),
            state_entered_at=data.get("state_entered_at", ""),
            escalated=data.get("escalated", False),
            escalated_to=data.get("escalated_to", ""),
            escalation_reason=data.get("escalation_reason", ""),
        )


@dataclass
class GSDStateEvent:
    """Event emitted on state transitions."""

    event_type: str  # state_transition, escalation, resolution, etc.
    conversation_id: str
    company_id: str
    from_state: str
    to_state: str
    timestamp: str
    metadata: Dict[str, Any]

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "GSDStateEvent":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


class GSDStateSync:
    """
    Synchronizes GSD state across workers using Redis.

    Features:
    - State persistence with TTL
    - Pub/sub for real-time updates
    - Escalation tracking
    """

    def __init__(self, redis_client: aioredis.Redis):
        """Initialize with Redis client."""
        self._redis = redis_client
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._event_handlers: Dict[str, Callable] = {}
        self._listener_task: Optional[asyncio.Task] = None

    def _get_state_key(self, conversation_id: str) -> str:
        """Get Redis key for conversation state."""
        return f"{REDIS_GSD_STATE_PREFIX}:{conversation_id}"

    def _get_escalation_key(self, company_id: str) -> str:
        """Get Redis key for escalation tracking."""
        return f"{REDIS_GSD_ESCALATION_PREFIX}:{company_id}"

    async def get_state(self, conversation_id: str) -> Optional[GSDConversationState]:
        """Get current state of a conversation."""
        key = self._get_state_key(conversation_id)

        try:
            data = await self._redis.get(key)
            if data:
                return GSDConversationState.from_dict(json.loads(data))
        except Exception as e:
            logger.warning("Failed to get state for %s: %s", conversation_id, e)

        return None

    async def save_state(self, state: GSDConversationState) -> bool:
        """Save conversation state with TTL."""
        key = self._get_state_key(state.conversation_id)

        # Update timestamps
        now = datetime.now(timezone.utc).isoformat()
        if not state.started_at:
            state.started_at = now
        state.last_activity_at = now

        try:
            await self._redis.setex(
                key,
                REDIS_GSD_STATE_TTL,
                json.dumps(state.to_dict()),
            )
            return True
        except Exception as e:
            logger.error("Failed to save state for %s: %s", state.conversation_id, e)
            return False

    async def transition_state(
        self,
        conversation_id: str,
        from_state: str,
        to_state: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Transition conversation to new state.

        Publishes event for other workers to react.
        """
        state = await self.get_state(conversation_id)

        if not state:
            logger.warning("No state found for %s", conversation_id)
            return False

        # Validate transition
        if state.current_state != from_state:
            logger.warning(
                "State mismatch for %s: expected %s, got %s",
                conversation_id, from_state, state.current_state,
            )
            return False

        # Update state
        state.previous_state = state.current_state
        state.current_state = to_state
        state.state_entered_at = datetime.now(timezone.utc).isoformat()

        # Save state
        success = await self.save_state(state)

        if success:
            # Publish event
            event = GSDStateEvent(
                event_type="state_transition",
                conversation_id=conversation_id,
                company_id=state.company_id,
                from_state=from_state,
                to_state=to_state,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata=metadata or {},
            )
            await self._publish_event(event)

        return success

    async def delete_state(self, conversation_id: str) -> bool:
        """Delete conversation state (e.g., after resolution)."""
        key = self._get_state_key(conversation_id)

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error("Failed to delete state for %s: %s", conversation_id, e)
            return False

    # ── Escalation Tracking ─────────────────────────────────────────────

    async def record_escalation(
        self,
        conversation_id: str,
        company_id: str,
        escalated_to: str,
        reason: str,
    ) -> bool:
        """Record an escalation and set escalation timestamp."""
        # Update conversation state
        state = await self.get_state(conversation_id)

        if state:
            state.escalated = True
            state.escalated_to = escalated_to
            state.escalation_reason = reason
            await self.save_state(state)

        # Track escalation for company
        escalation_key = self._get_escalation_key(company_id)
        now = datetime.now(timezone.utc).isoformat()

        try:
            await self._redis.hset(
                escalation_key,
                conversation_id,
                json.dumps({
                    "escalated_to": escalated_to,
                    "reason": reason,
                    "timestamp": now,
                }),
            )
            # Escalation records persist for 24 hours
            await self._redis.expire(escalation_key, 86400)
        except Exception as e:
            logger.error("Failed to record escalation: %s", e)

        # Publish escalation event
        event = GSDStateEvent(
            event_type="escalation",
            conversation_id=conversation_id,
            company_id=company_id,
            from_state="",
            to_state="ESCALATED",
            timestamp=now,
            metadata={"escalated_to": escalated_to, "reason": reason},
        )
        await self._publish_event(event)

        return True

    async def get_active_escalations(self, company_id: str) -> Dict[str, Any]:
        """Get all active escalations for a company."""
        escalation_key = self._get_escalation_key(company_id)

        try:
            data = await self._redis.hgetall(escalation_key)
            if data:
                return {k.decode(): json.loads(v.decode()) for k, v in data.items()}
        except Exception as e:
            logger.warning("Failed to get escalations for %s: %s", company_id, e)

        return {}

    # ── Pub/Sub for Real-time Updates ───────────────────────────────────

    async def _publish_event(self, event: GSDStateEvent) -> None:
        """Publish state event to Redis channel."""
        try:
            await self._redis.publish(
                REDIS_GSD_PUBSUB_CHANNEL,
                event.to_json(),
            )
        except Exception as e:
            logger.warning("Failed to publish event: %s", e)

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[GSDStateEvent], None],
    ) -> None:
        """Subscribe to state events of a specific type."""
        self._event_handlers[event_type] = handler

        # Start listener if not already running
        if not self._listener_task:
            self._listener_task = asyncio.create_task(self._listen_for_events())

    async def _listen_for_events(self) -> None:
        """Listen for state events from Redis pub/sub."""
        try:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(REDIS_GSD_PUBSUB_CHANNEL)

            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        event = GSDStateEvent.from_json(message["data"])
                        handler = self._event_handlers.get(event.event_type)

                        if handler:
                            await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)

                    except Exception as e:
                        logger.warning("Failed to process event: %s", e)

        except asyncio.CancelledError:
            logger.info("State sync listener cancelled")
        except Exception as e:
            logger.error("State sync listener error: %s", e)
        finally:
            if self._pubsub:
                await self._pubsub.unsubscribe(REDIS_GSD_PUBSUB_CHANNEL)
                await self._pubsub.close()

    async def close(self) -> None:
        """Close pub/sub connection and cancel listener."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.close()


# Singleton instance
_gsd_state_sync: Optional[GSDStateSync] = None


async def get_gsd_state_sync() -> GSDStateSync:
    """Get or create the singleton GSD state sync instance."""
    global _gsd_state_sync

    if _gsd_state_sync is None:
        from app.core.redis import get_redis_client

        redis_client = await get_redis_client()
        _gsd_state_sync = GSDStateSync(redis_client)

    return _gsd_state_sync
