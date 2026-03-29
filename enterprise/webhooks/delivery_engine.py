"""Webhook Delivery Engine"""
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import asyncio
import aiohttp
import time
from collections import deque

logger = logging.getLogger(__name__)

class DeliveryStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class DeliveryAttempt:
    attempt_id: str
    webhook_id: str
    event_id: str
    url: str
    payload: Dict[str, Any]
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempt_number: int = 1
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0

@dataclass
class RetryConfig:
    max_attempts: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True

class DeliveryEngine:
    def __init__(self, retry_config: RetryConfig = None):
        self.retry_config = retry_config or RetryConfig()
        self._queue: deque = deque()
        self._attempts: Dict[str, DeliveryAttempt] = {}
        self._processing = False
        self._metrics = {"total_deliveries": 0, "successful": 0, "failed": 0, "retries": 0}

    def queue_delivery(self, webhook_id: str, url: str, payload: Dict[str, Any], event_id: str) -> DeliveryAttempt:
        attempt_id = f"del_{int(time.time() * 1000)}_{len(self._attempts)}"
        attempt = DeliveryAttempt(
            attempt_id=attempt_id,
            webhook_id=webhook_id,
            event_id=event_id,
            url=url,
            payload=payload,
            max_attempts=self.retry_config.max_attempts
        )
        self._attempts[attempt_id] = attempt
        self._queue.append(attempt_id)
        self._metrics["total_deliveries"] += 1
        return attempt

    async def deliver(self, attempt: DeliveryAttempt, session: aiohttp.ClientSession = None) -> DeliveryAttempt:
        attempt.status = DeliveryStatus.IN_PROGRESS
        attempt.started_at = datetime.utcnow()
        start_time = time.time()

        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        try:
            async with session.post(attempt.url, json=attempt.payload, headers={"Content-Type": "application/json"}) as response:
                attempt.response_status = response.status
                attempt.response_body = await response.text()[:1000]
                attempt.latency_ms = (time.time() - start_time) * 1000

                if 200 <= response.status < 300:
                    attempt.status = DeliveryStatus.SUCCESS
                    attempt.completed_at = datetime.utcnow()
                    self._metrics["successful"] += 1
                else:
                    raise Exception(f"HTTP {response.status}")

        except Exception as e:
            attempt.error_message = str(e)
            attempt.latency_ms = (time.time() - start_time) * 1000

            if attempt.attempt_number < attempt.max_attempts:
                attempt.status = DeliveryStatus.RETRYING
                self._metrics["retries"] += 1
                await self._schedule_retry(attempt)
            else:
                attempt.status = DeliveryStatus.FAILED
                attempt.completed_at = datetime.utcnow()
                self._metrics["failed"] += 1

        finally:
            if own_session:
                await session.close()

        return attempt

    async def _schedule_retry(self, attempt: DeliveryAttempt) -> None:
        delay = self._calculate_delay(attempt.attempt_number)
        await asyncio.sleep(delay)
        attempt.attempt_number += 1
        self._queue.append(attempt.attempt_id)

    def _calculate_delay(self, attempt_number: int) -> float:
        delay = self.retry_config.base_delay_seconds * (self.retry_config.backoff_multiplier ** (attempt_number - 1))
        delay = min(delay, self.retry_config.max_delay_seconds)
        if self.retry_config.jitter:
            import random
            delay = delay * (0.5 + random.random())
        return delay

    async def process_queue(self) -> int:
        processed = 0
        while self._queue:
            attempt_id = self._queue.popleft()
            attempt = self._attempts.get(attempt_id)
            if attempt and attempt.status not in [DeliveryStatus.SUCCESS, DeliveryStatus.FAILED]:
                await self.deliver(attempt)
                processed += 1
        return processed

    def get_attempt(self, attempt_id: str) -> Optional[DeliveryAttempt]:
        return self._attempts.get(attempt_id)

    def get_pending_attempts(self) -> List[DeliveryAttempt]:
        return [a for a in self._attempts.values() if a.status == DeliveryStatus.PENDING]

    def get_retry_attempts(self) -> List[DeliveryAttempt]:
        return [a for a in self._attempts.values() if a.status == DeliveryStatus.RETRYING]

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics, "queue_size": len(self._queue), "total_attempts": len(self._attempts)}
