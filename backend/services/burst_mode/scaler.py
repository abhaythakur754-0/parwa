"""
Resource Scaler for Burst Mode.

Handles scaling operations when burst mode is activated,
including horizontal and vertical scaling hints with cooldown management.

Features:
- Scale resources up/down based on load
- Track scaling history
- Support horizontal and vertical scaling hints
- Implement cooldown periods between scaling operations
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ScalingDirection(Enum):
    """Direction of scaling operation."""
    UP = "up"
    DOWN = "down"
    NONE = "none"


class ScalingType(Enum):
    """Type of scaling operation."""
    HORIZONTAL = "horizontal"  # Add/remove instances
    VERTICAL = "vertical"      # Increase/decrease resources per instance


class ScalingStatus(Enum):
    """Status of a scaling operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScalingConfig:
    """Configuration for scaling operations."""
    # Instance limits
    min_instances: int = 1
    max_instances: int = 10

    # Resource limits (per instance)
    min_cpu_cores: float = 0.5
    max_cpu_cores: float = 8.0
    min_memory_gb: float = 0.5
    max_memory_gb: float = 32.0

    # Scaling thresholds
    scale_up_cpu_threshold: float = 80.0
    scale_down_cpu_threshold: float = 30.0
    scale_up_memory_threshold: float = 85.0
    scale_down_memory_threshold: float = 40.0

    # Cooldown periods (seconds)
    scale_up_cooldown: int = 60      # Wait between scale-up operations
    scale_down_cooldown: int = 300   # Wait before scaling down
    cooldown_after_burst: int = 600  # Cooldown after burst mode ends

    # Scaling increments
    horizontal_increment: int = 2    # Instances to add/remove
    vertical_cpu_increment: float = 1.0  # CPU cores to add/remove
    vertical_memory_increment: float = 2.0  # Memory GB to add/remove


@dataclass
class ScalingEvent:
    """Record of a scaling operation."""
    event_id: str
    timestamp: datetime
    direction: ScalingDirection
    scaling_type: ScalingType
    status: ScalingStatus
    reason: str
    old_value: float
    new_value: float
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "scaling_type": self.scaling_type.value,
            "status": self.status.value,
            "reason": self.reason,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ResourceState:
    """Current resource state."""
    instance_count: int = 1
    cpu_cores_per_instance: float = 1.0
    memory_gb_per_instance: float = 2.0
    total_cpu_capacity: float = 1.0
    total_memory_capacity: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "instance_count": self.instance_count,
            "cpu_cores_per_instance": self.cpu_cores_per_instance,
            "memory_gb_per_instance": self.memory_gb_per_instance,
            "total_cpu_capacity": self.total_cpu_capacity,
            "total_memory_capacity": self.total_memory_capacity,
        }

    def update_totals(self) -> None:
        """Update total capacity calculations."""
        self.total_cpu_capacity = self.instance_count * self.cpu_cores_per_instance
        self.total_memory_capacity = self.instance_count * self.memory_gb_per_instance


