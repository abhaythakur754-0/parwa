# Compliance Scheduler - Week 49 Builder 2
# Scheduled compliance checks and automation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid


class ScheduleType(Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ScheduleStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledCheck:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    schedule_type: ScheduleType = ScheduleType.DAILY
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    check_type: str = ""  # Type of compliance check
    parameters: Dict[str, Any] = field(default_factory=dict)
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""


@dataclass
class CheckExecution:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scheduled_check_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "running"
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class ComplianceScheduler:
    """Schedules and manages compliance checks"""

    def __init__(self):
        self._schedules: Dict[str, ScheduledCheck] = {}
        self._executions: List[CheckExecution] = []
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._metrics = {
            "total_schedules": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0
        }

    def register_handler(
        self,
        check_type: str,
        handler: Callable
    ) -> None:
        """Register a handler for a check type"""
        self._handlers[check_type] = handler

    def create_schedule(
        self,
        tenant_id: str,
        name: str,
        schedule_type: ScheduleType,
        check_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        created_by: str = ""
    ) -> ScheduledCheck:
        """Create a new scheduled check"""
        next_run = start_time or self._calculate_next_run(schedule_type)

        schedule = ScheduledCheck(
            tenant_id=tenant_id,
            name=name,
            schedule_type=schedule_type,
            check_type=check_type,
            parameters=parameters or {},
            next_run=next_run,
            created_by=created_by
        )

        self._schedules[schedule.id] = schedule
        self._metrics["total_schedules"] += 1

        return schedule

    def _calculate_next_run(
        self,
        schedule_type: ScheduleType,
        from_time: Optional[datetime] = None
    ) -> datetime:
        """Calculate next run time based on schedule type"""
        base = from_time or datetime.utcnow()

        if schedule_type == ScheduleType.ONCE:
            return base
        elif schedule_type == ScheduleType.DAILY:
            return base + timedelta(days=1)
        elif schedule_type == ScheduleType.WEEKLY:
            return base + timedelta(weeks=1)
        elif schedule_type == ScheduleType.MONTHLY:
            return base + timedelta(days=30)
        elif schedule_type == ScheduleType.QUARTERLY:
            return base + timedelta(days=90)
        elif schedule_type == ScheduleType.YEARLY:
            return base + timedelta(days=365)

        return base

    def execute_check(
        self,
        schedule_id: str
    ) -> Optional[CheckExecution]:
        """Execute a scheduled check"""
        schedule = self._schedules.get(schedule_id)
        if not schedule or schedule.status != ScheduleStatus.ACTIVE:
            return None

        handler = self._handlers.get(schedule.check_type)
        if not handler:
            return None

        execution = CheckExecution(scheduled_check_id=schedule.id)
        self._executions.append(execution)
        self._metrics["total_executions"] += 1

        try:
            # Execute handler (supports both sync and async)
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(handler(schedule.parameters))
                finally:
                    loop.close()
            else:
                result = handler(schedule.parameters)

            execution.results = result or {}
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            self._metrics["successful_executions"] += 1

            # Update schedule
            schedule.last_run = datetime.utcnow()
            schedule.run_count += 1

            if schedule.schedule_type == ScheduleType.ONCE:
                schedule.status = ScheduleStatus.COMPLETED
            elif schedule.max_runs and schedule.run_count >= schedule.max_runs:
                schedule.status = ScheduleStatus.COMPLETED
            else:
                schedule.next_run = self._calculate_next_run(
                    schedule.schedule_type,
                    datetime.utcnow()
                )

        except Exception as e:
            execution.status = "failed"
            execution.errors.append(str(e))
            execution.completed_at = datetime.utcnow()
            self._metrics["failed_executions"] += 1

        return execution

    def get_due_schedules(self) -> List[ScheduledCheck]:
        """Get all schedules that are due"""
        now = datetime.utcnow()
        return [
            s for s in self._schedules.values()
            if s.status == ScheduleStatus.ACTIVE
            and s.next_run
            and s.next_run <= now
        ]

    async def process_due_schedules(self) -> List[CheckExecution]:
        """Process all due schedules"""
        due = self.get_due_schedules()
        results = []

        for schedule in due:
            result = self.execute_check(schedule.id)
            if result:
                results.append(result)

        return results

    def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.PAUSED
        return True

    def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a paused schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule or schedule.status != ScheduleStatus.PAUSED:
            return False
        schedule.status = ScheduleStatus.ACTIVE
        schedule.next_run = self._calculate_next_run(
            schedule.schedule_type,
            datetime.utcnow()
        )
        return True

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.status = ScheduleStatus.CANCELLED
        return True

    def get_schedule(self, schedule_id: str) -> Optional[ScheduledCheck]:
        """Get a schedule by ID"""
        return self._schedules.get(schedule_id)

    def get_schedules_by_tenant(
        self,
        tenant_id: str,
        status: Optional[ScheduleStatus] = None
    ) -> List[ScheduledCheck]:
        """Get all schedules for a tenant"""
        schedules = [s for s in self._schedules.values() if s.tenant_id == tenant_id]
        if status:
            schedules = [s for s in schedules if s.status == status]
        return schedules

    def get_execution(self, execution_id: str) -> Optional[CheckExecution]:
        """Get an execution by ID"""
        for execution in self._executions:
            if execution.id == execution_id:
                return execution
        return None

    def get_executions_by_schedule(
        self,
        schedule_id: str,
        limit: int = 10
    ) -> List[CheckExecution]:
        """Get executions for a schedule"""
        executions = [
            e for e in self._executions
            if e.scheduled_check_id == schedule_id
        ]
        return executions[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get scheduler metrics"""
        active = len([
            s for s in self._schedules.values()
            if s.status == ScheduleStatus.ACTIVE
        ])
        paused = len([
            s for s in self._schedules.values()
            if s.status == ScheduleStatus.PAUSED
        ])

        return {
            **self._metrics,
            "active_schedules": active,
            "paused_schedules": paused,
            "total_executions_stored": len(self._executions)
        }

    def cleanup_old_executions(self, days: int = 30) -> int:
        """Remove old execution records"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        initial_count = len(self._executions)
        self._executions = [e for e in self._executions if e.started_at >= cutoff]
        return initial_count - len(self._executions)

    async def start(self, interval_seconds: int = 60) -> None:
        """Start the scheduler loop"""
        self._running = True
        while self._running:
            await self.process_due_schedules()
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        """Stop the scheduler loop"""
        self._running = False


# Import asyncio at module level for the scheduler
import asyncio
