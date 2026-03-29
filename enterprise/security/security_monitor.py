"""
Enterprise Security - Security Monitor
Security monitoring center for enterprise
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from collections import defaultdict


class MonitorStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SecurityMetric(BaseModel):
    """Security metric"""
    name: str
    value: float
    threshold: float
    status: MonitorStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class SecurityDashboard(BaseModel):
    """Security dashboard"""
    client_id: str
    status: MonitorStatus = MonitorStatus.HEALTHY
    metrics: Dict[str, SecurityMetric] = Field(default_factory=dict)
    active_alerts: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict()


class SecurityMonitor:
    """
    Security monitoring center for enterprise clients.
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.metrics: Dict[str, List[SecurityMetric]] = defaultdict(list)
        self.thresholds: Dict[str, float] = {
            "failed_logins": 100,
            "blocked_requests": 50,
            "vulnerabilities_critical": 0,
            "vulnerabilities_high": 5,
            "threat_events": 10
        }

    def record_metric(self, name: str, value: float) -> SecurityMetric:
        """Record a security metric"""
        threshold = self.thresholds.get(name, float('inf'))
        status = MonitorStatus.HEALTHY

        if value > threshold:
            status = MonitorStatus.CRITICAL
        elif value > threshold * 0.8:
            status = MonitorStatus.WARNING

        metric = SecurityMetric(
            name=name,
            value=value,
            threshold=threshold,
            status=status
        )
        self.metrics[name].append(metric)
        return metric

    def get_dashboard(self) -> SecurityDashboard:
        """Get security dashboard"""
        latest_metrics = {}
        for name, history in self.metrics.items():
            if history:
                latest_metrics[name] = history[-1]

        # Determine overall status
        status = MonitorStatus.HEALTHY
        for metric in latest_metrics.values():
            if metric.status == MonitorStatus.CRITICAL:
                status = MonitorStatus.CRITICAL
                break
            elif metric.status == MonitorStatus.WARNING:
                status = MonitorStatus.WARNING

        return SecurityDashboard(
            client_id=self.client_id,
            status=status,
            metrics=latest_metrics,
            active_alerts=sum(1 for m in latest_metrics.values() if m.status != MonitorStatus.HEALTHY)
        )

    def get_metric_history(self, name: str, hours: int = 24) -> List[SecurityMetric]:
        """Get metric history"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [m for m in self.metrics.get(name, []) if m.timestamp > cutoff]

    def check_thresholds(self) -> List[Dict[str, Any]]:
        """Check all thresholds and return alerts"""
        alerts = []
        latest_metrics = {name: history[-1] for name, history in self.metrics.items() if history}

        for name, metric in latest_metrics.items():
            if metric.status == MonitorStatus.CRITICAL:
                alerts.append({
                    "metric": name,
                    "value": metric.value,
                    "threshold": metric.threshold,
                    "severity": "critical"
                })
            elif metric.status == MonitorStatus.WARNING:
                alerts.append({
                    "metric": name,
                    "value": metric.value,
                    "threshold": metric.threshold,
                    "severity": "warning"
                })

        return alerts
