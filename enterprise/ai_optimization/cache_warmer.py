"""
Cache Warming Strategies for AI Optimization.

This module provides cache warming functionality to pre-populate caches
with frequently accessed data, improving initial performance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
import threading
import queue
import time
import random


class WarmingStrategy(Enum):
    """Strategies for cache warming."""
    PREDICTIVE = "predictive"  # Predict and warm based on access patterns
    SCHEDULED = "scheduled"    # Warm at scheduled times
    ADAPTIVE = "adaptive"      # Adaptively warm based on real-time demand


class WarmingStatus(Enum):
    """Status of a warming task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WarmingPriority(Enum):
    """Priority levels for warming tasks."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class WarmupTask:
    """Represents a single cache warmup task."""
    
    task_id: str
    key: str
    loader: Callable[[], Any]
    strategy: WarmingStrategy
    priority: WarmingPriority = WarmingPriority.MEDIUM
    status: WarmingStatus = WarmingStatus.PENDING
    ttl: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_running(self) -> None:
        """Mark task as running."""
        self.status = WarmingStatus.RUNNING
        self.started_at = datetime.now()
    
    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = WarmingStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = WarmingStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error
    
    def mark_cancelled(self) -> None:
        """Mark task as cancelled."""
        self.status = WarmingStatus.CANCELLED
        self.completed_at = datetime.now()
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retries < self.max_retries and self.status == WarmingStatus.FAILED
    
    def increment_retry(self) -> None:
        """Increment retry count and reset status."""
        self.retries += 1
        self.status = WarmingStatus.PENDING
        self.error = None
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get task duration in milliseconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() * 1000
        return None


@dataclass
class WarmingStats:
    """Statistics for cache warming operations."""
    
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    total_keys_warmed: int = 0
    total_load_time_ms: float = 0.0
    average_load_time_ms: float = 0.0
    
    # Strategy-specific stats
    predictive_warmed: int = 0
    scheduled_warmed: int = 0
    adaptive_warmed: int = 0
    
    def record_completion(self, task: WarmupTask) -> None:
        """Record a completed task."""
        self.completed_tasks += 1
        self.total_keys_warmed += 1
        
        if task.duration_ms:
            self.total_load_time_ms += task.duration_ms
            self.average_load_time_ms = self.total_load_time_ms / self.completed_tasks
        
        if task.strategy == WarmingStrategy.PREDICTIVE:
            self.predictive_warmed += 1
        elif task.strategy == WarmingStrategy.SCHEDULED:
            self.scheduled_warmed += 1
        elif task.strategy == WarmingStrategy.ADAPTIVE:
            self.adaptive_warmed += 1
    
    def record_failure(self) -> None:
        """Record a failed task."""
        self.failed_tasks += 1
    
    def record_cancellation(self) -> None:
        """Record a cancelled task."""
        self.cancelled_tasks += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'cancelled_tasks': self.cancelled_tasks,
            'total_keys_warmed': self.total_keys_warmed,
            'total_load_time_ms': self.total_load_time_ms,
            'average_load_time_ms': self.average_load_time_ms,
            'predictive_warmed': self.predictive_warmed,
            'scheduled_warmed': self.scheduled_warmed,
            'adaptive_warmed': self.adaptive_warmed,
            'success_rate': self.completed_tasks / self.total_tasks if self.total_tasks > 0 else 0.0,
        }


@dataclass
class AccessPattern:
    """Represents an access pattern for predictive warming."""
    
    key: str
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    first_accessed: datetime = field(default_factory=datetime.now)
    access_hours: Set[int] = field(default_factory=set)  # Hours of day when accessed
    avg_interval_seconds: float = 0.0
    _last_interval: float = 0.0
    
    def record_access(self) -> None:
        """Record a new access."""
        now = datetime.now()
        if self.last_accessed:
            interval = (now - self.last_accessed).total_seconds()
            if self._last_interval > 0:
                self.avg_interval_seconds = (self.avg_interval_seconds + interval) / 2
            else:
                self.avg_interval_seconds = interval
            self._last_interval = interval
        
        self.last_accessed = now
        self.access_count += 1
        self.access_hours.add(now.hour)
    
    def predict_next_access(self) -> Optional[datetime]:
        """Predict the next access time."""
        if self.avg_interval_seconds <= 0:
            return None
        return self.last_accessed + timedelta(seconds=self.avg_interval_seconds)
    
    @property
    def importance_score(self) -> float:
        """Calculate importance score for warming priority."""
        # Higher score = more important to warm
        recency = (datetime.now() - self.last_accessed).total_seconds()
        frequency_weight = self.access_count * 10
        recency_weight = max(0, 1000 - recency / 60)  # Decay over time
        
        return frequency_weight + recency_weight


class CacheWarmer:
    """
    Manages cache warming strategies and operations.
    
    Features:
    - Multiple warming strategies (Predictive, Scheduled, Adaptive)
    - Background warming support
    - Priority-based task execution
    - Retry mechanism for failed tasks
    - Access pattern tracking for predictive warming
    """
    
    def __init__(
        self,
        cache: Any,
        max_workers: int = 3,
        default_strategy: WarmingStrategy = WarmingStrategy.PREDICTIVE,
        warming_interval: float = 60.0,
    ):
        """
        Initialize the cache warmer.
        
        Args:
            cache: The cache instance to warm (must have get/set methods)
            max_workers: Maximum number of background workers
            default_strategy: Default warming strategy
            warming_interval: Interval for periodic warming in seconds
        """
        self._cache = cache
        self._max_workers = max_workers
        self._default_strategy = default_strategy
        self._warming_interval = warming_interval
        
        # Task management
        self._tasks: Dict[str, WarmupTask] = {}
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._access_patterns: Dict[str, AccessPattern] = {}
        
        # Background worker management
        self._workers: List[threading.Thread] = []
        self._running = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        
        # Statistics
        self._stats = WarmingStats()
        
        # Scheduled warmups
        self._scheduled_warmups: Dict[str, List[str]] = {}  # schedule_id -> keys
    
    def warm(
        self,
        keys: List[str],
        loader: Union[Callable[[str], Any], Callable[[], Any]],
        strategy: Optional[WarmingStrategy] = None,
        priority: WarmingPriority = WarmingPriority.MEDIUM,
        ttl: Optional[float] = None,
    ) -> List[str]:
        """
        Queue keys for cache warming.
        
        Args:
            keys: List of keys to warm
            loader: Function to load values (receives key if takes 1 arg)
            strategy: Warming strategy to use
            priority: Task priority
            ttl: TTL for cached values
            
        Returns:
            List of task IDs created
        """
        strategy = strategy or self._default_strategy
        task_ids = []
        
        with self._lock:
            for key in keys:
                task_id = f"warm_{key}_{datetime.now().timestamp()}"
                
                # Create loader wrapper
                def make_loader(k: str):
                    def load():
                        import inspect
                        sig = inspect.signature(loader)
                        if len(sig.parameters) > 0:
                            return loader(k)
                        return loader()
                    return load
                
                task = WarmupTask(
                    task_id=task_id,
                    key=key,
                    loader=make_loader(key),
                    strategy=strategy,
                    priority=priority,
                    ttl=ttl,
                )
                
                self._tasks[task_id] = task
                # Priority queue: lower priority number = higher priority
                self._task_queue.put((priority.value, task_id, task))
                self._stats.total_tasks += 1
                task_ids.append(task_id)
        
        return task_ids
    
    def prefill(
        self,
        data: Dict[str, Any],
        strategy: WarmingStrategy = WarmingStrategy.SCHEDULED,
        ttl: Optional[float] = None,
    ) -> int:
        """
        Prefill cache with known data.
        
        Args:
            data: Dictionary of key-value pairs to cache
            strategy: Warming strategy to use
            ttl: TTL for cached values
            
        Returns:
            Number of entries prefilled
        """
        count = 0
        with self._lock:
            for key, value in data.items():
                self._cache.set(key, value, ttl=ttl)
                count += 1
                self._stats.total_keys_warmed += 1
                
                if strategy == WarmingStrategy.PREDICTIVE:
                    self._stats.predictive_warmed += 1
                elif strategy == WarmingStrategy.SCHEDULED:
                    self._stats.scheduled_warmed += 1
                elif strategy == WarmingStrategy.ADAPTIVE:
                    self._stats.adaptive_warmed += 1
        
        return count
    
    def start_background(self) -> None:
        """Start background warming workers."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._stop_event.clear()
            
            for i in range(self._max_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"cache-warmer-worker-{i}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)
    
    def stop_background(self, timeout: float = 10.0) -> None:
        """Stop background warming workers."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            self._stop_event.set()
            
            # Wait for workers to finish
            for worker in self._workers:
                worker.join(timeout=timeout)
            
            self._workers.clear()
    
    def record_access(self, key: str) -> None:
        """
        Record a cache access for pattern tracking.
        
        Args:
            key: The accessed key
        """
        with self._lock:
            if key not in self._access_patterns:
                self._access_patterns[key] = AccessPattern(key=key)
            self._access_patterns[key].record_access()
    
    def get_predictive_keys(
        self,
        top_n: int = 10,
        min_access_count: int = 2,
    ) -> List[str]:
        """
        Get keys predicted to need warming.
        
        Args:
            top_n: Maximum number of keys to return
            min_access_count: Minimum access count to consider
            
        Returns:
            List of keys predicted to be accessed
        """
        with self._lock:
            # Filter and score patterns
            candidates = [
                (key, pattern)
                for key, pattern in self._access_patterns.items()
                if pattern.access_count >= min_access_count
            ]
            
            # Sort by importance score
            candidates.sort(key=lambda x: x[1].importance_score, reverse=True)
            
            return [key for key, _ in candidates[:top_n]]
    
    def schedule_warmup(
        self,
        schedule_id: str,
        keys: List[str],
        trigger_time: datetime,
    ) -> None:
        """
        Schedule a warmup for a specific time.
        
        Args:
            schedule_id: Unique identifier for this schedule
            keys: Keys to warm
            trigger_time: When to trigger the warmup
        """
        with self._lock:
            self._scheduled_warmups[schedule_id] = keys
    
    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a scheduled warmup."""
        with self._lock:
            if schedule_id in self._scheduled_warmups:
                del self._scheduled_warmups[schedule_id]
                return True
            return False
    
    def get_task(self, task_id: str) -> Optional[WarmupTask]:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_pending_tasks(self) -> List[WarmupTask]:
        """Get all pending tasks."""
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status == WarmingStatus.PENDING
            ]
    
    def get_running_tasks(self) -> List[WarmupTask]:
        """Get all running tasks."""
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.status == WarmingStatus.RUNNING
            ]
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == WarmingStatus.PENDING:
                task.mark_cancelled()
                self._stats.cancelled_tasks += 1
                return True
            return False
    
    def retry_failed(self) -> int:
        """
        Retry all failed tasks that haven't exceeded max retries.
        
        Returns:
            Number of tasks queued for retry
        """
        count = 0
        with self._lock:
            for task in self._tasks.values():
                if task.can_retry():
                    task.increment_retry()
                    self._task_queue.put((task.priority.value, task.task_id, task))
                    count += 1
        return count
    
    def get_stats(self) -> WarmingStats:
        """Get warming statistics."""
        with self._lock:
            return WarmingStats(
                total_tasks=self._stats.total_tasks,
                completed_tasks=self._stats.completed_tasks,
                failed_tasks=self._stats.failed_tasks,
                cancelled_tasks=self._stats.cancelled_tasks,
                total_keys_warmed=self._stats.total_keys_warmed,
                total_load_time_ms=self._stats.total_load_time_ms,
                average_load_time_ms=self._stats.average_load_time_ms,
                predictive_warmed=self._stats.predictive_warmed,
                scheduled_warmed=self._stats.scheduled_warmed,
                adaptive_warmed=self._stats.adaptive_warmed,
            )
    
    def clear_stats(self) -> None:
        """Clear warming statistics."""
        with self._lock:
            self._stats = WarmingStats()
    
    def _worker_loop(self) -> None:
        """Background worker loop for processing tasks."""
        while self._running and not self._stop_event.is_set():
            try:
                # Get task with timeout
                try:
                    priority, task_id, task = self._task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Check if cancelled
                if task.status == WarmingStatus.CANCELLED:
                    continue
                
                # Execute task
                self._execute_task(task)
                
            except Exception as e:
                # Log error and continue
                pass
    
    def _execute_task(self, task: WarmupTask) -> None:
        """Execute a single warmup task."""
        task.mark_running()
        
        try:
            # Load value
            value = task.loader()
            
            # Store in cache
            self._cache.set(task.key, value, ttl=task.ttl)
            
            task.mark_completed()
            self._stats.record_completion(task)
            
        except Exception as e:
            task.mark_failed(str(e))
            self._stats.record_failure()
    
    def execute_now(self, task_ids: Optional[List[str]] = None) -> int:
        """
        Execute warming tasks immediately.
        
        Args:
            task_ids: Specific task IDs to execute (None = all pending)
            
        Returns:
            Number of tasks executed
        """
        count = 0
        
        with self._lock:
            tasks_to_run = []
            
            if task_ids:
                tasks_to_run = [
                    self._tasks[tid] for tid in task_ids
                    if tid in self._tasks and self._tasks[tid].status == WarmingStatus.PENDING
                ]
            else:
                tasks_to_run = [
                    task for task in self._tasks.values()
                    if task.status == WarmingStatus.PENDING
                ]
            
            # Sort by priority
            tasks_to_run.sort(key=lambda t: t.priority.value)
            
            for task in tasks_to_run:
                self._execute_task(task)
                count += 1
        
        return count
    
    def __len__(self) -> int:
        """Get number of pending tasks."""
        return len(self.get_pending_tasks())
