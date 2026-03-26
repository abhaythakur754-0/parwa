"""
Rollback Executor for Auto-Rollback.

Executes model rollback:
- Automatic rollback trigger
- Target: <60 seconds
- Version management
- Rollback logging
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from enum import Enum
import logging
import time
import threading

logger = logging.getLogger(__name__)


class RollbackTrigger(Enum):
    """Reasons for rollback."""
    ACCURACY_DRIFT = "accuracy_drift"
    LATENCY_DEGRADATION = "latency_degradation"
    ERROR_RATE_SPIKE = "error_rate_spike"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


@dataclass
class RollbackConfig:
    """Configuration for rollback execution."""
    max_rollback_time_seconds: float = 60.0
    require_confirmation: bool = False
    notify_on_rollback: bool = True
    cooldown_seconds: float = 300.0  # 5 min between rollbacks
    max_rollbacks_per_hour: int = 3


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    success: bool
    trigger: RollbackTrigger
    previous_version: str
    target_version: str
    rollback_time_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "trigger": self.trigger.value,
            "previous_version": self.previous_version,
            "target_version": self.target_version,
            "rollback_time_seconds": self.rollback_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class RollbackExecutor:
    """
    Executes model rollbacks automatically.

    Features:
    - Automatic rollback trigger
    - Target rollback time: <60 seconds
    - Version management
    - Rollback logging and notification
    """

    def __init__(
        self,
        config: Optional[RollbackConfig] = None,
        model_registry: Optional[Any] = None
    ):
        """
        Initialize the rollback executor.

        Args:
            config: Rollback configuration
            model_registry: Optional model registry for version management
        """
        self.config = config or RollbackConfig()
        self.model_registry = model_registry

        # Version tracking
        self._current_version: str = "v1.0.0"
        self._previous_version: Optional[str] = None
        self._version_history: List[str] = ["v1.0.0"]

        # Rollback tracking
        self._rollback_history: List[RollbackResult] = []
        self._last_rollback_time: Optional[datetime] = None
        self._rollback_count_hour: int = 0
        self._hour_start: datetime = datetime.now()

        # Callbacks
        self._pre_rollback_callbacks: List[Callable] = []
        self._post_rollback_callbacks: List[Callable] = []

        # Lock for thread safety
        self._lock = threading.Lock()

    def register_pre_rollback_callback(self, callback: Callable):
        """Register a callback to run before rollback."""
        self._pre_rollback_callbacks.append(callback)

    def register_post_rollback_callback(self, callback: Callable):
        """Register a callback to run after rollback."""
        self._post_rollback_callbacks.append(callback)

    def set_current_version(self, version: str):
        """Set the current model version."""
        with self._lock:
            self._previous_version = self._current_version
            self._current_version = version
            self._version_history.append(version)

            logger.info(f"Model version updated: {version}")

    def can_rollback(self) -> Tuple[bool, str]:
        """
        Check if rollback is allowed.

        Returns:
            Tuple of (can_rollback, reason)
        """
        now = datetime.now()

        # Reset hourly counter
        if (now - self._hour_start).total_seconds() >= 3600:
            self._rollback_count_hour = 0
            self._hour_start = now

        # Check cooldown
        if self._last_rollback_time:
            cooldown_remaining = (
                self.config.cooldown_seconds -
                (now - self._last_rollback_time).total_seconds()
            )
            if cooldown_remaining > 0:
                return False, f"Cooldown active ({cooldown_remaining:.0f}s remaining)"

        # Check max rollbacks per hour
        if self._rollback_count_hour >= self.config.max_rollbacks_per_hour:
            return False, "Max rollbacks per hour exceeded"

        # Check if previous version exists
        if not self._previous_version:
            return False, "No previous version to rollback to"

        return True, "Rollback allowed"

    def execute_rollback(
        self,
        trigger: RollbackTrigger = RollbackTrigger.MANUAL,
        target_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RollbackResult:
        """
        Execute a model rollback.

        Args:
            trigger: Reason for rollback
            target_version: Specific version to rollback to (default: previous)
            metadata: Additional metadata

        Returns:
            RollbackResult with rollback details
        """
        start_time = time.time()

        with self._lock:
            # Check if rollback is allowed
            can_rollback, reason = self.can_rollback()
            if not can_rollback:
                return RollbackResult(
                    success=False,
                    trigger=trigger,
                    previous_version=self._current_version,
                    target_version=target_version or self._previous_version or "unknown",
                    rollback_time_seconds=0.0,
                    error_message=reason,
                    metadata=metadata
                )

            # Determine target version
            rollback_to = target_version or self._previous_version
            if not rollback_to:
                return RollbackResult(
                    success=False,
                    trigger=trigger,
                    previous_version=self._current_version,
                    target_version="unknown",
                    rollback_time_seconds=0.0,
                    error_message="No target version available",
                    metadata=metadata
                )

            # Run pre-rollback callbacks
            for callback in self._pre_rollback_callbacks:
                try:
                    callback(self._current_version, rollback_to)
                except Exception as e:
                    logger.error(f"Pre-rollback callback failed: {e}")

            # Perform rollback (simulated)
            try:
                # In production, this would:
                # 1. Load previous model from registry
                # 2. Update routing configuration
                # 3. Verify model is healthy
                # 4. Switch traffic

                previous_version = self._current_version
                self._current_version = rollback_to
                self._previous_version = previous_version

                rollback_time = time.time() - start_time

                # Update tracking
                self._last_rollback_time = datetime.now()
                self._rollback_count_hour += 1

                result = RollbackResult(
                    success=True,
                    trigger=trigger,
                    previous_version=previous_version,
                    target_version=rollback_to,
                    rollback_time_seconds=rollback_time,
                    metadata={
                        **(metadata or {}),
                        "within_target": rollback_time < self.config.max_rollback_time_seconds
                    }
                )

                self._rollback_history.append(result)

                # Run post-rollback callbacks
                for callback in self._post_rollback_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error(f"Post-rollback callback failed: {e}")

                logger.info(
                    f"Rollback completed: {previous_version} -> {rollback_to} "
                    f"in {rollback_time:.2f}s"
                )

                return result

            except Exception as e:
                rollback_time = time.time() - start_time
                logger.error(f"Rollback failed: {e}")

                return RollbackResult(
                    success=False,
                    trigger=trigger,
                    previous_version=self._current_version,
                    target_version=rollback_to,
                    rollback_time_seconds=rollback_time,
                    error_message=str(e),
                    metadata=metadata
                )

    def get_current_version(self) -> str:
        """Get current model version."""
        return self._current_version

    def get_previous_version(self) -> Optional[str]:
        """Get previous model version."""
        return self._previous_version

    def get_rollback_history(self, limit: int = 10) -> List[RollbackResult]:
        """Get rollback history."""
        return self._rollback_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            "current_version": self._current_version,
            "previous_version": self._previous_version,
            "total_rollbacks": len(self._rollback_history),
            "rollbacks_this_hour": self._rollback_count_hour,
            "last_rollback": (
                self._last_rollback_time.isoformat()
                if self._last_rollback_time else None
            ),
            "config": {
                "max_rollback_time": self.config.max_rollback_time_seconds,
                "cooldown_seconds": self.config.cooldown_seconds,
                "max_per_hour": self.config.max_rollbacks_per_hour,
            }
        }


def get_rollback_executor(
    max_rollback_time: float = 60.0
) -> RollbackExecutor:
    """
    Factory function to create a rollback executor.

    Args:
        max_rollback_time: Maximum allowed rollback time in seconds

    Returns:
        Configured RollbackExecutor instance
    """
    config = RollbackConfig(max_rollback_time_seconds=max_rollback_time)
    return RollbackExecutor(config=config)
