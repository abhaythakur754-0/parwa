"""
Enterprise Support - SLA Tracker
Track SLA compliance for enterprise clients
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class SLALevel(str, Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SLATarget(BaseModel):
    """SLA target definition"""
    level: SLALevel
    response_time_hours: int
    resolution_time_hours: int
    uptime_percentage: float
    support_hours: str = "24/7"

    model_config = ConfigDict()


class SLAMetrics(BaseModel):
    """SLA metrics"""
    client_id: str
    period_start: datetime
    period_end: datetime
    total_tickets: int = 0
    tickets_within_sla: int = 0
    tickets_breached: int = 0
    avg_response_time_hours: float = 0.0
    avg_resolution_time_hours: float = 0.0
    uptime_percentage: float = 100.0

    model_config = ConfigDict()


class SLATracker:
    """
    Track SLA compliance for enterprise clients.
    """

    DEFAULT_SLA_TARGETS = {
        SLALevel.BASIC: SLATarget(
            level=SLALevel.BASIC,
            response_time_hours=24,
            resolution_time_hours=72,
            uptime_percentage=99.0
        ),
        SLALevel.STANDARD: SLATarget(
            level=SLALevel.STANDARD,
            response_time_hours=8,
            resolution_time_hours=48,
            uptime_percentage=99.5
        ),
        SLALevel.PREMIUM: SLATarget(
            level=SLALevel.PREMIUM,
            response_time_hours=4,
            resolution_time_hours=24,
            uptime_percentage=99.9
        ),
        SLALevel.ENTERPRISE: SLATarget(
            level=SLALevel.ENTERPRISE,
            response_time_hours=1,
            resolution_time_hours=8,
            uptime_percentage=99.99
        )
    }

    def __init__(self):
        self.client_sla_levels: Dict[str, SLALevel] = {}
        self.metrics: Dict[str, List[SLAMetrics]] = {}

    def set_client_sla(self, client_id: str, level: SLALevel) -> None:
        """Set SLA level for a client"""
        self.client_sla_levels[client_id] = level

    def get_sla_target(self, client_id: str) -> SLATarget:
        """Get SLA target for a client"""
        level = self.client_sla_levels.get(client_id, SLALevel.STANDARD)
        return self.DEFAULT_SLA_TARGETS[level]

    def check_response_sla(
        self,
        client_id: str,
        created_at: datetime,
        first_response_at: datetime
    ) -> bool:
        """Check if response is within SLA"""
        target = self.get_sla_target(client_id)
        response_time = (first_response_at - created_at).total_seconds() / 3600
        return response_time <= target.response_time_hours

    def check_resolution_sla(
        self,
        client_id: str,
        created_at: datetime,
        resolved_at: datetime
    ) -> bool:
        """Check if resolution is within SLA"""
        target = self.get_sla_target(client_id)
        resolution_time = (resolved_at - created_at).total_seconds() / 3600
        return resolution_time <= target.resolution_time_hours

    def record_metrics(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime,
        total_tickets: int,
        within_sla: int,
        avg_response_hours: float,
        avg_resolution_hours: float
    ) -> SLAMetrics:
        """Record SLA metrics"""
        metrics = SLAMetrics(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            total_tickets=total_tickets,
            tickets_within_sla=within_sla,
            tickets_breached=total_tickets - within_sla,
            avg_response_time_hours=avg_response_hours,
            avg_resolution_time_hours=avg_resolution_hours
        )

        if client_id not in self.metrics:
            self.metrics[client_id] = []
        self.metrics[client_id].append(metrics)

        return metrics

    def get_sla_compliance(self, client_id: str) -> float:
        """Get SLA compliance percentage"""
        if client_id not in self.metrics or not self.metrics[client_id]:
            return 100.0

        latest = self.metrics[client_id][-1]
        if latest.total_tickets == 0:
            return 100.0

        return (latest.tickets_within_sla / latest.total_tickets) * 100
