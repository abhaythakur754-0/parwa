# Success Tracker - Week 47 Builder 5
# Success/failure tracking for webhook deliveries

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class DeliveryResult(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RETRY = "retry"


@dataclass
class DeliveryRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    tenant_id: str = ""
    url: str = ""
    result: DeliveryResult = DeliveryResult.SUCCESS
    http_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    attempt_number: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WebhookStats:
    webhook_id: str = ""
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    timeout_count: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None


@dataclass
class TenantStats:
    tenant_id: str = ""
    total_webhooks: int = 0
    total_deliveries: int = 0
    overall_success_rate: float = 0.0
    active_webhooks: int = 0
    failing_webhooks: int = 0


class SuccessTracker:
    """Tracks webhook delivery success/failure rates"""

    def __init__(self):
        self._records: List[DeliveryRecord] = []
        self._webhook_stats: Dict[str, WebhookStats] = {}
        self._tenant_stats: Dict[str, TenantStats] = {}
        self._retention_days = 30

    def record_delivery(
        self,
        webhook_id: str,
        tenant_id: str,
        url: str,
        result: DeliveryResult,
        http_status: Optional[int] = None,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        attempt_number: int = 1
    ) -> DeliveryRecord:
        """Record a delivery attempt"""
        record = DeliveryRecord(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            url=url,
            result=result,
            http_status=http_status,
            response_time_ms=response_time_ms,
            error_message=error_message,
            attempt_number=attempt_number
        )
        self._records.append(record)
        self._update_stats(record)
        return record

    def _update_stats(self, record: DeliveryRecord) -> None:
        """Update statistics after recording"""
        # Update webhook stats
        if record.webhook_id not in self._webhook_stats:
            self._webhook_stats[record.webhook_id] = WebhookStats(
                webhook_id=record.webhook_id
            )

        stats = self._webhook_stats[record.webhook_id]
        stats.total_deliveries += 1

        if record.result == DeliveryResult.SUCCESS:
            stats.successful_deliveries += 1
            stats.last_success = record.timestamp
        elif record.result == DeliveryResult.TIMEOUT:
            stats.timeout_count += 1
            stats.last_failure = record.timestamp
        else:
            stats.failed_deliveries += 1
            stats.last_failure = record.timestamp

        # Calculate success rate
        stats.success_rate = (
            stats.successful_deliveries / stats.total_deliveries * 100
            if stats.total_deliveries > 0 else 0
        )

        # Update average response time
        if record.response_time_ms:
            if stats.avg_response_time_ms == 0:
                stats.avg_response_time_ms = record.response_time_ms
            else:
                stats.avg_response_time_ms = (
                    stats.avg_response_time_ms + record.response_time_ms
                ) / 2

        # Update tenant stats
        if record.tenant_id not in self._tenant_stats:
            self._tenant_stats[record.tenant_id] = TenantStats(
                tenant_id=record.tenant_id
            )

        tenant = self._tenant_stats[record.tenant_id]
        tenant.total_deliveries += 1

    def get_webhook_stats(self, webhook_id: str) -> Optional[WebhookStats]:
        """Get statistics for a webhook"""
        return self._webhook_stats.get(webhook_id)

    def get_tenant_stats(self, tenant_id: str) -> Optional[TenantStats]:
        """Get statistics for a tenant"""
        return self._tenant_stats.get(tenant_id)

    def get_success_rate(
        self,
        webhook_id: str,
        since: Optional[datetime] = None
    ) -> float:
        """Get success rate for a webhook"""
        records = self._get_records_since(webhook_id, since)
        if not records:
            return 0.0

        successful = sum(1 for r in records if r.result == DeliveryResult.SUCCESS)
        return (successful / len(records)) * 100

    def get_failure_rate(
        self,
        webhook_id: str,
        since: Optional[datetime] = None
    ) -> float:
        """Get failure rate for a webhook"""
        return 100 - self.get_success_rate(webhook_id, since)

    def _get_records_since(
        self,
        webhook_id: str,
        since: Optional[datetime] = None
    ) -> List[DeliveryRecord]:
        """Get records since a timestamp"""
        records = [r for r in self._records if r.webhook_id == webhook_id]
        if since:
            records = [r for r in records if r.timestamp >= since]
        return records

    def get_failing_webhooks(
        self,
        threshold: float = 50.0
    ) -> List[WebhookStats]:
        """Get webhooks below success threshold"""
        return [
            stats for stats in self._webhook_stats.values()
            if stats.success_rate < threshold
        ]

    def get_healthy_webhooks(
        self,
        threshold: float = 95.0
    ) -> List[WebhookStats]:
        """Get webhooks above success threshold"""
        return [
            stats for stats in self._webhook_stats.values()
            if stats.success_rate >= threshold
        ]

    def get_recent_failures(
        self,
        webhook_id: str,
        count: int = 10
    ) -> List[DeliveryRecord]:
        """Get recent failures for a webhook"""
        records = [
            r for r in self._records
            if r.webhook_id == webhook_id and r.result != DeliveryResult.SUCCESS
        ]
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:count]

    def get_error_summary(
        self,
        webhook_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get summary of error types"""
        errors: Dict[str, int] = {}
        records = self._records

        if webhook_id:
            records = [r for r in records if r.webhook_id == webhook_id]

        for record in records:
            if record.result != DeliveryResult.SUCCESS:
                error_key = record.error_message or "unknown"
                errors[error_key] = errors.get(error_key, 0) + 1

        return errors

    def get_hourly_stats(
        self,
        webhook_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get hourly statistics"""
        now = datetime.utcnow()
        hourly = []

        for i in range(hours):
            hour_start = now - timedelta(hours=i+1)
            hour_end = now - timedelta(hours=i)

            records = [
                r for r in self._records
                if r.webhook_id == webhook_id
                and hour_start <= r.timestamp < hour_end
            ]

            successful = sum(1 for r in records if r.result == DeliveryResult.SUCCESS)

            hourly.append({
                "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                "total": len(records),
                "successful": successful,
                "failed": len(records) - successful,
                "success_rate": (successful / len(records) * 100) if records else 0
            })

        return hourly

    def cleanup_old_records(self) -> int:
        """Remove records older than retention period"""
        cutoff = datetime.utcnow() - timedelta(days=self._retention_days)
        initial_count = len(self._records)
        self._records = [r for r in self._records if r.timestamp >= cutoff]
        return initial_count - len(self._records)

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global delivery statistics"""
        total = len(self._records)
        successful = sum(1 for r in self._records if r.result == DeliveryResult.SUCCESS)
        failed = sum(1 for r in self._records if r.result == DeliveryResult.FAILURE)
        timeouts = sum(1 for r in self._records if r.result == DeliveryResult.TIMEOUT)

        return {
            "total_deliveries": total,
            "successful": successful,
            "failed": failed,
            "timeouts": timeouts,
            "overall_success_rate": (successful / total * 100) if total > 0 else 0,
            "total_webhooks_tracked": len(self._webhook_stats),
            "total_tenants_tracked": len(self._tenant_stats)
        }
