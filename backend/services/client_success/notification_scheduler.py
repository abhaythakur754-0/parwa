"""
Notification Scheduler Service

Schedules notifications with support for future messages, recurring
notifications, timezone-aware scheduling, optimal send time calculation,
and batch scheduling.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, time
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """Status of a scheduled notification."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RecurrenceType(str, Enum):
    """Types of recurrence."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class ScheduledNotification:
    """A scheduled notification."""
    schedule_id: str
    client_id: str
    channel: str
    subject: str
    body: str
    scheduled_for: datetime
    status: ScheduleStatus = ScheduleStatus.PENDING
    recurrence: RecurrenceType = RecurrenceType.NONE
    recurrence_config: Dict[str, Any] = field(default_factory=dict)
    timezone: str = "UTC"
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    next_occurrence: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationScheduler:
    """
    Schedule notifications for future delivery.

    Provides:
    - Schedule future messages
    - Recurring notifications
    - Timezone-aware scheduling
    - Optimal send time calculation
    - Batch scheduling
    """

    # Optimal send times by day of week (24-hour format)
    OPTIMAL_SEND_TIMES = {
        0: time(10, 0),  # Monday - 10 AM
        1: time(10, 0),  # Tuesday - 10 AM
        2: time(10, 0),  # Wednesday - 10 AM
        3: time(10, 0),  # Thursday - 10 AM
        4: time(10, 0),  # Friday - 10 AM
        5: None,         # Saturday - Not recommended
        6: None,         # Sunday - Not recommended
    }

    # All supported clients
    SUPPORTED_CLIENTS = [
        "client_001", "client_002", "client_003", "client_004", "client_005",
        "client_006", "client_007", "client_008", "client_009", "client_010"
    ]

    def __init__(self):
        """Initialize notification scheduler."""
        self._scheduled: Dict[str, List[ScheduledNotification]] = {
            client: [] for client in self.SUPPORTED_CLIENTS
        }
        self._schedule_counter = 0

    def schedule_notification(
        self,
        client_id: str,
        channel: str,
        subject: str,
        body: str,
        scheduled_for: datetime,
        timezone: str = "UTC",
        recurrence: RecurrenceType = RecurrenceType.NONE,
        recurrence_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScheduledNotification:
        """
        Schedule a notification for future delivery.

        Args:
            client_id: Client identifier
            channel: Communication channel
            subject: Message subject
            body: Message body
            scheduled_for: When to send
            timezone: Client timezone
            recurrence: Recurrence type
            recurrence_config: Recurrence configuration
            metadata: Optional metadata

        Returns:
            ScheduledNotification
        """
        if client_id not in self.SUPPORTED_CLIENTS:
            raise ValueError(f"Unsupported client: {client_id}")

        self._schedule_counter += 1
        schedule_id = f"schedule_{self._schedule_counter:06d}"

        # Calculate next occurrence for recurring
        next_occurrence = None
        if recurrence != RecurrenceType.NONE:
            next_occurrence = self._calculate_next_occurrence(
                scheduled_for, recurrence, recurrence_config
            )

        notification = ScheduledNotification(
            schedule_id=schedule_id,
            client_id=client_id,
            channel=channel,
            subject=subject,
            body=body,
            scheduled_for=scheduled_for,
            timezone=timezone,
            recurrence=recurrence,
            recurrence_config=recurrence_config or {},
            next_occurrence=next_occurrence,
            metadata=metadata or {},
        )

        self._scheduled[client_id].append(notification)
        logger.info(f"Scheduled notification {schedule_id} for {client_id} at {scheduled_for}")

        return notification

    def schedule_optimal_time(
        self,
        client_id: str,
        channel: str,
        subject: str,
        body: str,
        preferred_day: Optional[int] = None,
        timezone: str = "UTC"
    ) -> ScheduledNotification:
        """
        Schedule at optimal send time.

        Args:
            client_id: Client identifier
            channel: Communication channel
            subject: Message subject
            body: Message body
            preferred_day: Preferred day (0=Monday), defaults to next business day
            timezone: Client timezone

        Returns:
            ScheduledNotification at optimal time
        """
        now = datetime.utcnow()

        # Determine day
        if preferred_day is not None:
            days_ahead = (preferred_day - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week if same day
        else:
            # Next business day
            days_ahead = 1
            if now.weekday() >= 4:  # Friday or later
                days_ahead = (7 - now.weekday()) % 7 or 7

        target_date = now + timedelta(days=days_ahead)
        optimal_time = self.OPTIMAL_SEND_TIMES.get(target_date.weekday())

        if optimal_time is None:
            # Weekend, move to Monday
            days_until_monday = (7 - target_date.weekday()) % 7 or 7
            target_date = target_date + timedelta(days=days_until_monday)
            optimal_time = time(10, 0)

        scheduled_for = datetime.combine(target_date.date(), optimal_time)

        return self.schedule_notification(
            client_id=client_id,
            channel=channel,
            subject=subject,
            body=body,
            scheduled_for=scheduled_for,
            timezone=timezone
        )

    def batch_schedule(
        self,
        client_ids: List[str],
        channel: str,
        subject: str,
        body: str,
        scheduled_for: datetime,
        stagger_minutes: int = 5
    ) -> Dict[str, ScheduledNotification]:
        """
        Schedule notifications for multiple clients.

        Args:
            client_ids: List of client identifiers
            channel: Communication channel
            subject: Message subject
            body: Message body
            scheduled_for: Base scheduled time
            stagger_minutes: Minutes to stagger between clients

        Returns:
            Dict mapping client_id to ScheduledNotification
        """
        results = {}

        for i, client_id in enumerate(client_ids):
            if client_id not in self.SUPPORTED_CLIENTS:
                continue

            # Stagger times
            staggered_time = scheduled_for + timedelta(minutes=i * stagger_minutes)

            notification = self.schedule_notification(
                client_id=client_id,
                channel=channel,
                subject=subject,
                body=body,
                scheduled_for=staggered_time
            )
            results[client_id] = notification

        logger.info(f"Batch scheduled {len(results)} notifications")
        return results

    def get_pending_notifications(self) -> List[ScheduledNotification]:
        """
        Get all pending notifications due now.

        Returns:
            List of notifications ready to send
        """
        now = datetime.utcnow()
        pending = []

        for client_id, notifications in self._scheduled.items():
            for notification in notifications:
                if (notification.status == ScheduleStatus.PENDING
                    and notification.scheduled_for <= now):
                    pending.append(notification)

        # Sort by scheduled time
        pending.sort(key=lambda n: n.scheduled_for)
        return pending

    async def process_pending(
        self,
        send_handler: callable
    ) -> Dict[str, Any]:
        """
        Process all pending notifications.

        Args:
            send_handler: Async callable to send notifications

        Returns:
            Dict with processing results
        """
        pending = self.get_pending_notifications()
        results = {"processed": 0, "success": 0, "failed": 0}

        for notification in pending:
            notification.status = ScheduleStatus.QUEUED

            try:
                await send_handler(notification)
                notification.status = ScheduleStatus.SENT
                notification.sent_at = datetime.utcnow()
                results["success"] += 1

                # Handle recurring
                if notification.recurrence != RecurrenceType.NONE:
                    self._create_next_recurrence(notification)

            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                notification.status = ScheduleStatus.FAILED
                results["failed"] += 1

            results["processed"] += 1

        logger.info(f"Processed {results['processed']} notifications")
        return results

    def _calculate_next_occurrence(
        self,
        current: datetime,
        recurrence: RecurrenceType,
        config: Optional[Dict[str, Any]]
    ) -> datetime:
        """Calculate next occurrence for recurring notifications."""
        if recurrence == RecurrenceType.DAILY:
            return current + timedelta(days=1)
        elif recurrence == RecurrenceType.WEEKLY:
            return current + timedelta(weeks=1)
        elif recurrence == RecurrenceType.MONTHLY:
            # Same day next month
            next_month = current.month + 1
            next_year = current.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            return current.replace(year=next_year, month=next_month)
        elif recurrence == RecurrenceType.CUSTOM and config:
            days = config.get("interval_days", 7)
            return current + timedelta(days=days)
        else:
            return current + timedelta(days=7)

    def _create_next_recurrence(
        self,
        notification: ScheduledNotification
    ) -> Optional[ScheduledNotification]:
        """Create next occurrence of a recurring notification."""
        if notification.recurrence == RecurrenceType.NONE:
            return None

        next_time = self._calculate_next_occurrence(
            notification.scheduled_for,
            notification.recurrence,
            notification.recurrence_config
        )

        return self.schedule_notification(
            client_id=notification.client_id,
            channel=notification.channel,
            subject=notification.subject,
            body=notification.body,
            scheduled_for=next_time,
            timezone=notification.timezone,
            recurrence=notification.recurrence,
            recurrence_config=notification.recurrence_config,
            metadata=notification.metadata
        )

    def cancel_schedule(
        self,
        schedule_id: str
    ) -> Optional[ScheduledNotification]:
        """
        Cancel a scheduled notification.

        Args:
            schedule_id: Schedule identifier

        Returns:
            Cancelled ScheduledNotification
        """
        for client_id, notifications in self._scheduled.items():
            for notification in notifications:
                if notification.schedule_id == schedule_id:
                    if notification.status == ScheduleStatus.PENDING:
                        notification.status = ScheduleStatus.CANCELLED
                        logger.info(f"Cancelled schedule {schedule_id}")
                        return notification
        return None

    def get_client_schedules(
        self,
        client_id: str,
        include_sent: bool = False
    ) -> List[ScheduledNotification]:
        """
        Get schedules for a client.

        Args:
            client_id: Client identifier
            include_sent: Include already sent notifications

        Returns:
            List of ScheduledNotification
        """
        notifications = self._scheduled.get(client_id, [])

        if not include_sent:
            notifications = [
                n for n in notifications
                if n.status in [ScheduleStatus.PENDING, ScheduleStatus.QUEUED]
            ]

        return sorted(notifications, key=lambda n: n.scheduled_for)

    def get_upcoming_schedules(
        self,
        hours: int = 24
    ) -> List[ScheduledNotification]:
        """
        Get schedules coming up in the next hours.

        Args:
            hours: Hours to look ahead

        Returns:
            List of upcoming ScheduledNotification
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)

        upcoming = []
        for notifications in self._scheduled.values():
            for notification in notifications:
                if (notification.status == ScheduleStatus.PENDING
                    and now <= notification.scheduled_for <= cutoff):
                    upcoming.append(notification)

        return sorted(upcoming, key=lambda n: n.scheduled_for)

    def get_schedule_summary(self) -> Dict[str, Any]:
        """Get summary of all scheduled notifications."""
        total = 0
        by_status = {s.value: 0 for s in ScheduleStatus}
        by_channel = {}

        for notifications in self._scheduled.values():
            for notification in notifications:
                total += 1
                by_status[notification.status.value] += 1
                by_channel[notification.channel] = by_channel.get(notification.channel, 0) + 1

        return {
            "total_scheduled": total,
            "pending": by_status.get("pending", 0),
            "by_status": by_status,
            "by_channel": by_channel,
            "upcoming_24h": len(self.get_upcoming_schedules(24)),
        }

    def calculate_optimal_send_time(
        self,
        timezone: str = "UTC",
        preferred_days: Optional[List[int]] = None
    ) -> datetime:
        """
        Calculate the optimal send time for a notification.

        Args:
            timezone: Target timezone
            preferred_days: Preferred days (0=Monday)

        Returns:
            Optimal datetime to send
        """
        now = datetime.utcnow()

        # Default to business days
        if preferred_days is None:
            preferred_days = [0, 1, 2, 3, 4]  # Monday-Friday

        # Find next preferred day
        days_ahead = 0
        for i in range(7):
            check_day = (now.weekday() + i) % 7
            if check_day in preferred_days:
                days_ahead = i
                break

        target_date = now + timedelta(days=days_ahead)
        optimal_time = self.OPTIMAL_SEND_TIMES.get(target_date.weekday(), time(10, 0))

        if optimal_time is None:
            optimal_time = time(10, 0)

        return datetime.combine(target_date.date(), optimal_time)
