"""
PARWA End-to-End (E2E) Tests Module.

E2E tests validate complete user workflows from start to finish.
These tests verify that all system components work together correctly.

Key E2E Test Scenarios:
- Onboarding Flow: Signup → Onboarding → Live
- Refund Workflow: Ticket → Approval → Stripe call (once)
- Jarvis Commands: Pause/Resume refunds, System status
- Stuck Ticket Escalation: 4-phase escalation at 24h/48h/72h
- Agent Lightning Training: Collect → Export → Train → Deploy
- GDPR Compliance: Export, Erasure (PII anonymized, row preserved)

CRITICAL Requirements Tested:
- Stripe called EXACTLY once after approval, NEVER before
- Jarvis pause_refunds Redis key set within 500ms
- Escalation 4-phase fires at exact 24h/48h/72h thresholds
- Voice calls answered in < 6 seconds
- GDPR: PII anonymized, row preserved
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import asyncio
import time


class E2ETestHelper:
    """
    Helper class for E2E test utilities.

    Provides common functionality for E2E tests including
    timing measurements, state tracking, and assertions.
    """

    @staticmethod
    def measure_time_ms(start_time: float) -> float:
        """
        Measure elapsed time in milliseconds.

        Args:
            start_time: Start time from time.time()

        Returns:
            Elapsed time in milliseconds
        """
        return (time.time() - start_time) * 1000

    @staticmethod
    def assert_within_target(
        actual_ms: float,
        target_ms: float,
        operation: str = "Operation"
    ) -> None:
        """
        Assert that operation completed within target time.

        Args:
            actual_ms: Actual execution time in ms
            target_ms: Target execution time in ms
            operation: Name of operation for error message

        Raises:
            AssertionError: If actual time exceeds target
        """
        if actual_ms > target_ms:
            raise AssertionError(
                f"{operation} took {actual_ms:.2f}ms, "
                f"exceeds target of {target_ms}ms"
            )

    @staticmethod
    def create_timestamp(hours_ago: int = 0) -> datetime:
        """
        Create a timestamp relative to now.

        Args:
            hours_ago: Hours in the past

        Returns:
            Datetime timestamp
        """
        return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


class MockStripeClient:
    """
    Mock Stripe client for E2E testing.

    Tracks all refund calls to verify the refund gate is enforced.
    """

    def __init__(self) -> None:
        """Initialize mock Stripe client."""
        self._refund_calls: List[Dict[str, Any]] = []
        self._call_count = 0

    async def process_refund(
        self,
        amount: float,
        transaction_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mock process refund.

        Args:
            amount: Refund amount
            transaction_id: Original transaction ID
            reason: Optional refund reason

        Returns:
            Mock refund result
        """
        self._call_count += 1
        refund_record = {
            "call_number": self._call_count,
            "amount": amount,
            "transaction_id": transaction_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "processed",
            "refund_id": f"re_mock_{self._call_count}"
        }
        self._refund_calls.append(refund_record)
        return refund_record

    def get_call_count(self) -> int:
        """
        Get number of times process_refund was called.

        Returns:
            Number of refund calls
        """
        return self._call_count

    def get_calls(self) -> List[Dict[str, Any]]:
        """
        Get all refund call records.

        Returns:
            List of refund call records
        """
        return self._refund_calls.copy()

    def reset(self) -> None:
        """Reset the mock state."""
        self._refund_calls = []
        self._call_count = 0


class MockRedisClient:
    """
    Mock Redis client for E2E testing.

    Simulates Redis operations for pause/resume refund testing.
    """

    def __init__(self) -> None:
        """Initialize mock Redis client."""
        self._store: Dict[str, str] = {}
        self._expiry: Dict[str, datetime] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None
    ) -> bool:
        """
        Set a key-value pair.

        Args:
            key: Redis key
            value: Value to store
            ex: Expiry time in seconds

        Returns:
            True if successful
        """
        self._store[key] = value
        if ex:
            self._expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=ex)
        return True

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key.

        Args:
            key: Redis key

        Returns:
            Value if exists, None otherwise
        """
        # Check expiry
        if key in self._expiry:
            if datetime.now(timezone.utc) > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return None
        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        """
        Delete a key.

        Args:
            key: Key to delete

        Returns:
            True if deleted
        """
        if key in self._store:
            del self._store[key]
            if key in self._expiry:
                del self._expiry[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Key to check

        Returns:
            True if exists
        """
        # Check expiry
        if key in self._expiry:
            if datetime.now(timezone.utc) > self._expiry[key]:
                del self._store[key]
                del self._expiry[key]
                return False
        return key in self._store

    def reset(self) -> None:
        """Reset the mock state."""
        self._store = {}
        self._expiry = {}


__all__ = [
    "E2ETestHelper",
    "MockStripeClient",
    "MockRedisClient",
]
