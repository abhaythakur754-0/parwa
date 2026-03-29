"""
Burst Mode Service for PARWA.

Manages high-load scenarios by activating burst mode to handle
increased traffic and resource demands.

Features:
- Activate burst mode on high load detection
- Track system load metrics
- Configure burst thresholds
- Support manual activation/deactivation
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
import logging

from backend.core.config import get_config

logger = logging.getLogger(__name__)


class BurstModeState(Enum):
    """Burst mode operational states."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    TRANSITIONING = "transitioning"
    COOLDOWN = "cooldown"


class LoadLevel(Enum):
    """System load classification."""
    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BurstThresholds:
    """Configuration thresholds for burst mode activation."""
    cpu_percent: float = 80.0
    memory_percent: float = 85.0
    queue_depth: int = 100
    response_time_ms: int = 500
    request_rate_per_sec: int = 1000
    cooldown_seconds: int = 300  # 5 minutes cooldown after deactivation
    min_burst_duration_seconds: int = 60  # Minimum time to stay in burst mode


@dataclass
class SystemLoadMetrics:
    """Current system load metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    queue_depth: int = 0
    response_time_ms: float = 0.0
    request_rate_per_sec: float = 0.0
    active_connections: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "queue_depth": self.queue_depth,
            "response_time_ms": self.response_time_ms,
            "request_rate_per_sec": self.request_rate_per_sec,
            "active_connections": self.active_connections,
            "timestamp": self.timestamp,
        }

    def classify_load(self, thresholds: BurstThresholds) -> LoadLevel:
        """Classify current load level based on thresholds."""
        # Critical: multiple metrics at critical levels
        critical_count = sum([
            self.cpu_percent >= thresholds.cpu_percent * 1.2,
            self.memory_percent >= thresholds.memory_percent * 1.2,
            self.queue_depth >= thresholds.queue_depth * 1.5,
            self.response_time_ms >= thresholds.response_time_ms * 2,
        ])

        if critical_count >= 2:
            return LoadLevel.CRITICAL

        # High: at least one threshold exceeded significantly
        if any([
            self.cpu_percent >= thresholds.cpu_percent,
            self.memory_percent >= thresholds.memory_percent,
            self.queue_depth >= thresholds.queue_depth,
            self.response_time_ms >= thresholds.response_time_ms,
            self.request_rate_per_sec >= thresholds.request_rate_per_sec,
        ]):
            return LoadLevel.HIGH

        # Elevated: approaching thresholds
        if any([
            self.cpu_percent >= thresholds.cpu_percent * 0.75,
            self.memory_percent >= thresholds.memory_percent * 0.75,
            self.queue_depth >= thresholds.queue_depth * 0.75,
            self.response_time_ms >= thresholds.response_time_ms * 0.75,
        ]):
            return LoadLevel.ELEVATED

        # Normal vs Low
        if all([
            self.cpu_percent < 30,
            self.memory_percent < 30,
            self.queue_depth < 20,
        ]):
            return LoadLevel.LOW

        return LoadLevel.NORMAL


@dataclass
class BurstModeStatus:
    """Current burst mode status."""
    state: BurstModeState = BurstModeState.INACTIVE
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    activation_reason: str = ""
    current_load_level: LoadLevel = LoadLevel.NORMAL
    current_metrics: SystemLoadMetrics = field(default_factory=SystemLoadMetrics)
    burst_count: int = 0
    total_burst_time_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary."""
        return {
            "state": self.state.value,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "deactivated_at": self.deactivated_at.isoformat() if self.deactivated_at else None,
            "activation_reason": self.activation_reason,
            "current_load_level": self.current_load_level.value,
            "current_metrics": self.current_metrics.to_dict(),
            "burst_count": self.burst_count,
            "total_burst_time_seconds": self.total_burst_time_seconds,
        }


