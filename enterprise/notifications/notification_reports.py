# Notification Reports - Week 48 Builder 5
# Report generation for notification analytics

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json


class ReportType(Enum):
    SUMMARY = "summary"
    DELIVERY = "delivery"
    ENGAGEMENT = "engagement"
    CHANNEL = "channel"
    TREND = "trend"
    CUSTOM = "custom"


class ReportFormat(Enum):
    JSON = "json"
    CSV = "csv"
    HTML = "html"


class ReportPeriod(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class Report:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    report_type: ReportType = ReportType.SUMMARY
    period: ReportPeriod = ReportPeriod.DAILY
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    format: ReportFormat = ReportFormat.JSON
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReportConfig:
    include_channels: List[str] = field(default_factory=list)
    include_metrics: List[str] = field(default_factory=list)
    compare_with_previous: bool = False
    include_charts: bool = False
    group_by: Optional[str] = None


class NotificationReports:
    """Report generation for notification analytics"""

    def __init__(self, analytics=None, engagement=None):
        self._analytics = analytics
        self._engagement = engagement
        self._reports: Dict[str, Report] = {}
        self._templates: Dict[str, str] = {}

    def set_analytics(self, analytics) -> None:
        """Set the analytics engine"""
        self._analytics = analytics

    def set_engagement(self, engagement) -> None:
        """Set the engagement tracker"""
        self._engagement = engagement

    def generate_summary_report(
        self,
        tenant_id: str,
        period: ReportPeriod = ReportPeriod.DAILY,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Report:
        """Generate a summary report"""
        now = datetime.utcnow()

        if not start_time or not end_time:
            if period == ReportPeriod.DAILY:
                start_time = now - timedelta(days=1)
            elif period == ReportPeriod.WEEKLY:
                start_time = now - timedelta(weeks=1)
            else:
                start_time = now - timedelta(days=30)
            end_time = now

        data = {
            "tenant_id": tenant_id,
            "period": period.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "channels": {},
            "totals": {
                "sent": 0,
                "delivered": 0,
                "failed": 0,
                "opened": 0,
                "clicked": 0
            }
        }

        if self._analytics:
            from enterprise.notifications.notification_analytics import NotificationChannel
            for channel in NotificationChannel:
                metrics = self._analytics.get_channel_metrics(
                    tenant_id, channel, start_time, end_time
                )
                data["channels"][channel.value] = {
                    "sent": metrics.total_sent,
                    "delivered": metrics.total_delivered,
                    "failed": metrics.total_failed,
                    "delivery_rate": round(metrics.delivery_rate, 2),
                    "open_rate": round(metrics.open_rate, 2),
                    "click_rate": round(metrics.click_rate, 2)
                }
                data["totals"]["sent"] += metrics.total_sent
                data["totals"]["delivered"] += metrics.total_delivered
                data["totals"]["failed"] += metrics.total_failed
                data["totals"]["opened"] += metrics.total_opened
                data["totals"]["clicked"] += metrics.total_clicked

        # Calculate overall rates
        if data["totals"]["sent"] > 0:
            data["totals"]["delivery_rate"] = round(
                data["totals"]["delivered"] / data["totals"]["sent"] * 100, 2
            )
        else:
            data["totals"]["delivery_rate"] = 0

        report = Report(
            tenant_id=tenant_id,
            name=f"Summary Report - {period.value}",
            report_type=ReportType.SUMMARY,
            period=period,
            start_time=start_time,
            end_time=end_time,
            data=data
        )

        self._reports[report.id] = report
        return report

    def generate_engagement_report(
        self,
        tenant_id: str,
        period: ReportPeriod = ReportPeriod.WEEKLY
    ) -> Report:
        """Generate an engagement report"""
        now = datetime.utcnow()

        if period == ReportPeriod.DAILY:
            start_time = now - timedelta(days=1)
        elif period == ReportPeriod.WEEKLY:
            start_time = now - timedelta(weeks=1)
        else:
            start_time = now - timedelta(days=30)
        end_time = now

        data = {
            "tenant_id": tenant_id,
            "period": period.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "engagement_metrics": {},
            "device_breakdown": {},
            "top_clicked_urls": []
        }

        if self._engagement:
            data["engagement_metrics"] = self._engagement.get_metrics()
            data["device_breakdown"] = self._engagement.get_engagement_by_device(tenant_id)
            data["top_clicked_urls"] = self._engagement.get_top_clicked_urls(tenant_id)

        report = Report(
            tenant_id=tenant_id,
            name=f"Engagement Report - {period.value}",
            report_type=ReportType.ENGAGEMENT,
            period=period,
            start_time=start_time,
            end_time=end_time,
            data=data
        )

        self._reports[report.id] = report
        return report

    def generate_channel_comparison_report(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Report:
        """Generate channel comparison report"""
        now = datetime.utcnow()
        if not start_time:
            start_time = now - timedelta(days=7)
        if not end_time:
            end_time = now

        data = {
            "tenant_id": tenant_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "channels": {},
            "ranking": []
        }

        if self._analytics:
            from enterprise.notifications.notification_analytics import NotificationChannel
            channel_stats = []

            for channel in NotificationChannel:
                metrics = self._analytics.get_channel_metrics(
                    tenant_id, channel, start_time, end_time
                )
                data["channels"][channel.value] = {
                    "sent": metrics.total_sent,
                    "delivery_rate": metrics.delivery_rate,
                    "open_rate": metrics.open_rate,
                    "click_rate": metrics.click_rate
                }
                channel_stats.append({
                    "channel": channel.value,
                    "delivery_rate": metrics.delivery_rate
                })

            # Rank by delivery rate
            data["ranking"] = sorted(
                channel_stats,
                key=lambda x: x["delivery_rate"],
                reverse=True
            )

        report = Report(
            tenant_id=tenant_id,
            name="Channel Comparison Report",
            report_type=ReportType.CHANNEL,
            start_time=start_time,
            end_time=end_time,
            data=data
        )

        self._reports[report.id] = report
        return report

    def generate_trend_report(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Report:
        """Generate trend report"""
        now = datetime.utcnow()
        start_time = now - timedelta(days=days)
        end_time = now

        data = {
            "tenant_id": tenant_id,
            "period_days": days,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "trends": {}
        }

        if self._analytics:
            from enterprise.notifications.notification_analytics import MetricPeriod
            data["trends"] = self._analytics.get_delivery_trends(tenant_id, days)

        report = Report(
            tenant_id=tenant_id,
            name=f"Trend Report - {days} Days",
            report_type=ReportType.TREND,
            start_time=start_time,
            end_time=end_time,
            data=data
        )

        self._reports[report.id] = report
        return report

    def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by ID"""
        return self._reports.get(report_id)

    def get_reports_by_tenant(self, tenant_id: str) -> List[Report]:
        """Get all reports for a tenant"""
        return [r for r in self._reports.values() if r.tenant_id == tenant_id]

    def export_report_json(self, report_id: str) -> Optional[str]:
        """Export report as JSON"""
        report = self._reports.get(report_id)
        if not report:
            return None

        export_data = {
            "id": report.id,
            "tenant_id": report.tenant_id,
            "name": report.name,
            "report_type": report.report_type.value,
            "period": report.period.value,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat(),
            "data": report.data,
            "created_at": report.created_at.isoformat()
        }

        return json.dumps(export_data, indent=2)

    def export_report_csv(self, report_id: str) -> Optional[str]:
        """Export report as CSV"""
        report = self._reports.get(report_id)
        if not report:
            return None

        # Simple CSV export for summary reports
        lines = ["metric,value"]
        for key, value in report.data.get("totals", {}).items():
            lines.append(f"{key},{value}")

        return "\n".join(lines)

    def delete_report(self, report_id: str) -> bool:
        """Delete a report"""
        if report_id in self._reports:
            del self._reports[report_id]
            return True
        return False

    def schedule_report(
        self,
        tenant_id: str,
        report_type: ReportType,
        period: ReportPeriod,
        recipients: List[str]
    ) -> Dict[str, Any]:
        """Schedule a recurring report (placeholder)"""
        return {
            "scheduled": True,
            "tenant_id": tenant_id,
            "report_type": report_type.value,
            "period": period.value,
            "recipients": recipients,
            "next_run": (datetime.utcnow() + timedelta(days=1)).isoformat()
        }
