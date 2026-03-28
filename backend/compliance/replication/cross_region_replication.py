"""
Cross-Region Replication Service.

Handles replication between regions:
- Async replication between regions
- Event-driven replication
- Selective replication (metadata only)
- Replication lag tracking
- Automatic retry on failure
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class ReplicationStatus(str, Enum):
    """Status of replication."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ReplicationType(str, Enum):
    """Type of replication."""
    FULL = "full"
    METADATA_ONLY = "metadata_only"
    DELTA = "delta"


@dataclass
class ReplicationConfig:
    """Configuration for replication."""
    max_lag_ms: int = 500
    retry_attempts: int = 3
    retry_delay_ms: int = 100
    batch_size: int = 100
    replication_type: ReplicationType = ReplicationType.DELTA


@dataclass
class ReplicationEvent:
    """Event to be replicated."""
    event_id: str
    source_region: Region
    target_region: Region
    data_type: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    metadata_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "data_type": self.data_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "metadata_only": self.metadata_only
        }


@dataclass
class ReplicationResult:
    """Result of a replication operation."""
    event_id: str
    source_region: Region
    target_region: Region
    status: ReplicationStatus
    lag_ms: int
    attempts: int = 1
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "status": self.status.value,
            "lag_ms": self.lag_ms,
            "attempts": self.attempts,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


class CrossRegionReplication:
    """
    Handles replication between regions.

    Features:
    - Async replication between regions
    - Event-driven replication
    - Selective replication (metadata only)
    - Replication lag tracking
    - Automatic retry on failure
    """

    def __init__(
        self,
        config: Optional[ReplicationConfig] = None,
        region_connections: Optional[Dict[Region, Any]] = None
    ):
        """
        Initialize the replication service.

        Args:
            config: Replication configuration
            region_connections: Connections to other regions
        """
        self.config = config or ReplicationConfig()
        self._region_connections = region_connections or {}
        self._event_queue: List[ReplicationEvent] = []
        self._results: List[ReplicationResult] = []
        self._pending_retries: Dict[str, int] = {}

    def queue_event(
        self,
        event_id: str,
        source_region: Region,
        target_region: Region,
        data_type: str,
        payload: Dict[str, Any],
        metadata_only: bool = False
    ) -> ReplicationEvent:
        """
        Queue an event for replication.

        Args:
            event_id: Unique event identifier
            source_region: Source region
            target_region: Target region
            data_type: Type of data
            payload: Data payload
            metadata_only: Whether to replicate metadata only

        Returns:
            ReplicationEvent that was queued
        """
        event = ReplicationEvent(
            event_id=event_id,
            source_region=source_region,
            target_region=target_region,
            data_type=data_type,
            payload=payload,
            metadata_only=metadata_only
        )

        self._event_queue.append(event)
        logger.debug(f"Queued event {event_id} for replication to {target_region.value}")

        return event

    async def replicate_event(self, event: ReplicationEvent) -> ReplicationResult:
        """
        Replicate a single event.

        Args:
            event: Event to replicate

        Returns:
            ReplicationResult with status
        """
        start_time = datetime.now()

        try:
            # Simulate replication (in real implementation, would call region API)
            await self._send_to_region(event)

            # Calculate lag
            lag_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            result = ReplicationResult(
                event_id=event.event_id,
                source_region=event.source_region,
                target_region=event.target_region,
                status=ReplicationStatus.COMPLETED,
                lag_ms=lag_ms
            )

            logger.debug(
                f"Replicated {event.event_id} to {event.target_region.value} "
                f"in {lag_ms}ms"
            )

        except Exception as e:
            result = ReplicationResult(
                event_id=event.event_id,
                source_region=event.source_region,
                target_region=event.target_region,
                status=ReplicationStatus.FAILED,
                lag_ms=0,
                error=str(e)
            )

            logger.error(f"Replication failed for {event.event_id}: {e}")

        self._results.append(result)
        return result

    async def replicate_with_retry(self, event: ReplicationEvent) -> ReplicationResult:
        """
        Replicate with automatic retry.

        Args:
            event: Event to replicate

        Returns:
            ReplicationResult with final status
        """
        attempts = 0
        last_result = None

        while attempts < self.config.retry_attempts:
            attempts += 1
            last_result = await self.replicate_event(event)

            if last_result.status == ReplicationStatus.COMPLETED:
                last_result.attempts = attempts
                return last_result

            # Wait before retry
            if attempts < self.config.retry_attempts:
                await asyncio.sleep(self.config.retry_delay_ms / 1000)

        # All retries exhausted
        last_result.attempts = attempts
        last_result.status = ReplicationStatus.FAILED
        return last_result

    async def _send_to_region(self, event: ReplicationEvent) -> None:
        """Send event to target region (simulated)."""
        # Simulate network latency (10-100ms)
        latency = random.randint(10, 100) / 1000
        await asyncio.sleep(latency)

        # Simulate occasional failures (5% rate)
        if random.random() < 0.05:
            raise ConnectionError(f"Failed to connect to {event.target_region.value}")

    async def process_queue(self) -> List[ReplicationResult]:
        """
        Process all queued events.

        Returns:
            List of ReplicationResults
        """
        results = []
        events = self._event_queue.copy()
        self._event_queue.clear()

        # Process events in batches
        for i in range(0, len(events), self.config.batch_size):
            batch = events[i:i + self.config.batch_size]
            batch_results = await asyncio.gather(
                *[self.replicate_with_retry(event) for event in batch]
            )
            results.extend(batch_results)

        return results

    def get_queue_size(self) -> int:
        """Get the number of pending events."""
        return len(self._event_queue)

    def get_results(
        self,
        region: Optional[Region] = None,
        status: Optional[ReplicationStatus] = None
    ) -> List[ReplicationResult]:
        """
        Get replication results.

        Args:
            region: Filter by target region
            status: Filter by status

        Returns:
            List of ReplicationResults
        """
        results = self._results

        if region:
            results = [r for r in results if r.target_region == region]

        if status:
            results = [r for r in results if r.status == status]

        return results

    def get_lag_stats(self) -> Dict[str, Any]:
        """
        Get replication lag statistics.

        Returns:
            Statistics dictionary
        """
        completed = [r for r in self._results if r.status == ReplicationStatus.COMPLETED]

        if not completed:
            return {
                "avg_lag_ms": 0,
                "max_lag_ms": 0,
                "min_lag_ms": 0,
                "total_replicated": 0
            }

        lags = [r.lag_ms for r in completed]

        return {
            "avg_lag_ms": sum(lags) // len(lags),
            "max_lag_ms": max(lags),
            "min_lag_ms": min(lags),
            "total_replicated": len(completed)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get replication statistics."""
        total = len(self._results)
        completed = len([r for r in self._results if r.status == ReplicationStatus.COMPLETED])
        failed = len([r for r in self._results if r.status == ReplicationStatus.FAILED])

        lag_stats = self.get_lag_stats()

        return {
            "total_events": total,
            "completed": completed,
            "failed": failed,
            "pending": len(self._event_queue),
            "success_rate": completed / total if total > 0 else 1.0,
            **lag_stats
        }


def get_cross_region_replication(
    max_lag_ms: int = 500
) -> CrossRegionReplication:
    """Factory function to create replication service."""
    config = ReplicationConfig(max_lag_ms=max_lag_ms)
    return CrossRegionReplication(config=config)