class BurstModeService:
    """
    Main burst mode service for handling high-load scenarios.

    This service monitors system load and automatically activates
    burst mode when thresholds are exceeded. It also supports
    manual activation and deactivation.
    """

    def __init__(
        self,
        thresholds: Optional[BurstThresholds] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize burst mode service.

        Args:
            thresholds: Custom thresholds configuration
            redis_client: Optional Redis client for distributed state
        """
        self.thresholds = thresholds or BurstThresholds()
        self._redis = redis_client
        self._status = BurstModeStatus()
        self._metrics_history: List[SystemLoadMetrics] = []
        self._max_history_size = 100
        self._state_change_callbacks: List[Callable[[BurstModeState, BurstModeState], None]] = []
        self._lock = asyncio.Lock()
        self._config = get_config()

    @property
    def is_active(self) -> bool:
        """Check if burst mode is currently active."""
        return self._status.state == BurstModeState.ACTIVE

    @property
    def state(self) -> BurstModeState:
        """Get current burst mode state."""
        return self._status.state

    @property
    def current_metrics(self) -> SystemLoadMetrics:
        """Get current system metrics."""
        return self._status.current_metrics

    def add_state_change_callback(
        self,
        callback: Callable[[BurstModeState, BurstModeState], None]
    ) -> None:
        """
        Add a callback to be called on state changes.

        Args:
            callback: Function that takes (old_state, new_state) arguments
        """
        self._state_change_callbacks.append(callback)

    def remove_state_change_callback(
        self,
        callback: Callable[[BurstModeState, BurstModeState], None]
    ) -> None:
        """Remove a state change callback."""
        if callback in self._state_change_callbacks:
            self._state_change_callbacks.remove(callback)

    async def _notify_state_change(
        self,
        old_state: BurstModeState,
        new_state: BurstModeState
    ) -> None:
        """Notify all registered callbacks of state change."""
        for callback in self._state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_state, new_state)
                else:
                    callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

    async def update_metrics(
        self,
        cpu_percent: float,
        memory_percent: float,
        queue_depth: int,
        response_time_ms: float = 0.0,
        request_rate_per_sec: float = 0.0,
        active_connections: int = 0,
    ) -> LoadLevel:
        """
        Update system metrics and check for burst mode activation.

        Args:
            cpu_percent: Current CPU usage percentage
            memory_percent: Current memory usage percentage
            queue_depth: Current queue depth
            response_time_ms: Average response time in milliseconds
            request_rate_per_sec: Current request rate
            active_connections: Number of active connections

        Returns:
            Current load level classification
        """
        async with self._lock:
            metrics = SystemLoadMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                queue_depth=queue_depth,
                response_time_ms=response_time_ms,
                request_rate_per_sec=request_rate_per_sec,
                active_connections=active_connections,
            )

            # Update status
            self._status.current_metrics = metrics
            load_level = metrics.classify_load(self.thresholds)
            self._status.current_load_level = load_level

            # Store in history
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history_size:
                self._metrics_history.pop(0)

            # Check for auto-activation/deactivation
            await self._check_thresholds(load_level)

            return load_level

    async def _check_thresholds(self, load_level: LoadLevel) -> None:
        """Check thresholds and manage state transitions."""
        old_state = self._status.state

        if load_level in (LoadLevel.HIGH, LoadLevel.CRITICAL):
            if self._status.state == BurstModeState.INACTIVE:
                await self._activate(
                    reason=f"Auto-activated: {load_level.value} load detected"
                )
        elif load_level in (LoadLevel.LOW, LoadLevel.NORMAL):
            if self._status.state == BurstModeState.ACTIVE:
                # Check minimum burst duration
                if self._status.activated_at:
                    elapsed = (datetime.now() - self._status.activated_at).total_seconds()
                    if elapsed < self.thresholds.min_burst_duration_seconds:
                        logger.debug(
                            f"Skipping deactivation: minimum duration not met "
                            f"({elapsed}s < {self.thresholds.min_burst_duration_seconds}s)"
                        )
                        return
                await self._deactivate(reason="Load normalized")

    async def _activate(self, reason: str) -> bool:
        """
        Internal activation logic.

        Args:
            reason: Reason for activation

        Returns:
            True if activation succeeded
        """
        old_state = self._status.state

        # Check cooldown
        if self._status.deactivated_at:
            cooldown_remaining = (
                self.thresholds.cooldown_seconds -
                (datetime.now() - self._status.deactivated_at).total_seconds()
            )
            if cooldown_remaining > 0:
                logger.info(
                    f"Burst mode activation blocked: cooldown ({cooldown_remaining:.1f}s remaining)"
                )
                return False

        self._status.state = BurstModeState.ACTIVE
        self._status.activated_at = datetime.now()
        self._status.activation_reason = reason
        self._status.burst_count += 1

        logger.info(f"Burst mode activated: {reason}")

        await self._notify_state_change(old_state, self._status.state)
        return True

    async def activate(self, reason: str = "Manual activation") -> bool:
        """
        Manually activate burst mode.

        Args:
            reason: Reason for manual activation

        Returns:
            True if activation succeeded
        """
        async with self._lock:
            if self._status.state == BurstModeState.ACTIVE:
                logger.warning("Burst mode already active")
                return False

            return await self._activate(reason)

    async def _deactivate(self, reason: str) -> bool:
        """
        Internal deactivation logic.

        Args:
            reason: Reason for deactivation

        Returns:
            True if deactivation succeeded
        """
        old_state = self._status.state

        if self._status.activated_at:
            burst_duration = (
                datetime.now() - self._status.activated_at
            ).total_seconds()
            self._status.total_burst_time_seconds += burst_duration

        self._status.state = BurstModeState.INACTIVE
        self._status.deactivated_at = datetime.now()
        self._status.activation_reason = ""

        logger.info(f"Burst mode deactivated: {reason}")

        await self._notify_state_change(old_state, self._status.state)
        return True

    async def deactivate(self, reason: str = "Manual deactivation") -> bool:
        """
        Manually deactivate burst mode.

        Args:
            reason: Reason for manual deactivation

        Returns:
            True if deactivation succeeded
        """
        async with self._lock:
            if self._status.state != BurstModeState.ACTIVE:
                logger.warning("Burst mode not active")
                return False

            return await self._deactivate(reason)

    def get_status(self) -> BurstModeStatus:
        """Get current burst mode status."""
        return self._status

    def get_metrics_history(self, limit: int = 10) -> List[SystemLoadMetrics]:
        """
        Get recent metrics history.

        Args:
            limit: Maximum number of metrics to return

        Returns:
            List of recent metrics
        """
        return self._metrics_history[-limit:]

    def get_average_metrics(self, window_seconds: int = 60) -> Optional[SystemLoadMetrics]:
        """
        Get average metrics over a time window.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Averaged metrics or None if no data
        """
        cutoff_time = time.time() - window_seconds
        recent_metrics = [
            m for m in self._metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return None

        return SystemLoadMetrics(
            cpu_percent=sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            memory_percent=sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
            queue_depth=int(sum(m.queue_depth for m in recent_metrics) / len(recent_metrics)),
            response_time_ms=sum(m.response_time_ms for m in recent_metrics) / len(recent_metrics),
            request_rate_per_sec=sum(m.request_rate_per_sec for m in recent_metrics) / len(recent_metrics),
            active_connections=int(sum(m.active_connections for m in recent_metrics) / len(recent_metrics)),
        )

    def configure_thresholds(
        self,
        cpu_percent: Optional[float] = None,
        memory_percent: Optional[float] = None,
        queue_depth: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        request_rate_per_sec: Optional[int] = None,
        cooldown_seconds: Optional[int] = None,
        min_burst_duration_seconds: Optional[int] = None,
    ) -> None:
        """
        Update burst mode thresholds.

        Args:
            cpu_percent: CPU threshold percentage
            memory_percent: Memory threshold percentage
            queue_depth: Queue depth threshold
            response_time_ms: Response time threshold in milliseconds
            request_rate_per_sec: Request rate threshold
            cooldown_seconds: Cooldown period after deactivation
            min_burst_duration_seconds: Minimum burst mode duration
        """
        if cpu_percent is not None:
            self.thresholds.cpu_percent = cpu_percent
        if memory_percent is not None:
            self.thresholds.memory_percent = memory_percent
        if queue_depth is not None:
            self.thresholds.queue_depth = queue_depth
        if response_time_ms is not None:
            self.thresholds.response_time_ms = response_time_ms
        if request_rate_per_sec is not None:
            self.thresholds.request_rate_per_sec = request_rate_per_sec
        if cooldown_seconds is not None:
            self.thresholds.cooldown_seconds = cooldown_seconds
        if min_burst_duration_seconds is not None:
            self.thresholds.min_burst_duration_seconds = min_burst_duration_seconds

        logger.info(f"Burst mode thresholds updated: {self.thresholds}")

    def reset(self) -> None:
        """Reset burst mode service to initial state."""
        self._status = BurstModeStatus()
        self._metrics_history.clear()
        logger.info("Burst mode service reset")


# Singleton instance
_burst_mode_service: Optional[BurstModeService] = None


def get_burst_mode_service() -> BurstModeService:
    """Get the singleton burst mode service instance."""
    global _burst_mode_service
    if _burst_mode_service is None:
        _burst_mode_service = BurstModeService()
    return _burst_mode_service


def reset_burst_mode_service() -> None:
    """Reset the singleton burst mode service (for testing)."""
    global _burst_mode_service
    if _burst_mode_service:
        _burst_mode_service.reset()
    _burst_mode_service = None