class ResourceScaler:
    """
    Manages resource scaling operations for burst mode.

    Provides both horizontal (instance count) and vertical (resource per instance)
    scaling capabilities with configurable cooldown periods and limits.
    """

    def __init__(
        self,
        config: Optional[ScalingConfig] = None,
        burst_mode_service: Optional[Any] = None,
    ):
        """
        Initialize resource scaler.

        Args:
            config: Custom scaling configuration
            burst_mode_service: Reference to burst mode service
        """
        self.config = config or ScalingConfig()
        self._burst_mode_service = burst_mode_service
        self._state = ResourceState()
        self._scaling_history: List[ScalingEvent] = []
        self._max_history_size = 100
        self._last_scale_up_time: Optional[datetime] = None
        self._last_scale_down_time: Optional[datetime] = None
        self._scaling_callbacks: List[Callable[[ScalingEvent], None]] = []
        self._lock = asyncio.Lock()

    @property
    def current_state(self) -> ResourceState:
        """Get current resource state."""
        return self._state

    @property
    def can_scale_up(self) -> bool:
        """Check if scaling up is possible."""
        if self._state.instance_count >= self.config.max_instances:
            return False
        if self._last_scale_up_time:
            cooldown_remaining = (
                self.config.scale_up_cooldown -
                (datetime.now() - self._last_scale_up_time).total_seconds()
            )
            if cooldown_remaining > 0:
                return False
        return True

    @property
    def can_scale_down(self) -> bool:
        """Check if scaling down is possible."""
        if self._state.instance_count <= self.config.min_instances:
            return False
        if self._last_scale_down_time:
            cooldown_remaining = (
                self.config.scale_down_cooldown -
                (datetime.now() - self._last_scale_down_time).total_seconds()
            )
            if cooldown_remaining > 0:
                return False
        return True

    def add_scaling_callback(self, callback: Callable[[ScalingEvent], None]) -> None:
        """Add a callback to be called on scaling operations."""
        self._scaling_callbacks.append(callback)

    def remove_scaling_callback(self, callback: Callable[[ScalingEvent], None]) -> None:
        """Remove a scaling callback."""
        if callback in self._scaling_callbacks:
            self._scaling_callbacks.remove(callback)

    async def _notify_scaling(self, event: ScalingEvent) -> None:
        """Notify all callbacks of scaling operation."""
        for callback in self._scaling_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Scaling callback error: {e}")

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        return f"scale_{int(time.time() * 1000)}_{len(self._scaling_history)}"

    async def scale_horizontal(
        self,
        direction: ScalingDirection,
        count: Optional[int] = None,
        reason: str = "Manual scaling"
    ) -> Optional[ScalingEvent]:
        """
        Perform horizontal scaling (add/remove instances).

        Args:
            direction: UP to add instances, DOWN to remove
            count: Number of instances to add/remove (default: config increment)
            reason: Reason for scaling

        Returns:
            ScalingEvent if operation performed, None if blocked
        """
        async with self._lock:
            if direction == ScalingDirection.UP:
                return await self._scale_horizontal_up(count, reason)
            elif direction == ScalingDirection.DOWN:
                return await self._scale_horizontal_down(count, reason)
            return None

    async def _scale_horizontal_up(
        self,
        count: Optional[int],
        reason: str
    ) -> Optional[ScalingEvent]:
        """Add instances."""
        if not self.can_scale_up:
            logger.warning("Horizontal scale-up blocked: cooldown or limit reached")
            return None

        increment = count or self.config.horizontal_increment
        new_count = min(
            self._state.instance_count + increment,
            self.config.max_instances
        )
        actual_increment = new_count - self._state.instance_count

        if actual_increment <= 0:
            return None

        event = ScalingEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(),
            direction=ScalingDirection.UP,
            scaling_type=ScalingType.HORIZONTAL,
            status=ScalingStatus.IN_PROGRESS,
            reason=reason,
            old_value=self._state.instance_count,
            new_value=new_count,
        )

        old_count = self._state.instance_count
        self._state.instance_count = new_count
        self._state.update_totals()
        self._last_scale_up_time = datetime.now()

        event.status = ScalingStatus.COMPLETED
        event.duration_seconds = 0.1  # Simulated duration

        self._record_event(event)
        logger.info(f"Horizontal scale-up: {old_count} -> {new_count} instances ({reason})")

        await self._notify_scaling(event)
        return event

    async def _scale_horizontal_down(
        self,
        count: Optional[int],
        reason: str
    ) -> Optional[ScalingEvent]:
        """Remove instances."""
        if not self.can_scale_down:
            logger.warning("Horizontal scale-down blocked: cooldown or limit reached")
            return None

        decrement = count or self.config.horizontal_increment
        new_count = max(
            self._state.instance_count - decrement,
            self.config.min_instances
        )
        actual_decrement = self._state.instance_count - new_count

        if actual_decrement <= 0:
            return None

        event = ScalingEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(),
            direction=ScalingDirection.DOWN,
            scaling_type=ScalingType.HORIZONTAL,
            status=ScalingStatus.IN_PROGRESS,
            reason=reason,
            old_value=self._state.instance_count,
            new_value=new_count,
        )

        old_count = self._state.instance_count
        self._state.instance_count = new_count
        self._state.update_totals()
        self._last_scale_down_time = datetime.now()

        event.status = ScalingStatus.COMPLETED
        event.duration_seconds = 0.1  # Simulated duration

        self._record_event(event)
        logger.info(f"Horizontal scale-down: {old_count} -> {new_count} instances ({reason})")

        await self._notify_scaling(event)
        return event

    async def scale_vertical(
        self,
        direction: ScalingDirection,
        resource_type: str,  # "cpu" or "memory"
        amount: Optional[float] = None,
        reason: str = "Manual scaling"
    ) -> Optional[ScalingEvent]:
        """
        Perform vertical scaling (increase/decrease resources per instance).

        Args:
            direction: UP to increase, DOWN to decrease
            resource_type: "cpu" or "memory"
            amount: Amount to change (default: config increment)
            reason: Reason for scaling

        Returns:
            ScalingEvent if operation performed, None if blocked
        """
        async with self._lock:
            if resource_type == "cpu":
                return await self._scale_vertical_cpu(direction, amount, reason)
            elif resource_type == "memory":
                return await self._scale_vertical_memory(direction, amount, reason)
            return None

    async def _scale_vertical_cpu(
        self,
        direction: ScalingDirection,
        amount: Optional[float],
        reason: str
    ) -> Optional[ScalingEvent]:
        """Scale CPU per instance."""
        if direction == ScalingDirection.UP:
            if not self.can_scale_up:
                return None

            increment = amount or self.config.vertical_cpu_increment
            new_cpu = min(
                self._state.cpu_cores_per_instance + increment,
                self.config.max_cpu_cores
            )

            if new_cpu <= self._state.cpu_cores_per_instance:
                return None

            event = ScalingEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.now(),
                direction=ScalingDirection.UP,
                scaling_type=ScalingType.VERTICAL,
                status=ScalingStatus.COMPLETED,
                reason=reason,
                old_value=self._state.cpu_cores_per_instance,
                new_value=new_cpu,
                metadata={"resource_type": "cpu"}
            )

            self._state.cpu_cores_per_instance = new_cpu
            self._state.update_totals()
            self._last_scale_up_time = datetime.now()

            self._record_event(event)
            logger.info(f"Vertical CPU scale-up: {event.old_value} -> {new_cpu} cores ({reason})")

            await self._notify_scaling(event)
            return event

        elif direction == ScalingDirection.DOWN:
            if not self.can_scale_down:
                return None

            decrement = amount or self.config.vertical_cpu_increment
            new_cpu = max(
                self._state.cpu_cores_per_instance - decrement,
                self.config.min_cpu_cores
            )

            if new_cpu >= self._state.cpu_cores_per_instance:
                return None

            event = ScalingEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.now(),
                direction=ScalingDirection.DOWN,
                scaling_type=ScalingType.VERTICAL,
                status=ScalingStatus.COMPLETED,
                reason=reason,
                old_value=self._state.cpu_cores_per_instance,
                new_value=new_cpu,
                metadata={"resource_type": "cpu"}
            )

            self._state.cpu_cores_per_instance = new_cpu
            self._state.update_totals()
            self._last_scale_down_time = datetime.now()

            self._record_event(event)
            logger.info(f"Vertical CPU scale-down: {event.old_value} -> {new_cpu} cores ({reason})")

            await self._notify_scaling(event)
            return event

        return None

    async def _scale_vertical_memory(
        self,
        direction: ScalingDirection,
        amount: Optional[float],
        reason: str
    ) -> Optional[ScalingEvent]:
        """Scale memory per instance."""
        if direction == ScalingDirection.UP:
            if not self.can_scale_up:
                return None

            increment = amount or self.config.vertical_memory_increment
            new_memory = min(
                self._state.memory_gb_per_instance + increment,
                self.config.max_memory_gb
            )

            if new_memory <= self._state.memory_gb_per_instance:
                return None

            event = ScalingEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.now(),
                direction=ScalingDirection.UP,
                scaling_type=ScalingType.VERTICAL,
                status=ScalingStatus.COMPLETED,
                reason=reason,
                old_value=self._state.memory_gb_per_instance,
                new_value=new_memory,
                metadata={"resource_type": "memory"}
            )

            self._state.memory_gb_per_instance = new_memory
            self._state.update_totals()
            self._last_scale_up_time = datetime.now()

            self._record_event(event)
            logger.info(f"Vertical memory scale-up: {event.old_value} -> {new_memory} GB ({reason})")

            await self._notify_scaling(event)
            return event

        elif direction == ScalingDirection.DOWN:
            if not self.can_scale_down:
                return None

            decrement = amount or self.config.vertical_memory_increment
            new_memory = max(
                self._state.memory_gb_per_instance - decrement,
                self.config.min_memory_gb
            )

            if new_memory >= self._state.memory_gb_per_instance:
                return None

            event = ScalingEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.now(),
                direction=ScalingDirection.DOWN,
                scaling_type=ScalingType.VERTICAL,
                status=ScalingStatus.COMPLETED,
                reason=reason,
                old_value=self._state.memory_gb_per_instance,
                new_value=new_memory,
                metadata={"resource_type": "memory"}
            )

            self._state.memory_gb_per_instance = new_memory
            self._state.update_totals()
            self._last_scale_down_time = datetime.now()

            self._record_event(event)
            logger.info(f"Vertical memory scale-down: {event.old_value} -> {new_memory} GB ({reason})")

            await self._notify_scaling(event)
            return event

        return None

    def _record_event(self, event: ScalingEvent) -> None:
        """Record a scaling event in history."""
        self._scaling_history.append(event)
        if len(self._scaling_history) > self._max_history_size:
            self._scaling_history.pop(0)

    def get_scaling_history(
        self,
        limit: int = 10,
        direction: Optional[ScalingDirection] = None,
        scaling_type: Optional[ScalingType] = None,
    ) -> List[ScalingEvent]:
        """
        Get scaling history with optional filters.

        Args:
            limit: Maximum events to return
            direction: Filter by scaling direction
            scaling_type: Filter by scaling type

        Returns:
            List of scaling events
        """
        events = self._scaling_history

        if direction:
            events = [e for e in events if e.direction == direction]
        if scaling_type:
            events = [e for e in events if e.scaling_type == scaling_type]

        return events[-limit:]

    def get_scaling_recommendations(
        self,
        cpu_percent: float,
        memory_percent: float,
    ) -> List[Dict[str, Any]]:
        """
        Get scaling recommendations based on current metrics.

        Args:
            cpu_percent: Current CPU usage percentage
            memory_percent: Current memory usage percentage

        Returns:
            List of recommended scaling actions
        """
        recommendations = []

        # Check for scale-up needs
        if cpu_percent >= self.config.scale_up_cpu_threshold:
            if self._state.instance_count < self.config.max_instances:
                recommendations.append({
                    "action": "scale_up",
                    "type": "horizontal",
                    "reason": f"CPU at {cpu_percent}% (threshold: {self.config.scale_up_cpu_threshold}%)",
                    "suggested_instances": min(
                        self._state.instance_count + self.config.horizontal_increment,
                        self.config.max_instances
                    ),
                })
            if self._state.cpu_cores_per_instance < self.config.max_cpu_cores:
                recommendations.append({
                    "action": "scale_up",
                    "type": "vertical_cpu",
                    "reason": f"CPU at {cpu_percent}% - consider more cores per instance",
                    "suggested_cores": min(
                        self._state.cpu_cores_per_instance + self.config.vertical_cpu_increment,
                        self.config.max_cpu_cores
                    ),
                })

        if memory_percent >= self.config.scale_up_memory_threshold:
            if self._state.instance_count < self.config.max_instances:
                recommendations.append({
                    "action": "scale_up",
                    "type": "horizontal",
                    "reason": f"Memory at {memory_percent}% (threshold: {self.config.scale_up_memory_threshold}%)",
                    "suggested_instances": min(
                        self._state.instance_count + self.config.horizontal_increment,
                        self.config.max_instances
                    ),
                })
            if self._state.memory_gb_per_instance < self.config.max_memory_gb:
                recommendations.append({
                    "action": "scale_up",
                    "type": "vertical_memory",
                    "reason": f"Memory at {memory_percent}% - consider more memory per instance",
                    "suggested_memory_gb": min(
                        self._state.memory_gb_per_instance + self.config.vertical_memory_increment,
                        self.config.max_memory_gb
                    ),
                })

        # Check for scale-down opportunities
        if cpu_percent <= self.config.scale_down_cpu_threshold and memory_percent <= self.config.scale_down_memory_threshold:
            if self._state.instance_count > self.config.min_instances:
                recommendations.append({
                    "action": "scale_down",
                    "type": "horizontal",
                    "reason": f"Low resource usage (CPU: {cpu_percent}%, Memory: {memory_percent}%)",
                    "suggested_instances": max(
                        self._state.instance_count - self.config.horizontal_increment,
                        self.config.min_instances
                    ),
                })

        return recommendations

    def configure(
        self,
        min_instances: Optional[int] = None,
        max_instances: Optional[int] = None,
        scale_up_cooldown: Optional[int] = None,
        scale_down_cooldown: Optional[int] = None,
        **kwargs
    ) -> None:
        """
        Update scaler configuration.

        Args:
            min_instances: Minimum instance count
            max_instances: Maximum instance count
            scale_up_cooldown: Cooldown between scale-ups (seconds)
            scale_down_cooldown: Cooldown before scale-down (seconds)
            **kwargs: Additional configuration options
        """
        if min_instances is not None:
            self.config.min_instances = min_instances
        if max_instances is not None:
            self.config.max_instances = max_instances
        if scale_up_cooldown is not None:
            self.config.scale_up_cooldown = scale_up_cooldown
        if scale_down_cooldown is not None:
            self.config.scale_down_cooldown = scale_down_cooldown

        # Update any other config options
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        logger.info(f"Scaler configuration updated")

    def reset(self) -> None:
        """Reset scaler to initial state."""
        self._state = ResourceState()
        self._scaling_history.clear()
        self._last_scale_up_time = None
        self._last_scale_down_time = None
        logger.info("Resource scaler reset")


# Singleton instance
_resource_scaler: Optional[ResourceScaler] = None


def get_resource_scaler() -> ResourceScaler:
    """Get the singleton resource scaler instance."""
    global _resource_scaler
    if _resource_scaler is None:
        _resource_scaler = ResourceScaler()
    return _resource_scaler


def reset_resource_scaler() -> None:
    """Reset the singleton resource scaler (for testing)."""
    global _resource_scaler
    if _resource_scaler:
        _resource_scaler.reset()
    _resource_scaler = None
