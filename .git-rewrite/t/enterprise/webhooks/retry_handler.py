# Retry Handler - Week 47 Builder 3
# Retry logic with exponential backoff and jitter

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import random
import math


class RetryStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    EXHAUSTED = "exhausted"


@dataclass
class RetryAttempt:
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    delay_seconds: float = 0


@dataclass
class RetryConfig:
    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retryable_errors: List[str] = field(default_factory=list)


@dataclass
class RetryTask:
    id: str
    payload: Dict[str, Any]
    config: RetryConfig
    status: RetryStatus = RetryStatus.PENDING
    attempts: List[RetryAttempt] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_attempt_at: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    total_delay_seconds: float = 0


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter"""

    def __init__(self):
        self._tasks: Dict[str, RetryTask] = {}
        self._handlers: Dict[str, Callable] = {}
        self._metrics = {
            "total_retries": 0,
            "successful_retries": 0,
            "exhausted_retries": 0,
            "total_attempts": 0
        }

    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a handler for a task type"""
        self._handlers[task_type] = handler

    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate delay for the next attempt with exponential backoff"""
        # Exponential backoff
        delay = config.initial_delay_seconds * (config.backoff_multiplier ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, config.max_delay_seconds)
        
        # Add jitter
        if config.jitter:
            jitter_range = delay * config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)

    def create_task(
        self,
        task_id: str,
        payload: Dict[str, Any],
        config: Optional[RetryConfig] = None
    ) -> RetryTask:
        """Create a new retry task"""
        task = RetryTask(
            id=task_id,
            payload=payload,
            config=config or RetryConfig()
        )
        self._tasks[task_id] = task
        return task

    async def execute_with_retry(
        self,
        task_id: str,
        handler: Optional[Callable] = None
    ) -> RetryTask:
        """Execute a task with retry logic"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = RetryStatus.IN_PROGRESS

        for attempt_num in range(1, task.config.max_attempts + 1):
            self._metrics["total_attempts"] += 1
            attempt = RetryAttempt(
                attempt_number=attempt_num,
                started_at=datetime.utcnow()
            )

            if attempt_num > 1:
                delay = self.calculate_delay(attempt_num - 1, task.config)
                attempt.delay_seconds = delay
                task.total_delay_seconds += delay
                await asyncio.sleep(delay)

            try:
                h = handler or self._handlers.get(task.payload.get("type"))
                if not h:
                    raise ValueError("No handler available")

                if asyncio.iscoroutinefunction(h):
                    result = await h(task.payload)
                else:
                    result = h(task.payload)

                attempt.success = True
                attempt.completed_at = datetime.utcnow()
                task.attempts.append(attempt)
                task.status = RetryStatus.SUCCESS
                self._metrics["successful_retries"] += 1
                return task

            except Exception as e:
                attempt.success = False
                attempt.error_message = str(e)
                attempt.completed_at = datetime.utcnow()
                task.attempts.append(attempt)
                task.last_attempt_at = datetime.utcnow()

                # Check if error is retryable
                if task.config.retryable_errors:
                    if str(e) not in task.config.retryable_errors:
                        task.status = RetryStatus.FAILED
                        return task

        # All attempts exhausted
        task.status = RetryStatus.EXHAUSTED
        self._metrics["exhausted_retries"] += 1
        return task

    def schedule_retry(
        self,
        task_id: str,
        delay_seconds: float
    ) -> bool:
        """Schedule the next retry attempt"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        return True

    def get_task(self, task_id: str) -> Optional[RetryTask]:
        """Get a retry task by ID"""
        return self._tasks.get(task_id)

    def get_pending_tasks(self) -> List[RetryTask]:
        """Get all pending tasks"""
        return [t for t in self._tasks.values() if t.status == RetryStatus.PENDING]

    def get_exhausted_tasks(self) -> List[RetryTask]:
        """Get all exhausted tasks"""
        return [t for t in self._tasks.values() if t.status == RetryStatus.EXHAUSTED]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a retry task"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in [RetryStatus.SUCCESS, RetryStatus.EXHAUSTED]:
            return False
        task.status = RetryStatus.FAILED
        return True

    def get_remaining_attempts(self, task_id: str) -> int:
        """Get remaining attempts for a task"""
        task = self._tasks.get(task_id)
        if not task:
            return 0
        return task.config.max_attempts - len(task.attempts)

    def get_metrics(self) -> Dict[str, Any]:
        """Get retry handler metrics"""
        return {
            **self._metrics,
            "active_tasks": len([t for t in self._tasks.values() 
                               if t.status in [RetryStatus.PENDING, RetryStatus.IN_PROGRESS]]),
            "total_tasks": len(self._tasks)
        }

    def clear_completed_tasks(self, older_than: Optional[datetime] = None) -> int:
        """Clear completed tasks"""
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.status in [RetryStatus.SUCCESS, RetryStatus.EXHAUSTED, RetryStatus.FAILED]:
                if older_than is None or task.created_at < older_than:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        return len(to_remove)

    async def retry_exhausted_task(
        self,
        task_id: str,
        new_config: Optional[RetryConfig] = None
    ) -> Optional[RetryTask]:
        """Reset and retry an exhausted task"""
        task = self._tasks.get(task_id)
        if not task or task.status != RetryStatus.EXHAUSTED:
            return None

        task.status = RetryStatus.PENDING
        task.attempts = []
        task.total_delay_seconds = 0
        if new_config:
            task.config = new_config

        return await self.execute_with_retry(task_id)
