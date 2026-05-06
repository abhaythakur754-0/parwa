"""
Webhook Retry Logic
Enterprise Integration Hub - Week 43 Builder 4
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Retry strategy types"""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 5
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    jitter_factor: float = 0.1
    retry_on_status_codes: List[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "strategy": self.strategy.value,
            "base_delay_seconds": self.base_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "jitter_factor": self.jitter_factor,
            "retry_on_status_codes": self.retry_on_status_codes
        }


@dataclass
class RetryState:
    """State of a retry sequence"""
    attempt: int = 0
    next_delay: float = 0.0
    last_error: Optional[str] = None
    last_status_code: Optional[int] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_attempt_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt,
            "next_delay": self.next_delay,
            "last_error": self.last_error,
            "last_status_code": self.last_status_code,
            "started_at": self.started_at.isoformat(),
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None
        }


class RetryCalculator:
    """Calculate retry delays based on strategy"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number"""
        if attempt <= 0:
            return 0.0
        
        strategy = self.config.strategy
        
        if strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay_seconds
        
        elif strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay_seconds * attempt
        
        elif strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay_seconds * (2 ** (attempt - 1))
        
        elif strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = self.config.base_delay_seconds * (2 ** (attempt - 1))
            jitter = base_delay * self.config.jitter_factor * random.random()
            delay = base_delay + jitter
        
        else:
            delay = self.config.base_delay_seconds
        
        # Apply max delay cap
        return min(delay, self.config.max_delay_seconds)
    
    def should_retry(
        self,
        attempt: int,
        status_code: Optional[int] = None,
        error: Optional[str] = None
    ) -> bool:
        """Determine if a retry should be attempted"""
        if attempt >= self.config.max_retries:
            return False
        
        if status_code and status_code not in self.config.retry_on_status_codes:
            return False
        
        return True
    
    def get_next_retry_time(self, attempt: int) -> datetime:
        """Get the datetime for the next retry"""
        delay = self.calculate_delay(attempt)
        return datetime.utcnow() + timedelta(seconds=delay)


class WebhookRetryQueue:
    """Queue for managing webhook retries"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.calculator = RetryCalculator(self.config)
        self._queue: Dict[str, RetryState] = {}
        self._pending: List[Dict[str, Any]] = []
    
    def enqueue(
        self,
        webhook_id: str,
        endpoint_id: str,
        payload: Dict[str, Any],
        status_code: Optional[int] = None,
        error: Optional[str] = None
    ) -> RetryState:
        """Add a failed webhook to the retry queue"""
        existing = self._queue.get(webhook_id)
        
        if existing:
            existing.attempt += 1
            existing.last_error = error
            existing.last_status_code = status_code
            existing.last_attempt_at = datetime.utcnow()
            existing.next_delay = self.calculator.calculate_delay(existing.attempt)
        else:
            state = RetryState(
                attempt=1,
                next_delay=self.calculator.calculate_delay(1),
                last_error=error,
                last_status_code=status_code,
                last_attempt_at=datetime.utcnow()
            )
            self._queue[webhook_id] = state
        
        # Add to pending list
        self._pending.append({
            "webhook_id": webhook_id,
            "endpoint_id": endpoint_id,
            "payload": payload,
            "scheduled_for": self.calculator.get_next_retry_time(
                self._queue[webhook_id].attempt
            )
        })
        
        return self._queue[webhook_id]
    
    def dequeue(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Remove a webhook from the queue"""
        if webhook_id in self._queue:
            del self._queue[webhook_id]
        
        for i, item in enumerate(self._pending):
            if item["webhook_id"] == webhook_id:
                return self._pending.pop(i)
        
        return None
    
    def get_ready_retries(self) -> List[Dict[str, Any]]:
        """Get webhooks ready for retry"""
        now = datetime.utcnow()
        ready = []
        
        for item in self._pending:
            if item["scheduled_for"] <= now:
                ready.append(item)
        
        return ready
    
    def get_state(self, webhook_id: str) -> Optional[RetryState]:
        """Get retry state for a webhook"""
        return self._queue.get(webhook_id)
    
    def should_retry(self, webhook_id: str) -> bool:
        """Check if a webhook should be retried"""
        state = self._queue.get(webhook_id)
        if not state:
            return False
        
        return self.calculator.should_retry(
            state.attempt,
            state.last_status_code,
            state.last_error
        )
    
    def clear(self) -> None:
        """Clear all pending retries"""
        self._queue.clear()
        self._pending.clear()
    
    def size(self) -> int:
        """Get the number of pending retries"""
        return len(self._pending)


class WebhookRetryProcessor:
    """Process webhook retries with configurable behavior"""
    
    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        delivery_handler: Optional[Callable] = None
    ):
        self.config = config or RetryConfig()
        self.queue = WebhookRetryQueue(self.config)
        self.delivery_handler = delivery_handler
        self._running = False
        self._processed_count = 0
        self._success_count = 0
        self._failure_count = 0
    
    async def start(self) -> None:
        """Start the retry processor"""
        self._running = True
        logger.info("Webhook retry processor started")
        
        while self._running:
            try:
                await self._process_ready()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
    
    def stop(self) -> None:
        """Stop the retry processor"""
        self._running = False
        logger.info("Webhook retry processor stopped")
    
    async def _process_ready(self) -> None:
        """Process all ready retries"""
        ready = self.queue.get_ready_retries()
        
        for item in ready:
            try:
                if self.delivery_handler:
                    success = await self.delivery_handler(
                        item["endpoint_id"],
                        item["payload"]
                    )
                    
                    self._processed_count += 1
                    
                    if success:
                        self._success_count += 1
                        self.queue.dequeue(item["webhook_id"])
                        logger.info(f"Retry successful: {item['webhook_id']}")
                    else:
                        self._failure_count += 1
                        if self.queue.should_retry(item["webhook_id"]):
                            self.queue.enqueue(
                                item["webhook_id"],
                                item["endpoint_id"],
                                item["payload"],
                                error="Delivery failed"
                            )
                        else:
                            self.queue.dequeue(item["webhook_id"])
                            logger.warning(f"Max retries exceeded: {item['webhook_id']}")
                            
            except Exception as e:
                logger.error(f"Retry processing error: {e}")
    
    def add_failed_delivery(
        self,
        webhook_id: str,
        endpoint_id: str,
        payload: Dict[str, Any],
        status_code: Optional[int] = None,
        error: Optional[str] = None
    ) -> RetryState:
        """Add a failed delivery for retry"""
        return self.queue.enqueue(
            webhook_id,
            endpoint_id,
            payload,
            status_code,
            error
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retry processor statistics"""
        return {
            "running": self._running,
            "queue_size": self.queue.size(),
            "processed_count": self._processed_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "config": self.config.to_dict()
        }
    
    async def process_immediately(
        self,
        webhook_id: str,
        endpoint_id: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Immediately process a webhook (for testing)"""
        if self.delivery_handler:
            return await self.delivery_handler(endpoint_id, payload)
        return False
