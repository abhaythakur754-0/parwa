"""
PARWA Burst Mode Service.

Manages high-volume period handling with automatic scaling,
rate limiting, and resource optimization.

Features:
- Automatic burst detection
- Dynamic scaling coordination
- Rate limiting with backpressure
- Resource pool management
- Graceful degradation
- Recovery handling
"""
from typing import Any, Dict, Optional, List, Callable, Awaitable
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import math

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BurstStatus(str, Enum):
    """Status of burst mode."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    BURST = "burst"
    CRITICAL = "critical"
    RECOVERY = "recovery"


class ScalingAction(str, Enum):
    """Actions to take during burst."""
    NONE = "none"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    ENABLE_THROTTLING = "enable_throttling"
    DISABLE_THROTTLING = "disable_throttling"
    QUEUE_REQUESTS = "queue_requests"
    REJECT_REQUESTS = "reject_requests"


class BurstModeConfig(BaseModel):
    """Configuration for Burst Mode Manager."""
    # Thresholds
    normal_threshold_rpm: int = Field(default=100, ge=10, le=10000)
    elevated_threshold_rpm: int = Field(default=300, ge=50, le=20000)
    burst_threshold_rpm: int = Field(default=500, ge=100, le=50000)
    critical_threshold_rpm: int = Field(default=1000, ge=200, le=100000)
    
    # Timing
    burst_detection_window_seconds: int = Field(default=60, ge=10, le=300)
    burst_cooldown_seconds: int = Field(default=300, ge=60, le=1800)
    recovery_window_seconds: int = Field(default=180, ge=30, le=600)
    
    # Scaling
    max_concurrent_requests: int = Field(default=100, ge=10, le=10000)
    burst_max_concurrent: int = Field(default=200, ge=20, le=20000)
    critical_max_concurrent: int = Field(default=50, ge=5, le=5000)
    
    # Queue
    queue_max_size: int = Field(default=1000, ge=100, le=100000)
    queue_timeout_seconds: int = Field(default=30, ge=5, le=120)
    
    # Features
    enable_auto_scaling: bool = Field(default=True)
    enable_graceful_degradation: bool = Field(default=True)
    enable_queue_backpressure: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class RequestMetrics:
    """Metrics for request tracking."""
    timestamp: datetime
    request_count: int
    avg_response_time_ms: float
    error_rate: float
    queue_depth: int
    active_workers: int


@dataclass
class BurstEvent:
    """Record of a burst event."""
    event_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    peak_rpm: int = 0
    duration_seconds: float = 0
    status_changes: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    metrics_before: Optional[Dict[str, Any]] = None
    metrics_after: Optional[Dict[str, Any]] = None


class BurstModeManager:
    """
    Manages burst mode detection and handling.
    
    Features:
    - Automatic burst detection based on request rate
    - Dynamic scaling coordination
    - Rate limiting with backpressure
    - Resource pool management
    - Graceful degradation during critical load
    - Recovery handling
    
    Example:
        manager = BurstModeManager()
        
        # Check request
        status = await manager.check_request("company_123")
        if status == BurstStatus.CRITICAL:
            # Handle rejection
            pass
        
        # Record metrics
        await manager.record_metrics({
            "request_count": 150,
            "avg_response_time_ms": 250,
        })
        
        # Get current status
        status = manager.get_current_status()
    """
    
    def __init__(
        self,
        config: Optional[BurstModeConfig] = None,
        scaling_handlers: Optional[Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]]] = None
    ) -> None:
        """
        Initialize Burst Mode Manager.
        
        Args:
            config: Burst mode configuration
            scaling_handlers: Optional handlers for scaling events
        """
        self.config = config or BurstModeConfig()
        self._scaling_handlers = scaling_handlers or {}
        
        # State
        self._current_status = BurstStatus.NORMAL
        self._status_since = datetime.now(timezone.utc)
        
        # Metrics tracking
        self._metrics_history: List[RequestMetrics] = []
        self._request_count_window: List[datetime] = []
        
        # Burst tracking
        self._current_burst: Optional[BurstEvent] = None
        self._burst_history: List[BurstEvent] = []
        
        # Resource pools
        self._active_requests: Dict[str, datetime] = {}
        self._request_queue: asyncio.Queue = asyncio.Queue()
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        self._status_lock = asyncio.Lock()
        
        logger.info({
            "event": "burst_mode_initialized",
            "config": self.config.model_dump(),
        })
    
    async def check_request(
        self,
        request_id: str,
        company_id: Optional[str] = None,
        priority: int = 0
    ) -> BurstStatus:
        """
        Check if a request should be accepted.
        
        Args:
            request_id: Unique request identifier
            company_id: Optional company identifier
            priority: Request priority (higher = more important)
        
        Returns:
            BurstStatus indicating if request should proceed
        """
        # Update status based on current load
        await self._update_status()
        
        # Check if we should accept the request
        if self._current_status == BurstStatus.CRITICAL:
            if priority < 10:  # Low priority requests rejected
                logger.warning({
                    "event": "request_rejected",
                    "request_id": request_id,
                    "status": self._current_status.value,
                    "priority": priority,
                })
                return BurstStatus.CRITICAL
        
        # Track request
        self._request_count_window.append(datetime.now(timezone.utc))
        self._active_requests[request_id] = datetime.now(timezone.utc)
        
        # Clean old entries
        await self._cleanup_request_tracking()
        
        return self._current_status
    
    async def acquire_slot(
        self,
        request_id: str,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquire a processing slot for a request.
        
        Args:
            request_id: Request identifier
            timeout: Max seconds to wait for slot
        
        Returns:
            True if slot acquired, False if timed out
        """
        max_concurrent = self._get_max_concurrent()
        timeout = timeout or self.config.queue_timeout_seconds
        
        try:
            async with asyncio.timeout(timeout):
                await self._semaphore.acquire()
                return True
        except asyncio.TimeoutError:
            logger.warning({
                "event": "slot_acquire_timeout",
                "request_id": request_id,
                "max_concurrent": max_concurrent,
            })
            return False
    
    def release_slot(self, request_id: str) -> None:
        """Release a processing slot."""
        try:
            self._semaphore.release()
        except ValueError:
            pass  # Already released
        
        if request_id in self._active_requests:
            del self._active_requests[request_id]
    
    async def record_metrics(
        self,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Record request metrics for burst detection.
        
        Args:
            metrics: Dict with:
                - request_count: Number of requests
                - avg_response_time_ms: Average response time
                - error_rate: Error rate (0.0 - 1.0)
                - queue_depth: Current queue depth
                - active_workers: Number of active workers
        """
        metric = RequestMetrics(
            timestamp=datetime.now(timezone.utc),
            request_count=metrics.get("request_count", 0),
            avg_response_time_ms=metrics.get("avg_response_time_ms", 0.0),
            error_rate=metrics.get("error_rate", 0.0),
            queue_depth=metrics.get("queue_depth", 0),
            active_workers=metrics.get("active_workers", 0),
        )
        
        self._metrics_history.append(metric)
        
        # Keep only recent metrics
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        self._metrics_history = [
            m for m in self._metrics_history
            if m.timestamp > cutoff
        ]
        
        # Trigger status update
        await self._update_status()
    
    async def _update_status(self) -> None:
        """Update burst status based on current metrics."""
        rpm = self._calculate_rpm()
        error_rate = self._get_recent_error_rate()
        
        new_status = self._determine_status(rpm, error_rate)
        
        if new_status != self._current_status:
            await self._transition_status(new_status, rpm)
    
    def _calculate_rpm(self) -> int:
        """Calculate requests per minute."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.burst_detection_window_seconds)
        
        # Count requests in window
        recent_count = sum(
            1 for ts in self._request_count_window
            if ts > window_start
        )
        
        # Extrapolate to RPM
        window_seconds = self.config.burst_detection_window_seconds
        rpm = int((recent_count / window_seconds) * 60) if recent_count > 0 else 0
        
        return rpm
    
    def _get_recent_error_rate(self) -> float:
        """Get average error rate from recent metrics."""
        if not self._metrics_history:
            return 0.0
        
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent = [m for m in self._metrics_history if m.timestamp > cutoff]
        
        if not recent:
            return 0.0
        
        return sum(m.error_rate for m in recent) / len(recent)
    
    def _determine_status(
        self,
        rpm: int,
        error_rate: float
    ) -> BurstStatus:
        """Determine burst status based on metrics."""
        # Critical based on error rate or extreme load
        if error_rate > 0.5 or rpm >= self.config.critical_threshold_rpm:
            return BurstStatus.CRITICAL
        
        # Burst threshold
        if rpm >= self.config.burst_threshold_rpm:
            return BurstStatus.BURST
        
        # Elevated threshold
        if rpm >= self.config.elevated_threshold_rpm:
            return BurstStatus.ELEVATED
        
        # Recovery if coming down from burst
        if self._current_status in (BurstStatus.BURST, BurstStatus.CRITICAL):
            return BurstStatus.RECOVERY
        
        return BurstStatus.NORMAL
    
    async def _transition_status(
        self,
        new_status: BurstStatus,
        rpm: int
    ) -> None:
        """Transition to new status and trigger actions."""
        old_status = self._current_status
        
        async with self._status_lock:
            self._current_status = new_status
            self._status_since = datetime.now(timezone.utc)
            
            # Update burst event
            await self._update_burst_event(old_status, new_status, rpm)
            
            # Update semaphore for new limits
            max_concurrent = self._get_max_concurrent()
            self._semaphore = asyncio.Semaphore(max_concurrent)
            
            logger.info({
                "event": "burst_status_changed",
                "old_status": old_status.value,
                "new_status": new_status.value,
                "rpm": rpm,
                "max_concurrent": max_concurrent,
            })
            
            # Trigger scaling handlers
            await self._trigger_scaling_handlers(old_status, new_status, rpm)
    
    async def _update_burst_event(
        self,
        old_status: BurstStatus,
        new_status: BurstStatus,
        rpm: int
    ) -> None:
        """Update burst event tracking."""
        now = datetime.now(timezone.utc)
        
        # Starting a burst
        if old_status == BurstStatus.NORMAL and new_status != BurstStatus.NORMAL:
            self._current_burst = BurstEvent(
                event_id=f"burst_{uuid4().hex[:12]}",
                started_at=now,
                metrics_before={
                    "status": old_status.value,
                    "rpm": rpm,
                },
            )
        
        # Update burst event
        if self._current_burst:
            self._current_burst.peak_rpm = max(self._current_burst.peak_rpm, rpm)
            self._current_burst.status_changes.append({
                "from": old_status.value,
                "to": new_status.value,
                "at": now.isoformat(),
                "rpm": rpm,
            })
            
            # Ending a burst
            if new_status in (BurstStatus.NORMAL, BurstStatus.RECOVERY):
                self._current_burst.ended_at = now
                self._current_burst.duration_seconds = (
                    now - self._current_burst.started_at
                ).total_seconds()
                self._current_burst.metrics_after = {
                    "status": new_status.value,
                    "rpm": rpm,
                }
                
                self._burst_history.append(self._current_burst)
                self._current_burst = None
    
    async def _trigger_scaling_handlers(
        self,
        old_status: BurstStatus,
        new_status: BurstStatus,
        rpm: int
    ) -> None:
        """Trigger registered scaling handlers."""
        action = self._get_scaling_action(old_status, new_status)
        
        if action == ScalingAction.NONE:
            return
        
        handler_name = f"on_{action.value}"
        if handler_name in self._scaling_handlers:
            try:
                await self._scaling_handlers[handler_name]({
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "rpm": rpm,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error({
                    "event": "scaling_handler_error",
                    "handler": handler_name,
                    "error": str(e),
                })
        
        # Record action
        if self._current_burst:
            self._current_burst.actions_taken.append(action.value)
    
    def _get_scaling_action(
        self,
        old_status: BurstStatus,
        new_status: BurstStatus
    ) -> ScalingAction:
        """Determine scaling action from status change."""
        # Transition to burst
        if new_status == BurstStatus.BURST and old_status != BurstStatus.BURST:
            return ScalingAction.SCALE_UP
        
        if new_status == BurstStatus.ELEVATED and old_status == BurstStatus.NORMAL:
            return ScalingAction.ENABLE_THROTTLING
        
        if new_status == BurstStatus.CRITICAL:
            return ScalingAction.QUEUE_REQUESTS
        
        if new_status == BurstStatus.RECOVERY:
            return ScalingAction.SCALE_DOWN
        
        if new_status == BurstStatus.NORMAL and old_status in (BurstStatus.BURST, BurstStatus.ELEVATED):
            return ScalingAction.DISABLE_THROTTLING
        
        return ScalingAction.NONE
    
    def _get_max_concurrent(self) -> int:
        """Get max concurrent requests for current status."""
        if self._current_status == BurstStatus.CRITICAL:
            return self.config.critical_max_concurrent
        elif self._current_status in (BurstStatus.BURST, BurstStatus.ELEVATED):
            return self.config.burst_max_concurrent
        return self.config.max_concurrent_requests
    
    async def _cleanup_request_tracking(self) -> None:
        """Clean up old request tracking entries."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=5)
        
        # Clean request count window
        self._request_count_window = [
            ts for ts in self._request_count_window
            if ts > cutoff
        ]
        
        # Clean active requests (stale entries)
        stale = [
            rid for rid, ts in self._active_requests.items()
            if ts < cutoff
        ]
        for rid in stale:
            del self._active_requests[rid]
    
    def get_current_status(self) -> BurstStatus:
        """Get current burst status."""
        return self._current_status
    
    def get_status_duration(self) -> float:
        """Get duration of current status in seconds."""
        return (datetime.now(timezone.utc) - self._status_since).total_seconds()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics."""
        rpm = self._calculate_rpm()
        error_rate = self._get_recent_error_rate()
        
        return {
            "current_status": self._current_status.value,
            "status_since": self._status_since.isoformat(),
            "status_duration_seconds": self.get_status_duration(),
            "current_rpm": rpm,
            "error_rate": error_rate,
            "active_requests": len(self._active_requests),
            "max_concurrent": self._get_max_concurrent(),
            "queue_depth": self._request_queue.qsize(),
        }
    
    def get_burst_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get history of burst events."""
        return [
            {
                "event_id": event.event_id,
                "started_at": event.started_at.isoformat(),
                "ended_at": event.ended_at.isoformat() if event.ended_at else None,
                "peak_rpm": event.peak_rpm,
                "duration_seconds": event.duration_seconds,
                "actions_taken": event.actions_taken,
            }
            for event in self._burst_history[-limit:]
        ]
    
    def register_scaling_handler(
        self,
        action: ScalingAction,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Register a handler for a scaling action.
        
        Args:
            action: Scaling action to handle
            handler: Async handler function
        """
        handler_name = f"on_{action.value}"
        self._scaling_handlers[handler_name] = handler
        logger.info({
            "event": "scaling_handler_registered",
            "action": action.value,
        })
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.model_dump()
    
    async def force_status(
        self,
        status: BurstStatus,
        reason: str = "manual"
    ) -> None:
        """
        Force a specific status (for testing or maintenance).
        
        Args:
            status: Status to set
            reason: Reason for forced status
        """
        rpm = self._calculate_rpm()
        await self._transition_status(status, rpm)
        
        logger.info({
            "event": "burst_status_forced",
            "status": status.value,
            "reason": reason,
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            **self.get_metrics_summary(),
            "config": self.config.model_dump(),
            "burst_history_count": len(self._burst_history),
            "current_burst": {
                "event_id": self._current_burst.event_id,
                "started_at": self._current_burst.started_at.isoformat(),
                "peak_rpm": self._current_burst.peak_rpm,
            } if self._current_burst else None,
        }
