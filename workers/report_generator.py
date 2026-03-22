"""
Report Generator Worker.

Handles generating and delivering reports.

Features:
- Generate various report types
- Schedule reports
- Deliver reports via multiple channels
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ReportStatus(str, Enum):
    """Status of report generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    DELIVERED = "delivered"


class ReportType(str, Enum):
    """Types of reports."""
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    AGENT_PERFORMANCE = "agent_performance"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    SLA_COMPLIANCE = "sla_compliance"
    FINANCIAL_SUMMARY = "financial_summary"


@dataclass
class ReportRecord:
    """Record of a generated report."""
    report_id: str
    company_id: str
    report_type: ReportType
    status: ReportStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    scheduled_for: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReportGeneratorWorker:
    """
    Worker for generating and delivering reports.

    Features:
    - Generate various report types
    - Schedule reports
    - Deliver reports

    Example:
        worker = ReportGeneratorWorker()
        result = await worker.generate_report("comp_123", "weekly_summary")
    """

    def __init__(self) -> None:
        """Initialize Report Generator Worker."""
        self._reports: Dict[str, ReportRecord] = {}
        self._schedules: Dict[str, Dict[str, Any]] = {}

        logger.info({
            "event": "report_generator_worker_initialized"
        })

    async def generate_report(
        self,
        company_id: str,
        report_type: str,
        date_range: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a report for a company.

        Args:
            company_id: Company identifier
            report_type: Type of report to generate
            date_range: Optional date range for report
            metadata: Additional metadata

        Returns:
            Dict with report generation result
        """
        report_id = f"report_{uuid.uuid4().hex[:8]}"

        logger.info({
            "event": "report_generation_started",
            "report_id": report_id,
            "company_id": company_id,
            "report_type": report_type
        })

        try:
            rep_type = ReportType(report_type)
        except ValueError:
            rep_type = ReportType.WEEKLY_SUMMARY

        record = ReportRecord(
            report_id=report_id,
            company_id=company_id,
            report_type=rep_type,
            status=ReportStatus.GENERATING,
            metadata=metadata or {}
        )

        try:
            # Generate report data based on type
            report_data = await self._generate_report_data(
                company_id, rep_type, date_range
            )

            record.data = report_data
            record.status = ReportStatus.COMPLETED
            record.generated_at = datetime.now(timezone.utc)

            self._reports[report_id] = record

            logger.info({
                "event": "report_generated",
                "report_id": report_id,
                "company_id": company_id,
                "report_type": rep_type.value
            })

            return {
                "success": True,
                "status": ReportStatus.COMPLETED.value,
                "report_id": report_id,
                "company_id": company_id,
                "report_type": rep_type.value,
                "generated_at": record.generated_at.isoformat(),
                "data": report_data
            }

        except Exception as e:
            record.status = ReportStatus.FAILED
            self._reports[report_id] = record

            logger.error({
                "event": "report_generation_failed",
                "report_id": report_id,
                "error": str(e)
            })

            return {
                "success": False,
                "status": ReportStatus.FAILED.value,
                "error": str(e),
                "report_id": report_id
            }

    async def _generate_report_data(
        self,
        company_id: str,
        report_type: ReportType,
        date_range: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Generate report data based on type.

        Args:
            company_id: Company identifier
            report_type: Type of report
            date_range: Date range for report

        Returns:
            Dict with report data
        """
        # Simulate async data gathering
        await asyncio.sleep(0.01)

        base_data = {
            "company_id": company_id,
            "report_type": report_type.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date_range": date_range or {
                "start": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                "end": datetime.now(timezone.utc).isoformat()
            }
        }

        if report_type == ReportType.WEEKLY_SUMMARY:
            base_data["summary"] = {
                "total_tickets": 150,
                "resolved_tickets": 142,
                "average_resolution_time_hours": 4.5,
                "customer_satisfaction_score": 92,
                "escalation_count": 3
            }

        elif report_type == ReportType.AGENT_PERFORMANCE:
            base_data["agents"] = [
                {"agent_id": "agent_1", "tickets_resolved": 45, "avg_time_minutes": 12},
                {"agent_id": "agent_2", "tickets_resolved": 52, "avg_time_minutes": 10},
                {"agent_id": "agent_3", "tickets_resolved": 38, "avg_time_minutes": 15}
            ]

        elif report_type == ReportType.CUSTOMER_SATISFACTION:
            base_data["satisfaction"] = {
                "overall_score": 92,
                "positive_feedback_count": 128,
                "negative_feedback_count": 14,
                "neutral_feedback_count": 8
            }

        elif report_type == ReportType.SLA_COMPLIANCE:
            base_data["sla"] = {
                "compliance_rate": 96.5,
                "breaches": 5,
                "near_breaches": 12,
                "average_response_time_minutes": 8
            }

        elif report_type == ReportType.FINANCIAL_SUMMARY:
            base_data["financial"] = {
                "total_refunds_processed": 15,
                "total_refund_amount": 1250.00,
                "average_refund_amount": 83.33,
                "approval_rate": 0.92
            }

        return base_data

    async def schedule_report(
        self,
        company_id: str,
        schedule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Schedule a recurring report.

        Args:
            company_id: Company identifier
            schedule: Schedule configuration with:
                - report_type: Type of report
                - frequency: daily, weekly, monthly
                - time: Time to generate
                - recipients: List of recipients

        Returns:
            Dict with scheduling result
        """
        schedule_id = f"schedule_{uuid.uuid4().hex[:8]}"

        logger.info({
            "event": "report_scheduled",
            "schedule_id": schedule_id,
            "company_id": company_id,
            "frequency": schedule.get("frequency")
        })

        self._schedules[schedule_id] = {
            "schedule_id": schedule_id,
            "company_id": company_id,
            "report_type": schedule.get("report_type", "weekly_summary"),
            "frequency": schedule.get("frequency", "weekly"),
            "time": schedule.get("time", "09:00"),
            "recipients": schedule.get("recipients", []),
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return {
            "success": True,
            "schedule_id": schedule_id,
            "company_id": company_id,
            "next_run": self._calculate_next_run(schedule).isoformat()
        }

    def _calculate_next_run(
        self,
        schedule: Dict[str, Any]
    ) -> datetime:
        """Calculate next run time for scheduled report."""
        now = datetime.now(timezone.utc)
        frequency = schedule.get("frequency", "weekly")

        if frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "monthly":
            return now + timedelta(days=30)

        return now + timedelta(days=7)

    async def deliver_report(
        self,
        report_id: str,
        recipients: Optional[List[str]] = None,
        delivery_method: str = "email"
    ) -> Dict[str, Any]:
        """
        Deliver a generated report.

        Args:
            report_id: Report to deliver
            recipients: Optional override recipients
            delivery_method: How to deliver (email, webhook, etc.)

        Returns:
            Dict with delivery result
        """
        report = self._reports.get(report_id)

        if not report:
            return {
                "success": False,
                "error": f"Report {report_id} not found"
            }

        if report.status != ReportStatus.COMPLETED:
            return {
                "success": False,
                "error": f"Report not ready (status: {report.status.value})"
            }

        logger.info({
            "event": "report_delivering",
            "report_id": report_id,
            "delivery_method": delivery_method
        })

        # Simulate delivery
        await asyncio.sleep(0.01)

        report.delivered_at = datetime.now(timezone.utc)
        report.status = ReportStatus.DELIVERED

        logger.info({
            "event": "report_delivered",
            "report_id": report_id,
            "delivered_at": report.delivered_at.isoformat()
        })

        return {
            "success": True,
            "status": ReportStatus.DELIVERED.value,
            "report_id": report_id,
            "delivered_at": report.delivered_at.isoformat(),
            "delivery_method": delivery_method
        }

    def get_report(
        self,
        report_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a report by ID.

        Args:
            report_id: Report identifier

        Returns:
            Report data or None
        """
        report = self._reports.get(report_id)
        if report:
            return {
                "report_id": report.report_id,
                "company_id": report.company_id,
                "report_type": report.report_type.value,
                "status": report.status.value,
                "generated_at": report.generated_at.isoformat() if report.generated_at else None,
                "data": report.data
            }
        return None

    def get_company_reports(
        self,
        company_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get reports for a company.

        Args:
            company_id: Company identifier
            limit: Maximum records

        Returns:
            List of reports
        """
        reports = [
            r for r in self._reports.values()
            if r.company_id == company_id
        ]

        reports = sorted(reports, key=lambda r: r.created_at, reverse=True)

        return [
            {
                "report_id": r.report_id,
                "report_type": r.report_type.value,
                "status": r.status.value,
                "created_at": r.created_at.isoformat()
            }
            for r in reports[:limit]
        ]

    def get_status(self) -> Dict[str, Any]:
        """
        Get worker status.

        Returns:
            Dict with status information
        """
        return {
            "worker_type": "report_generator",
            "total_reports": len(self._reports),
            "scheduled_reports": len(self._schedules)
        }


# ARQ worker function
async def generate_report(
    ctx: Dict[str, Any],
    company_id: str,
    report_type: str
) -> Dict[str, Any]:
    """
    ARQ worker function for generating reports.

    Args:
        ctx: ARQ context
        company_id: Company identifier
        report_type: Type of report

    Returns:
        Report generation result
    """
    worker = ReportGeneratorWorker()
    return await worker.generate_report(company_id, report_type)


def get_report_generator_worker() -> ReportGeneratorWorker:
    """
    Get a ReportGeneratorWorker instance.

    Returns:
        ReportGeneratorWorker instance
    """
    return ReportGeneratorWorker()
