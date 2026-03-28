"""Recovery Scheduler for Cart Abandonment.

Provides optimal timing for recovery messages:
- Optimal timing algorithm
- Multi-touch sequence scheduling
- Timezone-aware scheduling
- Business hours respect
- Retry logic with backoff
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from decimal import Decimal
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SchedulePriority(str, Enum):
    """Schedule priority."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ScheduledRecovery:
    """Scheduled recovery message."""
    schedule_id: str
    cart_id: str
    customer_id: str
    channel: str
    scheduled_time: datetime
    priority: SchedulePriority
    attempt_number: int
    status: str = "pending"


@dataclass
class BusinessHours:
    """Business hours configuration."""
    start: time
    end: time
    timezone: str
    days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri


class RecoveryScheduler:
    """Scheduler for cart recovery messages."""

    # Optimal delays for multi-touch sequence (in hours)
    TOUCH_DELAYS = [1, 24, 72]  # 1 hour, 24 hours, 72 hours

    # Best times to send (hour in local time)
    OPTIMAL_HOURS = [10, 14, 19]  # 10am, 2pm, 7pm

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize scheduler.

        Args:
            client_id: Client identifier
            config: Optional configuration
        """
        self.client_id = client_id
        self.config = config or {}
        self.default_timezone = self.config.get("timezone", "America/New_York")
        self.business_hours = BusinessHours(
            start=time(9, 0),
            end=time(21, 0),
            timezone=self.default_timezone
        )
        self._schedules: Dict[str, ScheduledRecovery] = {}

    def schedule_recovery(
        self,
        cart_id: str,
        customer_id: str,
        customer_timezone: Optional[str] = None,
        cart_value: Optional[Decimal] = None
    ) -> List[ScheduledRecovery]:
        """Schedule multi-touch recovery sequence.

        Args:
            cart_id: Cart identifier
            customer_id: Customer identifier
            customer_timezone: Customer's timezone
            cart_value: Cart value for prioritization

        Returns:
            List of scheduled recoveries
        """
        timezone = customer_timezone or self.default_timezone
        priority = self._determine_priority(cart_value)

        schedules = []
        for attempt, delay_hours in enumerate(self.TOUCH_DELAYS):
            optimal_time = self._calculate_optimal_time(
                delay_hours, timezone, attempt
            )

            schedule = ScheduledRecovery(
                schedule_id=f"sch_{cart_id}_{attempt}",
                cart_id=cart_id,
                customer_id=customer_id,
                channel=self._select_channel(attempt, cart_value),
                scheduled_time=optimal_time,
                priority=priority,
                attempt_number=attempt + 1
            )

            schedules.append(schedule)
            self._schedules[schedule.schedule_id] = schedule

        logger.info(
            "Scheduled recovery sequence",
            extra={
                "client_id": self.client_id,
                "cart_id": cart_id,
                "schedules_count": len(schedules)
            }
        )

        return schedules

    def get_next_schedule(self, limit: int = 100) -> List[ScheduledRecovery]:
        """Get next scheduled recoveries to send.

        Args:
            limit: Maximum number to return

        Returns:
            List of schedules due for sending
        """
        now = datetime.utcnow()
        due = []

        for schedule in self._schedules.values():
            if (schedule.status == "pending" and
                schedule.scheduled_time <= now):
                due.append(schedule)

        # Sort by priority
        priority_order = {
            SchedulePriority.HIGH: 0,
            SchedulePriority.MEDIUM: 1,
            SchedulePriority.LOW: 2
        }
        due.sort(key=lambda x: priority_order[x.priority])

        return due[:limit]

    def mark_sent(self, schedule_id: str) -> bool:
        """Mark schedule as sent.

        Args:
            schedule_id: Schedule identifier

        Returns:
            True if successful
        """
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.status = "sent"
            return True
        return False

    def reschedule(
        self,
        schedule_id: str,
        new_time: datetime
    ) -> Optional[ScheduledRecovery]:
        """Reschedule a recovery message.

        Args:
            schedule_id: Schedule identifier
            new_time: New scheduled time

        Returns:
            Updated schedule or None
        """
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.scheduled_time = new_time
            schedule.status = "rescheduled"
            return schedule
        return None

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a scheduled recovery.

        Args:
            schedule_id: Schedule identifier

        Returns:
            True if cancelled
        """
        schedule = self._schedules.get(schedule_id)
        if schedule:
            schedule.status = "cancelled"
            return True
        return False

    def calculate_backoff(
        self,
        attempt: int,
        base_delay_hours: int = 24
    ) -> int:
        """Calculate backoff delay in hours.

        Args:
            attempt: Attempt number
            base_delay_hours: Base delay in hours

        Returns:
            Delay in hours
        """
        # Exponential backoff: 1x, 2x, 4x
        multiplier = 2 ** (attempt - 1)
        return base_delay_hours * multiplier

    def _calculate_optimal_time(
        self,
        delay_hours: int,
        timezone: str,
        attempt: int
    ) -> datetime:
        """Calculate optimal send time."""
        base_time = datetime.utcnow() + timedelta(hours=delay_hours)

        # Adjust to optimal hour
        optimal_hour = self.OPTIMAL_HOURS[attempt % len(self.OPTIMAL_HOURS)]
        adjusted = base_time.replace(
            hour=optimal_hour,
            minute=0,
            second=0,
            microsecond=0
        )

        # Ensure it's in the future
        if adjusted < datetime.utcnow():
            adjusted += timedelta(days=1)

        return adjusted

    def _determine_priority(
        self,
        cart_value: Optional[Decimal]
    ) -> SchedulePriority:
        """Determine schedule priority based on cart value."""
        if cart_value is None:
            return SchedulePriority.MEDIUM

        if cart_value >= Decimal("200"):
            return SchedulePriority.HIGH
        elif cart_value >= Decimal("50"):
            return SchedulePriority.MEDIUM
        return SchedulePriority.LOW

    def _select_channel(
        self,
        attempt: int,
        cart_value: Optional[Decimal]
    ) -> str:
        """Select channel based on attempt and value."""
        if attempt == 0:
            return "email"
        elif attempt == 1:
            return "email"
        else:
            return "sms"

    def is_within_business_hours(
        self,
        dt: datetime,
        timezone: Optional[str] = None
    ) -> bool:
        """Check if datetime is within business hours.

        Args:
            dt: Datetime to check
            timezone: Timezone to use

        Returns:
            True if within business hours
        """
        # Check day of week (0=Monday)
        if dt.weekday() not in self.business_hours.days:
            return False

        # Check time
        check_time = dt.time()
        return self.business_hours.start <= check_time <= self.business_hours.end

    def get_next_business_time(
        self,
        dt: datetime
    ) -> datetime:
        """Get next business time from given datetime.

        Args:
            dt: Starting datetime

        Returns:
            Next valid business datetime
        """
        result = dt

        # Adjust to business hours start if outside
        if result.time() < self.business_hours.start:
            result = result.replace(
                hour=self.business_hours.start.hour,
                minute=self.business_hours.start.minute
            )
        elif result.time() > self.business_hours.end:
            # Move to next day
            result = result + timedelta(days=1)
            result = result.replace(
                hour=self.business_hours.start.hour,
                minute=self.business_hours.start.minute
            )

        # Move to valid business day
        while result.weekday() not in self.business_hours.days:
            result = result + timedelta(days=1)

        return result
