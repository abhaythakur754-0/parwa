"""
Enterprise Analytics - Report Scheduler
Schedule automated reports for enterprise clients
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class ScheduleFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ScheduledReport(BaseModel):
    """Scheduled report definition"""
    report_id: str = Field(default_factory=lambda: f"rpt_{uuid.uuid4().hex[:8]}")
    name: str
    frequency: ScheduleFrequency
    recipients: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    active: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

    model_config = ConfigDict()


class ReportScheduler:
    """
    Schedule automated reports for enterprise clients.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.scheduled_reports: Dict[str, ScheduledReport] = {}

    def create_schedule(
        self,
        name: str,
        frequency: ScheduleFrequency,
        recipients: List[str],
        metrics: List[str]
    ) -> ScheduledReport:
        """Create a scheduled report"""
        report = ScheduledReport(
            name=name,
            frequency=frequency,
            recipients=recipients,
            metrics=metrics,
            next_run=self._calculate_next_run(frequency)
        )
        self.scheduled_reports[report.report_id] = report
        return report

    def _calculate_next_run(self, frequency: ScheduleFrequency) -> datetime:
        """Calculate next run time"""
        now = datetime.utcnow()
        if frequency == ScheduleFrequency.DAILY:
            return now + timedelta(days=1)
        elif frequency == ScheduleFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif frequency == ScheduleFrequency.MONTHLY:
            return now + timedelta(days=30)
        else:
            return now + timedelta(days=90)

    def get_due_reports(self) -> List[ScheduledReport]:
        """Get reports that are due to run"""
        now = datetime.utcnow()
        return [
            r for r in self.scheduled_reports.values()
            if r.active and r.next_run and r.next_run <= now
        ]

    def mark_run(self, report_id: str) -> bool:
        """Mark a report as run"""
        if report_id not in self.scheduled_reports:
            return False

        report = self.scheduled_reports[report_id]
        report.last_run = datetime.utcnow()
        report.next_run = self._calculate_next_run(report.frequency)
        return True

    def pause_schedule(self, report_id: str) -> bool:
        """Pause a scheduled report"""
        if report_id in self.scheduled_reports:
            self.scheduled_reports[report_id].active = False
            return True
        return False

    def resume_schedule(self, report_id: str) -> bool:
        """Resume a paused report"""
        if report_id in self.scheduled_reports:
            self.scheduled_reports[report_id].active = True
            return True
        return False
