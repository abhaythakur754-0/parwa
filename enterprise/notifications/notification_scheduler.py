# Notification Scheduler - Week 48 Builder 1
# Scheduled notification management and delivery

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
# Simple cron parser (no external dependency)


class ScheduleType(Enum):
    ONCE = "once"
    RECURRING = "recurring"
    INTERVAL = "interval"


class ScheduleStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledNotification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    schedule_type: ScheduleType = ScheduleType.ONCE
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    cron_expression: Optional[str] = None
    interval_minutes: Optional[int] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    notification_template: Dict[str, Any] = field(default_factory=dict)
    target_users: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class NotificationScheduler:
    """Manages scheduled and recurring notifications"""

    def __init__(self):
        self._schedules: Dict[str, ScheduledNotification] = {}
        self._callbacks: List[Callable] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def create_once_schedule(
        self,
        tenant_id: str,
        name: str,
        run_at: datetime,
        notification_template: Dict[str, Any],
        target_users: List[str]
    ) -> ScheduledNotification:
        """Create a one-time scheduled notification"""
        schedule = ScheduledNotification(
            tenant_id=tenant_id,
            name=name,
            schedule_type=ScheduleType.ONCE,
            next_run_at=run_at,
            notification_template=notification_template,
            target_users=target_users
        )
        self._schedules[schedule.id] = schedule
        return schedule

    def create_recurring_schedule(
        self,
        tenant_id: str,
        name: str,
        cron_expression: str,
        notification_template: Dict[str, Any],
        target_users: List[str],
        max_runs: Optional[int] = None
    ) -> ScheduledNotification:
        """Create a recurring notification with cron expression"""
        next_run = self._parse_cron_next_run(cron_expression)

        schedule = ScheduledNotification(
            tenant_id=tenant_id,
            name=name,
            schedule_type=ScheduleType.RECURRING,
            cron_expression=cron_expression,
            next_run_at=next_run,
            notification_template=notification_template,
            target_users=target_users,
            max_runs=max_runs
        )
        self._schedules[schedule.id] = schedule
        return schedule

    def _parse_cron_next_run(self, cron_expression: str) -> datetime:
        """Parse cron expression and return next run time (simplified)"""
        # Simplified: support common patterns like "*/5 * * * *" (every 5 min)
        parts = cron_expression.split()
        if len(parts) == 5:
            minute, hour, day, month, weekday = parts
            now = datetime.utcnow()
            
            # Handle */N pattern for minutes
            if minute.startswith('*/'):
                interval = int(minute[2:])
                next_minute = ((now.minute // interval) + 1) * interval
                if next_minute >= 60:
                    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                return now.replace(minute=next_minute, second=0, microsecond=0)
            
            # Handle hourly pattern
            if minute == '0' and hour == '*':
                return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            
            # Handle daily pattern
            if minute == '0' and hour == '0':
                return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Default: run in 1 hour
        return datetime.utcnow() + timedelta(hours=1)

    def create_interval_schedule(
        self,
        tenant_id: str,
        name: str,
        interval_minutes: int,
        notification_template: Dict[str, Any],
        target_users: List[str],
        start_at: Optional[datetime] = None,
        max_runs: Optional[int] = None
    ) -> ScheduledNotification:
        """Create an interval-based recurring notification"""
        next_run = start_at or datetime.utcnow() + timedelta(minutes=interval_minutes)

        schedule = ScheduledNotification(
            tenant_id=tenant_id,
            name=name,
            schedule_type=ScheduleType.INTERVAL,
            interval_minutes=interval_minutes,
            next_run_at=next_run,
            notification_template=notification_template,
            target_users=target_users,
            max_runs=max_runs
        )
        self._schedules[schedule.id] = schedule
        return schedule

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for when notifications are triggered"""
        self._callbacks.append(callback)

    async def _trigger_callbacks(self, schedule: ScheduledNotification) -> None:
        """Trigger all registered callbacks"""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(schedule)
                else:
                    callback(schedule)
            except Exception:
                pass

    def get_due_schedules(self) -> List[ScheduledNotification]:
        """Get all schedules that are due to run"""
        now = datetime.utcnow()
        due = []
        for schedule in self._schedules.values():
            if schedule.status != ScheduleStatus.ACTIVE:
                continue
            if schedule.next_run_at and schedule.next_run_at <= now:
                due.append(schedule)
        return due

    async def process_due_schedules(self) -> List[ScheduledNotification]:
        """Process all due schedules"""
        due = self.get_due_schedules()
        processed = []

        for schedule in due:
            await self._trigger_callbacks(schedule)
            schedule.last_run_at = datetime.utcnow()
            schedule.run_count += 1
            schedule.updated_at = datetime.utcnow()

            if schedule.schedule_type == ScheduleType.ONCE:
                schedule.status = ScheduleStatus.COMPLETED
            elif schedule.max_runs and schedule.run_count >= schedule.max_runs:
                schedule.status = ScheduleStatus.COMPLETED
            else:
                self._calculate_next_run(schedule)

            processed.append(schedule)

        return processed

    def _calculate_next_run(self, schedule: ScheduledNotification) -> None:
        """Calculate the next run time for a schedule"""
        now = datetime.utcnow()

        if schedule.schedule_type == ScheduleType.RECURRING and schedule.cron_expression:
            schedule.next_run_at = self._parse_cron_next_run(schedule.cron_expression)
        elif schedule.schedule_type == ScheduleType.INTERVAL and schedule.interval_minutes:
            schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)

    def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.PAUSED
        schedule.updated_at = datetime.utcnow()
        return True

    def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule or schedule.status != ScheduleStatus.PAUSED:
            return False
        schedule.status = ScheduleStatus.ACTIVE
        self._calculate_next_run(schedule)
        schedule.updated_at = datetime.utcnow()
        return True

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.CANCELLED
        schedule.updated_at = datetime.utcnow()
        return True

    def get_schedule(self, schedule_id: str) -> Optional[ScheduledNotification]:
        """Get a schedule by ID"""
        return self._schedules.get(schedule_id)

    def get_schedules_by_tenant(self, tenant_id: str) -> List[ScheduledNotification]:
        """Get all schedules for a tenant"""
        return [s for s in self._schedules.values() if s.tenant_id == tenant_id]

    def get_active_schedules(self) -> List[ScheduledNotification]:
        """Get all active schedules"""
        return [s for s in self._schedules.values() if s.status == ScheduleStatus.ACTIVE]

    def update_target_users(self, schedule_id: str, users: List[str]) -> bool:
        """Update target users for a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.target_users = users
        schedule.updated_at = datetime.utcnow()
        return True

    def update_template(self, schedule_id: str, template: Dict[str, Any]) -> bool:
        """Update notification template for a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.notification_template = template
        schedule.updated_at = datetime.utcnow()
        return True

    async def start(self, check_interval_seconds: int = 60) -> None:
        """Start the scheduler loop"""
        self._running = True
        while self._running:
            await self.process_due_schedules()
            await asyncio.sleep(check_interval_seconds)

    def stop(self) -> None:
        """Stop the scheduler loop"""
        self._running = False

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        active = len([s for s in self._schedules.values() if s.status == ScheduleStatus.ACTIVE])
        paused = len([s for s in self._schedules.values() if s.status == ScheduleStatus.PAUSED])
        completed = len([s for s in self._schedules.values() if s.status == ScheduleStatus.COMPLETED])
        cancelled = len([s for s in self._schedules.values() if s.status == ScheduleStatus.CANCELLED])

        total_runs = sum(s.run_count for s in self._schedules.values())

        return {
            "total_schedules": len(self._schedules),
            "active": active,
            "paused": paused,
            "completed": completed,
            "cancelled": cancelled,
            "total_runs_executed": total_runs
        }
